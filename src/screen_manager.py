"""多屏幕管理器 — Microsoft Treasure Hunt

实现屏幕状态机的核心职责：
- 注册各 GameState 对应的 BaseScreen 实例
- 切换屏幕时有序触发 on_exit → on_enter 生命周期钩子
- 将 handle_event / update / render 向下委托给当前活跃屏幕

v2.0 新增全局像素级渐变转场（Fade Transition）系统：
- FADING_OUT → FADING_IN → NONE 三态转场状态机
- 动态 Alpha 黑色覆盖层实现平滑画面过渡
- 转场时自动静音 BGM
- Headless / 测试模式下自动降级为即时瞬切
"""

import os

import pygame

from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT
from src.screens.base_screen import BaseScreen


class ScreenManager:
    """多屏幕状态机 — 管理所有已注册屏幕的实例与活跃屏幕的生命周期。

    用法::

        mgr = ScreenManager()
        mgr.register_screen(GameState.MAIN_MENU,    menu_screen)
        mgr.register_screen(GameState.PLAYING,     play_screen)
        mgr.switch_screen(GameState.MAIN_MENU)

        # 在主循环中：
        mgr.handle_event(event)
        mgr.update(dt)
        mgr.render(surface)
    """

    def __init__(self):
        self.screens: dict[GameState, BaseScreen] = {}
        self.current_screen: BaseScreen | None = None
        self.current_state: GameState | None = None

        # ---- 像素级渐变转场系统 ----
        self.instant_mode: bool = False  # True 时跳过所有动画（测试沙盒用）
        self.transition_state: str = "NONE"  # "NONE" | "FADING_OUT" | "FADING_IN"
        self.fade_duration: float = 0.3  # 总过渡时长（秒）
        self.fade_timer: float = 0.0
        self.pending_state: GameState | None = None
        self.pending_payload: dict | None = None
        self._fade_overlay: pygame.Surface | None = None  # 缓存的黑色覆盖层

    # =========================================================================
    # 屏幕注册
    # =========================================================================

    def register_screen(self, state: GameState, screen: BaseScreen):
        """注册一个具体屏幕界面实例到给定 GameState 键。

        Args:
            state: GameState 枚举值，作为该屏幕的唯一标识键。
            screen: 继承自 BaseScreen 的实例。

        Raises:
            TypeError: 如果 screen 不是 BaseScreen 的子类实例。
        """
        if not isinstance(screen, BaseScreen):
            raise TypeError(
                f"register_screen 期望 BaseScreen 子类实例，得到 {type(screen).__name__}"
            )
        self.screens[state] = screen

    # =========================================================================
    # 屏幕切换
    # =========================================================================

    @staticmethod
    def _detect_headless() -> bool:
        """检测当前是否运行在 Headless（Dummy 驱动）模式下。

        双重检测：
        1. 环境变量 SDL_VIDEODRIVER == "dummy"（测试文件在 pygame.init() 前设置）
        2. pygame.display.get_driver() == "dummy"（运行态实时检测）

        Returns:
            True 若检测到 Headless 驱动。
        """
        if os.environ.get("SDL_VIDEODRIVER") == "dummy":
            return True
        try:
            return pygame.display.get_driver() == "dummy"
        except pygame.error:
            return False

    def switch_screen(self, new_state: GameState, data_payload: dict = None):
        """切换活跃场景，支持平滑渐变转场。

        切换流程（标准模式）：
        1. 若 transition_state != NONE，先 _complete_transition_immediately()
        2. 若 current_screen 为 None（首次切换）→ 立即切换
        3. 若处于瞬切模式（instant / instant_mode / headless）→ 原行为：on_exit → on_enter
        4. 否则：进入 FADING_OUT，暂存目标状态，不调 on_exit/on_enter

        Args:
            new_state: 目标 GameState 枚举值。必须在之前已被 register_screen 注册。
            data_payload: 传递给新屏幕 on_enter 的数据负载。

        Raises:
            KeyError: 如果 new_state 尚未被注册。
        """
        if new_state not in self.screens:
            raise KeyError(f"GameState '{new_state}' 尚未被 register_screen 注册")

        # ---- 若正在过渡中，先强制完成当前过渡 ----
        if self.transition_state != "NONE":
            self._complete_transition_immediately()

        # ---- 首次切换（无 current_screen）：无屏可淡出，直接切换 ----
        if self.current_screen is None:
            self.current_state = new_state
            self.current_screen = self.screens[new_state]
            self.current_screen.on_enter(data_payload)
            return

        # ---- 判断是否为瞬切模式 ----
        if self.instant_mode or self._detect_headless():
            self.current_screen.on_exit()
            self.current_state = new_state
            self.current_screen = self.screens[new_state]
            self.current_screen.on_enter(data_payload)
            return

        # ---- 标准转场：进入 FADING_OUT 暂不切换 ----
        self.pending_state = new_state
        self.pending_payload = data_payload
        self.transition_state = "FADING_OUT"
        self.fade_timer = 0.0

        # 淡出当前 BGM（半程 150ms，配合 0.3s 过渡）
        try:
            from src.audio_manager import AudioManager

            AudioManager.get_instance().stop_bgm(fade_ms=150)
        except Exception:
            pass  # AudioManager 不可用时静默降级

    def _complete_transition_immediately(self):
        """强制完成当前正在进行的转场过渡。

        在过渡中再次调用 switch_screen 时，先调用此方法确保状态一致。
        - FADING_OUT: 执行 midpoint 切换 on_exit → on_enter
        - FADING_IN: 新屏已激活，直接清理
        - 无论何种状态，最终回到 NONE 并清空 pending。
        """
        if self.transition_state == "FADING_OUT":
            # Midpoint 尚未执行：旧屏仍在，需执行切换
            if self.current_screen is not None:
                self.current_screen.on_exit()
            self.current_state = self.pending_state
            self.current_screen = self.screens[self.pending_state]
            self.current_screen.on_enter(self.pending_payload)
        # FADING_IN: 新屏已激活，无需额外切换

        self.transition_state = "NONE"
        self.fade_timer = 0.0
        self.pending_state = None
        self.pending_payload = None

    # =========================================================================
    # 主循环委托 — update / render 支持转场状态机
    # =========================================================================

    def handle_event(self, event: pygame.event.Event):
        """将事件委托给当前活跃屏幕。无活跃屏幕时静默忽略。

        转场期间不拦截事件——旧屏或新屏正常接收，保证过渡中 UI 响应。"""
        if self.current_screen is not None:
            self.current_screen.handle_event(event)

    def update(self, dt: float):
        """将逻辑更新委托给当前活跃屏幕，并在转场时驱动过渡状态机。

        状态机行为：
        - NONE: 直接委托给 current_screen.update(dt)
        - FADING_OUT: 调用旧屏 update + 累加 timer；过半程时执行 midpoint（on_exit → on_enter）
        - FADING_IN: 调用新屏 update + 累加 timer；过半程时转场完成
        """
        if self.transition_state == "NONE":
            if self.current_screen is not None:
                self.current_screen.update(dt)
            return

        half_duration = self.fade_duration / 2.0

        if self.transition_state == "FADING_OUT":
            # 旧屏继续逻辑更新
            if self.current_screen is not None:
                self.current_screen.update(dt)

            self.fade_timer += dt
            if self.fade_timer >= half_duration:
                # ---- Midpoint：执行屏幕切换 ----
                try:
                    if self.current_screen is not None:
                        self.current_screen.on_exit()
                    self.current_state = self.pending_state
                    self.current_screen = self.screens[self.pending_state]
                    self.current_screen.on_enter(self.pending_payload)
                except Exception:
                    # 异常时强制回到 NONE，防止卡死在过渡态
                    self.transition_state = "NONE"
                    self.fade_timer = 0.0
                    self.pending_state = None
                    self.pending_payload = None
                    raise

                # 进入 FADING_IN
                self.transition_state = "FADING_IN"
                self.fade_timer -= half_duration  # 携带过量 dt

        elif self.transition_state == "FADING_IN":
            # 新屏逻辑更新
            if self.current_screen is not None:
                self.current_screen.update(dt)

            self.fade_timer += dt
            if self.fade_timer >= half_duration:
                # ---- 转场完成 ----
                self.transition_state = "NONE"
                self.fade_timer = 0.0
                self.pending_state = None
                self.pending_payload = None

    def render(self, surface: pygame.Surface):
        """将画面绘制委托给当前活跃屏幕，并在转场时叠加 Alpha 黑色覆盖层。

        渲染顺序：
        1. 委托 current_screen.render(surface) 绘制场景
        2. 若在转场中，在场景之上叠加半透明黑色 Surface（FADING_OUT 渐黑 / FADING_IN 渐亮）
        """
        if self.current_screen is None:
            return

        # 1. 委托当前屏幕渲染
        self.current_screen.render(surface)

        # 2. 非转场态直接返回
        if self.transition_state == "NONE":
            return

        half_duration = self.fade_duration / 2.0
        frac = max(0.0, min(1.0, self.fade_timer / half_duration if half_duration > 0 else 1.0))

        if self.transition_state == "FADING_OUT":
            alpha = int(frac * 255)
        else:  # FADING_IN
            alpha = int((1.0 - frac) * 255)

        if alpha <= 0:
            return
        if alpha > 255:
            alpha = 255

        # 3. 缓存黑色覆盖层（只创建一次）
        if self._fade_overlay is None:
            self._fade_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            self._fade_overlay.fill((0, 0, 0))

        self._fade_overlay.set_alpha(alpha)
        surface.blit(self._fade_overlay, (0, 0))
