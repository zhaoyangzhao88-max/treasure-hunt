"""AI 自动驾驶求解器 — Microsoft Treasure Hunt

基于当前地图状态进行扫雷式边界分析、障碍识别、
路径规划与随机探索，决定玩家下一步动作。

决策链优先级：
  1) 扫雷边界分析（100% 确定雷 → 标雷 / 100% 确定安全 → 开掘）
  2) 相邻障碍开路（铁锹破墙 / 钥匙开门）
  3) 终点大门规划（A* 寻迹到 LOCK_EXIT）
  4) 随机探测兜防（邻近 DIRT 或 A* 导航到最近 DIRT）
  5) 死局（NO_OP）

返回三元组 (action_type, (tx, ty)|None, extra_data|None)::

    action_type  目标坐标       extra_data
    ──────────  ────────────  ──────────
    "FLAG"      (x, y)         None
    "UNCOVER"   (x, y)         None
    "MOVE"      (x, y)         None
    "USE_TOOL"  (x, y)         "pickaxe" | "RED" | "GREEN" | "BLUE" | "EXIT"
    "NO_OP"      None           None
"""

import os as _os
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

from src.pathfinding import a_star_search

# 8 方向偏移（用于扫雷边界分析 / 邻居扫描）
_DIRS_8 = [(-1, -1), (0, -1), (1, -1),
           (-1, 0),           (1, 0),
           (-1, 1),  (0, 1),  (1, 1)]

# 4 方向偏移（用于障碍开路判定）
_DIRS_4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]

# 锁门 → 钥匙颜色映射
_LOCK_TO_KEY = {
    "LOCK_RED":    "RED",
    "LOCK_GREEN":  "GREEN",
    "LOCK_BLUE":   "BLUE",
    "LOCK_EXIT":   "EXIT",
}


