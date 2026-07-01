"""活性木乃伊 AI 系统单元测试 — 第 41 课

覆盖：
- A* 寻路（直路 / 绕墙 / 不可达）
- ActiveMummy 苏醒与追击步进
- 玩家移动时木乃伊同步步进
- 重合伤害 + 安全弹开
- 消灭（柴刀 / 弓箭 / 肉身）
- 散布规则（level < 5 不散布；level >= 5 可散布）
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

from src.map_data import GameMap
from src.pathfinding import a_star_search
from src.active_mummy import ActiveMummy, ALERT_RADIUS
from src.interaction_controller import InteractionController
from src.player_state import PlayerState
from src.level_generator import LevelGenerator
from src.tile_renderer import TileRenderer
from src.config import ACTIVE_MUMMY


def _make_open_map(w: int = 20, h: int = 20) -> GameMap:
    """构造一个全空地图（所有格子 UNCOVERED + NONE）。"""
    gm = GameMap(w, h)
    for y in range(h):
        for x in range(w):
            gm.layer0[y][x] = "UNCOVERED"
            gm.layer1[y][x] = "NONE"
    return gm


# =============================================================================
# A* 寻路测试
# =============================================================================

def test_a_star_straight_path():
    """直线路径：从 (0,0) 到 (5,0) 应返回 5 步，终点 (5,0)。"""
    gm = _make_open_map()
    path = a_star_search(gm, (0, 0), (5, 0))
    assert len(path) == 5, f"Expected 5 steps, got {len(path)}"
    assert path[0] == (1, 0), f"First step should be (1,0), got {path[0]}"
    assert path[-1] == (5, 0), f"Last step should be (5,0), got {path[-1]}"
    # 每步曼哈顿距离 == 1
    prev = (0, 0)
    for p in path:
        assert abs(p[0] - prev[0]) + abs(p[1] - prev[1]) == 1
        prev = p


def test_a_star_same_start_end():
    """起点 == 终点返回空列表。"""
    gm = _make_open_map()
    assert a_star_search(gm, (3, 3), (3, 3)) == []


def test_a_star_out_of_bounds():
    """越界起点或终点返回空列表。"""
    gm = _make_open_map()
    assert a_star_search(gm, (-1, 0), (5, 0)) == []
    assert a_star_search(gm, (0, 0), (100, 100)) == []


def test_a_star_avoid_wall():
    """在 (2,0) 立一堵墙，从 (0,0) → (4,0) 路径应绕过 (2,0)。"""
    gm = _make_open_map()
    gm.layer1[0][2] = "WALL"
    path = a_star_search(gm, (0, 0), (4, 0))
    assert path, "Path should exist"
    assert (2, 0) not in path, f"Path should not pass through wall (2,0), got {path}"
    assert path[-1] == (4, 0)


def test_a_star_unreachable():
    """四面被墙围死终点 → 返回 []。"""
    gm = _make_open_map()
    # 围死 (5,5)
    gm.layer1[4][5] = "WALL"
    gm.layer1[6][5] = "WALL"
    gm.layer1[5][4] = "WALL"
    gm.layer1[5][6] = "WALL"
    path = a_star_search(gm, (0, 0), (5, 5))
    assert path == [], f"Expected unreachable, got {path}"


def test_a_star_u_shape_wall():
    """U 形墙体完全包围终点 → 返回 []。"""
    gm = _make_open_map(15, 15)
    # 在 (7,7) 周围建 U 形墙
    for i in range(5, 10):
        gm.layer1[5][i] = "WALL"   # 上边
        gm.layer1[9][i] = "WALL"   # 下边
    for i in range(5, 10):
        gm.layer1[i][5] = "WALL"   # 左边
        gm.layer1[i][9] = "WALL"   # 右边
    # 终点 (7,7) 被完全围死
    path = a_star_search(gm, (0, 0), (7, 7))
    assert path == [], f"Expected unreachable (U-wall), got {path}"


# =============================================================================
# ActiveMummy 苏醒与追击
# =============================================================================

def test_mummy_sleep_to_chase():
    """木乃伊在 (6,0) 沉睡，玩家从 (0,0) 移动到 (1,0) → 距离 5 → 苏醒。

    再移动到 (2,0) → 距离 4 → 木乃伊追击一步到 (5,0)。
    """
    gm = _make_open_map()
    mummy = ActiveMummy(6, 0)
    player = PlayerState()
    ctrl = InteractionController(gm, player, start_x=0, start_y=0)
    ctrl.active_mummies = [mummy]

    # 玩家移动到 (1,0) — 距离 6 → 5，触发苏醒
    ctrl.move_player(1, 0)
    assert mummy.state == "CHASE", f"Expected CHASE, got {mummy.state}"
    # 苏醒回合不位移
    assert (mummy.x, mummy.y) == (6, 0)

    # 玩家移动到 (2,0) — 距离 5 → 4，木乃伊追击一步
    ctrl.move_player(2, 0)
    assert (mummy.x, mummy.y) == (5, 0), f"Expected (5,0), got ({mummy.x},{mummy.y})"
    dist = abs(mummy.x - ctrl.player_x) + abs(mummy.y - ctrl.player_y)
    assert dist == 3, f"Expected dist=3, got {dist}"


def test_mummy_chase_follows_player():
    """玩家沿通道移动，木乃伊跟随并每回合曼哈顿距离严格递减。"""
    gm = _make_open_map()
    mummy = ActiveMummy(10, 0)
    player = PlayerState()
    ctrl = InteractionController(gm, player, start_x=0, start_y=0)
    ctrl.active_mummies = [mummy]

    # 强制苏醒
    mummy.state = "CHASE"

    prev_dist = abs(mummy.x - ctrl.player_x) + abs(mummy.y - ctrl.player_y)
    for step in range(1, 6):
        ctrl.move_player(step, 0)
        new_dist = abs(mummy.x - ctrl.player_x) + abs(mummy.y - ctrl.player_y)
        assert new_dist < prev_dist, (
            f"Step {step}: dist should decrease, prev={prev_dist} new={new_dist}"
        )
        prev_dist = new_dist


def test_mummy_no_move_when_far():
    """玩家距离 > alert_radius 时木乃伊保持沉睡。"""
    gm = _make_open_map()
    mummy = ActiveMummy(10, 0)
    player = PlayerState()
    ctrl = InteractionController(gm, player, start_x=0, start_y=0)
    ctrl.active_mummies = [mummy]

    ctrl.move_player(1, 0)
    assert mummy.state == "SLEEP", f"Expected SLEEP, got {mummy.state}"
    assert (mummy.x, mummy.y) == (10, 0)


# =============================================================================
# 重合伤害 + 安全弹开
# =============================================================================

def test_mummy_overlap_damage_and_bounce():
    """木乃伊追击到与玩家重合 → 玩家受伤 + 木乃伊被弹开。

    设置：木乃伊在 (1,0) 苏醒，玩家从 (0,0) 移动到 (2,0)。
    玩家移动后触发木乃伊回合，木乃伊从 (1,0) 追向 (2,0) → 走到玩家格。
    move_player 要求相邻移动，因此分两步：玩家先走 (1,0)（被阻挡因为木乃伊在），
    为简化直接 spawn木乃伊 到 (3,0)，玩家走到 (2,0)，木乃伊追击走到 (2,0)。
    """
    gm = _make_open_map()
    mummy = ActiveMummy(3, 0)
    mummy.state = "CHASE"  # 强制苏醒
    player = PlayerState()
    player.current_hearts = 3
    player.current_shields = 0
    ctrl = InteractionController(gm, player, start_x=0, start_y=0)
    ctrl.active_mummies = [mummy]

    # 玩家走到 (1,0) 触发木乃伊回合
    result = ctrl.move_player(1, 0)
    assert result == "SUCCESS", f"Expected SUCCESS, got {result}"
    # 木乃伊追击：从 (3,0) 追到 (2,0)
    assert (mummy.x, mummy.y) == (2, 0), f"Expected mummy at (2,0), got ({mummy.x},{mummy.y})"

    # 玩家走到 (2,0)（相邻合法） → 触发木乃伊回合
    # 木乃伊从 (2,0) 追击 → 走到 (2,0) 玩家所在格 → 触发伤害
    ctrl.move_player(2, 0)

    # 玩家应受伤（红心 -1）
    assert player.current_hearts == 2, (
        f"Expected hearts=2, got {player.current_hearts}"
    )
    # 木乃伊应被弹开（坐标 != 玩家坐标）
    assert (mummy.x, mummy.y) != (ctrl.player_x, ctrl.player_y), (
        f"Mummy should be bounced away, but is at ({mummy.x},{mummy.y})"
    )
    # 屏闪标记应被置位
    assert ctrl.screen_flash_color is not None
    assert ctrl.screen_flash_duration > 0


def test_mummy_overlap_damage_shield_first():
    """玩家有护盾时，木乃伊撞击优先扣护盾。"""
    gm = _make_open_map()
    mummy = ActiveMummy(3, 0)
    mummy.state = "CHASE"
    player = PlayerState()
    player.current_hearts = 3
    player.current_shields = 2
    ctrl = InteractionController(gm, player, start_x=0, start_y=0)
    ctrl.active_mummies = [mummy]

    # 玩家走到 (1,0) 触发木乃伊追击
    ctrl.move_player(1, 0)
    # 玩家走到 (2,0) 触发重合
    ctrl.move_player(2, 0)

    # 护盾应扣 1，红心不变
    assert player.current_shields == 1, (
        f"Expected shields=1, got {player.current_shields}"
    )
    assert player.current_hearts == 3, (
        f"Expected hearts=3, got {player.current_hearts}"
    )


def test_invincible_timer_prevents_double_damage():
    """无敌窗口内木乃伊再次重合不重复扣血。"""
    gm = _make_open_map()
    mummy = ActiveMummy(3, 0)
    mummy.state = "CHASE"
    player = PlayerState()
    player.current_hearts = 3
    ctrl = InteractionController(gm, player, start_x=0, start_y=0)
    ctrl.active_mummies = [mummy]

    # 走到 (1,0) 触发追击
    ctrl.move_player(1, 0)
    # 走到 (2,0) 触发撞击
    ctrl.move_player(2, 0)
    hearts_after_first = player.current_hearts
    assert hearts_after_first == 2

    # 立即再次触发（无敌窗口内）
    ctrl.invincible_timer = 0.05  # 仍在无敌窗口
    ctrl._process_mummy_turn()
    # 不应再扣血
    assert player.current_hearts == hearts_after_first


# =============================================================================
# 消灭
# =============================================================================

def test_attack_kills_active_mummy_with_machete():
    """玩家有柴刀，点击相邻 ACTIVE_MUMMY → 木乃伊被抹杀。"""
    gm = _make_open_map()
    gm.set_entity(1, 0, ACTIVE_MUMMY)
    player = PlayerState()
    player.has_machete = True
    ctrl = InteractionController(gm, player, start_x=0, start_y=0)
    ctrl.link_active_mummies_from_map()
    assert len(ctrl.active_mummies) == 1

    killed = ctrl.attack_active_mummy(1, 0)
    assert killed is True
    assert len(ctrl.active_mummies) == 0
    assert gm.layer2[0][1] == "NONE"


def test_attack_kills_active_mummy_with_arrow():
    """玩家有 1 支弓箭，点击相邻 ACTIVE_MUMMY → 木乃伊被抹杀，弓箭 -1。"""
    gm = _make_open_map()
    gm.set_entity(1, 0, ACTIVE_MUMMY)
    player = PlayerState()
    player.arrows = 1
    ctrl = InteractionController(gm, player, start_x=0, start_y=0)
    ctrl.link_active_mummies_from_map()

    killed = ctrl.attack_active_mummy(1, 0)
    assert killed is True
    assert player.arrows == 0
    assert len(ctrl.active_mummies) == 0
    assert gm.layer2[0][1] == "NONE"


def test_attack_active_mummy_no_weapon_damages_player():
    """玩家无武器，点击相邻 ACTIVE_MUMMY → 玩家受伤，木乃伊保留。"""
    gm = _make_open_map()
    gm.set_entity(1, 0, ACTIVE_MUMMY)
    player = PlayerState()
    player.current_hearts = 3
    ctrl = InteractionController(gm, player, start_x=0, start_y=0)
    ctrl.link_active_mummies_from_map()

    killed = ctrl.attack_active_mummy(1, 0)
    assert killed is False
    assert player.current_hearts == 2
    assert len(ctrl.active_mummies) == 1
    assert gm.layer2[0][1] == ACTIVE_MUMMY


# =============================================================================
# 散布规则
# =============================================================================

def test_no_spawn_below_level_5():
    """Level < 5 时不应散布 ACTIVE_MUMMY。"""
    for level in (1, 2, 3, 4):
        gen = LevelGenerator(seed=42)
        gm, _, _ = gen.generate_level(level)
        entities = {
            gm.layer2[y][x]
            for y in range(gm.height)
            for x in range(gm.width)
            if gm.layer2[y][x] != "NONE"
        }
        assert ACTIVE_MUMMY not in entities, (
            f"Level {level} should not spawn ACTIVE_MUMMY, got {entities}"
        )


def test_spawn_active_mummy_at_level_5():
    """Level >= 5 时，在固定种子下应至少散布一个 ACTIVE_MUMMY。

    由于 30% 概率，使用多个种子尝试，确保至少有一个种子能生成。
    """
    found = False
    for seed in range(50):
        gen = LevelGenerator(seed=seed)
        gm, _, _ = gen.generate_level(5)
        for y in range(gm.height):
            for x in range(gm.width):
                if gm.layer2[y][x] == ACTIVE_MUMMY:
                    found = True
                    break
            if found:
                break
        if found:
            break
    assert found, "Expected at least one ACTIVE_MUMMY at level 5 across 50 seeds"


# =============================================================================
# 渲染测试
# =============================================================================

def test_tile_renderer_active_mummy_fallback():
    """TileRenderer 应能渲染 ACTIVE_MUMMY 退化瓦片而不崩溃。"""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    surface = pygame.Surface((48, 48))
    renderer = TileRenderer(tile_size=48)
    # 不应抛异常
    renderer.draw_tile(surface, ACTIVE_MUMMY, 0, 0, extra_info=0)
    renderer.draw_tile(surface, ACTIVE_MUMMY, 0, 0, extra_info=10)


# =============================================================================
# 主入口
# =============================================================================

def run_all_tests():
    """运行全部测试并打印结果。"""
    tests = [
        test_a_star_straight_path,
        test_a_star_same_start_end,
        test_a_star_out_of_bounds,
        test_a_star_avoid_wall,
        test_a_star_unreachable,
        test_a_star_u_shape_wall,
        test_mummy_sleep_to_chase,
        test_mummy_chase_follows_player,
        test_mummy_no_move_when_far,
        test_mummy_overlap_damage_and_bounce,
        test_mummy_overlap_damage_shield_first,
        test_invincible_timer_prevents_double_damage,
        test_attack_kills_active_mummy_with_machete,
        test_attack_kills_active_mummy_with_arrow,
        test_attack_active_mummy_no_weapon_damages_player,
        test_no_spawn_below_level_5,
        test_spawn_active_mummy_at_level_5,
        test_tile_renderer_active_mummy_fallback,
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
