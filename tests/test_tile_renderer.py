"""单元测试：Spritesheet 瓦片切割与 TileRenderer

验证 TileRenderer 在退化模式与正常切片模式下的正确性，
以及集成到 GameplayScreen 中的渲染兼容性。

测试模式（遵循项目既有规范）：
- SDL_VIDEODRIVER=dummy 实现无头渲染
- 使用 assert 断言，各测试函数独立
- 可直接运行 python tests/test_tile_renderer.py 或通过 pytest
"""

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

# 设置无头渲染模式（必须在 import pygame 之前）
_os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from src.config import TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT, BiomeType, BIOME_COLORS
from src.tile_renderer import TileRenderer, TILE_COORDS


def _init_pygame():
    """初始化 pygame（headless 模式）。"""
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass


# =============================================================================
# 测试 1：退化模式渲染所有瓦片类型
# =============================================================================

def test_fallback_render_all_tile_types():
    """验证退化模式下所有瓦片类型都能成功渲染而不抛异常。"""
    _init_pygame()

    renderer = TileRenderer(tile_size=48)
    assert renderer.use_fallback, "无实际 spritesheet 时应处于退化模式"

    surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
    tile_types = list(TILE_COORDS.keys())
    tile_types.append("NONE")  # 也测试未知类型

    for ttype in tile_types:
        try:
            extra = "3" if ttype == "UNCOVERED" else None
            renderer.draw_tile(surf, ttype, 0, 0, extra_info=extra)
        except Exception as e:
            assert False, f"draw_tile('{ttype}') 抛出异常: {e}"

    # 额外测试 extra_info 为各种数字的情况
    for num in ("1", "2", "3", "4", "5", "6", "7", "8", "0", "-1", "abc"):
        try:
            renderer.draw_tile(surf, "UNCOVERED", 0, 0, extra_info=num)
        except Exception as e:
            assert False, f"draw_tile UNCOVERED with '{num}' 抛出异常: {e}"

    print("[PASS] test_fallback_render_all_tile_types: 所有瓦片类型退化渲染成功")


# =============================================================================
# 测试 2：Spritesheet 切片正确性
# =============================================================================

def test_slicing_with_fake_spritesheet():
    """验证 TileRenderer 能正确切割伪 Spritesheet 并缓存切片。"""
    _init_pygame()

    # 构造一个 480x480 的伪图集（10 列 × 10 行 × 48px）
    grid_cols = 10
    grid_rows = 10
    fake_size = 48
    fake_sheet = pygame.Surface((grid_cols * fake_size, grid_rows * fake_size))

    # 为每个格子填充不同颜色用于验证
    for row in range(grid_rows):
        for col in range(grid_cols):
            color = ((col * 25) % 256, (row * 25) % 256, 128)
            rect = pygame.Rect(col * fake_size, row * fake_size,
                               fake_size, fake_size)
            pygame.draw.rect(fake_sheet, color, rect)

    # 创建 TileRenderer 并手动注入伪图集
    renderer = TileRenderer(tile_size=fake_size)
    renderer._slice_spritesheet(fake_sheet, fake_size)

    # 验证切片缓存
    assert (0, 0) in renderer.sliced_tiles, "缺少 (0,0) 切片"
    assert (1, 0) in renderer.sliced_tiles, "缺少 (1,0) 切片"
    assert (0, 1) in renderer.sliced_tiles, "缺少 (0,1) 切片"

    # 验证切片尺寸
    for coords, surf in renderer.sliced_tiles.items():
        assert surf.get_width() == fake_size, \
            f"切片 {coords} 宽度 {surf.get_width()} != {fake_size}"
        assert surf.get_height() == fake_size, \
            f"切片 {coords} 高度 {surf.get_height()} != {fake_size}"

    # 验证切片内容（与直接 subsurface 提取一致）
    test_coord = (2, 3)
    expected_surf = fake_sheet.subsurface(
        pygame.Rect(2 * fake_size, 3 * fake_size, fake_size, fake_size)
    ).copy()
    actual_surf = renderer.sliced_tiles[test_coord]
    expected_pixels = expected_surf.get_at((0, 0))
    actual_pixels = actual_surf.get_at((0, 0))
    assert expected_pixels == actual_pixels, \
        f"切片 {test_coord} 像素不匹配: {expected_pixels} vs {actual_pixels}"

    # 验证 get_sliced_tile 能正确映射
    dirt_surf = renderer.get_sliced_tile("DIRT")
    assert dirt_surf is not None, "get_sliced_tile('DIRT') 返回 None"
    assert dirt_surf.get_width() == fake_size

    # 验证 TILE_COORDS 中有映射的类型都能获取
    for ttype, coords in TILE_COORDS.items():
        tile = renderer.get_sliced_tile(ttype)
        assert tile is not None, f"get_sliced_tile('{ttype}') 不应为 None"

    print("[PASS] test_slicing_with_fake_spritesheet: 切片切割与缓存正确")


