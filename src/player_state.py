"""玩家状态核心数据模型 — Microsoft Treasure Hunt

管理玩家的生命、护盾、背包工具、钥匙、金币和升级逻辑。
所有数值常量从 src/config.py 统一导入，避免硬编码。
"""

import os as _os
import sys as _sys

# 将 src/ 加入模块搜索路径，使 `import config` 在任何工作目录下都能找到
_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

from config import (
    INITIAL_HEARTS,
    HARD_CAP_HEARTS,
    HEART_UPGRADE_PRICES,
    INITIAL_SHIELDS,
    HARD_CAP_SHIELDS,
    BAG_CAPACITY_TIERS,
    BAG_UPGRADE_PRICES,
    INITIAL_BAG_CAPACITY,
)


class PlayerState:
    """玩家全套状态容器 + 操作方法"""

    def __init__(self):
        # ---- 生命与护盾 ----
        self.current_hearts: int = INITIAL_HEARTS
        self.max_hearts: int = INITIAL_HEARTS
        self.current_shields: int = INITIAL_SHIELDS
        self.max_shields: int = 1  # 初始可装备 1 个护盾

        # ---- 经济 ----
        self.gold: int = 0

        # ---- 背包工具 ----
        self.tools: dict = {"pickaxe": 0, "dynamite": 0, "map": 0}
        self.bag_tier_index: int = 0

        # ---- 钥匙 ----
        self.keys: dict = {"RED": 0, "GREEN": 0, "BLUE": 0, "EXIT": 0}

        # ---- 生涯统计 ----
        self.highest_level_cleared: int = 0
        self.total_gold_earned: int = 0
        self.total_runs: int = 0          # 累计开始新游戏的次数
        self.total_monsters_slain: int = 0  # 累计击杀木乃伊数量
        self.unlocked_badges: list = []   # 已解锁成就 ID，如 "gold_rush_bronze"

        # ---- 一次性道具 / 临时状态 ----
        self.arrows: int = 0
        self.has_machete: bool = False
        self.has_amulet: bool = False
        self.has_clover: bool = False
        self.amulets_count: int = 0  # 护身符复活次数统计

    # =========================================================================
    # 属性（只读计算）
    # =========================================================================

    def max_capacity(self) -> int:
        """返回当前容量等级对应的背包上限"""
        return BAG_CAPACITY_TIERS[self.bag_tier_index]

    def total_tools(self) -> int:
        """返回当前携带的工具总量"""
        return sum(self.tools.values())

    # =========================================================================
    # 核心操作方法
    # =========================================================================

    def apply_damage(self, amount: int = 1) -> bool:
        """扣减伤害。护盾优先吸收，护盾耗尽再扣红心。

        Returns:
            True  = 仍然存活
            False = 红心归零（死亡）
        """
        remaining = amount

        # 优先扣护盾
        if self.current_shields > 0:
            absorbed = min(self.current_shields, remaining)
            self.current_shields -= absorbed
            remaining -= absorbed

        # 剩余伤害扣红心
        if remaining > 0:
            self.current_hearts = max(0, self.current_hearts - remaining)

        return self.current_hearts > 0

    def add_hearts(self, amount: int) -> int:
        """增加当前红心（不超过 max_hearts）。返回实际增加的值。"""
        if amount <= 0:
            return 0
        old = self.current_hearts
        self.current_hearts = min(self.current_hearts + amount, self.max_hearts)
        return self.current_hearts - old

    def add_shields(self, amount: int) -> int:
        """增加当前护盾（不超过 max_shields）。返回实际增加的值。"""
        if amount <= 0:
            return 0
        old = self.current_shields
        self.current_shields = min(self.current_shields + amount, self.max_shields)
        return self.current_shields - old

    def add_gold(self, amount: int) -> int:
        """增加金币。若 has_clover 为 True，金币翻倍。

        Returns:
            实际增加的金币数额
        """
        if amount <= 0:
            return 0
        actual = amount * 2 if self.has_clover else amount
        self.gold += actual
        return actual

    def add_tool(self, tool_type: str, amount: int) -> bool:
        """添加指定工具。若添加后超过 max_capacity 则拒绝。

        Args:
            tool_type: 'pickaxe' / 'dynamite' / 'map'
            amount:    数量（必须为正）

        Returns:
            True = 添加成功，False = 溢出被拒绝
        """
        if amount <= 0:
            return False
        if tool_type not in self.tools:
            return False
        if self.total_tools() + amount > self.max_capacity():
            return False
        self.tools[tool_type] += amount
        return True

    def use_tool(self, tool_type: str, amount: int = 1) -> bool:
        """消耗工具。数量足够则扣除并返回 True，否则 False。"""
        if amount <= 0:
            return False
        if tool_type not in self.tools:
            return False
        if self.tools[tool_type] < amount:
            return False
        self.tools[tool_type] -= amount
        return True

    def add_key(self, color: str, amount: int = 1) -> None:
        """增加对应颜色钥匙的数量。"""
        if amount <= 0:
            return
        if color in self.keys:
            self.keys[color] += amount

    def use_key(self, color: str) -> bool:
        """消耗 1 把对应颜色钥匙。成功返回 True，不足返回 False。"""
        if color not in self.keys or self.keys[color] <= 0:
            return False
        self.keys[color] -= 1
        return True

    def buy_upgrade(self, upgrade_type: str) -> bool:
        """在商店购买永久升级。

        Args:
            upgrade_type: 'max_hearts' 或 'bag_capacity'

        Returns:
            True = 购买成功
            False = 余额不足 / 已达硬性上限 / 未知类型
        """
        if upgrade_type == "max_hearts":
            # 硬性上限检查
            if self.max_hearts >= HARD_CAP_HEARTS:
                return False
            price = HEART_UPGRADE_PRICES.get(self.max_hearts)
            if price is None or self.gold < price:
                return False
            self.gold -= price
            self.max_hearts += 1
            self.add_hearts(1)  # 升级时顺带补 1 点红心
            return True

        elif upgrade_type == "bag_capacity":
            # 硬性上限检查（最后一个索引）
            if self.bag_tier_index >= len(BAG_CAPACITY_TIERS) - 1:
                return False
            price = BAG_UPGRADE_PRICES.get(self.bag_tier_index)
            if price is None or self.gold < price:
                return False
            self.gold -= price
            self.bag_tier_index += 1
            return True

        else:
            return False

    def purge_temporary_items(self) -> None:
        """跨关卡重置临时道具：钥匙清零、柴刀/弓箭/四叶草移除。"""
        for color in self.keys:
            self.keys[color] = 0
        self.arrows = 0
        self.has_machete = False
        self.has_clover = False

    # =========================================================================
    # 局内快照（暂停菜单「重新开始本关」沙盒重置用）
    # =========================================================================

    def get_snapshot(self) -> dict:
        """打下当前局内消耗品/状态快照（不含永久属性）。

        用于暂停菜单「重新开始本关」精准还原玩家局内数据：
        - 包含所有局内变动消耗数据（红心、护盾、金币、工具、钥匙、弓箭、柴刀、四叶草、护身符）
        - 不含 max_hearts、bag_tier_index、生涯统计、max_shields 等全局永久属性

        Returns:
            包含全部局内可变字段的拷贝字典
        """
        return {
            "current_hearts": int(self.current_hearts),
            "current_shields": int(self.current_shields),
            "gold": int(self.gold),
            "tools": {
                "pickaxe": int(self.tools.get("pickaxe", 0)),
                "dynamite": int(self.tools.get("dynamite", 0)),
                "map": int(self.tools.get("map", 0)),
            },
            "keys": {
                "RED": int(self.keys.get("RED", 0)),
                "GREEN": int(self.keys.get("GREEN", 0)),
                "BLUE": int(self.keys.get("BLUE", 0)),
                "EXIT": int(self.keys.get("EXIT", 0)),
            },
            "arrows": int(self.arrows),
            "has_machete": bool(self.has_machete),
            "has_clover": bool(self.has_clover),
            "has_amulet": bool(self.has_amulet),
        }

    def load_snapshot(self, snapshot_dict: dict) -> None:
        """从快照字典还原全部局内可变字段（原地写回）。

        用于「重新开始本关」安全重置：先由调用方调用 load_snapshot
        还原玩家数据，再重载地图、重连控制器。

        Args:
            snapshot_dict: get_snapshot() 返回的字典
        """
        if not isinstance(snapshot_dict, dict):
            return

        # 红心 / 护盾 / 金币 / 弓箭
        self.current_hearts = int(snapshot_dict.get("current_hearts", self.current_hearts))
        self.current_shields = int(snapshot_dict.get("current_shields", self.current_shields))
        self.gold = int(snapshot_dict.get("gold", self.gold))
        self.arrows = int(snapshot_dict.get("arrows", self.arrows))

        # 工具（整体重建字典，避免旧引用残留）
        tools_raw = snapshot_dict.get("tools", {})
        self.tools = {
            "pickaxe": int(tools_raw.get("pickaxe", 0)),
            "dynamite": int(tools_raw.get("dynamite", 0)),
            "map": int(tools_raw.get("map", 0)),
        }

        # 钥匙（整体重建字典）
        keys_raw = snapshot_dict.get("keys", {})
        self.keys = {
            "RED": int(keys_raw.get("RED", 0)),
            "GREEN": int(keys_raw.get("GREEN", 0)),
            "BLUE": int(keys_raw.get("BLUE", 0)),
            "EXIT": int(keys_raw.get("EXIT", 0)),
        }

        # 布尔状态
        self.has_machete = bool(snapshot_dict.get("has_machete", self.has_machete))
        self.has_clover = bool(snapshot_dict.get("has_clover", self.has_clover))
        self.has_amulet = bool(snapshot_dict.get("has_amulet", self.has_amulet))
