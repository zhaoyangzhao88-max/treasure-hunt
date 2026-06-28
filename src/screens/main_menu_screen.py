"""游戏主菜单界面 — Microsoft Treasure Hunt

首个具体屏幕实现，继承 BaseScreen 抽象契约：
- MainMenuScreen：三按钮主菜单 + hover/click 音效串联 + 场景切换

Button 辅助类已提取至 src/ui_helpers.py。
"""

import pygame

from src.screens.base_screen import BaseScreen
from src.ui_helpers import Button
from src.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    GameState,
    GRAY,
    WHITE,
    BLACK,
    GOLD,
    DARK_GREEN,
    SILVER,
)


# =============================================================================
# 主菜单界面
# =============================================================================

class MainMenuScreen(BaseScreen):
    """游戏主菜单 — 四个按钮 + 悬停/点击音效串联。

    按钮：
    1. "开始新游戏"       — 切换到 PLAYING 场景（新档）
    2. "读取进度"         — 切换到 PLAYING 场景（续档），无存档时置灰
    3. "设置 (Settings)"  — 切换到 SETTINGS 场景
    4. "退出游戏"         — 调用 GameManager.quit_game()
    """

    def __init__(self):
        """初始化主菜单（不含资源加载 — 由 on_enter 负责）。"""
        self.game_manager = None
        self.asset_manager = None
        self.screen_manager = None

        self.buttons: list[Button] = []
        self.btn_new_game: Button | None = None
        self.btn_continue: Button | None = None
        self.btn_settings: Button | None = None
        self.btn_quit: Button | None = None

        self.sound_hover = None
        self.sound_click = None
        self.font_button = None
        self.font_title = None

        self.highest_level_cleared: int = 0

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_enter(self, data_payload: dict = None):
        """进入主菜单时初始化按钮、音效与字体。

        Args:
            data_payload: 前屏传入数据（主菜单不消费此参数）。
        """
        from src.game_manager import GameManager

        self.game_manager = GameManager.get_instance()
        self.asset_manager = self.game_manager.asset_manager
        self.screen_manager = self.game_manager.screen_manager

        # ---- 判断存档状态 ----
        has_save = False
        self.highest_level_cleared = 0
        try:
            save_data = self.game_manager.save_manager.load()
            if save_data and "player" in save_data:
                cleared = save_data["player"].get("highest_level_cleared", 0)
                if cleared and cleared > 0:
                    has_save = True
                    self.highest_level_cleared = cleared
        except Exception:
            pass  # 存档加载异常时视为无存档

        # ---- 预载字体 ----
        # 使用 AssetManager 加载字体；传入占位名让它退化到系统默认 SysFont
        self.font_button = self.asset_manager.get_font("default", 36)
        self.font_title = self.asset_manager.get_font("default", 64)

        # ---- 初始化按钮 ----
        center_x = SCREEN_WIDTH // 2
        btn_width = 280
        btn_height = 52

        self.btn_new_game = Button(
            text="开始新游戏",
            center_pos=(center_x, 330),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        self.btn_continue = Button(
            text="读取进度",
            center_pos=(center_x, 430),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_continue.is_enabled = has_save

        self.btn_quit = Button(
            text="退出游戏",
            center_pos=(center_x, 540),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        self.btn_settings = Button(
            text="设置 (Settings)",
            center_pos=(center_x, 470),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        self.buttons = [self.btn_new_game, self.btn_continue, self.btn_settings, self.btn_quit]

        # ---- 预载音效 ----
        self.sound_hover = self.asset_manager.get_sound("hover.wav")
        self.sound_click = self.asset_manager.get_sound("click.wav")

        # ---- 启动主菜单背景音乐 ----
        from src.audio_manager import AudioManager
        AudioManager.get_instance().play_bgm("menu_bgm.ogg")

    def on_exit(self):
        """离开主菜单时释放临时引用。"""
        self.game_manager = None
        self.asset_manager = None
        self.screen_manager = None
        self.buttons = []
        self.btn_new_game = None
        self.btn_continue = None
        self.btn_settings = None
        self.btn_quit = None
        self.sound_hover = None
        self.sound_click = None
        self.font_button = None
        self.font_title = None

    # =========================================================================
    # 事件处理
    # =========================================================================

    def handle_event(self, event: pygame.event.Event):
        """分发鼠标事件：悬停检测 + 点击处理。"""
        if event.type == pygame.MOUSEMOTION:
            for button in self.buttons:
                just_hovered = button.update(event.pos)
                if just_hovered:
                    self.sound_hover.play()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # ---- 开始新游戏 ----
            if (
                self.btn_new_game.is_enabled
                and self.btn_new_game.rect.collidepoint(event.pos)
            ):
                self.sound_click.play()
                self.screen_manager.switch_screen(
                    GameState.PLAYING,
                    data_payload={"continue": False},
                )

            # ---- 读取进度 ----
            elif (
                self.btn_continue.is_enabled
                and self.btn_continue.rect.collidepoint(event.pos)
            ):
                self.sound_click.play()
                self.screen_manager.switch_screen(
                    GameState.PLAYING,
                    data_payload={
                        "continue": True,
                        "highest_level_cleared": self.highest_level_cleared,
                    },
                )

            # ---- 设置 ----
            elif (
                self.btn_settings.is_enabled
                and self.btn_settings.rect.collidepoint(event.pos)
            ):
                self.sound_click.play()
                self.screen_manager.switch_screen(GameState.SETTINGS)

            # ---- 退出游戏 ----
            elif (
                self.btn_quit.is_enabled
                and self.btn_quit.rect.collidepoint(event.pos)
            ):
                self.sound_click.play()
                self.game_manager.quit_game()

    # =========================================================================
    # 帧循环
    # =========================================================================

    def update(self, dt: float):
        """主菜单无帧间逻辑，no-op。"""
        pass

    def render(self, surface: pygame.Surface):
        """绘制标题与所有按钮。"""
        # ---- 背景填充 ----
        surface.fill(BLACK)

        # ---- 标题 ----
        title_surf = self.font_title.render("Microsoft Treasure Hunt", True, GOLD)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, 160))
        surface.blit(title_surf, title_rect)

        # ---- 按钮 ----
        for button in self.buttons:
            button.render(surface)
