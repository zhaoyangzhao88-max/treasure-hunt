"""StatsScreen 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_stats_screen.py` 直接运行。
使用 SDL dummy 驱动避免弹出实体窗口。
验证：进入数据读取、勋章评估边界（青铜/白银/黄金/锁定）、返回按钮路由、渲染无崩溃。
"""

import os
import sys

# 设置 headless 驱动必须在 pygame.init() 之前
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# 确保能找到 src/ 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 初始化 Pygame（display + font + mixer）— 仅初始化一次
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

from src.screens.stats_screen import StatsScreen, _ACHIEVEMENTS
from src.screens.base_screen import BaseScreen
from src.game_manager import GameManager
from src.asset_manager import AssetManager
from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------

def _reset_game_manager():
    """重置 GameManager 单例并初始化引擎，返回 gm。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)
    # 重置 player_state 为干净的初始状态
    gm.player_state.gold = 0
    gm.player_state.current_hearts = 3
    gm.player_state.max_hearts = 3
    gm.player_state.current_shields = 0
    gm.player_state.max_shields = 1
    gm.player_state.tools = {"pickaxe": 0, "dynamite": 0, "map": 0}
    gm.player_state.keys = {"RED": 0, "GREEN": 0, "BLUE": 0, "EXIT": 0}
    gm.player_state.bag_tier_index = 0
    gm.player_state.has_amulet = False
    gm.player_state.highest_level_cleared = 0
    gm.player_state.total_gold_earned = 0
    gm.player_state.total_runs = 0
    gm.player_state.total_monsters_slain = 0
    return gm


class MockSound:
    """静默音效 Mock — play() 不执行任何操作。"""

    def play(self, *a, **kw):
        pass


# --------------------------------------------------------------------------
# 测试
# --------------------------------------------------------------------------

def test_on_enter_reads_four_stats():
    """进入 StatsScreen 时应从 player_state 提取 4 项历史数据。"""
    gm = _reset_game_manager()
    gm.player_state.total_gold_earned = 12345
    gm.player_state.total_monsters_slain = 25
    gm.player_state.total_runs = 7
    gm.player_state.highest_level_cleared = 9

    screen = StatsScreen()
    gm.screen_manager.register_screen(GameState.STATS, screen)
    gm.screen_manager.switch_screen(GameState.STATS)

    assert screen.gold_earned == 12345, "应读取 total_gold_earned"
    assert screen.monsters_slain == 25, "应读取 total_monsters_slain"
    assert screen.runs == 7, "应读取 total_runs"
    assert screen.highest_level == 9, "应读取 highest_level_cleared"
    assert len(screen.achievement_results) == 4, "应评估 4 大勋章"
    assert screen.btn_back is not None, "返回按钮应存在"
    assert len(screen.buttons) == 1, "应包含 1 个按钮（返回）"

    print("[PASS] test_on_enter_reads_four_stats")


def test_evaluate_achievement_gold_tiers():
    """金币勋章（Gold Rush）的 4 个临界点边界断言。"""
    screen = StatsScreen()
    tiers = [5000, 20000, 50000]

    # 0 → LOCKED，下一阶 5000
    tier, goal = screen._evaluate_achievement(0, tiers)
    assert tier == "LOCKED" and goal == 5000, f"value=0 应 LOCKED/5000，实际 {tier}/{goal}"

    # 6000 → BRONZE，下一阶 20000
    tier, goal = screen._evaluate_achievement(6000, tiers)
    assert tier == "BRONZE" and goal == 20000, f"value=6000 应 BRONZE/20000，实际 {tier}/{goal}"

    # 25000 → SILVER，下一阶 50000
    tier, goal = screen._evaluate_achievement(25000, tiers)
    assert tier == "SILVER" and goal == 50000, f"value=25000 应 SILVER/50000，实际 {tier}/{goal}"

    # 60000 → GOLD，封顶 -1
    tier, goal = screen._evaluate_achievement(60000, tiers)
    assert tier == "GOLD" and goal == -1, f"value=60000 应 GOLD/-1，实际 {tier}/{goal}"

    # 精确边界：恰好等于 tiers[0]
    tier, goal = screen._evaluate_achievement(5000, tiers)
    assert tier == "BRONZE" and goal == 20000, f"value=5000 应 BRONZE/20000，实际 {tier}/{goal}"

    # 精确边界：恰好等于 tiers[2]
    tier, goal = screen._evaluate_achievement(50000, tiers)
    assert tier == "GOLD" and goal == -1, f"value=50000 应 GOLD/-1，实际 {tier}/{goal}"

    print("[PASS] test_evaluate_achievement_gold_tiers")


def test_evaluate_achievement_runs_and_monsters_boundary():
    """runs 与 monsters 勋章的段位临界点边界断言。"""
    screen = StatsScreen()

    # Persistent Pioneer: tiers [5, 20, 80]
    runs_tiers = [a["tiers"] for a in _ACHIEVEMENTS if a["key"] == "runs"][0]
    tier, goal = screen._evaluate_achievement(5, runs_tiers)
    assert tier == "BRONZE" and goal == 20, f"runs=5 应 BRONZE/20，实际 {tier}/{goal}"
    tier, goal = screen._evaluate_achievement(80, runs_tiers)
    assert tier == "GOLD" and goal == -1, f"runs=80 应 GOLD/-1，实际 {tier}/{goal}"

    # Mummy Hunter: tiers [10, 50, 200]
    mon_tiers = [a["tiers"] for a in _ACHIEVEMENTS if a["key"] == "monsters_slain"][0]
    tier, goal = screen._evaluate_achievement(200, mon_tiers)
    assert tier == "GOLD" and goal == -1, f"monsters=200 应 GOLD/-1，实际 {tier}/{goal}"
    tier, goal = screen._evaluate_achievement(9, mon_tiers)
    assert tier == "LOCKED" and goal == 10, f"monsters=9 应 LOCKED/10，实际 {tier}/{goal}"

    print("[PASS] test_evaluate_achievement_runs_and_monsters_boundary")


def test_back_button_routes_to_main_menu():
    """点击返回按钮应切回 GameState.MAIN_MENU。"""
    gm = _reset_game_manager()

    screen = StatsScreen()
    gm.screen_manager.register_screen(GameState.STATS, screen)

    # 注册一个 mock MAIN_MENU 屏幕以捕获路由
    class MockMainMenu(BaseScreen):
        def __init__(self):
            self.entered = False
            self.enter_payload = None

        def on_enter(self, data_payload=None):
            self.entered = True
            self.enter_payload = data_payload

        def on_exit(self):
            pass

        def handle_event(self, event):
            pass

        def update(self, dt):
            pass

        def render(self, surface):
            pass

    mock_main = MockMainMenu()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, mock_main)

    gm.screen_manager.switch_screen(GameState.STATS)
    assert gm.screen_manager.current_state == GameState.STATS

    # 模拟点击返回按钮中心
    screen.sound_click = MockSound()
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": screen.btn_back.rect.center},
    )
    screen.handle_event(click_event)

    assert gm.screen_manager.current_state == GameState.MAIN_MENU, (
        f"点击返回后应切回 MAIN_MENU，实际 {gm.screen_manager.current_state}"
    )
    assert mock_main.entered, "MAIN_MENU 屏幕应被进入"

    print("[PASS] test_back_button_routes_to_main_menu")


def test_render_no_exception():
    """渲染不应抛异常（无崩溃）。"""
    gm = _reset_game_manager()
    gm.player_state.total_gold_earned = 99999
    gm.player_state.total_monsters_slain = 300
    gm.player_state.total_runs = 100
    gm.player_state.highest_level_cleared = 50

    screen = StatsScreen()
    gm.screen_manager.register_screen(GameState.STATS, screen)
    gm.screen_manager.switch_screen(GameState.STATS)

    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.render(surface)  # 不应抛异常

    print("[PASS] test_render_no_exception")


def test_achievements_definition_four():
    """应定义 4 大勋章且字段完整。"""
    assert len(_ACHIEVEMENTS) == 4, "应定义 4 大勋章"
    keys = [a["key"] for a in _ACHIEVEMENTS]
    assert "gold_earned" in keys
    assert "monsters_slain" in keys
    assert "highest_level" in keys
    assert "runs" in keys
    for a in _ACHIEVEMENTS:
        assert "name" in a and "tiers" in a
        assert len(a["tiers"]) == 3, f"{a['name']} 应有 3 个段位阶梯"

    print("[PASS] test_achievements_definition_four")


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------

if __name__ == "__main__":
    test_on_enter_reads_four_stats()
    test_evaluate_achievement_gold_tiers()
    test_evaluate_achievement_runs_and_monsters_boundary()
    test_back_button_routes_to_main_menu()
    test_render_no_exception()
    test_achievements_definition_four()
    print("\n[ALL PASS] StatsScreen 全部测试通过")
