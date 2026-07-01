"""网格雷达迷你小地图（Minimap Overlay）系统 — Microsoft Treasure Hunt

以缩略图形式在屏幕中上方绘制完整地图的全局概览，
标记玩家位置、已探索区域、出口门与楼梯，
让玩家时刻了解自己在地牢中的方位。

使用方式::

    minimap = Minimap(game_map, player_state)
    # 每帧在 render() 中：
    minimap.render(surface, player_x, player_y, state_time)
    # Tab 切换显示/隐藏由 GameplayScreen 管理（show_minimap 标志）
"""

import os as _os
import sys as _sys
import math as _math

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from src.config import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_HEIGHT


# =============================================================================
# 常量
# =============================================================================

# 每个地图格子在小地图上的像素边长
GRID_SIZE = 6

# 格子之间的间距（像素）
GRID_GAP = 1

# 小地图最大边长（像素）— 动态钳制
MINIMAP_MAX_SIZE = 350

# 小地图距屏幕顶部的偏移（HUD 高度之下）
MINIMAP_TOP_OFFSET = 96

# 背景透明度（毛玻璃效果）
BG_ALPHA = 210

# 金色装饰细框透明度
BORDER_ALPHA = 180


# =============================================================================
# 固定高对比度色板（独立于 Biome，始终可读）
# =============================================================================

_MINIMAP_COLORS = {
    "WALL":       (10, 15, 25),       # 极深黑 — 不可破坏墙
    "DIRT":       (80, 50, 30),       # 深褐泥 — 未揭开泥土
    "UNCOVERED":  (50, 60, 70),       # 深灰 — 已掘通道
    "DIRT_WALL":  (140, 100, 70),     # 浅褐 — 泥墙
    "LOCK_RED":   (220, 60, 60),      # 红 — 红锁门
    "LOCK_GREEN": (60, 200, 80),      # 绿 — 绿锁门
    "LOCK_BLUE":  (60, 120, 220),     # 蓝 — 蓝锁门
    "EXIT":       (255, 215, 0),      # 金 — 出口门（呼吸闪烁）
    "STAIRS":     (240, 230, 140),    # 淡黄 — 楼梯
    "PLAYER_G":   (34, 197, 94),      # 亮绿 — 玩家标志（高频闪烁）
    "PLAYER_W":   (255, 255, 255),    # 亮白 — 玩家标志（高频闪烁）
    "BG":         (15, 23, 42, BG_ALPHA),       # 暗色半透明面板背景
    "BORDER":     (255, 215, 0, BORDER_ALPHA),  # 金色细框装饰线
}


# =============================================================================
# Minimap 类
# =============================================================================

