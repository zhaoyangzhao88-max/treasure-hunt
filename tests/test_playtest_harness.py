"""全自动 AI 仿真探险测试沙盒 (PlaytestHarness) 单元测试 — Microsoft Treasure Hunt

验证 PlaytestHarness 在 Headless 模式下可以自动推进场景切换、
AI 探索、商店购买和死亡路由，且全程 100% 零崩溃。
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

from src.game_manager import GameManager
from src.playtest_harness import PlaytestHarness
from src.config import GameState, BAG_CAPACITY_TIERS


# =========================================================================
# 辅助函数
# =========================================================================

def _reset_singletons():
    """重置全局单例，确保测试隔离。"""
    GameManager._instance = None


def _make_harness(max_levels: int = 5) -> tuple:
    """创建并返回 (GameManager, PlaytestHarness) 测试对。

    Args:
        max_levels: 最大通关关卡数

    Returns:
        (gm, harness) 元组
    """
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)
    harness = PlaytestHarness(gm, max_levels=max_levels)
    return gm, harness


# =========================================================================
# 测试 1: 主菜单 → 游戏场景的全自动切换
# =========================================================================

def test_harness_main_menu_to_playing():
    """验证 Harness 能从 MAIN_MENU 正确切换到 PLAYING 状态。"""
    _reset_singletons()
    gm, harness = _make_harness()

    # 初始状态应为 None（init_engine 后无活跃场景）
    assert gm.screen_manager.current_state is None, \
        "初始状态应为 None"

    # 第 1 步：自动切换到 MAIN_MENU
    result = harness.step_simulation()
    assert result == "INIT", f"期望 INIT，实际 {result}"
    assert gm.screen_manager.current_state == GameState.MAIN_MENU, \
        f"应为 MAIN_MENU，实际 {gm.screen_manager.current_state}"

    # 第 2 步：模拟点击"开始新游戏"
    result = harness.step_simulation()
    assert result == "START_NEW_GAME", f"期望 START_NEW_GAME，实际 {result}"
    assert gm.screen_manager.current_state == GameState.PLAYING, \
        f"应为 PLAYING，实际 {gm.screen_manager.current_state}"
    assert harness.runs_played == 1, \
        "开局计数器应递增"

    # 清理
    GameManager._instance = None
    print("[PASS] test_harness_main_menu_to_playing")


# =========================================================================
# 测试 2: AI 探索 30 步无崩溃
# =========================================================================

def test_harness_ai_exploring_no_crash():
    """验证 AI 在 PLAYING 状态下能运行 30 步而不崩溃。"""
    _reset_singletons()
    gm, harness = _make_harness()

    # 先切换到 PLAYING
    harness.step_simulation()  # INIT
    harness.step_simulation()  # START_NEW_GAME

    assert gm.screen_manager.current_state == GameState.PLAYING

    # 运行 30 步 AI 探索
    for step in range(30):
        result = harness.step_simulation()
        # AI 探索可能返回 EXPLORING / NO_SOLVER / NO_CTRL
        # 在切换场景前始终在 PLAYING
        assert result in ("EXPLORING", "NO_SOLVER", "NO_CTRL"), \
            f"第 {step + 1} 步结果异常: {result}"
        # 确保没有发生渲染或碰撞崩溃（只要不抛异常即为通过）

    # 清理
    GameManager._instance = None
    print("[PASS] test_harness_ai_exploring_no_crash")


# =========================================================================
# 测试 3: 商店 AI 智能购物
# =========================================================================

def test_harness_shop_ai_buy():
    """验证商店 AI 能自动购买物资并离开。"""
    _reset_singletons()
    gm, harness = _make_harness()

    ps = gm.player_state

    # 设置玩家金币和背包状态
    ps.gold = 200
    ps.tools["pickaxe"] = 0
    ps.tools["dynamite"] = 0
    ps.current_shields = 0
    # 默认 max_capacity = BAG_CAPACITY_TIERS[0] = 2
    # 默认 max_shields = 1

    # 手动切换到 MUMMY_SHOP
    gm.screen_manager.switch_screen(
        GameState.MUMMY_SHOP,
        data_payload={"next_level": 2},
    )
    assert gm.screen_manager.current_state == GameState.MUMMY_SHOP

    # 执行自动购物
    result = harness.step_simulation()
    assert result == "SHOPPING", f"期望 SHOPPING，实际 {result}"

    # 验证购买成功
    assert ps.tools.get("pickaxe", 0) >= 1, \
        f"应至少购买 1 把铁锹，实际 {ps.tools.get('pickaxe', 0)}"
    assert ps.tools.get("dynamite", 0) >= 1, \
        f"应至少购买 1 个炸药，实际 {ps.tools.get('dynamite', 0)}"

    # 金币应扣减（至少花掉 50+75=125）
    assert ps.gold <= 200 - 50 - 75, \
        f"金币应扣减至少 125，剩余 {ps.gold}"

    # 离开商店后应切换到 PLAYING（next_level=2）
    # 注：因离开按钮被点击后场景即时切换，当前状态已变
    assert gm.screen_manager.current_state == GameState.PLAYING, \
        f"离开商店后应为 PLAYING，实际 {gm.screen_manager.current_state}"

    # 清理
    GameManager._instance = None
    print("[PASS] test_harness_shop_ai_buy")


# =========================================================================
# 测试 4: 死亡路由 — 无护身符（Rogue-lite 重置）
# =========================================================================

def test_harness_death_routing_no_amulet():
    """验证无护身符死亡后正确 Rogue-lite 重置回 Level 1。"""
    _reset_singletons()
    gm, harness = _make_harness()

    ps = gm.player_state

    # 确保无护身符
    ps.has_amulet = False
    ps.gold = 100
    ps.current_hearts = 3

    # 手动切换到 GAME_OVER
    gm.screen_manager.switch_screen(
        GameState.GAME_OVER,
        data_payload={"current_level": 5},
    )
    assert gm.screen_manager.current_state == GameState.GAME_OVER

    # 执行死亡路由
    result = harness.step_simulation()
    assert result == "DIED", f"期望 DIED，实际 {result}"

    # 验证重置到了 PLAYING（Level 1）
    assert gm.screen_manager.current_state == GameState.PLAYING, \
        f"重置后应为 PLAYING，实际 {gm.screen_manager.current_state}"

    # 验证 Rogue-lite 重置后的关键属性保留和重置语义
    # 金币应归零（从未拾取）
    assert ps.gold == 0, f"重置后金币应为 0，实际 {ps.gold}"
    # 红心应填满
    assert ps.current_hearts == ps.max_hearts, \
        f"重置后应满血，实际 {ps.current_hearts}/{ps.max_hearts}"

    # 清理
    GameManager._instance = None
    print("[PASS] test_harness_death_routing_no_amulet")


# =========================================================================
# 测试 5: 死亡路由 — 有护身符（复活）
# =========================================================================

def test_harness_death_routing_with_amulet():
    """验证有护身符死亡后正确消耗护身符并跳转商店。"""
    _reset_singletons()
    gm, harness = _make_harness()

    ps = gm.player_state

    # 设置护身符
    ps.has_amulet = True
    ps.current_hearts = 1  # 残血
    ps.tools["pickaxe"] = 1
    ps.tools["dynamite"] = 1

    # 手动切换到 GAME_OVER
    gm.screen_manager.switch_screen(
        GameState.GAME_OVER,
        data_payload={"current_level": 5},
    )
    assert gm.screen_manager.current_state == GameState.GAME_OVER

    # 执行复活路由
    result = harness.step_simulation()
    assert result == "DIED_REVIVED", f"期望 DIED_REVIVED，实际 {result}"

    # 验证复活后场景变化：应跳转到 MUMMY_SHOP
    assert gm.screen_manager.current_state == GameState.MUMMY_SHOP, \
        f"复活后应为 MUMMY_SHOP，实际 {gm.screen_manager.current_state}"

    # 护身符应被消耗
    assert not ps.has_amulet, "护身符应已被消耗"

    # 应满血
    assert ps.current_hearts == ps.max_hearts, \
        f"复活后应满血，实际 {ps.current_hearts}/{ps.max_hearts}"

    # 消耗品应被清空（复活惩罚）
    assert ps.tools.get("pickaxe", 0) == 0, "铁锹应被清空"
    assert ps.tools.get("dynamite", 0) == 0, "炸药应被清空"

    # 清理
    GameManager._instance = None
    print("[PASS] test_harness_death_routing_with_amulet")


# =========================================================================
# 全部测试入口
# =========================================================================

if __name__ == "__main__":
    try:
        test_harness_main_menu_to_playing()
        test_harness_ai_exploring_no_crash()
        test_harness_shop_ai_buy()
        test_harness_death_routing_no_amulet()
        test_harness_death_routing_with_amulet()
        print("\n=== ALL PLAYTEST HARNESS TESTS PASSED ===")
    finally:
        GameManager._instance = None