# =============================================================================
# 测试 3：集成到 GameplayScreen 的渲染兼容性
# =============================================================================

def test_gameplay_screen_render_compatibility():
    """验证 GameplayScreen 在集成 TileRenderer 后渲染不崩溃。"""
    _init_pygame()

    # 重置单例，确保 AssetManager 可用
    from src.asset_manager import AssetManager
    from src.player_state import PlayerState
    AssetManager._instance = None
    AssetManager.get_instance()  # 初始化 AssetManager

    # 使用项目既有模式：FakeGameManager + 直接 on_enter
    from src.screens.gameplay_screen import GameplayScreen

    screen = GameplayScreen()
    class FakeGameManager:
        def __init__(self):
            self.player_state = PlayerState()
            self.screen_manager = None
            self.asset_manager = None
            self.save_manager = None
    screen.game_manager = FakeGameManager()

    # 确保 GameManager 单例可用（避免 on_enter 覆盖后因 player_state=None 崩溃）
    from src.game_manager import GameManager
    gm = GameManager.get_instance()
    if gm.player_state is None:
        gm.player_state = PlayerState()

    screen.on_enter(data_payload=None)

    # 确保 TileRenderer 已实例化
    assert hasattr(screen, 'tile_renderer'), "GameplayScreen 缺少 tile_renderer 属性"
    assert screen.tile_renderer is not None, "tile_renderer 未初始化"
    assert screen.tile_renderer.use_fallback, "无 spritesheet 时应使用退化模式"

    # 渲染测试 Surface（不应抛异常）
    test_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    try:
        screen.render(test_surface)
    except Exception as e:
        assert False, f"GameplayScreen.render() 抛出异常: {e}"

    print("[PASS] test_gameplay_screen_render_compatibility: "
          "GameplayScreen + TileRenderer 集成渲染成功")


# =============================================================================
# 测试 4：关键瓦片退化渲染的颜色一致性
# =============================================================================

def test_fallback_color_consistency():
    """验证退化模式下关键瓦片的颜色值符合预期。"""
    _init_pygame()

    renderer = TileRenderer(tile_size=48)
    assert renderer.use_fallback

    ts = 48
    surf = pygame.Surface((ts * 4, ts))

    # 绘制 DIRT 瓦片
    renderer.draw_tile(surf, "DIRT", 0, 0)
    # 检查边框内 2px 处像素（边框 1px，内部应为填充色 (120, 80, 50)）
    dirt_pixel = surf.get_at((2, 2))
    assert dirt_pixel[:3] == (120, 80, 50), \
        f"DIRT 像素颜色异常: {dirt_pixel[:3]}"

    # 绘制 WALL 瓦片 — 验证至少存在 WALL 颜色像素（默认 GRASSLAND 地貌）
    wall_color = BIOME_COLORS[BiomeType.GRASSLAND]["WALL"]
    renderer.draw_tile(surf, "WALL", ts, 0)
    found_wall = False
    for py in range(ts):
        for px in range(ts, 2 * ts):
            if surf.get_at((px, py))[:3] == wall_color:
                found_wall = True
                break
        if found_wall:
            break
    assert found_wall, f"WALL 瓦片中未找到基色 {wall_color}"

    # 绘制 PLAYER（绿色圆形 + 白色边框 + 白色十字）— 验证至少存在绿色像素
    renderer.draw_tile(surf, "PLAYER", 2 * ts, 0)
    found_green = False
    for py in range(ts):
        for px in range(2 * ts, 3 * ts):
            if surf.get_at((px, py))[:3] == (0, 180, 0):
                found_green = True
                break
        if found_green:
            break
    assert found_green, "PLAYER 瓦片中未找到绿色像素"

    # 绘制 COIN（金色圆形）— 验证至少存在金色像素
    renderer.draw_tile(surf, "COIN", 3 * ts, 0)
    found_gold = False
    for py in range(ts):
        for px in range(3 * ts, 4 * ts):
            if surf.get_at((px, py))[:3] == (212, 175, 55):
                found_gold = True
                break
        if found_gold:
            break
    assert found_gold, "COIN 瓦片中未找到金色像素"

    print("[PASS] test_fallback_color_consistency: 关键瓦片颜色验证通过")


