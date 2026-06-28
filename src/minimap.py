"""实时小地图渲染器 — Microsoft Treasure Hunt

以缩略图形式在屏幕右下角绘制完整地图的全局概览，
标记玩家位置、已探索区域和摄像机视口框线，
让玩家时刻了解自己在地牢中的方位。

使用方式::

    minimap = Minimap(game_map, player_x, player_y)
    # 每帧在 render() 中：
    minimap.player_x = new_x
    minimap.player_y = new_y
    minimap.render(surface, camera)
    # Tab 切换显示/隐藏：
    minimap.toggle()
"""

import os as _os
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from src.config import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_HEIGHT, TILE_SIZE


# =============================================================================
# 常量
# =============================================================================

# 小地图最大边长（像素）
MINIMAP_MAX_SIZE = 180

# 小地图距屏幕边缘的留白
MINIMAP_MARGIN = 8

# 玩家标记在 minimap 上的亮点尺寸（像素边长）
PLAYER_DOT_SIZE = 3


# =============================================================================
# 固定高对比度色板（独立于 Biome，始终可读）
# =============================================================================

_MINIMAP_COLORS = {
    "DIRT":       (80, 55, 35),       # 暗棕 — 未揭开泥土
    "UNCOVERED":  (55, 70, 90),       # 蓝灰 — 已揭开空地
    "WALL":       (25, 25, 35),       # 近黑 — 不可破坏墙
    "TRAP":       (180, 50, 50),      # 红 — 已揭开的数字格（邻雷>0）
    "FLAG":       (255, 100, 0),      # 橙 — 红旗标记
    "PLAYER":     (0, 220, 255),      # 青蓝 — 玩家位置
    "EXIT":       (255, 215, 0),      # 金色 — 出口/楼梯
    "VIEWPORT":   (255, 255, 255),    # 白 — 视口矩形框线
    "BG":         (0, 0, 0),          # 黑 — 小地图背景
    "BG_ALPHA":   180,                # 背景透明度
    "BORDER":     (100, 100, 100),    # 灰 — 外框描边
}


# =============================================================================
# Minimap 类
# =============================================================================

