"""HUD 交互与滚轮模式切换验证脚本 — Lesson 51

Headless 模式下验证：
- HUD 点击命中工具图标区域
- HUD 点击空白区域被拦截
- HUD 悬停高亮渲染无崩溃
- 滚轮上下双向切换模式
- HUD 触发地图扫描
- HUD 触发炸药模式切换

运行方式::

    python tests/test_hud_interaction.py
    python -m pytest tests/test_hud_interaction.py -v
"""

import os
import sys

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Headless 模式：必须在 pygame.init() 之前设置
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from src.config import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_HEIGHT, TILE_SIZE
from src.player_state import PlayerState
from src.hud import HUD
from src.screens.gameplay_screen import GameplayScreen


# =============================================================================
# 辅助函数
# =============================================================================

def _make_player() -> PlayerState:
    """创建带典型数值的 PlayerState。"""
    player = PlayerState()
    player.current_hearts = 4
    player.max_hearts = 5
    player.current_shields = 1
    player.gold = 100
    player.tools["pickaxe"] = 2
    player.tools["dynamite"] = 1
    player.tools["map"] = 1
    return player


def _make_surface() -> pygame.Surface:
    """创建离屏 Surface（支持 alpha）。"""
    if not pygame.get_init():
        pygame.init()
    return pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)


def _make_screen_with_tools() -> GameplayScreen:
    """创建并初始化 GameplayScreen，预置工具以便测试点击效果。"""
    if not pygame.get_init():
        pygame.init()

    player = _make_player()

    screen = GameplayScreen()

    class FakeGameManager:
        def __init__(self):
            self.player_state = player
            self.screen_manager = None
            self.asset_manager = None
            self.save_manager = None

    screen.game_manager = FakeGameManager()

    # 确保 GameManager 单例也使用同一个 PlayerState 实例
    # on_enter() 内部可能从单例获取 player_state，必须保持一致
    from src.game_manager import GameManager
    gm = GameManager.get_instance()
    gm.player_state = player

    screen.on_enter(data_payload=None)
    return screen


# =============================================================================
# HUD handle_click 基础测试
# =============================================================================

def test_hud_handle_click_pickaxe():
    """点击 pickaxe 图标中心应返回 'pickaxe'。"""
    player = _make_player()
    hud = HUD(player)
    # pickaxe rect: (450, 20, 50, 60) → center ≈ (475, 50)
    result = hud.handle_click((475, 50))
    assert result == "pickaxe", f"应返回 'pickaxe'，得到 {result!r}"
    print("[PASS] test_hud_handle_click_pickaxe")


def test_hud_handle_click_dynamite():
    """点击 dynamite 图标中心应返回 'dynamite'。"""
    player = _make_player()
    hud = HUD(player)
    # dynamite rect: (510, 20, 50, 60) → center ≈ (535, 50)
    result = hud.handle_click((535, 50))
    assert result == "dynamite", f"应返回 'dynamite'，得到 {result!r}"
    print("[PASS] test_hud_handle_click_dynamite")


def test_hud_handle_click_map():
    """点击 map 图标中心应返回 'map'。"""
    player = _make_player()
    hud = HUD(player)
    # map rect: (570, 20, 50, 60) → center ≈ (595, 50)
    result = hud.handle_click((595, 50))
    assert result == "map", f"应返回 'map'，得到 {result!r}"
    print("[PASS] test_hud_handle_click_map")


def test_hud_handle_click_blank_area():
    """点击 HUD 空白区域（非工具图标）应返回 None。"""
    player = _make_player()
    hud = HUD(player)
    # 点击 HP 区域 (100, 30) — 在工具区左侧
    result = hud.handle_click((100, 30))
    assert result is None, f"空白区域应返回 None，得到 {result!r}"
    # 点击工具区中间空白 (505, 50) — 在 pickaxe 和 dynamite 之间
    result = hud.handle_click((505, 50))
    assert result is None, f"工具间隙应返回 None，得到 {result!r}"
    print("[PASS] test_hud_handle_click_blank_area")


def test_hud_handle_click_outside_hud():
    """点击 HUD 外部（Y >= HUD_HEIGHT）应返回 None。"""
    player = _make_player()
    hud = HUD(player)
    result = hud.handle_click((500, 200))
    assert result is None, f"HUD 外部应返回 None，得到 {result!r}"
    print("[PASS] test_hud_handle_click_outside_hud")


# =============================================================================
# HUD 悬停高亮渲染测试
# =============================================================================

def test_hud_render_with_hover_glow_no_crash():
    """悬停高亮渲染不应崩溃（headless 模式下 mouse.get_pos() 可能抛异常）。"""
    player = _make_player()
    hud = HUD(player)
    surface = _make_surface()
    # 尝试设置鼠标位置 — headless 下可能失败，但渲染不应崩溃
    try:
        pygame.mouse.set_pos(475, 50)
    except Exception:
        pass
    hud.render(surface, current_level_num=1)
    print("[PASS] test_hud_render_with_hover_glow_no_crash")


# =============================================================================
# GameplayScreen HUD 点击交互测试
# =============================================================================

def test_hud_click_dynamite_toggles_mode():
    """HUD 点击 dynamite 应在有炸药时切换 input_mode。"""
    screen = _make_screen_with_tools()
    initial_mode = screen.input_mode
    assert initial_mode == "EXPLORE", f"初始模式应为 EXPLORE，得到 {initial_mode}"

    # 模拟点击 dynamite 图标中心
    dynamite_center = (535, 50)
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": dynamite_center, "button": 1}
    )
    screen.handle_event(event)

    assert screen.input_mode == "DYNAMITE", (
        f"点击 dynamite 后应切换到 DYNAMITE，得到 {screen.input_mode}"
    )

    # 再次点击应切回 EXPLORE
    event2 = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": dynamite_center, "button": 1}
    )
    screen.handle_event(event2)
    assert screen.input_mode == "EXPLORE", (
        f"再次点击 dynamite 后应切回 EXPLORE，得到 {screen.input_mode}"
    )
    print("[PASS] test_hud_click_dynamite_toggles_mode")


