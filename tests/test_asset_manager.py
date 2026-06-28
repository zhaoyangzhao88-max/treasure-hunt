"""AssetManager 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_asset_manager.py` 直接运行。
使用 SDL dummy 驱动避免弹出实体窗口。
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

from src.asset_manager import AssetManager, DummySound


def teardown():
    """清理 Pygame 和单例"""
    AssetManager._instance = None
    pygame.quit()


def test_image_returns_surface_on_missing():
    """缺失文件 → 返回占位 Surface，验证尺寸 48×48 与 magenta 色"""
    mgr = AssetManager.get_instance("assets/")

    surface = mgr.get_image("non_existent_hero.png")

    assert isinstance(surface, pygame.Surface), f"应返回 Surface，得到 {type(surface)}"
    assert surface.get_size() == (48, 48), f"占位图尺寸应为 (48, 48)，得到 {surface.get_size()}"

    # 检查中心像素颜色为品红 (255, 0, 255)
    pixel = surface.get_at((24, 24))
    assert pixel[:3] == (255, 0, 255), f"占位图中心应为品红，得到 {pixel[:3]}"

    print("[PASS] test_image_returns_surface_on_missing")


def test_font_fallback():
    """不存在的字体 → 返回 Font 实例（系统字体降级）"""
    mgr = AssetManager.get_instance("assets/")

    font = mgr.get_font("non_existent_font_xyz", 24)

    assert isinstance(font, pygame.font.Font), f"应返回 Font 实例，得到 {type(font)}"
    # 验证 Font 可正常使用
    rendered = font.render("Test", True, (255, 255, 255))
    assert isinstance(rendered, pygame.Surface)

    print("[PASS] test_font_fallback")


def test_sound_fallback():
    """缺失音频 → 返回 DummySound 实例，play() 无异常"""
    mgr = AssetManager.get_instance("assets/")

    sound = mgr.get_sound("non_existent_sfx.wav")

    assert isinstance(sound, DummySound), f"应返回 DummySound，得到 {type(sound)}"

    # 验证所有 DummySound 方法不抛异常
    sound.play()
    sound.stop()
    sound.set_volume(0.5)
    vol = sound.get_volume()
    assert vol == 0.0, f"DummySound.get_volume() 应返回 0.0，得到 {vol}"

    print("[PASS] test_sound_fallback")


def test_image_cache_identity():
    """连续两次 get_image（同一负路径）→ 返回同一 Surface 对象"""
    mgr = AssetManager.get_instance("assets/")

    s1 = mgr.get_image("another_missing_sprite.png")
    s2 = mgr.get_image("another_missing_sprite.png")

    assert s1 is s2, "两次同一 key 应返回同一 Surface 对象"

    print("[PASS] test_image_cache_identity")


def test_sound_cache_identity():
    """连续两次 get_sound（同一缺失路径）→ 返回同一 DummySound 对象"""
    mgr = AssetManager.get_instance("assets/")

    d1 = mgr.get_sound("missing_bgm.ogg")
    d2 = mgr.get_sound("missing_bgm.ogg")

    assert d1 is d2, "两次同一缺失音效应返回同一 DummySound 对象"

    print("[PASS] test_sound_cache_identity")


if __name__ == "__main__":
    try:
        test_image_returns_surface_on_missing()
        test_font_fallback()
        test_sound_fallback()
        test_image_cache_identity()
        test_sound_cache_identity()
        print("\n=== ALL TESTS PASSED ===")
    finally:
        teardown()
