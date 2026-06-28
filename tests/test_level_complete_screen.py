"""LevelCompleteScreen 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_level_complete_screen.py` 直接运行。
使用 SDL dummy 驱动避免弹出实体窗口。
验证：结算显示、自动保存、智能路由跳转、无崩溃渲染。
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

from src.screens.level_complete_screen import LevelCompleteScreen
from src.screens.base_screen import BaseScreen
from src.game_manager import GameManager
from src.asset_manager import AssetManager
from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------

def _reset_game_manager():
    """重置 GameManager 和 AssetManager 单例，并初始化引擎。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)
    # 重置 player_state 为干净的初始状态
    gm.player_state.highest_level_cleared = 0
    gm.player_state.total_gold_earned = 0
    gm.player_state.gold = 0
    gm.player_state.current_hearts = 3
    gm.player_state.max_hearts = 3
    gm.player_state.current_shields = 0
    gm.player_state.max_shields = 1
    gm.player_state.tools = {"pickaxe": 0, "dynamite": 0, "map": 0}
    gm.player_state.keys = {"RED": 0, "GREEN": 0, "BLUE": 0, "EXIT": 0}
    gm.player_state.bag_tier_index = 0
    return gm


# ==========================================================================
# 测试
# ==========================================================================

def test_on_enter_save_called_and_state_updated():
    """on_enter 应调用 save() 并正确更新 highest_level_cleared / total_gold_earned。"""
    gm = _reset_game_manager()

    # Mock save() 记录调用
    save_calls = []
    original_save = gm.save_manager.save

    def mock_save(player_data, settings_data=None):
        save_calls.append({"player": player_data, "settings": settings_data})
        return True

    gm.save_manager.save = mock_save

    screen = LevelCompleteScreen()
    gm.screen_manager.register_screen(GameState.LEVEL_COMPLETE, screen)
    gm.screen_manager.switch_screen(
        GameState.LEVEL_COMPLETE,
        data_payload={
            "completed_level": 1,
            "gold_earned": 150,
            "remaining_hearts": 3,
            "remaining_shields": 1,
        },
    )

    # 断言 save 被调用
    assert len(save_calls) == 1, f"save() 应被调用 1 次，实际 {len(save_calls)} 次"

    # 断言存档数据正确
    player_data = save_calls[0]["player"]
    assert player_data["highest_level_cleared"] == 1, (
        f"highest_level_cleared 应为 1，得到 {player_data['highest_level_cleared']}"
    )
    assert player_data["total_gold_earned"] == 150, (
        f"total_gold_earned 应为 150，得到 {player_data['total_gold_earned']}"
    )

    # 断言内存状态正确
    assert gm.player_state.highest_level_cleared == 1
    assert gm.player_state.total_gold_earned == 150

    # 恢复
    gm.save_manager.save = original_save
    print("[PASS] test_on_enter_save_called_and_state_updated")


def test_level1_next_level_routes_to_shop():
    """第 1 关通关后，点击"继续下一关"应路由到 MUMMY_SHOP。"""
    gm = _reset_game_manager()

    # Mock save
    gm.save_manager.save = lambda p, s=None: True

    screen = LevelCompleteScreen()
    gm.screen_manager.register_screen(GameState.LEVEL_COMPLETE, screen)

    # 注册模拟目标屏幕
    class MockShop(BaseScreen):
        def __init__(self):
            self.enter_payload = None
        def on_enter(self, data_payload=None):
            self.enter_payload = data_payload
        def on_exit(self): pass
        def handle_event(self, event): pass
        def update(self, dt): pass
        def render(self, surface): pass

    mock_shop = MockShop()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, mock_shop)

    # 进入结算界面（Level 1 通关）
    gm.screen_manager.switch_screen(
        GameState.LEVEL_COMPLETE,
        data_payload={
            "completed_level": 1,
            "gold_earned": 150,
            "remaining_hearts": 3,
            "remaining_shields": 1,
        },
    )

    # 模拟点击"继续下一关"按钮
    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    btn = screen.btn_next_level
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    # 断言路由到了 MUMMY_SHOP
    assert gm.screen_manager.current_state == GameState.MUMMY_SHOP, (
        f"Level 1 后应路由到 MUMMY_SHOP，实际为 {gm.screen_manager.current_state}"
    )
    assert mock_shop.enter_payload == {"next_level": 2}, (
        f"传给商店的 payload 应为 {{'next_level': 2}}，得到 {mock_shop.enter_payload}"
    )

    print("[PASS] test_level1_next_level_routes_to_shop")


