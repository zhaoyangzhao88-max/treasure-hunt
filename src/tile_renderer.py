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

from src.config import TILE_SIZE, BiomeType, BIOME_COLORS
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
    # ---- 特殊 ----
    "PLAYER": (0, 3),
    "FLAG": (1, 3),
    "LOCKED_CHEST": (2, 3),
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
                  x: int, y: int, extra_info: Any = None):
        """在指定像素位置绘制一个瓦片。

        Args:
            surface: 目标 Surface。
            tile_type: 瓦片类型（"DIRT", "COIN", "PLAYER" 等）。
            x: 目标绘制位置的左上角 X 坐标（像素）。
            y: 目标绘制位置的左上角 Y 坐标（像素）。
            extra_info: 可选附加信息，如 UNCOVERED 的邻域雷数字符串。
        """
        if not self.use_fallback:
            tile_surf = self.get_sliced_tile(tile_type)
            if tile_surf is not None:
                surface.blit(tile_surf, (x, y))
                return

        # 退化分支：按瓦片类型绘制彩色几何 + 文字
        self._draw_fallback(surface, tile_type, x, y, extra_info)

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

        elif tile_type == "STAIRS":
            pygame.draw.rect(surface, _COLOR_STAIRS, rect)
            # 黑色斜条纹
            for i in range(0, ts, 6):
                pygame.draw.line(surface, _COLOR_BLACK,
                                 (x + i, y), (x + i, y + ts), 1)
            self._draw_centered_text(surface, "DN", _COLOR_BLACK, x, y, ts)

        elif tile_type == "PLAYER":
            animator = extra_info if isinstance(extra_info, Animator) else None
            self._draw_player_fallback(surface, x, y, animator)

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

    # =========================================================================
    # 动画退化渲染（基于 Animator 的数学弹性动效）
    # =========================================================================

    def _draw_player_fallback(self, surface: pygame.Surface,
                              x: int, y: int,
                              animator: Animator | None):
        """退化模式玩家渲染 — 根据动画状态应用数学弹性动效。

        Args:
            surface: 目标 Surface。
            x, y: 瓦片左上角像素坐标。
            animator: 可选 Animator，提供当前状态与计时。
                      为 None 时使用 IDLE/t=0（向后兼容）。
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
