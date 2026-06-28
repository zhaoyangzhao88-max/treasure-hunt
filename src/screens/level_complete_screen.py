"""关卡通过结算界面 — Microsoft Treasure Hunt

玩家通关后展示的结算场景：
- 显示通关关卡、金币增量、生存状况
- 自动将金币和最高关卡通关记录安全落盘
- 智能路由：特定关卡后进入商店，其余直接下一关
"""

import os as _os
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from src.screens.base_screen import BaseScreen
from src.ui_helpers import Button
from src.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    GameState,
    WHITE,
    BLACK,
    GREEN,
    GOLD,
    LIGHT_BLUE,
    DARK_GREEN,
)


# =============================================================================
# 结算界面颜色常量
# =============================================================================

_COLOR_BG = (15, 23, 42)           # 深蓝黑背景
_COLOR_TITLE = (255, 215, 0)        # 金色大标题
_COLOR_STAT_GREEN = (0, 255, 0)     # 通关关卡 - 绿色
_COLOR_STAT_GOLD = (255, 215, 0)    # 金币增量 - 金色
_COLOR_STAT_BLUE = (173, 216, 230)  # 生存状况 - 淡蓝色


# =============================================================================
# 关卡结算场景
# =============================================================================

class LevelCompleteScreen(BaseScreen):
    """关卡通过结算界面 — 展示通关数据、自动存档、智能路由下一关。

    生命周期：
    - on_enter: 解析通关数据 → 更新 player_state → 安全落盘 → 初始化按钮
    - handle_event: 鼠标悬停 + 点击判定
    - update: no-op
    - render: 深蓝背景 + 标题 + 统计 + 按钮

    路由规则：
    - 若 completed_level == 1 或 completed_level > 1 且 completed_level % 5 == 0：
      → 切换到 MUMMY_SHOP（贪婪木乃伊商店）
    - 否则：
      → 直接切换到 PLAYING（下一关）
    """

    def __init__(self):
        """初始化结算界面（不含资源加载 — 由 on_enter 负责）。"""
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None

        self.completed_level: int = 0
        self.gold_earned: int = 0
        self.remaining_hearts: int = 0
        self.remaining_shields: int = 0

        self.buttons: list[Button] = []
        self.btn_next_level: Button | None = None
        self.btn_save_exit: Button | None = None

        self.font_title = None
        self.font_stats = None
        self.sound_click = None

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_enter(self, data_payload: dict = None):
        """进入结算界面 — 解析通关数据、更新状态、安全落盘、初始化按钮。

        Args:
            data_payload: GameplayScreen 传入的通关数据。
                需包含：completed_level, gold_earned, remaining_hearts, remaining_shields
        """
        from src.game_manager import GameManager

        # None guard
        data_payload = data_payload or {}

        self.game_manager = GameManager.get_instance()
        self.screen_manager = self.game_manager.screen_manager
        self.asset_manager = self.game_manager.asset_manager

        # ---- 解析数据载荷 ----
        self.completed_level = data_payload.get("completed_level", 0)
        self.gold_earned = data_payload.get("gold_earned", 0)
        self.remaining_hearts = data_payload.get("remaining_hearts", 0)
        self.remaining_shields = data_payload.get("remaining_shields", 0)

        # ---- 更新全局玩家状态 ----
        ps = self.game_manager.player_state
        ps.total_gold_earned += self.gold_earned
        if self.completed_level > ps.highest_level_cleared:
            ps.highest_level_cleared = self.completed_level

        # ---- 安全落盘 ----
        self.game_manager.save_manager.save(
            self._build_player_dict(ps),
            {
                "sound_volume": 1.0,
                "music_volume": 1.0,
            },
        )

        # ---- 初始化字体 ----
        self.font_title = self.asset_manager.get_font("default", 64)
        self.font_stats = self.asset_manager.get_font("default", 36)

        # ---- 初始化按钮 ----
        center_x = SCREEN_WIDTH // 2
        btn_width = 320
        btn_height = 52

        self.btn_next_level = Button(
            text="继续下一关 (Next Level)",
            center_pos=(center_x, 420),
            width=btn_width,
            height=btn_height,
            font=self.font_stats,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        self.btn_save_exit = Button(
            text="保存并返回菜单 (Save & Exit)",
            center_pos=(center_x, 500),
            width=btn_width,
            height=btn_height,
            font=self.font_stats,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )

        self.buttons = [self.btn_next_level, self.btn_save_exit]

        # ---- 预载音效 ----
        self.sound_click = self.asset_manager.get_sound("click.wav")

    def on_exit(self):
        """离开结算界面时释放临时引用。"""
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None
        self.buttons = []
        self.btn_next_level = None
        self.btn_save_exit = None
        self.font_title = None
        self.font_stats = None
        self.sound_click = None

    # =========================================================================
    # 事件处理
    # =========================================================================

    def handle_event(self, event: pygame.event.Event):
        """分发鼠标事件：悬停检测 + 点击处理。"""
        if event.type == pygame.MOUSEMOTION:
            for button in self.buttons:
                button.update(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # ---- 继续下一关 ----
            if (
                self.btn_next_level is not None
                and self.btn_next_level.is_enabled
                and self.btn_next_level.rect.collidepoint(event.pos)
            ):
                if self.sound_click is not None:
                    self.sound_click.play()
                self._route_next_level()

            # ---- 保存并返回菜单 ----
            elif (
                self.btn_save_exit is not None
                and self.btn_save_exit.is_enabled
                and self.btn_save_exit.rect.collidepoint(event.pos)
            ):
                if self.sound_click is not None:
                    self.sound_click.play()
                self.screen_manager.switch_screen(GameState.MAIN_MENU)

    def _route_next_level(self):
        """智能路由：特定关卡后进入商店，其余直接下一关。

        规则：
        - completed_level == 1 → 商店
        - completed_level > 1 且 completed_level % 5 == 0 → 商店
        - 否则 → 直接下一关
        """
        should_trigger_shop = (
            self.completed_level == 1
            or (self.completed_level > 1 and self.completed_level % 5 == 0)
        )

        if should_trigger_shop:
            self.screen_manager.switch_screen(
                GameState.MUMMY_SHOP,
                data_payload={"next_level": self.completed_level + 1},
            )
        else:
            self.screen_manager.switch_screen(
                GameState.PLAYING,
                data_payload={
                    "level_num": self.completed_level + 1,
                    "continue": True,
                },
            )

    # =========================================================================
    # 帧循环
    # =========================================================================

    def update(self, dt: float):
        """结算界面无帧间逻辑，no-op。"""
        pass

    def render(self, surface: pygame.Surface):
        """画面绘制 — 深蓝背景 + 标题 + 统计 + 按钮。"""
        # ---- 背景填充 ----
        surface.fill(_COLOR_BG)

        # ---- 大标题 ----
        if self.font_title is not None:
            title_surf = self.font_title.render("LEVEL COMPLETED!", True, _COLOR_TITLE)
            title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, 120))
            surface.blit(title_surf, title_rect)

        # ---- 结算统计列表 ----
        if self.font_stats is not None:
            center_x = SCREEN_WIDTH // 2
            start_y = 220
            line_gap = 50

            # 通关关卡 — 绿色
            stat_level = self.font_stats.render(
                f"Cleared: Level {self.completed_level}", True, _COLOR_STAT_GREEN
            )
            stat_level_rect = stat_level.get_rect(center=(center_x, start_y))
            surface.blit(stat_level, stat_level_rect)

            # 金币增量 — 金色
            stat_gold = self.font_stats.render(
                f"Gold Picked: +{self.gold_earned}", True, _COLOR_STAT_GOLD
            )
            stat_gold_rect = stat_gold.get_rect(center=(center_x, start_y + line_gap))
            surface.blit(stat_gold, stat_gold_rect)

            # 生存状况 — 淡蓝色
            stat_vitals = self.font_stats.render(
                f"Vitals: {self.remaining_hearts} Hearts / {self.remaining_shields} Shields",
                True,
                _COLOR_STAT_BLUE,
            )
            stat_vitals_rect = stat_vitals.get_rect(center=(center_x, start_y + line_gap * 2))
            surface.blit(stat_vitals, stat_vitals_rect)

        # ---- 按钮 ----
        for button in self.buttons:
            button.render(surface)

    # =========================================================================
    # 内部辅助
    # =========================================================================

    @staticmethod
    def _build_player_dict(ps) -> dict:
        """将 PlayerState 序列化为 SaveManager 期望的 player 字典格式。

        包含完整字段以确保保存/加载往返完整性。

        Args:
            ps: PlayerState 实例

        Returns:
            序列化后的 player 数据字典
        """
        return {
            "max_hearts": ps.max_hearts,
            "current_hearts": ps.current_hearts,
            "max_shields_limit": ps.max_shields,
            "current_shields": ps.current_shields,
            "bag_tier_index": ps.bag_tier_index,
            "highest_level_cleared": ps.highest_level_cleared,
            "total_runs": 0,
            "total_gold_earned": ps.total_gold_earned,
            "gold": ps.gold,
            "tools": dict(ps.tools),
            "keys": dict(ps.keys),
        }
