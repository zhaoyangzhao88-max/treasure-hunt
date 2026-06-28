"""PlayerState 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_player_state.py` 直接运行。
"""

import sys
import os

# 确保能找到 src/ 模块（当从项目根目录运行时）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.player_state import PlayerState


def test_initial_state():
    """验证 __init__ 初始值"""
    p = PlayerState()
    assert p.current_hearts == 3, f"初始红心应为 3，得到 {p.current_hearts}"
    assert p.max_hearts == 3, f"初始 max_hearts 应为 3，得到 {p.max_hearts}"
    assert p.current_shields == 0, f"初始护盾应为 0，得到 {p.current_shields}"
    assert p.max_shields == 1, f"初始 max_shields 应为 1，得到 {p.max_shields}"
    assert p.gold == 0, f"初始金币应为 0，得到 {p.gold}"
    assert p.total_tools() == 0, f"初始工具总数应为 0，得到 {p.total_tools()}"
    assert p.max_capacity() == 2, f"初始容量上限应为 2，得到 {p.max_capacity()}"
    assert p.bag_tier_index == 0
    assert all(v == 0 for v in p.keys.values()), "初始钥匙应全为 0"
    assert p.arrows == 0
    assert p.has_machete is False
    assert p.has_amulet is False
    assert p.has_clover is False
    print("[PASS] test_initial_state")


def test_gold_pickup():
    """验证金币拾取 + clover 翻倍效果"""
    p = PlayerState()
    added = p.add_gold(100)
    assert added == 100, f"无 clover 时应增加 100，得到 {added}"
    assert p.gold == 100

    # 激活 clover 后再捡
    p.has_clover = True
    added = p.add_gold(50)
    assert added == 100, f"有 clover 时 50 应翻倍为 100，得到 {added}"
    assert p.gold == 200, f"总金币应为 200，得到 {p.gold}"
    print("[PASS] test_gold_pickup")


def test_tools_add_and_use():
    """验证工具拾取与使用"""
    p = PlayerState()
    assert p.add_tool("pickaxe", 1) is True
    assert p.add_tool("dynamite", 1) is True
    assert p.total_tools() == 2

    # 使用工具
    assert p.use_tool("pickaxe", 1) is True
    assert p.tools["pickaxe"] == 0
    assert p.total_tools() == 1

    # 使用不存在的工具应失败
    assert p.use_tool("map", 1) is False
    assert p.use_tool("pickaxe", 5) is False  # 数量不足
    print("[PASS] test_tools_add_and_use")


def test_bag_overflow():
    """验证背包溢出拒绝（初始容量 2）"""
    p = PlayerState()
    assert p.max_capacity() == 2
    assert p.add_tool("pickaxe", 1) is True
    assert p.add_tool("dynamite", 1) is True
    assert p.total_tools() == 2

    # 已满，再加应失败
    assert p.add_tool("map", 1) is False
    assert p.total_tools() == 2  # 未变化
    print("[PASS] test_bag_overflow")


def test_damage_and_death():
    """验证伤害吸收：护盾优先 → 红心扣减 → 死亡判定"""
    p = PlayerState()
    # 给 1 护盾
    p.add_shields(1)
    assert p.current_shields == 1

    # 受 1 伤害 → 护盾吸收
    alive = p.apply_damage(1)
    assert alive is True
    assert p.current_shields == 0, "护盾应被消耗"
    assert p.current_hearts == 3, "红心不变"

    # 再受 2 伤害 → 直接扣红心
    alive = p.apply_damage(2)
    assert alive is True
    assert p.current_hearts == 1

    # 再受 2 伤害 → 红心归零，死亡
    alive = p.apply_damage(2)
    assert alive is False, "应判定死亡"
    assert p.current_hearts == 0
    print("[PASS] test_damage_and_death")


def test_purge_temporary_items():
    """验证跨关重置临时道具"""
    p = PlayerState()
    # 给玩家一些临时道具
    p.add_key("RED", 3)
    p.add_key("BLUE", 1)
    p.arrows = 5
    p.has_machete = True
    p.has_clover = True

    # 重置
    p.purge_temporary_items()
    assert p.keys["RED"] == 0
    assert p.keys["BLUE"] == 0
    assert p.arrows == 0
    assert p.has_machete is False
    assert p.has_clover is False
    # 永久属性不应受影响
    assert p.max_hearts == 3
    assert p.gold == 0
    print("[PASS] test_purge_temporary_items")


def test_buy_upgrade_max_hearts():
    """验证购买生命上限升级"""
    p = PlayerState()
    p.gold = 1000  # 足够买一次

    old_max = p.max_hearts
    success = p.buy_upgrade("max_hearts")
    assert success is True, "应有足够金币购买"
    assert p.max_hearts == old_max + 1, "max_hearts 应增加 1"
    assert p.current_hearts == old_max + 1 or p.current_hearts == old_max
    # 注意：max_hearts 变为 4，add_hearts(1) → current = 4
    assert p.current_hearts == 4

    # 验证金币扣除
    assert p.gold == 1000 - 200, f"应扣除 200，剩余 {p.gold}"

    # 测试达到硬上限后拒绝
    p.gold = 99999
    p.max_hearts = 8
    p.current_hearts = 8
    success = p.buy_upgrade("max_hearts")
    assert success is False, "已达 HARD_CAP 应拒绝"

    # 测试余额不足
    p.max_hearts = 3
    p.gold = 100  # HEART_UPGRADE_PRICES[3] = 200
    success = p.buy_upgrade("max_hearts")
    assert success is False, "余额不足应拒绝"
    print("[PASS] test_buy_upgrade_max_hearts")


def test_buy_upgrade_bag_capacity():
    """验证购买背包扩容升级"""
    p = PlayerState()
    p.gold = 500

    old_tier = p.bag_tier_index
    success = p.buy_upgrade("bag_capacity")
    assert success is True, "应有足够金币扩容"
    assert p.bag_tier_index == old_tier + 1, "容量索引应增加 1"
    assert p.max_capacity() == 4, "扩容后容量上限应为 4"
    assert p.gold == 500 - 100, f"应扣除 100，剩余 {p.gold}"

    # 测试达到最高阶梯后拒绝
    p.gold = 99999
    p.bag_tier_index = 8  # 最大索引 = len(BAG_CAPACITY_TIERS)-1
    success = p.buy_upgrade("bag_capacity")
    assert success is False, "已达最高阶梯应拒绝"
    print("[PASS] test_buy_upgrade_bag_capacity")


def test_use_key():
    """验证钥匙使用逻辑"""
    p = PlayerState()
    p.add_key("RED", 2)
    assert p.keys["RED"] == 2

    assert p.use_key("RED") is True
    assert p.keys["RED"] == 1

    assert p.use_key("RED") is True
    assert p.keys["RED"] == 0

    # 不足应失败
    assert p.use_key("RED") is False
    # 未拥有的颜色
    assert p.use_key("GREEN") is False
    print("[PASS] test_use_key")


if __name__ == "__main__":
    test_initial_state()
    test_gold_pickup()
    test_tools_add_and_use()
    test_bag_overflow()
    test_damage_and_death()
    test_purge_temporary_items()
    test_buy_upgrade_max_hearts()
    test_buy_upgrade_bag_capacity()
    test_use_key()
    print("\n=== ALL TESTS PASSED ===")
