"""GameOverScreen 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_game_over_screen.py` 直接运行。
使用 SDL dummy 驱动避免弹出实体窗口。
验证：有无护身符分支渲染、时空溯源算法、Rogue-lite 属性继承与重置落盘、状态机跳转。
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

from src.screens.game_over_screen import GameOverScreen
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
    gm.player_state.gold = 0
    gm.player_state.current_hearts = 3
    gm.player_state.max_hearts = 3
    gm.player_state.current_shields = 0
    gm.player_state.max_shields = 1
    gm.player_state.tools = {"pickaxe": 0, "dynamite": 0, "map": 0}
    gm.player_state.keys = {"RED": 0, "GREEN": 0, "BLUE": 0, "EXIT": 0}
    gm.player_state.bag_tier_index = 0
    gm.player_state.has_amulet = False
    gm.player_state.has_clover = False
    gm.player_state.has_machete = False
    gm.player_state.arrows = 0
    gm.player_state.highest_level_cleared = 0
    gm.player_state.total_gold_earned = 0
    return gm


def _find_button_by_action(screen, action: str):
    """根据 action 查找对应的按钮。"""
    for btn in screen.buttons:
        if getattr(btn, "action", None) == action:
            return btn
    return None


# ==========================================================================
# 测试
# ==========================================================================

def test_amulet_revive_path():
    """有护身符时：应显示复活按钮，点击后消耗护身符、满血、清空工具、跳转商店。"""
    gm = _reset_game_manager()

    # 设置存档记录
    save_calls = []

    def mock_save(player_data, settings_data=None):
        save_calls.append({"player": player_data, "settings": settings_data})
        return True

    gm.save_manager.save = mock_save

    # 设置玩家状态：500 金币、当前生命 0（上限 5）、有护身符、2 铁锹
    gm.player_state.gold = 500
    gm.player_state.current_hearts = 0
    gm.player_state.max_hearts = 5
    gm.player_state.has_amulet = True
    gm.player_state.tools = {"pickaxe": 2, "dynamite": 1, "map": 1}
    gm.player_state.keys = {"RED": 3, "GREEN": 0, "BLUE": 0, "EXIT": 0}

    screen = GameOverScreen()
    gm.screen_manager.register_screen(GameState.GAME_OVER, screen)
    gm.screen_manager.switch_screen(
        GameState.GAME_OVER,
        data_payload={"current_level": 3},
    )

    # 断言：有护身符时应显示 2 个按钮
    assert len(screen.buttons) == 2, f"应有 2 个按钮，实际 {len(screen.buttons)}"

    # 断言：存在 revive 按钮
    btn_revive = _find_button_by_action(screen, "revive")
    assert btn_revive is not None, "应有 revive 按钮"

    # 注册模拟 MUMMY_SHOP 屏幕
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

    # 模拟点击复活按钮
    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn_revive.rect.center},
    )
    screen.handle_event(click_event)

    # 断言：护身符变为 False
    assert gm.player_state.has_amulet is False, "护身符应被消耗"

    # 断言：复活次数增加
    assert gm.player_state.amulets_count == 1, "复活次数应为 1"

    # 断言：生命恢复为满值 5
    assert gm.player_state.current_hearts == 5, (
        f"生命应为 5，得到 {gm.player_state.current_hearts}"
    )

    # 断言：所有工具被清空
    assert gm.player_state.tools["pickaxe"] == 0, "铁锹应为 0"
    assert gm.player_state.tools["dynamite"] == 0, "炸药应为 0"
    assert gm.player_state.tools["map"] == 0, "地图应为 0"

    # 断言：钥匙被清空（purge_temporary_items）
    assert gm.player_state.keys["RED"] == 0, "钥匙应为 0"

    # 断言：时空溯源计算 — Level 3 死亡，shop_completed=1，next=2
    assert screen._calculate_respawn_level(3) == 2, (
        "Level 3 复活应回到 Level 2"
    )

    # 断言：save 被调用
    assert len(save_calls) == 1, f"save() 应被调用 1 次，实际 {len(save_calls)} 次"

    # 断言：路由到了 MUMMY_SHOP
    assert gm.screen_manager.current_state == GameState.MUMMY_SHOP, (
        f"应路由到 MUMMY_SHOP，实际为 {gm.screen_manager.current_state}"
    )

    # 断言：传给商店的 payload 正确
    assert mock_shop.enter_payload == {"next_level": 2}, (
        f"传给商店的 payload 应为 {{'next_level': 2}}，得到 {mock_shop.enter_payload}"
    )

    print("[PASS] test_amulet_revive_path")


def test_no_amulet_restart_path():
    """无护身符时：点击重整旗鼓应触发 Rogue-lite 重置，保留永久升级，跳转 PLAYING。"""
    gm = _reset_game_manager()

    # 设置存档记录
    save_calls = []

    def mock_save(player_data, settings_data=None):
        save_calls.append({"player": player_data, "settings": settings_data})
        return True

    gm.save_manager.save = mock_save

    # 设置玩家状态：500 金币、生命上限 5（当前 0）、背包等级 2、有工具、无护身符
    gm.player_state.gold = 500
    gm.player_state.current_hearts = 0
    gm.player_state.max_hearts = 5
    gm.player_state.bag_tier_index = 2
    gm.player_state.has_amulet = False
    gm.player_state.tools = {"pickaxe": 3, "dynamite": 2, "map": 1}
    gm.player_state.keys = {"RED": 1, "GREEN": 1, "BLUE": 0, "EXIT": 0}

    screen = GameOverScreen()
    gm.screen_manager.register_screen(GameState.GAME_OVER, screen)
    gm.screen_manager.switch_screen(
        GameState.GAME_OVER,
        data_payload={"current_level": 7},
    )

    # 断言：无护身符时应显示 2 个按钮
    assert len(screen.buttons) == 2, f"应有 2 个按钮，实际 {len(screen.buttons)}"

    # 断言：存在 restart 按钮
    btn_restart = _find_button_by_action(screen, "restart")
    assert btn_restart is not None, "应有 restart 按钮"

    # 注册模拟 PLAYING 屏幕
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

    # 模拟点击重整旗鼓按钮
    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn_restart.rect.center},
    )
    screen.handle_event(click_event)

    # 断言：金币变为 0
    assert gm.player_state.gold == 0, f"金币应为 0，得到 {gm.player_state.gold}"

    # 断言：工具全部变为 0
    assert gm.player_state.tools["pickaxe"] == 0, "铁锹应为 0"
    assert gm.player_state.tools["dynamite"] == 0, "炸药应为 0"
    assert gm.player_state.tools["map"] == 0, "地图应为 0"

    # 关键 Roguelite 继承断言：最大生命上限依然保持为 5
    assert gm.player_state.max_hearts == 5, (
        f"最大生命上限应保持为 5，得到 {gm.player_state.max_hearts}"
    )

    # 关键 Roguelite 继承断言：背包容量等级依然保持为 2
    assert gm.player_state.bag_tier_index == 2, (
        f"背包容量等级应保持为 2，得到 {gm.player_state.bag_tier_index}"
    )

    # 断言：当前生命满血
    assert gm.player_state.current_hearts == 5, (
        f"当前生命应为 5，得到 {gm.player_state.current_hearts}"
    )

    # 断言：save 被调用
    assert len(save_calls) == 1, f"save() 应被调用 1 次，实际 {len(save_calls)} 次"

    # 断言：路由到了 PLAYING
    assert gm.screen_manager.current_state == GameState.PLAYING, (
        f"应路由到 PLAYING，实际为 {gm.screen_manager.current_state}"
    )

    # 断言：传给 PLAYING 的 payload 正确
    assert mock_playing.enter_payload == {"level_num": 1, "continue": False}, (
        f"传给 PLAYING 的 payload 应为 {{'level_num': 1, 'continue': False}}，"
        f"得到 {mock_playing.enter_payload}"
    )

    print("[PASS] test_no_amulet_restart_path")


def test_exit_to_main_menu():
    """无护身符时：点击返回主菜单应触发 Rogue-lite 重置，跳转 MAIN_MENU。"""
    gm = _reset_game_manager()

    save_calls = []
    gm.save_manager.save = lambda p, s=None: (save_calls.append(1), True)[1]

    # 设置玩家状态：有金币、工具、无护身符
    gm.player_state.gold = 1000
    gm.player_state.max_hearts = 6
    gm.player_state.bag_tier_index = 3
    gm.player_state.has_amulet = False
    gm.player_state.tools = {"pickaxe": 5, "dynamite": 3, "map": 2}

    screen = GameOverScreen()
    gm.screen_manager.register_screen(GameState.GAME_OVER, screen)

    # 注册模拟 MAIN_MENU 屏幕
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

    gm.screen_manager.switch_screen(
        GameState.GAME_OVER,
        data_payload={"current_level": 7},
    )

    # 找到 exit_menu 按钮
    btn_exit = _find_button_by_action(screen, "exit_menu")
    assert btn_exit is not None, "应有 exit_menu 按钮"

    # 模拟点击
    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn_exit.rect.center},
    )
    screen.handle_event(click_event)

    # 断言：Rogue-lite 重置
    assert gm.player_state.gold == 0, "金币应重置为 0"
    assert gm.player_state.tools["pickaxe"] == 0, "工具应重置为 0"

    # 断言：永久属性保留
    assert gm.player_state.max_hearts == 6, "最大生命上限应保持为 6"
    assert gm.player_state.bag_tier_index == 3, "背包容量等级应保持为 3"

    # 断言：save 被调用
    assert len(save_calls) == 1, f"save() 应被调用 1 次，实际 {len(save_calls)} 次"

    # 断言：路由到了 MAIN_MENU
    assert gm.screen_manager.current_state == GameState.MAIN_MENU, (
        f"应路由到 MAIN_MENU，实际为 {gm.screen_manager.current_state}"
    )

    print("[PASS] test_exit_to_main_menu")


def test_temporal_algorithm():
    """时空溯源算法应正确计算复活目标关卡。"""
    # L <= 6: shop_completed = 1, next = 2
    assert GameOverScreen._calculate_respawn_level(1) == 2
    assert GameOverScreen._calculate_respawn_level(2) == 2
    assert GameOverScreen._calculate_respawn_level(6) == 2

    # L = 7: ((7-2)//5)*5 = (5//5)*5 = 5, next = 6
    assert GameOverScreen._calculate_respawn_level(7) == 6

    # L = 10: ((10-2)//5)*5 = (8//5)*5 = 5, next = 6
    assert GameOverScreen._calculate_respawn_level(10) == 6

    # L = 11: ((11-2)//5)*5 = (9//5)*5 = 5, next = 6
    assert GameOverScreen._calculate_respawn_level(11) == 6

    # L = 12: ((12-2)//5)*5 = (10//5)*5 = 10, next = 11
    assert GameOverScreen._calculate_respawn_level(12) == 11

    # L = 15: ((15-2)//5)*5 = (13//5)*5 = 10, next = 11
    assert GameOverScreen._calculate_respawn_level(15) == 11

    # L = 16: ((16-2)//5)*5 = (14//5)*5 = 10, next = 11
    assert GameOverScreen._calculate_respawn_level(16) == 11

    # L = 17: ((17-2)//5)*5 = (15//5)*5 = 15, next = 16
    assert GameOverScreen._calculate_respawn_level(17) == 16

    print("[PASS] test_temporal_algorithm")


def test_render_no_exception_with_amulet():
    """有护身符时 render 应不抛异常。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    gm.player_state.gold = 500
    gm.player_state.current_hearts = 0
    gm.player_state.max_hearts = 5
    gm.player_state.has_amulet = True

    screen = GameOverScreen()
    gm.screen_manager.register_screen(GameState.GAME_OVER, screen)
    gm.screen_manager.switch_screen(
        GameState.GAME_OVER,
        data_payload={"current_level": 3},
    )

    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.render(surface)

    print("[PASS] test_render_no_exception_with_amulet")