def test_level2_next_level_routes_to_playing():
    """第 2 关通关后，点击"继续下一关"应路由到 PLAYING（level_num=3）。"""
    gm = _reset_game_manager()

    # Mock save
    gm.save_manager.save = lambda p, s=None: True

    screen = LevelCompleteScreen()
    gm.screen_manager.register_screen(GameState.LEVEL_COMPLETE, screen)

    # 注册模拟目标屏幕
    class MockPlaying(BaseScreen):
        def __init__(self):
            self.enter_payload = None
        def on_enter(self, data_payload=None):
            self.enter_payload = data_payload
        def on_exit(self): pass
        def handle_event(self, event): pass
        def update(self, dt): pass
        def render(self, surface): pass

    mock_playing = MockPlaying()
    gm.screen_manager.register_screen(GameState.PLAYING, mock_playing)

    # 进入结算界面（Level 2 通关）
    gm.screen_manager.switch_screen(
        GameState.LEVEL_COMPLETE,
        data_payload={
            "completed_level": 2,
            "gold_earned": 80,
            "remaining_hearts": 2,
            "remaining_shields": 0,
        },
    )

    # 模拟点击"继续下一关"按钮
    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    btn = screen.btn_next_level
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    # 断言路由到了 PLAYING
    assert gm.screen_manager.current_state == GameState.PLAYING, (
        f"Level 2 后应路由到 PLAYING，实际为 {gm.screen_manager.current_state}"
    )
    assert mock_playing.enter_payload == {"level_num": 3, "continue": True}, (
        f"传给 PLAYING 的 payload 应为 {{'level_num': 3, 'continue': True}}，"
        f"得到 {mock_playing.enter_payload}"
    )

    print("[PASS] test_level2_next_level_routes_to_playing")


def test_save_exit_routes_to_main_menu():
    """点击"保存并返回菜单"应路由到 MAIN_MENU。"""
    gm = _reset_game_manager()

    # Mock save
    gm.save_manager.save = lambda p, s=None: True

    screen = LevelCompleteScreen()
    gm.screen_manager.register_screen(GameState.LEVEL_COMPLETE, screen)

    # 注册模拟主菜单
    class MockMainMenu(BaseScreen):
        def __init__(self):
            self.enter_payload = None
        def on_enter(self, data_payload=None):
            self.enter_payload = data_payload
        def on_exit(self): pass
        def handle_event(self, event): pass
        def update(self, dt): pass
        def render(self, surface): pass

    mock_menu = MockMainMenu()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, mock_menu)

    # 进入结算界面
    gm.screen_manager.switch_screen(
        GameState.LEVEL_COMPLETE,
        data_payload={
            "completed_level": 3,
            "gold_earned": 100,
            "remaining_hearts": 2,
            "remaining_shields": 1,
        },
    )

    # 模拟点击"保存并返回菜单"按钮
    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    btn = screen.btn_save_exit
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    # 断言路由到了 MAIN_MENU
    assert gm.screen_manager.current_state == GameState.MAIN_MENU, (
        f"Save & Exit 应路由到 MAIN_MENU，实际为 {gm.screen_manager.current_state}"
    )

    print("[PASS] test_save_exit_routes_to_main_menu")