class Minimap:
    """网格雷达迷你小地图 — 将 GameMap 全图缩约绘制到屏幕中上方。

    属性:
        game_map: GameMap 引用（直接读取，不拷贝）
        player_state: PlayerState 引用
        grid_size: 每个地图格子映射到 minimap 上的像素边长
        minimap_width / minimap_height: minimap Surface 的像素尺寸
    """

    def __init__(self, game_map, player_state):
        """初始化小地图。

        Args:
            game_map: GameMap 实例（持引用，不拷贝）
            player_state: PlayerState 实例
        """
        self.game_map = game_map
        self.player_state = player_state
        self.grid_size = GRID_SIZE

        # 动态算定画布大小（含间距），并钳制在 MINIMAP_MAX_SIZE 内
        cols = game_map.width
        rows = game_map.height
        raw_w = cols * (GRID_SIZE + GRID_GAP) - GRID_GAP
        raw_h = rows * (GRID_SIZE + GRID_GAP) - GRID_GAP
        scale = 1.0
        if raw_w > MINIMAP_MAX_SIZE:
            scale = MINIMAP_MAX_SIZE / raw_w
        if raw_h > MINIMAP_MAX_SIZE:
            scale = min(scale, MINIMAP_MAX_SIZE / raw_h)
        self.grid_size = max(1, int(GRID_SIZE * scale))
        # 重新计算最终画布尺寸
        self.minimap_width = cols * (self.grid_size + GRID_GAP) - GRID_GAP
        self.minimap_height = rows * (self.grid_size + GRID_GAP) - GRID_GAP

    # =========================================================================
    # 公共 API
    # =========================================================================

    def render(self, surface: pygame.Surface, player_x: int, player_y: int,
               state_time: float) -> None:
        """将小地图渲染到屏幕中上方（含金色细框与玩家闪烁标志）。

        Args:
            surface: 目标 Surface（通常是屏幕 Surface）
            player_x: 玩家当前网格 X 坐标
            player_y: 玩家当前网格 Y 坐标
            state_time: 当前状态时间（秒），用于呼吸/闪烁动画
        """
        game_map = self.game_map
        if game_map is None:
            return

        w = max(1, self.minimap_width)
        h = max(1, self.minimap_height)

        # ---- 1) 创建 minimap Surface（透明背景）----
        mm_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        mm_surf.fill(_MINIMAP_COLORS["BG"])

        gs = self.grid_size

        # ---- 2) 遍历全图，逐格着色 ----
        for row in range(game_map.height):
            for col in range(game_map.width):
                rx = col * (gs + GRID_GAP)
                ry = row * (gs + GRID_GAP)

                # 越界保护（极端情况下）
                if rx + gs > w or ry + gs > h:
                    continue

                terrain = game_map.layer0[row][col]
                obstacle = game_map.layer1[row][col]
                entity = game_map.layer2[row][col]

                # 确定底色（优先级：不可破坏墙 > 泥墙 > 已掘通道 > 泥土）
                if obstacle == "WALL":
                    color = _MINIMAP_COLORS["WALL"]
                elif obstacle == "DIRT_WALL":
                    color = _MINIMAP_COLORS["DIRT_WALL"]
                elif terrain == "UNCOVERED":
                    color = _MINIMAP_COLORS["UNCOVERED"]
                elif terrain == "DIRT":
                    color = _MINIMAP_COLORS["DIRT"]
                else:
                    color = _MINIMAP_COLORS["DIRT"]

                rect = pygame.Rect(rx, ry, gs, gs)
                mm_surf.fill(color, rect)

                # 锁门（layer1 包含 LOCK_）
                if obstacle.startswith("LOCK_") and obstacle not in ("LOCK_EXIT",):
                    if "RED" in obstacle:
                        mm_surf.fill(_MINIMAP_COLORS["LOCK_RED"], rect)
                    elif "GREEN" in obstacle:
                        mm_surf.fill(_MINIMAP_COLORS["LOCK_GREEN"], rect)
                    elif "BLUE" in obstacle:
                        mm_surf.fill(_MINIMAP_COLORS["LOCK_BLUE"], rect)

                # 出口门（呼吸闪烁金色点）
                if obstacle == "LOCK_EXIT":
                    pulse = abs(_math.sin(state_time * 10.0))
                    gold = _MINIMAP_COLORS["EXIT"]
                    exit_color = (
                        int(gold[0] * (0.4 + 0.6 * pulse)),
                        int(gold[1] * (0.4 + 0.6 * pulse)),
                        int(gold[2] * (0.4 + 0.6 * pulse)),
                    )
                    mm_surf.fill(exit_color, rect)

                # 楼梯（淡黄色小点）
                if entity == "STAIRS":
                    mm_surf.fill(_MINIMAP_COLORS["STAIRS"], rect)

        # ---- 3) 玩家位置闪烁圆点 ----
        if (0 <= player_x < game_map.width
                and 0 <= player_y < game_map.height):
            prx = player_x * (gs + GRID_GAP)
            pry = player_y * (gs + GRID_GAP)
            # 高频闪烁：绿/白交替
            blink = _math.sin(state_time * 14.0) >= 0
            dot_color = (_MINIMAP_COLORS["PLAYER_G"]
                         if blink else _MINIMAP_COLORS["PLAYER_W"])
            # 绘制圆形点（比格子略小，居中）
            dot_r = max(1, gs // 2)
            center = (prx + gs // 2, pry + gs // 2)
            try:
                pygame.draw.circle(mm_surf, dot_color, center, dot_r)
            except Exception:
                # 兜底：矩形点
                mm_surf.fill(dot_color,
                             pygame.Rect(prx, pry, gs, gs))

        # ---- 4) 金色细框装饰线 ----
        pygame.draw.rect(mm_surf, _MINIMAP_COLORS["BORDER"],
                         mm_surf.get_rect(), 1)

        # ---- 5) Blit 到屏幕中上方（水平居中，Y=MINIMAP_TOP_OFFSET）----
        dest_x = max(0, (SCREEN_WIDTH - w) // 2)
        dest_y = max(HUD_HEIGHT + 8,
                     min(MINIMAP_TOP_OFFSET,
                         SCREEN_HEIGHT - h - 8))
        surface.blit(mm_surf, (dest_x, dest_y))
