"""实时小地图（Minimap）系统验证脚本 — Microsoft Treasure Hunt

Headless 模式下验证：
- 自适应像素比计算（不同地图尺寸）
- minimap_width / minimap_height 与地图尺寸一致
- 默认 visible = True
- toggle() 切换 True ↔ False
- 渲染不崩溃（GameMap / Surface / Camera 均有效）
- 渲染不崩溃（camera=None 时跳过视口框线）
- visible=False 时 render() 提前返回（不绘制任何像素）
- 渲染后小地图 Surface 右下角区域存在非零像素
- 玩家标记颜色像素存在
- GameplayScreen 集成：Tab 键切换 minimap.visible
- BonusLevelScreen 集成：Tab 键切换 minimap.visible

运行方式::

    python tests/test_minimap.py
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
from src.map_data import GameMap
from src.camera import Camera
from src.minimap import Minimap, MINIMAP_MAX_SIZE, PLAYER_DOT_SIZE
from src.player_state import PlayerState


# =============================================================================
# 辅助函数
# =============================================================================

def _ensure_pygame():
    """确保 Pygame 已初始化（headless dummy 驱动）。"""
    if not pygame.get_init():
        pygame.init()
    try:
        pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    except Exception:
        pass


def _make_map(w: int, h: int) -> GameMap:
    """创建指定尺寸的测试地图（默认全 DIRT）。"""
    return GameMap(w, h)


def _make_camera() -> Camera:
    """创建一个简单 Camera 实例（偏移归零）。"""
    cam = Camera()
    cam.offset_x = 0.0
    cam.offset_y = 0.0
    return cam


# =============================================================================
# 测试 1：自适应像素比计算
# =============================================================================

def test_pixel_size_scaling():
    """不同地图尺寸下 pixel_size 自适应计算正确。"""
    # 小地图 8×8 → pixel_size = max(1, 180 // 8) = 22
    mm8 = Minimap(_make_map(8, 8), 0, 0)
    assert mm8.pixel_size == max(1, MINIMAP_MAX_SIZE // 8), (
        f"8×8 地图 pixel_size 期望 {max(1, MINIMAP_MAX_SIZE // 8)}，"
        f"得到 {mm8.pixel_size}"
    )
    # 大地图 40×40 → pixel_size = max(1, 180 // 40) = 4
    mm40 = Minimap(_make_map(40, 40), 0, 0)
    assert mm40.pixel_size == max(1, MINIMAP_MAX_SIZE // 40), (
        f"40×40 地图 pixel_size 期望 {max(1, MINIMAP_MAX_SIZE // 40)}，"
        f"得到 {mm40.pixel_size}"
    )
    # 中等地图 15×15 → pixel_size = max(1, 180 // 15) = 12
    mm15 = Minimap(_make_map(15, 15), 0, 0)
    assert mm15.pixel_size == max(1, MINIMAP_MAX_SIZE // 15), (
        f"15×15 地图 pixel_size 期望 {max(1, MINIMAP_MAX_SIZE // 15)}，"
        f"得到 {mm15.pixel_size}"
    )


# =============================================================================
# 测试 2：minimap_width / minimap_height 与地图尺寸一致
# =============================================================================

def test_minimap_dimensions():
    """minimap_width / minimap_height 正确映射地图尺寸。"""
    gm = _make_map(20, 30)
    mm = Minimap(gm, 0, 0)
    ps = mm.pixel_size
    assert mm.minimap_width == 20 * ps, (
        f"minimap_width 期望 {20 * ps}，得到 {mm.minimap_width}"
    )
    assert mm.minimap_height == 30 * ps, (
        f"minimap_height 期望 {30 * ps}，得到 {mm.minimap_height}"
    )


# =============================================================================
# 测试 3：默认 visible = True
# =============================================================================

def test_default_visible():
    """Minimap 默认应为可见。"""
    mm = Minimap(_make_map(10, 10), 0, 0)
    assert mm.visible is True, "默认 visible 应为 True"


# =============================================================================
# 测试 4：toggle() 切换 True ↔ False
# =============================================================================

def test_toggle():
    """toggle() 在 True ↔ False 之间交替。"""
    mm = Minimap(_make_map(10, 10), 0, 0)
    assert mm.visible is True
    mm.toggle()
    assert mm.visible is False, "第一次 toggle 后应为 False"
    mm.toggle()
    assert mm.visible is True, "第二次 toggle 后应为 True"
    mm.toggle()
    assert mm.visible is False, "第三次 toggle 后应为 False"


# =============================================================================
# 测试 5：渲染不崩溃（有 Camera）
# =============================================================================

def test_render_no_crash_with_camera():
    """render() 在有 Camera 时不崩溃。"""
    _ensure_pygame()
    gm = _make_map(15, 15)
    mm = Minimap(gm, 5, 5)
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    cam = _make_camera()
    # 不应抛出任何异常
    mm.render(surf, cam)


# =============================================================================
# 测试 6：渲染不崩溃（camera=None）
# =============================================================================

def test_render_no_crash_without_camera():
    """render() 在 camera=None 时不崩溃（跳过视口框线）。"""
    _ensure_pygame()
    gm = _make_map(15, 15)
    mm = Minimap(gm, 5, 5)
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    # 不应抛出任何异常
    mm.render(surf, camera=None)


# =============================================================================
# 测试 7：visible=False 时 render() 提前返回（不绘制像素）
# =============================================================================

def test_render_skip_when_hidden():
    """visible=False 时 render() 不修改目标 Surface。"""
    _ensure_pygame()
    gm = _make_map(15, 15)
    mm = Minimap(gm, 5, 5)
    mm.toggle()  # → False
    assert mm.visible is False

    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))
    # 保存渲染前快照
    before = surf.copy()

    mm.render(surf, camera=None)

    # 全像素一致 → render 没有绘制任何东西
    assert pygame.image.tostring(surf, "RGB") == pygame.image.tostring(before, "RGB"), (
        "visible=False 时 render() 不应修改 Surface"
    )


# =============================================================================
# 测试 8：渲染后右下角区域存在非零像素
# =============================================================================

def test_render_produces_pixels():
    """render() 后右下角区域应有非零像素（确认小地图被绘制）。"""
    _ensure_pygame()
    gm = _make_map(15, 15)
    mm = Minimap(gm, 5, 5)
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))

    mm.render(surf, camera=None)

    # 检查右下角小地图区域是否有非零像素
    from src.minimap import MINIMAP_MARGIN
    dest_x = SCREEN_WIDTH - mm.minimap_width - MINIMAP_MARGIN
    dest_y = SCREEN_HEIGHT - mm.minimap_height - MINIMAP_MARGIN
    # 裁剪小地图区域
    region = surf.subsurface(pygame.Rect(dest_x, dest_y, mm.minimap_width, mm.minimap_height))

    has_nonzero = False
    for y in range(region.get_height()):
        for x in range(region.get_width()):
            if region.get_at((x, y))[:3] != (0, 0, 0):
                has_nonzero = True
                break
        if has_nonzero:
            break

    assert has_nonzero, "渲染后右下角小地图区域应存在非零像素"


# =============================================================================
# 测试 9：玩家标记颜色像素存在
# =============================================================================

def test_player_dot_rendered():
    """render() 后小地图上应存在玩家颜色（青蓝色）像素。"""
    _ensure_pygame()
    gm = _make_map(15, 15)
    mm = Minimap(gm, 7, 7)
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))

    mm.render(surf, camera=None)

    from src.minimap import MINIMAP_MARGIN, _MINIMAP_COLORS
    dest_x = SCREEN_WIDTH - mm.minimap_width - MINIMAP_MARGIN
    dest_y = SCREEN_HEIGHT - mm.minimap_height - MINIMAP_MARGIN
    region = surf.subsurface(pygame.Rect(dest_x, dest_y, mm.minimap_width, mm.minimap_height))

    player_color = _MINIMAP_COLORS["PLAYER"]
    dot_x = 7 * mm.pixel_size
    dot_y = 7 * mm.pixel_size

    # 检查玩家标记中心像素
    px_color = region.get_at((dot_x, dot_y))[:3]
    assert px_color == player_color, (
        f"玩家标记位置像素颜色应为 {player_color}，得到 {px_color}"
    )


# =============================================================================
# 测试 10：GameplayScreen 集成 — Tab 切换 minimap.visible
# =============================================================================

def test_gameplay_tab_toggles_minimap():
    """GameplayScreen 中按 Tab 键切换 minimap.visible。"""
    _ensure_pygame()

    from src.game_manager import GameManager
    from src.screens.gameplay_screen import GameplayScreen

    # 重置 GameManager
    gm = GameManager.get_instance()
    gm.player_state = PlayerState()

    class FakeScreenManager:
        def __init__(self):
            self.last_state = None
            self.last_payload = None
            self.current_screen = None
        def switch_screen(self, new_state, data_payload=None):
            self.last_state = new_state
            self.last_payload = data_payload

    gm.screen_manager = FakeScreenManager()
    gm.suspended_level_state = None
    gm.asset_manager = None
    gm.save_manager = None

    screen = GameplayScreen()
    screen.on_enter(data_payload=None)

    # 确认小地图已初始化且默认可见
    assert screen.minimap is not None, "小地图应已初始化"
    assert screen.minimap.visible is True, "小地图默认应可见"

    # Tab → 隐藏
    tab_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_TAB})
    screen.handle_event(tab_event)
    assert screen.minimap.visible is False, "Tab 后小地图应隐藏"

    # Tab → 显示
    screen.handle_event(tab_event)
    assert screen.minimap.visible is True, "再次 Tab 后小地图应显示"


# =============================================================================
# 测试 11：BonusLevelScreen 集成 — Tab 切换 minimap.visible
# =============================================================================

def test_bonus_tab_toggles_minimap():
    """BonusLevelScreen 中按 Tab 键切换 minimap.visible。"""
    _ensure_pygame()

    from src.game_manager import GameManager
    from src.screens.bonus_level_screen import BonusLevelScreen

    gm = GameManager.get_instance()
    gm.player_state = PlayerState()

    class FakeScreenManager:
        def __init__(self):
            self.last_state = None
            self.last_payload = None
            self.current_screen = None
        def switch_screen(self, new_state, data_payload=None):
            self.last_state = new_state
            self.last_payload = data_payload

    gm.screen_manager = FakeScreenManager()
    gm.suspended_level_state = None

    # 需要最小 asset_manager / save_manager 存根
    gm.asset_manager = None
    gm.save_manager = None

    screen = BonusLevelScreen()
    screen.on_enter()

    # 确认小地图已初始化且默认可见
    assert screen.minimap is not None, "奖励关小地图应已初始化"
    assert screen.minimap.visible is True, "奖励关小地图默认应可见"

    # Tab → 隐藏
    tab_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_TAB})
    screen.handle_event(tab_event)
    assert screen.minimap.visible is False, "Tab 后奖励关小地图应隐藏"

    # Tab → 显示
    screen.handle_event(tab_event)
    assert screen.minimap.visible is True, "再次 Tab 后奖励关小地图应显示"


# =============================================================================
# 测试 12：视口框线绘制（有 Camera 时存在白色像素）
# =============================================================================

def test_viewport_rect_drawn():
    """render() 在有 Camera 时小地图上应有视口框线白色像素。"""
    _ensure_pygame()
    gm = _make_map(30, 30)
    mm = Minimap(gm, 5, 5)
    cam = _make_camera()

    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))
    mm.render(surf, camera=cam)

    from src.minimap import MINIMAP_MARGIN, _MINIMAP_COLORS
    dest_x = SCREEN_WIDTH - mm.minimap_width - MINIMAP_MARGIN
    dest_y = SCREEN_HEIGHT - mm.minimap_height - MINIMAP_MARGIN
    region = surf.subsurface(pygame.Rect(dest_x, dest_y, mm.minimap_width, mm.minimap_height))

    white = _MINIMAP_COLORS["VIEWPORT"]
    # 在整个 minimap Surface 上搜索白色像素（视口框线）
    found_white = False
    for y in range(region.get_height()):
        for x in range(region.get_width()):
            if region.get_at((x, y))[:3] == white:
                found_white = True
                break
        if found_white:
            break

    assert found_white, "视口框线应在小地图上产生白色像素"


# =============================================================================
# 测试 13：minimap.player_x / player_y 动态更新
# =============================================================================

def test_player_coords_update():
    """动态更新 player_x / player_y 后渲染的玩家位置应随之改变。"""
    _ensure_pygame()
    gm = _make_map(15, 15)
    mm = Minimap(gm, 2, 2)

    # 更新坐标
    mm.player_x = 10
    mm.player_y = 10

    assert mm.player_x == 10, "player_x 应动态更新为 10"
    assert mm.player_y == 10, "player_y 应动态更新为 10"

    # 渲染后验证新位置有玩家颜色
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))
    mm.render(surf, camera=None)

    from src.minimap import MINIMAP_MARGIN, _MINIMAP_COLORS
    dest_x = SCREEN_WIDTH - mm.minimap_width - MINIMAP_MARGIN
    dest_y = SCREEN_HEIGHT - mm.minimap_height - MINIMAP_MARGIN
    region = surf.subsurface(pygame.Rect(dest_x, dest_y, mm.minimap_width, mm.minimap_height))

    player_color = _MINIMAP_COLORS["PLAYER"]
    dot_x = 10 * mm.pixel_size
    dot_y = 10 * mm.pixel_size
    px_color = region.get_at((dot_x, dot_y))[:3]
    assert px_color == player_color, (
        f"更新后玩家标记位置像素应为 {player_color}，得到 {px_color}"
    )


# =============================================================================
# 入口（standalone 运行）
# =============================================================================

if __name__ == "__main__":
    tests = [
        ("test_pixel_size_scaling",         test_pixel_size_scaling),
        ("test_minimap_dimensions",         test_minimap_dimensions),
        ("test_default_visible",            test_default_visible),
        ("test_toggle",                     test_toggle),
        ("test_render_no_crash_with_camera", test_render_no_crash_with_camera),
        ("test_render_no_crash_without_camera", test_render_no_crash_without_camera),
        ("test_render_skip_when_hidden",    test_render_skip_when_hidden),
        ("test_render_produces_pixels",     test_render_produces_pixels),
        ("test_player_dot_rendered",        test_player_dot_rendered),
        ("test_gameplay_tab_toggles_minimap", test_gameplay_tab_toggles_minimap),
        ("test_bonus_tab_toggles_minimap",  test_bonus_tab_toggles_minimap),
        ("test_viewport_rect_drawn",        test_viewport_rect_drawn),
        ("test_player_coords_update",       test_player_coords_update),
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
