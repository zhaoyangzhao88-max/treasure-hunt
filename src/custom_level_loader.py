"""外部关卡解析引擎 — Microsoft Treasure Hunt

将根目录或外部路径提供的 JSON 格式的简写地图，解压为完整
``GameMap`` 四层网格（layer0 地形 / layer1 障碍 / layer2 实体 / traps 埋藏雷），
同时做严格的 Schema 断言与几何自检，拦截任何损坏的 ``custom_map.json`` 并抛出
描述性的 :class:`MalformedMapError`，供 gameplay_screen.on_enter 捕获，
在 UI 层保障游戏永不卡死在空白界面。

使用方式
--------
.. code-block:: python

    from src.custom_level_loader import CustomLevelLoader, MalformedMapError

    loader = CustomLevelLoader()
    game_map, start_pos, exit_pos = loader.load_from_json("custom_map.json")

    # 或者直接解析 JSON 字符串（测试友好路径）
    game_map, start_pos, exit_pos = loader.load_from_json(raw_json, is_raw_string=True)

JSON 字段契约
------------
::

    {
      "width": 6, "height": 6,
      "start_pos": [1, 1],
      "exit_pos":  [4, 4],
      "layer0": [ ["D","D",...], ... ],
      "layer1": [ [".","W",...], ... ],
      "layer2": [ [".","c",...], ... ],
      "traps":  [ [0,0,...],    ... ]
    }
"""

from __future__ import annotations

import json as _json
import os as _os
import sys as _sys

# 任务书明确要求引用 Pygame：loader 自身不依赖 Pygame 显示模块，
# 但声明式引用让调用方（gameplay_screen）可感知运行时图谱完整性。
# 在无 pygame 的特殊环境下以防御性 try/except 保持模块可导入。
try:
    import pygame as _pygame  # noqa: F401
except ImportError:  # pragma: no cover — 特殊无 pygame 环境
    _pygame = None  # type: ignore[assignment]

# 兼容独立运行与测试沙盒：确保能引用 src.map_data / src.config
_src = _os.path.dirname(_os.path.abspath(__file__))
if _src not in _sys.path:
    _sys.path.insert(0, _src)

from src.map_data import GameMap  # noqa: E402


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------

