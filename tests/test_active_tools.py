"""主动工具（炸药、地图）验证脚本 — Microsoft Treasure Hunt

验证炸药 3x3 无伤爆破、地图 5x5 自动插旗以及 GameplayScreen 输入状态机转换。
使用 Headless 模式，通过 `python tests/test_active_tools.py` 直接运行。
"""

import os
import sys

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Headless 模式：必须在 pygame.init() 之前设置
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from src.interaction_controller import InteractionController
from src.map_data import GameMap
from src.player_state import PlayerState
from src.config import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_HEIGHT, TILE_SIZE


# =============================================================================
# 辅助函数
# =============================================================================

def _make_screen():
    """创建并初始化一个 GameplayScreen（headless 模式）。

    使用 FakeGameManager 注入，通过替换 GameManager.get_instance 使其在 on_enter 中被使用。
    """
    from src.screens.gameplay_screen import GameplayScreen
    from src.game_manager import GameManager

    if not pygame.get_init():
        pygame.init()

    class FakeGameManager:
        def __init__(self):
            self.player_state = PlayerState()
            self.screen_manager = None
            self.asset_manager = None
            self.save_manager = None

    fake_gm = FakeGameManager()
    screen = GameplayScreen()

    # Monkey-patch GameManager.get_instance to return our fake
    original_get_instance = GameManager.get_instance
    GameManager.get_instance = classmethod(lambda cls: fake_gm)
    try:
        screen.on_enter(data_payload=None)
    finally:
        GameManager.get_instance = original_get_instance

    # 确保 on_enter 后 game_manager 引用正确
    screen.game_manager = fake_gm
    return screen


# =============================================================================
# 测试炸药爆破
# =============================================================================

def test_use_dynamite_full_blast():
    """测试炸药 3x3 无伤爆破完整效果。

    布置 5x5 地图，中心 (2,2) 为爆破点：
    - 周围放置 DIRT_WALL、MONSTER、隐藏陷阱、埋藏 COIN
    - 给予玩家 1 个炸药
    - 在中心触发 use_dynamite(2, 2)
    - 验证所有效果 + 玩家生命值无损
    """
    m = GameMap(5, 5)

    # 布置地图：全部默认为 DIRT
    # 在 (1,1) 放置 DIRT_WALL（可破坏泥墙）
    m.set_obstacle(1, 1, "DIRT_WALL")

    # 在 (3,1) 放置 DIRT_WALL
    m.set_obstacle(3, 1, "DIRT_WALL")

    # 在 (1,3) 放置 WALL（不可破坏墙，应免疫）
    m.set_obstacle(1, 3, "WALL")

    # 在 (3,2) 放置 MONSTER（应气化）
    m.set_entity(3, 2, "MONSTER")

    # 在 (2,1) 放置隐藏陷阱
    m.traps[1][2] = True

    # 在 (2,3) 埋藏 COIN（layer2 泥土下）
    m.set_entity(2, 3, "COIN")

    # 在 (3,3) 放置另一处隐藏陷阱
    m.traps[3][3] = True

    # 给玩家 1 个炸药
    p = PlayerState()
    p.add_tool("dynamite", 1)
    initial_hearts = p.current_hearts

    ctrl = InteractionController(m, p, start_x=2, start_y=2)

    # 执行爆破
    result = ctrl.use_dynamite(2, 2)
    assert result is True, "use_dynamite 应返回 True"

    # 炸药消耗
    assert p.tools["dynamite"] == 0, f"炸药应消耗为 0，得到 {p.tools['dynamite']}"

    # DIRT_WALL 粉碎
    assert m.layer1[1][1] == "NONE", f"(1,1) DIRT_WALL 应被粉碎，得到 {m.layer1[1][1]}"
    assert m.layer1[1][3] == "NONE", f"(3,1) DIRT_WALL 应被粉碎，得到 {m.layer1[1][3]}"

    # WALL 免疫
    assert m.layer1[3][1] == "WALL", f"(1,3) WALL 应免疫，得到 {m.layer1[3][1]}"

    # 泥土强揭为 UNCOVERED
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            tx, ty = 2 + dx, 2 + dy
            if m.is_in_bounds(tx, ty) and m.layer1[ty][tx] != "WALL":
                assert m.layer0[ty][tx] == "UNCOVERED", (
                    f"({tx},{ty}) 泥土应变为 UNCOVERED，得到 {m.layer0[ty][tx]}"
                )

    # 隐藏陷阱清除（无伤）
    assert m.traps[1][2] is False, "(2,1) 陷阱应被清除"
    assert m.traps[3][3] is False, "(3,3) 陷阱应被清除"

    # 怪物气化
    assert m.layer2[2][3] == "NONE", f"(3,2) MONSTER 应被气化，得到 {m.layer2[2][3]}"

    # COIN 保留在原地
    assert m.layer2[3][2] == "COIN", f"(2,3) COIN 应保留，得到 {m.layer2[3][2]}"

    # 玩家生命值无损
    assert p.current_hearts == initial_hearts, (
        f"玩家生命值不应变化，初始={initial_hearts}，当前={p.current_hearts}"
    )

    print("[PASS] test_use_dynamite_full_blast")


