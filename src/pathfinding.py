"""A* 路径搜索引擎 — Microsoft Treasure Hunt

基于曼哈顿距离启发式的四方向 A* 寻路实现，
专为本项目的多层网格 `GameMap` 设计。

可通行条件严格依赖 ``GameMap.is_walkable(x, y)``：
- 坐标必须在地图边界内
- layer0 地形必须为 ``"UNCOVERED"``（已开掘）
- layer1 障碍物层必须为 ``"NONE"``（无墙体/封门）

使用标准库 ``heapq`` 作为 open 列表的优先队列，保证
``O(E log V)`` 级别的时间复杂度。

用法::

    from src.pathfinding import a_star_search

    path = a_star_search(game_map, (sx, sy), (ex, ey))
    # path = [(nx, ny), ...]  —  不含起点、含终点；不可达返回 []
"""

from __future__ import annotations

import heapq
import sys

# 4 方向（上下左右）— 每次移动代价 g = 1
_DIRECTIONS: list[tuple[int, int]] = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def a_star_search(game_map, start: tuple[int, int],
                  end: tuple[int, int]) -> list[tuple[int, int]]:
    """在 ``game_map`` 上搜索一条最短路径。

    采用经典的 A* 算法：
    - ``f = g + h``，其中 ``g`` 为实际步数，``h`` 为曼哈顿启发距离。
    - open 列表以 ``(f, g, (x, y))`` 元组入堆，兼顾稳定排序。
    - 仅当邻居处于界内且 ``game_map.is_walkable(tx, ty)`` 为 True 时才会扩展。

    Args:
        game_map: ``GameMap`` 实例，提供 ``is_in_bounds`` / ``is_walkable``。
        start:    起点网格坐标 (x, y)。
        end:      终点网格坐标 (x, y)。

    Returns:
        路径坐标列表，**不含起点、含终点**；若不可达返回 ``[]``。
    """
    sx, sy = start
    ex, ey = end

    # 起点/终点校验
    if not game_map.is_in_bounds(sx, sy) or not game_map.is_in_bounds(ex, ey):
        return []

    # 起点即终点：无需寻路
    if start == end:
        return []

    def heuristic(x: int, y: int) -> int:
        """曼哈顿距离启发式"""
        return abs(x - ex) + abs(y - ey)

    # 起点必须可通行——否则根本无法起步
    if not game_map.is_walkable(sx, sy):
        return []

    # open 列表：堆化的 (f_score, g_cost, (x, y))
    open_heap: list[tuple[int, int, tuple[int, int]]] = []
    start_g = 0
    start_f = start_g + heuristic(sx, sy)
    heapq.heappush(open_heap, (start_f, start_g, (sx, sy)))

    # close 集合：已确定最短距离的节点
    closed: set[tuple[int, int]] = set()

    # 路径追溯：记录每个节点的最佳前驱
    parent: dict[tuple[int, int], tuple[int, int]] = {}

    # 起点已入堆，不需要在 close 中再记录
    # A* 主循环
    while open_heap:
        f, g, current = heapq.heappop(open_heap)
        cx, cy = current

        # 跳过已在 close 中的节点（同一坐标可能多次入堆）
        if current in closed:
            continue

        # 扩展至 close 列表
        closed.add(current)

        # 到达终点 — 回溯路径
        if current == end:
            # 还原路径（不含起点）
            path = []
            node = current
            while node != start:
                path.append(node)
                node = parent[node]
            path.reverse()
            return path

        # 扩展 4 方向邻居
        for dx, dy in _DIRECTIONS:
            nx, ny = cx + dx, cy + dy
            neighbor = (nx, ny)

            # 已在 close 中或不可通行 → 跳过
            if neighbor in closed:
                continue
            if not game_map.is_in_bounds(nx, ny):
                continue
            if not game_map.is_walkable(nx, ny):
                continue

            new_g = g + 1

            # 记录前驱（首次发现该节点即是最短——A* 保证，因为曼哈顿启发一致）
            if neighbor not in parent:
                parent[neighbor] = (cx, cy)

            new_f = new_g + heuristic(nx, ny)
            heapq.heappush(open_heap, (new_f, new_g, neighbor))

    # 开放列表空但未达终点 → 不可达
    return []


def _run_standalone_test():
    """简易独立测试 — 直接运行此文件时执行。"""
    import os as _os
    _os.environ["SDL_VIDEODRIVER"] = "dummy"
    # 将 src/ 加入搜索路径，使 `import map_data` 可用
    _src_dir = _os.path.dirname(_os.path.abspath(__file__))
    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)
    from map_data import GameMap

    # 测试 1：直线路径
    gm = GameMap(10, 10)
    for y in range(10):
        for x in range(10):
            gm.layer0[y][x] = "UNCOVERED"
            gm.layer1[y][x] = "NONE"

    path = a_star_search(gm, (0, 0), (5, 0))
    assert len(path) == 5, f"Expected path length 5, got {len(path)}"
    assert path[0] == (1, 0), f"First step should be (1,0), got {path[0]}"
    assert path[-1] == (5, 0), f"Last step should be (5,0), got {path[-1]}"

    # 测试 2：起点 == 终点返回空
    assert a_star_search(gm, (3, 3), (3, 3)) == []

    # 测试 3：越界起点返回空
    assert a_star_search(gm, (-1, 0), (5, 0)) == []

    # 测试 4：不可达（四面被墙）
    gm.layer1[4][5] = "WALL"
    gm.layer1[5][4] = "WALL"
    gm.layer1[5][6] = "WALL"
    gm.layer1[6][5] = "WALL"
    gm.layer0[5][5] = "UNCOVERED"
    assert a_star_search(gm, (0, 0), (5, 5)) == []

    print(f"[PASS] A* path = {path}")
    print("[PASS] Edge cases handled correctly")
    print("=== A* STANDALONE TESTS PASSED ===")


if __name__ == "__main__":
    _run_standalone_test()
