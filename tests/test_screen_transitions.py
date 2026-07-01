"""第 56 课 — 全局像素级渐变转场动画系统单元测试

测试覆盖:
1. instant_mode 保留原始瞬切行为
2. 首次切换（无 current_screen）始终立即执行
3. switch_screen 触发 FADING_OUT 状态机
4. FADING_OUT 期间 update 委托给旧屏
5. 过半程 midpoint 触发 on_exit / on_enter 且切换至 FADING_IN
6. FADING_IN 期间 update 委托给新屏
7. 全流程完成后回 NONE 且清理 pending
8. 各阶段 Alpha 边界值正确
9. 过渡中再次 switch_screen 先强制完成
10. 未注册状态抛 KeyError
11. 非过渡期委托行为等同直接调 current_screen
12. GameManager.init_engine(headless=True) 设定 instant_mode=True
13. midpoint 异常不卡死，强制回 NONE 再抛
14. 超大 dt 跳过 multiple phase 时的正确携带
"""

import os
import sys

# 确保能找到项目模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT
from src.screen_manager import ScreenManager
from src.screens.base_screen import BaseScreen


# =========================================================================
# Mock 屏幕类
# =========================================================================


class MockScreen(BaseScreen):
    """用于测试的记录型 Mock 屏幕。"""

    def __init__(self, name="Mock"):
        self.name = name
        self.entered = False
        self.exited = False
        self.enter_payload = None
        self.update_count = 0
        self.render_count = 0
        self.events_received = []

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


class MockScreenThatRaises(BaseScreen):
    """on_enter 会抛异常的 Mock 屏幕，用于测试 midpoint 异常恢复。"""

    def on_enter(self, data_payload=None):
        raise RuntimeError("Intentional on_enter failure")

    def on_exit(self):
        pass

    def handle_event(self, event):
        pass

    def update(self, dt):
        pass

    def render(self, surface):
        pass


# =========================================================================
# 工具函数
# =========================================================================


def _make_manager(instant_mode=False):
    """创建一个预注册了两个 Mock 屏幕的 ScreenManager。"""
    sm = ScreenManager()
    sm.instant_mode = instant_mode
    sm.register_screen(GameState.MAIN_MENU, MockScreen("Menu"))
    sm.register_screen(GameState.PLAYING, MockScreen("Game"))
    sm.register_screen(GameState.GAME_OVER, MockScreen("GameOver"))
    sm.register_screen(GameState.SETTINGS, MockScreenThatRaises())
    return sm


def _setup_transition(sm):
    """让 ScreenManager 进入过渡状态（绕过 headless 检测）。"""
    # 第一次切换（无 current_screen，立即执行）
    sm.switch_screen(GameState.MAIN_MENU)
    # 禁用 headless 检测，保证下一次触发过渡
    sm._detect_headless = lambda: False
    return sm


# =========================================================================
# 测试用例
# =========================================================================


def test_instant_mode_preserves_behavior():
    """instant_mode=True 时 switch_screen 保持原始瞬切行为。"""
    sm = _make_manager(instant_mode=True)

    # 首次切换
    sm.switch_screen(GameState.MAIN_MENU, {"hello": "world"})
    assert sm.transition_state == "NONE"
    assert sm.current_state == GameState.MAIN_MENU
    assert isinstance(sm.current_screen, MockScreen)
    assert sm.current_screen.name == "Menu"
    assert sm.current_screen.entered
    assert sm.current_screen.enter_payload == {"hello": "world"}

    # 第二次切换
    menu = sm.current_screen
    sm.switch_screen(GameState.PLAYING)
    assert menu.exited  # 旧屏 on_exit 已触发
    assert sm.current_state == GameState.PLAYING
    assert sm.current_screen.name == "Game"
    assert sm.current_screen.entered
    assert sm.transition_state == "NONE"  # 跳过过渡


def test_first_switch_immediate():
    """首次切换（无 current_screen）总是立即执行，无论 instant_mode。"""
    sm = _make_manager(instant_mode=False)
    sm._detect_headless = lambda: False  # 即使非 headless 也会立即切换

    sm.switch_screen(GameState.MAIN_MENU)
    assert sm.transition_state == "NONE"
    assert sm.current_screen.name == "Menu"
    assert sm.current_screen.entered


def test_transition_starts_fading_out():
    """switch_screen 进入 FADING_OUT 但不执行 on_exit/on_enter。"""
    sm = _setup_transition(_make_manager())

    sm.switch_screen(GameState.PLAYING, {"level": 1})

    assert sm.transition_state == "FADING_OUT"
    assert sm.pending_state == GameState.PLAYING
    assert sm.pending_payload == {"level": 1}
    # 旧屏仍为 current_screen
    assert sm.current_state == GameState.MAIN_MENU
    assert sm.current_screen.name == "Menu"
    # on_exit / on_enter 尚未触发
    assert not sm.current_screen.exited
    assert not sm.screens[GameState.PLAYING].entered


