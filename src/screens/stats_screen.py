"""历史数据与生涯成就陈列室（StatsScreen）— Microsoft Treasure Hunt

展示玩家终身累计的 4 项生涯统计（总金币 / 击杀木乃伊 / 运行次数 / 最高通关），
并以 4 大主题勋章（淘金者 / 木乃伊猎人 / 深渊征服者 / 坚韧先驱）的
青铜(BRONZE) / 白银(SILVER) / 黄金(GOLD) / 锁定(LOCKED) 三阶段位
动态评估算法呈现荣誉成就。

第 42 课新增：Hall of Trophies 荣誉陈列室。
第 43 课重排：左侧 2×2 勋章架 + 右侧 Top 5 本地高分榜双分屏画廊。
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
    GOLD,
    DARK_GREEN,
    GRAY,
)


# =============================================================================
# 颜色常量
# =============================================================================

_COLOR_BG = (15, 23, 42)            # 深蓝黑背景
_COLOR_TITLE = (255, 215, 0)         # 金色大标题
_COLOR_DATA_BAR_BG = (30, 41, 59)    # 数据栏格子背景
_COLOR_DATA_BAR_BORDER = (100, 116, 139)  # 数据栏格子边框
_COLOR_DATA_VALUE = (255, 215, 0)    # 数据值 - 金色
_COLOR_DATA_LABEL = (148, 163, 184)  # 数据标签 - 银灰
_COLOR_CARD_BG = (30, 41, 59)        # 勋章卡片背景
_COLOR_CARD_BORDER = (100, 116, 139) # 勋章卡片边框
_COLOR_ACHIEV_NAME = (255, 255, 255) # 成就名 - 白色
_COLOR_ACHIEV_STATUS = (173, 216, 230)  # 成就状况 - 淡蓝色
_COLOR_ACHIEV_GOAL = (255, 215, 0)   # 下一阶段目标 - 金色

# 勋章段位配色
_COLOR_LOCKED = (100, 116, 139)      # 锁定 - 灰色
_COLOR_BRONZE = (180, 110, 50)       # 古铜色
_COLOR_SILVER = (192, 192, 192)      # 亮银色
_COLOR_GOLD = (255, 215, 0)          # 璀璨金色


# =============================================================================
# 勋章定义
# =============================================================================

# 4 大勋章：(名称, 数值来源字段, 三阶段位阶梯)
_ACHIEVEMENTS = [
    {"name": "Gold Rush",       "key": "gold_earned",     "tiers": [5000, 20000, 50000]},
    {"name": "Mummy Hunter",    "key": "monsters_slain",  "tiers": [10, 50, 200]},
    {"name": "Abyss Conqueror", "key": "highest_level",   "tiers": [5, 15, 40]},
    {"name": "Persistent Pioneer", "key": "runs",         "tiers": [5, 20, 80]},
]

# 勋章卡片 2×2 网格布局（左面板 X: 80 ~ 480，宽度 400）
_PANEL_LEFT = 80
_PANEL_LEFT_W = 400
# 勋章卡片尺寸与中心坐标
_CARD_WIDTH = 170
_CARD_HEIGHT = 170
_ROW_Y_CENTERS = (290, 480)   # 第 1、2 行的 Y 中心
_COL_X_CENTERS = (165, 395)   # 左列、右列的 X 中心

# 右面板：Top 5 本地高分榜（X: 540 ~ 944，Y: 200 ~ 580）
_PANEL_RIGHT = 540
_PANEL_RIGHT_W = 400
_PANEL_RIGHT_H = 380
_PANEL_RIGHT_TOP = 200
_PANEL_RIGHT_BOTTOM = 580
_LEADERBOARD_ROW_GAP = 65

# 排行榜名次配色
_COLOR_RANK_GOLD = (255, 215, 0)
_COLOR_RANK_SILVER = (192, 192, 192)
_COLOR_RANK_BRONZE = (180, 110, 50)
_COLOR_LEADERBOARD_BORDER = (255, 215, 0)  # 金色细边框
_LEADERBOARD_RANK_COLORS = (
    _COLOR_RANK_GOLD,   # #1
    _COLOR_RANK_SILVER, # #2
    _COLOR_RANK_BRONZE, # #3
    GRAY,               # #4
    GRAY,               # #5
)


class StatsScreen(BaseScreen):
    """荣誉陈列室屏幕 — 展示生涯统计与 4 大勋章段位。"""

    def __init__(self):
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None
        self.font_title = None
        self.font_label = None
        self.font_value = None
        self.font_info = None
        self.sound_click = None
        self.sound_hover = None
        self.buttons = []
        self.btn_back = None

        # 生涯统计
        self.gold_earned = 0
        self.monsters_slain = 0
        self.runs = 0
        self.highest_level = 0

        # 勋章评估结果：list of (badge_tier, next_tier_goal)
        self.achievement_results = []

        # 本地 Top 5 排行榜缓存
        self.leaderboard = []

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_enter(self, data_payload: dict = None):
        """进入陈列室：读取生涯数据并评估 4 大勋章段位。"""
        from src.game_manager import GameManager

        data_payload = data_payload or {}
        self.game_manager = GameManager.get_instance()
        self.screen_manager = self.game_manager.screen_manager
        self.asset_manager = self.game_manager.asset_manager

        # 字体
        self.font_title = self.asset_manager.get_font("default", 48)
        self.font_label = self.asset_manager.get_font("default", 20)
        self.font_value = self.asset_manager.get_font("default", 28)
        self.font_info = self.asset_manager.get_font("default", 18)

        # 音效（失败时 None）
        self.sound_click = self.asset_manager.get_sound("click.wav")
        self.sound_hover = self.asset_manager.get_sound("hover.wav")

        # 读取生涯统计
        player = self.game_manager.player_state
        self.gold_earned = getattr(player, "total_gold_earned", 0)
        self.monsters_slain = getattr(player, "total_monsters_slain", 0)
        self.runs = getattr(player, "total_runs", 0)
        self.highest_level = getattr(player, "highest_level_cleared", 0)

        # 评估 4 大勋章
        values = {
            "gold_earned": self.gold_earned,
            "monsters_slain": self.monsters_slain,
            "highest_level": self.highest_level,
            "runs": self.runs,
        }
        self.achievement_results = []
        for ach in _ACHIEVEMENTS:
            result = self._evaluate_achievement(values[ach["key"]], ach["tiers"])
            self.achievement_results.append(result)

        # 加载本地 Top 5 排行榜
        try:
            self.leaderboard = self.game_manager.save_manager.load().get("leaderboard", [])
            if not isinstance(self.leaderboard, list):
                self.leaderboard = []
        except Exception:
            self.leaderboard = []

        # 返回按钮
        self.btn_back = Button(
            text="Back to Menu",
            center_pos=(512, 652),
            width=260,
            height=45,
            font=self.font_label,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.buttons = [self.btn_back]

    def on_exit(self):
        """离开陈列室：释放引用。"""
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None
        self.buttons = []
        self.btn_back = None
        self.achievement_results = []
        self.leaderboard = []

    # =========================================================================
    # 勋章评估算法
    # =========================================================================

    def _evaluate_achievement(self, value: int, tiers: list) -> tuple:
        """根据当前值与三阶段位阶梯评估勋章段位。

        Args:
            value: 当前累计数值
            tiers: 三阶段位阶梯，例如 [10, 50, 200]

        Returns:
            (badge_tier, next_tier_goal)：
            - value < tiers[0]            → ("LOCKED", tiers[0])
            - tiers[0] <= value < tiers[1] → ("BRONZE", tiers[1])
            - tiers[1] <= value < tiers[2] → ("SILVER", tiers[2])
            - value >= tiers[2]            → ("GOLD", -1)（-1 表示封顶）
        """
        if value < tiers[0]:
            return ("LOCKED", tiers[0])
        if value < tiers[1]:
            return ("BRONZE", tiers[1])
        if value < tiers[2]:
            return ("SILVER", tiers[2])
        return ("GOLD", -1)

    # =========================================================================
    # 事件处理
    # =========================================================================

    def handle_event(self, event: pygame.event.Event):
        """处理鼠标事件：悬停音效 + 返回按钮点击路由回主菜单。"""
        if event.type == pygame.MOUSEMOTION:
            for button in self.buttons:
                just_hovered = button.update(event.pos)
                if just_hovered and self.sound_hover is not None:
                    self.sound_hover.play()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if not button.is_enabled:
                    continue
                if not button.rect.collidepoint(event.pos):
                    continue
                if button is self.btn_back:
                    if self.sound_click is not None:
                        self.sound_click.play()
                    self.screen_manager.switch_screen(GameState.MAIN_MENU)
                break

    def update(self, dt: float):
        """逻辑更新（无动态逻辑，留空）。"""
        pass

    # =========================================================================
    # 渲染
    # =========================================================================

    def render(self, surface: pygame.Surface):
        """渲染荣誉陈列室：标题 + 数据栏 + 左 2×2 勋章 + 右 Top 5 排行榜 + 返回按钮。"""
        surface.fill(_COLOR_BG)
        center_x = SCREEN_WIDTH // 2

        # ---- 大标题 ----
        self._render_text(
            surface, "HALL OF TROPHIES", self.font_title,
            _COLOR_TITLE, center_x, 60,
        )

        # ---- 上方数据栏（横跨全宽） ----
        self._render_data_bar(surface)

        # ---- 左侧 2×2 勋章网格 ----
        # 排列顺序：第 1 行左=淘金者 右=木乃伊猎人；第 2 行左=深渊征服者 右=执着探险家
        for idx, ach in enumerate(_ACHIEVEMENTS):
            row, col = divmod(idx, 2)
            cx = _COL_X_CENTERS[col]
            cy = _ROW_Y_CENTERS[row]
            badge_tier, next_goal = self.achievement_results[idx]
            self._render_achievement_card(
                surface, cx, cy, _CARD_WIDTH, _CARD_HEIGHT,
                ach["name"], badge_tier, next_goal,
            )

        # ---- 右侧 Top 5 排行榜 ----
        self._render_leaderboard_panel(surface)

        # ---- 返回按钮 ----
        for button in self.buttons:
            button.render(surface)

    def _render_data_bar(self, surface: pygame.Surface):
        """绘制上方 4 格数据栏：Total Gold / Slain / Runs / High Level。"""
        labels = [
            ("Total Gold", self.gold_earned),
            ("Slain", self.monsters_slain),
            ("Runs", self.runs),
            ("High Level", self.highest_level),
        ]
        # 4 格均匀分布于 X:100~900
        bar_y = 130
        bar_height = 70
        gap = 16
        total_width = 800  # 900 - 100
        cell_width = (total_width - gap * 3) // 4
        start_x = 100

        for idx, (label, value) in enumerate(labels):
            x = start_x + idx * (cell_width + gap)
            cell_rect = pygame.Rect(x, bar_y, cell_width, bar_height)
            pygame.draw.rect(surface, _COLOR_DATA_BAR_BG, cell_rect)
            pygame.draw.rect(surface, _COLOR_DATA_BAR_BORDER, cell_rect, 2)

            # 标签（上方）
            self._render_text(
                surface, label, self.font_label, _COLOR_DATA_LABEL,
                cell_rect.centerx, cell_rect.y + 16,
            )
            # 数值（下方）
            self._render_text(
                surface, str(value), self.font_value, _COLOR_DATA_VALUE,
                cell_rect.centerx, cell_rect.y + 44,
            )

    def _render_achievement_card(
        self,
        surface: pygame.Surface,
        center_x: int, center_y: int, width: int, height: int,
        name: str, badge_tier: str, next_goal: int,
    ):
        """绘制单张勋章卡片（紧凑版，适配 2×2 网格）。

        采用中心坐标系，卡片尺寸 170×170。
        """
        x = center_x - width // 2
        y = center_y - height // 2
        card_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(surface, _COLOR_CARD_BG, card_rect)
        pygame.draw.rect(surface, _COLOR_CARD_BORDER, card_rect, 2)

        # 矢量盾牌徽章（缩小适配紧凑卡片）
        shield_top = y + 15
        self._render_shield(surface, center_x, shield_top, badge_tier)

        # 成就名称
        self._render_text(
            surface, name, self.font_info, _COLOR_ACHIEV_NAME,
            center_x, y + 90,
        )

        # 当前段位状况
        if badge_tier == "LOCKED":
            status_text = "Level: Locked"
        elif badge_tier == "BRONZE":
            status_text = "Level: Bronze"
        elif badge_tier == "SILVER":
            status_text = "Level: Silver"
        else:
            status_text = "Level: Gold"
        self._render_text(
            surface, status_text, self.font_info, _COLOR_ACHIEV_STATUS,
            center_x, y + 115,
        )

        # 下一阶段目标
        if next_goal == -1:
            goal_text = "Maxed!"
        else:
            goal_text = f"Goal: {next_goal}"
        self._render_text(
            surface, goal_text, self.font_info, _COLOR_ACHIEV_GOAL,
            center_x, y + 140,
        )

    def _render_shield(
        self, surface: pygame.Surface, cx: int, top: int, badge_tier: str,
    ):
        """在卡片顶部绘制矢量盾牌徽章（紧凑尺寸适配 170×170 卡片）。

        - LOCKED：灰色空心盾 + "?"
        - BRONZE / SILVER / GOLD：对应颜色实心盾 + "B" / "S" / "G"
        """
        shield_w = 56
        shield_h = 64
        left = cx - shield_w // 2
        shield_rect = pygame.Rect(left, top, shield_w, shield_h)

        if badge_tier == "LOCKED":
            color = _COLOR_LOCKED
            pygame.draw.rect(surface, color, shield_rect, 3)  # 空心
            self._render_text(surface, "?", self.font_value, color, cx, top + shield_h // 2)
        elif badge_tier == "BRONZE":
            color = _COLOR_BRONZE
            pygame.draw.rect(surface, color, shield_rect)  # 实心
            pygame.draw.rect(surface, WHITE, shield_rect, 2)  # 双边框
            self._render_text(surface, "B", self.font_value, WHITE, cx, top + shield_h // 2)
        elif badge_tier == "SILVER":
            color = _COLOR_SILVER
            pygame.draw.rect(surface, color, shield_rect)
            pygame.draw.rect(surface, WHITE, shield_rect, 2)
            self._render_text(surface, "S", self.font_value, BLACK, cx, top + shield_h // 2)
        else:  # GOLD
            color = _COLOR_GOLD
            pygame.draw.rect(surface, color, shield_rect)
            pygame.draw.rect(surface, WHITE, shield_rect, 2)
            self._render_text(surface, "G", self.font_value, BLACK, cx, top + shield_h // 2)

    def _render_leaderboard_panel(self, surface: pygame.Surface):
        """绘制右侧 Top 5 排行榜面板。

        结构：
        - 深底 + 金色细边框矩形容器
        - 顶部金色标题 "★ LOCAL LEADERBOARD ★"
        - 最多 5 行：#排名 | "Level N" | "{gold:,} Gold" | 日期（小字）
        - 名次颜色：#1 金 #2 银 #3 铜 #4/#5 灰
        - 空榜：居中灰色斜体提示
        """
        panel_rect = pygame.Rect(
            _PANEL_RIGHT, _PANEL_RIGHT_TOP,
            _PANEL_RIGHT_W, _PANEL_RIGHT_H,
        )
        pygame.draw.rect(surface, _COLOR_CARD_BG, panel_rect)
        pygame.draw.rect(surface, _COLOR_LEADERBOARD_BORDER, panel_rect, 3)

        self._render_text(
            surface, "★ LOCAL LEADERBOARD ★", self.font_value, GOLD,
            panel_rect.centerx, _PANEL_RIGHT_TOP + 25,
        )

        if not self.leaderboard:
            # 空榜：灰色斜体提示
            italic_font = self.font_info
            try:
                italic_font.set_italic(True)
                surf = italic_font.render(
                    "No high scores recorded yet. Go adventure!", True, GRAY,
                )
            finally:
                italic_font.set_italic(False)
            rect = surf.get_rect(center=panel_rect.center)
            surface.blit(surf, rect)
            return

        # 绘制 Top 5 行（Y 步进 _LEADERBOARD_ROW_GAP）
        row_start_y = _PANEL_RIGHT_TOP + 60
        rank_x = _PANEL_RIGHT + 20
        level_x = _PANEL_RIGHT + 80
        gold_x = _PANEL_RIGHT + 200
        date_x = _PANEL_RIGHT + 330

        for rank_idx, entry in enumerate(self.leaderboard[:5]):
            y = row_start_y + rank_idx * _LEADERBOARD_ROW_GAP
            color = _LEADERBOARD_RANK_COLORS[rank_idx] if rank_idx < len(_LEADERBOARD_RANK_COLORS) else GRAY

            # 排名
            self._render_text(
                surface, f"#{rank_idx + 1}",
                self.font_value, color, rank_x + 18, y,
            )
            # 关卡
            self._render_text(
                surface, f"Level {entry.get('level_reached', 0)}",
                self.font_info, _COLOR_ACHIEV_NAME, level_x + 30, y,
            )
            # 得分（千分位）
            self._render_text(
                surface, f"{int(entry.get('gold_score', 0)):,} Gold",
                self.font_info, GOLD, gold_x + 40, y,
            )
            # 日期（小字）
            self._render_text(
                surface, str(entry.get("date", "")),
                self.font_info, _COLOR_DATA_LABEL, date_x + 30, y,
            )

    @staticmethod
    def _render_text(
        surface: pygame.Surface, text: str, font, color, cx: int, cy: int,
    ):
        """安全绘制居中文字（font 为 None 时跳过）。"""
        if font is None:
            return
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(cx, cy))
        surface.blit(surf, rect)
