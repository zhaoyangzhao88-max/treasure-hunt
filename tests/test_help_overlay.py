"""玩法指南蒙层（HelpOverlay）与游戏时停暂停机制验证脚本 — Microsoft Treasure Hunt

Headless 模式下验证：
- H / F1 切换 help 开 / 关
- 帮助开启时键盘移动被完全拦截
- 帮助开启时鼠标点击开掘 / 标雷被完全拦截
- 帮助开启时 effects_manager / damage_flash_timer 推进被冻结
- 帮助开启时 BonusLevelScreen 30 秒倒计时冻结
- 帮助开启下 render 无崩溃

运行方式::

    python tests/test_help_overlay.py
"""

import os
import sys

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Headless 模式：必须在 pygame.init() 之前设置
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from src.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    HUD_HEIGHT,
    TILE_SIZE,
)
from src.player_state import PlayerState
from src.game_manager import GameManager
from src.screens.gameplay_screen import GameplayScreen
from src.screens.bonus_level_screen import BonusLevelScreen, BONUS_TIMER
from src.help_overlay import HelpOverlay


# =============================================================================
# 桩替身
# =============================================================================

class FakeScreenManager:
    """最小 ScreenManager 桩 — 记录 switch_screen 调用，不执行实际跳转。"""
    def __init__(self):
        self.last_state = None
        self.last_payload = None
        self.current_screen = None

    def switch_screen(self, new_state, data_payload=None):
        self.last_state = new_state
        self.last_payload = data_payload


# =============================================================================
# 辅助函数
# =============================================================================

def _reset_gm():
    """重置 GameManager 单例为测试用干净状态。"""
    if not pygame.get_init():
        pygame.init()
    # 给 dummy 驱动一个最小 display mode（部分 pygame 版本需要）
    try:
        pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    except Exception:
        pass
    gm = GameManager.get_instance()
    gm.player_state = PlayerState()
    gm.screen_manager = FakeScreenManager()
    gm.suspended_level_state = None
    gm.asset_manager = None
    gm.save_manager = None
    return gm


def _make_gameplay_screen() -> GameplayScreen:
    """创建并初始化一个 GameplayScreen（headless 模式）。"""
    gm = _reset_gm()
    screen = GameplayScreen()
    # 注入最小 game_manager（避免不必要地初始化整棵引擎）
    class FakeGameManager:
        def __init__(self):
            self.player_state = PlayerState()
            self.screen_manager = gm.screen_manager
            self.asset_manager = None
            self.save_manager = None

    screen.game_manager = FakeGameManager()
    # 确保 GameManager 单例 player_state 非 None
    if gm.player_state is None:
        gm.player_state = PlayerState()
    return screen


def _make_bonus_screen(gm) -> BonusLevelScreen:
    """创建并初始化一个 BonusLevelScreen。"""
    screen = BonusLevelScreen()
    screen.game_manager = gm
    screen.screen_manager = gm.screen_manager
    return screen


def _key_event(key: int) -> pygame.event.Event:
    """构造一个 KEYDOWN 事件。"""
    return pygame.event.Event(pygame.KEYDOWN, {"key": key})


def _mouse_event(button: int, pos: tuple) -> pygame.event.Event:
    """构造一个 MOUSEBUTTONDOWN 事件。"""
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
        "button": button,
        "pos": pos,
    })


# =============================================================================
# 测试 1：H / F1 切换触发
# =============================================================================

def test_h_f1_toggles_help():
    """GameplayScreen：按 K_h / K_F1 切换 show_help 布尔值。"""
    screen = _make_gameplay_screen()
    screen.on_enter(data_payload=None)

    # 初始关闭
    assert screen.show_help is False, "帮助蒙层默认应为关闭"

    # K_h → True
    screen.handle_event(_key_event(pygame.K_h))
    assert screen.show_help is True, "K_h 应打开帮助"

    # K_F1 → False
    screen.handle_event(_key_event(pygame.K_F1))
    assert screen.show_help is False, "K_F1 应关闭帮助"

    # K_F1 → True（只按 F1 也能打开）
    screen.handle_event(_key_event(pygame.K_F1))
    assert screen.show_help is True, "K_F1 应打开帮助"

    # K_h → False（切回）
    screen.handle_event(_key_event(pygame.K_h))
    assert screen.show_help is False, "K_h 应再次关闭帮助"


# =============================================================================
# 测试 2：按键与鼠标拦截（GameplayScreen）
# =============================================================================

