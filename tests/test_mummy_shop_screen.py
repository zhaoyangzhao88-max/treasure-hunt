"""MummyShopScreen 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_mummy_shop_screen.py` 直接运行。
使用 SDL dummy 驱动避免弹出实体窗口。
验证：商品列表渲染、购买约束判定、金币扣除、自动存盘、离开路由跳转。
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

from src.screens.mummy_shop_screen import MummyShopScreen, SHOP_ITEMS
from src.screens.base_screen import BaseScreen
from src.game_manager import GameManager
from src.asset_manager import AssetManager
from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT, HARD_CAP_HEARTS


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
    gm.player_state.highest_level_cleared = 0
    gm.player_state.total_gold_earned = 0
    return gm


def _find_button_by_item_id(screen, item_id: str):
    """根据 item_id 查找对应的按钮。"""
    for btn in screen.buttons:
        if getattr(btn, "item_id", None) == item_id:
            return btn
    return None


# ==========================================================================
# 测试
# ==========================================================================

def test_on_enter_records_next_level():
    """on_enter 应正确记录 next_level 参数。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(
        GameState.MUMMY_SHOP,
        data_payload={"next_level": 3},
    )

    assert screen.next_level_num == 3, (
        f"next_level_num 应为 3，得到 {screen.next_level_num}"
    )

    print("[PASS] test_on_enter_records_next_level")


def test_on_enter_default_next_level():
    """on_enter 无参数时，next_level 默认为 2。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP)

    assert screen.next_level_num == 2, (
        f"默认 next_level_num 应为 2，得到 {screen.next_level_num}"
    )

    print("[PASS] test_on_enter_default_next_level")


def test_buy_shield():
    """金币充裕时购买护盾，应扣金币、加护盾、触发存盘。"""
    gm = _reset_game_manager()

    # 记录 save 调用
    save_calls = []
    original_save = gm.save_manager.save

    def mock_save(player_data, settings_data=None):
        save_calls.append({"player": player_data, "settings": settings_data})
        return True

    gm.save_manager.save = mock_save

    # 设置充裕金币
    gm.player_state.gold = 1000
    gm.player_state.current_shields = 0
    gm.player_state.max_shields = 1

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    # 找到护盾 Buy 按钮并点击
    btn = _find_button_by_item_id(screen, "shield")
    assert btn is not None, "应存在护盾 Buy 按钮"
    assert btn.is_enabled is True, "护盾按钮应可点击"

    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    # 断言金币减少（护盾价格 = max_shields * 75 = 1 * 75 = 75）
    assert gm.player_state.gold == 925, (
        f"金币应为 925，得到 {gm.player_state.gold}"
    )
    # 断言护盾满充
    assert gm.player_state.current_shields == 1, (
        f"护盾应为 1，得到 {gm.player_state.current_shields}"
    )
    # 断言 save 被调用
    assert len(save_calls) == 1, f"save() 应被调用 1 次，实际 {len(save_calls)} 次"

    # 恢复
    gm.save_manager.save = original_save
    print("[PASS] test_buy_shield")


def test_buy_pickaxe_and_capacity_limit():
    """购买铁锹受背包容量限制，满容量后按钮置灰。"""
    gm = _reset_game_manager()
    save_calls = []
    gm.save_manager.save = lambda p, s=None: (save_calls.append(1), True)[1]

    # 设置：1000 金币，容量 2，当前 0 工具
    gm.player_state.gold = 1000
    gm.player_state.bag_tier_index = 0  # capacity = 2
    gm.player_state.tools = {"pickaxe": 0, "dynamite": 0, "map": 0}

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    btn = _find_button_by_item_id(screen, "pickaxe")
    assert btn is not None
    assert btn.is_enabled is True, "初始铁锹按钮应可点击"

    # 买第一个铁锹
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)
    assert gm.player_state.tools["pickaxe"] == 1, "铁锹应为 1"
    assert gm.player_state.gold == 950, "金币应为 950"

    # 刷新按钮状态
    screen.refresh_shop_buttons()
    btn = _find_button_by_item_id(screen, "pickaxe")
    assert btn.is_enabled is True, "容量仍有空间，按钮应可点击"

    # 买第二个铁锹（达到容量上限 2）
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)
    assert gm.player_state.tools["pickaxe"] == 2, "铁锹应为 2"
    assert gm.player_state.gold == 900, "金币应为 900"

    # 刷新按钮状态 — 已满，应置灰
    screen.refresh_shop_buttons()
    btn = _find_button_by_item_id(screen, "pickaxe")
    assert btn.is_enabled is False, "容量已满，铁锹按钮应置灰"

    assert len(save_calls) == 2, f"save() 应被调用 2 次，实际 {len(save_calls)} 次"

    print("[PASS] test_buy_pickaxe_and_capacity_limit")


def test_buy_amulet():
    """购买护身符后 has_amulet 应为 True，按钮置灰。"""
    gm = _reset_game_manager()
    save_calls = []
    gm.save_manager.save = lambda p, s=None: (save_calls.append(1), True)[1]

    gm.player_state.gold = 1000
    gm.player_state.has_amulet = False

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    btn = _find_button_by_item_id(screen, "amulet")
    assert btn is not None
    assert btn.is_enabled is True, "护身符按钮应可点击"

    # 点击购买
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    assert gm.player_state.has_amulet is True, "has_amulet 应为 True"
    assert gm.player_state.gold == 900, f"金币应为 900，得到 {gm.player_state.gold}"

    # 刷新后按钮应置灰
    screen.refresh_shop_buttons()
    btn = _find_button_by_item_id(screen, "amulet")
    assert btn.is_enabled is False, "已购买护身符，按钮应置灰"

    assert len(save_calls) == 1, f"save() 应被调用 1 次，实际 {len(save_calls)} 次"

    print("[PASS] test_buy_amulet")


def test_insufficient_gold_disables_buttons():
    """金币不足时，所有 Buy 按钮应置灰。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    # 只给 10 金币
    gm.player_state.gold = 10

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    # 检查所有商品按钮都置灰
    for item in SHOP_ITEMS:
        btn = _find_button_by_item_id(screen, item["id"])
        assert btn is not None, f"应存在 {item['id']} 按钮"
        assert btn.is_enabled is False, (
            f"金币不足时 {item['id']} 按钮应置灰，实际 is_enabled={btn.is_enabled}"
        )

    print("[PASS] test_insufficient_gold_disables_buttons")