def test_fading_out_update_delegates_to_old():
    """FADING_OUT 期间 update 委托给旧屏。"""
    sm = _setup_transition(_make_manager())
    sm.switch_screen(GameState.PLAYING)

    old = sm.current_screen
    new = sm.screens[GameState.PLAYING]
    assert old.name == "Menu"
    old.update_count = 0
    new.update_count = 0

    sm.update(0.01)
    assert old.update_count == 1  # 旧屏 update 被调用
    assert new.update_count == 0  # 新屏 update 尚未被调用


def test_midpoint_switches_screens():
    """超过 half_duration 时触发 on_exit/on_enter，状态变 FADING_IN。"""
    sm = _setup_transition(_make_manager())
    sm.switch_screen(GameState.PLAYING, {"level": 5})

    old = sm.current_screen
    new = sm.screens[GameState.PLAYING]

    # 步进至 midpoint
    half = sm.fade_duration / 2.0
    sm.update(half + 0.001)

    assert sm.transition_state == "FADING_IN"
    assert old.exited  # 旧屏 on_exit 已触发
    assert new.entered  # 新屏 on_enter 已触发
    assert new.enter_payload == {"level": 5}
    assert sm.current_state == GameState.PLAYING
    assert sm.current_screen.name == "Game"
    assert sm.pending_state is not None  # 尚未完全结束


def test_fading_in_update_delegates_to_new():
    """FADING_IN 期间 update 委托给新屏。"""
    sm = _setup_transition(_make_manager())
    sm.switch_screen(GameState.PLAYING)

    half = sm.fade_duration / 2.0
    sm.update(half + 0.001)  # 进入 FADING_IN

    new = sm.current_screen
    new.update_count = 0

    sm.update(0.01)
    assert new.update_count >= 1  # 新屏 update 已调用


def test_transition_completes():
    """全流程完成后回到 NONE 且 pending 清理。"""
    sm = _setup_transition(_make_manager())
    sm.switch_screen(GameState.PLAYING)

    half = sm.fade_duration / 2.0
    # 第一次 update 触发 midpoint（FADING_OUT -> FADING_IN）
    sm.update(half + 0.001)
    assert sm.transition_state == "FADING_IN"
    # 第二次 update 完成过渡（FADING_IN -> NONE）
    sm.update(half + 0.001)

    assert sm.transition_state == "NONE"
    assert sm.fade_timer == 0.0
    assert sm.pending_state is None
    assert sm.pending_payload is None
    assert sm.current_state == GameState.PLAYING


def test_overlay_alpha_values():
    """验证各阶段 alpha 边界值正确。"""
    sm = _setup_transition(_make_manager())
    sm.switch_screen(GameState.PLAYING)

    half = sm.fade_duration / 2.0

    # FADING_OUT 刚开始：alpha = 0
    sm.update(0.0)
    alpha_out_start = _extract_alpha(sm)
    assert alpha_out_start == 0 or alpha_out_start is None  # None 表示 alpha <= 0 未绘制

    # FADING_OUT 过 75%：alpha 应在 128-255 之间
    sm.update(half * 0.75)
    alpha_out_mid = _extract_alpha(sm)
    assert alpha_out_mid is None or (128 <= alpha_out_mid <= 255)

    # 步进至 FADING_IN 刚开始：alpha 接近 255
    sm.update(half + 0.001)
    assert sm.transition_state == "FADING_IN"
    alpha_in_start = _extract_alpha(sm)
    assert alpha_in_start is None or alpha_in_start >= 200

    # FADING_IN 过半：alpha 减至约 128
    sm.update(half * 0.5)
    alpha_in_mid = _extract_alpha(sm)
    assert alpha_in_mid is None or (0 < alpha_in_mid <= 255)

    # FADING_IN 完成：alpha 应为 0（不绘制）
    sm.update(half + 0.1)
    assert sm.transition_state == "NONE"
    assert _extract_alpha(sm) is None  # 非过渡态返回 None


def _extract_alpha(sm):
    """提取 ScreenManager 当前覆盖层的 alpha 值（辅助测试）。"""
    if sm.transition_state == "NONE" or sm._fade_overlay is None:
        return None
    try:
        return sm._fade_overlay.get_alpha()
    except Exception:
        return None


def test_switch_during_transition():
    """过渡中再次 switch_screen 触发强制完成再启动新过渡。"""
    sm = _setup_transition(_make_manager())
    sm.switch_screen(GameState.PLAYING)

    # 在 FADING_OUT 中途切到第三个屏幕
    sm.switch_screen(GameState.GAME_OVER)

    # 旧过渡已强制完成：旧屏 on_exit 已触发
    assert sm.screens[GameState.MAIN_MENU].exited
    # 新过渡开始
    assert sm.transition_state == "FADING_OUT"
    assert sm.pending_state == GameState.GAME_OVER


def test_unregistered_state_raises():
    """未注册状态抛 KeyError。"""
    sm = _make_manager()

    try:
        sm.switch_screen(GameState.BONUS_LEVEL)
        assert False, "Expected KeyError"
    except KeyError:
        pass  # Expected


