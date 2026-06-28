"""摄像机视口控制器 — Microsoft Treasure Hunt

实现平滑随动（Lerp）与边界钳制（Clamping）的 2D 摄像机，
负责将世界坐标映射到屏幕坐标、计算可视瓦片范围（用于视口裁剪渲染）。

使用方式::

    cam = Camera()
    cam.update(player_px_x, player_px_y, map_width_px, map_height_px, dt)
    grid_x, grid_y = cam.screen_to_grid(mouse_x, mouse_y)
    start_col, end_col, start_row, end_row = cam.get_visible_tile_bounds(cols, rows)
"""

import os as _os
import sys as _sys
import random as _random

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

from config import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_HEIGHT, TILE_SIZE


class Camera:
    """2D 摄像机 — 平滑跟随玩家并钳制在地图边界内。

    坐标系：
    - offset_x / offset_y 为摄像机左下角在世界像素坐标中的位置。
    - 屏幕坐标 = 世界坐标 - 摄像机偏移。
    - shake_offset_x / shake_offset_y 为震颤瞬态偏移，
      通过 get_render_offset() 叠加到最终渲染偏移中。
    """

    def __init__(self):
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0

        # 屏幕震颤状态
        self.shake_duration: float = 0.0
        self.shake_amplitude: float = 0.0
        self.shake_offset_x: float = 0.0
        self.shake_offset_y: float = 0.0

    # =========================================================================
    # 平滑随动与边界钳制
    # =========================================================================

    def update(self, player_px_x: float, player_px_y: float,
               map_width_px: int, map_height_px: int, dt: float):
        """更新摄像机偏移，使玩家趋近屏幕中心。

        Args:
            player_px_x:  玩家在世界像素坐标中的 X（中心点）
            player_px_y:  玩家在世界像素坐标中的 Y（中心点）
            map_width_px:  地图总像素宽度
            map_height_px: 地图总像素高度
            dt:           本帧时间间隔（秒），会被安全钳制到 [0, 0.25]
        """
        # 目标点定位：让玩家位于游戏视口几何中心
        target_x = player_px_x - SCREEN_WIDTH / 2
        target_y = player_px_y - HUD_HEIGHT - (SCREEN_HEIGHT - HUD_HEIGHT) / 2

        # 安全 dt 控制：防止过大步长导致跳帧
        safe_dt = min(dt, 0.25)

        # 平滑插值（Lerp），刚度因子 10.0
        self.offset_x += (target_x - self.offset_x) * 10.0 * safe_dt
        self.offset_y += (target_y - self.offset_y) * 10.0 * safe_dt

        # 边界钳制：确保不滑出地图边缘
        max_x = max(0, map_width_px - SCREEN_WIDTH)
        max_y = max(0, map_height_px - (SCREEN_HEIGHT - HUD_HEIGHT))
        self.offset_x = max(0, min(self.offset_x, max_x))
        self.offset_y = max(0, min(self.offset_y, max_y))

        # ── 屏幕震颤：噪声偏移 + 时间衰减 ────────────────────────
        if self.shake_duration > 0:
            self.shake_offset_x = _random.uniform(-self.shake_amplitude,
                                                    self.shake_amplitude)
            self.shake_offset_y = _random.uniform(-self.shake_amplitude,
                                                    self.shake_amplitude)
            self.shake_duration -= safe_dt
            if self.shake_duration <= 0:
                self.shake_duration = 0.0
                self.shake_offset_x = 0.0
                self.shake_offset_y = 0.0

    # =========================================================================
    # 屏幕震颤控制
    # =========================================================================

    def trigger_shake(self, duration: float = 0.4, amplitude: float = 8.0):
        """触发屏幕震颤。

        Args:
            duration:  震颤持续秒数（默认 0.4）
            amplitude: 最大偏移像素量（默认 8.0）
        """
        self.shake_duration = duration
        self.shake_amplitude = amplitude
        # 立即产生初始偏移
        self.shake_offset_x = _random.uniform(-amplitude, amplitude)
        self.shake_offset_y = _random.uniform(-amplitude, amplitude)

    def get_render_offset(self) -> tuple[float, float]:
        """获取用于渲染的最终摄像机偏移（叠加了震颤偏移）。

        Returns:
            (render_offset_x, render_offset_y)
        """
        return (self.offset_x + self.shake_offset_x,
                self.offset_y + self.shake_offset_y)

    # =========================================================================
    # 坐标映射
    # =========================================================================

    def screen_to_grid(self, screen_x: int, screen_y: int) -> tuple[int, int]:
        """将屏幕像素坐标转换为网格坐标。

        若点击位于 HUD 区域（Y < HUD_HEIGHT），返回 (-1, -1) 代表无效。

        Args:
            screen_x: 屏幕像素 X 坐标
            screen_y: 屏幕像素 Y 坐标

        Returns:
            (grid_x, grid_y) 网格坐标，或 (-1, -1) 表示无效操作。
        """
        if screen_y < HUD_HEIGHT:
            return (-1, -1)
        grid_x = int((screen_x + self.offset_x) / TILE_SIZE)
        grid_y = int((screen_y - HUD_HEIGHT + self.offset_y) / TILE_SIZE)
        return (grid_x, grid_y)

    # =========================================================================
    # 视口裁剪
    # =========================================================================

    def get_visible_tile_bounds(self, map_cols: int, map_rows: int) -> tuple[int, int, int, int]:
        """计算当前屏幕可视的瓦片行列范围（用于视口裁剪优化渲染）。

        Args:
            map_cols: 地图总列数
            map_rows: 地图总行数

        Returns:
            (start_col, end_col, start_row, end_row) — 半开区间 [start, end)
        """
        start_col = max(0, int(self.offset_x / TILE_SIZE))
        end_col = min(map_cols, int((self.offset_x + SCREEN_WIDTH) / TILE_SIZE) + 1)
        start_row = max(0, int(self.offset_y / TILE_SIZE))
        end_row = min(map_rows, int((self.offset_y + SCREEN_HEIGHT - HUD_HEIGHT) / TILE_SIZE) + 1)
        return (start_col, end_col, start_row, end_row)
