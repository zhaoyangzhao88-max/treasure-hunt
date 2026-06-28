"""单元测试：多环境地貌（Biomes）色彩与主题自适应渲染引擎

验证 Biome 枚举、关卡-地貌映射、退化模式主题色切换以及地貌 BGM 自动调度。

测试模式（遵循项目既有规范）：
- SDL_VIDEODRIVER=dummy 实现无头渲染
- 使用 assert 断言，各测试函数独立
- 可直接运行 python tests/test_biomes_and_themes.py 或通过 pytest
"""

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

# 设置无头渲染模式（必须在 import pygame 之前）
_os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from src.config import (
    BiomeType,
    get_biome_for_level,
    BIOME_COLORS,
    BIOME_BGM,
    TILE_SIZE,
)


def _init_pygame():
    """初始化 pygame（headless 模式）。"""
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass


# =============================================================================
# 测试 1：关卡-地貌映射确定性
# =============================================================================

def test_biome_level_mapping():
    """验证 get_biome_for_level 在不同关卡区间的映射正确性。"""
    # GRASSLAND: 关卡 1~5
    assert get_biome_for_level(1) == BiomeType.GRASSLAND
    assert get_biome_for_level(4) == BiomeType.GRASSLAND
    assert get_biome_for_level(5) == BiomeType.GRASSLAND

    # DESERT: 关卡 6~10
    assert get_biome_for_level(6) == BiomeType.DESERT
    assert get_biome_for_level(7) == BiomeType.DESERT
    assert get_biome_for_level(10) == BiomeType.DESERT

    # ICE_CAVE: 关卡 11~15
    assert get_biome_for_level(11) == BiomeType.ICE_CAVE
    assert get_biome_for_level(12) == BiomeType.ICE_CAVE
    assert get_biome_for_level(15) == BiomeType.ICE_CAVE

    # VOLCANO: 关卡 16+
    assert get_biome_for_level(16) == BiomeType.VOLCANO
    assert get_biome_for_level(18) == BiomeType.VOLCANO
    assert get_biome_for_level(99) == BiomeType.VOLCANO

    print("[PASS] test_biome_level_mapping: 关卡-地貌映射全部正确")


# =============================================================================
# 测试 2：Biome 色板一致性
# =============================================================================

def test_biome_color_consistency():
    """验证设置不同地貌后，退化渲染的 DIRT / UNCOVERED / WALL
    瓦片颜色与 BIOME_COLORS 定义 100% 对齐。"""
    _init_pygame()

    from src.tile_renderer import TileRenderer

    renderer = TileRenderer(tile_size=48)
    assert renderer.use_fallback

    ts = TILE_SIZE

    for biome in BiomeType:
        renderer.set_biome(biome)
        pal = BIOME_COLORS[biome]

        # -- 测试 DIRT 基色 --
        surf = pygame.Surface((ts, ts))
        renderer.draw_tile(surf, "DIRT", 0, 0)
        # 内部像素（2px 偏移避开 1px 边框）
        dirt_pixel = surf.get_at((2, 2))
        assert dirt_pixel[:3] == pal["DIRT"], (
            f"{biome} DIRT 颜色不匹配: expected {pal['DIRT']}, got {dirt_pixel[:3]}"
        )

        # -- 测试 UNCOVERED 基色 --
        surf = pygame.Surface((ts, ts))
        renderer.draw_tile(surf, "UNCOVERED", 0, 0)
        uncovered_pixel = surf.get_at((2, 2))
        assert uncovered_pixel[:3] == pal["UNCOVERED"], (
            f"{biome} UNCOVERED 颜色不匹配: expected {pal['UNCOVERED']}, "
            f"got {uncovered_pixel[:3]}"
        )

        # -- 测试 WALL 基色（扫描查找，因为 WALL 有交叉线覆盖） --
        surf = pygame.Surface((ts, ts))
        renderer.draw_tile(surf, "WALL", 0, 0)
        found = False
        for py in range(ts):
            for px in range(ts):
                if surf.get_at((px, py))[:3] == pal["WALL"]:
                    found = True
                    break
            if found:
                break
        assert found, (
            f"{biome} WALL 瓦片中未找到基色 {pal['WALL']}"
        )

    print("[PASS] test_biome_color_consistency: 全部 4 大地貌色板一致性验证通过")


