"""程序化关卡生成引擎与可解性验证 — Microsoft Treasure Hunt

三阶段生成管道：
  1. 物理迷宫雕刻（Randomized Prim）
  2. 锁钥依赖拓扑（安全割点放置法）
  3. 扫雷雷区填充 + 道具散布

提供 generate_level() 与 verify_solvability() 两个核心 API。
"""

import os as _os
import sys as _sys
from collections import deque
import random

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

from map_data import GameMap
from loot_table import LootTable


class LevelGenerator:
    """程序化关卡生成器。

    使用种子化 RNG 确保可复现性。
    所有随机操作通过 self._rng 执行，避免全局 random 状态污染。
    """

    def __init__(self, seed: int | None = None):
        self._seed = seed
        self._rng = random.Random(seed)

    # =========================================================================
    # 难度数值计算
    # =========================================================================

    @staticmethod
    def _get_grid_size(level_num: int) -> int:
        """地图尺寸随关卡线性增长，范围 [15, 40]。"""
        return max(15, min(40, 15 + (level_num - 1) * 2))

    @staticmethod
    def _get_trap_density(level_num: int) -> float:
        """陷阱密度随关卡线性增长，上限 0.22。"""
        return min(0.22, 0.10 + (level_num - 1) * 0.01)

    # =========================================================================
    # 阶段 1：物理迷宫雕刻
    # =========================================================================

    def _carve_maze(self, game_map: GameMap, start_x: int = 1, start_y: int = 1) -> None:
        """随机 Prim 算法雕刻连通通道。

        约定：奇数坐标为通道，偶坐标为墙体。
        边界保留 1 格墙体外框。
        """
        w, h = game_map.width, game_map.height

        # 全图初始化为 WALL
        for y in range(h):
            for x in range(w):
                game_map.layer1[y][x] = "WALL"

        visited = [[False] * w for _ in range(h)]
        frontier = []

        # 起点打通
        game_map.layer1[start_y][start_x] = "NONE"
        visited[start_y][start_x] = True

        # 初始化 frontier（距离 2 的四方向邻居）
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            nx, ny = start_x + dx, start_y + dy
            if 0 < nx < w - 1 and 0 < ny < h - 1:
                frontier.append((nx, ny, start_x, start_y))

        while frontier:
            idx = self._rng.randint(0, len(frontier) - 1)
            fx, fy, px, py = frontier.pop(idx)

            if visited[fy][fx]:
                continue

            # 打通父节点与 frontier 之间的墙
            game_map.layer1[fy][fx] = "NONE"
            game_map.layer1[(fy + py) // 2][(fx + px) // 2] = "NONE"
            visited[fy][fx] = True

            # 添加新 frontier
            for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                nx, ny = fx + dx, fy + dy
                if 0 < nx < w - 1 and 0 < ny < h - 1 and not visited[ny][nx]:
                    frontier.append((nx, ny, fx, fy))

    def _add_loops(self, game_map: GameMap, loop_factor: float) -> None:
        """随机移除部分内墙添加环路，防止迷宫过于线性。

        仅移除连接两个通道的墙体（非外墙）。
        """
        w, h = game_map.width, game_map.height
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if game_map.layer1[y][x] != "WALL":
                    continue
                if self._rng.random() >= loop_factor:
                    continue
                # 检查是否连接两个通道
                passage_neighbors = sum(
                    1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if game_map.layer1[y + dy][x + dx] == "NONE"
                )
                if passage_neighbors >= 2:
                    game_map.layer1[y][x] = "NONE"

    # =========================================================================
    # 阶段 2：锁钥依赖拓扑
    # =========================================================================

    def _bfs_path(self, game_map: GameMap, start: tuple, end: tuple) -> list:
        """BFS 寻找从 start 到 end 的路径（仅在 layer1=="NONE" 的格子上移动）。

        Returns:
            路径坐标列表（含起点和终点），无路径时返回空列表。
        """
        queue = deque([(start, [start])])
        visited = {start}
        while queue:
            (cx, cy), path = queue.popleft()
            if (cx, cy) == end:
                return path
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if (game_map.is_in_bounds(nx, ny)
                        and (nx, ny) not in visited
                        and game_map.layer1[ny][nx] == "NONE"):
                    visited.add((nx, ny))
                    queue.append(((nx, ny), path + [(nx, ny)]))
        return []

    def _bfs_reachable(self, game_map: GameMap, start: tuple,
                       blocked: tuple = None) -> set:
        """BFS 返回从 start 可达的所有位置集合。

        Args:
            blocked: 可选，视为不可通过的位置。
        """
        queue = deque([start])
        visited = {start}
        while queue:
            cx, cy = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if not game_map.is_in_bounds(nx, ny):
                    continue
                if (nx, ny) in visited:
                    continue
                if blocked and (nx, ny) == blocked:
                    continue
                if game_map.layer1[ny][nx] != "NONE":
                    continue
                visited.add((nx, ny))
                queue.append((nx, ny))
        return visited

    def _find_chokepoints(self, game_map: GameMap, path: list) -> list:
        """检测路径上的割点：移除该点后起点无法到达终点。

        仅测试主路径上的中间节点（排除起点和终点）。
        """
        chokepoints = []
        for i, (px, py) in enumerate(path[1:-1], 1):
            # 临时封锁
            original = game_map.layer1[py][px]
            game_map.layer1[py][px] = "WALL"
            reachable = self._bfs_reachable(game_map, path[0])
            game_map.layer1[py][px] = original  # 恢复
            if path[-1] not in reachable:
                chokepoints.append((px, py))
        return chokepoints

    def _place_lock_and_key(self, game_map: GameMap, level_num: int,
                            start: tuple, exit_: tuple) -> None:
        """放置锁钥依赖链。

        始终放置 KEY_EXIT（解锁出口门）。
        level_num >= 2 时额外放置 LOCK_RED + KEY_RED 增加难度。
        """
        # 计算主路径（忽略出口门，因为出口格被 LOCK_EXIT 占据）
        # 使用出口可达的最近邻居作为路径终点
        exit_neighbors = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = exit_[0] + dx, exit_[1] + dy
            if game_map.is_in_bounds(nx, ny) and game_map.layer1[ny][nx] == "NONE":
                exit_neighbors.append((nx, ny))

        if not exit_neighbors:
            return  # 极端情况：出口被完全封闭

        # 选择可达的出口邻居作为路径终点
        # 优先选择能从起点到达的邻居（排除死端）
        path = []
        path_end = exit_neighbors[0]
        for neighbor in exit_neighbors:
            test_path = self._bfs_path(game_map, start, neighbor)
            if test_path:
                path = test_path
                path_end = neighbor
                break
        if not path:
            return  # 所有出口邻居都不可达（不应发生）

        # ---- 始终放置 KEY_EXIT ----
        # KEY_EXIT 放在路径前半段（玩家获取后能打开出口）
        # 如果存在 LOCK_RED，KEY_EXIT 必须在 LOCK_RED 之后（先拿红钥匙过红门）
        key_exit_idx = len(path) // 3  # 路径前 1/3 处
        key_exit_pos = path[key_exit_idx]
        cur = game_map.layer2[key_exit_pos[1]][key_exit_pos[0]]
        if cur == "NONE":
            game_map.set_entity(key_exit_pos[0], key_exit_pos[1], "KEY_EXIT")

        # ---- level >= 2：放置 LOCK_RED + KEY_RED ----
        if level_num < 2:
            return

        # 检测割点
        chokepoints = self._find_chokepoints(game_map, path)
        if not chokepoints:
            mid = len(path) // 2
            chokepoints = [path[mid]]

        # 优先选择位于路径 40-60% 位置的割点
        best_gate = chokepoints[0]
        target_idx = int(len(path) * 0.5)
        for cp in chokepoints:
            cp_idx = path.index(cp)
            if abs(cp_idx - target_idx) < abs(path.index(best_gate) - target_idx):
                best_gate = cp

        gate_pos = best_gate
        game_map.set_obstacle(gate_pos[0], gate_pos[1], "LOCK_RED")

        # BFS 从起点出发（把 LOCK_RED 当作墙），得到门之前可达区域
        reachable_before_gate = self._bfs_reachable(game_map, start, blocked=gate_pos)

        # 在可达区域内寻找非主通道的 DIRT 格放置钥匙
        path_set = set(path)
        candidates = [
            (rx, ry) for (rx, ry) in reachable_before_gate
            if (rx, ry) not in path_set and game_map.layer0[ry][rx] == "DIRT"
        ]

        if not candidates:
            # 回退：使用可达区域内任意 DIRT 格
            candidates = [
                (rx, ry) for (rx, ry) in reachable_before_gate
                if game_map.layer0[ry][rx] == "DIRT"
            ]

        if candidates:
            key_pos = self._rng.choice(candidates)
            game_map.set_entity(key_pos[0], key_pos[1], "KEY_RED")

        # 重新计算路径（LOCK_RED 已放置），更新 KEY_EXIT 位置确保可达
        # KEY_EXIT 必须在 LOCK_RED 之前可达
        reachable_before_red = self._bfs_reachable(game_map, start, blocked=gate_pos)
        if key_exit_pos not in reachable_before_red:
            # 重新放置 KEY_EXIT 到可达区域
            new_candidates = [
                pos for pos in reachable_before_red
                if (game_map.layer2[pos[1]][pos[0]] == "NONE"
                    and pos != gate_pos)
            ]
            if new_candidates:
                # 选择离起点最近的候选（确保早期可达）
                new_key_exit = new_candidates[0]
                game_map.set_entity(key_exit_pos[0], key_exit_pos[1], "NONE")  # 清除旧位置
                game_map.set_entity(new_key_exit[0], new_key_exit[1], "KEY_EXIT")

    # =========================================================================
    # 阶段 3：雷区填充与道具散布
    # =========================================================================

    def _place_traps(self, game_map: GameMap, trap_density: float,
                     start: tuple) -> None:
        """在非通道 DIRT 格子上以 trap_density 概率布雷。

        起点 3x3 安全区强制无雷。
        """
        sx, sy = start
        safe_zone = {
            (sx + dx, sy + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if game_map.is_in_bounds(sx + dx, sy + dy)
        }

        placeable = []
        for y in range(game_map.height):
            for x in range(game_map.width):
                if (x, y) in safe_zone:
                    continue
                if game_map.layer0[y][x] != "DIRT":
                    continue
                if game_map.layer1[y][x] != "NONE":
                    continue
                if game_map.layer2[y][x] != "NONE":
                    continue
                placeable.append((x, y))

        num_traps = int(len(placeable) * trap_density)
        if num_traps > len(placeable):
            num_traps = len(placeable)

        for tx, ty in self._rng.sample(placeable, num_traps):
            game_map.traps[ty][tx] = True

    def _is_dead_end(self, game_map: GameMap, x: int, y: int) -> bool:
        """判定 (x, y) 是否为迷宫死胡同。

        死胡同定义：正交 4 方向中 ≥3 个不可通行（越界/WALL/非 NONE）。
        """
        if game_map.layer1[y][x] != "NONE":
            return False
        wall_count = 0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (not game_map.is_in_bounds(nx, ny)
                    or game_map.layer1[ny][nx] != "NONE"):
                wall_count += 1
        return wall_count >= 3

    def _place_chests(self, game_map: GameMap, level_num: int,
                      start: tuple, exit_: tuple) -> None:
        """在死胡同位置散布宝箱。

        规则：
        - 普通宝箱（CHEST）：1~2 个
        - 上锁宝箱（LOCKED_CHEST）：level >= 2 时 0~1 个
        """
        dead_end_candidates = []
        for y in range(game_map.height):
            for x in range(game_map.width):
                if game_map.layer1[y][x] != "NONE":
                    continue
                if game_map.layer2[y][x] != "NONE":
                    continue
                if game_map.traps[y][x]:
                    continue
                if (x, y) == start or (x, y) == exit_:
                    continue
                if self._is_dead_end(game_map, x, y):
                    dead_end_candidates.append((x, y))

        if not dead_end_candidates:
            return

        # 随机打乱候选
        self._rng.shuffle(dead_end_candidates)

        # 普通宝箱：1~2 个
        num_chests = self._rng.randint(1, min(2, len(dead_end_candidates)))
        for i in range(num_chests):
            pos = dead_end_candidates[i]
            game_map.set_entity(pos[0], pos[1], "CHEST")

        # 上锁宝箱：level >= 2 时 0~1 个
        if level_num >= 2 and len(dead_end_candidates) > num_chests:
            if self._rng.random() < 0.5:  # 50% 概率出现
                pos = dead_end_candidates[num_chests]
                game_map.set_entity(pos[0], pos[1], "LOCKED_CHEST")

    def _scatter_entities(self, game_map: GameMap, level_num: int,
                          start: tuple, exit_: tuple) -> None:
        """在通道格子上散落道具（玩家可走过的空地）。

        候选格子：layer1=="NONE"（通道）、layer2=="NONE"（无实体）、无雷。
        排除起点和出口格。

        散布逻辑：
        - 先调用 _place_chests 在死胡同放置宝箱
        - 硬编码保证 MACHETE（1 个）与 ARROW（~5%）
        - 其余通用道具槽位使用 LootTable 动态决定
        """
        candidates = []
        for y in range(game_map.height):
            for x in range(game_map.width):
                if game_map.layer1[y][x] != "NONE":
                    continue
                if game_map.layer2[y][x] != "NONE":
                    continue
                if game_map.traps[y][x]:
                    continue
                if (x, y) == start or (x, y) == exit_:
                    continue
                candidates.append((x, y))

        # ── 宝箱散布（优先占用死胡同） ──────────────────────────────
        self._place_chests(game_map, level_num, start, exit_)

        # 宝箱放置后，从 candidates 中移除已被占用的格子
        candidates = [
            pos for pos in candidates
            if game_map.layer2[pos[1]][pos[0]] == "NONE"
        ]

        if not candidates:
            return

        # ── 硬编码保障项 ──────────────────────────────────────────
        # MACHETE：每关必出 1 把（但不超过候选数）
        guaranteed_items = [
            ("MACHETE", 1),
        ]
        for entity_type, count in guaranteed_items:
            actual = min(count, len(candidates))
            if actual <= 0:
                continue
            for _ in range(actual):
                idx = self._rng.randint(0, len(candidates) - 1)
                pos = candidates.pop(idx)
                game_map.set_entity(pos[0], pos[1], entity_type)

        # ARROW：约 5% 的通路格
        arrow_count = max(1, int(len(candidates) * 0.05)) if candidates else 0
        actual_arrows = min(arrow_count, len(candidates))
        for _ in range(actual_arrows):
            idx = self._rng.randint(0, len(candidates) - 1)
            pos = candidates.pop(idx)
            game_map.set_entity(pos[0], pos[1], "ARROW")

        if not candidates:
            return

        # ── LootTable 动态通用道具 ──────────────────────────────────
        # 使用 LootTable.get_random_loot 决定每个槽位的实体
        loot_table = LootTable(seed=level_num)
        generic_count = min(3 + level_num, len(candidates))
        for _ in range(generic_count):
            idx = self._rng.randint(0, len(candidates) - 1)
            pos = candidates.pop(idx)
            entity = loot_table.get_random_loot(level_num)
            game_map.set_entity(pos[0], pos[1], entity)

    def _place_monsters(self, game_map: GameMap, start: tuple,
                        exit_: tuple) -> None:
        """在通道格子上随机散落 2~4 个怪物。

        怪物放在通路格子上（玩家可走过的空地），
        确保起点 3×3 安全区内绝无怪物。
        排除出口格及已有实体的格子。
        """
        sx, sy = start
        safe_zone = {
            (sx + dx, sy + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if game_map.is_in_bounds(sx + dx, sy + dy)
        }

        candidates = []
        for y in range(game_map.height):
            for x in range(game_map.width):
                if (x, y) in safe_zone:
                    continue
                if (x, y) == exit_:
                    continue
                if game_map.layer1[y][x] != "NONE":
                    continue
                if game_map.layer2[y][x] != "NONE":
                    continue
                if game_map.traps[y][x]:
                    continue
                candidates.append((x, y))

        monster_count = self._rng.randint(2, 4)
        actual = min(monster_count, len(candidates))
        if actual <= 0:
            return

        for _ in range(actual):
            idx = self._rng.randint(0, len(candidates) - 1)
            pos = candidates.pop(idx)
            game_map.set_entity(pos[0], pos[1], "MONSTER")

    # =========================================================================
    # 核心 API：generate_level
    # =========================================================================

    def generate_level(self, level_num: int) -> tuple:
        """生成完整关卡。

        Args:
            level_num: 关卡编号（从 1 开始）。

        Returns:
            (game_map, (start_x, start_y), (exit_x, exit_y))
        """
        grid_size = self._get_grid_size(level_num)
        trap_density = self._get_trap_density(level_num)

        game_map = GameMap(grid_size, grid_size)

        # 阶段 1：雕刻迷宫
        self._carve_maze(game_map, start_x=1, start_y=1)

        # 添加环路（随关卡增长）
        loop_factor = min(0.20, 0.05 + (level_num - 1) * 0.005)
        self._add_loops(game_map, loop_factor)

        # 设置起点和终点
        start = (1, 1)
        exit_ = (grid_size - 2, grid_size - 2)

        game_map.layer0[start[1]][start[0]] = "UNCOVERED"
        game_map.set_obstacle(exit_[0], exit_[1], "LOCK_EXIT")

        # 确保出口至少有一个可达的通道邻居
        # 出口位于 (偶, 偶) 坐标时，邻居是 (奇, 偶) 或 (偶, 奇) 的"墙格"
        # 需要打通其中一个邻居确保连通
        has_passable_neighbor = False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = exit_[0] + dx, exit_[1] + dy
            if game_map.is_in_bounds(nx, ny) and game_map.layer1[ny][nx] == "NONE":
                has_passable_neighbor = True
                break
        if not has_passable_neighbor:
            # 打通左侧或上方邻居（优先选择靠近中心的方向）
            for dx, dy in ((-1, 0), (0, -1), (1, 0), (0, 1)):
                nx, ny = exit_[0] + dx, exit_[1] + dy
                if game_map.is_in_bounds(nx, ny):
                    game_map.layer1[ny][nx] = "NONE"
                    break

        # 阶段 2：锁钥依赖
        self._place_lock_and_key(game_map, level_num, start, exit_)

        # 阶段 3：雷区 + 道具 + 怪物
        self._place_traps(game_map, trap_density, start)
        self._scatter_entities(game_map, level_num, start, exit_)
        self._place_monsters(game_map, start, exit_)

        return game_map, start, exit_

    # =========================================================================
    # 核心 API：verify_solvability
    # =========================================================================

    def verify_solvability(self, game_map: GameMap, start: tuple,
                           exit_: tuple) -> bool:
        """BFS 模拟求解器验证关卡可解性。

        状态：(x, y, frozenset(held_keys), pickaxe_count)
        模拟玩家从起点出发，收集钥匙/工具，开启锁门，
        判断是否能到达终点并打开 LOCK_EXIT。

        设有访问上限防止状态空间爆炸。
        """
        # 钥匙颜色数量上限（RED, GREEN, BLUE, EXIT）
        max_key_types = 4
        max_pickaxes = 5
        # 访问状态上限
        max_visited = 500_000

        initial_state = (start[0], start[1], frozenset(), 0)
        queue = deque([initial_state])
        visited = {initial_state}

        while queue:
            x, y, keys, pickaxes = queue.popleft()

            # 检查是否到达终点（已经踏上门，无需二次检查钥匙）
            if (x, y) == exit_:
                return True

            # 探索四方向邻居
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not game_map.is_in_bounds(nx, ny):
                    continue

                obstacle = game_map.layer1[ny][nx]
                entity = game_map.layer2[ny][nx]
                new_keys = set(keys)
                new_pickaxes = pickaxes

                # 障碍判定
                if obstacle == "WALL":
                    continue
                elif obstacle == "DIRT_WALL":
                    if pickaxes <= 0:
                        continue
                    new_pickaxes -= 1
                elif obstacle.startswith("LOCK_"):
                    color = obstacle.replace("LOCK_", "")
                    if color not in keys:
                        continue
                    new_keys.discard(color)  # 消耗钥匙

                # 收集实体道具
                if entity.startswith("KEY_"):
                    color = entity.replace("KEY_", "")
                    new_keys.add(color)
                elif entity == "PICKAXE":
                    new_pickaxes += 1

                # 限制状态空间
                if len(new_keys) > max_key_types:
                    continue
                if new_pickaxes > max_pickaxes:
                    new_pickaxes = max_pickaxes

                state_key = (nx, ny, frozenset(new_keys), new_pickaxes)
                if state_key not in visited:
                    visited.add(state_key)
                    if len(visited) < max_visited:
                        queue.append(state_key)

        return False
