"""多屏幕管理器 — Microsoft Treasure Hunt

实现屏幕状态机的核心职责：
- 注册各 GameState 对应的 BaseScreen 实例
- 切换屏幕时有序触发 on_exit → on_enter 生命周期钩子
- 将 handle_event / update / render 向下委托给当前活跃屏幕
"""

import pygame

from src.config import GameState
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

    def switch_screen(self, new_state: GameState, data_payload: dict = None):
        """切换活跃场景。

        切换流程：
        1. 若 current_screen 存在，调用其 on_exit()。
        2. 更新 current_state = new_state。
        3. 更新 current_screen = screens[new_state]。
        4. 调用新屏幕的 on_enter(data_payload)，完成跨屏数据传递。

        Args:
            new_state: 目标 GameState 枚举值。必须在之前已被 register_screen 注册。
            data_payload: 传递给新屏幕 on_enter 的数据负载。

        Raises:
            KeyError: 如果 new_state 尚未被注册。
        """
        if new_state not in self.screens:
            raise KeyError(f"GameState '{new_state}' 尚未被 register_screen 注册")

        # 1. 退出当前屏幕
        if self.current_screen is not None:
            self.current_screen.on_exit()

        # 2. 切换状态
        self.current_state = new_state
        self.current_screen = self.screens[new_state]

        # 3. 进入新屏幕（传递数据负载）
        self.current_screen.on_enter(data_payload)

    # =========================================================================
    # 主循环委托
    # =========================================================================

    def handle_event(self, event: pygame.event.Event):
        """将事件委托给当前活跃屏幕。无活跃屏幕时静默忽略。"""
        if self.current_screen is not None:
            self.current_screen.handle_event(event)

    def update(self, dt: float):
        """将逻辑更新委托给当前活跃屏幕。无活跃屏幕时静默忽略。"""
        if self.current_screen is not None:
            self.current_screen.update(dt)

    def render(self, surface: pygame.Surface):
        """将画面绘制委托给当前活跃屏幕。无活跃屏幕时静默忽略。"""
        if self.current_screen is not None:
            self.current_screen.render(surface)
