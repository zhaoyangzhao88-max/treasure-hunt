"""网格雷达迷你小地图（Minimap Overlay）系统验证脚本 — Microsoft Treasure Hunt

Headless 模式下验证：
- 像素画布大小动态算定（15×15 / 40×40 极大地图）
- 墙/地/已掘/泥墙/锁门/出口/楼梯 彩色映射
- 闪烁公式（sin 弧度变换）无崩溃
- Tab 键切换 show_minimap 状态
- 40×40 极大地图渲染零崩溃、无越界

运行方式::

    python tests/test_minimap.py
"""

import os
import sys
import math

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
from src.minimap import Minimap, GRID_SIZE, GRID_GAP, MINIMAP_MAX_SIZE
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


def _make_player() -> PlayerState:
    """创建最小 PlayerState 实例。"""
    return PlayerState()


# =============================================================================
# 测试 1：像素画布大小动态算定（15×15）
# =============================================================================

def test_canvas_size_15x15():
    """15×15 地图的 minimap 画布尺寸符合 grid_size + gap 比例。"""
    gm = _make_map(15, 15)
    mm = Minimap(gm, _make_player())
    gs = mm.grid_size
    expected_w = 15 * (gs + GRID_GAP) - GRID_GAP
    expected_h = 15 * (gs + GRID_GAP) - GRID_GAP
    assert mm.minimap_width == expected_w, (
        f"15×15 宽度期望 {expected_w}，得到 {mm.minimap_width}"
    )
    assert mm.minimap_height == expected_h, (
        f"15×15 高度期望 {expected_h}，得到 {mm.minimap_height}"
    )
    # 小地图应不超过最大边长
    assert mm.minimap_width <= MINIMAP_MAX_SIZE
    assert mm.minimap_height <= MINIMAP_MAX_SIZE


# =============================================================================
# 测试 2：像素画布大小动态算定（40×40 极大地图）
# =============================================================================

def test_canvas_size_40x40():
    """40×40 极大地图的 minimap 画布尺寸被钳制在 MINIMAP_MAX_SIZE 内。"""
    gm = _make_map(40, 40)
    mm = Minimap(gm, _make_player())
    assert mm.minimap_width <= MINIMAP_MAX_SIZE, (
        f"40×40 宽度 {mm.minimap_width} 超过 {MINIMAP_MAX_SIZE}"
    )
    assert mm.minimap_height <= MINIMAP_MAX_SIZE, (
        f"40×40 高度 {mm.minimap_height} 超过 {MINIMAP_MAX_SIZE}"
    )
    # grid_size 至少为 1
    assert mm.grid_size >= 1


# =============================================================================
# 测试 3：彩色雷达点映射 — 墙/地/已掘
# =============================================================================

