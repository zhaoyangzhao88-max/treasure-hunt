"""即时成就解锁弹窗管理器 — Microsoft Treasure Hunt (第 48 课)

提供跨场景悬浮的"成就解锁"弹窗通知：
- AchievementPopup：右侧 Y=120 卡片，X 轴 SLIDE_IN → STAY → SLIDE_OUT → FINISHED
  三阶段 Lerp 滑移 + 自动清空；卡片段位配色 + 小型双边框盾牌 + 标题文本。
- AchievementManager：绑定 PlayerState，按四大成就三阶段 12 项规则判定
  `check_unlocks()`，防重播（unlocked_badges 集合）+ 原子落盘 + SFX 联动。
"""

from __future__ import annotations

import math
import os
import sys
from typing import Optional

import pygame

# sys.path 自举（与项目其它模块保持一致）
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.audio_manager import AudioManager  # noqa: E402
from src.config import SCREEN_WIDTH  # noqa: E402


# =============================================================================
# 模块常量
# =============================================================================

# 段位配色 — 与 stats_screen._COLOR_* 同值镜像（避免反向耦合）
_COLOR_BRONZE = (180, 110, 50)
_COLOR_SILVER = (192, 192, 192)
_COLOR_GOLD = (255, 215, 0)
_COLOR_LOCKED = (100, 116, 139)
_COLOR_BLACK = (0, 0, 0)
_COLOR_WHITE = (255, 255, 255)
_COLOR_EYEBROW = (251, 191, 36)  # "ACHIEVEMENT UNLOCKED!" 金色

# 弹窗几何
_TOAST_W = 300
_TOAST_H = 80
_TOAST_Y = 120  # 题目指定 Y = 120
_X_OFFSCREEN = float(SCREEN_WIDTH)              # 1024.0 — 起始在屏幕右外侧
_X_REST = float(SCREEN_WIDTH - _TOAST_W - 20)   # 704.0 — 右侧留 20px 边距

# 时序（秒）
_SLIDE_IN_DUR = 0.4
_STAY_DUR = 3.0
_SLIDE_OUT_DUR = 0.4

# 状态机
_STATE_SLIDE_IN = "SLIDE_IN"
_STATE_STAY = "STAY"
_STATE_SLIDE_OUT = "SLIDE_OUT"
_STATE_FINISHED = "FINISHED"

# 段位显示名（大写）与徽章 slug（小写）
_TIER_NAMES = ("BRONZE", "SILVER", "GOLD")
_TIER_SLUG = ("bronze", "silver", "gold")

# StatsScreen._ACHIEVEMENTS 中 `key` → PlayerState 字段名的映射
_STAT_FIELD = {
    "gold_earned": "total_gold_earned",
    "monsters_slain": "total_monsters_slain",
    "highest_level": "highest_level_cleared",
    "runs": "total_runs",
}


def _lerp(a: float, b: float, t: float) -> float:
    """线性插值 a → b，t 通常钳制在 [0, 1]。"""
    return a + (b - a) * t


def _slug(name: str) -> str:
    """把成就显示名转成徽章 ID 片段：'Gold Rush' → 'gold_rush'。"""
    return name.lower().strip().replace(" ", "_")


# =============================================================================
# 成就弹窗
# =============================================================================


