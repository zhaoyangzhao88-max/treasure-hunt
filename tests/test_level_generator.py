"""LevelGenerator 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_level_generator.py` 直接运行。
验证参数随关卡缩放、雷区生成、锁钥依赖链与可解性求解器。
"""

import sys
import os
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.level_generator import LevelGenerator


def test_map_size_scaling():
    """验证地图尺寸随关卡线性增长，范围 [15, 40]。"""
    gen = LevelGenerator(seed=1)

    m1, _, _ = gen.generate_level(1)
    assert m1.width == 15 and m1.height == 15, f"Level 1 应为 15x15，得到 {m1.width}x{m1.height}"

    m5, _, _ = gen.generate_level(5)
    assert m5.width == 23 and m5.height == 23, f"Level 5 应为 23x23，得到 {m5.width}x{m5.height}"

    m10, _, _ = gen.generate_level(10)
    assert m10.width == 33 and m10.height == 33, f"Level 10 应为 33x33，得到 {m10.width}x{m10.height}"

    m13, _, _ = gen.generate_level(13)
    assert m13.width == 39 and m13.height == 39, f"Level 13 应为 39x39，得到 {m13.width}x{m13.height}"

    # 上限截断
    m20, _, _ = gen.generate_level(20)
    assert m20.width == 40 and m20.height == 40, f"Level 20 应为 40x40，得到 {m20.width}x{m20.height}"

    m50, _, _ = gen.generate_level(50)
    assert m50.width == 40 and m50.height == 40, f"Level 50 应截断到 40x40，得到 {m50.width}x{m50.height}"

    print("[PASS] test_map_size_scaling")


def test_trap_density_scaling():
    """验证高密度关卡陷阱更多。"""
    gen = LevelGenerator(seed=42)

    m1, _, _ = gen.generate_level(1)
    m10, _, _ = gen.generate_level(10)

    traps1 = sum(m1.traps[y][x] for y in range(m1.height) for x in range(m1.width))
    traps10 = sum(m10.traps[y][x] for y in range(m10.height) for x in range(m10.width))

    assert traps10 > traps1, f"Level 10 陷阱 ({traps10}) 应多于 Level 1 ({traps1})"

    # 验证 trap_density 上限
    m30, _, _ = gen.generate_level(30)
    total_cells = m30.width * m30.height
    traps30 = sum(m30.traps[y][x] for y in range(m30.height) for x in range(m30.width))
    density = traps30 / total_cells
    assert density < 0.25, f"Level 30 陷阱密度 ({density:.3f}) 应低于 0.25"

    print("[PASS] test_trap_density_scaling")


def test_start_safe_zone():
    """验证起点 3x3 安全区无雷。"""
    gen = LevelGenerator(seed=42)

    for level in [1, 5, 10]:
        m, start, _ = gen.generate_level(level)
        sx, sy = start
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = sx + dx, sy + dy
                if m.is_in_bounds(nx, ny):
                    assert not m.traps[ny][nx], \
                        f"Level {level} 起点安全区 ({nx},{ny}) 不应有雷"

    print("[PASS] test_start_safe_zone")


def test_exit_lock_placed():
    """验证终点有 LOCK_EXIT。"""
    gen = LevelGenerator(seed=1)

    for level in [1, 5, 10]:
        m, _, exit_ = gen.generate_level(level)
        assert m.layer1[exit_[1]][exit_[0]] == "LOCK_EXIT", \
            f"Level {level} 终点应为 LOCK_EXIT，得到 {m.layer1[exit_[1]][exit_[0]]}"

    print("[PASS] test_exit_lock_placed")


def test_start_is_uncovered():
    """验证起点已揭开。"""
    gen = LevelGenerator(seed=2)
    m, start, _ = gen.generate_level(1)
    assert m.layer0[start[1]][start[0]] == "UNCOVERED", \
        f"起点应为 UNCOVERED，得到 {m.layer0[start[1]][start[0]]}"

    print("[PASS] test_start_is_uncovered")


