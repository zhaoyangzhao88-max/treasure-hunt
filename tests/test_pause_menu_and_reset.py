"""第 45 课：暂停菜单与关卡重置单元测试 — Microsoft Treasure Hunt

Headless 模式下验证：
- 玩家状态快照 get/load 往返精确还原（永久字段不受影响）
- ESC 键切换暂停菜单
- 暂停态冻结 WASD / 方向键输入
- 继续 / 帮助 / 保存退出按钮路由正确
- 「重新开始本关」时空自愈：玩家数值精确还原 + 地图重生 + 控制器重连

运行方式::

    python tests/test_pause_menu_and_reset.py
    python -m pytest tests/test_pause_menu_and_reset.py -v
"""

import os
import sys

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Headless 模式：必须在 pygame.init() 之前设置
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from src.player_state import PlayerState
from src.screens.gameplay_screen import GameplayScreen
from src.pause_overlay import (
    PauseOverlay,
    ACTION_RESUME,
    ACTION_RESTART,
    ACTION_HELP,
    ACTION_SAVE_EXIT,
)


# =============================================================================
# 辅助函数
# =============================================================================


class _FakeScreenManager:
    """简易 screen_manager mock：记录 switch_screen 调用目标。"""

    def __init__(self):
        self.switched_to = None

    def switch_screen(self, state, data_payload=None):
        self.switched_to = state


class _FakeSaveManager:
    """简易 save_manager mock：记录 save 调用参数。"""

    def __init__(self):
        self.saved = []

    def save(self, player_data, settings_data=None):
        self.saved.append({"player": player_data, "settings": settings_data})
        return True


class _FakeGameManager:
    """最小 game_manager mock（满足 GameplayScreen 子系统的访问需求）。"""

    def __init__(self):
        self.player_state = PlayerState()
        self.screen_manager = _FakeScreenManager()
        self.asset_manager = None
        self.save_manager = _FakeSaveManager()
        self.settings_data = {"sound_volume": 1.0, "music_volume": 1.0}


def _make_screen() -> GameplayScreen:
    """创建并初始化一个 GameplayScreen（headless 模式 + mock 引擎）。

    关键：GameplayScreen.on_enter 通过 GameManager.get_instance() 重新拉取
    单例引用，所以这里必须把 fake 引擎注入单例，而非仅赋给局部变量。
    """
    if not pygame.get_init():
        pygame.init()

    from src.game_manager import GameManager

    # 强制重置单例，避免上一个测试的副作用污染
    GameManager._instance = None
    gm = GameManager.get_instance()

    # 覆写单例的关键子系统为 safe mock
    fake = _FakeGameManager()
    gm.player_state = fake.player_state
    gm.screen_manager = fake.screen_manager
    gm.asset_manager = fake.asset_manager
    gm.save_manager = fake.save_manager
    gm.settings_data = fake.settings_data

    screen = GameplayScreen()
    return screen


# =============================================================================
# 测试用例
# =============================================================================


def test_snapshot_get_load():
    """快照 get+load 往返测试：修改 PlayerState → 快照 → 重新创建 → 还原。"""
    ps = PlayerState()
    ps.gold = 123
    ps.tools["pickaxe"] = 2
    ps.current_shields = 1
    ps.keys["RED"] = 2
    ps.arrows = 3
    ps.has_machete = True
    ps.has_clover = True

    snap = ps.get_snapshot()

    # 重新创建全新 PlayerState（彻底清空数据）
    ps2 = PlayerState()
    assert ps2.gold == 0
    assert ps2.tools["pickaxe"] == 0
    assert ps2.current_shields == 0
    assert ps2.keys["RED"] == 0

    # 还原快照
    ps2.load_snapshot(snap)
    assert ps2.gold == 123, f"gold 应为 123，得到 {ps2.gold}"
    assert ps2.tools["pickaxe"] == 2
    assert ps2.current_shields == 1
    assert ps2.keys["RED"] == 2
    assert ps2.arrows == 3
    assert ps2.has_machete is True
    assert ps2.has_clover is True

    # 永久字段不应出现在快照中（仅验证键名，值仍保持 PlayerState 默认值）
    assert "max_hearts" not in snap, "快照不应包含 max_hearts（永久属性）"
    assert "bag_tier_index" not in snap, "快照不应包含 bag_tier_index（永久属性）"

    print("[PASS] test_snapshot_get_load")


def test_esc_toggles_pause():
    """ESC 切换暂停态测试：第一次 ESC 进暂停，第二次 ESC 退暂停。"""
    screen = _make_screen()
    screen.on_enter(data_payload=None)

    assert screen.show_paused is False

    # 第一次 ESC → 进入暂停
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))
    assert screen.show_paused is True
    assert screen.pause_overlay is not None

    # 第二次 ESC → 退出暂停
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))
    assert screen.show_paused is False

    print("[PASS] test_esc_toggles_pause")


