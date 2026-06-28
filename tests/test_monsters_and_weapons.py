"""第 28 课：怪物、武器收集与多级战斗判定 — 单元测试

覆盖范围：
- 武器拾取（弓箭上限、柴刀激活）
- 多级战斗判定（柴刀击杀、弓箭击杀、无武器扣血）
- move_player 战斗返回信号
- 跨关临时道具清空（purge_temporary_items）
- 关卡生成散布验证（怪物、弓箭、柴刀存在性）
"""

import os
import sys

# 将项目根目录加入 sys.path，保证直接运行时能正确导入
_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from src.map_data import GameMap
from src.player_state import PlayerState
from src.interaction_controller import InteractionController
from src.level_generator import LevelGenerator


# =========================================================================
# 辅助函数
# =========================================================================

def _make_walkable(gm: GameMap, tiles: list[tuple[int, int]]) -> None:
    """将指定格子设为可通行（UNCOVERED 地形 + NONE 障碍）。"""
    for x, y in tiles:
        gm.layer0[y][x] = "UNCOVERED"
        gm.layer1[y][x] = "NONE"


def _set_player_start(ctrl: InteractionController, x: int, y: int) -> None:
    """设置玩家初始位置并确保该格可通行。"""
    _make_walkable(ctrl.game_map, [(x, y)])
    ctrl.player_x = x
    ctrl.player_y = y


# =========================================================================
# 测试 1：武器拾取与上限
# =========================================================================

def test_arrow_pickup_and_cap():
    """玩家踩中 ARROW 累加数量，上限 9。"""
    gm = GameMap(15, 15)
    p = PlayerState()
    ctrl = InteractionController(gm, p, start_x=1, start_y=1)
    _set_player_start(ctrl, 1, 1)

    # 在 (2,1) 放置一支箭并步行走过去
    gm.set_entity(2, 1, "ARROW")
    _make_walkable(gm, [(2, 1)])
    result = ctrl.move_player(2, 1)
    assert result == "SUCCESS", f"移动失败: {result}"
    assert p.arrows == 1, f"弓箭数量应为 1，实际为 {p.arrows}"
    assert gm.layer2[1][2] == "NONE", "弓箭格应被清空"

    # 连续在右侧放置更多箭并逐一拾取，验证上限 9
    p.arrows = 0  # 重置计数
    for i in range(3, 12):
        gm.set_entity(i, 1, "ARROW")
        _make_walkable(gm, [(i, 1)])

    for i in range(3, 12):
        result = ctrl.move_player(i, 1)
        assert result == "SUCCESS", f"第 {i} 步移动失败: {result}"

    assert p.arrows == 9, f"弓箭上限应为 9，实际为 {p.arrows}"
    print("  [PASS] test_arrow_pickup_and_cap")


def test_machete_pickup():
    """玩家踩中 MACHETE 激活柴刀。"""
    gm = GameMap(10, 10)
    p = PlayerState()
    ctrl = InteractionController(gm, p, start_x=1, start_y=1)
    _set_player_start(ctrl, 1, 1)

    gm.set_entity(2, 1, "MACHETE")
    _make_walkable(gm, [(2, 1)])
    result = ctrl.move_player(2, 1)
    assert result == "SUCCESS", f"移动失败: {result}"
    assert p.has_machete is True, "应获得柴刀"
    assert gm.layer2[1][2] == "NONE", "柴刀格应被清空"
    print("  [PASS] test_machete_pickup")


# =========================================================================
# 测试 2：多级战斗判定
# =========================================================================

def _setup_combat_scenario(has_machete: bool = False, arrows: int = 0):
    """创建战斗测试场景：玩家在 (1,1)，怪物在 (2,1)。"""
    gm = GameMap(10, 10)
    p = PlayerState()
    p.has_machete = has_machete
    p.arrows = arrows
    p.current_hearts = 3
    p.current_shields = 0
    ctrl = InteractionController(gm, p, start_x=1, start_y=1)
    _set_player_start(ctrl, 1, 1)

    # 放置怪物
    gm.set_entity(2, 1, "MONSTER")
    _make_walkable(gm, [(2, 1)])

    return gm, p, ctrl