# =============================================================================
# 测试 5：奖励关渲染兼容性
# =============================================================================

def test_bonus_level_render_compatibility():
    """验证 BonusLevelScreen 集成 TileRenderer 后渲染不崩溃。"""
    _init_pygame()

    # 初始化 GameManager（headless 模式），确保 player_state 可用
    from src.game_manager import GameManager
    from src.asset_manager import AssetManager
    GameManager._instance = None
    AssetManager._instance = None

    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    from src.screens.bonus_level_screen import BonusLevelScreen

    screen = BonusLevelScreen()
    screen.on_enter(data_payload=None)

    # 确保 TileRenderer 已实例化
    assert hasattr(screen, 'tile_renderer'), "BonusLevelScreen 缺少 tile_renderer"
    assert screen.tile_renderer is not None
    assert screen.tile_renderer.use_fallback

    test_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    try:
        screen.render(test_surface)
    except Exception as e:
        assert False, f"BonusLevelScreen.render() 抛出异常: {e}"

    print("[PASS] test_bonus_level_render_compatibility: "
          "BonusLevelScreen + TileRenderer 集成渲染成功")


# =============================================================================
# 测试 6：draw_tile 忽略未知类型不抛异常
# =============================================================================

def test_unknown_tile_type():
    """验证传入未知瓦片类型时 draw_tile 不抛异常。"""
    _init_pygame()

    renderer = TileRenderer(tile_size=48)
    surf = pygame.Surface((TILE_SIZE, TILE_SIZE))

    try:
        renderer.draw_tile(surf, "NONEXISTENT_TYPE", 0, 0)
        renderer.draw_tile(surf, "", 0, 0)
        renderer.draw_tile(surf, "INVALID!@#", 0, 0)
    except Exception as e:
        assert False, f"未知瓦片类型抛出异常: {e}"

    print("[PASS] test_unknown_tile_type: 未知类型安全忽略")


# =============================================================================
# 测试 7：TileRenderer 支持不同 tile_size
# =============================================================================

def test_custom_tile_size():
    """验证 TileRenderer 支持自定义瓦片大小。"""
    _init_pygame()

    for custom_size in (32, 48, 64):
        renderer = TileRenderer(tile_size=custom_size)
        assert renderer.tile_size == custom_size
        assert renderer.use_fallback

        surf = pygame.Surface((custom_size, custom_size))
        try:
            renderer.draw_tile(surf, "DIRT", 0, 0)
            renderer.draw_tile(surf, "PLAYER", 0, 0)
            renderer.draw_tile(surf, "UNCOVERED", 0, 0, extra_info="5")
        except Exception as e:
            assert False, f"tile_size={custom_size} 时抛出异常: {e}"

    print("[PASS] test_custom_tile_size: 自定义瓦片大小支持正常")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TileRenderer 单元测试")
    print("=" * 60)

    test_fallback_render_all_tile_types()
    test_slicing_with_fake_spritesheet()
    test_gameplay_screen_render_compatibility()
    test_fallback_color_consistency()
    test_bonus_level_render_compatibility()
    test_unknown_tile_type()
    test_custom_tile_size()

    print("=" * 60)
    print("=== ALL TileRenderer TESTS PASSED ===")
    print("=" * 60)
