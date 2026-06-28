"""GameManager / ScreenManager / BaseScreen 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_game_manager.py` 直接运行。
使用 SDL dummy 驱动避免弹出实体窗口。
"""

import os
import sys

# 设置 headless 驱动必须在 pygame.init() 之前
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# 确保能找到 src/ 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 初始化 Pygame（display + font + mixer）
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

from src.screens.base_screen import BaseScreen
from src.screen_manager import ScreenManager
from src.game_manager import GameManager, MAX_DT
from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT


# --------------------------------------------------------------------------
# Mock 屏幕
# --------------------------------------------------------------------------

class MockMenuScreen(BaseScreen):
    """记录全部生命周期调用，用于验证 ScreenManager 与 GameManager 的分发。"""

    def __init__(self):
        self.entered = False
        self.exited = False
        self.enter_payload = "UNSET"
        self.events_received = []
        self.update_count = 0
        self.render_count = 0

    def on_enter(self, data_payload=None):
        self.entered = True
        self.enter_payload = data_payload

    def on_exit(self):
        self.exited = True

    def handle_event(self, event):
        self.events_received.append(event)

    def update(self, dt):
        self.update_count += 1

    def render(self, surface):
        self.render_count += 1


class MockGameScreen(BaseScreen):
    """第二个 Mock 屏幕，行为与 MockMenuScreen 一致但独立实例。"""

    def __init__(self):
        self.entered = False
        self.exited = False
        self.enter_payload = "UNSET"
        self.events_received = []
        self.update_count = 0
        self.render_count = 0

    def on_enter(self, data_payload=None):
        self.entered = True
        self.enter_payload = data_payload

    def on_exit(self):
        self.exited = True

    def handle_event(self, event):
        self.events_received.append(event)

    def update(self, dt):
        self.update_count += 1

    def render(self, surface):
        self.render_count += 1


# --------------------------------------------------------------------------
# 测试用例
# --------------------------------------------------------------------------

def test_engine_init_headless():
    """headless=True 时引擎应成功初始化，screen 是 Surface，clock 存在。"""
    # 重置单例，避免前次测试污染
    GameManager._instance = None
    mgr = GameManager.get_instance()

    mgr.init_engine(headless=True)

    assert isinstance(mgr.screen, pygame.Surface), "screen 应为 Surface 实例"
    assert mgr.clock is not None, "clock 应已初始化"
    assert mgr.asset_manager is not None, "asset_manager 应已初始化"
    assert mgr.save_manager is not None, "save_manager 应已初始化"
    assert mgr.screen_manager is not None, "screen_manager 应已初始化"
    assert mgr.player_state is not None, "player_state 应已初始化"
    assert mgr.running is True, "running 应为 True"
    assert mgr.screen.get_size() == (SCREEN_WIDTH, SCREEN_HEIGHT), (
        f"headless Surface 尺寸应为 ({SCREEN_WIDTH}, {SCREEN_HEIGHT})，"
        f"得到 {mgr.screen.get_size()}"
    )

    print("[PASS] test_engine_init_headless")


def test_screen_registration_and_switch():
    """注册两个 Mock 屏幕并切换，验证 on_exit / on_enter / data_payload 正确。"""
    mgr = ScreenManager()

    menu = MockMenuScreen()
    game = MockGameScreen()

    mgr.register_screen(GameState.MAIN_MENU, menu)
    mgr.register_screen(GameState.PLAYING, game)

    # 切换到 MAIN_MENU
    mgr.switch_screen(GameState.MAIN_MENU, data_payload={"test": 123})
    assert mgr.current_state == GameState.MAIN_MENU
    assert mgr.current_screen is menu
    assert menu.entered is True, "MAIN_MENU 的 on_enter 应被调用"
    assert menu.enter_payload == {"test": 123}, (
        f"MAIN_MENU 应收到 data_payload={{'test': 123}}，得到 {menu.enter_payload}"
    )
    assert menu.exited is False, "MAIN_MENU 不应被 exit"
    assert game.entered is False, "PLAYING 尚未 enter"

    # 切换到 PLAYING — 验证旧屏 on_exit 触发
    mgr.switch_screen(GameState.PLAYING, data_payload={"level": 5})
    assert mgr.current_state == GameState.PLAYING
    assert mgr.current_screen is game
    assert menu.exited is True, "MAIN_MENU 的 on_exit 应被调用"
    assert game.entered is True, "PLAYING 的 on_enter 应被调用"
    assert game.enter_payload == {"level": 5}, (
        f"PLAYING 应收到 data_payload={{'level': 5}}，得到 {game.enter_payload}"
    )

    print("[PASS] test_screen_registration_and_switch")


