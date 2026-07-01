"""法老王首领（MummyKing）Boss 战系统单元测试 — 第 49 课

覆盖 4 个验证场景：
1. Boss 三血量击杀：3 次武器命中 → 死亡 + 掉落 KEY_EXIT，玩家拾取
2. Boss 命中召唤仆从：每次命中召唤一只 ACTIVE_MUMMY 到首个空余正交邻居
3. Boss 关卡生成：level % 10 == 0 时无散放 KEY_EXIT 且恰好 1 只 MUMMY_KING
4. Boss 渲染：TileRenderer 应能绘制 MUMMY_KING 退化瓦片
"""

import os
import sys

# 将项目根目录加入搜索路径
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()

from collections import deque

from src.map_data import GameMap
from src.mummy_king import MummyKing
from src.interaction_controller import InteractionController
from src.player_state import PlayerState
from src.level_generator import LevelGenerator
from src.tile_renderer import TileRenderer
from src.config import MUMMY_KING, ACTIVE_MUMMY, MUMMY_KING_MAX_HEARTS


def _make_open_map(w: int = 20, h: int = 20) -> GameMap:
    """构造一个全空地图（所有格子 UNCOVERED + NONE）。"""
    gm = GameMap(w, h)
    for y in range(h):
        for x in range(w):
            gm.layer0[y][x] = "UNCOVERED"
            gm.layer1[y][x] = "NONE"
    return gm


# =============================================================================
# 场景 1：Boss 三血量击杀 + 掉落 KEY_EXIT
# =============================================================================

def test_boss_three_hits_to_kill_and_drops_key_exit():
    """用柴刀命中 Boss 3 次：前两次 Boss 存活 + 召唤，第三次死亡并掉落 KEY_EXIT。

    同时验证：玩家拾取掉落的 KEY_EXIT 后，player.keys["EXIT"] == 1。
    """
    gm = _make_open_map()
    bx, by = 2, 0
    gm.set_entity(bx, by, MUMMY_KING)

    player = PlayerState()
    player.has_machete = True
    player.current_hearts = 3

    ctrl = InteractionController(gm, player, start_x=1, start_y=0)
    king = MummyKing(bx, by)
    ctrl.mummy_kings = [king]

    # 第 1 次命中 — 3→2，Boss 存活，100% 召唤
    result = ctrl.attack_mummy_king(bx, by)
    assert result is False, "未击杀应返回 False"
    assert king.hearts == MUMMY_KING_MAX_HEARTS - 1, f"Boss 应剩 2 血，实际 {king.hearts}"
    assert gm.layer2[by][bx] == MUMMY_KING, "Boss 存活时 layer2 应保持 MUMMY_KING"
    assert len(ctrl.active_mummies) >= 1, "受击应召唤至少 1 只爪牙"

    # 第 2 次命中 — 2→1，Boss 存活
    mummies_before = len(ctrl.active_mummies)
    result = ctrl.attack_mummy_king(bx, by)
    assert result is False
    assert king.hearts == 1
    assert gm.layer2[by][bx] == MUMMY_KING
    assert len(ctrl.active_mummies) > mummies_before, "每次命中都应新增爪牙"

    # 第 3 次命中 — 1→0，击杀
    result = ctrl.attack_mummy_king(bx, by)
    assert result is True, "击杀应返回 True"
    assert gm.layer2[by][bx] == "KEY_EXIT", "Boss 死亡应掉落 KEY_EXIT"
    assert len(ctrl.mummy_kings) == 0, "击杀后 mummy_kings 列表应为空"

    # 玩家走到 KEY_EXIT 格 → 收集，获得 EXIT 钥匙
    ctrl.move_player(bx, by)
    assert player.keys["EXIT"] == 1, f"玩家应获得 EXIT 钥匙，实际 keys={dict(player.keys)}"


def test_boss_arrow_three_hits():
    """用弓箭命中 Boss 3 次：箭消耗 3 支，击杀后掉落 KEY_EXIT。"""
    gm = _make_open_map()
    bx, by = 2, 0
    gm.set_entity(bx, by, MUMMY_KING)

    player = PlayerState()
    player.arrows = 5

    ctrl = InteractionController(gm, player, start_x=1, start_y=0)
    king = MummyKing(bx, by)
    ctrl.mummy_kings = [king]

    for _ in range(3):
        ctrl.attack_mummy_king(bx, by)

    assert player.arrows == 2, f"应消耗 3 箭剩 2，实际 {player.arrows}"
    assert gm.layer2[by][bx] == "KEY_EXIT"