def test_combat_machete_kill():
    """柴刀击杀：怪物消灭，柴刀不消耗，红心无损。"""
    gm, p, ctrl = _setup_combat_scenario(has_machete=True, arrows=0)
    initial_hearts = p.current_hearts
    initial_arrows = p.arrows

    result = ctrl.attack_monster(2, 1)
    assert result is True, "柴刀击杀应返回 True"
    assert gm.layer2[1][2] == "NONE", "怪物应被消灭"
    assert p.current_hearts == initial_hearts, "柴刀击杀不应扣血"
    assert p.arrows == initial_arrows, "柴刀击杀不应消耗弓箭"
    assert p.has_machete is True, "柴刀不应被消耗"
    print("  [PASS] test_combat_machete_kill")


def test_combat_arrow_kill():
    """弓箭击杀：怪物消灭，弓箭减少，红心无损。"""
    gm, p, ctrl = _setup_combat_scenario(has_machete=False, arrows=2)
    initial_hearts = p.current_hearts

    result = ctrl.attack_monster(2, 1)
    assert result is True, "弓箭击杀应返回 True"
    assert gm.layer2[1][2] == "NONE", "怪物应被消灭"
    assert p.arrows == 1, f"弓箭应消耗为 1，实际为 {p.arrows}"
    assert p.current_hearts == initial_hearts, "弓箭击杀不应扣血"
    print("  [PASS] test_combat_arrow_kill")


def test_combat_unarmed_damage():
    """无武器硬推：扣血，怪物保留。"""
    gm, p, ctrl = _setup_combat_scenario(has_machete=False, arrows=0)
    initial_hearts = 3

    result = ctrl.attack_monster(2, 1)
    assert result is False, "无武器应返回 False"
    assert gm.layer2[1][2] == "MONSTER", "怪物应保留"
    assert p.current_hearts == initial_hearts - 1, f"应扣除 1 心，实际剩余 {p.current_hearts}"
    print("  [PASS] test_combat_unarmed_damage")


def test_combat_move_player_machete():
    """move_player 遇到怪物时触发柴刀战斗，返回 MONSTER_KILLED。"""
    gm, p, ctrl = _setup_combat_scenario(has_machete=True, arrows=0)
    initial_hearts = p.current_hearts

    result = ctrl.move_player(2, 1)
    assert result == "MONSTER_KILLED", f"应返回 MONSTER_KILLED，实际为 {result}"
    assert gm.layer2[1][2] == "NONE", "怪物应被消灭"
    assert ctrl.player_x == 1 and ctrl.player_y == 1, "玩家不应移动"
    assert p.current_hearts == initial_hearts, "不应扣血"
    print("  [PASS] test_combat_move_player_machete")


def test_combat_move_player_unarmed():
    """move_player 遇到怪物时触发无武器战斗，返回 MONSTER_DAMAGED_PLAYER。"""
    gm, p, ctrl = _setup_combat_scenario(has_machete=False, arrows=0)
    initial_hearts = 3

    result = ctrl.move_player(2, 1)
    assert result == "MONSTER_DAMAGED_PLAYER", f"应返回 MONSTER_DAMAGED_PLAYER，实际为 {result}"
    assert gm.layer2[1][2] == "MONSTER", "怪物应保留"
    assert ctrl.player_x == 1 and ctrl.player_y == 1, "玩家不应移动"
    assert p.current_hearts == initial_hearts - 1, "应扣血"
    print("  [PASS] test_combat_move_player_unarmed")


def test_combat_not_adjacent():
    """攻击非相邻怪物应返回 False。"""
    gm, p, ctrl = _setup_combat_scenario(has_machete=True)
    # 玩家在 (1,1)，怪物在 (5,5)，不相邻
    gm.set_entity(5, 5, "MONSTER")
    result = ctrl.attack_monster(5, 5)
    assert result is False, "非相邻攻击应返回 False"
    assert gm.layer2[5][5] == "MONSTER", "非相邻怪物应保留"
    print("  [PASS] test_combat_not_adjacent")


def test_combat_not_monster():
    """攻击非怪物格应返回 False。"""
    gm, p, ctrl = _setup_combat_scenario(has_machete=True)
    gm.set_entity(2, 1, "COIN")  # 金币不是怪物
    result = ctrl.attack_monster(2, 1)
    assert result is False, "攻击非怪物格应返回 False"
    print("  [PASS] test_combat_not_monster")


# =========================================================================
# 测试 3：跨关清空
# =========================================================================

