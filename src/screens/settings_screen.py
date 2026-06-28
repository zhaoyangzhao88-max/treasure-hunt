"""设置与选项界面 — Microsoft Treasure Hunt

提供音乐/音效音量实时调节、全屏切换等功能。
音量设置将通过 AssetManager.get_sound() 自动联动到全局音效。
"""

import pygame

from src.audio_manager import AudioManager
from src.screens.base_screen import BaseScreen
from src.ui_helpers import Button
from src.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    GameState,
    WHITE,
    BLACK,
    GOLD,
    DARK_GREEN,
    GRAY,
    SILVER,
)


# =============================================================================
# 常量
# =============================================================================

_BG_COLOR = (15, 23, 42)
"""设置界面专用深蓝色背景"""

_FONT_TITLE_SIZE = 48
_FONT_LABEL_SIZE = 28
_FONT_BUTTON_SIZE = 36

_BTN_W = 40
_BTN_H = 40
_BTN_WIDE_W = 260
_BTN_WIDE_H = 40
_BTN_BACK_W = 280
_BTN_BACK_H = 52

_VOLUME_STEP = 0.1
_VOLUME_FILLED_CHAR = "█"
_VOLUME_EMPTY_CHAR = "░"
_VOLUME_BAR_SEGMENTS = 10


# =============================================================================
# 设置界面
# =============================================================================

