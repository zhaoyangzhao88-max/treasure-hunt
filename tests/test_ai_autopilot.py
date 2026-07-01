"""AI 自动驾驶求解器验证脚本 — Microsoft Treasure Hunt

Headless 模式下验证 AISolver 的扫雷决策链与 GameplayScreen 的 P 键状态机。

运行方式::

    python tests/test_ai_autopilot.py
"""

import os
import sys

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Headless 模式：必须在 pygame.init() 之前设置
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from src.ai_autopilot import AISolver
from src.config import SCREEN_WIDTH, SCREEN_HEIGHT
from src.interaction_controller import InteractionController
from src.map_data import GameMap
from src.player_state import PlayerState
from src.screens.gameplay_screen import GameplayScreen


# =============================================================================
# 辅助函数
# =============================================================================

def _make_solver(w=10, h=10, px=0, py=0):
    """创建一个 AISolver + 空白地图 + 玩家状态 + 控制器组合。"""
    gm = GameMap(w, h)
    ps = PlayerState()
    ctrl = InteractionController(gm, ps, start_x=px, start_y=py)
    solver = AISolver(gm, ps, ctrl)
    return solver, gm, ps, ctrl


def _make_open_map(w, h):
    """创建全 UNCOVERED / NONE 的空白地图。"""
    gm = GameMap(w, h)
    for y in range(h):
        for x in range(w):
            gm.layer0[y][x] = "UNCOVERED"
            gm.layer1[y][x] = "NONE"
    return gm


# =============================================================================
# 测试用例
# =============================================================================

def test_rule_a_flag():
    """规则 A：100% 确定雷 → 标雷。

    场景：3×3 地图，仅 (0,0) 是 DIRT，其余全 UNCOVERED。
    陷阱在 (0,0)。数字格 (1,1) 的邻域雷数 == 1，
    其 8 邻域中仅 (0,0) 一个 DIRT → 必为雷 → FLAG。
    """
    solver, gm, ps, ctrl = _make_solver(w=3, h=3, px=1, py=1)

    # 全图揭开（除 (0,0) 是 DIRT）
    for y in range(3):
        for x in range(3):
            gm.layer0[y][x] = "UNCOVERED"
            gm.layer1[y][x] = "NONE"
    gm.layer0[0][0] = "DIRT"

    # 陷阱在 (0, 0) — 这是 (1,1) 邻域内唯一的雷
    gm.traps[0][0] = True

    ctrl.player_x = 1
    ctrl.player_y = 1

    action_type, target, _ = solver.think_next_action(1, 1)

    assert action_type == "FLAG", f"Expected FLAG, got {action_type}"
    assert target == (0, 0), f"Expected (0, 0), got {target}"
    print("[PASS] test_rule_a_flag")


def test_rule_b_uncover():
    """规则 B：100% 确定安全 → 开掘。

    场景：3×3 地图，陷阱在 (2,2) 且已 flag。
    数字格 (1,1) 邻域雷数 == 1 == flag 数 → 所有 DIRT 邻格必安全。
    (1,0) 是 DIRT 且与玩家 (0,0) 相邻 → 直接揭开。
    """
    solver, gm, ps, ctrl = _make_solver(w=3, h=3, px=0, py=0)

    # 全图揭开（除 DIRT 区域）
    for y in range(3):
        for x in range(3):
            gm.layer0[y][x] = "UNCOVERED"
            gm.layer1[y][x] = "NONE"

    # 仅留 (1,0) 为 DIRT（与玩家 (0,0) 相邻）
    gm.layer0[0][1] = "DIRT"

    # 陷阱在 (2, 2) 并 flag — 这是 (1,1) 的唯一邻雷
    gm.traps[2][2] = True
    gm.flags[2][2] = True

    ctrl.player_x = 0
    ctrl.player_y = 0

    action_type, target, _ = solver.think_next_action(0, 0)

    assert action_type == "UNCOVER", f"Expected UNCOVER, got {action_type}"
    assert target == (1, 0), f"Expected (1, 0), got {target}"
    print("[PASS] test_rule_b_uncover")


