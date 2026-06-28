"""单元测试 — AudioManager

验证全局音频管理器的核心行为：单例模式、防重叠播放、音量钳制、BGM 切换、
停止清除、以及混音器不可用时的静默沙盒安全。

可以直接运行::
    python tests/test_audio_manager.py

或通过 pytest::
    python -m pytest tests/test_audio_manager.py -v
"""

import os
import sys

# 必须在 pygame 初始化前设置 dummy 视频驱动（Headless 模式）
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
except pygame.error:
    pass

from src.audio_manager import AudioManager


# =============================================================================
# 辅助
# =============================================================================

def setup():
    """重置单例状态，确保每个测试从干净状态开始。"""
    AudioManager._instance = None


def teardown():
    """测试结束后清理。"""
    AudioManager._instance = None
    try:
        if pygame.mixer.get_init() is not None:
            pygame.mixer.music.stop()
    except Exception:
        pass


# =============================================================================
# 测试用例
# =============================================================================

def test_singleton_returns_same_instance():
    """get_instance() 前后两次调用应返回同一个对象。"""
    a1 = AudioManager.get_instance()
    a2 = AudioManager.get_instance()
    assert a1 is a2, "单例模式违反：两次 get_instance() 返回了不同对象"
    print("[PASS] test_singleton_returns_same_instance")


def test_initial_state():
    """新创建实例的初始值应为：current_bgm=None, 音量=1.0。"""
    mgr = AudioManager.get_instance()
    assert mgr.current_bgm is None, f"expected None, got {mgr.current_bgm}"
    assert mgr.music_volume == 1.0, f"expected 1.0, got {mgr.music_volume}"
    assert mgr.sfx_volume == 1.0, f"expected 1.0, got {mgr.sfx_volume}"
    print("[PASS] test_initial_state")


def test_set_music_volume_clamps():
    """set_music_volume 应将值钳制在 [0.0, 1.0] 范围内。"""
    mgr = AudioManager.get_instance()
    mgr.set_music_volume(1.5)
    assert mgr.music_volume == 1.0, f"expected 1.0, got {mgr.music_volume}"
    mgr.set_music_volume(-0.5)
    assert mgr.music_volume == 0.0, f"expected 0.0, got {mgr.music_volume}"
    mgr.set_music_volume(0.5)
    assert mgr.music_volume == 0.5, f"expected 0.5, got {mgr.music_volume}"
    print("[PASS] test_set_music_volume_clamps")


def test_set_sfx_volume_clamps():
    """set_sfx_volume 应将值钳制在 [0.0, 1.0] 范围内。"""
    mgr = AudioManager.get_instance()
    mgr.set_sfx_volume(1.5)
    assert mgr.sfx_volume == 1.0, f"expected 1.0, got {mgr.sfx_volume}"
    mgr.set_sfx_volume(-0.5)
    assert mgr.sfx_volume == 0.0, f"expected 0.0, got {mgr.sfx_volume}"
    mgr.set_sfx_volume(0.3)
    assert mgr.sfx_volume == 0.3, f"expected 0.3, got {mgr.sfx_volume}"
    print("[PASS] test_set_sfx_volume_clamps")


