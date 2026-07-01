"""MainMenuScreen / Button 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_main_menu_screen.py` 直接运行。
使用 SDL dummy 驱动避免弹出实体窗口。
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

from src.screens.main_menu_screen import Button, MainMenuScreen
from src.screens.base_screen import BaseScreen
from src.game_manager import GameManager
from src.asset_manager import AssetManager
from src.screen_manager import ScreenManager
from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT, DARK_GREEN, GOLD, WHITE


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------

def _make_font(size=36):
    # NOTE: pygame 2.6.1 on Windows has a bug in SysFont() font scanning;
    #       use Font(None) for the built-in freesansbold font instead.
    return pygame.font.Font(None, size)


# ==========================================================================
# Button 测试（不依赖 GameManager，隔离纯逻辑）
# ==========================================================================

def test_button_construction():
    """验证 Button 构造后的 rect、初始状态。"""
    font = _make_font()
    btn = Button("测试", (512, 350), 280, 52, font)

    assert btn.text == "测试"
    assert btn.rect.width == 280
    assert btn.rect.height == 52
    assert btn.rect.center == (512, 350)
    assert btn.is_hovered is False, "初始不应悬停"
    assert btn.is_enabled is True, "初始应该启用"

    print("[PASS] test_button_construction")


def test_button_hover_detection():
    """鼠标在 rect 内 → is_hovered=True；在外 → is_hovered=False。"""
    font = _make_font()
    btn = Button("测试", (512, 350), 280, 52, font)

    # 鼠标移入按钮中心
    result = btn.update((512, 350))
    assert btn.is_hovered is True, "中心点应在按钮内"
    assert result is True, "首次进入悬停应返回 True"

    # 鼠标留在按钮内 — 无突变
    result = btn.update((520, 355))
    assert btn.is_hovered is True
    assert result is False, "已在悬停，无突变"

    # 鼠标移出按钮
    result = btn.update((0, 0))
    assert btn.is_hovered is False, "移出后不应悬停"
    assert result is False, "离开悬停无突变"

    # 再次移入 — 突变
    result = btn.update((512, 350))
    assert btn.is_hovered is True
    assert result is True, "重新进入悬停应返回 True"

    print("[PASS] test_button_hover_detection")


def test_button_disabled_no_hover():
    """禁用按钮：update 始终不悬停、无突变信号。"""
    font = _make_font()
    btn = Button("禁用", (512, 350), 280, 52, font)
    btn.is_enabled = False

    result = btn.update((512, 350))
    assert btn.is_hovered is False, "禁用按钮即使鼠标在内也不悬停"
    assert result is False, "禁用按钮无突变信号"

    # 先启用设为悬停，再禁用
    btn.is_enabled = True
    btn.update((512, 350))
    assert btn.is_hovered is True

    btn.is_enabled = False
    result = btn.update((512, 350))
    assert btn.is_hovered is False, "禁用后强制取消悬停"
    assert result is False

    print("[PASS] test_button_disabled_no_hover")


def test_button_transition_signal_out_in():
    """验证完整悬停突变信号序列：外→内→内→外→内。"""
    font = _make_font()
    btn = Button("信号", (512, 350), 280, 52, font)

    signals = []
    positions = [
        (0, 0),       # 外
        (512, 350),   # 内 — 突变
        (515, 350),   # 内 — 无突变
        (515, 350),   # 内 — 无突变
        (0, 0),       # 外 — 无突变
        (512, 350),   # 内 — 突变
    ]
    for pos in positions:
        signals.append(btn.update(pos))

    assert signals == [False, True, False, False, False, True], (
        f"突变信号序列不匹配：{signals}"
    )

    print("[PASS] test_button_transition_signal_out_in")


def test_button_render_no_exception():
    """验证 Button render 三态均不抛异常。"""
    font = _make_font()
    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    btn = Button("测试", (512, 350), 280, 52, font)

    # 正常态
    btn.is_hovered = False
    btn.is_enabled = True
    btn.render(surface)

    # 悬停态
    btn.is_hovered = True
    btn.render(surface)

    # 禁用态
    btn.is_enabled = False
    btn.is_hovered = False
    btn.render(surface)

    print("[PASS] test_button_render_no_exception")


# ==========================================================================
# MainMenuScreen 测试
# ==========================================================================
# 所有 MainMenuScreen 测试共享一个 GameManager 实例，
# 避免反复调用 init_engine() 导致 SDL dummy 驱动段错误。

def test_main_menu_on_enter_buttons_initialized():
    """on_enter 应正确初始化 3 个按钮、音效和字体。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    screen = MainMenuScreen()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    assert screen.btn_new_game is not None, "开始新游戏按钮应存在"
    assert screen.btn_continue is not None, "读取进度按钮应存在"
    assert screen.btn_achievements is not None, "荣誉成就按钮应存在"
    assert screen.btn_settings is not None, "设置按钮应存在"
    assert screen.btn_custom is not None, "自定义关卡按钮应存在"
    assert screen.btn_save_slots is not None, "选择存档槽按钮应存在"
    assert screen.btn_map_editor is not None, "设计地图按钮应存在"
    assert screen.btn_quit is not None, "退出游戏按钮应存在"
    # 第 57 课：新增「设计地图」按钮，总数由 7 升至 8
    assert len(screen.buttons) == 8, (
        "应包含 8 个按钮（新游戏/继续/荣誉成就/设置/设计地图/自定义关卡/选择存档槽/退出）"
    )

    assert screen.sound_hover is not None, "悬停音效应已加载"
    assert screen.sound_click is not None, "点击音效应已加载"
    assert screen.font_button is not None, "按钮字体应已加载"
    assert screen.font_title is not None, "标题字体应已加载"

    print("[PASS] test_main_menu_on_enter_buttons_initialized")