def test_max_hearts_disables_upgrade():
    """生命上限已达硬上限时，升级按钮应置灰。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    gm.player_state.gold = 10000
    gm.player_state.max_hearts = HARD_CAP_HEARTS  # 8

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    btn = _find_button_by_item_id(screen, "max_hearts")
    assert btn is not None
    assert btn.is_enabled is False, "max_hearts=8 时生命升级按钮应置灰"

    print("[PASS] test_max_hearts_disables_upgrade")


def test_leave_shop_routes_to_playing():
    """点击"离开商店"应路由到 PLAYING，携带正确的 level_num。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)

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

    # 进入商店，next_level=3
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    # 找到离开按钮并点击
    btn_leave = _find_button_by_item_id(screen, "leave")
    assert btn_leave is not None, "应存在离开按钮"

    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn_leave.rect.center},
    )
    screen.handle_event(click_event)

    # 断言路由到了 PLAYING
    assert gm.screen_manager.current_state == GameState.PLAYING, (
        f"应路由到 PLAYING，实际为 {gm.screen_manager.current_state}"
    )
    # 断言携带正确的 level_num
    assert mock_playing.enter_payload == {"level_num": 3, "continue": True}, (
        f"payload 应为 {{'level_num': 3, 'continue': True}}，"
        f"得到 {mock_playing.enter_payload}"
    )

    print("[PASS] test_leave_shop_routes_to_playing")


def test_render_no_exception():
    """render 应不抛异常。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    gm.player_state.gold = 500

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.render(surface)

    print("[PASS] test_render_no_exception")


def test_tool_buy_refund_on_capacity_full():
    """背包已满时购买工具，金币不应被扣除。"""
    gm = _reset_game_manager()
    save_calls = []
    gm.save_manager.save = lambda p, s=None: (save_calls.append(1), True)[1]

    # 设置：容量 2，已满
    gm.player_state.gold = 1000
    gm.player_state.bag_tier_index = 0  # capacity = 2
    gm.player_state.tools = {"pickaxe": 2, "dynamite": 0, "map": 0}  # 已满

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    btn = _find_button_by_item_id(screen, "pickaxe")
    assert btn is not None
    assert btn.is_enabled is False, "容量已满，按钮应已置灰"

    # 即使强制点击（模拟竞态），也不应扣金币
    # 这里测试 _buy_item 的防御逻辑：即使按钮被绕过，_can_buy 也会拦截
    screen._buy_item("pickaxe")

    assert gm.player_state.gold == 1000, (
        f"背包已满，金币不应被扣除，得到 {gm.player_state.gold}"
    )
    assert gm.player_state.tools["pickaxe"] == 2, "工具数量不应变化"
    assert len(save_calls) == 0, "不应触发 save"

    print("[PASS] test_tool_buy_refund_on_capacity_full")


def test_on_exit_clears_refs():
    """on_exit 应清空所有临时引用。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    screen.on_exit()

    assert screen.game_manager is None
    assert screen.screen_manager is None
    assert screen.asset_manager is None
    assert screen.buttons == []
    assert screen.font_title is None
    assert screen.font_info is None
    assert screen.sound_click is None
    assert screen.sound_buy is None

    print("[PASS] test_on_exit_clears_refs")


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        test_on_enter_records_next_level()
        test_on_enter_default_next_level()
        test_buy_shield()
        test_buy_pickaxe_and_capacity_limit()
        test_buy_amulet()
        test_insufficient_gold_disables_buttons()
        test_max_hearts_disables_upgrade()
        test_leave_shop_routes_to_playing()
        test_render_no_exception()
        test_tool_buy_refund_on_capacity_full()
        test_on_exit_clears_refs()

        print("\n=== ALL TESTS PASSED ===")
    finally:
        # 仅重置单例，不调用 pygame.quit()
        GameManager._instance = None
        AssetManager._instance = None
