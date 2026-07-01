"""多存档插槽选择界面 — Microsoft Treasure Hunt

第 46 课新增：
- 横向 3 卡槽位选择屏（空槽 / 已占用槽摘要）
- 点击空槽 → 绑定该槽位并开启新游戏
- 点击已占用槽 → 绑定该槽位并切回主菜单（由主菜单决定续档或新局）
- Back 按钮 → MAIN_MENU
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
    SILVER,
    MAX_SAVE_SLOTS,
)

# ---------------------------------------------------------------------------
# 布局常量
# ---------------------------------------------------------------------------
_CARD_WIDTH = 280
_CARD_HEIGHT = 360
_CARD_GAP = 30
_CARD_START_Y = 200
_TITLE_Y = 80
_BACK_Y = 660
_BACK_W = 260
_BACK_H = 52

# 槽位卡内文字颜色
_COLOR_CARD_BG = (30, 41, 59)
_COLOR_EMPTY_TEXT = GRAY
_COLOR_VALUE = SILVER


class SaveSlotsScreen(BaseScreen):
    """存档槽位选择屏 — 3 卡横向排列。"""

    def __init__(self):
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None
        self.font_title = None
        self.font_card = None
        self.font_info = None
        self.font_button = None
        self.sound_click = None
        self.sound_hover = None

        self.buttons: list[Button] = []
        self.btn_back: Button | None = None

        self.slot_summaries: list[dict] = []
        self.slot_rects: list[pygame.Rect] = []

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def on_enter(self, data_payload: dict = None):
        # 惰性导入，避免与 GameManager / SaveManager 循环引用
        from src.game_manager import GameManager
        from src.save_manager import SaveManager

        self.game_manager = GameManager.get_instance()
        self.screen_manager = self.game_manager.screen_manager
        self.asset_manager = self.game_manager.asset_manager

        # 字体（沿用现有屏幕的 try/except 容错写法）
        try:
            self.font_title = self.asset_manager.get_font("default", 52)
        except Exception:
            self.font_title = pygame.font.SysFont(None, 52)
        try:
            self.font_card = self.asset_manager.get_font("default", 30)
        except Exception:
            self.font_card = pygame.font.SysFont(None, 30)
        try:
            self.font_info = self.asset_manager.get_font("default", 22)
        except Exception:
            self.font_info = pygame.font.SysFont(None, 22)
        try:
            self.font_button = self.asset_manager.get_font("default", 30)
        except Exception:
            self.font_button = pygame.font.SysFont(None, 30)

        try:
            self.sound_click = self.asset_manager.get_sound("click")
            self.sound_hover = self.asset_manager.get_sound("hover")
        except Exception:
            self.sound_click = None
            self.sound_hover = None

        # 扫描全部槽位摘要
        self.slot_summaries = SaveManager.get_all_slots_summary(MAX_SAVE_SLOTS)

        # 计算 3 卡水平居中排列的 Rect
        total_w = MAX_SAVE_SLOTS * _CARD_WIDTH + (MAX_SAVE_SLOTS - 1) * _CARD_GAP
        start_x = (SCREEN_WIDTH - total_w) // 2
        self.slot_rects = []
        for i in range(MAX_SAVE_SLOTS):
            left = start_x + i * (_CARD_WIDTH + _CARD_GAP)
            rect = pygame.Rect(left, _CARD_START_Y, _CARD_WIDTH, _CARD_HEIGHT)
            self.slot_rects.append(rect)

        # Back 按钮
        self.btn_back = Button(
            text="Back",
            center_pos=(SCREEN_WIDTH // 2, _BACK_Y),
            width=_BACK_W,
            height=_BACK_H,
            font=self.font_button,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.buttons = [self.btn_back]

    def on_exit(self):
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None
        self.buttons = []
        self.btn_back = None
        self.slot_summaries = []
        self.slot_rects = []

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEMOTION:
            for btn in self.buttons:
                just_hovered = btn.update(event.pos)
                if just_hovered and self.sound_hover is not None:
                    try:
                        self.sound_hover.play()
                    except Exception:
                        pass

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Back 按钮
            if self.btn_back.is_enabled and self.btn_back.rect.collidepoint(event.pos):
                if self.sound_click is not None:
                    try:
                        self.sound_click.play()
                    except Exception:
                        pass
                self.screen_manager.switch_screen(GameState.MAIN_MENU)
                return

            # 槽位点击
            for i, rect in enumerate(self.slot_rects):
                if rect.collidepoint(event.pos):
                    if self.sound_click is not None:
                        try:
                            self.sound_click.play()
                        except Exception:
                            pass
                    self._bind_slot_and_navigate(i + 1)
                    return

    def _bind_slot_and_navigate(self, slot_id: int):
        """绑定存档槽位并导航。"""
        gm = self.game_manager
        gm.bind_save_slot(slot_id)

        summary = (
            self.slot_summaries[slot_id - 1]
            if slot_id <= len(self.slot_summaries)
            else None
        )
        if summary and summary.get("exists"):
            # 已占用槽 → 回主菜单（玩家可选续档或新游戏）
            gm.screen_manager.switch_screen(GameState.MAIN_MENU)
        else:
            # 空槽 → 直接开新局
            gm.screen_manager.switch_screen(
                GameState.PLAYING,
                data_payload={"continue": False},
            )

    # ------------------------------------------------------------------
    # 更新 / 渲染
    # ------------------------------------------------------------------

    def update(self, dt: float):
        pass

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        center_x = SCREEN_WIDTH // 2

        # ---- 大标题 ----
        if self.font_title is not None:
            surf = self.font_title.render("SELECT YOUR ADVENTURE", True, GOLD)
            rect = surf.get_rect(center=(center_x, _TITLE_Y))
            surface.blit(surf, rect)

        # ---- 3 张槽位卡 ----
        for rect, summary in zip(self.slot_rects, self.slot_summaries):
            self._render_slot_card(surface, rect, summary)

        # ---- Back 按钮 ----
        for btn in self.buttons:
            btn.render(surface)

    def _render_slot_card(
        self, surface: pygame.Surface, rect: pygame.Rect, summary: dict
    ):
        """渲染单张槽位卡。"""
        occupied = bool(summary.get("exists"))
        border_color = GOLD if occupied else _COLOR_EMPTY_TEXT

        pygame.draw.rect(surface, _COLOR_CARD_BG, rect)
        pygame.draw.rect(surface, border_color, rect, 3)

        cx = rect.centerx
        slot_id = summary["slot_id"]

        # 槽位编号
        if self.font_card is not None:
            surf = self.font_card.render(f"SLOT {slot_id}", True, GOLD)
            surface.blit(surf, surf.get_rect(center=(cx, rect.y + 40)))

        if not occupied:
            # 空槽提示
            if self.font_info is not None:
                surf = self.font_info.render("Empty Slot", True, _COLOR_EMPTY_TEXT)
                surface.blit(surf, surf.get_rect(center=(cx, rect.centery - 10)))
                surf = self.font_info.render(
                    "Click to start", True, _COLOR_EMPTY_TEXT
                )
                surface.blit(surf, surf.get_rect(center=(cx, rect.centery + 20)))
        else:
            # 已占用槽摘要
            y = rect.y + 105
            for label, value in [
                ("Level", summary.get("level")),
                ("Gold", summary.get("gold")),
                ("Runs", summary.get("total_runs")),
                ("Date", summary.get("date")),
            ]:
                if self.font_info is not None:
                    surf = self.font_info.render(
                        f"{label}: {value}", True, _COLOR_VALUE
                    )
                    surface.blit(surf, surf.get_rect(center=(cx, y)))
                    y += 32
