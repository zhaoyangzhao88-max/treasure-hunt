"""GameplayScreen 与 Camera 验证脚本 — Microsoft Treasure Hunt

Headless 模式下注册并初始化 GameplayScreen，验证：
- 关卡初始化（新游戏 / 续档）
- 键盘方向移动
- 鼠标点击转化与范围越界
- 摄像机平滑更新
- 摄像机边界钳制
- 视口裁剪

运行方式::

    python tests/test_gameplay_screen.py
"""

import os
import sys

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Headless 模式：必须在 pygame.init() 之前设置
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from src.config import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_HEIGHT, TILE_SIZE
from src.camera import Camera
from src.map_data import GameMap
from src.player_state import PlayerState
from src.level_generator import LevelGenerator
from src.interaction_controller import InteractionController
from src.screens.gameplay_screen import GameplayScreen


# =============================================================================
# 辅助函数
# =============================================================================

def _make_screen() -> GameplayScreen:
    """创建并初始化一个 GameplayScreen（headless 模式）。"""
    # 确保 pygame 已初始化
    if not pygame.get_init():
        pygame.init()

    screen = GameplayScreen()
    # 注入 game_manager 引用（避免真正初始化整个引擎）
    # 使用最小 mock 对象
    class FakeGameManager:
        def __init__(self):
            self.player_state = PlayerState()
            self.screen_manager = None
            self.asset_manager = None
            self.save_manager = None

    screen.game_manager = FakeGameManager()

    # 关键修复：确保 GameManager 单例也有 PlayerState
    # 当 on_enter() 用真实单例覆盖 fake 时不会因 player_state=None 崩溃
    from src.game_manager import GameManager
    gm = GameManager.get_instance()
    if gm.player_state is None:
        gm.player_state = PlayerState()

    return screen


def _make_camera() -> Camera:
    """创建一个新的 Camera 实例。"""
    return Camera()


# =============================================================================
# 测试用例
# =============================================================================

def test_level_init_new_game():
    """测试新游戏初始化：on_enter 无 payload → level 1，GameMap 实例正确创建。"""
    screen = _make_screen()
    screen.on_enter(data_payload=None)

    assert screen.current_level_num == 1, f"新游戏应为 level 1，得到 {screen.current_level_num}"
    assert screen.game_map is not None, "game_map 不应为 None"
    # 使用属性检查代替 isinstance（避免双重导入路径导致的类身份不一致）
    assert hasattr(screen.game_map, 'layer0') and hasattr(screen.game_map, 'traps'), (
        "game_map 应具有 GameMap 的关键属性"
    )
    assert screen.interaction_controller is not None, "interaction_controller 不应为 None"
    assert screen.camera is not None, "camera 不应为 None"

    # 玩家应位于起点 (1, 1)
    assert screen.interaction_controller.player_x == 1
    assert screen.interaction_controller.player_y == 1

    print("[PASS] test_level_init_new_game")


def test_level_init_continue():
    """测试续档初始化：on_enter 传入 continue=True + highest_level_cleared=5 → level 5。"""
    screen = _make_screen()
    screen.on_enter(data_payload={"continue": True, "highest_level_cleared": 5})

    assert screen.current_level_num == 5, f"续档应为 level 5，得到 {screen.current_level_num}"
    assert screen.game_map is not None
    assert hasattr(screen.game_map, 'layer0') and hasattr(screen.game_map, 'traps')

    print("[PASS] test_level_init_continue")


def test_keyboard_move_right():
    """测试键盘右移：模拟 K_RIGHT 事件，验证 player_x 增加。"""
    screen = _make_screen()
    screen.on_enter(data_payload=None)

    initial_x = screen.interaction_controller.player_x
    initial_y = screen.interaction_controller.player_y

    # 揭开目标格确保可行走（is_walkable 要求 layer0 == UNCOVERED）
    target_x = initial_x + 1
    target_y = initial_y
    if screen.game_map.is_in_bounds(target_x, target_y):
        screen.game_map.layer0[target_y][target_x] = "UNCOVERED"

    # 模拟按键事件
    event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RIGHT})
    screen.handle_event(event)

    assert screen.interaction_controller.player_x == initial_x + 1, (
        f"右移后 player_x 应为 {initial_x + 1}，得到 {screen.interaction_controller.player_x}"
    )
    assert screen.interaction_controller.player_y == initial_y, (
        f"右移不应改变 player_y，得到 {screen.interaction_controller.player_y}"
    )

    print("[PASS] test_keyboard_move_right")