class MalformedMapError(Exception):
    """外部地图 JSON 不符合契约时抛出的结构化错误。

    单一 ``message`` 字段承载可读的失败原因（含缺失字段名、几何差异、
    未知符号等上下文），便于 gameplay_screen.on_enter 打印严重警告
    与单元测试做 ``msg_substr`` 匹配。
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


# ---------------------------------------------------------------------------
# 简写 → 全名 对照 CHAR_TO_TILE
# ---------------------------------------------------------------------------
# 任务书拆解：
#   layer0 地形  : D=DIRT, U=UNCOVERED
#   layer1 障碍  .=NONE, W=WALL, d=DIRT_WALL
#                 r=LOCK_RED, g=LOCK_GREEN, b=LOCK_BLUE, E=LOCK_EXIT
#                 S=SPIKE_RETRACTED（统一映射到地刺基础状态 SPIKE_TRAP）
#   layer2 实体  .=NONE, c=COIN, g=GEM, p=PICKAXE, y=DYNAMITE, m=MAP
#                 h=HEART, s=SHIELD, a=AMULET, w=ARROW, t=MACHETE
#                 M=MONSTER, A=ACTIVE_MUMMY, K=STAIRS
#                 kr=KEY_RED, kg=KEY_GREEN, kb=KEY_BLUE, ke=KEY_EXIT
#                 cb=CHEST, cl=LOCKED_CHEST
#   traps 埋藏雷  0=False, 1=True
#
# 注意：字符 "g" 在 layer1（LOCK_GREEN）和 layer2（GEM）同时出现，
#       这是按层隔离的合法重载，不会冲突。

# 任务书要求的「地形层」CODEMAP —— layer0
_CHAR_TILE_LAYER0: dict[str, str] = {
    "D": "DIRT",
    "U": "UNCOVERED",
}

# 任务书要求的「障碍层」CODEMAP —— layer1
_CHAR_TILE_LAYER1: dict[str, str] = {
    ".": "NONE",
    "W": "WALL",
    "d": "DIRT_WALL",
    "r": "LOCK_RED",
    "g": "LOCK_GREEN",
    "b": "LOCK_BLUE",
    "E": "LOCK_EXIT",
    # 地刺：任务书允许 SPIKE_RETRACTED / SPIKE_EXTENDED 都统一到地刺基础状态
    "S": "SPIKE_TRAP",
}

# 任务书要求的「实体道具层」CODEMAP —— layer2
_CHAR_TILE_LAYER2: dict[str, str] = {
    ".": "NONE",
    "c": "COIN",
    "g": "GEM",
    "p": "PICKAXE",
    "y": "DYNAMITE",
    "m": "MAP",
    "h": "HEART",
    "s": "SHIELD",
    "a": "AMULET",
    "w": "ARROW",
    "t": "MACHETE",
    "M": "MONSTER",
    "A": "ACTIVE_MUMMY",
    "K": "STAIRS",
    "kr": "KEY_RED",
    "kg": "KEY_GREEN",
    "kb": "KEY_BLUE",
    "ke": "KEY_EXIT",
    "cb": "CHEST",
    "cl": "LOCKED_CHEST",
}

# 逆向映射：全名 → 简写字符（用于地图编辑器 JSON 导出）
_TILE_CHAR_LAYER0: dict[str, str] = {v: k for k, v in _CHAR_TILE_LAYER0.items()}
_TILE_CHAR_LAYER1: dict[str, str] = {v: k for k, v in _CHAR_TILE_LAYER1.items()}
_TILE_CHAR_LAYER2: dict[str, str] = {v: k for k, v in _CHAR_TILE_LAYER2.items()}

TILE_TO_CHAR: dict[str, dict[str, str]] = {
    "layer0": _TILE_CHAR_LAYER0,
    "layer1": _TILE_CHAR_LAYER1,
    "layer2": _TILE_CHAR_LAYER2,
}

# 多层统一的 CHAR_TO_TILE 打包接口
CHAR_TO_TILE: dict[str, dict[str, str]] = {
    "layer0": _CHAR_TILE_LAYER0,
    "layer1": _CHAR_TILE_LAYER1,
    "layer2": _CHAR_TILE_LAYER2,
}

# traps 0/1 → bool 映射
_TRAP_BOOL: dict[int, bool] = {0: False, 1: True}

# traps bool → 0/1 映射（用于地图编辑器 JSON 导出）
TRAP_TO_INT: dict[bool, int] = {False: 0, True: 1}

# Schema 必填字段清单
_REQUIRED_FIELDS: list[str] = [
    "width",
    "height",
    "start_pos",
    "exit_pos",
    "layer0",
    "layer1",
    "layer2",
    "traps",
]

# 网格尺寸几何合法域
_MIN_DIM = 5
_MAX_DIM = 50


# ---------------------------------------------------------------------------
# 主加载器
# ---------------------------------------------------------------------------

class CustomLevelLoader:
    """外部 JSON 简写地图 → 完整 GameMap 的防腐层加载器。

    单一公开入口 :meth:`load_from_json` 承担：
      1) 读入（文件路径 或 原始 JSON 字符串）
      2) Schema 结构性断言
      3) 几何维度自检
      4) 简写查表解压 → 填充 GameMap
    任何失败都抛出 :class:`MalformedMapError`，绝不返回半填充状态。
    """

    def load_from_json(
        self,
        file_path_or_str: str,
        is_raw_string: bool = False,
    ) -> tuple[GameMap, tuple[int, int], tuple[int, int]]:
        """解析并解压 ``custom_map.json`` 为完整 GameMap。

        Args:
            file_path_or_str: JSON 文件路径，或（当 ``is_raw_string=True`` 时）
                直接的 JSON 文本。
            is_raw_string: 为 True 时把 ``file_path_or_str`` 视作 JSON 内容文本。

        Returns:
            三元组 ``(game_map, start_pos, exit_pos)``：
              * ``game_map``        : 完全填充的 GameMap 实例（含陷阱布尔矩阵）
              * ``start_pos``       : ``(x, y)`` 玩家出生点
              * ``exit_pos``        : ``(x, y)`` 出口坐标

        Raises:
            MalformedMapError: JSON 解析失败、字段缺失、几何违规、
                尺寸越界、起点/出口越界、未知简写符号。
        """
        # ------------------------------------------------------------------
        # 1) 读入
        # ------------------------------------------------------------------
        data = self._read_input(file_path_or_str, is_raw_string)

        # ------------------------------------------------------------------
        # 2) Schema 结构性断言
        # ------------------------------------------------------------------
        self._assert_required_fields(data)

        width: int = data["width"]
        height: int = data["height"]
        start_pos_raw = data["start_pos"]
        exit_pos_raw = data["exit_pos"]

        # ------------------------------------------------------------------
        # 3) 几何维度自检
        # ------------------------------------------------------------------
        self._check_dimensions(width, height)
        self._check_position(start_pos_raw, width, height, "start_pos")
        self._check_position(exit_pos_raw, width, height, "exit_pos")

        layer0_raw = data["layer0"]
        layer1_raw = data["layer1"]
        layer2_raw = data["layer2"]
        traps_raw = data["traps"]

        self._check_grid_geometry(layer0_raw, height, width, "layer0")
        self._check_grid_geometry(layer1_raw, height, width, "layer1")
        self._check_grid_geometry(layer2_raw, height, width, "layer2")
        self._check_grid_geometry(traps_raw, height, width, "traps")

        # ------------------------------------------------------------------
        # 4) 解压 → 填充 GameMap
        # ------------------------------------------------------------------
        game_map = GameMap(width, height)

        for y in range(height):
            for x in range(width):
                code0 = layer0_raw[y][x]
                code1 = layer1_raw[y][x]
                code2 = layer2_raw[y][x]
                code_t = traps_raw[y][x]

                tile0 = _CHAR_TILE_LAYER0.get(code0)
                if tile0 is None:
                    raise MalformedMapError(
                        f"Unknown tile code '{code0}' at layer0 ({y},{x})"
                    )
                game_map.layer0[y][x] = tile0

                tile1 = _CHAR_TILE_LAYER1.get(code1)
                if tile1 is None:
                    raise MalformedMapError(
                        f"Unknown tile code '{code1}' at layer1 ({y},{x})"
                    )
                game_map.layer1[y][x] = tile1

                tile2 = _CHAR_TILE_LAYER2.get(code2)
                if tile2 is None:
                    raise MalformedMapError(
                        f"Unknown tile code '{code2}' at layer2 ({y},{x})"
                    )
                game_map.layer2[y][x] = tile2

                if code_t not in _TRAP_BOOL:
                    raise MalformedMapError(
                        f"Invalid trap flag '{code_t}' at ({y}, {x}), expected 0 or 1"
                    )
                game_map.traps[y][x] = _TRAP_BOOL[code_t]

        return game_map, (int(start_pos_raw[0]), int(start_pos_raw[1])), (
            int(exit_pos_raw[0]),
            int(exit_pos_raw[1]),
        )

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _read_input(self, file_path_or_str: str, is_raw_string: bool) -> dict:
        """读取并解析 JSON 文本，统一错误 → MalformedMapError。"""
        try:
            if is_raw_string:
                return _json.loads(file_path_or_str)
            with open(file_path_or_str, encoding="utf-8") as f:
                return _json.loads(f.read())
        except _json.JSONDecodeError as exc:
            raise MalformedMapError(
                f"Invalid JSON format: {exc.msg} (line {exc.lineno})"
            ) from exc
        except (OSError, UnicodeDecodeError) as exc:
            # 交给调用方统一捕获（gameplay_screen 捕获 FileNotFoundError/OSError），
            # 这里仅对非 JSON 的读入错误做封装；但为简化逃生路径，
            # 也让 OSError / UnicodeDecodeError 以 MalformedMapError 冒泡。
            raise MalformedMapError(f"Cannot read map file: {exc}") from exc

    def _assert_required_fields(self, data: dict) -> None:
        for field in _REQUIRED_FIELDS:
            if field not in data:
                raise MalformedMapError(f"Missing required field: {field}")

    def _check_dimensions(self, width: int, height: int) -> None:
        if not isinstance(width, int) or not isinstance(height, int):
            raise MalformedMapError(
                f"Inconsistent grid geometry: width/height must be integers"
            )
        if not (_MIN_DIM <= width <= _MAX_DIM) or not (_MIN_DIM <= height <= _MAX_DIM):
            raise MalformedMapError(
                f"Inconsistent grid geometry: Width/Height must be in [{_MIN_DIM}, {_MAX_DIM}]"
            )

    def _check_position(
        self,
        pos,
        width: int,
        height: int,
        name: str,
    ) -> None:
        if (
            not isinstance(pos, list)
            or len(pos) != 2
            or not isinstance(pos[0], int)
            or not isinstance(pos[1], int)
        ):
            raise MalformedMapError(
                f"Inconsistent grid geometry: {name} must be [x, y] of integers"
            )
        x, y = pos[0], pos[1]
        if not (0 <= x < width) or not (0 <= y < height):
            raise MalformedMapError(
                f"{name} ({x}, {y}) out-of-bounds for grid {width}x{height}"
            )

    def _check_grid_geometry(
        self,
        grid,
        height: int,
        width: int,
        name: str,
    ) -> None:
        if not isinstance(grid, list) or len(grid) != height:
            raise MalformedMapError(
                f"Inconsistent grid geometry: {name} must have {height} rows"
            )
        for i, row in enumerate(grid):
            if not isinstance(row, list) or len(row) != width:
                raise MalformedMapError(
                    f"Inconsistent grid geometry: {name} row {i} must have {width} columns"
                )
