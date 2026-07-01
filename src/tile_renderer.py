"""Spritesheet 瓦片切割与渲染器 — Microsoft Treasure Hunt

TileRenderer 统一管理所有瓦片的渲染逻辑，支持两种模式：
1. 正常模式：从精灵图集（Spritesheet）切割切片并 blit 渲染
2. 优雅退化模式：使用矢量几何 + 文字标识降级渲染（无资产文件时）

提供 draw_tile() 核心 API 供各 Screen 调用。
"""

import os as _os
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import math
import random
from typing import Any

import pygame

from src.config import (TILE_SIZE, BiomeType, BIOME_COLORS,
                        ACTIVE_MUMMY, MUMMY_KING, SPIKE_TRAP)
from src.animation import Animator


# =============================================================================
# 精灵图集网格坐标索引表
# 将游戏中所有瓦片类型映射到 Spritesheet 上的 (col, row) 网格坐标
# =============================================================================

TILE_COORDS: dict[str, tuple[int, int]] = {
    # ---- 地形层 (layer0) ----
    "DIRT": (0, 0),
    "UNCOVERED": (1, 0),
    # ---- 障碍物层 (layer1) ----
    "WALL": (2, 0),
    "DIRT_WALL": (3, 0),
    "LOCK_RED": (4, 0),
    "LOCK_GREEN": (5, 0),
    "LOCK_BLUE": (6, 0),
    "LOCK_EXIT": (7, 0),
    # ---- 实体道具层 (layer2) ----
    "TRAP": (0, 1),
    "COIN": (1, 1),
    "GEM": (2, 1),
    "PICKAXE": (3, 1),
    "DYNAMITE": (4, 1),
    "MAP": (5, 1),
    "HEART": (6, 1),
    "SHIELD": (7, 1),
    "AMULET": (0, 2),
    "KEY_RED": (1, 2),
    "KEY_GREEN": (2, 2),
    "KEY_BLUE": (3, 2),
    "KEY_EXIT": (4, 2),
    "MONSTER": (5, 2),
    "STAIRS": (6, 2),
    "CHEST": (7, 2),
    # ---- 活性木乃伊（第 41 课） ----
    ACTIVE_MUMMY: (0, 4),
    # ---- 法老王首领（第 49 课） ----
    MUMMY_KING: (1, 4),
    # ---- 特殊 ----
    "PLAYER": (0, 3),
    "FLAG": (1, 3),
    "LOCKED_CHEST": (2, 3),
    # ---- 火把（第 55 课） ----
    "TORCH": (3, 3),
}

# ── 退化模式颜色方案 ──────────────────────────────────────────────────────────

_COLOR_DIRT = (120, 80, 50)
_COLOR_DIRT_BORDER = (80, 50, 30)
_COLOR_UNCOVERED = (30, 41, 59)
_COLOR_UNCOVERED_BORDER = (60, 71, 89)
_COLOR_WALL = (25, 32, 42)
_COLOR_DIRT_WALL = (161, 98, 7)
_COLOR_LOCK_RED = (160, 30, 30)
_COLOR_LOCK_GREEN = (20, 120, 40)
_COLOR_LOCK_BLUE = (20, 50, 160)
_COLOR_LOCK_EXIT = (212, 175, 55)
_COLOR_TRAP = (180, 30, 30)
_COLOR_COIN = (212, 175, 55)
_COLOR_GEM = (0, 180, 180)
_COLOR_PICKAXE = (130, 130, 130)
_COLOR_DYNAMITE = (160, 40, 40)
_COLOR_MAP = (230, 210, 170)
_COLOR_HEART = (200, 30, 30)
_COLOR_SHIELD = (30, 80, 200)
_COLOR_AMULET = (140, 40, 180)
_COLOR_KEY_RED = (180, 30, 30)
_COLOR_KEY_GREEN = (30, 140, 50)
_COLOR_KEY_BLUE = (30, 60, 180)
_COLOR_KEY_EXIT = (212, 175, 55)
_COLOR_MONSTER = (20, 80, 40)
_COLOR_STAIRS = (200, 180, 30)
_COLOR_PLAYER = (0, 180, 0)
_COLOR_FLAG = (180, 40, 40)
_COLOR_CHEST = (160, 110, 50)
_COLOR_CHEST_LOCK = (212, 175, 55)
_COLOR_LOCKED_CHEST = (140, 90, 40)
_COLOR_LOCKED_CHEST_GRID = (100, 100, 100)
# 活性木乃伊退化配色 — 深黑底 + 闪烁红色边框 + 白色 [AM] 字
_COLOR_ACTIVE_MUMMY_BG = (15, 15, 25)
_COLOR_ACTIVE_MUMMY_BORDER_DIM = (140, 25, 25)
_COLOR_ACTIVE_MUMMY_BORDER_BRIGHT = (240, 50, 50)
# 法老王首领退化配色 — 暗红底 + 双层暗金闪烁边框 + 亮黄 [MK] 字
_COLOR_MUMMY_KING_BG = (35, 5, 8)
_COLOR_MUMMY_KING_BORDER = (200, 140, 30)
_COLOR_MUMMY_KING_BORDER_BRIGHT = (255, 200, 60)
_COLOR_MUMMY_KING_INNER = (120, 30, 30)
# 周期地刺退化配色（第 50 课）— 安全态金属灰板 / 危险态鲜黄底 + 白蓝尖刺 + 红"!"
_COLOR_SPIKE_METAL = (120, 120, 130)
_COLOR_SPIKE_METAL_BORDER = (70, 70, 85)
_COLOR_SPIKE_BG = (255, 235, 120)
_COLOR_SPIKE_TRIANGLE = (245, 245, 255)
_COLOR_SPIKE_TRIANGLE_BORDER = (80, 160, 255)
# 火把退化配色（第 55 课）—— 黑方框 + 橙红蜡烛 + 中央 "T"
_COLOR_TORCH_RING = (40, 15, 10)
_COLOR_TORCH_BODY = (120, 55, 20)
_COLOR_TORCH_FLAME_CORE = (255, 230, 120)
_COLOR_TORCH_FLAME_MID = (255, 150, 40)
_COLOR_TORCH_FLAME_OUTER = (230, 70, 20)