def test_boss_no_weapon_damages_player():
    """无武器攻击 Boss → 玩家受伤，Boss 无损。"""
    gm = _make_open_map()
    bx, by = 2, 0
    gm.set_entity(bx, by, MUMMY_KING)

    player = PlayerState()
    player.current_hearts = 3

    ctrl = InteractionController(gm, player, start_x=1, start_y=0)
    king = MummyKing(bx, by)
    ctrl.mummy_kings = [king]

    result = ctrl.attack_mummy_king(bx, by)
    assert result is False, "无武器应返回 False"
    assert player.current_hearts == 2
    assert king.hearts == MUMMY_KING_MAX_HEARTS, "Boss 血量应不变"


# =============================================================================
# 场景 2：命中召唤仆从（首个正交邻居）
# =============================================================================

def test_boss_hit_summons_minion_to_first_orthogonal_neighbor():
    """Boss 被命中后，在首个空余正交邻居格召唤一只 ACTIVE_MUMMY。

    搜索顺序：上 → 下 → 左 → 右。
    Boss 在 (5,5)，玩家位于 (4,5)（左邻），召唤应落在上方 (5,4)。
    """
    gm = _make_open_map()
    bx, by = 5, 5
    gm.set_entity(bx, by, MUMMY_KING)

    player = PlayerState()
    player.has_machete = True

    ctrl = InteractionController(gm, player, start_x=4, start_y=5)
    king = MummyKing(bx, by)
    ctrl.mummy_kings = [king]

    ctrl.attack_mummy_king(bx, by)

    assert len(ctrl.active_mummies) == 1, "应召唤 1 只仆从"
    minion = ctrl.active_mummies[0]
    assert (minion.x, minion.y) == (5, 4), (
        f"仆从应在首个空邻 (5,4)，实际在 ({minion.x},{minion.y})"
    )
    assert gm.layer2[4][5] == ACTIVE_MUMMY, "上方格 layer2 应为 ACTIVE_MUMMY"


def test_boss_hit_summon_skips_occupied_neighbor():
    """首个正交邻居被占用时，召唤到下一个空余邻居。

    Boss 在 (5,5)，上方 (5,4) 放 COIN → 召唤应落下方 (5,6)。
    """
    gm = _make_open_map()
    bx, by = 5, 5
    gm.set_entity(bx, by, MUMMY_KING)
    gm.set_entity(5, 4, "COIN")  # 占用上方

    player = PlayerState()
    player.has_machete = True

    ctrl = InteractionController(gm, player, start_x=4, start_y=5)
    king = MummyKing(bx, by)
    ctrl.mummy_kings = [king]

    ctrl.attack_mummy_king(bx, by)

    assert len(ctrl.active_mummies) == 1
    minion = ctrl.active_mummies[0]
    assert (minion.x, minion.y) == (5, 6), (
        f"仆从应在下一个空邻 (5,6)，实际在 ({minion.x},{minion.y})"
    )


def test_boss_hit_summon_no_space_silent_skip():
    """所有正交邻居均不可用时，召唤静默跳过（不崩溃）。"""
    gm = _make_open_map()
    bx, by = 5, 5
    gm.set_entity(bx, by, MUMMY_KING)
    # 占用所有正交邻居
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        gm.layer2[by + dy][bx + dx] = "COIN"

    player = PlayerState()
    player.has_machete = True

    ctrl = InteractionController(gm, player, start_x=4, start_y=4)
    king = MummyKing(bx, by)
    ctrl.mummy_kings = [king]

    # 不应崩溃
    ctrl.attack_mummy_king(bx, by)
    assert len(ctrl.active_mummies) == 0, "无空余邻居时不应召唤仆从"


# =============================================================================
# 场景 3：Boss 关卡生成（唯一性约束 + 可达性）
# =============================================================================

def _solver_style_reachable(gm: GameMap, start: tuple) -> set:
    """与 verify_solvability 一致的通行 BFS（仅 WALL 阻挡）。"""
    visited = {start}
    q = deque([start])
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if not gm.is_in_bounds(nx, ny):
                continue
            if (nx, ny) in visited:
                continue
            if gm.layer1[ny][nx] == "WALL":
                continue
            visited.add((nx, ny))
            q.append((nx, ny))
    return visited


