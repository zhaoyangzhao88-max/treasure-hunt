"""胜利通关与死亡判定触发器单元测试 — Microsoft Treasure Hunt

验证 GameplayScreen 的胜利/死亡判定逻辑在 Headless 模式下
正确触发场景跳转并携带正确载荷。

测试覆盖:
- 移动至已解锁出口 → LEVEL_COMPLETE 跳转
- 生命值归零 → GAME_OVER 跳转
"""

import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import GameState
from src.game_manager import GameManager


# =============================================================================
# 辅助函数
# =============================================================================

def _reset_singletons():
    """重置全部单例以获得干净的测试环境。"""
    GameManager._instance = None
    from src.asset_manager import AssetManager
    AssetManager._instance = None


def _start_new_game():
    """初始化 Headless 游戏引擎并开始新游戏（Level 1）。

    Returns:
        (game_manager, gameplay_screen) 元组
    """
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)
    gm.screen_manager.switch_screen(GameState.PLAYING, {"continue": False})
    gs = gm.screen_manager.current_screen
    return gm, gs


# =============================================================================
# 测试 1: 移动至已解锁出口 → LEVEL_COMPLETE
# =============================================================================

def test_move_to_exit_triggers_level_complete():
    """玩家站在已解锁的出口格上触发 LEVEL_COMPLETE 跳转。

    验证步骤:
    1. 启动探索关 Level 1，玩家拥有 150 金币
    2. 将玩家置于出口相邻格，并清除出口障碍（模拟使用 KEY_EXIT）
    3. 将玩家移至出口格
    4. 调用 update(0.1) 触发判定
    5. 断言系统切换到 GameState.LEVEL_COMPLETE
    6. 断言 payload 中 completed_level == 1，gold_earned == 150
    """
    _reset_singletons()
    gm, gs = _start_new_game()

    # 给予玩家金币，用于 payload 校验
    gm.player_state.gold = 150

    # 获取由 LevelGenerator 放置的出口坐标
    exit_x, exit_y = gs.exit_pos

    # 玩家相邻格（出口左侧）
    adj_x, adj_y = exit_x - 1, exit_y

    # 确保相邻格和出口格均可步行
    gs.game_map.layer0[adj_y][adj_x] = "UNCOVERED"
    gs.game_map.layer1[adj_y][adj_x] = "NONE"
    gs.game_map.layer0[exit_y][exit_x] = "UNCOVERED"
    gs.game_map.layer1[exit_y][exit_x] = "NONE"   # 模拟钥匙已使用，锁门已清除

    # 将玩家置于出口相邻格
    gs.interaction_controller.player_x = adj_x
    gs.interaction_controller.player_y = adj_y

    # 将玩家移至出口格
    gs.interaction_controller.player_x = exit_x
    gs.interaction_controller.player_y = exit_y

    # 触发胜利判定
    gs.update(0.1)

    # 断言：场景已切换到 LEVEL_COMPLETE
    assert gm.screen_manager.current_state == GameState.LEVEL_COMPLETE, (
        f"期望 {GameState.LEVEL_COMPLETE}，实际 {gm.screen_manager.current_state}"
    )

    # 断言: payload 已正确传递到 LevelCompleteScreen
    lc_screen = gm.screen_manager.current_screen
    assert lc_screen.completed_level == 1, (
        f"completed_level 应为 1，实际 {lc_screen.completed_level}"
    )
    assert lc_screen.gold_earned == 150, (
        f"gold_earned 应为 150，实际 {lc_screen.gold_earned}"
    )
    assert lc_screen.remaining_hearts == 3, (
        f"remaining_hearts 应为 3，实际 {lc_screen.remaining_hearts}"
    )

    _reset_singletons()
    print("[PASS] test_move_to_exit_triggers_level_complete")


# =============================================================================
# 测试 2: 空血 → GAME_OVER
# =============================================================================

def test_zero_hearts_triggers_game_over():
    """玩家生命值归零时触发 GAME_OVER 跳转。

    验证步骤:
    1. 启动探索关 Level 1
    2. 将玩家生命值强设为 0
    3. 调用 update(0.1) 触发判定
    4. 断言系统切换到 GameState.GAME_OVER
    5. 断言 payload 中 current_level 为当前关卡数
    """
    _reset_singletons()
    gm, gs = _start_new_game()

    # 将玩家生命值置零
    gm.player_state.current_hearts = 0

    # 触发死亡判定
    gs.update(0.1)

    # 断言：场景已切换到 GAME_OVER
    assert gm.screen_manager.current_state == GameState.GAME_OVER, (
        f"期望 {GameState.GAME_OVER}，实际 {gm.screen_manager.current_state}"
    )

    # 断言: payload 中 current_level 为当前关卡数
    go_screen = gm.screen_manager.current_screen
    assert go_screen.current_level == 1, (
        f"current_level 应为 1，实际 {go_screen.current_level}"
    )

    _reset_singletons()
    print("[PASS] test_zero_hearts_triggers_game_over")


