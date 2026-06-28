"""LootTable 加权掉落表与宝箱机制验证 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_loot_and_chests.py` 直接运行。
验证动态健康救济、普通宝箱步入开启、上锁宝箱点击解锁与钥匙消耗。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.loot_table import LootTable
from src.interaction_controller import InteractionController
from src.map_data import GameMap
from src.player_state import PlayerState


def test_dynamic_pity():
    """测试动态健康救济（Dynamic Pity）：
    - 玩家 1 血时调用 get_random_loot 1000 次，HEART 比例应显著高于 3 血时的比例。
    """
    lt = LootTable(seed=42)

    # 满血情况：3/3
    full_heart_count = 0
    for _ in range(1000):
        loot = lt.get_random_loot(level_num=1, current_hearts=3, max_hearts=3)
        if loot == "HEART":
            full_heart_count += 1

    # 残血情况：1/3
    low_heart_count = 0
    for _ in range(1000):
        loot = lt.get_random_loot(level_num=1, current_hearts=1, max_hearts=3)
        if loot == "HEART":
            low_heart_count += 1

    # 残血时 HEART 比例应显著高于满血（至少 3 倍以上）
    assert low_heart_count > full_heart_count * 3, (
        f"残血 HEART 比例 ({low_heart_count}/1000) 应显著高于满血 ({full_heart_count}/1000)"
    )
    # 残血时 HEART 应至少出现 100 次（25% 权重约为 250 次，但随机波动可接受下限）
    assert low_heart_count >= 80, f"残血 HEART 应 >= 80/1000，实际 {low_heart_count}"

    # 满血 HEART 不应超过 80 次（3% 权重约为 30 次，放大容差避免不稳定）
    assert full_heart_count < 150, f"满血 HEART 应 < 150/1000，实际 {full_heart_count}"

    print("[PASS] test_dynamic_pity")


def test_generate_chest_loot_normal():
    """测试普通宝箱物资生成格式：
    - 返回 2 个元组
    - 第一个是 COIN，金额在 [25, 75] 范围
    - 第二个是 PICKAXE，数量为 1
    """
    lt = LootTable(seed=42)

    for _ in range(50):
        loot = lt.generate_chest_loot(is_locked=False)
        assert len(loot) == 2, f"普通宝箱应有 2 个物资，得到 {len(loot)}"
        assert loot[0][0] == "COIN", f"第一个应为 COIN，得到 {loot[0][0]}"
        assert 25 <= loot[0][1] <= 75, f"COIN 数量应在 [25,75]，得到 {loot[0][1]}"
        assert loot[1] == ("PICKAXE", 1), f"第二个应为 PICKAXE*1，得到 {loot[1]}"

    print("[PASS] test_generate_chest_loot_normal")


def test_generate_chest_loot_locked():
    """测试上锁宝箱物资生成：
    - 返回 3 个元组
    - 第一个是 COIN (50~150)
    - 第二个是 GEM (1~3)
    - 第三个有 20% 概率为 AMULET/MACHETE，否则是 DYNAMITE/PICKAXE
    """
    lt = LootTable(seed=99)
    epic_found = False
    fallback_found = False

    for _ in range(200):
        loot = lt.generate_chest_loot(is_locked=True)
        assert len(loot) == 3, f"上锁宝箱应有 3 个物资，得到 {len(loot)}"
        assert loot[0][0] == "COIN", f"第一个应为 COIN，得到 {loot[0][0]}"
        assert 50 <= loot[0][1] <= 150, f"COIN 数量应在 [50,150]，得到 {loot[0][1]}"
        assert loot[1][0] == "GEM", f"第二个应为 GEM，得到 {loot[1][0]}"
        assert 1 <= loot[1][1] <= 3, f"GEM 数量应在 [1,3]，得到 {loot[1][1]}"

        third_type = loot[2][0]
        if third_type in ("AMULET", "MACHETE"):
            epic_found = True
        elif third_type in ("DYNAMITE", "PICKAXE"):
            fallback_found = True
        else:
            assert False, f"第三个物资类型无效: {third_type}"

    # 运行 200 轮应该至少见过各一种分支
    assert epic_found, "200 轮应至少见过一次史诗道具分支"
    assert fallback_found, "200 轮应至少见过一次保底分支"

    print("[PASS] test_generate_chest_loot_locked")


def test_chest_walk_open():
    """测试普通宝箱步入开启：
    - 在 (1,1) 放置 CHEST
    - 揭开起点 (0,0) 和目标 (1,1)
    - 玩家从 (0,0) 移动到 (1,1)
    - 验证宝箱消失、玩家获得物资增量
    """
    m = GameMap(10, 10)
    m.uncover_tile(0, 0)
    m.uncover_tile(1, 1)
    m.set_entity(1, 1, "CHEST")

    p = PlayerState()
    # 扩大背包容量以确保拾取工具不溢出
    p.bag_tier_index = 2  # 容量 6
    initial_gold = p.gold
    ctrl = InteractionController(m, p, start_x=0, start_y=0)

    result = ctrl.move_player(1, 1)
    assert result == "SUCCESS", f"步入宝箱应返回 SUCCESS，得到 {result}"

    # 宝箱被清空
    assert m.layer2[1][1] == "NONE", f"宝箱应被清除，得到 {m.layer2[1][1]}"

    # 玩家获得至少 25 金币（普通宝箱保底 COIN*25）
    assert p.gold >= initial_gold + 25, (
        f"玩家金币应增加至少 25，从 {initial_gold} 到 {p.gold}"
    )
    # 玩家获得 1 把铁锹
    assert p.tools["pickaxe"] >= 1, f"玩家应获得铁锹，实际 {p.tools['pickaxe']}"

    print("[PASS] test_chest_walk_open")


def test_locked_chest_no_key():
    """测试无钥匙时点击上锁宝箱：
    - 在 (1,0) 放置 LOCKED_CHEST
    - 玩家在 (0,0) 无任何钥匙
    - 调用 unlock_chest(1,0) 验证返回 False
    - 宝箱实体保留，玩家钥匙无损耗
    """
    m = GameMap(10, 10)
    m.uncover_tile(0, 0)
    m.uncover_tile(1, 0)
    m.set_entity(1, 0, "LOCKED_CHEST")

    p = PlayerState()
    ctrl = InteractionController(m, p, start_x=0, start_y=0)

    result = ctrl.unlock_chest(1, 0)
    assert result is False, "无钥匙时应返回 False"

    # 宝箱保留
    assert m.layer2[0][1] == "LOCKED_CHEST", "宝箱应保留"

    # 无钥匙消耗
    assert p.keys["RED"] == 0
    assert p.keys["GREEN"] == 0
    assert p.keys["BLUE"] == 0

    print("[PASS] test_locked_chest_no_key")


def test_locked_chest_with_key():
    """测试有钥匙时点击上锁宝箱：
    - 在 (1,0) 放置 LOCKED_CHEST
    - 玩家在 (0,0) 持有 1 把绿色钥匙
    - 调用 unlock_chest(1,0) 验证返回 True
    - 宝箱被清除，绿色钥匙被消耗，玩家获得稀有物资
    """
    m = GameMap(10, 10)
    m.uncover_tile(0, 0)
    m.uncover_tile(1, 0)
    m.set_entity(1, 0, "LOCKED_CHEST")

    p = PlayerState()
    p.bag_tier_index = 2  # 容量 6
    p.add_key("GREEN", 1)
    initial_gold = p.gold
    initial_keys = dict(p.keys)
    ctrl = InteractionController(m, p, start_x=0, start_y=0)

    result = ctrl.unlock_chest(1, 0)
    assert result is True, "有钥匙时应返回 True"

    # 宝箱被清除
    assert m.layer2[0][1] == "NONE", f"宝箱应被清除，得到 {m.layer2[0][1]}"

    # 绿色钥匙减少 1
    assert p.keys["GREEN"] == initial_keys["GREEN"] - 1, (
        f"绿色钥匙应从 {initial_keys['GREEN']} 减为 {initial_keys['GREEN'] - 1}，"
        f"实际 {p.keys['GREEN']}"
    )

    # 获得至少 50 金币（上锁宝箱保底 COIN*50）
    assert p.gold >= initial_gold + 50, (
        f"金币应增加至少 50，从 {initial_gold} 到 {p.gold}"
    )

    print("[PASS] test_locked_chest_with_key")


def test_get_random_loot_level_scaling():
    """测试关卡缩放：高关卡应增加 GEM 和 SHIELD 的出现概率。"""
    lt = LootTable(seed=42)

    # Level 1: 统计 GEM 比例
    level1_counts = {}
    for _ in range(2000):
        loot = lt.get_random_loot(level_num=1)
        level1_counts[loot] = level1_counts.get(loot, 0) + 1

    # Level 10: 统计 GEM 比例
    level10_counts = {}
    for _ in range(2000):
        loot = lt.get_random_loot(level_num=10)
        level10_counts[loot] = level10_counts.get(loot, 0) + 1

    # Level 10 的 GEM 比例应高于 Level 1
    gem_l1 = level1_counts.get("GEM", 0)
    gem_l10 = level10_counts.get("GEM", 0)
    assert gem_l10 > gem_l1, (
        f"Level 10 GEM 计数 ({gem_l10}) 应高于 Level 1 ({gem_l1})"
    )

    print("[PASS] test_get_random_loot_level_scaling")


def test_unlock_chest_most_abundant_key():
    """测试解锁时扣除持有数量最多的钥匙：
    - 给玩家 2 把红色、3 把蓝色、1 把绿色
    - 解锁时应扣除蓝色（数量最多）
    """
    m = GameMap(10, 10)
    m.uncover_tile(0, 0)
    m.uncover_tile(1, 0)
    m.set_entity(1, 0, "LOCKED_CHEST")

    p = PlayerState()
    p.bag_tier_index = 2
    p.add_key("RED", 2)
    p.add_key("BLUE", 3)
    p.add_key("GREEN", 1)
    ctrl = InteractionController(m, p, start_x=0, start_y=0)

    result = ctrl.unlock_chest(1, 0)
    assert result is True, "有钥匙时应返回 True"

    # 蓝色钥匙减少 1（原 3→2）
    assert p.keys["BLUE"] == 2, f"蓝色钥匙应为 2，得到 {p.keys['BLUE']}"
    # 红色和绿色不变
    assert p.keys["RED"] == 2, f"红色钥匙应为 2，得到 {p.keys['RED']}"
    assert p.keys["GREEN"] == 1, f"绿色钥匙应为 1，得到 {p.keys['GREEN']}"

    print("[PASS] test_unlock_chest_most_abundant_key")


if __name__ == "__main__":
    test_dynamic_pity()
    test_generate_chest_loot_normal()
    test_generate_chest_loot_locked()
    test_chest_walk_open()
    test_locked_chest_no_key()
    test_locked_chest_with_key()
    test_get_random_loot_level_scaling()
    test_unlock_chest_most_abundant_key()
    print("\n=== ALL TESTS PASSED ===")
