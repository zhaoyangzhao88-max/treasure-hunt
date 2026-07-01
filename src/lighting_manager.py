"""实时光照计算与阴影遮罩管理 — Microsoft Treasure Hunt（第 55 课）

提供 LightingManager 类，负责三件事：
1) 根据当前地貌返回实时基础视野半径；
2) 累积玩家捡到的火把所带来的额外视野加成（torch_expansion，关卡间可重置）；
3) 对任意瓦片 (tile_x, tile_y) 计算相对玩家的实时光照强度（0.0 ~ 1.0）。

光照度算法（calculate_tile_lighting）：
    dist = hypot(tile - player)
    - dist <= sight_radius            → 1.0         （完全明亮）
    - dist >= sight_radius + PENUMBRA → 0.0         （完全漆黑，战争迷雾）
    - 否则                            → 1.0 - (dist - sight_radius) / PENUMBRA   （半影淡化过渡）

本模块不依赖 pygame，可安全地在 Headless 单元测试 / 服务端逻辑中复用。
"""

import os as _os
import sys as _sys
import math
from typing import Optional

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

from src.config import (
    BiomeType,
    BIOME_BASE_SIGHT,
    FOG_PENUMBRA,
)


class LightingManager:
    """战争迷雾的实时光照计算管理器。

    状态由两段构成：
    - base_sight_radius：后备默认视野半径（当 BiomeType 未在 BIOME_BASE_SIGHT 中录入时使用）。
    - torch_expansion：玩家累计捡到的火把加成（每把 +TORCH_EXPANSION 格），
      进入新关卡时由 GameplayScreen.on_enter 调用 reset() 清空。
    """

    def __init__(self, base_sight_radius: float = 5.0,
                 torch_expansion: float = 0.0) -> None:
        """构造光照管理器。

        Args:
            base_sight_radius: 未录入地貌的后备视野半径（默认 5.0 格）。
            torch_expansion: 初始火把累计加成（默认 0.0；通常保持为 0）。
        """
        self.base_sight_radius: float = base_sight_radius
        self.torch_expansion: float = torch_expansion

    def reset(self) -> None:
        """重置火把累计加成 —— 在 GameplayScreen 进入新关卡时调用，保证跨关视野回滚。"""
        self.torch_expansion = 0.0

    def get_sight_radius(self, biome_type: BiomeType) -> float:
        """根据地貌类型返回实时视野半径（基础 + 火把加成）。

        Args:
            biome_type: 当前关卡的地貌。

        Returns:
            实时视野半径（单位：格），已包含 torch_expansion。
        """
        base = BIOME_BASE_SIGHT.get(biome_type, self.base_sight_radius)
        return base + self.torch_expansion

    def calculate_tile_lighting(self,
                                tile_x: int,
                                tile_y: int,
                                player_x: int,
                                player_y: int,
                                sight_radius: float) -> float:
        """计算某瓦片相对玩家的实时光照强度。

        Args:
            tile_x, tile_y: 目标瓦片坐标（格）。
            player_x, player_y: 玩家所在瓦片坐标（格）。
            sight_radius: 当前实时视野半径（格，已含火把加成）。

        Returns:
            光照强度值 ∈ [0.0, 1.0]。1.0 为完全明亮，0.0 为完全漆黑。
        """
        dist = math.hypot(tile_x - player_x, tile_y - player_y)
        if dist <= sight_radius:
            return 1.0
        if dist >= sight_radius + FOG_PENUMBRA:
            return 0.0
        # 半影区线性淡化
        return 1.0 - (dist - sight_radius) / FOG_PENUMBRA