def test_keyboard_move_all_directions():
    """测试所有方向移动：WASD 和方向键。

    注意：迷宫生成器中偶坐标为墙体，玩家位于 (1,1)（奇坐标通道）。
    可移动方向为 (2,1)（右）和 (1,2)（下）。
    (0,1) 和 (1,0) 是边界墙体，无法移动。
    测试策略：先右移，再下移，再左移回，再上移回。
    """
    screen = _make_screen()
    screen.on_enter(data_payload=None)

    px = screen.interaction_controller.player_x
    py = screen.interaction_controller.player_y

    # 揭开可通行格（直接设置 layer0，因为 is_walkable 要求 UNCOVERED）
    for dx, dy in [(1, 0), (0, 1), (2, 0), (0, 2)]:
        nx, ny = px + dx, py + dy
        if screen.game_map.is_in_bounds(nx, ny):
            screen.game_map.layer0[ny][nx] = "UNCOVERED"

    # 测试 K_d (右) — 从 (1,1) 到 (2,1)
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_d}))
    assert screen.interaction_controller.player_x == px + 1, (
        f"K_d 后 player_x 应为 {px+1}，得到 {screen.interaction_controller.player_x}"
    )
    assert screen.interaction_controller.player_y == py

    # 测试 K_s (下) — 从 (2,1) 到 (2,2) 不可行（WALL），改到 (1,2) 需要先左移
    # 先左移回 (1,1)
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_a}))
    assert screen.interaction_controller.player_x == px, (
        f"K_a 后 player_x 应为 {px}，得到 {screen.interaction_controller.player_x}"
    )

    # 测试 K_s (下) — 从 (1,1) 到 (1,2)
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_s}))
    assert screen.interaction_controller.player_x == px
    assert screen.interaction_controller.player_y == py + 1, (
        f"K_s 后 player_y 应为 {py+1}，得到 {screen.interaction_controller.player_y}"
    )

    # 测试 K_w (上) — 从 (1,2) 回到 (1,1)
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_w}))
    assert screen.interaction_controller.player_x == px
    assert screen.interaction_controller.player_y == py, (
        f"K_w 后 player_y 应为 {py}，得到 {screen.interaction_controller.player_y}"
    )

    print("[PASS] test_keyboard_move_all_directions")


def test_mouse_click_hud_invalid():
    """测试鼠标点击 HUD 区域：应返回 (-1, -1)。"""
    cam = _make_camera()
    # 点击 HUD 区域（Y < HUD_HEIGHT）
    result = cam.screen_to_grid(512, HUD_HEIGHT - 1)
    assert result == (-1, -1), f"HUD 区域点击应返回 (-1, -1)，得到 {result}"

    result = cam.screen_to_grid(0, 0)
    assert result == (-1, -1), f"Y=0 应返回 (-1, -1)，得到 {result}"

    print("[PASS] test_mouse_click_hud_invalid")


def test_mouse_click_game_area_conversion():
    """测试鼠标点击游戏渲染区：正确转化为网格坐标。"""
    cam = _make_camera()
    cam.offset_x = 0.0
    cam.offset_y = 0.0

    # 点击屏幕中心偏下（在游戏渲染区）
    # 屏幕坐标 (SCREEN_WIDTH/2, HUD_HEIGHT + TILE_SIZE/2) 应映射到网格 (0, 0) 附近
    screen_x = SCREEN_WIDTH // 2
    screen_y = HUD_HEIGHT + TILE_SIZE // 2
    grid_x, grid_y = cam.screen_to_grid(screen_x, screen_y)

    # 由于 offset=0，screen_x ≈ 512，grid_x = int(512/48) = 10
    expected_gx = int((screen_x + 0) / TILE_SIZE)
    expected_gy = int((screen_y - HUD_HEIGHT + 0) / TILE_SIZE)

    assert grid_x == expected_gx, f"grid_x 应为 {expected_gx}，得到 {grid_x}"
    assert grid_y == expected_gy, f"grid_y 应为 {expected_gy}，得到 {grid_y}"

    # 验证偏移后的转化
    cam.offset_x = 48.0  # 向右移动一格
    cam.offset_y = 48.0  # 向下移动一格
    grid_x2, grid_y2 = cam.screen_to_grid(screen_x, screen_y)
    expected_gx2 = int((screen_x + 48) / TILE_SIZE)
    expected_gy2 = int((screen_y - HUD_HEIGHT + 48) / TILE_SIZE)

    assert grid_x2 == expected_gx2, f"偏移后 grid_x 应为 {expected_gx2}，得到 {grid_x2}"
    assert grid_y2 == expected_gy2, f"偏移后 grid_y 应为 {expected_gy2}，得到 {grid_y2}"

    print("[PASS] test_mouse_click_game_area_conversion")