# =============================================================================
# 测试 3: 胜利判定在死亡判定之后的优先级（先死后胜）
# =============================================================================

def test_death_priority_over_victory():
    """当玩家同时满足死亡和胜利条件时，死亡判定优先。

    验证步骤:
    1. 启动探索关 Level 1
    2. 将玩家置于出口格，并将生命值设为 0
    3. 调用 update(0.1)
    4. 断言系统切换到 GameState.GAME_OVER（而非 LEVEL_COMPLETE）
    """
    _reset_singletons()
    gm, gs = _start_new_game()

    # 设置出口可用
    exit_x, exit_y = gs.exit_pos
    adj_x, adj_y = exit_x - 1, exit_y
    gs.game_map.layer0[adj_y][adj_x] = "UNCOVERED"
    gs.game_map.layer1[adj_y][adj_x] = "NONE"
    gs.game_map.layer0[exit_y][exit_x] = "UNCOVERED"
    gs.game_map.layer1[exit_y][exit_x] = "NONE"

    # 玩家在出口上但生命值为 0
    gs.interaction_controller.player_x = exit_x
    gs.interaction_controller.player_y = exit_y
    gm.player_state.current_hearts = 0

    gs.update(0.1)

    # 死亡应优先于胜利
    assert gm.screen_manager.current_state == GameState.GAME_OVER, (
        f"死亡应优先，期望 {GameState.GAME_OVER}，实际 {gm.screen_manager.current_state}"
    )

    _reset_singletons()
    print("[PASS] test_death_priority_over_victory")


# =============================================================================
# 测试 4: 未解锁出口不触发胜利（LOCK_EXIT 仍在）
# =============================================================================

def test_locked_exit_does_not_trigger_victory():
    """出口锁门未清除时，站在出口位置不触发胜利。"""
    _reset_singletons()
    gm, gs = _start_new_game()

    exit_x, exit_y = gs.exit_pos
    adj_x, adj_y = exit_x - 1, exit_y

    # 相邻格可步行，但出口仍为 LOCK_EXIT（不设为 NONE）
    gs.game_map.layer0[adj_y][adj_x] = "UNCOVERED"
    gs.game_map.layer1[adj_y][adj_x] = "NONE"

    # 玩家移动到出口相邻格
    gs.interaction_controller.player_x = adj_x
    gs.interaction_controller.player_y = adj_y

    # move_player 会因 LOCK_EXIT 阻挡而返回 "BLOCKED"
    # 直接强行设置位置到出口
    gs.interaction_controller.player_x = exit_x
    gs.interaction_controller.player_y = exit_y

    gs.update(0.1)

    # 断言：未触发胜利（LOCK_EXIT 仍在 layer1 中）
    assert gm.screen_manager.current_state != GameState.LEVEL_COMPLETE, (
        "LOCK_EXIT 未清除时不应触发胜利"
    )
    # 断言仍处于 PLAYING 状态
    assert gm.screen_manager.current_state == GameState.PLAYING, (
        f"应仍在 PLAYING，实际 {gm.screen_manager.current_state}"
    )

    _reset_singletons()
    print("[PASS] test_locked_exit_does_not_trigger_victory")


# =============================================================================
# 测试 5: 正血量不触发死亡
# =============================================================================

def test_positive_hearts_no_game_over():
    """玩家生命值大于 0 时不应触发 GAME_OVER。"""
    _reset_singletons()
    gm, gs = _start_new_game()

    # 玩家初始 3 心，不应死亡
    gs.update(0.1)

    assert gm.screen_manager.current_state != GameState.GAME_OVER, (
        "3 心时不应触发 GAME_OVER"
    )
    assert gm.screen_manager.current_state == GameState.PLAYING, (
        f"应仍在 PLAYING，实际 {gm.screen_manager.current_state}"
    )

    _reset_singletons()
    print("[PASS] test_positive_hearts_no_game_over")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    try:
        test_move_to_exit_triggers_level_complete()
        test_zero_hearts_triggers_game_over()
        test_death_priority_over_victory()
        test_locked_exit_does_not_trigger_victory()
        test_positive_hearts_no_game_over()
        print("\n=== ALL TESTS PASSED ===")
    finally:
        pygame.quit()