def test_key_exit_placed():
    """验证 KEY_EXIT 始终存在（解锁出口门）。"""
    gen = LevelGenerator(seed=42)

    for level in [1, 2, 3, 5, 10]:
        m, _, _ = gen.generate_level(level)
        found_key_exit = any(
            m.layer2[y][x] == "KEY_EXIT"
            for y in range(m.height)
            for x in range(m.width)
        )
        assert found_key_exit, f"Level {level} 应放置 KEY_EXIT"

    print("[PASS] test_key_exit_placed")


def test_key_red_placed_for_level_2_plus():
    """验证 level >= 2 时放置 LOCK_RED 和 KEY_RED。"""
    gen = LevelGenerator(seed=7)

    for level in [2, 3, 5, 10]:
        m, _, _ = gen.generate_level(level)
        found_lock = any(
            m.layer1[y][x] == "LOCK_RED"
            for y in range(m.height)
            for x in range(m.width)
        )
        found_key = any(
            m.layer2[y][x] == "KEY_RED"
            for y in range(m.height)
            for x in range(m.width)
        )
        assert found_lock, f"Level {level} 应放置 LOCK_RED"
        assert found_key, f"Level {level} 应放置 KEY_RED"

    print("[PASS] test_key_red_placed_for_level_2_plus")


def test_key_red_reachable_before_lock():
    """验证 KEY_RED 在 LOCK_RED 之前可达。"""
    gen = LevelGenerator(seed=42)

    for level in [2, 3, 5]:
        m, start, _ = gen.generate_level(level)

        # 找到 LOCK_RED 和 KEY_RED 的位置
        lock_pos = None
        key_pos = None
        for y in range(m.height):
            for x in range(m.width):
                if m.layer1[y][x] == "LOCK_RED":
                    lock_pos = (x, y)
                if m.layer2[y][x] == "KEY_RED":
                    key_pos = (x, y)

        assert lock_pos is not None, f"Level {level} 未找到 LOCK_RED"
        assert key_pos is not None, f"Level {level} 未找到 KEY_RED"

        # BFS 从起点出发，把 LOCK_RED 当作墙
        reachable = gen._bfs_reachable(m, start, blocked=lock_pos)
        assert key_pos in reachable, \
            f"Level {level} KEY_RED 应在 LOCK_RED 之前可达"

    print("[PASS] test_key_red_reachable_before_lock")


def test_verify_solvability_generated_levels():
    """验证生成的关卡通过求解器。"""
    for seed in [1, 2, 3, 4, 5, 42]:
        gen = LevelGenerator(seed=seed)
        for level in [1, 3, 5, 10]:
            m, start, exit_ = gen.generate_level(level)
            assert gen.verify_solvability(m, start, exit_), \
                f"seed={seed}, level={level} 应可解"

    print("[PASS] test_verify_solvability_generated_levels")


def test_verify_solvability_blocked_path():
    """验证求解器在路径被封锁时返回 False。"""
    gen = LevelGenerator(seed=42)
    m, start, exit_ = gen.generate_level(3)

    # 找到出口的一个可达邻居，用 WALL 封锁它
    # 封锁所有出口邻居
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = exit_[0] + dx, exit_[1] + dy
        if m.is_in_bounds(nx, ny) and m.layer1[ny][nx] == "NONE":
            m.layer1[ny][nx] = "WALL"

    # 求解器应返回 False
    assert not gen.verify_solvability(m, start, exit_), \
        "封锁出口后应不可解"

    print("[PASS] test_verify_solvability_blocked_path")


def test_determinism():
    """验证相同种子生成相同地图。"""
    for seed in [1, 42, 100]:
        gen1 = LevelGenerator(seed=seed)
        gen2 = LevelGenerator(seed=seed)
        m1, s1, e1 = gen1.generate_level(5)
        m2, s2, e2 = gen2.generate_level(5)

        assert s1 == s2, "起点应相同"
        assert e1 == e2, "终点应相同"
        assert m1.layer1 == m2.layer1, "layer1 应相同"
        assert m1.layer2 == m2.layer2, "layer2 应相同"
        assert m1.traps == m2.traps, "traps 应相同"

    print("[PASS] test_determinism")