class AchievementPopup:
    """右侧悬浮成就通知卡片，带三阶段 Lerp 滑移状态机。

    用法：由 AchievementManager 实例化；外部只需调用 update(dt) / render(surface)。
    """

    def __init__(self, badge_name: str, badge_tier: str):
        self.badge_name: str = badge_name
        self.badge_tier: str = badge_tier.upper() if badge_tier else "LOCKED"

        # 几何与状态
        self.x: float = _X_OFFSCREEN
        self.y: int = _TOAST_Y
        self.w: int = _TOAST_W
        self.h: int = _TOAST_H
        self.state: str = _STATE_SLIDE_IN
        self._elapsed: float = 0.0

        # 盾牌首字母
        self._initial: str = badge_name.strip()[0].upper() if badge_name else "?"

        # 段位色
        self._tier_color = {
            "BRONZE": _COLOR_BRONZE,
            "SILVER": _COLOR_SILVER,
            "GOLD": _COLOR_GOLD,
        }.get(self.badge_tier, _COLOR_LOCKED)

        # 字体（SysFont 带优雅回退，无需资源文件）
        try:
            self._font_eyebrow = pygame.font.SysFont("arial", 14, bold=True)
            self._font_name = pygame.font.SysFont("arial", 16)
        except Exception:
            self._font_eyebrow = pygame.font.Font(None, 14)
            self._font_name = pygame.font.Font(None, 16)

    # -------------------------------------------------------------------------
    # 状态机
    # -------------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """推进状态机；累计 _elapsed >= 段位时长时切换状态。

        调用方保证 dt 为有限浮点数；负值会被忽略。
        """
        if dt < 0:
            dt = 0.0
        if self.state == _STATE_FINISHED:
            return

        self._elapsed += dt

        if self.state == _STATE_SLIDE_IN:
            t = min(self._elapsed / _SLIDE_IN_DUR, 1.0)
            self.x = _lerp(_X_OFFSCREEN, _X_REST, t)
            if self._elapsed >= _SLIDE_IN_DUR:
                self.x = _X_REST
                self.state = _STATE_STAY
                self._elapsed = 0.0

        elif self.state == _STATE_STAY:
            self.x = _X_REST
            if self._elapsed >= _STAY_DUR:
                self.state = _STATE_SLIDE_OUT
                self._elapsed = 0.0

        elif self.state == _STATE_SLIDE_OUT:
            t = min(self._elapsed / _SLIDE_OUT_DUR, 1.0)
            self.x = _lerp(_X_REST, _X_OFFSCREEN, t)
            if self._elapsed >= _SLIDE_OUT_DUR:
                self.state = _STATE_FINISHED

    # -------------------------------------------------------------------------
    # 渲染
    # -------------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        """在当前 self.x/self.y 绘制半透明黑色卡片 + 段位双边框 + 盾牌 + 文本。"""
        if self.state == _STATE_FINISHED:
            return
        if surface is None:
            return

        # 1. 半透明卡片底板
        rect = pygame.Rect(int(round(self.x)), self.y, self.w, self.h)
        card = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        card.fill((10, 10, 10, 210))

        # 2. 段位双边框
        pygame.draw.rect(card, self._tier_color, card.get_rect(), 3, border_radius=8)
        inner = card.get_rect().inflate(-6, -6)
        pygame.draw.rect(card, (40, 40, 40), inner, 2, border_radius=6)

        # 3. 小型双边框盾牌（复用 StatsScreen 的同款视觉：实心色 + 白边 + 首字母）
        self._render_shield(card, cx=15 + 28, top=8, tier=self.badge_tier)

        # 4. 文本
        anchor_x = 15 + 56 + 12
        eyebrow = self._font_eyebrow.render("ACHIEVEMENT UNLOCKED!", True, _COLOR_EYEBROW)
        name = self._font_name.render(
            f"{self.badge_name} ({self.badge_tier.title()})", True, _COLOR_WHITE
        )
        card.blit(eyebrow, (anchor_x, 12))
        card.blit(name, (anchor_x, 40))

        surface.blit(card, rect.topleft)

    def _render_shield(self, surface: pygame.Surface, cx: int, top: int, tier: str) -> None:
        """绘制 56×64 的小型双边框实心盾牌 + 段位首字母。

        与 stats_screen._render_shield 同形同色（独立实现，避免反向耦合）。
        """
        shield_w, shield_h = 56, 64
        left = cx - shield_w // 2
        shield_rect = pygame.Rect(left, top, shield_w, shield_h)

        if tier == "BRONZE":
            color = _COLOR_BRONZE
            pygame.draw.rect(surface, color, shield_rect)
            pygame.draw.rect(surface, _COLOR_WHITE, shield_rect, 2)
            letter = "B"
            letter_color = _COLOR_WHITE
        elif tier == "SILVER":
            color = _COLOR_SILVER
            pygame.draw.rect(surface, color, shield_rect)
            pygame.draw.rect(surface, _COLOR_WHITE, shield_rect, 2)
            letter = "S"
            letter_color = _COLOR_BLACK
        elif tier == "GOLD":
            color = _COLOR_GOLD
            pygame.draw.rect(surface, color, shield_rect)
            pygame.draw.rect(surface, _COLOR_WHITE, shield_rect, 2)
            letter = "G"
            letter_color = _COLOR_BLACK
        else:  # LOCKED / 未知
            color = _COLOR_LOCKED
            pygame.draw.rect(surface, color, shield_rect, 3)
            letter = "?"
            letter_color = _COLOR_LOCKED

        if letter:
            try:
                font = pygame.font.SysFont("arial", 28, bold=True)
            except Exception:
                font = pygame.font.Font(None, 28)
            text = font.render(letter, True, letter_color)
            surface.blit(
                text,
                (cx - text.get_width() // 2, top + shield_h // 2 - text.get_height() // 2),
            )


# =============================================================================
# 全局成就管理器
# =============================================================================


class AchievementManager:
    """全局成就解锁管理器 — 单弹窗位 + 防重播 + 原子落盘 + SFX。

    由 GameManager 在 init_engine 时实例化并调用 check_unlocks()
    （静默回标老玩家已达成项，防首次启动密集弹窗）。
    """

    def __init__(self, game_manager=None):
        # 单例兜底，避免 import 循环
        if game_manager is None:
            from src.game_manager import GameManager
            self._gm = GameManager.get_instance()
        else:
            self._gm = game_manager
        self.active_popup: Optional[AchievementPopup] = None

    # -------------------------------------------------------------------------
    # 评估 + 解锁判定
    # -------------------------------------------------------------------------

    def check_unlocks(self, silent: bool = False) -> None:
        """遍历四大成就 × 三阶段，发现新解锁项立即落盘；首次新解锁弹一次窗。

        Args:
            silent: 静默模式（init_engine 启动回标用）— 只落盘不弹窗、不播 SFX。
                   用于老玩家首次进游戏时静默标记历史已达成项，防密集弹窗。

        防重播：每个 badge_id 只在第一次越过阈值时播放；已在
        player.unlocked_badges 中的直接跳过。
        """
        try:
            player = self._gm.player_state
            unlocked = list(getattr(player, "unlocked_badges", []) or [])
        except Exception:
            return

        newly_name = None
        newly_tier = None

        # 延迟导入目录：stats_screen 模块含 pygame 资源操作，延迟可降低启动耦合
        try:
            from src.screens.stats_screen import _ACHIEVEMENTS
        except Exception:
            return

        for ach in _ACHIEVEMENTS:
            name = ach.get("name")
            key = ach.get("key")
            tiers = ach.get("tiers")
            if not name or not key or not isinstance(tiers, list) or len(tiers) != 3:
                continue
            field = _STAT_FIELD.get(key)
            if not field:
                continue
            try:
                value = int(getattr(player, field, 0) or 0)
            except Exception:
                value = 0

            # 每个成就：解锁所有已达成且未解锁的段位（按阈值从小到大）。
            # 弹窗位优先最低未解锁段位（newly_name 仅被赋值一次）。
            first_unlocked_idx = None
            newly_locked_this_ach = []
            for i, threshold in enumerate(tiers):
                try:
                    threshold_i = int(threshold)
                except Exception:
                    continue
                if value < threshold_i:
                    break  # 后续阈值更高，直接跳出
                badge_id = f"{_slug(name)}_{_TIER_SLUG[i]}"
                if badge_id in unlocked:
                    continue
                newly_locked_this_ach.append((i, badge_id))

            if not newly_locked_this_ach:
                continue

            # 即时落盘：所有段位一次性写入并持久化
            try:
                for _, bid in newly_locked_this_ach:
                    unlocked.append(bid)
                player.unlocked_badges = list(unlocked)
                self._persist(player)
            except Exception:
                # 落盘失败：回滚本成就的所有写入，继续判定下一项
                for _, bid in newly_locked_this_ach:
                    if bid in unlocked:
                        unlocked.remove(bid)
                continue

            if first_unlocked_idx is None or newly_locked_this_ach[0][0] < first_unlocked_idx:
                first_unlocked_idx = newly_locked_this_ach[0][0]
                newly_name = name
                newly_tier = _TIER_NAMES[first_unlocked_idx]

        if newly_name is None:
            return

        # 静默模式（init_engine 启动回标）：只落盘不弹窗、不播 SFX
        if silent:
            return

        if self.active_popup is None:
            try:
                self.active_popup = AchievementPopup(newly_name, newly_tier or "BRONZE")
                AudioManager.get_instance().play_sfx("achievement.wav")
            except Exception:
                # SFX 失败不应中断流程
                pass

    # -------------------------------------------------------------------------
    # 持久化（player dict 字段集必须与 4 处 _build_player_dict 完全对齐）
    # -------------------------------------------------------------------------

    def _persist(self, player) -> None:
        """构造与既有 _build_player_dict 同字段集的 player dict 并原子落盘。"""
        player_dict = {
            "max_hearts": getattr(player, "max_hearts", 3),
            "current_hearts": getattr(player, "current_hearts", 3),
            "max_shields_limit": getattr(player, "max_shields", 1),
            "current_shields": getattr(player, "current_shields", 0),
            "bag_tier_index": getattr(player, "bag_tier_index", 0),
            "highest_level_cleared": getattr(player, "highest_level_cleared", 0),
            "total_runs": getattr(player, "total_runs", 0),
            "total_monsters_slain": getattr(player, "total_monsters_slain", 0),
            "total_gold_earned": getattr(player, "total_gold_earned", 0),
            "gold": getattr(player, "gold", 0),
            "tools": dict(getattr(player, "tools", {})),
            "keys": dict(getattr(player, "keys", {})),
            "has_amulet": getattr(player, "has_amulet", False),
            "unlocked_badges": list(getattr(player, "unlocked_badges", []) or []),
        }
        self._gm.save_manager.save(player_dict, self._gm.settings_data)

    # -------------------------------------------------------------------------
    # 主循环
    # -------------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """推弹窗状态机；FINISHED 后清空。"""
        if self.active_popup is None:
            return
        try:
            self.active_popup.update(dt)
            if self.active_popup.state == _STATE_FINISHED:
                self.active_popup = None
        except Exception:
            # 弹窗异常不应拖垮主循环
            self.active_popup = None

    def render(self, surface: pygame.Surface) -> None:
        """渲染当前活动弹窗（顶层）。"""
        if self.active_popup is None:
            return
        try:
            self.active_popup.render(surface)
        except Exception:
            pass