def test_camera_smooth_follow():
    """测试摄像机平滑跟随：玩家移动后，update(0.1) 使 offset 向玩家靠近。"""
    cam = _make_camera()

    # 玩家位于屏幕中心以右的像素位置（确保 target > 0）
    # SCREEN_WIDTH=1024, HUD_HEIGHT=96, game viewport height=672
    # target_x = player_px_x - 512, target_y = player_px_y - 96 - 336 = player_px_y - 432
    player_px_x = 1000.0
    player_px_y = 800.0
    map_width_px = 3000
    map_height_px = 3000

    # 初始偏移为 0
    cam.offset_x = 0.0
    cam.offset_y = 0.0

    # 记录初始偏移
    initial_offset_x = cam.offset_x
    initial_offset_y = cam.offset_y

    # 更新摄像机
    cam.update(player_px_x, player_px_y, map_width_px, map_height_px, 0.1)

    # 偏移应增加（向玩家方向移动）
    assert cam.offset_x > initial_offset_x, (
        f"摄像机 offset_x 应向玩家靠近（增加），"
        f"初始={initial_offset_x}，更新后={cam.offset_x}"
    )
    assert cam.offset_y > initial_offset_y, (
        f"摄像机 offset_y 应向玩家靠近（增加），"
        f"初始={initial_offset_y}，更新后={cam.offset_y}"
    )

    # 多次更新后应更接近目标
    for _ in range(20):
        cam.update(player_px_x, player_px_y, map_width_px, map_height_px, 0.1)

    target_x = player_px_x - SCREEN_WIDTH / 2
    target_y = player_px_y - HUD_HEIGHT - (SCREEN_HEIGHT - HUD_HEIGHT) / 2
    # 允许一定误差（lerp 渐进，不会完全到达）
    assert abs(cam.offset_x - target_x) < target_x * 0.1, (
        f"多次更新后 offset_x 应接近目标 {target_x}，得到 {cam.offset_x}"
    )
    assert abs(cam.offset_y - target_y) < target_y * 0.1, (
        f"多次更新后 offset_y 应接近目标 {target_y}，得到 {cam.offset_y}"
    )

    print("[PASS] test_camera_smooth_follow")


def test_camera_clamp_at_origin():
    """测试摄像机边界钳制：玩家靠近 (0,0) 时，偏移不为负值。"""
    cam = _make_camera()

    # 玩家位于地图原点
    player_px_x = 0.0
    player_px_y = 0.0
    map_width_px = 2000
    map_height_px = 2000

    cam.update(player_px_x, player_px_y, map_width_px, map_height_px, 0.1)

    assert cam.offset_x >= 0.0, f"offset_x 不应为负，得到 {cam.offset_x}"
    assert cam.offset_y >= 0.0, f"offset_y 不应为负，得到 {cam.offset_y}"

    # 玩家位于极小地图（比视口还小）
    cam2 = _make_camera()
    cam2.update(24.0, 24.0, 48, 48, 0.1)

    assert cam2.offset_x == 0.0, f"小地图 offset_x 应钳制为 0，得到 {cam2.offset_x}"
    assert cam2.offset_y == 0.0, f"小地图 offset_y 应钳制为 0，得到 {cam2.offset_y}"

    print("[PASS] test_camera_clamp_at_origin")