# =============================================================================
# 测试 3：地貌 BGM 自动调度
# =============================================================================

def test_biome_bgm_auto_switch():
    """验证进入不同关卡时 AudioManager 自动切换对应地貌 BGM，
    且防重叠机制正常运作。"""
    _init_pygame()

    from src.audio_manager import AudioManager

    # 重置单例
    AudioManager._instance = None

    # Mock pygame.mixer.music 方法（避免实际文件 I/O）
    _orig_load = pygame.mixer.music.load
    _orig_play = pygame.mixer.music.play
    _orig_set_vol = pygame.mixer.music.set_volume
    pygame.mixer.music.load = lambda f: None
    pygame.mixer.music.play = lambda loops=-1, fade_ms=0: None
    pygame.mixer.music.set_volume = lambda v: None

    try:
        mgr = AudioManager.get_instance()
        mgr.current_bgm = None

        # ---- 模拟进入关卡 2 (GRASSLAND) ----
        biome = get_biome_for_level(2)
        assert biome == BiomeType.GRASSLAND, "关卡 2 应为 GRASSLAND"
        mgr.play_bgm(BIOME_BGM[biome])
        assert mgr.current_bgm == "grassland_bgm.ogg", (
            f"GRASSLAND BGM 不匹配: expected 'grassland_bgm.ogg', "
            f"got {mgr.current_bgm}"
        )

        # ---- 模拟进入关卡 8 (DESERT) ----
        biome = get_biome_for_level(8)
        assert biome == BiomeType.DESERT, "关卡 8 应为 DESERT"
        mgr.play_bgm(BIOME_BGM[biome])
        assert mgr.current_bgm == "desert_bgm.ogg", (
            f"DESERT BGM 不匹配: expected 'desert_bgm.ogg', "
            f"got {mgr.current_bgm}"
        )

        # ---- 验证防重叠（重复设置同一 BGM 不应改变 current_bgm） ----
        mgr.play_bgm("desert_bgm.ogg")
        assert mgr.current_bgm == "desert_bgm.ogg", "防重叠机制失效"

        # ---- 模拟进入关卡 13 (ICE_CAVE) ----
        biome = get_biome_for_level(13)
        assert biome == BiomeType.ICE_CAVE, "关卡 13 应为 ICE_CAVE"
        mgr.play_bgm(BIOME_BGM[biome])
        assert mgr.current_bgm == "ice_cave_bgm.ogg", (
            f"ICE_CAVE BGM 不匹配: expected 'ice_cave_bgm.ogg', "
            f"got {mgr.current_bgm}"
        )

        # ---- 模拟进入关卡 20 (VOLCANO) ----
        biome = get_biome_for_level(20)
        assert biome == BiomeType.VOLCANO, "关卡 20 应为 VOLCANO"
        mgr.play_bgm(BIOME_BGM[biome])
        assert mgr.current_bgm == "volcano_bgm.ogg", (
            f"VOLCANO BGM 不匹配: expected 'volcano_bgm.ogg', "
            f"got {mgr.current_bgm}"
        )

    finally:
        # 还原 Mock
        pygame.mixer.music.load = _orig_load
        pygame.mixer.music.play = _orig_play
        pygame.mixer.music.set_volume = _orig_set_vol
        AudioManager._instance = None

    print("[PASS] test_biome_bgm_auto_switch: 地貌 BGM 自动切换与防重叠验证通过")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Biomes and Themes 单元测试")
    print("=" * 60)

    test_biome_level_mapping()
    test_biome_color_consistency()
    test_biome_bgm_auto_switch()

    print("=" * 60)
    print("=== ALL BIOMES AND THEMES TESTS PASSED ===")
    print("=" * 60)