def test_main_menu_continue_button_disabled_fresh():
    """无存档时（highest_level_cleared=0），读取进度按钮应置灰。"""
    # 重置单例以重新 on_enter
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    screen = MainMenuScreen()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    if screen.highest_level_cleared == 0:
        assert screen.btn_continue.is_enabled is False, (
            "无存档时读取进度应置灰"
        )

    print("[PASS] test_main_menu_continue_button_disabled_fresh")


def test_main_menu_continue_button_enabled_with_save():
    """模拟有存档时，读取进度按钮应可用。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    # 模拟存档
    original_load = gm.save_manager.load
    def mock_load():
        return {
            "version": "1.0.0",
            "player": {"highest_level_cleared": 7},
            "settings": {"sound_volume": 1.0, "music_volume": 1.0},
            "checksum": "mock",
        }
    gm.save_manager.load = mock_load

    screen = MainMenuScreen()
    screen.on_enter()

    assert screen.btn_continue.is_enabled is True, "有存档时读取进度应可用"
    assert screen.highest_level_cleared == 7

    gm.save_manager.load = original_load
    print("[PASS] test_main_menu_continue_button_enabled_with_save")


def test_main_menu_hover_plays_sound():
    """鼠标悬停突变时，hover 音效应被播放。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    screen = MainMenuScreen()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    # 替换 sound_hover 为可追踪的 mock
    play_count = [0]
    class MockSound:
        def play(self, *a, **kw):
            play_count[0] += 1
    screen.sound_hover = MockSound()

    btn = screen.btn_new_game
    hover_event = pygame.event.Event(pygame.MOUSEMOTION, {"pos": btn.rect.center})
    screen.handle_event(hover_event)

    assert play_count[0] == 1, "悬停突变应触发 hover 音效"

    hover_event2 = pygame.event.Event(
        pygame.MOUSEMOTION, {"pos": (btn.rect.centerx + 5, btn.rect.centery)}
    )
    screen.handle_event(hover_event2)
    assert play_count[0] == 1, "持续悬停不应再次触发音效"

    print("[PASS] test_main_menu_hover_plays_sound")


