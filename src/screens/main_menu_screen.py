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
        self.btn_achievements: Button | None = None
        self.btn_settings: Button | None = None
        self.btn_map_editor: Button | None = None
        self.btn_quit: Button | None = None
        self.btn_save_slots: Button | None = None
        # 第 54 课：自定义关卡按钮（无 custom_map.json 时置灰）
        self.btn_custom: Button | None = None

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

        # ---- 第 54 课：自检根目录 custom_map.json 是否存在 ----
        # 双态兼容：开发态（项目根）与 PyInstaller 态（_MEIPASS）。
        _has_custom_map = False
        try:
            from src.asset_manager import get_resource_path
            import os as _os
            _has_custom_map = _os.path.exists(get_resource_path("custom_map.json"))
        except Exception:
            _has_custom_map = False

        # ---- 初始化按钮 ----
        # Y 重排（第 57 课）：8 按钮均匀 60px 间距以容纳「设计地图」按钮。
        # 底边 = 670 + 26 = 696 < 768，距屏底 72px 安全。
        center_x = SCREEN_WIDTH // 2
        btn_width = 280
        btn_height = 52

        self.btn_new_game = Button(
            text="开始新游戏",
            center_pos=(center_x, 250),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        self.btn_continue = Button(
            text="读取进度",
            center_pos=(center_x, 310),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_continue.is_enabled = has_save

        self.btn_achievements = Button(
            text="荣誉成就",
            center_pos=(center_x, 370),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        self.btn_settings = Button(
            text="选项设置",
            center_pos=(center_x, 430),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        # 第 57 课：可视化地图编辑器入口
        self.btn_map_editor = Button(
            text="设计地图",
            center_pos=(center_x, 490),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        # 第 54 课：自定义关卡入口
        self.btn_custom = Button(
            text="自定义关卡",
            center_pos=(center_x, 550),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_custom.is_enabled = _has_custom_map

        # 第 46 课：多存档插槽选择入口
        self.btn_save_slots = Button(
            text="选择存档槽",
            center_pos=(center_x, 610),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        self.btn_quit = Button(
            text="退出游戏",
            center_pos=(center_x, 670),
            width=btn_width,
            height=btn_height,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        self.buttons = [
            self.btn_new_game,
            self.btn_continue,
            self.btn_achievements,
            self.btn_settings,
            self.btn_map_editor,
            self.btn_custom,
            self.btn_save_slots,
            self.btn_quit,
        ]

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
        self.btn_achievements = None
        self.btn_settings = None
        self.btn_map_editor = None
        self.btn_save_slots = None
        self.btn_custom = None
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
                # 生涯统计：新一局开始前先累加探险次数再落盘
                player = self.game_manager.player_state
                player.total_runs += 1
                self.game_manager.save_manager.save(
                    self._build_player_dict(player),
                    {"sound_volume": 1.0, "music_volume": 1.0},
                )
                # 成就评估（runs 可能解锁 Persistent Pioneer）
                try:
                    am = self.game_manager.achievement_manager
                    if am is not None:
                        am.check_unlocks()
                except Exception:
                    pass
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

            # ---- 荣誉成就 ----
            elif (
                self.btn_achievements.is_enabled
                and self.btn_achievements.rect.collidepoint(event.pos)
            ):
                self.sound_click.play()
                self.screen_manager.switch_screen(GameState.STATS)

            # ---- 设置 ----
            elif (
                self.btn_settings.is_enabled
                and self.btn_settings.rect.collidepoint(event.pos)
            ):
                self.sound_click.play()
                self.screen_manager.switch_screen(GameState.SETTINGS)

            # ---- 地图编辑器（第 57 课） ----
            elif (
                self.btn_map_editor is not None
                and self.btn_map_editor.is_enabled
                and self.btn_map_editor.rect.collidepoint(event.pos)
            ):
                self.sound_click.play()
                self.screen_manager.switch_screen(GameState.MAP_EDITOR)

            # ---- 自定义关卡（第 54 课） ----
            elif (
                self.btn_custom is not None
                and self.btn_custom.is_enabled
                and self.btn_custom.rect.collidepoint(event.pos)
            ):
                # 先结算 run-count 与成就评估（与「开始新游戏」一致）
                player = self.game_manager.player_state
                player.total_runs += 1
                self.game_manager.save_manager.save(
                    self._build_player_dict(player),
                    {"sound_volume": 1.0, "music_volume": 1.0},
                )
                try:
                    am = self.game_manager.achievement_manager
                    if am is not None:
                        am.check_unlocks()
                except Exception:
                    pass
                self.sound_click.play()
                self.screen_manager.switch_screen(
                    GameState.PLAYING,
                    data_payload={"custom_map_path": "custom_map.json"},
                )

            # ---- 选择存档槽（第 46 课） ----
            elif (
                self.btn_save_slots.is_enabled
                and self.btn_save_slots.rect.collidepoint(event.pos)
            ):
                self.sound_click.play()
                self.screen_manager.switch_screen(GameState.SAVE_SLOT_SELECT)

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

    # ------------------------------------------------------------------
    # 序列化 helper
    # ------------------------------------------------------------------

    @staticmethod
    def _build_player_dict(ps) -> dict:
        """将 PlayerState 序列化为 SaveManager 期望的 player 字典格式。

        与 GameOverScreen / LevelCompleteScreen 保持字段集一致。
        """
        return {
            "max_hearts": ps.max_hearts,
            "current_hearts": ps.current_hearts,
            "max_shields_limit": ps.max_shields,
            "current_shields": ps.current_shields,
            "bag_tier_index": ps.bag_tier_index,
            "highest_level_cleared": ps.highest_level_cleared,
            "total_runs": ps.total_runs,
            "total_monsters_slain": ps.total_monsters_slain,
            "total_gold_earned": ps.total_gold_earned,
            "gold": ps.gold,
            "tools": dict(ps.tools),
            "keys": dict(ps.keys),
            "has_amulet": ps.has_amulet,
            "unlocked_badges": list(getattr(ps, "unlocked_badges", []) or []),
        }

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
