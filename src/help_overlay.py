"""玩法指南与控制键位蒙层 — Microsoft Treasure Hunt

在游戏画面上叠一层毛玻璃半透明幕布，左侧显示键盘按键绑定，
右侧显示鼠标行为与瓦片符号图例，帮助玩家随时查阅规则而
不必离开当前关卡。

开启H/F1帮助时，主循环须冻结玩家移动、特效推进与受击闪烁；
在 BonusLevelScreen 中还会同时冻结 30 秒倒计时。

使用方式::

    overlay = HelpOverlay()
    # 在 render() 末尾：
    if show_help:
        overlay.render(surface)
"""

import os as _os
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from src.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    HUD_HEIGHT,
    WHITE,
    BLACK,
    GRAY,
    RED,
    GREEN,
    BLUE,
    YELLOW,
    ORANGE,
    PURPLE,
    CYAN,
    BROWN,
    DARK_GREEN,
    LIGHT_BLUE,
    GOLD,
    SILVER,
)
from src.asset_manager import AssetManager


# =============================================================================
# 布局常量
# =============================================================================

# 蒙层区域（紧贴 HUD 下方）
_OVERLAY_TOP = HUD_HEIGHT
_OVERLAY_HEIGHT = SCREEN_HEIGHT - HUD_HEIGHT

# 外围水平边距
_MARGIN_X = 64

# 双面板间隙
_PANEL_GAP = 48

# 面板内边距
_PANEL_PAD = 24

# 行间距
_LINE_GAP = 6


# =============================================================================
# 绘制辅助
# =============================================================================

def _render_line(surface: pygame.Surface, font: pygame.font.Font,
                 y: int, text: str, color: tuple) -> int:
    """在指定 y 坐标渲染一行文字，返回渲染后的新 y。"""
    try:
        surf = font.render(text, True, color)
        surface.blit(surf, (_MARGIN_X, y))
        return y + surf.get_height() + _LINE_GAP
    except Exception:
        return y + font.get_linesize() + _LINE_GAP


def _render_keycap(surface: pygame.Surface, font: pygame.font.Font,
                  x: int, y: int, label: str, color: tuple) -> pygame.Rect:
    """绘制一个小型键帽（比文字略大的着色矩形），返回其 Rect。"""
    try:
        text_surf = font.render(label, True, BLACK)
    except Exception:
        text_surf = None

    pad = 6
    if text_surf is not None:
        w = text_surf.get_width() + pad * 2
        h = text_surf.get_height() + pad * 2
    else:
        w = len(label) * 8 + pad * 2
        h = font.get_linesize() + pad * 2

    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surface, color, rect, border_radius=4)
    if text_surf is not None:
        surface.blit(text_surf, (x + pad, y + pad))
    return rect