# 地刺状态字符串常量（与 src/spike_trap.py 中的值相等，避免反向引用）
_SPIKE_STATE_EXTENDED = "EXTENDED"
_SPIKE_STATE_RETRACTED = "RETRACTED"
_COLOR_BG = (30, 41, 59)
_COLOR_WHITE = (255, 255, 255)
_COLOR_BLACK = (0, 0, 0)
_COLOR_GRAY = (180, 180, 180)
_COLOR_BLUE_NUM = (50, 100, 255)
_COLOR_GREEN_NUM = (30, 180, 50)
_COLOR_RED_NUM = (220, 40, 40)
_COLOR_PURPLE_NUM = (140, 40, 200)
_COLOR_MAROON_NUM = (160, 80, 40)
_COLOR_CYAN_NUM = (30, 200, 200)
_COLOR_DARK_NUM = (80, 80, 80)
_COLOR_YELLOW_NUM = (200, 200, 30)


class TileRenderer:
    """统一瓦片渲染器。

    支持 Spritesheet 切片渲染和优雅退化矢量几何渲染两种模式。
    退化模式确保没有资产文件时游戏也能获得高品质视觉效果。

    Args:
        tile_size: 每格瓦片的像素大小（默认 48）。
    """

    def __init__(self, tile_size: int = TILE_SIZE):
        self.tile_size = tile_size
        self.sliced_tiles: dict[tuple[int, int], pygame.Surface] = {}
        self.use_fallback = True  # 默认退化；加载成功后再设为 False
        self.current_biome = BiomeType.GRASSLAND  # 默认地貌

        try:
            from src.asset_manager import AssetManager
            asset_mgr = AssetManager.get_instance()
            sheet = asset_mgr.get_image("spritesheet", size=None)
            # 判断是否为占位 surface（品红色占位 = 加载失败）
            # AssetManager 在加载失败时返回 48x48 品红色 surface；若 spritesheet
            # 实际不存在，此处总是进入退化模式
            if sheet.get_width() > self.tile_size * 2:
                self._slice_spritesheet(sheet, self.tile_size)
                self.use_fallback = False
        except Exception:
            self.use_fallback = True

    def set_biome(self, biome: BiomeType):
        """设置当前地貌，切换退化渲染的主题色板。

        Args:
            biome: 目标地貌类型枚举值。
        """
        self.current_biome = biome

    # =========================================================================
    # Spritesheet 切片
    # =========================================================================

    def _slice_spritesheet(self, sheet: pygame.Surface, tile_size: int):
        """将完整大图按网格切割并缓存到 self.sliced_tiles。

        Args:
            sheet: 完整的精灵图集 Surface。
            tile_size: 每格瓦片像素大小。
        """
        sheet_width = sheet.get_width()
        sheet_height = sheet.get_height()
        cols = sheet_width // tile_size
        rows = sheet_height // tile_size

        for row in range(rows):
            for col in range(cols):
                rect = pygame.Rect(col * tile_size, row * tile_size,
                                   tile_size, tile_size)
                try:
                    tile_surf = sheet.subsurface(rect).copy()
                    self.sliced_tiles[(col, row)] = tile_surf
                except Exception:
                    continue

    def get_sliced_tile(self, tile_type: str) -> pygame.Surface | None:
        """根据瓦片类型从已缓存的切片中获取对应的 Surface。

        Args:
            tile_type: 瓦片类型字符串（如 "DIRT", "COIN" 等）。

        Returns:
            对应的 Surface，若未找到则返回 None。
        """
        coords = TILE_COORDS.get(tile_type)
        if coords is None:
            return None
        return self.sliced_tiles.get(coords)

    # =========================================================================
    # 核心渲染 API
    # =========================================================================

    def draw_tile(self, surface: pygame.Surface, tile_type: str,
                  x: int, y: int, extra_info: Any = None,
                  light_intensity: float = 1.0):
        """在指定像素位置绘制一个瓦片。

        Args:
            surface: 目标 Surface。
            tile_type: 瓦片类型（"DIRT", "COIN", "PLAYER" 等）。
            x: 目标绘制位置的左上角 X 坐标（像素）。
            y: 目标绘制位置的左上角 Y 坐标（像素）。
            extra_info: 可选附加信息，如 UNCOVERED 的邻域雷数字符串。
            light_intensity: 该瓦片的光照强度 ∈ [0.0, 1.0]，默认 1.0 代表完全明亮（不叠加阴影遮罩
                ）；取值 < 1.0 时按对应 Alpha 叠加半透明黑色遮罩（战争迷雾 / 火把半影效果）。
        """
        if not self.use_fallback:
            tile_surf = self.get_sliced_tile(tile_type)
            if tile_surf is not None:
                surface.blit(tile_surf, (x, y))
                # Spritesheet 路径下也统一追加阴影遮罩，保持光照与退化渲染行为一致
                self._apply_light_overlay(surface, x, y, light_intensity)
                return

        # 退化分支：按瓦片类型绘制彩色几何 + 文字
        self._draw_fallback(surface, tile_type, x, y, extra_info)
        # 在完成所有矢量绘制后，追加阴影遮罩（位于最顶层）
        self._apply_light_overlay(surface, x, y, light_intensity)

    def _apply_light_overlay(self, surface: pygame.Surface,
                             x: int, y: int,
                             light_intensity: float) -> None:
        """在已绘制的瓦片表面叠加战争迷雾阴影遮罩。

        当 light_intensity == 1.0（完全明亮）时不做任何操作，节省分配；
        当 light_intensity == 0.0 时 alpha == 255，等价于全黑覆盖。
        """
        if light_intensity >= 1.0:
            return
        alpha = int(255 * (1.0 - light_intensity))
        if alpha <= 0:
            return
        shadow = pygame.Surface((self.tile_size, self.tile_size), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, alpha))
        surface.blit(shadow, (x, y))

    # =========================================================================
    # 退化模式：矢量几何 + 文字标识
    # =========================================================================

    def _draw_fallback(self, surface: pygame.Surface, tile_type: str,
                       x: int, y: int, extra_info: Any = None):
        """优雅退化渲染 — 使用矢量几何和文字标识绘制瓦片。

        Args:
            surface: 目标 Surface。
            tile_type: 瓦片类型。
            x: 左上角 X。
            y: 左上角 Y。
            extra_info: 附加信息（如 UNCOVERED 的数字）。
        """
        ts = self.tile_size
        rect = pygame.Rect(x, y, ts, ts)
        pal = BIOME_COLORS[self.current_biome]

        if tile_type == "DIRT":
            pygame.draw.rect(surface, pal["DIRT"], rect)
            pygame.draw.rect(surface, pal["DIRT_BORDER"], rect, 1)
            self._draw_centered_text(surface, "D", _COLOR_WHITE, x, y, ts)

        elif tile_type == "UNCOVERED":
            pygame.draw.rect(surface, pal["UNCOVERED"], rect)
            pygame.draw.rect(surface, pal["UNCOVERED_BORDER"], rect, 1)
            if extra_info and extra_info.isdigit():
                num = int(extra_info)
                if 1 <= num <= 8:
                    num_color = self._get_number_color(num)
                    self._draw_centered_text(surface, str(num), num_color,
                                             x, y, ts)

        elif tile_type == "WALL":
            pygame.draw.rect(surface, pal["WALL"], rect)
            # 双重交叉线
            mid_x = x + ts // 2
            mid_y = y + ts // 2
            pygame.draw.line(surface, _COLOR_BLACK, (x, y), (x + ts, y + ts), 1)
            pygame.draw.line(surface, _COLOR_BLACK, (x + ts, y), (x, y + ts), 1)
            pygame.draw.line(surface, _COLOR_BLACK, (mid_x, y), (mid_x, y + ts), 1)
            pygame.draw.line(surface, _COLOR_BLACK, (x, mid_y), (x + ts, mid_y), 1)

        elif tile_type == "DIRT_WALL":
            pygame.draw.rect(surface, pal["DIRT_WALL"], rect)
            # 黄色对角网纹
            pygame.draw.line(surface, _COLOR_YELLOW_NUM, (x, y), (x + ts, y + ts), 2)
            pygame.draw.line(surface, _COLOR_YELLOW_NUM, (x + ts, y), (x, y + ts), 2)
            self._draw_centered_text(surface, "W", _COLOR_WHITE, x, y, ts)

        elif tile_type == "LOCK_RED":
            pygame.draw.rect(surface, _COLOR_LOCK_RED, rect)
            pygame.draw.rect(surface, _COLOR_WHITE, rect, 2)
            self._draw_centered_text(surface, "G", _COLOR_WHITE, x, y, ts)

        elif tile_type == "LOCK_GREEN":
            pygame.draw.rect(surface, _COLOR_LOCK_GREEN, rect)
            pygame.draw.rect(surface, _COLOR_WHITE, rect, 2)
            self._draw_centered_text(surface, "G", _COLOR_WHITE, x, y, ts)

        elif tile_type == "LOCK_BLUE":
            pygame.draw.rect(surface, _COLOR_LOCK_BLUE, rect)
            pygame.draw.rect(surface, _COLOR_WHITE, rect, 2)
            self._draw_centered_text(surface, "G", _COLOR_WHITE, x, y, ts)

        elif tile_type == "LOCK_EXIT":
            pygame.draw.rect(surface, _COLOR_LOCK_EXIT, rect)
            pygame.draw.rect(surface, _COLOR_WHITE, rect, 2)
            self._draw_centered_text(surface, "G", _COLOR_BLACK, x, y, ts)

        elif tile_type == "TRAP":
            pygame.draw.rect(surface, _COLOR_TRAP, rect)
            self._draw_centered_text(surface, "X", _COLOR_WHITE, x, y, ts, bold=True)

        elif tile_type == "COIN":
            center = (x + ts // 2, y + ts // 2)
            pygame.draw.circle(surface, _COLOR_COIN, center, ts // 3)
            pygame.draw.circle(surface, _COLOR_GRAY, center, ts // 3, 1)
            self._draw_centered_text(surface, "$", _COLOR_BLACK, x, y, ts)

        elif tile_type == "GEM":
            pygame.draw.rect(surface, _COLOR_GEM, rect)
            pygame.draw.rect(surface, _COLOR_WHITE, rect, 1)
            self._draw_centered_text(surface, "◇", _COLOR_WHITE, x, y, ts)

        elif tile_type == "PICKAXE":
            pygame.draw.rect(surface, _COLOR_PICKAXE, rect)
            self._draw_centered_text(surface, "P", _COLOR_WHITE, x, y, ts)

        elif tile_type == "DYNAMITE":
            pygame.draw.rect(surface, _COLOR_DYNAMITE, rect)
            self._draw_centered_text(surface, "B", _COLOR_WHITE, x, y, ts)

        elif tile_type == "MAP":
            pygame.draw.rect(surface, _COLOR_MAP, rect)
            self._draw_centered_text(surface, "M", _COLOR_BLACK, x, y, ts)

        elif tile_type == "HEART":
            pygame.draw.rect(surface, _COLOR_HEART, rect)
            self._draw_centered_text(surface, "♥", _COLOR_WHITE, x, y, ts)

        elif tile_type == "SHIELD":
            pygame.draw.rect(surface, _COLOR_SHIELD, rect)
            self._draw_centered_text(surface, "S", _COLOR_WHITE, x, y, ts)

        elif tile_type == "AMULET":
            pygame.draw.rect(surface, _COLOR_AMULET, rect)
            self._draw_centered_text(surface, "A", _COLOR_WHITE, x, y, ts)

        elif tile_type in ("KEY_RED", "KEY_GREEN", "KEY_BLUE", "KEY_EXIT"):
            key_colors = {
                "KEY_RED": _COLOR_KEY_RED,
                "KEY_GREEN": _COLOR_KEY_GREEN,
                "KEY_BLUE": _COLOR_KEY_BLUE,
                "KEY_EXIT": _COLOR_KEY_EXIT,
            }
            pygame.draw.rect(surface, key_colors[tile_type], rect)
            self._draw_centered_text(surface, "K", _COLOR_WHITE, x, y, ts)

        elif tile_type == "MONSTER":
            animator = extra_info if isinstance(extra_info, Animator) else None
            self._draw_monster_fallback(surface, x, y, animator)

        elif tile_type == ACTIVE_MUMMY:
            # extra_info 提供一个整数计数器以实现闪烁动画
            self._draw_active_mummy_fallback(surface, x, y, extra_info)

        elif tile_type == MUMMY_KING:
            # extra_info 提供一个整数计数器以实现暗金边框闪烁动画
            self._draw_mummy_king_fallback(surface, x, y, extra_info)

        elif tile_type == "STAIRS":
            pygame.draw.rect(surface, _COLOR_STAIRS, rect)
            # 黑色斜条纹
            for i in range(0, ts, 6):
                pygame.draw.line(surface, _COLOR_BLACK,
                                 (x + i, y), (x + i, y + ts), 1)
            self._draw_centered_text(surface, "DN", _COLOR_BLACK, x, y, ts)

        elif tile_type == "PLAYER":
            # 支持两种 extra_info 形态：
            # 1) dict: {"animator": Animator, "player_state": PlayerState}
            # 2) Animator 实例（向后兼容）
            animator = None
            player_state = None
            if isinstance(extra_info, dict):
                animator = extra_info.get("animator")
                player_state = extra_info.get("player_state")
            elif isinstance(extra_info, Animator):
                animator = extra_info
            self._draw_player_fallback(surface, x, y, animator, player_state)

        elif tile_type == "FLAG":
            center = (x + ts // 2, y + ts // 2)
            radius = ts // 3
            pygame.draw.circle(surface, _COLOR_FLAG, center, radius)
            pygame.draw.circle(surface, _COLOR_WHITE, center, radius, 1)
            self._draw_centered_text(surface, "F", _COLOR_WHITE, x, y, ts)

        elif tile_type == "CHEST":
            # 木色圆角矩形 + 黄色金锁扣横线 + [C] 文字
            pygame.draw.rect(surface, _COLOR_CHEST, rect, border_radius=4)
            pygame.draw.rect(surface, pal["DIRT_BORDER"], rect, 1, border_radius=4)
            # 金色锁扣横线（瓦片上方 1/3 处）
            lock_y = y + ts // 3
            pygame.draw.line(surface, _COLOR_CHEST_LOCK,
                             (x + 4, lock_y), (x + ts - 4, lock_y), 3)
            # 锁扣中心圆点
            pygame.draw.circle(surface, _COLOR_CHEST_LOCK,
                               (x + ts // 2, lock_y), ts // 8)
            self._draw_centered_text(surface, "[C]", _COLOR_WHITE, x, y, ts)

        elif tile_type == "LOCKED_CHEST":
            # 深木色矩形 + 灰色网纹 + [LC] 文字
            pygame.draw.rect(surface, _COLOR_LOCKED_CHEST, rect)
            # 灰色斜线网纹
            for i in range(0, ts, 8):
                pygame.draw.line(surface, _COLOR_LOCKED_CHEST_GRID,
                                 (x + i, y), (x + i + ts // 2, y + ts // 2), 1)
                pygame.draw.line(surface, _COLOR_LOCKED_CHEST_GRID,
                                 (x + ts - i, y), (x + ts - i - ts // 2, y + ts // 2), 1)
            pygame.draw.rect(surface, pal["DIRT_BORDER"], rect, 2)
            self._draw_centered_text(surface, "[LC]", _COLOR_RED_NUM, x, y, ts)

        elif tile_type == "TORCH":
            # 火把：黑方框包围 + 橙红蜡烛/火苗 + 中央字符 "T"
            pygame.draw.rect(surface, _COLOR_TORCH_RING, rect)
            pygame.draw.rect(surface, _COLOR_BLACK, rect, 2)
            body_rect = pygame.Rect(x + ts // 2 - ts // 8,
                                    y + ts // 3,
                                    ts // 4, ts * 2 // 3)
            pygame.draw.rect(surface, _COLOR_TORCH_BODY, body_rect)
            # 火焰 —— 三道同心椭圆（外->中->芯）
            flame_x = x + ts // 2
            flame_base_y = y + ts // 3
            outer_rect = pygame.Rect(flame_x - ts // 5,
                                     flame_base_y - ts // 4,
                                     ts * 2 // 5, ts // 2)
            pygame.draw.ellipse(surface, _COLOR_TORCH_FLAME_OUTER, outer_rect)
            mid_rect = pygame.Rect(flame_x - ts // 8,
                                   flame_base_y - ts // 6,
                                   ts // 4, ts // 3)
            pygame.draw.ellipse(surface, _COLOR_TORCH_FLAME_MID, mid_rect)
            core_rect = pygame.Rect(flame_x - ts // 16,
                                    flame_base_y - ts // 8,
                                    ts // 8, ts // 4)
            pygame.draw.ellipse(surface, _COLOR_TORCH_FLAME_CORE, core_rect)
            self._draw_centered_text(surface, "T", _COLOR_TORCH_FLAME_CORE,
                                     x, y, ts)

        elif tile_type == SPIKE_TRAP:
            self._draw_spike_trap_fallback(surface, x, y, extra_info)

    # =========================================================================
    # 周期地刺退化渲染（第 50 课）
    # =========================================================================

    def _draw_spike_trap_fallback(self, surface: pygame.Surface,
                                  x: int, y: int,
                                  extra_info: Any = None):
        """周期地刺双态退化矢量渲染。

        - ``RETRACTED``（默认态 / ``extra_info != "EXTENDED"``）：
          覆盖地形底色 + 中央金属灰钢板 + 四角装饰气孔圆点。
        - ``EXTENDED``（``extra_info == "EXTENDED"``）：
          鲜黄警示底 + 稍小的金属内胆 + 四角白蓝边三角尖刺 + 红色"!"。

        ``extra_info`` 也接受 SpikeTrap 实例：按其 ``get_state()`` 决定态。
        """
        ts = self.tile_size
        rect = pygame.Rect(x, y, ts, ts)
        pal = BIOME_COLORS[self.current_biome]

        # 解析状态
        state = _SPIKE_STATE_RETRACTED
        if isinstance(extra_info, str):
            state = extra_info
        # 兼容 SpikeTrap 实例或带 get_state() 的对象
        elif extra_info is not None and hasattr(extra_info, "get_state"):
            try:
                state = extra_info.get_state()
            except Exception:
                state = _SPIKE_STATE_RETRACTED

        cx, cy = x + ts // 2, y + ts // 2
        tri_len = max(4, ts // 5)

        if state == _SPIKE_STATE_EXTENDED:
            # 危险态：鲜黄警示底
            pygame.draw.rect(surface, _COLOR_SPIKE_BG, rect)
            # 稍小的金属内胆
            inner = pygame.Rect(x + 8, y + 8, ts - 16, ts - 16)
            pygame.draw.rect(surface, _COLOR_SPIKE_METAL, inner, border_radius=3)
            pygame.draw.rect(surface, _COLOR_SPIKE_METAL_BORDER, inner,
                             2, border_radius=3)
            # 四角尖刺（上 / 下 / 左 / 右）
            # 上尖刺
            pygame.draw.polygon(surface, _COLOR_SPIKE_TRIANGLE,
                                [(x + 4, y), (x + ts - 4, y), (cx, y + tri_len)])
            pygame.draw.polygon(surface, _COLOR_SPIKE_TRIANGLE_BORDER,
                                [(x + 4, y), (x + ts - 4, y), (cx, y + tri_len)], 2)
            # 下尖刺
            pygame.draw.polygon(surface, _COLOR_SPIKE_TRIANGLE,
                                [(x + 4, y + ts), (x + ts - 4, y + ts),
                                 (cx, y + ts - tri_len)])
            pygame.draw.polygon(surface, _COLOR_SPIKE_TRIANGLE_BORDER,
                                [(x + 4, y + ts), (x + ts - 4, y + ts),
                                 (cx, y + ts - tri_len)], 2)
            # 左尖刺
            pygame.draw.polygon(surface, _COLOR_SPIKE_TRIANGLE,
                                [(x, y + 4), (x, y + ts - 4),
                                 (x + tri_len, cy)])
            pygame.draw.polygon(surface, _COLOR_SPIKE_TRIANGLE_BORDER,
                                [(x, y + 4), (x, y + ts - 4),
                                 (x + tri_len, cy)], 2)
            # 右尖刺
            pygame.draw.polygon(surface, _COLOR_SPIKE_TRIANGLE,
                                [(x + ts, y + 4), (x + ts, y + ts - 4),
                                 (x + ts - tri_len, cy)])
            pygame.draw.polygon(surface, _COLOR_SPIKE_TRIANGLE_BORDER,
                                [(x + ts, y + 4), (x + ts, y + ts - 4),
                                 (x + ts - tri_len, cy)], 2)
            # 中央红色警告
            self._draw_centered_text(surface, "!", _COLOR_RED_NUM,
                                     x, y, ts, bold=True)
        else:
            # 安全态：透明覆盖地形 + 金属钢板 + 装饰圆点
            pygame.draw.rect(surface, pal["UNCOVERED"], rect)
            inner = pygame.Rect(x + 6, y + 6, ts - 12, ts - 12)
            pygame.draw.rect(surface, _COLOR_SPIKE_METAL, inner, border_radius=3)
            pygame.draw.rect(surface, _COLOR_SPIKE_METAL_BORDER, inner,
                             2, border_radius=3)
            # 四角装饰圆点（设备气孔）
            hole_color = (50, 50, 55)
            hole_r = max(1, ts // 14)
            margin = 10
            for hx, hy in ((x + margin, y + margin),
                           (x + ts - margin, y + margin),
                           (x + margin, y + ts - margin),
                           (x + ts - margin, y + ts - margin)):
                pygame.draw.circle(surface, hole_color, (hx, hy), hole_r)

    # =========================================================================
    # 动画退化渲染（基于 Animator 的数学弹性动效）
    # =========================================================================

    def _draw_player_fallback(self, surface: pygame.Surface,
                              x: int, y: int,
                              animator: Animator | None,
                              player_state=None):
        """退化模式玩家渲染 — 根据动画状态应用数学弹性动效。

        Args:
            surface: 目标 Surface。
            x, y: 瓦片左上角像素坐标。
            animator: 可选 Animator，提供当前状态与计时。
                      为 None 时使用 IDLE/t=0（向后兼容）。
            player_state: 可选 PlayerState，用于绘制护盾波纹与四叶草绿芒。
        """
        ts = self.tile_size
        state = animator.current_state if animator else "IDLE"
        t = animator.state_time if animator else 0.0

        # 构建基础玩家图形（绿色圆形 + 白色十字）
        temp = pygame.Surface((ts, ts), pygame.SRCALPHA)
        cx, cy = ts // 2, ts // 2
        radius = ts // 3

        if state == "HURT":
            flash = int(t / 0.1) % 2
            player_color = (200, 30, 30) if flash == 0 else (0, 180, 0)
        else:
            player_color = (0, 180, 0)

        pygame.draw.circle(temp, player_color, (cx, cy), radius)
        pygame.draw.circle(temp, _COLOR_WHITE, (cx, cy), radius, 2)
        cross = radius // 2
        pygame.draw.line(temp, _COLOR_WHITE, (cx, cy - cross), (cx, cy + cross), 2)
        pygame.draw.line(temp, _COLOR_WHITE, (cx - cross, cy), (cx + cross, cy), 2)

        # ── 护盾呼吸波纹（在玩家 sprite 后方绘制） ──────────────
        if player_state is not None and getattr(player_state, "current_shields", 0) > 0:
            cx = x + ts // 2
            cy = y + ts // 2
            base_r = ts // 2 + 6
            pulse_r = int(base_r * (1.0 + 0.12 * math.sin(t * 8.0)))
            aura_surf = pygame.Surface((pulse_r * 2 + 8, pulse_r * 2 + 8), pygame.SRCALPHA)
            acx = pulse_r + 4
            pygame.draw.circle(aura_surf, (0, 240, 255, 80),  (acx, acx), pulse_r)
            pygame.draw.circle(aura_surf, (0, 240, 255, 160), (acx, acx), max(1, pulse_r - 4))
            surface.blit(aura_surf, (cx - acx, cy - acx))

        # ── 状态驱动的数学动效 ────────────────────────────────

        if state == "IDLE":
            # 呼吸：Y 轴缩放微幅振荡
            scale_y = 1.0 + 0.05 * math.sin(t * 6.0)
            new_h = max(1, int(ts * scale_y))
            scaled = pygame.transform.scale(temp, (ts, new_h))
            off_y = (ts - new_h) // 2
            surface.blit(scaled, (x, y + off_y))

        elif state.startswith("WALK"):
            # 弹性蹦跳：Y 轴压缩 + X 轴拉伸 + 浮动
            comp = 0.08 * abs(math.sin(t * 12.0))
            scale_y = 1.0 - comp
            scale_x = 1.0 + 0.04 * abs(math.sin(t * 12.0))
            new_w = max(1, int(ts * scale_x))
            new_h = max(1, int(ts * scale_y))
            scaled = pygame.transform.scale(temp, (new_w, new_h))
            ox = (ts - new_w) // 2
            oy = (ts - new_h) // 2
            float_off = int(3.0 * math.sin(t * 8.0))
            surface.blit(scaled, (x + ox, y + oy + float_off))

        elif state == "HURT":
            # 高频颤抖（指数衰减）
            amplitude = 4.0 * math.exp(-t * 5.0)
            sx = random.uniform(-amplitude, amplitude)
            sy = random.uniform(-amplitude, amplitude)
            surface.blit(temp, (x + sx, y + sy))

        elif state == "DIG":
            # 刺入旋转（0.3s 内完成一次正弦偏转）
            if t < 0.3:
                angle = 30.0 * math.sin(t * math.pi / 0.3)
                rotated = pygame.transform.rotate(temp, angle)
                rx = x + (ts - rotated.get_width()) // 2
                ry = y + (ts - rotated.get_height()) // 2
                surface.blit(rotated, (rx, ry))
            else:
                surface.blit(temp, (x, y))

        else:
            # 未知状态：静态绘制
            surface.blit(temp, (x, y))

        # ── 四叶草绿芒旋转光点（在所有状态动画之上） ──────────────
        if player_state is not None and getattr(player_state, "has_clover", False):
            cx = x + ts // 2
            top_y = y - 6
            for i, phase in enumerate((0.0, math.pi)):
                sx = cx + int(10 * math.sin(t * 4.0 + phase))
                sy = top_y + int(4 * math.cos(t * 3.0 + phase))
                spark = pygame.Surface((8, 8), pygame.SRCALPHA)
                pygame.draw.circle(spark, (34, 197, 94, 220), (4, 4), 3)
                pygame.draw.circle(spark, (180, 255, 180, 255), (4, 4), 1)
                surface.blit(spark, (sx - 4, sy - 4))

    def _draw_active_mummy_fallback(self, surface: pygame.Surface,
                                    x: int, y: int,
                                    blink_counter: int | None = None):
        """退化模式活性木乃伊渲染 — 深黑底 + 闪烁红色边框 + [AM] 文字。

        Args:
            surface:       目标 Surface。
            x, y:          瓦片左上角像素坐标。
            blink_counter: 整数计数器（如 GameManager 帧计数），用于颜色闪烁。
                           为 None 时使用固定亮度。
        """
        ts = self.tile_size
        rect = pygame.Rect(x, y, ts, ts)

        # 底色深黑
        pygame.draw.rect(surface, _COLOR_ACTIVE_MUMMY_BG, rect)

        # 边框颜色基于计数器闪烁（每 8 帧切换一次）
        if blink_counter is not None:
            bright = (blink_counter // 8) % 2 == 0
        else:
            bright = True
        border_color = _COLOR_ACTIVE_MUMMY_BORDER_BRIGHT if bright else _COLOR_ACTIVE_MUMMY_BORDER_DIM
        pygame.draw.rect(surface, border_color, rect, 2)

        # 中央 [AM] 文字
        self._draw_centered_text(surface, "[AM]", _COLOR_WHITE, x, y, ts)

    def _draw_mummy_king_fallback(self, surface: pygame.Surface,
                                  x: int, y: int,
                                  blink_counter: int | None = None):
        """退化模式法老王首领渲染 — 暗红底 + 双层暗金闪烁边框 + [MK] 文字。

        Args:
            surface:       目标 Surface。
            x, y:          瓦片左上角像素坐标。
            blink_counter: 整数计数器（如 GameManager 帧计数），用于颜色闪烁。
                           为 None 时使用固定亮度。
        """
        ts = self.tile_size
        rect = pygame.Rect(x, y, ts, ts)

        # 底色暗红
        pygame.draw.rect(surface, _COLOR_MUMMY_KING_BG, rect)

        # 内层边框（暗红，2 像素）
        inner = pygame.Rect(x + 3, y + 3, ts - 6, ts - 6)
        pygame.draw.rect(surface, _COLOR_MUMMY_KING_INNER, inner, 2)

        # 外层边框颜色基于计数器闪烁（每 8 帧切换一次）
        if blink_counter is not None:
            bright = (blink_counter // 8) % 2 == 0
        else:
            bright = True
        border_color = (_COLOR_MUMMY_KING_BORDER_BRIGHT if bright
                        else _COLOR_MUMMY_KING_BORDER)
        pygame.draw.rect(surface, border_color, rect, 2)

        # 中央亮黄 [MK] 文字（Pharaoh Mummy King 皇冠标识）
        self._draw_centered_text(surface, "[MK]", _COLOR_YELLOW_NUM, x, y, ts)

    def _draw_monster_fallback(self, surface: pygame.Surface,
                               x: int, y: int,
                               animator: Animator | None):
        """退化模式怪物渲染 — 简易动画动效。"""
        ts = self.tile_size
        state = animator.current_state if animator else "IDLE"
        t = animator.state_time if animator else 0.0

        temp = pygame.Surface((ts, ts), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, ts, ts)

        monster_color = (20, 80, 40)
        if state == "HURT":
            monster_color = (200, 30, 30) if int(t / 0.12) % 2 == 0 else (20, 80, 40)

        pygame.draw.rect(temp, monster_color, rect)
        # 白色眼睛
        eye_r = max(2, ts // 10)
        pygame.draw.circle(temp, _COLOR_WHITE, (ts // 3, ts // 3), eye_r)
        pygame.draw.circle(temp, _COLOR_WHITE, (2 * ts // 3, ts // 3), eye_r)
        self._draw_centered_text(temp, "M", _COLOR_WHITE, 0, 0, ts)

        # ── 状态驱动的简易动效 ────────────────────────────────

        if state == "IDLE":
            scale_y = 1.0 + 0.04 * math.sin(t * 5.0)
            new_h = max(1, int(ts * scale_y))
            scaled = pygame.transform.scale(temp, (ts, new_h))
            off_y = (ts - new_h) // 2
            surface.blit(scaled, (x, y + off_y))

        elif state == "ATTACK":
            stretch = 1.0 + 0.1 * abs(math.sin(t * 8.0))
            new_w = max(1, int(ts * stretch))
            scaled = pygame.transform.scale(temp, (new_w, ts))
            off_x = (ts - new_w) // 2
            surface.blit(scaled, (x + off_x, y))

        elif state == "HURT":
            amplitude = 4.0 * math.exp(-t * 4.0)
            sx = random.uniform(-amplitude, amplitude)
            sy = random.uniform(-amplitude, amplitude)
            surface.blit(temp, (x + sx, y + sy))

        else:
            surface.blit(temp, (x, y))

    # =========================================================================
    # 辅助方法
    # =========================================================================

    @staticmethod
    def _get_number_color(num: int) -> tuple[int, int, int]:
        """根据 Minesweeper 风格返回数字 1-8 对应的颜色。"""
        colors = {
            1: _COLOR_BLUE_NUM,
            2: _COLOR_GREEN_NUM,
            3: _COLOR_RED_NUM,
            4: _COLOR_PURPLE_NUM,
            5: _COLOR_MAROON_NUM,
            6: _COLOR_CYAN_NUM,
            7: _COLOR_DARK_NUM,
            8: _COLOR_YELLOW_NUM,
        }
        return colors.get(num, _COLOR_WHITE)

    def _draw_centered_text(self, surface: pygame.Surface, text: str,
                            color: tuple[int, int, int],
                            x: int, y: int, ts: int, bold: bool = False):
        """在瓦片中央绘制文本。

        Args:
            surface: 目标 Surface。
            text: 文本内容。
            color: RGB 颜色元组。
            x: 瓦片左上角 X。
            y: 瓦片左上角 Y。
            ts: 瓦片大小（tile_size）。
            bold: 是否加粗。
        """
        try:
            from src.asset_manager import AssetManager
            font = AssetManager.get_instance().get_font(None, ts // 2)
        except Exception:
            font = pygame.font.Font(None, ts // 2)

        try:
            label = font.render(text, True, color)
        except Exception:
            return

        text_x = x + (ts - label.get_width()) // 2
        text_y = y + (ts - label.get_height()) // 2
        surface.blit(label, (text_x, text_y))


def _run_standalone_test():
    """简易独立测试 — 直接运行此文件时执行。"""
    import os
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()

    ts = TILE_SIZE
    test_surface = pygame.Surface((ts * 8, ts * 9))
    renderer = TileRenderer(tile_size=ts)

    print(f"TileRenderer initialized: use_fallback={renderer.use_fallback}")

    # 测试所有瓦片类型的退化渲染
    tile_types = list(TILE_COORDS.keys())
    print(f"Testing {len(tile_types)} tile types...")
    for idx, ttype in enumerate(tile_types):
        col_idx = idx % 8
        row_idx = idx // 8
        px = col_idx * ts
        py = row_idx * ts
        extra = "3" if ttype == "UNCOVERED" else None
        renderer.draw_tile(test_surface, ttype, px, py, extra_info=extra)

    # 测试额外信息渲染
    print("Testing UNCOVERED with number 4...")
    renderer.draw_tile(test_surface, "UNCOVERED", 4 * ts, 8 * ts, extra_info="4")
    renderer.draw_tile(test_surface, "UNCOVERED", 5 * ts, 8 * ts, extra_info="8")
    renderer.draw_tile(test_surface, "UNCOVERED", 6 * ts, 8 * ts, extra_info="0")

    print("[PASS] All tile types rendered without error")
    print(f"[PASS] Rendered surface size: {test_surface.get_width()}x{test_surface.get_height()}")
    print("=== ALL STANDALONE TESTS PASSED ===")


if __name__ == "__main__":
    _run_standalone_test()
