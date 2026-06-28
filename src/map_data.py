"""地图核心数据模型与多层网格数据结构 — Microsoft Treasure Hunt

5 层网格系统：地形 / 障碍物 / 实体道具 / 陷阱 / 红旗。
提供扫雷式邻域计数、通行判定、揭开与标记等核心 API。
"""


class GameMap:
    """多层地图网格容器。

    坐标约定：x 为列（0 … width-1），y 为行（0 … height-1）。
    所有矩阵以 [y][x] 索引。
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

        # layer0 地形层："DIRT"（泥土覆盖）/ "UNCOVERED"（已揭开）
        self.layer0 = [["DIRT" for _ in range(width)] for _ in range(height)]

        # layer1 障碍物层："NONE" / "WALL" / "RED_DOOR" / "GREEN_DOOR" / "BLUE_DOOR" 等
        self.layer1 = [["NONE" for _ in range(width)] for _ in range(height)]

        # layer2 实体道具层："NONE" / "GOLD" / "HEART" / "BOMB_SPAWN" 等
        self.layer2 = [["NONE" for _ in range(width)] for _ in range(height)]

        # traps 隐藏陷阱层（扫雷式）
        self.traps = [[False for _ in range(width)] for _ in range(height)]

        # flags 红旗标记层
        self.flags = [[False for _ in range(width)] for _ in range(height)]

    # =========================================================================
    # 边界与查询
    # =========================================================================

    def is_in_bounds(self, x: int, y: int) -> bool:
        """验证坐标 (x, y) 是否在网格界限内"""
        return 0 <= x < self.width and 0 <= y < self.height

    def get_adjacent_traps_count(self, x: int, y: int) -> int:
        """计算 (x, y) 周围 8 个方向相邻网格中的陷阱数量。

        自身不计入；越界邻居自动跳过。
        """
        count = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self.is_in_bounds(nx, ny) and self.traps[ny][nx]:
                    count += 1
        return count

    def is_walkable(self, x: int, y: int) -> bool:
        """判定该格子角色是否可以直接走上去。

        条件：
        - 坐标在边界内
        - layer0 已揭开（"UNCOVERED"）
        - layer1 无障碍物（"NONE"）
        """
        if not self.is_in_bounds(x, y):
            return False
        if self.layer0[y][x] != "UNCOVERED":
            return False
        if self.layer1[y][x] != "NONE":
            return False
        return True

    # =========================================================================
    # 玩家交互
    # =========================================================================

    def toggle_flag(self, x: int, y: int) -> bool:
        """对指定格子插红旗/取消红旗。

        仅当 layer0[y][x] == "DIRT" 时生效。
        已挖开的格子操作不生效并返回 False。

        Returns:
            操作后的 flag 状态；返回 False 表示未操作或无变化。
        """
        if not self.is_in_bounds(x, y):
            return False
        if self.layer0[y][x] != "DIRT":
            return False
        self.flags[y][x] = not self.flags[y][x]
        return self.flags[y][x]

    def uncover_tile(self, x: int, y: int) -> bool:
        """揭开指定泥土瓦片。

        条件：在边界内 + 当前为 "DIRT" + 未标记红旗。

        Returns:
            True 成功揭开；False 已揭开 / 已标记 / 越界。
        """
        if not self.is_in_bounds(x, y):
            return False
        if self.layer0[y][x] != "DIRT":
            return False
        if self.flags[y][x]:
            return False
        self.layer0[y][x] = "UNCOVERED"
        return True

    # =========================================================================
    # 辅助赋值（含越界检查）
    # =========================================================================

    def set_obstacle(self, x: int, y: int, obstacle_type: str) -> None:
        """设置障碍物层（layer1）。越界静默忽略。"""
        if self.is_in_bounds(x, y):
            self.layer1[y][x] = obstacle_type

    def set_entity(self, x: int, y: int, entity_type: str) -> None:
        """设置实体道具层（layer2）。越界静默忽略。"""
        if self.is_in_bounds(x, y):
            self.layer2[y][x] = entity_type