def test_input_frozen_while_help_open():
    """帮助开启时：模拟鼠标点击 + 键盘移动被完全拦截。"""
    screen = _make_gameplay_screen()
    screen.on_enter(data_payload=None)

    # 确保子系统健全
    assert screen.interaction_controller is not None
    assert screen.game_map is not None

    # 开启帮助
    screen.handle_event(_key_event(pygame.K_h))
    assert screen.show_help is True

    # 记录玩家当前位置
    px_before = screen.interaction_controller.player_x
    py_before = screen.interaction_controller.player_y

    # 鼠标点击（左上角第一块瓦片中心）— 该位置通常在地图内
    # 计算第一个格子的屏幕坐标（玩家所在格），用摄像机反推
    click_x = int(px_before * TILE_SIZE - screen.camera.offset_x + TILE_SIZE // 2)
    click_y = int(py_before * TILE_SIZE - screen.camera.offset_y + HUD_HEIGHT + TILE_SIZE // 2)
    screen.handle_event(_mouse_event(1, (click_x, click_y)))

    # 键盘移动（K_d → 右移）
    screen.handle_event(_key_event(pygame.K_d))

    # 玩家位置必须未发生任何偏移
    px_after = screen.interaction_controller.player_x
    py_after = screen.interaction_controller.player_y
    assert px_after == px_before, (
        f"帮助开启时键盘移动应被拦截：player_x 期望 {px_before}，得到 {px_after}"
    )
    assert py_after == py_before, (
        f"帮助开启时键盘移动应被拦截：player_y 期望 {py_before}，得到 {py_after}"
    )


# =============================================================================
# 测试 3：effects_manager / damage_flash_timer 时停保护
# =============================================================================

def test_effects_paused_while_help_open():
    """帮助开启时：effects_manager 推进停止、damage_flash_timer 不衰减。"""
    screen = _make_gameplay_screen()
    screen.on_enter(data_payload=None)

    assert screen.effects_manager is not None

    # 注入一个 1s 生命期的浮动文本
    screen.effects_manager.spawn_text(200.0, 200.0, "TEST", (255, 255, 255), font_size=20)
    assert len(screen.effects_manager.floating_texts) >= 1, "spawn_text 后应至少存在一条浮动文本"
    ft = screen.effects_manager.floating_texts[0]
    lifetime_before = ft.lifetime

    # 设置受击闪烁
    screen.damage_flash_timer = 0.25

    # 记录摄像机偏移
    camera_ox_before = screen.camera.offset_x
    camera_oy_before = screen.camera.offset_y

    # 开启帮助
    screen.handle_event(_key_event(pygame.K_h))
    assert screen.show_help is True

    # 推进 0.5s
    screen.update(0.5)

    # 浮动文本 lifetime 应保持不变
    ft_after = screen.effects_manager.floating_texts[0] if screen.effects_manager.floating_texts else ft
    assert ft_after.lifetime == lifetime_before, (
        f"帮助开启时应冻结特效：lifetime 期望 {lifetime_before}，得到 {ft_after.lifetime}"
    )

    # 受击闪烁应未衰减
    assert screen.damage_flash_timer == 0.25, (
        f"帮助开启时应冻结受击闪烁：damage_flash_timer 期望 0.25，得到 {screen.damage_flash_timer}"
    )

    # 摄像机偏移应不变
    assert screen.camera.offset_x == camera_ox_before, (
        f"帮助开启时摄像机 offset_x 应冻结：期望 {camera_ox_before}，得到 {screen.camera.offset_x}"
    )
    assert screen.camera.offset_y == camera_oy_before, (
        f"帮助开启时摄像机 offset_y 应冻结：期望 {camera_oy_before}，得到 {screen.camera.offset_y}"
    )


# =============================================================================
# 测试 4：BonusLevelScreen 倒计时时停保护
# =============================================================================

def test_bonus_timer_frozen():
    """BonusLevelScreen：帮助开启时 30 秒倒计时不应减少。"""
    gm = _reset_gm()
    screen = _make_bonus_screen(gm)
    screen.on_enter()

    # 初始应激活且满 30 秒
    assert screen.bonus_active is True
    assert screen.timer == BONUS_TIMER, (
        f"初始倒计时应为 {BONUS_TIMER}，得到 {screen.timer}"
    )

    # 开启帮助
    screen.handle_event(_key_event(pygame.K_h))
    assert screen.show_help is True

    # 推进 5s × 3（共 15 秒）
    for i in range(3):
        screen.update(5.0)

    # 倒计时应死死锁定在 30.0
    assert screen.timer == BONUS_TIMER, (
        f"帮助开启时倒计时应冻结在 {BONUS_TIMER}，得到 {screen.timer}"
    )

    # 关闭帮助后再推进 5s → 应开始减少
    screen.handle_event(_key_event(pygame.K_h))
    assert screen.show_help is False
    screen.update(5.0)
    assert screen.timer == BONUS_TIMER - 5.0, (
        f"帮助关闭后倒计时应再次推进：期望 {BONUS_TIMER - 5.0}，得到 {screen.timer}"
    )


# =============================================================================
# 测试 5：蒙层渲染不崩溃
# =============================================================================

def test_render_does_not_crash():
    """GameplayScreen / BonusLevelScreen 在帮助开启下 render 无异常。"""
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

    # GameplayScreen
    g_screen = _make_gameplay_screen()
    g_screen.on_enter(data_payload=None)
    g_screen.handle_event(_key_event(pygame.K_h))
    assert g_screen.show_help is True
    g_screen.render(surf)

    # BonusLevelScreen
    gm = _reset_gm()
    b_screen = _make_bonus_screen(gm)
    b_screen.on_enter()
    b_screen.handle_event(_key_event(pygame.K_h))
    assert b_screen.show_help is True
    b_screen.render(surf)


# =============================================================================
# 测试 6：HelpOverlay 直接实例化 + 渲染不崩溃
# =============================================================================

def test_overlay_renders():
    """HelpOverlay().render() 应在空白 surface 上无异常。"""
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    overlay = HelpOverlay()
    overlay.render(surf)


# =============================================================================
# 入口（standalone 运行）
# =============================================================================

if __name__ == "__main__":
    tests = [
        ("test_h_f1_toggles_help",         test_h_f1_toggles_help),
        ("test_input_frozen_while_help_open", test_input_frozen_while_help_open),
        ("test_effects_paused_while_help_open", test_effects_paused_while_help_open),
        ("test_bonus_timer_frozen",         test_bonus_timer_frozen),
        ("test_render_does_not_crash",      test_render_does_not_crash),
        ("test_overlay_renders",            test_overlay_renders),
    ]

    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL  {name}: {type(exc).__name__}: {exc}")

    if failed == 0:
        print(f"\n=== 全部 {len(tests)} 项测试 PASS ===")
        sys.exit(0)
    else:
        print(f"\n=== {failed}/{len(tests)} 项测试 FAIL ===")
        sys.exit(1)