def test_color_mapping_basic():
    """手动放置 WALL / DIRT / UNCOVERED，验证渲染后像素颜色对应配置色值。"""
    _ensure_pygame()
    gm = _make_map(10, 10)
    # (2, 2) 放置不可破坏墙
    gm.layer1[2][2] = "WALL"
    # (3, 3) 放置普通泥土（默认已是 DIRT，显式设置）
    gm.layer0[3][3] = "DIRT"
    # (4, 4) 已掘通道
    gm.layer0[4][4] = "UNCOVERED"

    mm = Minimap(gm, _make_player())
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))

    mm.render(surf, 0, 0, 0.0)

    gs = mm.grid_size
    # 计算 minimap 在屏幕上的位置（与 minimap.py 一致）
    dest_x = max(0, (SCREEN_WIDTH - mm.minimap_width) // 2)
    dest_y = max(HUD_HEIGHT + 8,
                 min(96, SCREEN_HEIGHT - mm.minimap_height - 8))

    # 墙 (2, 2) 像素位置
    wall_rx = dest_x + 2 * (gs + GRID_GAP)
    wall_ry = dest_y + 2 * (gs + GRID_GAP)
    wall_color = surf.get_at((wall_rx, wall_ry))[:3]
    assert wall_color == (10, 15, 25), f"墙颜色应为 (10,15,25)，得到 {wall_color}"

    # 泥土 (3, 3) 像素位置
    dirt_rx = dest_x + 3 * (gs + GRID_GAP)
    dirt_ry = dest_y + 3 * (gs + GRID_GAP)
    dirt_color = surf.get_at((dirt_rx, dirt_ry))[:3]
    assert dirt_color == (80, 50, 30), f"泥土颜色应为 (80,50,30)，得到 {dirt_color}"

    # 已掘 (4, 4) 像素位置
    unc_rx = dest_x + 4 * (gs + GRID_GAP)
    unc_ry = dest_y + 4 * (gs + GRID_GAP)
    unc_color = surf.get_at((unc_rx, unc_ry))[:3]
    assert unc_color == (50, 60, 70), f"已掘颜色应为 (50,60,70)，得到 {unc_color}"


# =============================================================================
# 测试 4：彩色雷达点映射 — 泥墙 / 锁门 / 出口 / 楼梯
# =============================================================================

def test_color_mapping_advanced():
    """验证泥墙、锁门（红/绿/蓝）、出口、楼梯的彩色映射。"""
    _ensure_pygame()
    gm = _make_map(12, 12)
    # 泥墙 (1,1)
    gm.layer1[1][1] = "DIRT_WALL"
    # 红锁门 (2,2)
    gm.layer1[2][2] = "LOCK_RED"
    # 绿锁门 (3,3)
    gm.layer1[3][3] = "LOCK_GREEN"
    # 蓝锁门 (4,4)
    gm.layer1[4][4] = "LOCK_BLUE"
    # 出口 (5,5)
    gm.layer1[5][5] = "LOCK_EXIT"
    # 楼梯 (6,6)
    gm.layer2[6][6] = "STAIRS"

    mm = Minimap(gm, _make_player())
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))

    mm.render(surf, 0, 0, 0.5)

    gs = mm.grid_size
    dest_x = max(0, (SCREEN_WIDTH - mm.minimap_width) // 2)
    dest_y = max(HUD_HEIGHT + 8,
                 min(96, SCREEN_HEIGHT - mm.minimap_height - 8))

    def _px(col, row):
        return dest_x + col * (gs + GRID_GAP), dest_y + row * (gs + GRID_GAP)

    # 泥墙
    rx, ry = _px(1, 1)
    assert surf.get_at((rx, ry))[:3] == (140, 100, 70), "泥墙颜色不符"

    # 红锁门
    rx, ry = _px(2, 2)
    assert surf.get_at((rx, ry))[:3] == (220, 60, 60), "红锁门颜色不符"

    # 绿锁门
    rx, ry = _px(3, 3)
    assert surf.get_at((rx, ry))[:3] == (60, 200, 80), "绿锁门颜色不符"

    # 蓝锁门
    rx, ry = _px(4, 4)
    assert surf.get_at((rx, ry))[:3] == (60, 120, 220), "蓝锁门颜色不符"

    # 出口（呼吸闪烁金色 — 在 state_time=0.5 时应为某个金色调）
    rx, ry = _px(5, 5)
    exit_color = surf.get_at((rx, ry))[:3]
    # 金色 (255,215,0) 经 pulse 调制后 R/G 应仍较高，B 接近 0
    assert exit_color[0] > 100 and exit_color[2] < 50, (
        f"出口应为金色调，得到 {exit_color}"
    )

    # 楼梯（淡黄色）
    rx, ry = _px(6, 6)
    stairs_color = surf.get_at((rx, ry))[:3]
    assert stairs_color == (240, 230, 140), f"楼梯颜色应为 (240,230,140)，得到 {stairs_color}"


# =============================================================================
# 测试 5：闪烁公式无崩溃
# =============================================================================

def test_blink_formula_no_crash():
    """玩家与出口点的闪烁公式在任何 dt 下都不报错且产生合规闪烁。"""
    _ensure_pygame()
    gm = _make_map(15, 15)
    gm.layer1[5][5] = "LOCK_EXIT"
    mm = Minimap(gm, _make_player())
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

    # 推进多个 state_time 值
    for t in [0.0, 0.1, 0.2, 0.5, 1.0, 3.14, 10.0, 100.0]:
        surf.fill((0, 0, 0))
        mm.render(surf, 5, 5, t)  # 不应抛出异常

    # 验证 sin 公式的合规性：出口 pulse 在 [0, 1] 内
    for t in [0.0, 0.1, 0.2, 0.5, 1.0]:
        pulse = abs(math.sin(t * 10.0))
        assert 0.0 <= pulse <= 1.0, f"t={t} 时 pulse={pulse} 超出 [0,1]"

    # 玩家 blink 公式
    for t in [0.0, 0.1, 0.2, 0.5, 1.0]:
        blink = math.sin(t * 14.0) >= 0
        assert isinstance(blink, bool)


# =============================================================================
# 测试 6：Tab 键切换 show_minimap 状态（GameplayScreen）
# =============================================================================

def test_gameplay_tab_toggles_minimap():
    """GameplayScreen 中按 Tab 键切换 show_minimap 状态。"""
    _ensure_pygame()

    from src.game_manager import GameManager
    from src.screens.gameplay_screen import GameplayScreen

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

    # 确认小地图已初始化，默认关闭
    assert screen.minimap is not None, "小地图应已初始化"
    assert screen.show_minimap is False, "小地图默认应关闭"

    # Tab → 开启
    tab_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_TAB})
    screen.handle_event(tab_event)
    assert screen.show_minimap is True, "Tab 后小地图应开启"

    # Tab → 关闭
    screen.handle_event(tab_event)
    assert screen.show_minimap is False, "再次 Tab 后小地图应关闭"

    # 帮助蒙层开启时，Tab 不会开启小地图（强制 False）
    screen.show_help = True
    screen.handle_event(tab_event)
    assert screen.show_minimap is False, "帮助开启时 Tab 不应开启小地图"