def test_hud_click_map_triggers_scan():
    """HUD 点击 map 应调用 use_map() 并消耗地图。"""
    screen = _make_screen_with_tools()
    initial_map_count = screen.interaction_controller.player.tools["map"]
    assert initial_map_count >= 1, f"预置地图数量应 >= 1，得到 {initial_map_count}"

    # 模拟点击 map 图标中心
    map_center = (595, 50)
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": map_center, "button": 1}
    )
    screen.handle_event(event)

    new_count = screen.interaction_controller.player.tools["map"]
    assert new_count == initial_map_count - 1, (
        f"点击 map 后地图应减少 1，得到 {new_count}（初始 {initial_map_count}）"
    )
    print("[PASS] test_hud_click_map_triggers_scan")


def test_hud_click_blank_does_not_uncover_tile():
    """点击 HUD 空白区域不应触发任何网格开掘。"""
    screen = _make_screen_with_tools()
    # 记录初始 DIRT 数量
    dirt_before = sum(
        1 for y in range(screen.game_map.height)
        for x in range(screen.game_map.width)
        if screen.game_map.layer0[y][x] == "DIRT"
    )

    # 点击 HUD 空白区域（HP 区域左侧）
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": (100, 30), "button": 1}
    )
    screen.handle_event(event)

    # DIRT 数量应不变
    dirt_after = sum(
        1 for y in range(screen.game_map.height)
        for x in range(screen.game_map.width)
        if screen.game_map.layer0[y][x] == "DIRT"
    )
    assert dirt_after == dirt_before, (
        f"HUD 空白点击不应开掘，DIRT 变化 {dirt_before} → {dirt_after}"
    )
    print("[PASS] test_hud_click_blank_does_not_uncover_tile")


# =============================================================================
# 滚轮模式切换测试
# =============================================================================

def test_scroll_wheel_up_toggles_mode():
    """滚轮上滚应切换 input_mode（EXPLORE → DYNAMITE）。"""
    screen = _make_screen_with_tools()
    assert screen.input_mode == "EXPLORE"

    event = pygame.event.Event(pygame.MOUSEWHEEL, {"y": 1})
    screen.handle_event(event)

    assert screen.input_mode == "DYNAMITE", (
        f"滚轮上滚后应为 DYNAMITE，得到 {screen.input_mode}"
    )
    print("[PASS] test_scroll_wheel_up_toggles_mode")


def test_scroll_wheel_down_toggles_mode():
    """滚轮下滚应切换 input_mode（双向切换）。"""
    screen = _make_screen_with_tools()
    # 先确保在 EXPLORE
    screen.input_mode = "EXPLORE"

    event = pygame.event.Event(pygame.MOUSEWHEEL, {"y": -1})
    screen.handle_event(event)

    assert screen.input_mode == "DYNAMITE", (
        f"滚轮下滚后应为 DYNAMITE，得到 {screen.input_mode}"
    )

    # 再滚一次应切回
    event2 = pygame.event.Event(pygame.MOUSEWHEEL, {"y": 1})
    screen.handle_event(event2)
    assert screen.input_mode == "EXPLORE", (
        f"再次滚轮后应切回 EXPLORE，得到 {screen.input_mode}"
    )
    print("[PASS] test_scroll_wheel_down_toggles_mode")


def test_scroll_wheel_bidirectional():
    """滚轮双向切换完整循环：EXPLORE → DYNAMITE → EXPLORE。"""
    screen = _make_screen_with_tools()
    screen.input_mode = "EXPLORE"

    for expected_mode in ["DYNAMITE", "EXPLORE"]:
        event = pygame.event.Event(pygame.MOUSEWHEEL, {"y": 1})
        screen.handle_event(event)
        assert screen.input_mode == expected_mode, (
            f"滚轮后应为 {expected_mode}，得到 {screen.input_mode}"
        )
    print("[PASS] test_scroll_wheel_bidirectional")


def test_scroll_wheel_no_dynamite_no_toggle():
    """玩家无炸药时滚轮不应切换模式。"""
    screen = _make_screen_with_tools()
    screen.input_mode = "EXPLORE"
    screen.interaction_controller.player.tools["dynamite"] = 0

    event = pygame.event.Event(pygame.MOUSEWHEEL, {"y": 1})
    screen.handle_event(event)

    assert screen.input_mode == "EXPLORE", (
        f"无炸药时滚轮不应切换，得到 {screen.input_mode}"
    )
    print("[PASS] test_scroll_wheel_no_dynamite_no_toggle")


# =============================================================================
# 入口点
# =============================================================================

if __name__ == "__main__":
    test_hud_handle_click_pickaxe()
    test_hud_handle_click_dynamite()
    test_hud_handle_click_map()
    test_hud_handle_click_blank_area()
    test_hud_handle_click_outside_hud()
    test_hud_render_with_hover_glow_no_crash()
    test_hud_click_dynamite_toggles_mode()
    test_hud_click_map_triggers_scan()
    test_hud_click_blank_does_not_uncover_tile()
    test_scroll_wheel_up_toggles_mode()
    test_scroll_wheel_down_toggles_mode()
    test_scroll_wheel_bidirectional()
    test_scroll_wheel_no_dynamite_no_toggle()
    print("\n=== ALL HUD INTERACTION TESTS PASSED ===")