def test_boss_level_has_mummy_king_and_no_key_exit():
    """Boss 关卡 (level 10)：无散放 KEY_EXIT，恰好 1 只 MUMMY_KING。"""
    gen = LevelGenerator(seed=42)
    gm, _, _ = gen.generate_level(10)

    king_count = 0
    key_exit_count = 0
    for y in range(gm.height):
        for x in range(gm.width):
            e = gm.layer2[y][x]
            if e == MUMMY_KING:
                king_count += 1
            elif e == "KEY_EXIT":
                key_exit_count += 1

    assert king_count == 1, f"Level 10 应有 1 只 MUMMY_KING，实际 {king_count}"
    assert key_exit_count == 0, f"Level 10 不应有散放 KEY_EXIT，实际 {key_exit_count}"


def test_boss_level_across_seeds():
    """多个种子下 level 10 始终有 1 只 Boss 且无 KEY_EXIT，且 Boss 可达/邻出口。"""
    for seed in range(10):
        gen = LevelGenerator(seed=seed)
        gm, start, exit_ = gen.generate_level(10)

        king_count = 0
        key_exit_count = 0
        boss_pos = None
        for y in range(gm.height):
            for x in range(gm.width):
                e = gm.layer2[y][x]
                if e == MUMMY_KING:
                    king_count += 1
                    boss_pos = (x, y)
                elif e == "KEY_EXIT":
                    key_exit_count += 1

        assert king_count == 1, f"seed {seed}: 应有 1 Boss，实际 {king_count}"
        assert key_exit_count == 0, f"seed {seed}: 不应有 KEY_EXIT，实际 {key_exit_count}"

        # 可达性（玩家能从起点挖掘到 Boss 邻格）
        reach = _solver_style_reachable(gm, start)
        assert boss_pos in reach, f"seed {seed}: Boss {boss_pos} 不可达"
        # Boss 与出口相邻
        assert max(abs(boss_pos[0] - exit_[0]), abs(boss_pos[1] - exit_[1])) == 1, (
            f"seed {seed}: Boss {boss_pos} 不与出口 {exit_} 相邻"
        )


def test_non_boss_level_has_key_exit():
    """非 Boss 关卡 (level 9)：应有 KEY_EXIT，无 MUMMY_KING。"""
    gen = LevelGenerator(seed=42)
    gm, _, _ = gen.generate_level(9)

    king_count = 0
    key_exit_count = 0
    for y in range(gm.height):
        for x in range(gm.width):
            e = gm.layer2[y][x]
            if e == MUMMY_KING:
                king_count += 1
            elif e == "KEY_EXIT":
                key_exit_count += 1

    assert king_count == 0, f"Level 9 不应有 MUMMY_KING，实际 {king_count}"
    assert key_exit_count >= 1, f"Level 9 应有 KEY_EXIT，实际 {key_exit_count}"


# =============================================================================
# 场景 4：Boss 渲染 & 属性
# =============================================================================

def test_tile_renderer_mummy_king_fallback():
    """TileRenderer 应能渲染 MUMMY_KING 退化瓦片而不崩溃。"""
    surface = pygame.Surface((48, 48))
    renderer = TileRenderer(tile_size=48)
    # 不应抛异常
    renderer.draw_tile(surface, MUMMY_KING, 0, 0, extra_info=0)
    renderer.draw_tile(surface, MUMMY_KING, 0, 0, extra_info=10)


def test_boss_alert_radius_is_6():
    """MummyKing 苏醒半径应为 6（比普通木乃伊大 1）。"""
    king = MummyKing(0, 0)
    assert king.alert_radius == 6, f"预期 alert_radius=6，实际 {king.alert_radius}"
    assert king.hearts == MUMMY_KING_MAX_HEARTS, (
        f"预期 hearts={MUMMY_KING_MAX_HEARTS}，实际 {king.hearts}"
    )


# =============================================================================
# 主入口
# =============================================================================

def run_all_tests():
    """运行全部测试并打印结果。"""
    tests = [
        test_boss_three_hits_to_kill_and_drops_key_exit,
        test_boss_arrow_three_hits,
        test_boss_no_weapon_damages_player,
        test_boss_hit_summons_minion_to_first_orthogonal_neighbor,
        test_boss_hit_summon_skips_occupied_neighbor,
        test_boss_hit_summon_no_space_silent_skip,
        test_boss_level_has_mummy_king_and_no_key_exit,
        test_boss_level_across_seeds,
        test_non_boss_level_has_key_exit,
        test_tile_renderer_mummy_king_fallback,
        test_boss_alert_radius_is_6,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n=== {passed}/{passed + failed} tests passed ===")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