def test_switch_screen_without_current():
    """首次切换时 current_screen=None，不应触发 on_exit，新屏正常 on_enter。"""
    mgr = ScreenManager()

    menu = MockMenuScreen()
    mgr.register_screen(GameState.MAIN_MENU, menu)

    # 首次切换 — current_screen 为 None
    mgr.switch_screen(GameState.MAIN_MENU)
    assert mgr.current_screen is menu
    assert menu.entered is True, "首次切换仍应触发 on_enter"
    assert menu.enter_payload is None, "未传 data_payload 时应收到 None"

    print("[PASS] test_switch_screen_without_current")


def test_main_loop_delegation():
    """手动调用 update / render 若干次，验证 Mock 屏幕正确承接到更新与绘制。"""
    mgr = ScreenManager()

    menu = MockMenuScreen()
    mgr.register_screen(GameState.MAIN_MENU, menu)
    mgr.switch_screen(GameState.MAIN_MENU)

    # 模拟 3 帧更新 + 渲染
    for _ in range(3):
        mgr.update(1 / 60)
        mgr.render(pygame.display.get_surface())

    assert menu.update_count == 3, f"update 应被调用 3 次，得到 {menu.update_count}"
    assert menu.render_count == 3, f"render 应被调用 3 次，得到 {menu.render_count}"

    # 模拟事件分发
    fake_events = [
        pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE}),
        pygame.event.Event(pygame.KEYUP, {"key": pygame.K_SPACE}),
    ]
    for e in fake_events:
        mgr.handle_event(e)

    assert len(menu.events_received) == 2, (
        f"应收到 2 个事件，得到 {len(menu.events_received)}"
    )

    print("[PASS] test_main_loop_delegation")


def test_quit_stops_loop():
    """quit_game() 将 running 置 False；running=False 时 run() 立即退出。"""
    GameManager._instance = None
    mgr = GameManager.get_instance()
    mgr.init_engine(headless=True)

    # 验证 quit_game 将 running 置 False
    mgr.quit_game()
    assert mgr.running is False, "quit_game 后 running 应为 False"

    # 重新初始化，验证 run() 在 running=False 时立即退出
    GameManager._instance = None
    mgr = GameManager.get_instance()
    mgr.init_engine(headless=True)
    mgr.running = False  # 模拟外部停止信号

    # run() 应立刻退出，不会阻塞
    mgr.run()
    # 能走到这里说明 run() 正确退出
    assert True

    print("[PASS] test_quit_stops_loop")


def test_dt_clamp_constant():
    """验证 MAX_DT 常量为 0.25 秒（docs/10 §2.3.2 契约）。"""
    assert MAX_DT == 0.25, f"MAX_DT 应为 0.25，得到 {MAX_DT}"
    print("[PASS] test_dt_clamp_constant")


def test_switch_unregistered_raises():
    """切换到未注册的 GameState 应抛 KeyError。"""
    mgr = ScreenManager()
    try:
        mgr.switch_screen(GameState.MAIN_MENU)
        assert False, "未注册的 GameState 应抛 KeyError"
    except KeyError:
        pass  # 预期行为

    print("[PASS] test_switch_unregistered_raises")


# --------------------------------------------------------------------------
# teardown
# --------------------------------------------------------------------------

def teardown():
    """清理 Pygame 和单例。"""
    GameManager._instance = None
    AssetManager._instance = None
    pygame.quit()


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        from src.asset_manager import AssetManager  # noqa: F401 — teardown 引用

        test_engine_init_headless()
        test_screen_registration_and_switch()
        test_switch_screen_without_current()
        test_main_loop_delegation()
        test_quit_stops_loop()
        test_dt_clamp_constant()
        test_switch_unregistered_raises()
        print("\n=== ALL TESTS PASSED ===")
    finally:
        teardown()