def test_duplicate_prevention():
    """连续两次调用 play_bgm("x") 应被去重机制拦截，current_bgm 维持不变。

    使用 mock 模拟 pygame.mixer.music 的成功加载，避免因文件缺失导致
    current_bgm 被设为 None 从而绕过去重判定。
    """
    # Mock mixer.music 方法以确保 play_bgm "成功"
    _orig_load = pygame.mixer.music.load
    _orig_play = pygame.mixer.music.play
    _orig_set_vol = pygame.mixer.music.set_volume
    pygame.mixer.music.load = lambda f: None
    pygame.mixer.music.play = lambda loops=-1, fade_ms=0: None
    pygame.mixer.music.set_volume = lambda v: None

    try:
        mgr = AudioManager.get_instance()
        mgr.current_bgm = None

        # 第一次调用 — 应成功并记录 track_a
        mgr.play_bgm("track_a.ogg")
        first = mgr.current_bgm
        assert first == "track_a.ogg", f"第一次调用后期望 track_a.ogg，得到 {first}"

        # 第二次调用相同路径 — 应触发去重，current_bgm 不变
        mgr.play_bgm("track_a.ogg")
        assert mgr.current_bgm == first, (
            f"去重失败：第二次调用后 current_bgm 从 {first} 变为 {mgr.current_bgm}"
        )
    finally:
        pygame.mixer.music.load = _orig_load
        pygame.mixer.music.play = _orig_play
        pygame.mixer.music.set_volume = _orig_set_vol

    print("[PASS] test_duplicate_prevention")


def test_switching_changes_current_bgm():
    """依次调用 play_bgm 播放不同曲目时，current_bgm 应正确演进。

    使用 mock 模拟 pygame.mixer.music 的成功加载，避免因文件缺失导致
    每次调用都将 current_bgm 置为 None。
    """
    # Mock mixer.music 方法
    _orig_load = pygame.mixer.music.load
    _orig_play = pygame.mixer.music.play
    _orig_set_vol = pygame.mixer.music.set_volume
    pygame.mixer.music.load = lambda f: None
    pygame.mixer.music.play = lambda loops=-1, fade_ms=0: None
    pygame.mixer.music.set_volume = lambda v: None

    try:
        mgr = AudioManager.get_instance()
        mgr.current_bgm = None

        mgr.play_bgm("track_a.ogg")
        first = mgr.current_bgm
        assert first == "track_a.ogg", f"第一次调用后期望 track_a.ogg，得到 {first}"

        mgr.play_bgm("track_b.ogg")
        assert mgr.current_bgm != first, "切换失败：current_bgm 未发生变化"
        assert mgr.current_bgm == "track_b.ogg", (
            f"期望 track_b.ogg，得到 {mgr.current_bgm}"
        )
    finally:
        pygame.mixer.music.load = _orig_load
        pygame.mixer.music.play = _orig_play
        pygame.mixer.music.set_volume = _orig_set_vol

    print("[PASS] test_switching_changes_current_bgm")


def test_stop_bgm_clears_current():
    """stop_bgm() 应将 current_bgm 置为 None。"""
    mgr = AudioManager.get_instance()
    mgr.current_bgm = "some_track.ogg"
    mgr.stop_bgm()
    assert mgr.current_bgm is None, f"stop_bgm 后 expected None, got {mgr.current_bgm}"
    print("[PASS] test_stop_bgm_clears_current")


def test_safe_when_mixer_unavailable():
    """模拟混音器未初始化时，所有方法应安全无异常地降级为静默沙盒。"""
    setup()
    mgr = AudioManager.get_instance()

    # 记录当前混音器状态，临时退出
    was_init = pygame.mixer.get_init() is not None
    if was_init:
        pygame.mixer.quit()

    try:
        # 这些调用都不应抛出任何异常
        mgr.play_bgm("test_bgm.ogg")
        mgr.stop_bgm()
        mgr.pause_bgm()
        mgr.resume_bgm()
        mgr.play_sfx("test_sfx.wav")
        mgr.set_music_volume(0.5)
        mgr.set_sfx_volume(0.5)
    except Exception as e:
        assert False, f"混音器不可用时调用方法引发了异常: {e}"
    finally:
        if was_init:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)

    print("[PASS] test_safe_when_mixer_unavailable")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    setup()
    try:
        test_singleton_returns_same_instance()
        test_initial_state()
        test_set_music_volume_clamps()
        test_set_sfx_volume_clamps()
        test_duplicate_prevention()
        test_switching_changes_current_bgm()
        test_stop_bgm_clears_current()
        test_safe_when_mixer_unavailable()
        print("\n=== ALL TESTS PASSED ===")
    finally:
        teardown()