def test_entities_scattered():
    """验证道具散落（新版 LootTable 动态散布）。"""
    gen = LevelGenerator(seed=9)
    m, _, _ = gen.generate_level(5)

    entities = {
        m.layer2[y][x]
        for y in range(m.height)
        for x in range(m.width)
        if m.layer2[y][x] != "NONE"
    }

    assert "MACHETE" in entities, "应有 MACHETE（硬编码保障）"
    assert "ARROW" in entities, "应有 ARROW（5% 通路保障）"
    # 通用道具由 LootTable 动态决定，应至少出现 COIN 或 GEM 之一
    has_loot = "COIN" in entities or "GEM" in entities
    assert has_loot, "应至少出现 COIN 或 GEM（LootTable 通用槽位）"
    # 宝箱散布（level >= 2 可能生成 LOCKED_CHEST）
    assert "CHEST" in entities, "应有 CHEST（死胡同宝箱）"

    print("[PASS] test_entities_scattered")


def test_different_seeds_different_maps():
    """验证不同种子生成不同地图。"""
    gen1 = LevelGenerator(seed=100)
    gen2 = LevelGenerator(seed=200)
    m1, _, _ = gen1.generate_level(5)
    m2, _, _ = gen2.generate_level(5)

    different = (
        m1.layer1 != m2.layer1
        or m1.layer2 != m2.layer2
        or m1.traps != m2.traps
    )
    assert different, "不同种子应生成不同地图"

    print("[PASS] test_different_seeds_different_maps")


def test_minimum_grid_15x15():
    """验证 level 1 精确为 15x15。"""
    gen = LevelGenerator(seed=10)
    m, start, exit_ = gen.generate_level(1)
    assert m.width == 15 and m.height == 15
    assert start == (1, 1)
    assert exit_ == (13, 13)
    assert gen.verify_solvability(m, start, exit_)

    print("[PASS] test_minimum_grid_15x15")


def test_large_grid_solvable():
    """验证 level 20 (40x40) 可生成且可解。"""
    gen = LevelGenerator(seed=11)
    m, start, exit_ = gen.generate_level(20)
    assert m.width == 40 and m.height == 40
    assert gen.verify_solvability(m, start, exit_)

    print("[PASS] test_large_grid_solvable")


def test_key_exit_reachable():
    """验证 KEY_EXIT 从起点可达（不被 LOCK_RED 阻挡）。"""
    gen = LevelGenerator(seed=42)

    for level in [1, 2, 3, 5]:
        m, start, _ = gen.generate_level(level)

        # 找到 KEY_EXIT
        key_exit_pos = None
        for y in range(m.height):
            for x in range(m.width):
                if m.layer2[y][x] == "KEY_EXIT":
                    key_exit_pos = (x, y)
                    break
            if key_exit_pos:
                break

        assert key_exit_pos is not None, f"Level {level} 未找到 KEY_EXIT"

        # 找到 LOCK_RED（如果存在）
        lock_red_pos = None
        for y in range(m.height):
            for x in range(m.width):
                if m.layer1[y][x] == "LOCK_RED":
                    lock_red_pos = (x, y)
                    break
            if lock_red_pos:
                break

        # BFS 从起点，把 LOCK_RED 当作墙
        blocked = lock_red_pos if lock_red_pos else (-1, -1)
        reachable = gen._bfs_reachable(m, start, blocked=blocked)
        assert key_exit_pos in reachable, \
            f"Level {level} KEY_EXIT 应在锁门之前可达"

    print("[PASS] test_key_exit_reachable")


if __name__ == "__main__":
    test_map_size_scaling()
    test_trap_density_scaling()
    test_start_safe_zone()
    test_exit_lock_placed()
    test_start_is_uncovered()
    test_key_exit_placed()
    test_key_red_placed_for_level_2_plus()
    test_key_red_reachable_before_lock()
    test_verify_solvability_generated_levels()
    test_verify_solvability_blocked_path()
    test_determinism()
    test_entities_scattered()
    test_different_seeds_different_maps()
    test_minimum_grid_15x15()
    test_large_grid_solvable()
    test_key_exit_reachable()
    print("\n=== ALL TESTS PASSED ===")
