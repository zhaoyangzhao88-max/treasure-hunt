"""核心交互逻辑与扫雷连锁开掘控制器 — Microsoft Treasure Hunt

将 GameMap（地图数据）与 PlayerState（玩家状态）连接起来，
处理玩家点击开掘、Flood Fill 连锁、双击 Chording、障碍交互、
玩家移动与道具收集等核心业务逻辑。
"""

import os as _os
import sys as _sys
from collections import deque

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

from map_data import GameMap
from player_state import PlayerState
from loot_table import LootTable


# 可收集道具集合
_COLLECTIBLE_ENTITIES = {
    "COIN", "GEM", "PICKAXE", "DYNAMITE", "MAP",
    "HEART", "SHIELD", "AMULET", "STAIRS",
    "ARROW", "MACHETE", "CHEST",
}

# 锁门颜色前缀提取
_LOCK_COLORS = {"RED", "GREEN", "BLUE", "EXIT"}


class InteractionController:
    """交互控制器：处理玩家对地图的所有操作。

    持有玩家当前在地图中的网格坐标 (player_x, player_y)，
    并将操作委托给 GameMap 与 PlayerState。
    """

    def __init__(self, game_map: GameMap, player: PlayerState,
                 start_x: int = 0, start_y: int = 0):
        self.game_map = game_map
        self.player = player
        self.player_x = start_x
        self.player_y = start_y

    # =========================================================================
    # 左键开掘 + Flood Fill
    # =========================================================================

    def uncover_tile(self, x: int, y: int) -> bool:
        """处理左键开掘 (x, y)。

        - 验证坐标在界内、layer0 == DIRT、未插旗。
        - 陷阱 → 强制揭开 + apply_damage + layer2 写入 TRAP。
        - 安全 → 揭开 + 若邻域雷数为 0 触发 Flood Fill 连锁。

        Returns:
            True 表示操作生效；False 表示无效操作。
        """
        gm = self.game_map

        # 边界与状态校验
        if not gm.is_in_bounds(x, y):
            return False
        if gm.layer0[y][x] != "DIRT":
            return False
        if gm.flags[y][x]:
            return False

        # 陷阱分支
        if gm.traps[y][x]:
            gm.uncover_tile(x, y)            # 强制揭开
            self.player.apply_damage(1)      # 扣血
            gm.set_entity(x, y, "TRAP")      # 静态陷阱显形
            return True

        # 安全分支：揭开当前格
        gm.uncover_tile(x, y)

        # Flood Fill：邻域雷数为 0 时自动揭开连通安全区
        adjacent_traps = gm.get_adjacent_traps_count(x, y)
        if adjacent_traps == 0:
            self._flood_fill(x, y)

        return True

    def _flood_fill(self, start_x: int, start_y: int) -> None:
        """BFS 连锁开掘：从 (start_x, start_y) 出发，
        自动揭开所有连通的 0 雷格及其边缘相邻的数字格。
        跳过已揭开或已插旗的格子。
        """
        gm = self.game_map
        queue = deque()
        queue.append((start_x, start_y))

        while queue:
            cx, cy = queue.popleft()

            # 遍历 8 邻域
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = cx + dx, cy + dy

                    if not gm.is_in_bounds(nx, ny):
                        continue
                    if gm.layer0[ny][nx] != "DIRT":
                        continue  # 已揭开或非泥土
                    if gm.flags[ny][nx]:
                        continue  # 已插旗，跳过

                    # 揭开该邻格
                    gm.uncover_tile(nx, ny)

                    # 若该邻格也是 0 雷，加入队列继续扩散
                    if gm.get_adjacent_traps_count(nx, ny) == 0:
                        queue.append((nx, ny))
                    # 否则为数字格：仅揭开，不再扩散（边缘停止）

    # =========================================================================
    # 右键标雷
    # =========================================================================

    def toggle_flag(self, x: int, y: int) -> bool:
        """处理右键标雷：直接委托给 GameMap.toggle_flag。"""
        return self.game_map.toggle_flag(x, y)

    # =========================================================================
    # 双击 Chording
    # =========================================================================

    def trigger_chording(self, x: int, y: int) -> bool:
        """处理对已揭开数字格的双击/Chording。

        若该格周围实际插旗数 == 周围雷数，则自动揭开所有未标记的邻格
        （安全格 → 递归 Flood Fill，陷阱格 → 触发扣血 + TRAP 显形）。
        """
        gm = self.game_map
        if not gm.is_in_bounds(x, y):
            return False
        if gm.layer0[y][x] != "UNCOVERED":
            return False

        adjacent_mines = gm.get_adjacent_traps_count(x, y)
        if adjacent_mines <= 0:
            return False

        # 统计 8 邻域内实际插旗数
        flag_count = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if gm.is_in_bounds(nx, ny) and gm.flags[ny][nx]:
                    flag_count += 1

        if flag_count != adjacent_mines:
            return False

        # 递归开掘所有未标记的邻格
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not gm.is_in_bounds(nx, ny):
                    continue
                if gm.layer0[ny][nx] == "DIRT" and not gm.flags[ny][nx]:
                    self.uncover_tile(nx, ny)

        return True

    # =========================================================================
    # 障碍交互
    # =========================================================================

    def interact_with_adjacent_obstacle(self, x: int, y: int) -> bool:
        """处理与相邻障碍的交互。

        要求 (x, y) 与玩家当前位置距离不超过 1.5 瓦片（8 邻域）。
        - DIRT_WALL → 消耗 1 把铁锹（pickaxe）
        - LOCK_RED/GREEN/BLUE/EXIT → 消耗对应颜色钥匙

        Returns:
            True 表示障碍被成功清除；False 表示无需交互或资源不足。
        """
        gm = self.game_map

        # 距离校验：8 邻域（距离 ≤ 1 瓦片 < 1.5）
        if abs(x - self.player_x) > 1 or abs(y - self.player_y) > 1:
            return False
        if not gm.is_in_bounds(x, y):
            return False

        obstacle = gm.layer1[y][x]

        # DIRT_WALL 分支
        if obstacle == "DIRT_WALL":
            if self.player.use_tool("pickaxe"):
                gm.set_obstacle(x, y, "NONE")
                gm.uncover_tile(x, y)
                return True
            return False

        # 锁门分支
        for color in _LOCK_COLORS:
            if obstacle == f"LOCK_{color}":
                if self.player.use_key(color):
                    gm.set_obstacle(x, y, "NONE")
                    gm.uncover_tile(x, y)
                    return True
                return False

        return False

    # =========================================================================
    # 怪物战斗判定
    # =========================================================================

    def attack_monster(self, x: int, y: int) -> bool:
        """多级战斗判定树攻击相邻怪物。

        邻域验证：怪物坐标 (x, y) 必须与玩家当前坐标相邻（8 邻域）。
        实体验证：layer2[y][x] 必须为 "MONSTER"。

        战斗判定树：
        1) 柴刀击杀：has_machete == True → 无伤消灭，怪物消失。
        2) 弓箭击杀：arrows > 0 → 消耗 1 箭，无伤消灭，怪物消失。
        3) 肉身硬推：无武器 → apply_damage(1)，怪物保留。

        Returns:
            True 表示怪物被击杀（无伤或消耗弹药）；
            False 表示击杀失败且玩家受伤。
        """
        # 邻域校验：8 邻域内
        if max(abs(x - self.player_x), abs(y - self.player_y)) > 1:
            return False

        gm = self.game_map
        if not gm.is_in_bounds(x, y):
            return False
        if gm.layer2[y][x] != "MONSTER":
            return False

        p = self.player

        # 1) 柴刀击杀
        if p.has_machete:
            gm.set_entity(x, y, "NONE")
            return True

        # 2) 弓箭击杀
        if p.arrows > 0:
            p.arrows -= 1
            gm.set_entity(x, y, "NONE")
            return True

        # 3) 肉身硬推 — 扣血，怪物保留
        p.apply_damage(1)
        return False

    # =========================================================================
    # 玩家移动 + 步入收集
    # =========================================================================

    def move_player(self, target_x: int, target_y: int) -> str:
        """处理玩家移动尝试。

        Returns:
            "SUCCESS"                — 成功移动
            "MONSTER_KILLED"         — 目标格怪物被击杀（未移动）
            "MONSTER_DAMAGED_PLAYER" — 目标格怪物击伤玩家（未移动）
            "ENTER_BONUS"            — 步入楼梯，进入奖励关
            "BLOCKED"                — 不合法移动（不相邻/不可通行）
        """
        gm = self.game_map

        # 相邻校验
        if abs(target_x - self.player_x) > 1 or abs(target_y - self.player_y) > 1:
            return "BLOCKED"

        # 通行校验
        if not gm.is_walkable(target_x, target_y):
            return "BLOCKED"

        # 上锁宝箱 → 阻挡通行（必须用钥匙点击开启）
        if gm.layer2[target_y][target_x] == "LOCKED_CHEST":
            return "BLOCKED"

        # 怪物卡点 → 触发战斗
        if gm.layer2[target_y][target_x] == "MONSTER":
            if self.attack_monster(target_x, target_y):
                return "MONSTER_KILLED"
            else:
                return "MONSTER_DAMAGED_PLAYER"

        # 更新玩家位置
        self.player_x = target_x
        self.player_y = target_y

        # 步入收集处理
        entity = gm.layer2[target_y][target_x]
        if entity != "NONE":
            self._collect_entity(target_x, target_y, entity)
            if entity == "STAIRS":
                return "ENTER_BONUS"

        return "SUCCESS"

    def _collect_entity(self, x: int, y: int, entity: str) -> None:
        """处理道具收集：调用 player 方法 + 清空实体。"""
        p = self.player

        if entity == "CHEST":
            # 宝箱 → 多物资爆出
            loot_items = LootTable().generate_chest_loot(is_locked=False)
            for item_type, amount in loot_items:
                self._apply_loot(item_type, amount)
            self.game_map.set_entity(x, y, "NONE")
            return

        if entity == "COIN":
            p.add_gold(1)
        elif entity == "GEM":
            p.add_gold(10)
        elif entity == "PICKAXE":
            p.add_tool("pickaxe", 1)
        elif entity == "DYNAMITE":
            p.add_tool("dynamite", 1)
        elif entity == "MAP":
            p.add_tool("map", 1)
        elif entity == "HEART":
            p.add_hearts(1)
        elif entity == "SHIELD":
            p.add_shields(1)
        elif entity == "AMULET":
            p.has_amulet = True
        elif entity == "ARROW":
            p.arrows = min(p.arrows + 1, 9)
        elif entity == "MACHETE":
            p.has_machete = True

        # 清空该格实体（无论是否实际获得）
        self.game_map.set_entity(x, y, "NONE")

    # =========================================================================
    # 宝箱交互
    # =========================================================================

    def unlock_chest(self, x: int, y: int) -> bool:
        """点击解锁相邻的上锁宝箱。

        判定流程：
        1. 目标格必须为 LOCKED_CHEST
        2. 玩家必须位于 8 邻域内
        3. 玩家必须持有至少 1 把钥匙（任意颜色）
        4. 扣除持有数量最多的那把钥匙
        5. 生成上锁宝箱大奖物资并堆叠到玩家
        6. 清空实体

        Returns:
            True 表示开锁成功；False 表示钥匙不足/不合法。
        """
        gm = self.game_map

        # 边界与实体验证
        if not gm.is_in_bounds(x, y):
            return False
        if gm.layer2[y][x] != "LOCKED_CHEST":
            return False

        # 邻域校验：必须在 8 邻域内
        if max(abs(x - self.player_x), abs(y - self.player_y)) > 1:
            return False

        p = self.player

        # 找持有数量最多的钥匙颜色
        max_color = max(p.keys, key=lambda c: p.keys[c])
        if p.keys[max_color] <= 0:
            return False  # 没有任何钥匙

        # 扣除钥匙
        p.use_key(max_color)

        # 生成宝箱大奖
        loot_items = LootTable().generate_chest_loot(is_locked=True)
        for item_type, amount in loot_items:
            self._apply_loot(item_type, amount)

        # 清空实体（玩家留在原地，不位移）
        gm.set_entity(x, y, "NONE")
        return True

    def _apply_loot(self, item_type: str, amount: int) -> None:
        """将单条物资条目应用到玩家数据。"""
        p = self.player

        if item_type == "COIN":
            p.add_gold(amount)
        elif item_type == "GEM":
            p.add_gold(amount * 10)
        elif item_type == "PICKAXE":
            for _ in range(amount):
                p.add_tool("pickaxe", 1)
        elif item_type == "DYNAMITE":
            for _ in range(amount):
                p.add_tool("dynamite", 1)
        elif item_type == "MAP":
            for _ in range(amount):
                p.add_tool("map", 1)
        elif item_type == "HEART":
            p.add_hearts(amount)
        elif item_type == "SHIELD":
            p.add_shields(amount)
        elif item_type == "AMULET":
            p.has_amulet = True
        elif item_type == "ARROW":
            p.arrows = min(p.arrows + amount, 9)
        elif item_type == "MACHETE":
            p.has_machete = True

    # =========================================================================
    # 主动工具：炸药爆破
    # =========================================================================

    def use_dynamite(self, center_x: int, center_y: int) -> bool:
        """使用炸药进行 3x3 无伤爆破。

        消耗 1 个炸药，对以 (center_x, center_y) 为中心的 3x3 区域施加：
        - DIRT_WALL 障碍粉碎（设为 NONE）
        - WALL / LOCK_EXIT 等核心物体免疫
        - DIRT 地形强揭为 UNCOVERED，并清除该格红旗
        - 隐藏陷阱直接清除（不触发扣血）
        - MONSTER 实体气化销毁
        - 宝物（COIN/GEM 等）保留在原地

        Returns:
            True 表示爆破成功；False 表示炸药不足。
        """
        # 消耗校验
        if not self.player.use_tool("dynamite"):
            return False

        gm = self.game_map

        # 爆破范围循环：3x3 区域
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                tx, ty = center_x + dx, center_y + dy

                # 越界过滤
                if not gm.is_in_bounds(tx, ty):
                    continue

                # 1) 障碍粉碎：DIRT_WALL → NONE；WALL/LOCK_* 等免疫
                obstacle = gm.layer1[ty][tx]
                if obstacle == "DIRT_WALL":
                    gm.set_obstacle(tx, ty, "NONE")
                # WALL / LOCK_RED / LOCK_GREEN / LOCK_BLUE / LOCK_EXIT 等不予处理（免疫）

                # 2) 地形强揭：DIRT → UNCOVERED，并清除红旗
                if gm.layer0[ty][tx] == "DIRT":
                    gm.layer0[ty][tx] = "UNCOVERED"
                    gm.flags[ty][tx] = False

                # 3) 陷阱清除：直接强行设为 False（无伤安全扫雷）
                if gm.traps[ty][tx]:
                    gm.traps[ty][tx] = False

                # 4) 生物抹杀：MONSTER → NONE
                if gm.layer2[ty][tx] == "MONSTER":
                    gm.set_entity(tx, ty, "NONE")

                # 5) 宝物保留：COIN/GEM/PICKAXE/DYNAMITE/MAP/HEART/SHIELD/AMULET/STAIRS
                # 不处理 layer2 中的非 MONSTER 实体，保留在原地
                # 因为泥土已变为 UNCOVERED，玩家后续可走上去拾取

        return True

    # =========================================================================
    # 主动工具：地图扫描
    # =========================================================================

    def use_map(self) -> bool:
        """使用地图进行 5x5 雷达扫描并自动插旗。

        消耗 1 个地图，以玩家当前位置为中心扫描 5x5 区域：
        - 对未挖开泥土 (layer0 == DIRT) 且下有隐藏陷阱 (traps == True) 的格子
        - 自动为玩家插上安全红旗 (flags = True)

        Returns:
            True 表示扫描成功；False 表示地图不足。
        """
        # 消耗校验
        if not self.player.use_tool("map"):
            return False

        gm = self.game_map
        px, py = self.player_x, self.player_y

        # 扫描范围循环：5x5 区域
        for dy in (-2, -1, 0, 1, 2):
            for dx in (-2, -1, 0, 1, 2):
                tx, ty = px + dx, py + dy

                # 越界过滤
                if not gm.is_in_bounds(tx, ty):
                    continue

                # 雷达标注：未挖开泥土 + 隐藏陷阱 → 自动插旗
                if gm.layer0[ty][tx] == "DIRT" and gm.traps[ty][tx]:
                    gm.flags[ty][tx] = True

        return True