def test_use_dynamite_no_dynamite():
    """测试无炸药时返回 False。"""
    m = GameMap(5, 5)
    p = PlayerState()
    # 不给玩家炸药
    ctrl = InteractionController(m, p, start_x=2, start_y=2)

    result = ctrl.use_dynamite(2, 2)
    assert result is False, "无炸药时 use_dynamite 应返回 False"

    print("[PASS] test_use_dynamite_no_dynamite")


def test_use_dynamite_lock_exit_immune():
    """测试 LOCK_EXIT 免疫爆炸。"""
    m = GameMap(5, 5)
    m.set_obstacle(2, 1, "LOCK_EXIT")  # 上方一格放置 LOCK_EXIT

    p = PlayerState()
    p.add_tool("dynamite", 1)
    ctrl = InteractionController(m, p, start_x=2, start_y=2)

    result = ctrl.use_dynamite(2, 2)
    assert result is True, "use_dynamite 应返回 True"

    # LOCK_EXIT 不受影响
    assert m.layer1[1][2] == "LOCK_EXIT", (
        f"LOCK_EXIT 应免疫，得到 {m.layer1[1][2]}"
    )

    print("[PASS] test_use_dynamite_lock_exit_immune")


def test_use_dynamite_flag_clearing():
    """测试爆破时自动清除红旗标记。"""
    m = GameMap(5, 5)
    # 在 (1,1) 插上红旗
    m.flags[1][1] = True

    p = PlayerState()
    p.add_tool("dynamite", 1)
    ctrl = InteractionController(m, p, start_x=2, start_y=2)

    result = ctrl.use_dynamite(2, 2)
    assert result is True

    # 红旗应被清除（泥土被揭开后标志自动移除）
    assert m.flags[1][1] is False, "(1,1) 红旗应被清除"

    print("[PASS] test_use_dynamite_flag_clearing")


# =============================================================================
# 测试地图扫描
# =============================================================================

def test_use_map_auto_flagging():
    """测试地图 5x5 扫描自动插旗。

    以玩家 (2,2) 为中心，在 5x5 内放置数个隐藏陷阱和安全泥土。
    调用 use_map() 后验证：有陷阱的泥土被插旗，安全泥土不插旗。
    """
    m = GameMap(5, 5)

    # 放置隐藏陷阱（默认为 DIRT + traps=True）
    m.traps[0][0] = True
    m.traps[1][1] = True
    m.traps[3][3] = True
    m.traps[4][4] = True

    # 安全泥土（DIRT + traps=False）— 不插旗
    # (0,1) (1,0) (4,0) (0,4) 保持默认 DIRT + traps=False

    p = PlayerState()
    p.add_tool("map", 1)
    ctrl = InteractionController(m, p, start_x=2, start_y=2)

    result = ctrl.use_map()
    assert result is True, "use_map 应返回 True"

    # 地图消耗
    assert p.tools["map"] == 0, f"地图应消耗为 0，得到 {p.tools['map']}"

    # 有陷阱的泥土应被插旗
    assert m.flags[0][0] is True, "(0,0) 应有陷阱，应被插旗"
    assert m.flags[1][1] is True, "(1,1) 应有陷阱，应被插旗"
    assert m.flags[3][3] is True, "(3,3) 应有陷阱，应被插旗"
    assert m.flags[4][4] is True, "(4,4) 应有陷阱，应被插旗"

    # 安全泥土不应被插旗
    assert m.flags[1][0] is False, "(0,1) 安全泥土不应插旗"
    assert m.flags[0][1] is False, "(1,0) 安全泥土不应插旗"
    assert m.flags[0][4] is False, "(4,0) 安全泥土不应插旗"
    assert m.flags[4][0] is False, "(0,4) 安全泥土不应插旗"

    print("[PASS] test_use_map_auto_flagging")