def test_purge_temporary_items():
    """purge_temporary_items 清空弓箭、柴刀、钥匙，保留金币和铁锹等。"""
    p = PlayerState()
    # 设置临时道具
    p.arrows = 3
    p.has_machete = True
    p.keys = {"RED": 2, "GREEN": 2, "BLUE": 2, "EXIT": 2}
    p.has_clover = True
    # 设置永久资产
    p.gold = 100
    p.tools["pickaxe"] = 2
    p.bag_tier_index = 1
    p.current_hearts = 2

    p.purge_temporary_items()

    assert p.arrows == 0, "弓箭应归零"
    assert p.has_machete is False, "柴刀应失效"
    assert p.has_clover is False, "四叶草应失效"
    assert all(p.keys[k] == 0 for k in ("RED", "GREEN", "BLUE", "EXIT")), "所有钥匙应归零"

    # 验证永久资产保留
    assert p.gold == 100, "金币应保留"
    assert p.tools["pickaxe"] == 2, "铁锹应保留"
    assert p.bag_tier_index == 1, "背包等级应保留"
    assert p.current_hearts == 2, "红心应保留"
    print("  [PASS] test_purge_temporary_items")


# =========================================================================
# 测试 4：关卡生成散布
# =========================================================================

def test_generator_creates_monsters():
    """关卡生成器中应有 MONSTER 实体。"""
    gen = LevelGenerator(seed=42)
    gm, start, exit_ = gen.generate_level(5)
    found = any(
        gm.layer2[y][x] == "MONSTER"
        for y in range(gm.height)
        for x in range(gm.width)
    )
    assert found, "关卡中至少应有 1 个 MONSTER"
    print("  [PASS] test_generator_creates_monsters")


def test_generator_creates_weapons():
    """关卡生成器中应有 ARROW 和 MACHETE 实体。"""
    gen = LevelGenerator(seed=42)
    gm, start, exit_ = gen.generate_level(5)

    has_arrow = any(
        gm.layer2[y][x] == "ARROW"
        for y in range(gm.height)
        for x in range(gm.width)
    )
    has_machete = any(
        gm.layer2[y][x] == "MACHETE"
        for y in range(gm.height)
        for x in range(gm.width)
    )

    assert has_arrow, "关卡中至少应有 1 个 ARROW"
    assert has_machete, "关卡中至少应有 1 个 MACHETE"
    print("  [PASS] test_generator_creates_weapons")


def test_safe_zone_no_monsters():
    """起点 3x3 安全区内应绝无怪物。"""
    for level in range(1, 6):
        gen = LevelGenerator(seed=level * 10)
        gm, start, exit_ = gen.generate_level(level)

        sx, sy = start
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = sx + dx, sy + dy
                if gm.is_in_bounds(nx, ny):
                    assert gm.layer2[ny][nx] != "MONSTER", \
                        f"关卡 {level} 安全区 ({nx},{ny}) 发现怪物"

    print("  [PASS] test_safe_zone_no_monsters")


def test_generator_monster_count_range():
    """每关怪物数量应在 2~4 范围内。"""
    gen = LevelGenerator(seed=77)
    gm, start, exit_ = gen.generate_level(3)

    monster_count = sum(
        1
        for y in range(gm.height)
        for x in range(gm.width)
        if gm.layer2[y][x] == "MONSTER"
    )
    assert 2 <= monster_count <= 4, \
        f"怪物数量应在 2~4 之间，实际为 {monster_count}"
    print("  [PASS] test_generator_monster_count_range")


# =========================================================================
# 主入口
# =========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("第 28 课：怪物、武器收集与多级战斗判定 — 单元测试")
    print("=" * 60)
    print()

    # 武器拾取
    print("[武器拾取与上限]")
    test_arrow_pickup_and_cap()
    test_machete_pickup()
    print()

    # 多级战斗判定
    print("[多级战斗判定]")
    test_combat_machete_kill()
    test_combat_arrow_kill()
    test_combat_unarmed_damage()
    test_combat_move_player_machete()
    test_combat_move_player_unarmed()
    test_combat_not_adjacent()
    test_combat_not_monster()
    print()

    # 跨关清空
    print("[跨关临时道具清空]")
    test_purge_temporary_items()
    print()

    # 关卡生成散布
    print("[关卡生成散布验证]")
    test_generator_creates_monsters()
    test_generator_creates_weapons()
    test_safe_zone_no_monsters()
    test_generator_monster_count_range()
    print()

    print("=" * 60)
    print("全部测试通过！ PASS")
    print("=" * 60)