def test_a_star_stepping():
    """A* 引导步进：安全 DIRT 在远处 → 沿 A* 路径走 1 步。

    场景：7×7 全 UNCOVERED 地图，玩家 (0,0)，
    仅 (5,5) 处有一块 DIRT（目标）。
    规则 1/2/3 不触发 → 规则 4 导航到 (5,5) 并返回第 1 步。
    """
    solver, gm, ps, ctrl = _make_solver(w=7, h=7, px=0, py=0)

    # 全图揭开
    for y in range(7):
        for x in range(7):
            gm.layer0[y][x] = "UNCOVERED"
            gm.layer1[y][x] = "NONE"

    # 仅留 (5, 5) 为 DIRT
    gm.layer0[5][5] = "DIRT"

    ctrl.player_x = 0
    ctrl.player_y = 0

    action_type, target, _ = solver.think_next_action(0, 0)

    assert action_type == "MOVE", f"Expected MOVE, got {action_type}"
    assert target is not None, "Expected non-None target"
    tx, ty = target
    # 步进格必须与玩家 4-邻相邻
    assert abs(tx - 0) + abs(ty - 0) == 1, \
        f"Step must be 4-adjacent to player, got ({tx},{ty})"
    # 步进格必须朝 (5,5) 前进（曼哈顿距离减少）
    old_dist = abs(5 - 0) + abs(5 - 0)  # 10
    new_dist = abs(5 - tx) + abs(5 - ty)
    assert new_dist < old_dist, \
        f"Step must reduce distance to target: {old_dist} → {new_dist}"

    # 验证步进后控制器能正常移动
    result = ctrl.move_player(tx, ty)
    assert result == "SUCCESS", f"move_player should succeed, got {result}"
    assert ctrl.player_x == tx and ctrl.player_y == ty
    print("[PASS] test_a_star_stepping")


def test_auto_tool_use():
    """自动道具使用：相邻 LOCK_RED + 有 RED 钥匙 → USE_TOOL RED。

    场景：5×5 地图，玩家 (2,2)，右侧 (3,2) 有 LOCK_RED，
    玩家背包有 1 把 RED 钥匙。
    """
    solver, gm, ps, ctrl = _make_solver(w=5, h=5, px=2, py=2)

    # 全图揭开
    for y in range(5):
        for x in range(5):
            gm.layer0[y][x] = "UNCOVERED"
            gm.layer1[y][x] = "NONE"

    # 放置红色锁门在 (3, 2)
    gm.layer1[2][3] = "LOCK_RED"

    # 给玩家 1 把红色钥匙
    ps.keys["RED"] = 1

    ctrl.player_x = 2
    ctrl.player_y = 2

    action_type, target, extra = solver.think_next_action(2, 2)

    assert action_type == "USE_TOOL", f"Expected USE_TOOL, got {action_type}"
    assert target == (3, 2), f"Expected (3, 2), got {target}"
    assert extra == "RED", f"Expected 'RED', got {extra}"

    # 验证执行后锁门被清除
    result = ctrl.interact_with_adjacent_obstacle(3, 2)
    assert result is True, "interact_with_adjacent_obstacle should succeed"
    assert gm.layer1[2][3] == "NONE", "Lock should be cleared"
    assert ps.keys["RED"] == 0, "RED key should be consumed"
    print("[PASS] test_auto_tool_use")


def test_p_key_toggle():
    """P 键一键托管状态机：切换 True/False，WASD 被拦截。"""
    if not pygame.get_init():
        pygame.init()

    screen = GameplayScreen()

    class FakeGameManager:
        def __init__(self):
            self.player_state = PlayerState()
            self.screen_manager = None
            self.asset_manager = None
            self.save_manager = None

    screen.game_manager = FakeGameManager()

    # 构建最小可运行状态
    gm = _make_open_map(7, 7)
    ps = screen.game_manager.player_state
    ctrl = InteractionController(gm, ps, start_x=1, start_y=1)
    screen.interaction_controller = ctrl
    screen.game_map = gm
    screen.ai_solver = AISolver(gm, ps, ctrl)
    screen.show_paused = False
    screen.show_help = False

    # 初始状态
    assert screen.autoplay_mode is False, "Should start with autoplay off"

    # 第 1 次 P → 开启
    ev_on = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_p})
    screen.handle_event(ev_on)
    assert screen.autoplay_mode is True, "P should enable autoplay"

    # 第 2 次 P → 关闭
    ev_off = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_p})
    screen.handle_event(ev_off)
    assert screen.autoplay_mode is False, "P should disable autoplay"

    # 再次开启，验证 WASD 被拦截
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_p}))
    assert screen.autoplay_mode is True

    px_before = ctrl.player_x
    # 尝试右键移动（应被拦截）
    screen.handle_event(pygame.event.Event(
        pygame.KEYDOWN, {"key": pygame.K_RIGHT}))
    assert ctrl.player_x == px_before, \
        "WASD must be blocked during autoplay"

    # 关闭后恢复移动
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_p}))
    assert screen.autoplay_mode is False
    screen.handle_event(pygame.event.Event(
        pygame.KEYDOWN, {"key": pygame.K_RIGHT}))
    assert ctrl.player_x == px_before + 1, \
        "WASD should work after autoplay disabled"

    # update 不崩溃（autoplay 开 + 0.3s 步进触发 AI tick）
    screen.autoplay_mode = True
    screen.ai_tick_timer = 0.0
    screen.update(0.3)  # 超过 0.25s 间隔
    # 无崩溃 = 通过

    print("[PASS] test_p_key_toggle")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    test_rule_a_flag()
    test_rule_b_uncover()
    test_a_star_stepping()
    test_auto_tool_use()
    test_p_key_toggle()
    print("\n=== ALL AI AUTOPILOT TESTS PASSED ===")