def test_use_map_no_map():
    """测试无地图时返回 False。"""
    m = GameMap(5, 5)
    p = PlayerState()
    # 不给玩家地图
    ctrl = InteractionController(m, p, start_x=2, start_y=2)

    result = ctrl.use_map()
    assert result is False, "无地图时 use_map 应返回 False"

    print("[PASS] test_use_map_no_map")


def test_use_map_already_flagged():
    """测试已有红旗的陷阱格不会重复操作但保持 flag=True。"""
    m = GameMap(5, 5)
    m.traps[1][1] = True
    m.flags[1][1] = True  # 已有红旗

    p = PlayerState()
    p.add_tool("map", 1)
    ctrl = InteractionController(m, p, start_x=2, start_y=2)

    result = ctrl.use_map()
    assert result is True

    # 红旗应保持为 True
    assert m.flags[1][1] is True, "(1,1) 已有红旗应保持 True"

    print("[PASS] test_use_map_already_flagged")


# =============================================================================
# 测试 GameplayScreen 输入状态机
# =============================================================================

def test_input_mode_switch_to_dynamite():
    """测试按下 B 键进入 DYNAMITE 瞄准模式。"""
    if not pygame.get_init():
        pygame.init()

    screen = _make_screen()
    # _make_screen 已调用 on_enter，无需重复调用

    # 确保玩家有炸药
    screen.game_manager.player_state.add_tool("dynamite", 1)

    # 初始应为 EXPLORE
    assert screen.input_mode == "EXPLORE", f"初始模式应为 EXPLORE，得到 {screen.input_mode}"

    # 模拟 K_b 按键
    event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_b})
    screen.handle_event(event)

    assert screen.input_mode == "DYNAMITE", (
        f"K_b 后 input_mode 应为 DYNAMITE，得到 {screen.input_mode}"
    )

    print("[PASS] test_input_mode_switch_to_dynamite")


def test_input_mode_escape_resets():
    """测试 ESC 键切换暂停菜单（ESC 已升级为暂停触发器）。

    原 DYNAMITE 取消语义已迁移到暂停态机制：进入暂停时 input_mode
    强制压为 EXPLORE 并通过 _saved_input_mode 记录先前模式，恢复时原样还原。
    """
    if not pygame.get_init():
        pygame.init()

    screen = _make_screen()

    # 默认应未暂停
    assert screen.show_paused is False

    # 模拟 ESC
    event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE})
    screen.handle_event(event)

    # 应进入暂停态
    assert screen.show_paused is True, "ESC 后应进入暂停态"
    # ESC 进入暂停时 input_mode 被强制设为 EXPLORE 与 _saved_input_mode 机制
    assert screen.input_mode == "EXPLORE"

    # 再按一次 ESC 退出暂停
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))
    assert screen.show_paused is False

    print("[PASS] test_input_mode_escape_resets")


def test_dynamite_mode_click_triggers_blast():
    """测试 DYNAMITE 模式下鼠标左键触发爆破并自动回到 EXPLORE。"""
    if not pygame.get_init():
        pygame.init()

    screen = _make_screen()

    # 给炸药
    screen.game_manager.player_state.add_tool("dynamite", 1)

    # 进入 DYNAMITE 模式
    screen.input_mode = "DYNAMITE"

    # 模拟鼠标点击地图中心（对应 grid 坐标需要看摄像机位置）
    # 摄像机初始化后 snap 到玩家位置 (1,1) 的像素中心
    # 玩家位于 (1,1)，像素 (1*TILE_SIZE + TILE_SIZE/2, 1*TILE_SIZE + TILE_SIZE/2)
    # 屏幕坐标 offset_x = player_px_x - SCREEN_WIDTH/2
    # 点击屏幕中心应映射到靠近玩家的格子
    cam = screen.camera
    player_px_x = screen.interaction_controller.player_x * TILE_SIZE + TILE_SIZE // 2
    player_px_y = screen.interaction_controller.player_y * TILE_SIZE + TILE_SIZE // 2

    # 点击玩家所在格对应的屏幕位置
    screen_x = player_px_x - int(cam.offset_x)
    screen_y = player_px_y - int(cam.offset_y) + HUD_HEIGHT

    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": (screen_x, screen_y), "button": 1}
    )
    screen.handle_event(event)

    # 触发爆破后应回到 EXPLORE
    assert screen.input_mode == "EXPLORE", (
        f"爆破后 input_mode 应为 EXPLORE，得到 {screen.input_mode}"
    )

    # 炸药被消耗
    assert screen.game_manager.player_state.tools["dynamite"] == 0, (
        "炸药应被消耗"
    )

    print("[PASS] test_dynamite_mode_click_triggers_blast")