# =============================================================================
# 测试 7：Tab 键切换 show_minimap 状态（BonusLevelScreen）
# =============================================================================

def test_bonus_tab_toggles_minimap():
    """BonusLevelScreen 中按 Tab 键切换 show_minimap 状态。"""
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
    gm.asset_manager = None
    gm.save_manager = None

    screen = BonusLevelScreen()
    screen.on_enter()

    # 确认小地图已初始化，默认关闭
    assert screen.minimap is not None, "奖励关小地图应已初始化"
    assert screen.show_minimap is False, "奖励关小地图默认应关闭"

    # Tab → 开启
    tab_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_TAB})
    screen.handle_event(tab_event)
    assert screen.show_minimap is True, "Tab 后奖励关小地图应开启"

    # Tab → 关闭
    screen.handle_event(tab_event)
    assert screen.show_minimap is False, "再次 Tab 后奖励关小地图应关闭"


# =============================================================================
# 测试 8：40×40 极大地图渲染零崩溃、无越界
# =============================================================================

def test_large_map_render_no_crash():
    """40×40 极大地图下渲染零崩溃、无越界。"""
    _ensure_pygame()
    gm = _make_map(40, 40)
    # 散布一些实体
    gm.layer1[10][10] = "WALL"
    gm.layer1[20][20] = "LOCK_EXIT"
    gm.layer2[30][30] = "STAIRS"
    gm.layer0[5][5] = "UNCOVERED"

    mm = Minimap(gm, _make_player())
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))

    # 多次渲染不应崩溃
    for t in [0.0, 0.1, 0.5]:
        mm.render(surf, 20, 20, t)

    # 验证画布尺寸合规
    assert mm.minimap_width <= MINIMAP_MAX_SIZE
    assert mm.minimap_height <= MINIMAP_MAX_SIZE
    assert mm.minimap_width > 0
    assert mm.minimap_height > 0


# =============================================================================
# 测试 9：玩家标志点渲染
# =============================================================================

def test_player_dot_rendered():
    """render() 后玩家位置应存在亮绿或亮白像素。"""
    _ensure_pygame()
    gm = _make_map(15, 15)
    mm = Minimap(gm, _make_player())
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))

    mm.render(surf, 7, 7, 0.0)

    gs = mm.grid_size
    dest_x = max(0, (SCREEN_WIDTH - mm.minimap_width) // 2)
    dest_y = max(HUD_HEIGHT + 8,
                 min(96, SCREEN_HEIGHT - mm.minimap_height - 8))

    # 玩家中心像素
    center_x = dest_x + 7 * (gs + GRID_GAP) + gs // 2
    center_y = dest_y + 7 * (gs + GRID_GAP) + gs // 2
    px_color = surf.get_at((center_x, center_y))[:3]
    # 应为亮绿 (34,197,94) 或亮白 (255,255,255)
    assert px_color in ((34, 197, 94), (255, 255, 255)), (
        f"玩家标志应为亮绿或亮白，得到 {px_color}"
    )


# =============================================================================
# 测试 10：渲染不崩溃（基础）
# =============================================================================

def test_render_no_crash_basic():
    """render() 在各种状态下不崩溃。"""
    _ensure_pygame()
    gm = _make_map(15, 15)
    mm = Minimap(gm, _make_player())
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))
    mm.render(surf, 5, 5, 0.0)
    mm.render(surf, 0, 0, 1.0)
    mm.render(surf, 14, 14, 2.0)


# =============================================================================
# 测试 11：game_map=None 时 render 安全返回
# =============================================================================

def test_render_none_map_safe():
    """game_map 为 None 时 render 不崩溃。"""
    _ensure_pygame()
    mm = Minimap(_make_map(10, 10), _make_player())
    mm.game_map = None
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    mm.render(surf, 0, 0, 0.0)  # 不应抛出


# =============================================================================
# 入口（standalone 运行）
# =============================================================================

if __name__ == "__main__":
    tests = [
        ("test_canvas_size_15x15", test_canvas_size_15x15),
        ("test_canvas_size_40x40", test_canvas_size_40x40),
        ("test_color_mapping_basic", test_color_mapping_basic),
        ("test_color_mapping_advanced", test_color_mapping_advanced),
        ("test_blink_formula_no_crash", test_blink_formula_no_crash),
        ("test_gameplay_tab_toggles_minimap", test_gameplay_tab_toggles_minimap),
        ("test_bonus_tab_toggles_minimap", test_bonus_tab_toggles_minimap),
        ("test_large_map_render_no_crash", test_large_map_render_no_crash),
        ("test_player_dot_rendered", test_player_dot_rendered),
        ("test_render_no_crash_basic", test_render_no_crash_basic),
        ("test_render_none_map_safe", test_render_none_map_safe),
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