class SettingsScreen(BaseScreen):
    """游戏设置界面 — 音量调节、全屏切换与设置持久化。

    按钮布局（所有坐标基于 1024×768 画布）：
        Music Volume:  [-] X=380,Y=260  |  [+] X=600,Y=260
        SFX Volume:    [-] X=380,Y=360  |  [+] X=600,Y=360
        Display Mode:  [全屏切换]        X=380,Y=460 (260×40)
        Back:          [Back to Menu]    Y=580  (280×52)
    """

    def __init__(self):
        """初始化设置界面（不含资源加载 — 由 on_enter 负责）。"""
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None
        self.save_manager = None

        # 当前音量值
        self.sound_volume: float = 1.0   # 音效音量（对应 save.json → sound_volume）
        self.music_volume: float = 1.0   # 音乐音量（对应 save.json → music_volume）
        self.is_fullscreen: bool = False

        # 按钮集合
        self.buttons: list[Button] = []
        self.btn_music_minus: Button | None = None
        self.btn_music_plus: Button | None = None
        self.btn_sfx_minus: Button | None = None
        self.btn_sfx_plus: Button | None = None
        self.btn_fullscreen: Button | None = None
        self.btn_back: Button | None = None

        # 资源引用
        self.font_title = None
        self.font_label = None
        self.font_button = None
        self.sound_hover = None
        self.sound_click = None

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_enter(self, data_payload: dict = None):
        """进入设置界面时读取存档设置、初始化按钮与资源。

        Args:
            data_payload: 前屏传入数据（设置界面不消费此参数）。
        """
        from src.game_manager import GameManager

        self.game_manager = GameManager.get_instance()
        self.screen_manager = self.game_manager.screen_manager
        self.asset_manager = self.game_manager.asset_manager
        self.save_manager = self.game_manager.save_manager

        # ---- 读取当前设置 ----
        save_data = self.save_manager.load()
        settings = save_data.get("settings", {})
        self.sound_volume = float(settings.get("sound_volume", 1.0))
        self.music_volume = float(settings.get("music_volume", 1.0))

        # 检测当前全屏状态
        try:
            flags = pygame.display.get_surface().get_flags()
            self.is_fullscreen = bool(flags & pygame.FULLSCREEN)
        except Exception:
            self.is_fullscreen = False

        # ---- 预载字体 ----
        self.font_title = self.asset_manager.get_font("default", _FONT_TITLE_SIZE)
        self.font_label = self.asset_manager.get_font("default", _FONT_LABEL_SIZE)
        self.font_button = self.asset_manager.get_font("default", _FONT_BUTTON_SIZE)

        # ---- 预载音效 ----
        self.sound_hover = self.asset_manager.get_sound("hover.wav")
        self.sound_click = self.asset_manager.get_sound("click.wav")

        # ---- 创建按钮 ----
        self._create_buttons()

        # ---- 启动菜单背景音乐（与主菜单共享） ----
        from src.audio_manager import AudioManager
        AudioManager.get_instance().play_bgm("menu_bgm.ogg")

    def on_exit(self):
        """离开设置界面时释放临时引用。"""
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None
        self.save_manager = None
        self.buttons = []
        self.btn_music_minus = None
        self.btn_music_plus = None
        self.btn_sfx_minus = None
        self.btn_sfx_plus = None
        self.btn_fullscreen = None
        self.btn_back = None
        self.font_title = None
        self.font_label = None
        self.font_button = None
        self.sound_hover = None
        self.sound_click = None

    # =========================================================================
    # 按钮构建
    # =========================================================================

    def _create_buttons(self):
        """创建全部六个调节按钮。"""
        self.btn_music_minus = Button(
            text="−",
            center_pos=(380, 260),
            width=_BTN_W,
            height=_BTN_H,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_music_minus.item_id = "music_minus"

        self.btn_music_plus = Button(
            text="+",
            center_pos=(600, 260),
            width=_BTN_W,
            height=_BTN_H,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_music_plus.item_id = "music_plus"

        self.btn_sfx_minus = Button(
            text="−",
            center_pos=(380, 360),
            width=_BTN_W,
            height=_BTN_H,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_sfx_minus.item_id = "sfx_minus"

        self.btn_sfx_plus = Button(
            text="+",
            center_pos=(600, 360),
            width=_BTN_W,
            height=_BTN_H,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_sfx_plus.item_id = "sfx_plus"

        # 全屏切换按钮 — 文本根据当前全屏状态动态显示
        fs_text = "Fullscreen: ON" if self.is_fullscreen else "Fullscreen: OFF"
        self.btn_fullscreen = Button(
            text=fs_text,
            center_pos=(510, 480),
            width=_BTN_WIDE_W,
            height=_BTN_WIDE_H,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_fullscreen.item_id = "fullscreen"

        self.btn_back = Button(
            text="Back to Menu",
            center_pos=(SCREEN_WIDTH // 2, 580),
            width=_BTN_BACK_W,
            height=_BTN_BACK_H,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_back.item_id = "back"

        self.buttons = [
            self.btn_music_minus,
            self.btn_music_plus,
            self.btn_sfx_minus,
            self.btn_sfx_plus,
            self.btn_fullscreen,
            self.btn_back,
        ]

    # =========================================================================
    # 事件处理
    # =========================================================================

    def handle_event(self, event: pygame.event.Event):
        """分发鼠标事件：悬停检测 + 点击处理（音量增减 / 全屏切换 / 返回）。"""
        if event.type == pygame.MOUSEMOTION:
            for button in self.buttons:
                just_hovered = button.update(event.pos)
                if just_hovered:
                    self.sound_hover.play()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if not button.is_enabled or not button.rect.collidepoint(event.pos):
                    continue
                item_id = getattr(button, "item_id", None)

                # ---- 音乐音量减 ----
                if item_id == "music_minus" and self.music_volume > 0.0:
                    self.music_volume = max(0.0, self.music_volume - _VOLUME_STEP)
                    AudioManager.get_instance().set_music_volume(self.music_volume)
                    self.sound_click.play()

                # ---- 音乐音量加 ----
                elif item_id == "music_plus" and self.music_volume < 1.0:
                    self.music_volume = min(1.0, self.music_volume + _VOLUME_STEP)
                    AudioManager.get_instance().set_music_volume(self.music_volume)
                    self.sound_click.play()

                # ---- 音效音量减 ----
                elif item_id == "sfx_minus" and self.sound_volume > 0.0:
                    self.sound_volume = max(0.0, self.sound_volume - _VOLUME_STEP)
                    AudioManager.get_instance().set_sfx_volume(self.sound_volume)
                    self.game_manager.settings_data["sound_volume"] = self.sound_volume
                    self.sound_click.play()

                # ---- 音效音量加 ----
                elif item_id == "sfx_plus" and self.sound_volume < 1.0:
                    self.sound_volume = min(1.0, self.sound_volume + _VOLUME_STEP)
                    AudioManager.get_instance().set_sfx_volume(self.sound_volume)
                    self.game_manager.settings_data["sound_volume"] = self.sound_volume
                    self.sound_click.play()

                # ---- 全屏切换 ----
                elif item_id == "fullscreen":
                    try:
                        pygame.display.toggle_fullscreen()
                        self.is_fullscreen = not self.is_fullscreen
                    except Exception:
                        pass
                    # 更新按钮文本反映当前模式
                    fs_text = "Fullscreen: ON" if self.is_fullscreen else "Fullscreen: OFF"
                    self.btn_fullscreen.text = fs_text
                    self.sound_click.play()

                # ---- 返回主菜单（保存设置） ----
                elif item_id == "back":
                    self.sound_click.play()
                    self._save_and_return()

    # =========================================================================
    # 设置持久化
    # =========================================================================

    def _save_and_return(self):
        """将当前音量设置写入 save.json 并切换回主菜单。"""
        # 获取已有存档数据以保留玩家状态
        current_data = self.save_manager.load()
        player_data = current_data.get("player", {})

        # 构建最新设置字典
        settings_data = {
            "sound_volume": self.sound_volume,
            "music_volume": self.music_volume,
        }

        # 持久化到磁盘
        self.save_manager.save(player_data, settings_data)

        # 同步 GameManager 内存中的设置引用（供 AssetManager 读取）
        self.game_manager.settings_data = settings_data

        # 返回主菜单
        self.screen_manager.switch_screen(GameState.MAIN_MENU)

    # =========================================================================
    # 帧循环
    # =========================================================================

    def update(self, dt: float):
        """设置界面无帧间逻辑，no-op。"""
        pass

    def render(self, surface: pygame.Surface):
        """绘制背景、标题、音量标签/进度条与全部按钮。"""
        # ---- 背景填充 ----
        surface.fill(_BG_COLOR)

        center_x = SCREEN_WIDTH // 2

        # ---- 标题 ----
        if self.font_title is not None:
            title_surf = self.font_title.render(
                "SETTINGS & OPTIONS", True, GOLD
            )
            title_rect = title_surf.get_rect(center=(center_x, 100))
            surface.blit(title_surf, title_rect)

        # ---- 音量标签与进度条 ----
        if self.font_label is not None:
            # -- Music Volume --
            music_label = self.font_label.render("Music Volume", True, WHITE)
            music_label_rect = music_label.get_rect(center=(center_x, 220))
            surface.blit(music_label, music_label_rect)

            self._render_volume_bar(surface, 380, 600, 270, self.music_volume)
            music_val = self.font_label.render(
                f"{self.music_volume:.1f}", True, GOLD
            )
            surface.blit(music_val, (620, 260))

            # -- SFX Volume --
            sfx_label = self.font_label.render("SFX Volume", True, WHITE)
            sfx_label_rect = sfx_label.get_rect(center=(center_x, 320))
            surface.blit(sfx_label, sfx_label_rect)

            self._render_volume_bar(surface, 380, 600, 370, self.sound_volume)
            sfx_val = self.font_label.render(
                f"{self.sound_volume:.1f}", True, GOLD
            )
            surface.blit(sfx_val, (620, 360))

            # -- Display Mode label --
            display_label = self.font_label.render("Display Mode", True, WHITE)
            display_label_rect = display_label.get_rect(center=(center_x, 425))
            surface.blit(display_label, display_label_rect)

        # ---- 按钮 ----
        for button in self.buttons:
            button.render(surface)

    # =========================================================================
    # 内部辅助
    # =========================================================================

    def _render_volume_bar(
        self,
        surface: pygame.Surface,
        btn_left_x: int,
        btn_right_x: int,
        y: int,
        volume: float,
    ):
        """在减/加按钮之间绘制 Unicode 字符音量进度条。

        Args:
            surface: 绘制目标 Surface
            btn_left_x: 左侧按钮的 X 坐标（减号按钮）
            btn_right_x: 右侧按钮的 X 坐标（加号按钮）
            y: 进度条 Y 坐标
            volume: 当前音量值 [0.0, 1.0]
        """
        if self.font_label is None:
            return

        n_filled = int(volume * _VOLUME_BAR_SEGMENTS)
        n_empty = _VOLUME_BAR_SEGMENTS - n_filled
        bar_text = _VOLUME_FILLED_CHAR * n_filled + _VOLUME_EMPTY_CHAR * n_empty

        bar_surf = self.font_label.render(bar_text, True, WHITE)
        bar_rect = bar_surf.get_rect()
        bar_rect.center = ((btn_left_x + btn_right_x) // 2, y)
        surface.blit(bar_surf, bar_rect)