class AISolver:
    """扫雷确定性求解 + 自动驾驶决策器。

    Args:
        game_map: ``GameMap`` 实例（5 层网格数据）。
        player_state: ``PlayerState`` 实例（工具 / 钥匙 / 血量）。
        interaction_controller: ``InteractionController`` 实例
            （仅用于读取 player_x / player_y，不直接调用操作方法）。
    """

    def __init__(self, game_map, player_state, interaction_controller):
        self.game_map = game_map
        self.player_state = player_state
        self.interaction_controller = interaction_controller
        # 第 59 课：记住出口坐标，供钥匙开门后导航踩点用
        self._exit_target: tuple[int, int] | None = None

    # =====================================================================
    # 公开入口
    # =====================================================================

    def think_next_action(self, player_x: int, player_y: int):
        """决策主循环 — 按优先级链依次判定。

        Returns:
            (action_type, (tx, ty)|None, extra_data|None)
        """
        gm = self.game_map

        # 0. 自检
        if gm is None:
            return ("NO_OP", None, None)

        # 1. 扫雷边界分析
        action = self._minesweeper_boundary(player_x, player_y)
        if action is not None:
            return action

        # 2. 障碍开路
        action = self._break_obstacles(player_x, player_y)
        if action is not None:
            return action

        # 3. 导航到 KEY_EXIT（尚未获得出口钥匙时）
        action = self._path_to_key_exit(player_x, player_y)
        if action is not None:
            return action

        # 4. 出口门已开：导航步至出口格（第 59 课）
        action = self._step_onto_exit(player_x, player_y)
        if action is not None:
            return action

        # 5. 出口门路径规划（含开锁）
        action = self._path_to_exit(player_x, player_y)
        if action is not None:
            return action

        # 6. 随机探索兜底
        action = self._random_explore(player_x, player_y)
        if action is not None:
            return action

        # 5. 死局
        return ("NO_OP", None, None)

    # =====================================================================
    # 内部辅助 — 邻居生成器
    # =====================================================================

    def _neighbors_8(self, x: int, y: int):
        gm = self.game_map
        for dx, dy in _DIRS_8:
            nx, ny = x + dx, y + dy
            if gm.is_in_bounds(nx, ny):
                yield nx, ny

    def _neighbors_4(self, x: int, y: int):
        gm = self.game_map
        for dx, dy in _DIRS_4:
            nx, ny = x + dx, y + dy
            if gm.is_in_bounds(nx, ny):
                yield nx, ny

    # =====================================================================
    # 规则 1：扫雷边界分析
    # =====================================================================

    def _minesweeper_boundary(self, px: int, py: int):
        gm = self.game_map
        for y in range(gm.height):
            for x in range(gm.width):
                # 仅处理已揭开且周围有雷的数字格
                if gm.layer0[y][x] != "UNCOVERED":
                    continue
                tile_num = gm.get_adjacent_traps_count(x, y)
                if tile_num <= 0:
                    continue

                # 分类 8 邻域中的未揭开泥土和已插旗格
                dirt_coords = []
                flag_coords = []
                for nx, ny in self._neighbors_8(x, y):
                    if gm.layer0[ny][nx] == "DIRT" and not gm.flags[ny][nx]:
                        dirt_coords.append((nx, ny))
                    elif gm.flags[ny][nx]:
                        flag_coords.append((nx, ny))

                # 规则 A：所有剩余 dirt 必然都是雷 → 标雷
                if (len(dirt_coords) + len(flag_coords) == tile_num
                        and len(dirt_coords) > 0):
                    return ("FLAG", dirt_coords[0], None)

                # 规则 B：所有雷都已被标记，剩余 dirt 必安全 → 开掘
                if (len(flag_coords) == tile_num
                        and len(dirt_coords) > 0):
                    # 选最近的安全格（曼哈顿距离）
                    dirt_coords.sort(
                        key=lambda c: abs(c[0] - px) + abs(c[1] - py))
                    target = dirt_coords[0]
                    # 与玩家相邻 → 直接揭开
                    if (abs(target[0] - px) <= 1
                            and abs(target[1] - py) <= 1):
                        return ("UNCOVER", target, None)
                    # 不相邻 → A* 导航过去
                    path = a_star_search(gm, (px, py), target)
                    if path:
                        return ("MOVE", path[0], None)
        return None

    # =====================================================================
    # 规则 2：相邻障碍开路
    # =====================================================================

    def _break_obstacles(self, px: int, py: int):
        gm = self.game_map
        ps = self.player_state
        for nx, ny in self._neighbors_4(px, py):
            obs = gm.layer1[ny][nx]
            if obs == "DIRT_WALL":
                if ps.tools.get("pickaxe", 0) > 0:
                    return ("USE_TOOL", (nx, ny), "pickaxe")
            elif obs in _LOCK_TO_KEY:
                key_color = _LOCK_TO_KEY[obs]
                if ps.keys.get(key_color, 0) > 0:
                    return ("USE_TOOL", (nx, ny), key_color)
        return None

    # =====================================================================
    # 规则 3：导航至 KEY_EXIT 实体（第 59 课）
    # =====================================================================

    def _path_to_key_exit(self, px: int, py: int):
        """在未持有出口钥匙时，扫描已可见的 KEY_EXIT 实体并导航靠近。"""
        if self.player_state.keys.get("EXIT", 0) > 0:
            return None  # 已有钥匙，无需再找
        gm = self.game_map

        # 扫描已揭开区域中的 KEY_EXIT
        candidates = [
            (x, y)
            for y in range(gm.height)
            for x in range(gm.width)
            if gm.layer0[y][x] == "UNCOVERED"
            and gm.layer2[y][x] == "KEY_EXIT"
        ]
        if not candidates:
            return None

        # 选最近的一个
        candidates.sort(key=lambda c: abs(c[0] - px) + abs(c[1] - py))
        target = candidates[0]

        # 若相邻 → 直接走过去收集
        if abs(target[0] - px) <= 1 and abs(target[1] - py) <= 1:
            if gm.is_walkable(target[0], target[1]):
                return ("MOVE", target, None)
            return None

        # A* 导航
        path = a_star_search(gm, (px, py), target)
        if path:
            return ("MOVE", path[0], None)
        return None

    # =====================================================================
    # 规则 4：出口门已开 → 步至出口格（第 59 课）
    # =====================================================================

    def _step_onto_exit(self, px: int, py: int):
        """钥匙已使用（LOCK_EXIT 已清），直接导航到出口格。"""
        if self._exit_target is None:
            return None
        tx, ty = self._exit_target
        gm = self.game_map

        # 若出口仍被 LOCK_EXIT 占据（门还没开），让 _path_to_exit 处理
        if gm.layer1[ty][tx] == "LOCK_EXIT":
            return None

        # 已站在出口上 → 清除目标（由 check_victory_condition 接管跳转）
        if (px, py) == (tx, ty):
            self._exit_target = None
            return None

        # 出口可通行 → A* 导航
        if gm.is_walkable(tx, ty):
            path = a_star_search(gm, (px, py), (tx, ty))
            if path:
                return ("MOVE", path[0], None)

        # 出口暂不可通行（可能被 DIRT 覆盖）→ 由 _random_explore 处理
        return None

    # =====================================================================
    # 规则 4：出口门路径规划
    # =====================================================================

    def _path_to_exit(self, px: int, py: int):
        gm = self.game_map
        ps = self.player_state
        if ps.keys.get("EXIT", 0) <= 0:
            return None

        # 扫描所有 LOCK_EXIT 格
        exit_cells = [
            (x, y)
            for y in range(gm.height)
            for x in range(gm.width)
            if gm.layer1[y][x] == "LOCK_EXIT"
        ]
        if not exit_cells:
            return None

        # 选最近出口门
        exit_cells.sort(key=lambda c: abs(c[0] - px) + abs(c[1] - py))
        target = exit_cells[0]

        # 若相邻 → 记住出口坐标，然后用钥匙开门
        if abs(target[0] - px) <= 1 and abs(target[1] - py) <= 1:
            self._exit_target = target
            return ("USE_TOOL", target, "EXIT")

        # 不相邻 → A* 导航到 LOCK_EXIT 的最近可通行邻居（LOCK_EXIT 本身不可通行）
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = target[0] + dx, target[1] + dy
            if gm.is_walkable(nx, ny):
                path = a_star_search(gm, (px, py), (nx, ny))
                if path:
                    return ("MOVE", path[0], None)
        return None

    # =====================================================================
    # 规则 7：随机探索兜底
    # =====================================================================

    def _random_explore(self, px: int, py: int):
        gm = self.game_map

        # 优先：相邻 DIRT 直接揭开
        for nx, ny in self._neighbors_8(px, py):
            if gm.layer0[ny][nx] == "DIRT" and not gm.flags[ny][nx]:
                return ("UNCOVER", (nx, ny), None)

        # 其次：导航到最近 DIRT 的相邻可通行格（DIRT 本身不可通行）
        dirt_cells = [
            (x, y)
            for y in range(gm.height)
            for x in range(gm.width)
            if gm.layer0[y][x] == "DIRT" and not gm.flags[y][x]
        ]
        if not dirt_cells:
            return None

        # 按曼哈顿距离排序，仅对最近 5 个做 A*（防大地图卡顿）
        dirt_cells.sort(key=lambda c: abs(c[0] - px) + abs(c[1] - py))
        for dirt in dirt_cells[:5]:
            # 找到该 DIRT 周围可通行的邻居格作为 A* 目标
            for nx, ny in self._neighbors_8(dirt[0], dirt[1]):
                if gm.is_walkable(nx, ny):
                    path = a_star_search(gm, (px, py), (nx, ny))
                    if path:
                        return ("MOVE", path[0], None)
        return None
