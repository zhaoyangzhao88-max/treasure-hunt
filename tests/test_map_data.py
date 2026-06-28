"""GameMap 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_map_data.py` 直接运行。
使用 10x10 地图验证越界、雷数、通行、揭开、旗帜等机制。
"""

import sys
import os

# 确保能找到 src/ 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.map_data import GameMap


def test_bounds_check():
    """验证 is_in_bounds 越界返回 False"""
    m = GameMap(10, 10)

    # 越界：x 超出宽度
    assert m.is_in_bounds(10, 5) is False, "x=10 应越界（width=10，有效 0-9）"
    # 越界：x 为负
    assert m.is_in_bounds(-1, 0) is False, "x=-1 应越界"
    # 越界：y 超出高度
    assert m.is_in_bounds(0, 10) is False, "y=10 应越界"
    # 越界：y 为负
    assert m.is_in_bounds(0, -1) is False, "y=-1 应越界"
    # 合法坐标
    assert m.is_in_bounds(0, 0) is True
    assert m.is_in_bounds(9, 9) is True
    assert m.is_in_bounds(5, 5) is True

    print("[PASS] test_bounds_check")


def test_adjacent_traps_count():
    """验证 8 邻域陷阱计数（手动布雷）"""
    m = GameMap(10, 10)

    # 在 (1,1)、(2,2)、(3,3) 三个对角位置布雷
    m.traps[1][1] = True
    m.traps[2][2] = True
    m.traps[3][3] = True

    # (2,1) 的邻居：(1,0)(2,0)(3,0)(1,1)(3,1)(1,2)(2,2)(3,2)
    # 其中 traps=True 的有 (1,1) 和 (2,2) → count=2
    count = m.get_adjacent_traps_count(2, 1)
    assert count == 2, f"(2,1) 邻域雷数应为 2，得到 {count}"

    # (2,2) 的邻居：(1,1)(2,1)(3,1)(1,2)(3,2)(1,3)(2,3)(3,3)
    # 其中 traps=True 的有 (1,1) 和 (3,3) → count=2（(2,2) 自身不算）
    count = m.get_adjacent_traps_count(2, 2)
    assert count == 2, f"(2,2) 邻域雷数应为 2，得到 {count}"

    # (0,0) 角点只有 3 个邻居：(1,0)(0,1)(1,1)，仅 (1,1) 是陷阱 → count=1
    count = m.get_adjacent_traps_count(0, 0)
    assert count == 1, f"(0,0) 邻域雷数应为 1，得到 {count}"

    print("[PASS] test_adjacent_traps_count")


def test_walkable():
    """验证通行判定"""
    m = GameMap(10, 10)

    # 默认 DIRT → 不可通行
    assert m.is_walkable(0, 0) is False, "DIRT 格子不应可通行"

    # 揭开 → 可通行
    assert m.uncover_tile(0, 0) is True
    assert m.is_walkable(0, 0) is True, "揭开后应可通行"

    # 放墙 → 再次不可通行
    m.set_obstacle(0, 0, "WALL")
    assert m.is_walkable(0, 0) is False, "WALL 格不应可通行"

    # 障碍移除 → 恢复通行
    m.set_obstacle(0, 0, "NONE")
    assert m.is_walkable(0, 0) is True, "移除障碍后应恢复通行"

    # 越界 → False
    assert m.is_walkable(-1, 0) is False
    assert m.is_walkable(10, 0) is False

    print("[PASS] test_walkable")


def test_flag_and_uncover_interaction():
    """验证插旗与揭开的交互约束"""
    m = GameMap(10, 10)

    # DIRT 上插旗 → flags=True
    result = m.toggle_flag(3, 3)
    assert result is True, f"DIRT 插旗应返回 True，得到 {result}"
    assert m.flags[3][3] is True, "flags[3][3] 应为 True"

    # 再次 toggle → flags=False
    result = m.toggle_flag(3, 3)
    assert result is False, "取消旗帜应返回 False"
    assert m.flags[3][3] is False

    # 插旗后无法揭开
    m.toggle_flag(5, 5)
    assert m.flags[5][5] is True
    result = m.uncover_tile(5, 5)
    assert result is False, "已 flag 的格子不应能被揭开"
    assert m.layer0[5][5] == "DIRT", "flagged 格子不应被揭开"

    # 已揭开的格子无法 flag
    m.uncover_tile(7, 7)
    assert m.layer0[7][7] == "UNCOVERED"
    result = m.toggle_flag(7, 7)
    assert result is False, "已揭开格子不应能 flag"
    assert m.flags[7][7] is False, "已揭开格子 flag 应为 False"

    # 已揭开的格子再次 uncover 应返回 False（非 DIRT）
    result = m.uncover_tile(7, 7)
    assert result is False, "已揭开格子再次 uncover 应返回 False"

    print("[PASS] test_flag_and_uncover_interaction")


def test_set_obstacle_and_entity():
    """验证辅助赋值方法与越界静默"""
    m = GameMap(10, 10)

    m.set_obstacle(2, 3, "WALL")
    assert m.layer1[3][2] == "WALL"

    m.set_entity(4, 5, "GOLD")
    assert m.layer2[5][4] == "GOLD"

    # 越界静默
    m.set_obstacle(-1, 0, "WALL")  # 不应抛异常
    m.set_entity(10, 10, "GOLD")
    assert m.is_in_bounds(-1, 0) is False
    assert m.is_in_bounds(10, 10) is False

    # 修改陷阱
    m.traps[0][0] = True
    assert m.traps[0][0] is True

    print("[PASS] test_set_obstacle_and_entity")


if __name__ == "__main__":
    test_bounds_check()
    test_adjacent_traps_count()
    test_walkable()
    test_flag_and_uncover_interaction()
    test_set_obstacle_and_entity()
    print("\n=== ALL TESTS PASSED ===")
