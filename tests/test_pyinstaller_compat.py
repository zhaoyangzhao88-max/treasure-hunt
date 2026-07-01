"""PyInstaller 兼容性验证 — Microsoft Treasure Hunt

验证自愈路径解析器 `get_resource_path()` 在开发态与打包态下的正确性，
以及 AssetManager 在路径重构后缓存一致性依然 100% 绿旗通过。

使用 SDL dummy 驱动避免弹出实体窗口（Headless 模式）。
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

# 尝试初始化 mixer（某些环境可能无音频设备，但不影响测试）
try:
    pygame.mixer.init()
except pygame.error:
    pass

from src.asset_manager import AssetManager, DummySound, get_resource_path


# =============================================================================
# 路径解析器测试
# =============================================================================

def test_get_resource_path_dev_mode():
    """开发态（sys.frozen 缺失）→ 返回当前工作目录拼接的绝对路径。"""
    # 确保处于开发态：移除可能存在的 frozen / _MEIPASS 属性
    saved_frozen = getattr(sys, 'frozen', None)
    saved_meipass = getattr(sys, '_MEIPASS', None)
    try:
        if hasattr(sys, 'frozen'):
            del sys.frozen
        if hasattr(sys, '_MEIPASS'):
            del sys._MEIPASS

        result = get_resource_path("assets/images/spritesheet.png")
        expected_base = os.path.abspath(".")
        expected = os.path.join(expected_base, "assets", "images", "spritesheet.png")

        # 使用 os.path.normcase 统一路径分隔符后比较（Windows 下 / 与 \ 等价）
        assert os.path.normcase(result) == os.path.normcase(expected), (
            f"开发态路径应为 '{expected}'，得到 '{result}'"
        )
        # 验证路径结构包含 assets/images/spritesheet.png
        assert "assets" in result and "images" in result and "spritesheet.png" in result, (
            f"路径结构不正确: {result}"
        )
        print("[PASS] test_get_resource_path_dev_mode")
    finally:
        # 恢复原状
        if saved_frozen is not None:
            sys.frozen = saved_frozen
        if saved_meipass is not None:
            sys._MEIPASS = saved_meipass


def test_get_resource_path_frozen_mode():
    """打包态（sys.frozen == True + sys._MEIPASS）→ 重定向到临时解压目录。"""
    saved_frozen = getattr(sys, 'frozen', None)
    saved_meipass = getattr(sys, '_MEIPASS', None)
    try:
        sys.frozen = True
        sys._MEIPASS = "C:\\Temp\\_MEI12345"

        result = get_resource_path("assets/images/spritesheet.png")
        expected = "C:\\Temp\\_MEI12345\\assets/images/spritesheet.png"

        assert result == expected, (
            f"打包态路径应为 '{expected}'，得到 '{result}'"
        )
        print("[PASS] test_get_resource_path_frozen_mode")
    finally:
        # 恢复原状，防止污染其他测试
        if saved_frozen is not None:
            sys.frozen = saved_frozen
        elif hasattr(sys, 'frozen'):
            del sys.frozen
        if saved_meipass is not None:
            sys._MEIPASS = saved_meipass
        elif hasattr(sys, '_MEIPASS'):
            del sys._MEIPASS


def test_get_resource_path_frozen_without_meipass():
    """sys.frozen == True 但无 _MEIPASS → 退化回开发态行为（防御性）。"""
    saved_frozen = getattr(sys, 'frozen', None)
    saved_meipass = getattr(sys, '_MEIPASS', None)
    try:
        sys.frozen = True
        # 显式移除 _MEIPASS，模拟异常状态
        if hasattr(sys, '_MEIPASS'):
            del sys._MEIPASS

        result = get_resource_path("assets/images/test.png")
        expected_base = os.path.abspath(".")
        expected = os.path.join(expected_base, "assets", "images", "test.png")

        # 使用 os.path.normcase 统一路径分隔符后比较（Windows 下 / 与 \ 等价）
        assert os.path.normcase(result) == os.path.normcase(expected), (
            f"无 _MEIPASS 时应退化到开发态路径 '{expected}'，得到 '{result}'"
        )
        print("[PASS] test_get_resource_path_frozen_without_meipass")
    finally:
        if saved_frozen is not None:
            sys.frozen = saved_frozen
        elif hasattr(sys, 'frozen'):
            del sys.frozen
        if saved_meipass is not None:
            sys._MEIPASS = saved_meipass


# =============================================================================
# AssetManager 缓存一致性测试（验证路径重构后向后兼容）
# =============================================================================

def test_asset_manager_image_cache_consistency():
    """路径重构后，get_image 缓存行为依然正确（同一 key 返回同一 Surface）。"""
    AssetManager._instance = None
    mgr = AssetManager.get_instance("assets/")

    s1 = mgr.get_image("non_existent_hero.png")
    s2 = mgr.get_image("non_existent_hero.png")

    assert s1 is s2, "两次同一 key 应返回同一 Surface 对象"
    assert isinstance(s1, pygame.Surface)
    print("[PASS] test_asset_manager_image_cache_consistency")


def test_asset_manager_sound_cache_consistency():
    """路径重构后，get_sound 缓存行为依然正确（同一缺失路径返回同一 DummySound）。"""
    AssetManager._instance = None
    mgr = AssetManager.get_instance("assets/")

    d1 = mgr.get_sound("non_existent_sfx.wav")
    d2 = mgr.get_sound("non_existent_sfx.wav")

    assert d1 is d2, "两次同一缺失音效应返回同一 DummySound 对象"
    assert isinstance(d1, DummySound)
    print("[PASS] test_asset_manager_sound_cache_consistency")


def test_asset_manager_font_fallback():
    """路径重构后，get_font 在字体缺失时依然正确降级为内置字体。"""
    AssetManager._instance = None
    mgr = AssetManager.get_instance("assets/")

    font = mgr.get_font("non_existent_font_xyz", 24)
    assert isinstance(font, pygame.font.Font), (
        f"应返回 Font 实例，得到 {type(font)}"
    )
    # 验证 Font 可正常使用
    rendered = font.render("Test", True, (255, 255, 255))
    assert isinstance(rendered, pygame.Surface)
    print("[PASS] test_asset_manager_font_fallback")


def test_asset_manager_image_placeholder():
    """路径重构后，get_image 在图片缺失时返回品红占位 Surface。"""
    AssetManager._instance = None
    mgr = AssetManager.get_instance("assets/")

    surface = mgr.get_image("missing_sprite.png")
    assert isinstance(surface, pygame.Surface)
    assert surface.get_size() == (48, 48), (
        f"占位图尺寸应为 (48, 48)，得到 {surface.get_size()}"
    )
    pixel = surface.get_at((24, 24))
    assert pixel[:3] == (255, 0, 255), (
        f"占位图中心应为品红，得到 {pixel[:3]}"
    )
    print("[PASS] test_asset_manager_image_placeholder")


# =============================================================================
# 入口
# =============================================================================

def teardown():
    """清理 Pygame 和单例"""
    AssetManager._instance = None
    pygame.quit()


if __name__ == "__main__":
    try:
        test_get_resource_path_dev_mode()
        test_get_resource_path_frozen_mode()
        test_get_resource_path_frozen_without_meipass()
        test_asset_manager_image_cache_consistency()
        test_asset_manager_sound_cache_consistency()
        test_asset_manager_font_fallback()
        test_asset_manager_image_placeholder()
        print("\n=== ALL TESTS PASSED ===")
    finally:
        teardown()