def _render_tile_swatch(surface: pygame.Surface, x: int, y: int,
                       size: int, bg_color: tuple,
                       glyph: str = "", glyph_color: tuple = BLACK) -> pygame.Rect:
    """绘制一个瓦片小色块 + 符号（覆盖在色块上）。"""
    rect = pygame.Rect(x, y, size, size)
    pygame.draw.rect(surface, bg_color, rect, border_radius=3)
    if glyph:
        try:
            # 使用粗体小字号让符号更清晰
            swatch_font = pygame.font.Font(None, max(12, size * 6 // 10))
            g_surf = swatch_font.render(glyph, True, glyph_color)
            g_rect = g_surf.get_rect(center=rect.center)
            surface.blit(g_surf, g_rect)
        except Exception:
            pass
    return rect


# =============================================================================
# 主蒙层类
# =============================================================================

class HelpOverlay:
    """玩法指南毛玻璃蒙层。

    绘制分层（从底到顶）：
    1. 半透明黑色幕布（Alpha=200），让关卡若隐若现
    2. 顶部横幅标题
    3. 双框线面板（左：键盘  / 右：鼠标+图例）
    4. 底部退出提示

    属性:
        font_body: 正文小号字体
        font_title: 标题字体（粗体）
        font_keycap: 键帽内小字体
    """

    def __init__(self):
        asset_mgr = AssetManager.get_instance()

        # 正文（按键说明 / 图例行）
        self.font_body = asset_mgr.get_font("arial", 16)
        # 面板标题（粗体大号）
        try:
            self.font_title = pygame.font.SysFont("arial", 22, bold=True)
        except Exception:
            self.font_title = pygame.font.Font(None, 22)
        # 顶部横幅
        try:
            self.font_banner = pygame.font.SysFont("arial", 28, bold=True)
        except Exception:
            self.font_banner = pygame.font.Font(None, 28)
        # 键帽内的小字
        self.font_keycap = asset_mgr.get_font("arial", 13)

    # =========================================================================
    # 主渲染
    # =========================================================================

    def render(self, surface: pygame.Surface):
        """在指定 surface 上自下而上绘制完整蒙层。"""
        if surface is None:
            return

        self._draw_scrim(surface)
        self._draw_banner(surface)
        self._draw_panels(surface)
        self._draw_footer(surface)

    # =========================================================================
    # 分层绘制
    # =========================================================================

    def _draw_scrim(self, surface: pygame.Surface):
        """半透明黑色幕布（convert_alpha / SRCALPHA）。"""
        try:
            overlay = pygame.Surface(
                (SCREEN_WIDTH, _OVERLAY_HEIGHT),
                pygame.SRCALPHA,
            )
            overlay.fill((0, 0, 0, 200))
            surface.blit(overlay, (0, _OVERLAY_TOP))
        except Exception:
            pass

    def _draw_banner(self, surface: pygame.Surface):
        """顶部横幅标题。"""
        y = _OVERLAY_TOP + 16
        try:
            surf = self.font_banner.render("TREASURE HUNT  HELP", True, GOLD)
        except Exception:
            surf = None
        if surf is not None:
            x = (SCREEN_WIDTH - surf.get_width()) // 2
            surface.blit(surf, (x, y))

    def _draw_panels(self, surface: pygame.Surface):
        """双栏面板描边 + 内容。"""
        content_top = _OVERLAY_TOP + 72

        # 左右面板尺寸（二等分，减去边距与间隙）
        usable_w = SCREEN_WIDTH - 2 * _MARGIN_X - _PANEL_GAP
        panel_w = usable_w // 2
        panel_h = _OVERLAY_HEIGHT - 72 - 80  # 留 80 给底部

        left_rect = pygame.Rect(
            _MARGIN_X, content_top, panel_w, panel_h
        )
        right_rect = pygame.Rect(
            _MARGIN_X + panel_w + _PANEL_GAP, content_top,
            panel_w, panel_h,
        )

        # 描边（双框线：外浅灰 + 内白，视觉层次）
        for rect in (left_rect, right_rect):
            pygame.draw.rect(surface, GRAY, rect, 3, border_radius=8)
            inner = rect.inflate(-6, -6)
            pygame.draw.rect(surface, WHITE, inner, 1, border_radius=6)

        # 左面板内容
        self._draw_keyboard_panel(surface, left_rect)
        # 右面板内容
        self._draw_tiles_panel(surface, right_rect)

    def _draw_keyboard_panel(self, surface: pygame.Surface, rect: pygame.Rect):
        """左：KEYBOARD CONTROLS 按键列表。"""
        x = rect.x + _PANEL_PAD
        y = rect.y + _PANEL_PAD

        # 标题
        try:
            title = self.font_title.render("KEYBOARD", True, YELLOW)
            surface.blit(title, (x, y))
        except Exception:
            pass
        y += 30

        # 按键行列表：(label, desc)
        rows = [
            ("W A S D", "Move (move up/down/left/right)"),
            ("Arrow Keys", "Move (move up/down/left/right)"),
            ("B", "Dynamite (blast 3x3)"),
            ("M", "Map (5x5 radar scan)"),
            ("H  /  F1", "Toggle this help"),
            ("ESC", "Cancel tool / back"),
        ]
        for label, desc in rows:
            # 键帽
            key_rect = _render_keycap(
                surface, self.font_keycap,
                x, y + 2, label, CYAN if "/" not in label else GRAY,
            )
            # 描述文字（右对齐，橙黄色）
            desc_x = key_rect.right + 10
            try:
                surf_desc = self.font_body.render(desc, True, ORANGE if "Move" in desc else SILVER)
                surface.blit(surf_desc, (desc_x, y + 4))
            except Exception:
                pass
            y = max(y + 28, key_rect.bottom + 8)

    def _draw_tiles_panel(self, surface: pygame.Surface, rect: pygame.Rect):
        """右：MOUSE & TILES 行为 + 符号图例。"""
        x = rect.x + _PANEL_PAD
        y = rect.y + _PANEL_PAD

        try:
            title = self.font_title.render("MOUSE & TILES", True, YELLOW)
            surface.blit(title, (x, y))
        except Exception:
            pass
        y += 30

        # 鼠标操作行
        mouse_rows = [
            ("Left Click", "Dig dirt (开掘)", GREEN),
            ("Right Click", "Toggle flag (标旗)", GREEN),
            ("Click number", "Chording (连锁数字)", CYAN),
        ]
        for label, desc, accent in mouse_rows:
            try:
                label_surf = self.font_body.render(label, True, accent)
                surface.blit(label_surf, (x, y))
            except Exception:
                label_surf = None
            try:
                desc_surf = self.font_body.render("-> " + desc, True, SILVER)
                surface.blit(desc_surf, (x + 110, y))
            except Exception:
                pass
            step = label_surf.get_height() if label_surf is not None else self.font_body.get_linesize()
            y += step + _LINE_GAP + 4

        # 分隔空行
        y += 8
        # 图例标题
        try:
            legend_title = self.font_title.render("Symbols", True, YELLOW)
            surface.blit(legend_title, (x, y))
        except Exception:
            pass
        y += 28

        # 图例行：(bg_color, glyph, glyph_color, description)
        sw = 28
        sh = 28
        legend_rows = [
            (BROWN,       "C",  WHITE, "Chest (宝箱)"),
            (RED,         "X",  WHITE, "Trap (陷阱)"),
            (LIGHT_BLUE,  "@",  BLACK, "Player (玩家)"),
            (GOLD,        "*",  BLACK, "Coin (金币)"),
            (GREEN,       "+",  BLACK, "Gem (宝石)"),
            (RED,         "v",  WHITE, "Heart (心)"),
            (BLUE,        "s",  WHITE, "Shield (盾)"),
            (PURPLE,      "A",  WHITE, "Amulet (护身符)"),
        ]
        for bg, glyph, glyph_clr, desc in legend_rows:
            _render_tile_swatch(surface, x, y, sh, bg, glyph, glyph_clr)
            try:
                desc_surf = self.font_body.render(desc, True, WHITE)
                surface.blit(desc_surf, (x + sw + 8, y + 5))
            except Exception:
                pass
            y += sh + 4

    def _draw_footer(self, surface: pygame.Surface):
        """底部退出提示。"""
        footer_text = "Press H or F1 to Exit Help & Resume Game"
        try:
            surf = self.font_title.render(footer_text, True, WHITE)
            x = (SCREEN_WIDTH - surf.get_width()) // 2
            y = SCREEN_HEIGHT - 48
            surface.blit(surf, (x, y))
        except Exception:
            pass