def test_key_2_also_triggers_dynamite_mode():
    """测试 K_2 键同样可进入 DYNAMITE 模式。"""
    if not pygame.get_init():
        pygame.init()

    screen = _make_screen()
    screen.game_manager.player_state.add_tool("dynamite", 1)

    event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_2})
    screen.handle_event(event)

    assert screen.input_mode == "DYNAMITE", (
        f"K_2 后 input_mode 应为 DYNAMITE，得到 {screen.input_mode}"
    )

    print("[PASS] test_key_2_also_triggers_dynamite_mode")


def test_key_m_triggers_map():
    """测试 K_m 键触发地图扫描。"""
    if not pygame.get_init():
        pygame.init()

    screen = _make_screen()
    screen.game_manager.player_state.add_tool("map", 1)

    # 放置一个隐藏陷阱
    # 玩家位于 (1,1)，5x5 范围覆盖 (0..3, 0..3)（受边界限制）
    screen.game_map.traps[0][0] = True

    event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_m})
    screen.handle_event(event)

    # 地图被消耗
    assert screen.game_manager.player_state.tools["map"] == 0, "地图应被消耗"

    # 陷阱位置应被插旗
    assert screen.game_map.flags[0][0] is True, "(0,0) 应被插旗"

    # 输入模式不变（仍为 EXPLORE）
    assert screen.input_mode == "EXPLORE", "使用地图不改变输入模式"

    print("[PASS] test_key_m_triggers_map")


def test_key_3_also_triggers_map():
    """测试 K_3 键同样可触发地图扫描。"""
    if not pygame.get_init():
        pygame.init()

    screen = _make_screen()
    screen.game_manager.player_state.add_tool("map", 1)
    # 在 (col=1, row=0) 放置隐藏陷阱 — 强制设为 DIRT 确保地图扫描能识别
    screen.game_map.layer0[0][1] = "DIRT"
    screen.game_map.traps[0][1] = True

    event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_3})
    screen.handle_event(event)

    assert screen.game_manager.player_state.tools["map"] == 0, "地图应被消耗"
    assert screen.game_map.flags[0][1] is True, "(col=1, row=0) 应被插旗"

    print("[PASS] test_key_3_also_triggers_map")


def test_dynamite_mode_without_tool_no_switch():
    """测试无炸药时按 B 键不切换模式。"""
    if not pygame.get_init():
        pygame.init()

    screen = _make_screen()
    # 不给玩家炸药

    event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_b})
    screen.handle_event(event)

    assert screen.input_mode == "EXPLORE", (
        f"无炸药时 K_b 不应切换模式，得到 {screen.input_mode}"
    )

    print("[PASS] test_dynamite_mode_without_tool_no_switch")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    # 炸药测试
    test_use_dynamite_full_blast()
    test_use_dynamite_no_dynamite()
    test_use_dynamite_lock_exit_immune()
    test_use_dynamite_flag_clearing()

    # 地图测试
    test_use_map_auto_flagging()
    test_use_map_no_map()
    test_use_map_already_flagged()

    # GameplayScreen 状态机测试
    test_input_mode_switch_to_dynamite()
    test_input_mode_escape_resets()
    test_dynamite_mode_click_triggers_blast()
    test_key_2_also_triggers_dynamite_mode()
    test_key_m_triggers_map()
    test_key_3_also_triggers_map()
    test_dynamite_mode_without_tool_no_switch()

    print("\n=== ALL TESTS PASSED ===")