def test_main_menu_click_new_game():
    """点击"开始新游戏"应切换到 PLAYING 场景并传 continue=False。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    screen = MainMenuScreen()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)

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
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    btn = screen.btn_new_game
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    assert mock_playing.enter_payload == {"continue": False}, (
        f"开始新游戏应传 continue=False，得到 {mock_playing.enter_payload}"
    )

    print("[PASS] test_main_menu_click_new_game")


def test_main_menu_click_continue():
    """点击"读取进度"应切换到 PLAYING 并传 continue=True + level。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    # 模拟存档
    original_load = gm.save_manager.load
    def mock_load():
        return {
            "version": "1.0.0",
            "player": {"highest_level_cleared": 5},
            "settings": {"sound_volume": 1.0, "music_volume": 1.0},
            "checksum": "mock",
        }
    gm.save_manager.load = mock_load

    screen = MainMenuScreen()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)

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
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    btn = screen.btn_continue
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    assert mock_playing.enter_payload == {
        "continue": True,
        "highest_level_cleared": 5,
    }, f"读取进度应传继续存档数据，得到 {mock_playing.enter_payload}"

    gm.save_manager.load = original_load
    print("[PASS] test_main_menu_click_continue")


def test_main_menu_click_quit():
    """点击"退出游戏"应调用 game_manager.quit_game()。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    screen = MainMenuScreen()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    # Mock quit_game to only set running=False (avoid calling pygame.quit()
    # which causes segfault on process exit with SDL dummy driver)
    original_quit_game = gm.quit_game
    gm.quit_game = lambda: setattr(gm, 'running', False)

    btn = screen.btn_quit
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    assert gm.running is False, "退出游戏后 running 应为 False"

    gm.quit_game = original_quit_game
    print("[PASS] test_main_menu_click_quit")


def test_main_menu_disabled_continue_not_clickable():
    """读取进度按钮禁用时，点击不应切换场景。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    screen = MainMenuScreen()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    screen.btn_continue.is_enabled = False

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

    class MockSound:
        def play(self, *a, **kw): pass
    screen.sound_click = MockSound()

    btn = screen.btn_continue
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)

    assert mock_playing.enter_payload is None, "禁用按钮点击不应触发场景切换"

    print("[PASS] test_main_menu_disabled_continue_not_clickable")


def test_main_menu_on_exit_clears_refs():
    """on_exit 应清空所有临时引用。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    screen = MainMenuScreen()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    screen.on_exit()

    assert screen.game_manager is None
    assert screen.buttons == []
    assert screen.btn_new_game is None, "on_exit 应清理 btn_new_game"
    assert screen.btn_continue is None, "on_exit 应清理 btn_continue"
    assert screen.btn_achievements is None, "on_exit 应清理 btn_achievements"
    assert screen.btn_settings is None, "on_exit 应清理 btn_settings"
    assert screen.btn_map_editor is None, "on_exit 应清理 btn_map_editor"
    assert screen.btn_custom is None, "on_exit 应清理 btn_custom"
    assert screen.btn_save_slots is None, "on_exit 应清理 btn_save_slots"
    assert screen.btn_quit is None, "on_exit 应清理 btn_quit"
    assert screen.sound_hover is None, "on_exit 应清理 sound_hover"
    assert screen.sound_click is None, "on_exit 应清理 sound_click"

    print("[PASS] test_main_menu_on_exit_clears_refs")


def test_main_menu_render_no_exception():
    """render 应不抛异常。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    screen = MainMenuScreen()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.render(surface)

    print("[PASS] test_main_menu_render_no_exception")


# ==========================================================================
# 第 54 课新增：主菜单「自定义关卡」按钮相关测试
# ==========================================================================