def test_level5_routes_to_shop():
    """第 5 关通关后（5 % 5 == 0），应路由到 MUMMY_SHOP。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = LevelCompleteScreen()
    gm.screen_manager.register_screen(GameState.LEVEL_COMPLETE, screen)

    class MockShop(BaseScreen):
        def __init__(self):
            self.enter_payload = None
        def on_enter(self, data_payload=None):
            self.enter_payload = data_payload
        def on_exit(self): pass
        def handle_event(self, event): pass
        def update(self, dt): pass
        def render(self, surface): pass

    mock_shop = MockShop()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, mock_shop)

    gm.screen_manager.switch_screen(
        GameState.LEVEL_COMPLETE,
        data_payload={
            "completed_level": 5,
            "gold_earned": 200,
            "remaining_hearts": 1,
            "remaining_shields": 0,
        },
    )

    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    btn = screen.btn_next_level
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    assert gm.screen_manager.current_state == GameState.MUMMY_SHOP, (
        f"Level 5 后应路由到 MUMMY_SHOP，实际为 {gm.screen_manager.current_state}"
    )
    assert mock_shop.enter_payload == {"next_level": 6}, (
        f"传给商店的 payload 应为 {{'next_level': 6}}，得到 {mock_shop.enter_payload}"
    )

    print("[PASS] test_level5_routes_to_shop")


def test_level3_routes_to_playing():
    """第 3 关通关后（非商店触发），应路由到 PLAYING（level_num=4）。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = LevelCompleteScreen()
    gm.screen_manager.register_screen(GameState.LEVEL_COMPLETE, screen)

    class MockPlaying(BaseScreen):
        def __init__(self):
            self.enter_payload = None
        def on_enter(self, data_payload=None):
            self.enter_payload = data_payload
        def on_exit(self): pass
        def handle_event(self, event): pass
        def update(self, dt): pass
        def render(self, surface): pass

    mock_playing = MockPlaying()
    gm.screen_manager.register_screen(GameState.PLAYING, mock_playing)

    gm.screen_manager.switch_screen(
        GameState.LEVEL_COMPLETE,
        data_payload={
            "completed_level": 3,
            "gold_earned": 90,
            "remaining_hearts": 2,
            "remaining_shields": 1,
        },
    )

    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    btn = screen.btn_next_level
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    assert gm.screen_manager.current_state == GameState.PLAYING, (
        f"Level 3 后应路由到 PLAYING，实际为 {gm.screen_manager.current_state}"
    )
    assert mock_playing.enter_payload == {"level_num": 4, "continue": True}, (
        f"传给 PLAYING 的 payload 应为 {{'level_num': 4, 'continue': True}}，"
        f"得到 {mock_playing.enter_payload}"
    )

    print("[PASS] test_level3_routes_to_playing")


def test_render_no_exception():
    """render 应不抛异常。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = LevelCompleteScreen()
    gm.screen_manager.register_screen(GameState.LEVEL_COMPLETE, screen)
    gm.screen_manager.switch_screen(
        GameState.LEVEL_COMPLETE,
        data_payload={
            "completed_level": 2,
            "gold_earned": 80,
            "remaining_hearts": 2,
            "remaining_shields": 0,
        },
    )

    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.render(surface)

    print("[PASS] test_render_no_exception")


def test_on_exit_clears_refs():
    """on_exit 应清空所有临时引用。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = LevelCompleteScreen()
    gm.screen_manager.register_screen(GameState.LEVEL_COMPLETE, screen)
    gm.screen_manager.switch_screen(
        GameState.LEVEL_COMPLETE,
        data_payload={
            "completed_level": 1,
            "gold_earned": 100,
            "remaining_hearts": 3,
            "remaining_shields": 1,
        },
    )

    screen.on_exit()

    assert screen.game_manager is None
    assert screen.screen_manager is None
    assert screen.asset_manager is None
    assert screen.buttons == []
    assert screen.btn_next_level is None
    assert screen.btn_save_exit is None
    assert screen.font_title is None
    assert screen.font_stats is None
    assert screen.sound_click is None

    print("[PASS] test_on_exit_clears_refs")


def test_highest_level_not_downgraded():
    """若 completed_level <= 已保存的 highest_level_cleared，不应降级。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    # 设置已通关记录为 5
    gm.player_state.highest_level_cleared = 5
    gm.player_state.total_gold_earned = 500

    screen = LevelCompleteScreen()
    gm.screen_manager.register_screen(GameState.LEVEL_COMPLETE, screen)
    gm.screen_manager.switch_screen(
        GameState.LEVEL_COMPLETE,
        data_payload={
            "completed_level": 3,
            "gold_earned": 50,
            "remaining_hearts": 2,
            "remaining_shields": 0,
        },
    )

    # highest_level_cleared 应保持为 5（不降级）
    assert gm.player_state.highest_level_cleared == 5, (
        f"highest_level_cleared 不应降级，期望 5，得到 {gm.player_state.highest_level_cleared}"
    )
    # total_gold_earned 应累加
    assert gm.player_state.total_gold_earned == 550, (
        f"total_gold_earned 应为 550，得到 {gm.player_state.total_gold_earned}"
    )

    print("[PASS] test_highest_level_not_downgraded")


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        test_on_enter_save_called_and_state_updated()
        test_level1_next_level_routes_to_shop()
        test_level2_next_level_routes_to_playing()
        test_save_exit_routes_to_main_menu()
        test_level5_routes_to_shop()
        test_level3_routes_to_playing()
        test_render_no_exception()
        test_on_exit_clears_refs()
        test_highest_level_not_downgraded()

        print("\n=== ALL TESTS PASSED ===")
    finally:
        # 仅重置单例，不调用 pygame.quit()
        # （SDL dummy 驱动在进程退出时自动清理，
        #   显式 pygame.quit() 会导致段错误）
        GameManager._instance = None
        AssetManager._instance = None