def test_render_no_exception_without_amulet():
    """无护身符时 render 应不抛异常。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    gm.player_state.gold = 500
    gm.player_state.current_hearts = 0
    gm.player_state.max_hearts = 5
    gm.player_state.has_amulet = False

    screen = GameOverScreen()
    gm.screen_manager.register_screen(GameState.GAME_OVER, screen)
    gm.screen_manager.switch_screen(
        GameState.GAME_OVER,
        data_payload={"current_level": 7},
    )

    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.render(surface)

    print("[PASS] test_render_no_exception_without_amulet")


def test_on_exit_clears_refs():
    """on_exit 应清空所有临时引用。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = GameOverScreen()
    gm.screen_manager.register_screen(GameState.GAME_OVER, screen)
    gm.screen_manager.switch_screen(
        GameState.GAME_OVER,
        data_payload={"current_level": 3},
    )

    screen.on_exit()

    assert screen.game_manager is None
    assert screen.screen_manager is None
    assert screen.asset_manager is None
    assert screen.buttons == []
    assert screen.font_title is None
    assert screen.font_info is None
    assert screen.sound_click is None

    print("[PASS] test_on_exit_clears_refs")


def test_no_revive_triggers_restart():
    """有护身符时点击"不复活，重头开始"应触发 Rogue-lite 重置，跳转 PLAYING。"""
    gm = _reset_game_manager()

    save_calls = []
    gm.save_manager.save = lambda p, s=None: (save_calls.append(1), True)[1]

    gm.player_state.gold = 800
    gm.player_state.max_hearts = 6
    gm.player_state.bag_tier_index = 1
    gm.player_state.has_amulet = True
    gm.player_state.tools = {"pickaxe": 2, "dynamite": 1, "map": 0}

    screen = GameOverScreen()
    gm.screen_manager.register_screen(GameState.GAME_OVER, screen)

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
        GameState.GAME_OVER,
        data_payload={"current_level": 5},
    )

    btn_no_revive = _find_button_by_action(screen, "no_revive")
    assert btn_no_revive is not None, "应有 no_revive 按钮"

    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn_no_revive.rect.center},
    )
    screen.handle_event(click_event)

    # 断言：Rogue-lite 重置
    assert gm.player_state.gold == 0, "金币应重置为 0"
    assert gm.player_state.tools["pickaxe"] == 0, "工具应重置为 0"

    # 断言：永久属性保留
    assert gm.player_state.max_hearts == 6, "最大生命上限应保持为 6"
    assert gm.player_state.bag_tier_index == 1, "背包容量等级应保持为 1"

    # 断言：路由到了 PLAYING
    assert gm.screen_manager.current_state == GameState.PLAYING
    assert mock_playing.enter_payload == {"level_num": 1, "continue": False}

    print("[PASS] test_no_revive_triggers_restart")


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        test_amulet_revive_path()
        test_no_amulet_restart_path()
        test_exit_to_main_menu()
        test_temporal_algorithm()
        test_render_no_exception_with_amulet()
        test_render_no_exception_without_amulet()
        test_on_exit_clears_refs()
        test_no_revive_triggers_restart()

        print("\n=== ALL TESTS PASSED ===")
    finally:
        # 仅重置单例，不调用 pygame.quit()
        GameManager._instance = None
        AssetManager._instance = None