def test_main_menu_custom_button_greyed_out_when_missing():
    """无 custom_map.json 时，自定义关卡按钮应置灰（is_enabled=False）。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    screen = MainMenuScreen()
    gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    # 当前测试沙盒根目录不放置 custom_map.json → 按钮必须置灰
    assert screen.btn_custom is not None, "自定义关卡按钮应始终创建"
    assert screen.btn_custom.is_enabled is False, (
        "无 custom_map.json 时自定义关卡按钮应置灰"
    )

    # 渲染不应崩溃
    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.render(surface)

    print("[PASS] test_main_menu_custom_button_greyed_out_when_missing")


def test_main_menu_custom_button_enabled_when_present(monkeypatch=None):
    """mock os.path.exists 返回 True 时，自定义关卡按钮应启用。"""
    import os as _os

    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    # mock os.path.exists 强制返回 True
    _original_exists = _os.path.exists
    _os.path.exists = lambda p: True if p.endswith("custom_map.json") else _original_exists(p)
    try:
        screen = MainMenuScreen()
        gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)
        gm.screen_manager.switch_screen(GameState.MAIN_MENU)

        assert screen.btn_custom is not None, "自定义关卡按钮应始终创建"
        assert screen.btn_custom.is_enabled is True, (
            "根目录有 custom_map.json 时自定义关卡按钮应启用"
        )
    finally:
        _os.path.exists = _original_exists

    print("[PASS] test_main_menu_custom_button_enabled_when_present")


def test_main_menu_custom_button_click_routes_to_playing():
    """点击「自定义关卡」应切换到 PLAYING 场景并传 custom_map_path payload。"""
    import os as _os

    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    _original_exists = _os.path.exists
    _os.path.exists = lambda p: True if p.endswith("custom_map.json") else _original_exists(p)
    try:
        screen = MainMenuScreen()
        gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)

        class MockPlaying(BaseScreen):
            def __init__(self):
                self.enter_payload = None
            def on_enter(self, data_payload=None):
                self.enter_payload = data_payload
            def on_exit(self): pass
            def handle_event(self, event): pass
            def update(self, dt): pass
            def render(self, surface): pass

        class MockSettings(BaseScreen):
            def __init__(self): pass
            def on_enter(self, data_payload=None): pass
            def on_exit(self): pass
            def handle_event(self, event): pass
            def update(self, dt): pass
            def render(self, surface): pass

        mock_playing = MockPlaying()
        mock_settings = MockSettings()
        gm.screen_manager.register_screen(GameState.PLAYING, mock_playing)
        gm.screen_manager.register_screen(GameState.SETTINGS, mock_settings)
        gm.screen_manager.register_screen(GameState.STATS, MockSettings())
        gm.screen_manager.register_screen(GameState.SAVE_SLOT_SELECT, MockSettings())
        gm.screen_manager.switch_screen(GameState.MAIN_MENU)

        class MockSound:
            def play(self, *a, **kw): pass
        screen.sound_click = MockSound()

        btn = screen.btn_custom
        assert btn.is_enabled is True, "已 mock 文件存在，按钮应启用"
        click_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": btn.rect.center},
        )
        screen.handle_event(click_event)

        assert mock_playing.enter_payload == {"custom_map_path": "custom_map.json"}, (
            f"自定义关卡应传 custom_map_path payload，得到 {mock_playing.enter_payload}"
        )
    finally:
        _os.path.exists = _original_exists

    print("[PASS] test_main_menu_custom_button_click_routes_to_playing")


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        test_button_construction()
        test_button_hover_detection()
        test_button_disabled_no_hover()
        test_button_transition_signal_out_in()
        test_button_render_no_exception()

        test_main_menu_on_enter_buttons_initialized()
        test_main_menu_continue_button_disabled_fresh()
        test_main_menu_continue_button_enabled_with_save()
        test_main_menu_hover_plays_sound()
        test_main_menu_click_new_game()
        test_main_menu_click_continue()
        test_main_menu_click_quit()
        test_main_menu_disabled_continue_not_clickable()
        test_main_menu_on_exit_clears_refs()
        test_main_menu_render_no_exception()
        test_main_menu_custom_button_greyed_out_when_missing()
        test_main_menu_custom_button_enabled_when_present()
        test_main_menu_custom_button_click_routes_to_playing()

        print("\n=== ALL TESTS PASSED ===")
    finally:
        # 仅重置单例，不调用 pygame.quit()
        # （SDL dummy 驱动在进程退出时自动清理，
        #   显式 pygame.quit() 会导致段错误）
        GameManager._instance = None
        AssetManager._instance = None