class Minimap:
    """实时小地图渲染器 — 将 GameMap 全图缩约绘制到屏幕右下角。

    属性:
        game_map: GameMap 引用（直接读取，不拷贝）
        player_x / player_y: 玩家当前网格坐标（由外部帧间更新）
        pixel_size: 每个地图格子映射到 minimap 上的像素边长
        minimap_width / minimap_height: minimap Surface 的像素尺寸
    """

    def __init__(self, game_map, player_x: int, player_y: int):
        """初始化小地图。

        Args:
            game_map: GameMap 实例（持引用，不拷贝）
            player_x: 玩家初始网格 X 坐标
            player_y: 玩家初始网格 Y 坐标
        """
        self.game_map = game_map
        self.player_x = player_x
        self.player_y = player_y

        # 计算自适应像素比
        map_max_dim = max(game_map.width, game_map.height)
        self.pixel_size: int = max(1, MINIMAP_MAX_SIZE // map_max_dim)
        self.minimap_width: int = game_map.width * self.pixel_size
        self.minimap_height: int = game_map.height * self.pixel_size

        # 显示/隐藏状态（默认开启）
        self._visible: bool = True

    # =========================================================================
    # 公共 API
    # =========================================================================

    @property
    def visible(self) -> bool:
        """当前小地图是否可见。"""
        return self._visible

    def toggle(self) -> None:
        """切换小地图显示/隐藏。"""
        self._visible = not self._visible

    def render(self, surface: pygame.Surface, camera=None) -> None:
        """将小地图渲染到屏幕右下角（含视口框线与玩家标记）。

        Args:
            surface: 目标 Surface（通常是屏幕 Surface）
            camera: Camera 实例，用于计算视口框线；None 时跳过视口框线
        """
        if not self._visible:
            return

        game_map = self.game_map
        if game_map is None:
            return

        # ---- 1) 创建 minimap Surface（透明背景）----
        mm_surf = pygame.Surface(
            (self.minimap_width, self.minimap_height),
            pygame.SRCALPHA,
        )
        mm_surf.fill((0, 0, 0, _MINIMAP_COLORS["BG_ALPHA"]))

        ps = self.pixel_size

        # ---- 2) 遍历全图，逐格着色 ----
        terrain_color = _MINIMAP_COLORS["DIRT"]
        uncovered_color = _MINIMAP_COLORS["UNCOVERED"]
        wall_color = _MINIMAP_COLORS["WALL"]
        trap_color = _MINIMAP_COLORS["TRAP"]
        flag_color = _MINIMAP_COLORS["FLAG"]
        exit_color = _MINIMAP_COLORS["EXIT"]

        for row in range(game_map.height):
            for col in range(game_map.width):
                terrain = game_map.layer0[row][col]
                obstacle = game_map.layer1[row][col]

                # 确定底色
                if obstacle == "WALL":
                    color = wall_color
                elif terrain == "UNCOVERED":
                    # 数字格（邻雷 > 0）用红色标记
                    if game_map.get_adjacent_traps_count(col, row) > 0:
                        color = trap_color
                    else:
                        color = uncovered_color
                else:
                    color = terrain_color

                # 绘制格子
                rect = pygame.Rect(col * ps, row * ps, ps, ps)
                mm_surf.fill(color, rect)

                # 红旗覆盖
                if game_map.flags[row][col]:
                    mm_surf.fill(flag_color, rect)

                # 出口 / 楼梯标记（layer2 中的特殊实体）
                entity = game_map.layer2[row][col]
                if entity in ("STAIRS", "EXIT_GATE"):
                    # 用 1px 或更大的金色方块标记
                    mm_surf.fill(exit_color, rect)

        # ---- 3) 玩家位置亮点 ----
        if (0 <= self.player_x < game_map.width
                and 0 <= self.player_y < game_map.height):
            dot = pygame.Rect(
                self.player_x * ps,
                self.player_y * ps,
                PLAYER_DOT_SIZE * ps,
                PLAYER_DOT_SIZE * ps,
            )
            # 钳制到 minimap 边界内
            dot.clamp_ip(mm_surf.get_rect())
            mm_surf.fill(_MINIMAP_COLORS["PLAYER"], dot)

        # ---- 4) 摄像机视口矩形框 ----
        if camera is not None:
            self._draw_viewport_rect(mm_surf, camera)

        # ---- 5) 外框描边 ----
        pygame.draw.rect(mm_surf, _MINIMAP_COLORS["BORDER"],
                         mm_surf.get_rect(), 1)

        # ---- 6) Blit 到屏幕右下角 ----
        dest_x = SCREEN_WIDTH - self.minimap_width - MINIMAP_MARGIN
        dest_y = SCREEN_HEIGHT - self.minimap_height - MINIMAP_MARGIN
        surface.blit(mm_surf, (dest_x, dest_y))

    # =========================================================================
    # 内部辅助
    # =========================================================================

    def _draw_viewport_rect(self, mm_surf: pygame.Surface, camera) -> None:
        """在小地图上绘制摄像机视口对应的矩形框线。

        将摄像机的屏幕像素范围反算为网格范围，
        再映射到 minimap 像素坐标。

        Args:
            mm_surf: minimap 内部 Surface
            camera: Camera 实例
        """
        ps = self.pixel_size

        # 摄像机可视网格范围
        sc, ec, sr, er = camera.get_visible_tile_bounds(
            self.game_map.width, self.game_map.height
        )

        # 映射到 minimap 像素
        vp_x = sc * ps
        vp_y = sr * ps
        vp_w = (ec - sc) * ps
        vp_h = (er - sr) * ps

        # 钳制宽高不低于 1
        vp_w = max(1, vp_w)
        vp_h = max(1, vp_h)

        vp_rect = pygame.Rect(vp_x, vp_y, vp_w, vp_h)
        pygame.draw.rect(mm_surf, _MINIMAP_COLORS["VIEWPORT"], vp_rect, 1)