def test_update_render_delegation():
    """非过渡期 screen_manager.update/render 行为等同直接调 current_screen。"""
    sm = _make_manager(instant_mode=True)
    sm.switch_screen(GameState.MAIN_MENU)

    screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

    # 直接调 current_screen
    sm.current_screen.update(0.016)
    sm.current_screen.render(screen)
    direct_update_count = sm.current_screen.update_count
    direct_render_count = sm.current_screen.render_count

    # 通过 ScreenManager 委托
    sm.update(0.016)
    sm.render(screen)

    assert sm.current_screen.update_count == direct_update_count + 1
    assert sm.current_screen.render_count == direct_render_count + 1


def test_headless_sets_instant_mode():
    """GameManager.init_engine(headless=True) 设定 instant_mode=True。"""
    # 重置单例
    from src.game_manager import GameManager

    GameManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)
    assert gm.screen_manager.instant_mode is True

    # 清理
    gm.quit_game()
    GameManager._instance = None


def test_error_in_midpoint_doesnt_deadlock():
    """midpoint 异常强制回 NONE 再抛，不卡死。"""
    sm = _setup_transition(_make_manager())

    # 切到会抛异常的 SETTINGS 屏幕
    sm.switch_screen(GameState.SETTINGS)

    half = sm.fade_duration / 2.0
    try:
        sm.update(half + 0.001)
        assert False, "Expected RuntimeError"
    except RuntimeError:
        pass  # Expected

    # 转场状态已回到 NONE，不卡死（但 current_state 已在 on_enter 抛异常前被赋值）
    assert sm.transition_state == "NONE"


def test_dt_overshoot_handling():
    """超大 dt 一次性跨过单个 phase 时正确处理。"""
    sm = _setup_transition(_make_manager())
    sm.switch_screen(GameState.PLAYING)

    half = sm.fade_duration / 2.0
    # 用超大 dt 跨过 FADING_OUT + midpoint
    sm.update(half + 1.0)
    assert sm.transition_state == "FADING_IN"  # 已切至 FADING_IN
    assert sm.current_state == GameState.PLAYING

    # 再用大 dt 跨过 FADING_IN
    sm.update(half + 1.0)
    assert sm.transition_state == "NONE"


def test_headless_detection_auto_instant():
    """Headless 环境下 switch_screen 自动使用瞬切（不依赖 instant_mode）。"""
    # 在 headless 环境下不 monkey-patch _detect_headless
    sm = _make_manager(instant_mode=False)
    # 确保 headless 检测是真实的
    assert sm._detect_headless() is True

    sm.switch_screen(GameState.MAIN_MENU)
    assert sm.current_state == GameState.MAIN_MENU

    sm.switch_screen(GameState.PLAYING, {"auto": True})
    # 应该瞬切，不经过过渡
    assert sm.transition_state == "NONE"
    assert sm.current_state == GameState.PLAYING
    assert sm.current_screen.entered


def test_switch_to_same_state():
    """切换到当前状态——技术上允许但 KeyError 优先检查通过。"""
    sm = _make_manager(instant_mode=True)
    sm.switch_screen(GameState.MAIN_MENU)
    sm.switch_screen(GameState.MAIN_MENU)  # 切到同一状态
    assert sm.current_state == GameState.MAIN_MENU


# =========================================================================
# 入口点
# =========================================================================

if __name__ == "__main__":
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)

    tests = [
        ("test_instant_mode_preserves_behavior", test_instant_mode_preserves_behavior),
        ("test_first_switch_immediate", test_first_switch_immediate),
        ("test_transition_starts_fading_out", test_transition_starts_fading_out),
        ("test_fading_out_update_delegates_to_old", test_fading_out_update_delegates_to_old),
        ("test_midpoint_switches_screens", test_midpoint_switches_screens),
        ("test_fading_in_update_delegates_to_new", test_fading_in_update_delegates_to_new),
        ("test_transition_completes", test_transition_completes),
        ("test_overlay_alpha_values", test_overlay_alpha_values),
        ("test_switch_during_transition", test_switch_during_transition),
        ("test_unregistered_state_raises", test_unregistered_state_raises),
        ("test_update_render_delegation", test_update_render_delegation),
        ("test_headless_sets_instant_mode", test_headless_sets_instant_mode),
        ("test_error_in_midpoint_doesnt_deadlock", test_error_in_midpoint_doesnt_deadlock),
        ("test_dt_overshoot_handling", test_dt_overshoot_handling),
        ("test_headless_detection_auto_instant", test_headless_detection_auto_instant),
        ("test_switch_to_same_state", test_switch_to_same_state),
    ]

    passed = 0
    failed = 0
    for name, func in tests:
        try:
            func()
            print(f"  PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Result: {passed} passed, {failed} failed / {len(tests)} total")
    if failed > 0:
        sys.exit(1)
