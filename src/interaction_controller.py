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
from active_mummy import ActiveMummy
from mummy_king import MummyKing
from spike_trap import SpikeTrap, FLIPPED_OUT, FLIPPED_IN, EVENT_NONE
from config import ACTIVE_MUMMY, MUMMY_KING, MUMMY_KING_MAX_HEARTS
from config import SPIKE_TRAP


# 可收集道具集合
_COLLECTIBLE_ENTITIES = {
    "COIN", "GEM", "PICKAXE", "DYNAMITE", "MAP",
    "HEART", "SHIELD", "AMULET", "STAIRS",
    "ARROW", "MACHETE", "CHEST", "KEY_EXIT",
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

        # 当前地图中所有活性木乃伊（来自散布 / 关卡生成）
        self.active_mummies: list[ActiveMummy] = []

        # 当前地图中所有法老王首领（Boss 关卡，来自关卡生成）
        self.mummy_kings: list[MummyKing] = []

        # 当前地图中所有周期地刺（来自关卡生成 + 后续铺放）
        self.spike_traps: list[SpikeTrap] = []

        # 玩家受伤后的短暂无敌计时（单位秒），防止每帧重复扣血。
        # 当玩家受到伤害时设为一个很小的正值（如 0.05），每帧递减至 0。
        # 仅作为"本次重生后不再连续受伤"的保护。
        self.invincible_timer: float = 0.0

        # 屏幕闪烁：一次性的颜色 + 剩余时长（绘图层读取以实现闪屏效果）
        self.screen_flash_color: tuple[int, int, int] | None = None
        self.screen_flash_duration: float = 0.0

    # =========================================================================
    # 活性木乃伊 — 生成对接
    # =========================================================================

    def link_active_mummies_from_map(self) -> int:
        """扫描地图 layer2 中的 ACTIVE_MUMMY 占位并创建对应 ActiveMummy 实例。

        应在关卡生成后由 GameplayScreen.on_enter() 调用一次，
        避免每次 move_player 时重复合并。

        同时扫描法老王首领 MUMMY_KING —— 三个 game_screen 调用点
        (on_enter / 重置 / 读档) 均通过此入口，因此一处修改即覆盖全部。

        Returns:
            扫描到的活性木乃伊数量（不含 Boss）。
        """
        if self.active_mummies or self.mummy_kings:
            # 已初始化，避免重复合并
            return len(self.active_mummies) + len(self.mummy_kings)

        found = 0
        king_found = 0
        gm = self.game_map
        for y in range(gm.height):
            for x in range(gm.width):
                cell = gm.layer2[y][x]
                if cell == ACTIVE_MUMMY:
                    self.active_mummies.append(ActiveMummy(x, y))
                    found += 1
                elif cell == MUMMY_KING:
                    self.mummy_kings.append(MummyKing(x, y))
                    king_found += 1
        return found + king_found

    def link_spike_traps_from_map(self) -> int:
        """扫描地图 layer2 中的 SPIKE_TRAP 占位并创建对应 SpikeTrap 实例。

        应在关卡生成后由 GameplayScreen.on_enter() 调用一次，
        避免每次 move_player 时重复合并。

        Returns:
            扫描到的地刺数量。
        """
        if self.spike_traps:
            # 已初始化，避免重复合并
            return len(self.spike_traps)

        gm = self.game_map
        found = 0
        for y in range(gm.height):
            for x in range(gm.width):
                if gm.layer2[y][x] == SPIKE_TRAP:
                    self.spike_traps.append(SpikeTrap(x, y))
                    found += 1
        return found

    def spawn_active_mummy(self, x: int, y: int) -> None:
        """在指定坐标生成一个活性木乃伊（同步写入 layer2 + 实例列表）。

        仅在坐标合法且该格不是墙时使用。"""
        gm = self.game_map
        if not gm.is_in_bounds(x, y):
            return
        if gm.layer0[y][x] != "UNCOVERED":
            return
        if gm.layer1[y][x] != "NONE":
            return
        # 避免重叠
        if gm.layer2[y][x] == ACTIVE_MUMMY:
            return
        gm.set_entity(x, y, ACTIVE_MUMMY)
        self.active_mummies.append(ActiveMummy(x, y))

    def spawn_mummy_king(self, x: int, y: int) -> None:
        """在指定坐标生成一个法老王首领（同步写入 layer2 + 实例列表）。

        仅在坐标合法、层 0 UNCOVERED、层 1 NONE、层 2 NONE 时使用。
        """
        gm = self.game_map
        if not gm.is_in_bounds(x, y):
            return
        if gm.layer0[y][x] != "UNCOVERED":
            return
        if gm.layer1[y][x] != "NONE":
            return
        if gm.layer2[y][x] != "NONE":
            return
        gm.set_entity(x, y, MUMMY_KING)
        self.mummy_kings.append(MummyKing(x, y))

    def _find_first_empty_orthogonal(self, cx: int, cy: int) -> tuple[int, int] | None:
        """返回 (cx, cy) 的 4 正交邻中首个层 0/1/2 均为空的格子。

        搜索顺序：上 → 下 → 左 → 右，与召唤规格一致。
        无合法格时返回 None。
        """
        gm = self.game_map
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = cx + dx, cy + dy
            if not gm.is_in_bounds(nx, ny):
                continue
            if gm.layer0[ny][nx] != "UNCOVERED":
                continue
            if gm.layer1[ny][nx] != "NONE":
                continue
            if gm.layer2[ny][nx] != "NONE":
                continue
            return (nx, ny)
        return None

    def summon_minion(self, king: MummyKing) -> bool:
        """在首领相邻 4 正交空地中召唤一只爪牙（ActiveMummy）。

        选取首个合法空邻（顺序：上/下/左/右）。
        若无合法格则静默跳过。

        Returns:
            True 表示成功召唤；False 表示无合法格。
        """
        cell = self._find_first_empty_orthogonal(king.x, king.y)
        if cell is None:
            return False
        self.spawn_active_mummy(cell[0], cell[1])
        return True

    @staticmethod
    def _play_metal_clang() -> None:
        """播放金属打击重音（柴刀 / 弓箭命中首领）。静默容错。"""
        try:
            from src.asset_manager import AssetManager
            AssetManager.get_instance().get_sound("metal_clang").play()
        except Exception:
            pass

    @staticmethod
    def _play_summon_growl() -> None:
        """播放爪牙召唤低吼声。静默容错。"""
        try:
            from src.asset_manager import AssetManager
            AssetManager.get_instance().get_sound("summon_growl").play()
        except Exception:
            pass

    @staticmethod
    def _play_boss_slain_fanfare() -> None:
        """播放首领倒下欢呼声。静默容错。"""
        try:
            from src.asset_manager import AssetManager
            AssetManager.get_instance().get_sound("boss_slain_fanfare").play()
        except Exception:
            pass

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
            # 开掘动作作为一拍，驱动地刺（静态 trap 与 地刺同拍触发）
            self._process_spike_turn()
            return True

        # 安全分支：揭开当前格
        gm.uncover_tile(x, y)

        # Flood Fill：邻域雷数为 0 时自动揭开连通安全区
        adjacent_traps = gm.get_adjacent_traps_count(x, y)
        if adjacent_traps == 0:
            self._flood_fill(x, y)

        # 开掘动作作为一拍，驱动地刺步数递增（触发驻留刺击判定）
        self._process_spike_turn()

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

        # Chording 结算作为一次消耗型操作，驱动地刺步数递增
        self._process_spike_turn()

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
            p.total_monsters_slain += 1
            self._check_achievements()
            return True

        # 2) 弓箭击杀
        if p.arrows > 0:
            p.arrows -= 1
            gm.set_entity(x, y, "NONE")
            p.total_monsters_slain += 1
            self._check_achievements()
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

        # 法老王首领卡点 → 触发战斗（走入 Boss 格等同于发动一次攻击）
        if gm.layer2[target_y][target_x] == MUMMY_KING:
            alive = self.attack_mummy_king(target_x, target_y)
            if alive:
                # Boss 被击杀 —— attack_mummy_king 已将格改为 KEY_EXIT，
                # 玩家步入这个已变为钥匙的格并收集它。
                self.player_x = target_x
                self.player_y = target_y
                self._collect_entity(target_x, target_y,
                                    gm.layer2[target_y][target_x])
                self._process_king_turn()
                self._process_mummy_turn()
                return "BOSS_SLAIN"
            return "BOSS_DAMAGED_PLAYER"

        # 更新玩家位置
        self.player_x = target_x
        self.player_y = target_y

        # 步入收集处理
        entity = gm.layer2[target_y][target_x]
        if entity != "NONE":
            self._collect_entity(target_x, target_y, entity)
            if entity == "STAIRS":
                return "ENTER_BONUS"

        # 玩家成功移动后，推进地刺、首领、活性木乃伊的回合
        self._process_spike_turn()   # 地刺翻转 + 驻留刺击判定
        self._process_king_turn()
        self._process_mummy_turn()

        return "SUCCESS"

    def _collect_entity(self, x: int, y: int, entity: str) -> None:
        """处理道具收集：调用 player 方法 + 清空实体。"""
        p = self.player

        if entity == "CHEST":
            # 宝箱 → 多物资爆出
            loot_items = LootTable().generate_chest_loot(is_locked=False)
            for item_type, amount in loot_items:
                self._apply_loot(item_type, amount)
            self._check_achievements()
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
        elif entity == "KEY_EXIT":
            # 终点钥匙 —— 首领爆落后玩家走入此格取得，用于开启 LOCK_EXIT
            p.keys["EXIT"] += 1

        # 金币/道具收集后触发成就评估（拾取金币可能解锁 Gold Rush）
        self._check_achievements()

        # 清空该格实体（无论是否实际获得）
        self.game_map.set_entity(x, y, "NONE")

    # =========================================================================
    # 周期地刺 — 驱动 / 驻留刺击 / 危险伤害
    # =========================================================================

    def _process_spike_turn(self) -> None:
        """玩家成功执行一次消耗型操作后驱动所有地刺推进一拍。

        对每个地刺调用 ``on_player_move()``：
        - 若状态翻转 → 派发弹出 / 收缩音效。

        驱动完成后做一次「玩家站位扫描」：
        - 若玩家所在格存在处于 ``EXTENDED`` 的地刺 → 触发伤害
          （覆盖两种场景：进入已弹出的尖刺格 + 驻留原地被弹出的尖刺刺伤）。

        无敌帧保护：``invincible_timer > 0`` 时跳过整轮驱动与判定。
        """
        if self.invincible_timer > 0:
            return

        try:
            from src.audio_manager import AudioManager
        except Exception:
            AudioManager = None

        # 1) 推进所有地刺一拍，派发翻转音效
        for spike in self.spike_traps:
            event = spike.on_player_move()
            if event not in (FLIPPED_OUT, FLIPPED_IN):
                continue
            if AudioManager is not None:
                try:
                    sound = "spike_out.wav" if event == FLIPPED_OUT else "spike_in.wav"
                    AudioManager.get_instance().play_sfx(sound)
                except Exception:
                    pass

        # 2) 玩家站位扫描：只要站在 EXTENDED 的地刺上，即受伤
        if self.invincible_timer > 0:
            return
        px, py = self.player_x, self.player_y
        for spike in self.spike_traps:
            if spike.x == px and spike.y == py and spike.is_extended():
                self._apply_hazard_damage("spike")
                break  # 单格至多一个地刺，命中即跳出

    def _apply_hazard_damage(self, hazard_type: str) -> bool:
        """统一的周期性危险伤害入口：扣血 + 屏闪 + 受伤音效。

        Args:
            hazard_type: 危险类型字符串，用于映射受伤音效
                         （"spike" → ``spike_damage.wav``,
                          "trap"  → ``trap_damage.wav``, 其他 → ``hit.wav``）。

        Returns:
            玩家受到伤害后是否存活。
        """
        if self.invincible_timer > 0:
            return True

        alive = self.player.apply_damage(1)

        # 短无敌帧 + 红色屏闪标记（渲染层读取）
        self.invincible_timer = 0.25
        self.screen_flash_color = (255, 60, 60)
        self.screen_flash_duration = 0.18

        sound_map = {
            "spike": "spike_damage.wav",
            "trap": "trap_damage.wav",
        }
        sound = sound_map.get(hazard_type, "hit.wav")
        try:
            from src.audio_manager import AudioManager
            AudioManager.get_instance().play_sfx(sound)
        except Exception:
            pass

        return alive

    # =========================================================================
    # 活性木乃伊 — 回合处理 / 伤害 / 安全弹开
    # =========================================================================

    def _process_mummy_turn(self) -> None:
        """推进所有活性木乃伊的一个回合。

        对每个木乃伊：
        1) 调用 ``update_action_turn`` 获取新坐标。
        2) 同步 layer2：清除旧占位 / 写入新占位。
        3) 若木乃伊任一时刻（移动前原本就站在玩家格，或移动后落到玩家格）
           与玩家坐标重合 → 触发伤害 + 安全弹开。

        遍历时使用快照列表，避免在迭代期间修改 ``active_mummies``。
        """
        # 提前过滤掉已经死亡的可能（比如被炸药气化）——实际不在此处理
        living = [m for m in self.active_mummies if m is not None]
        self.active_mummies = living

        for mummy in list(living):
            prev = (mummy.x, mummy.y)

            # 若木乃伊此刻已经站在玩家身上（玩家走进木乃伊格），
            # 记录标志并强制触发碰撞（不等待木乃伊再次位移）。
            already_overlapped = (prev == (self.player_x, self.player_y))

            new_x, new_y = mummy.update_action_turn(
                self.player_x, self.player_y, self.game_map
            )

            # 防止恶意写入越界坐标
            if not self.game_map.is_in_bounds(new_x, new_y):
                new_x, new_y = prev

            # 同步 layer2
            if (new_x, new_y) != prev:
                self.game_map.set_entity(prev[0], prev[1], "NONE")
                self.game_map.set_entity(new_x, new_y, ACTIVE_MUMMY)

            # 检查重合：已重叠或木乃伊移动到了玩家所在格
            if ((new_x, new_y) == (self.player_x, self.player_y)
                    or already_overlapped) and self.invincible_timer <= 0:
                self._apply_mummy_damage(mummy, prev)

    def _apply_mummy_damage(self, mummy: ActiveMummy,
                            prev_pos: tuple[int, int]) -> None:
        """木乃伊撞击玩家：发动伤害 + 飘字 + 屏闪 + 安全弹开。

        伤害优先扣护盾；不足则扣红心。
        安全弹开：沿木乃伊来时的反方向推 1 格；若被阻挡则重置回 prev_pos；
        仍不行则从玩家周围找距离 ≥ 2 的可行通路格子放置。
        """
        # 1. 发动伤害
        alive = self.player.apply_damage(1)

        # 触发短暂无敌窗口，防止下一帧木乃伊仍在原地继续扣血
        self.invincible_timer = 0.1

        # 飘字与屏闪标记（由渲染层在 GameplayScreen 读取播放）
        self.screen_flash_color = (255, 30, 30)  # 红色屏闪
        self.screen_flash_duration = 0.15

        # 2. 安全弹开木乃伊
        dx = mummy.x - prev_pos[0]
        dy = mummy.y - prev_pos[1]
        # 反弹目标：沿来时的反方向
        bounce_x = mummy.x + dx
        bounce_y = mummy.y + dy

        if self._is_valid_mummy_cell(bounce_x, bounce_y, exclude_player=True):
            final_x, final_y = bounce_x, bounce_y
        elif self._is_valid_mummy_cell(prev_pos[0], prev_pos[1], exclude_player=True):
            final_x, final_y = prev_pos
        else:
            # 从玩家周围找距离 >= 2 的可行通路
            final_x, final_y = self._find_fallback_cell()

        # 用 NONE 覆盖当前（重合）坐标 → ACTIVE_MUMMI 写到新位置
        # 注意：此时 mummy.x/y 仍在玩家身上，需先清 NONE
        self.game_map.set_entity(mummy.x, mummy.y, "NONE")
        mummy.x, mummy.y = final_x, final_y
        self.game_map.set_entity(final_x, final_y, ACTIVE_MUMMY)

        if not alive:
            # 玩家死亡 — GameplayScreen 会在主循环中检测到 player 死亡
            pass

    def _is_valid_mummy_cell(self, x: int, y: int,
                             exclude_player: bool = False) -> bool:
        """判断木乃伊是否能占据 (x, y)。"""
        if not self.game_map.is_in_bounds(x, y):
            return False
        if not self.game_map.is_walkable(x, y):
            return False
        # 不允许覆盖宝箱/推门等实体（可自定义规则）
        entity = self.game_map.layer2[y][x]
        if entity not in ("NONE", ACTIVE_MUMMY):
            return False
        if exclude_player and (x, y) == (self.player_x, self.player_y):
            return False
        return True

    def _find_fallback_cell(self) -> tuple[int, int]:
        """从玩家周围绕行寻找曼哈顿距离 >= 2 的可行走格子。

        尝试顺序：曼哈顿距离从 2 到 5，从玩家坐标向外扩散。
        若全部不可行，返回玩家坐标（极端情况，交由外层判断）。
        """
        for manhattan in range(2, 6):
            # 扫描与玩家曼哈顿距离为 manhattan 的所有格子
            for dy in range(-manhattan, manhattan + 1):
                for dx in range(-manhattan, manhattan + 1):
                    if abs(dx) + abs(dy) != manhattan:
                        continue
                    cx = self.player_x + dx
                    cy = self.player_y + dy
                    if self._is_valid_mummy_cell(cx, cy, exclude_player=True):
                        return (cx, cy)
        # 极端回退：返回玩家当前位置（让子弹下一次再处理）
        return (self.player_x, self.player_y)

    def tick_invincible(self, dt: float) -> None:
        """每帧由控制器外部推进，衰减无敌窗口。"""
        if self.invincible_timer > 0:
            self.invincible_timer = max(0.0, self.invincible_timer - dt)
        if self.screen_flash_duration > 0:
            self.screen_flash_duration = max(0.0, self.screen_flash_duration - dt)
            if self.screen_flash_duration <= 0:
                self.screen_flash_color = None

    # =========================================================================
    # 活性木乃伊 — 消灭
    # =========================================================================

    def attack_active_mummy(self, x: int, y: int) -> bool:
        """尝试消灭坐标 (x, y) 上的活性木乃伊。

        采用与 ``attack_monster`` 相同的优先级：
        1) 柴刀消耗免耗（has_machete）→ 无伤灭亡
        2) 弓箭（arrows > 0）→ 消耗 1 箭，无伤灭亡
        3) 肉身硬推 → apply_damage(1)，且本次不会移除木乃伊（保留实体）

        Returns:
            True 表示木乃伊已死亡并从地图/列表中移除；
            False 表示攻击失败且玩家受伤。
        """
        # 邻域校验：8 邻域
        if max(abs(x - self.player_x), abs(y - self.player_y)) > 1:
            return False
        if not self.game_map.is_in_bounds(x, y):
            return False
        if self.game_map.layer2[y][x] != ACTIVE_MUMMY:
            return False

        p = self.player

        # 找到该格对应的 ActiveMummy 实例
        target = None
        for m in self.active_mummies:
            if m.x == x and m.y == y:
                target = m
                break

        # 1. 柴刀
        if p.has_machete:
            self._kill_mummy(target, x, y)
            p.total_monsters_slain += 1
            self._check_achievements()
            return True

        # 2. 弓箭
        if p.arrows > 0:
            p.arrows -= 1
            self._kill_mummy(target, x, y)
            p.total_monsters_slain += 1
            self._check_achievements()
            return True

        # 3. 肉身硬推
        p.apply_damage(1)
        self.invincible_timer = 0.1
        self.screen_flash_color = (255, 30, 30)
        self.screen_flash_duration = 0.15
        return False

    def _kill_mummy(self, mummy: ActiveMummy | None, x: int, y: int) -> None:
        """从地图和活跃列表中移除木乃伊。"""
        self.game_map.set_entity(x, y, "NONE")
        if mummy is not None:
            # 安全删除 — 用 try/except 防止已被提前移除
            try:
                self.active_mummies.remove(mummy)
            except ValueError:
                pass

    # =========================================================================
    # 法老王首领 — 战斗 / 回合 / 召唤 / 死亡掉落
    # =========================================================================

    def attack_mummy_king(self, x: int, y: int) -> bool:
        """攻击坐标 (x, y) 上的法老王首领。

        采用与 ``attack_monster`` 相同的武器优先级：
        1) 柴刀（has_machete）→ 不消耗，扣 1 血
        2) 弓箭（arrows > 0）→ 消耗 1 箭，扣 1 血
        3) 肉身硬推 → apply_damage(1)，Boss 保留

        **受击 100% 召唤**：只要 Boss 未死亡，每次命中后必在相邻
        4 正交空地召唤一只 ``ActiveMummy`` 爪牙。

        **死亡掉落终点钥匙**：生命归零时，将 Boss 所在格 layer2 改写
        为 ``"KEY_EXIT"``，玩家拾取后方可开启出口门。

        Returns:
            True 表示 Boss 被击杀（死亡并掉落钥匙）；
            False 表示命中但 Boss 仍存活，或玩家无武器而受伤。
        """
        # 邻域校验：8 邻域内
        if max(abs(x - self.player_x), abs(y - self.player_y)) > 1:
            return False

        gm = self.game_map
        if not gm.is_in_bounds(x, y):
            return False
        if gm.layer2[y][x] != MUMMY_KING:
            return False

        p = self.player

        # 找到该格对应的 MummyKing 实例
        target: MummyKing | None = None
        for k in self.mummy_kings:
            if k.x == x and k.y == y:
                target = k
                break
        if target is None:
            # 层 2 占位与实例不同步 — 防御性清理
            gm.set_entity(x, y, "NONE")
            return False

        has_weapon = p.has_machete or p.arrows > 0

        # 1) 柴刀命中
        if p.has_machete:
            self._play_metal_clang()
            target.hearts -= 1
            if target.hearts > 0:
                # 受创 100% 召唤爪牙
                self._on_king_hit_summon(target)
                return False
            # 死亡 → 掉落终点钥匙
            self._kill_king_drop_key(target)
            return True

        # 2) 弓箭命中
        if p.arrows > 0:
            p.arrows -= 1
            self._play_metal_clang()
            target.hearts -= 1
            if target.hearts > 0:
                self._on_king_hit_summon(target)
                return False
            self._kill_king_drop_key(target)
            return True

        # 3) 肉身硬推 — 扣血，Boss 保留，双方反向弹开
        p.apply_damage(1)
        self.invincible_timer = 0.1
        self.screen_flash_color = (255, 30, 30)
        self.screen_flash_duration = 0.15
        self._bounce_king_from_player(target)
        return False

    def _on_king_hit_summon(self, king: MummyKing) -> None:
        """受击召唤：100% 概率在相邻空地召唤一只爪牙。"""
        self.summon_minion(king)
        self._play_summon_growl()
        # 屏闪标记（蓝色 — 召唤特效）
        self.screen_flash_color = (80, 120, 255)
        self.screen_flash_duration = 0.12

    def _kill_king_drop_key(self, king: MummyKing) -> None:
        """击杀首领：移除实例，原格掉落终点钥匙 KEY_EXIT。"""
        # 安全移除实例
        try:
            self.mummy_kings.remove(king)
        except ValueError:
            pass
        # 原格改写为终点钥匙
        self.game_map.set_entity(king.x, king.y, "KEY_EXIT")
        # 金色屏闪 + 欢呼音
        self.screen_flash_color = (255, 215, 0)
        self.screen_flash_duration = 0.25
        self._play_boss_slain_fanfare()

    def _bounce_king_from_player(self, king: MummyKing) -> None:
        """肉身硬推：将首领向玩家反方向弹开 1 格。"""
        px, py = self.player_x, self.player_y
        dx = king.x - px
        dy = king.y - py
        # 标准化方向（避免 0 向量）
        if dx == 0 and dy == 0:
            dx = 1
        step_x = 1 if dx > 0 else (-1 if dx < 0 else 0)
        step_y = 1 if dy > 0 else (-1 if dy < 0 else 0)
        bounce_x = king.x + step_x
        bounce_y = king.y + step_y
        gm = self.game_map
        if (gm.is_in_bounds(bounce_x, bounce_y)
                and gm.is_walkable(bounce_x, bounce_y)
                and gm.layer2[bounce_y][bounce_x] == "NONE"):
            gm.set_entity(king.x, king.y, "NONE")
            king.x, king.y = bounce_x, bounce_y
            gm.set_entity(king.x, king.y, MUMMY_KING)

    def _process_king_turn(self) -> None:
        """推进所有法老王首领的一个回合。

        对每个首领：
        1) 调用 ``update_action_turn`` 获取新坐标。
        2) 同步 layer2：清除旧占位 / 写入新占位。
        3) 若满足回合召唤条件 → 召唤爪牙 + 重置计数器。
        4) 若与玩家坐标重合 → 触发伤害 + 安全弹开。
        """
        living = [k for k in self.mummy_kings if k is not None]
        self.mummy_kings = living

        for king in list(living):
            prev = (king.x, king.y)
            already_overlapped = (prev == (self.player_x, self.player_y))

            new_x, new_y = king.update_action_turn(
                self.player_x, self.player_y, self.game_map
            )

            # 防止恶意写入越界坐标
            if not self.game_map.is_in_bounds(new_x, new_y):
                new_x, new_y = prev

            # 同步 layer2
            if (new_x, new_y) != prev:
                self.game_map.set_entity(prev[0], prev[1], "NONE")
                self.game_map.set_entity(new_x, new_y, MUMMY_KING)

            # 回合召唤（每 5 回合自动召唤一只爪牙）
            if king.should_summon_this_turn():
                if self.summon_minion(king):
                    king.reset_summon_counter()

            # 检查重合：已重叠或首领移动到了玩家所在格
            if ((new_x, new_y) == (self.player_x, self.player_y)
                    or already_overlapped) and self.invincible_timer <= 0:
                self._apply_king_damage(king, prev)

    def _apply_king_damage(self, king: MummyKing,
                           prev_pos: tuple[int, int]) -> None:
        """首领撞击玩家：发动伤害 + 屏闪 + 安全弹开。

        与 ``_apply_mummy_damage`` 语义一致，伤害为 1 点。
        """
        # 1. 发动伤害
        alive = self.player.apply_damage(1)

        # 触发短暂无敌窗口
        self.invincible_timer = 0.1

        # 红色屏闪标记
        self.screen_flash_color = (255, 30, 30)
        self.screen_flash_duration = 0.15

        # 2. 安全弹开首领
        dx = king.x - prev_pos[0]
        dy = king.y - prev_pos[1]
        bounce_x = king.x + dx
        bounce_y = king.y + dy

        if self._is_valid_mummy_cell(bounce_x, bounce_y, exclude_player=True):
            final_x, final_y = bounce_x, bounce_y
        elif self._is_valid_mummy_cell(prev_pos[0], prev_pos[1], exclude_player=True):
            final_x, final_y = prev_pos
        else:
            final_x, final_y = self._find_fallback_cell()

        self.game_map.set_entity(king.x, king.y, "NONE")
        king.x, king.y = final_x, final_y
        self.game_map.set_entity(final_x, final_y, MUMMY_KING)

        if not alive:
            pass

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

    # =========================================================================
    # 成就触发（第 48 课）
    # =========================================================================

    def _check_achievements(self) -> None:
        """在玩家状态发生变化时，由调用点触发一次成就解锁评估。

        成就逻辑必须绝不中断主流程：任何异常都静默吞掉。
        """
        try:
            from src.game_manager import GameManager
            am = GameManager.get_instance().achievement_manager
            if am is not None:
                am.check_unlocks()
        except Exception:
            pass