def test_camera_clamp_at_far_edge():
    """测试摄像机边界钳制：玩家位于地图远端时，偏移不超出最大值。"""
    cam = _make_camera()

    map_width_px = 2000
    map_height_px = 2000
    # 玩家位于地图最远端
    player_px_x = 1999.0
    player_px_y = 1999.0

    # 多次更新让摄像机趋近
    for _ in range(100):
        cam.update(player_px_x, player_px_y, map_width_px, map_height_px, 0.1)

    max_x = max(0, map_width_px - SCREEN_WIDTH)
    max_y = max(0, map_height_px - (SCREEN_HEIGHT - HUD_HEIGHT))

    assert cam.offset_x <= max_x + 0.01, (
        f"offset_x 应 <= {max_x}，得到 {cam.offset_x}"
    )
    assert cam.offset_y <= max_y + 0.01, (
        f"offset_y 应 <= {max_y}，得到 {cam.offset_y}"
    )

    print("[PASS] test_camera_clamp_at_far_edge")


def test_camera_visible_tile_bounds():
    """测试视口裁剪：get_visible_tile_bounds 返回合理区间。"""
    cam = _make_camera()

    map_cols = 50
    map_rows = 50

    # 摄像机在原点
    cam.offset_x = 0.0
    cam.offset_y = 0.0
    start_col, end_col, start_row, end_row = cam.get_visible_tile_bounds(map_cols, map_rows)

    assert 0 <= start_col < end_col <= map_cols, (
        f"列范围应在 [0, {map_cols}] 内，得到 start_col={start_col}, end_col={end_col}"
    )
    assert 0 <= start_row < end_row <= map_rows, (
        f"行范围应在 [0, {map_rows}] 内，得到 start_row={start_row}, end_row={end_row}"
    )

    # 摄像机移动到地图中间
    cam.offset_x = 500.0
    cam.offset_y = 400.0
    start_col, end_col, start_row, end_row = cam.get_visible_tile_bounds(map_cols, map_rows)

    assert 0 <= start_col < end_col <= map_cols
    assert 0 <= start_row < end_row <= map_rows

    # 摄像机移动到地图边缘
    cam.offset_x = 2000.0
    cam.offset_y = 2000.0
    start_col, end_col, start_row, end_row = cam.get_visible_tile_bounds(map_cols, map_rows)

    assert 0 <= start_col < end_col <= map_cols, (
        f"边缘处列范围应合法，得到 start_col={start_col}, end_col={end_col}"
    )
    assert 0 <= start_row < end_row <= map_rows, (
        f"边缘处行范围应合法，得到 start_row={start_row}, end_row={end_row}"
    )

    print("[PASS] test_camera_visible_tile_bounds")


def test_gameplay_screen_render():
    """测试渲染流程：headless 模式下调用 render 不抛异常。"""
    if not pygame.get_init():
        pygame.init()

    screen = _make_screen()
    screen.on_enter(data_payload=None)

    # 创建 NOFRAME surface 用于 headless 渲染
    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

    # 渲染不应抛异常
    screen.render(surface)

    print("[PASS] test_gameplay_screen_render")


def test_gameplay_screen_update():
    """测试更新流程：headless 模式下调用 update 不抛异常。"""
    screen = _make_screen()
    screen.on_enter(data_payload=None)

    # 更新摄像机
    screen.update(0.016)  # 约 60fps 的 dt

    # 摄像机偏移应为有限数值（int 或 float 均可）
    assert isinstance(screen.camera.offset_x, (int, float)), (
        f"offset_x 应为数值，得到 {type(screen.camera.offset_x)}"
    )
    assert isinstance(screen.camera.offset_y, (int, float)), (
        f"offset_y 应为数值，得到 {type(screen.camera.offset_y)}"
    )

    print("[PASS] test_gameplay_screen_update")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    test_level_init_new_game()
    test_level_init_continue()
    test_keyboard_move_right()
    test_keyboard_move_all_directions()
    test_mouse_click_hud_invalid()
    test_mouse_click_game_area_conversion()
    test_camera_smooth_follow()
    test_camera_clamp_at_origin()
    test_camera_clamp_at_far_edge()
    test_camera_visible_tile_bounds()
    test_gameplay_screen_update()
    test_gameplay_screen_render()
    print("\n=== ALL TESTS PASSED ===")