def test_pause_freezes_input():
    """暂停态输入冻结：WASD / 方向键移动应被完全拦截。"""
    screen = _make_screen()
    screen.on_enter(data_payload=None)

    # 进入暂停
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))
    assert screen.show_paused is True

    # 记录当前位置
    x0 = screen.interaction_controller.player_x
    y0 = screen.interaction_controller.player_y

    # 尝试各种移动
    for key in (pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d,
                pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
        screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": key}))

    # 位置应完全不变
    assert screen.interaction_controller.player_x == x0, (
        f"暂停时 player_x 应不变，得到 {screen.interaction_controller.player_x} vs {x0}"
    )
    assert screen.interaction_controller.player_y == y0

    print("[PASS] test_pause_freezes_input")


def test_resume_button():
    """Resume 按钮路由测试：暂停态下调用 dispatch 后退出暂停。"""
    screen = _make_screen()
    screen.on_enter(data_payload=None)
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))
    assert screen.show_paused is True

    screen._dispatch_pause_action(ACTION_RESUME)
    assert screen.show_paused is False

    print("[PASS] test_resume_button")


def test_help_button():
    """Help 按钮路由：暂停 → 帮助无缝切换。"""
    screen = _make_screen()
    screen.on_enter(data_payload=None)
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))

    screen._dispatch_pause_action(ACTION_HELP)
    assert screen.show_paused is False
    assert screen.show_help is True

    print("[PASS] test_help_button")


def test_save_exit_button():
    """Save & Exit 按钮路由：触发持久化 + 切回主菜单。"""
    from src.config import GameState

    screen = _make_screen()
    screen.on_enter(data_payload=None)

    # 修改一些值以验证保存内容
    screen.game_manager.player_state.gold = 999
    screen.game_manager.player_state.current_hearts = 2

    screen._dispatch_pause_action(ACTION_SAVE_EXIT)

    # 应已触发落盘
    assert len(screen.game_manager.save_manager.saved) == 1, (
        f"save 应被调用 1 次，实际 {len(screen.game_manager.save_manager.saved)}"
    )
    saved_player = screen.game_manager.save_manager.saved[0]["player"]
    assert saved_player["gold"] == 999
    assert saved_player["current_hearts"] == 2

    # 应已切回 MAIN_MENU
    assert screen.game_manager.screen_manager.switched_to == GameState.MAIN_MENU

    print("[PASS] test_save_exit_button")


def test_restart_restores_state():
    """Restart Level 时空自愈：改数值 → 重启 → 完全还原 + 地图重生。"""
    screen = _make_screen()
    screen.on_enter(data_payload={"continue": False})

    # 打下初始快照（默认 gold=0, pickaxe=0, shields=0）
    snap = screen.level_start_player_snapshot
    assert snap is not None, "on_enter 后 level_start_player_snapshot 不应为 None"

    # 模拟本关内各类变化：拾取金币 / 工具、踩雷失去护盾等等
    screen.game_manager.player_state.gold = 150
    screen.game_manager.player_state.tools["pickaxe"] = 2
    screen.game_manager.player_state.current_shields = 0
    screen.game_manager.player_state.has_clover = True

    # 进入暂停并重启
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))
    screen._dispatch_pause_action(ACTION_RESTART)

    ps = screen.game_manager.player_state
    # 精确还原至初始快照
    assert ps.gold == snap["gold"], (
        f"gold 应还原为 {snap['gold']}，得到 {ps.gold}"
    )
    assert ps.tools["pickaxe"] == snap["tools"]["pickaxe"]
    assert ps.current_shields == snap["current_shields"]
    assert ps.has_clover == snap["has_clover"]
    # 暂停已退出
    assert screen.show_paused is False

    # 地图应已重生（仍是有效可行走地图）
    assert screen.game_map is not None
    assert screen.interaction_controller is not None
    # 玩家位置重置回起点 (1, 1)
    assert screen.interaction_controller.player_x == 1
    assert screen.interaction_controller.player_y == 1

    print("[PASS] test_restart_restores_state")


# =============================================================================
# 自运行入口
# =============================================================================

if __name__ == "__main__":
    test_snapshot_get_load()
    test_esc_toggles_pause()
    test_pause_freezes_input()
    test_resume_button()
    test_help_button()
    test_save_exit_button()
    test_restart_restores_state()
    print("\n[ALL PASS] 7/7 tests passed")
