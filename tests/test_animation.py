"""单元测试：帧动画系统（Animation / Animator）与数学弹性兜底渲染

验证内容：
- Animation：帧率步进、非循环终止、图集切片
- Animator：多状态切换、计时重置、非循环自动 IDLE 回退
- TileRenderer：退化模式下各动画状态的数学动效无异常
- 向后兼容性：字符串 extra_info 仍能正常渲染 UNCOVERED

测试模式（遵循项目既有规范）：
- SDL_VIDEODRIVER=dummy 实现无头渲染
- 使用 assert 断言，各测试函数独立
- 可直接运行 python tests/test_animation.py 或通过 pytest
"""

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

# 设置无头渲染模式（必须在 import pygame 之前）
_os.environ["SDL_VIDEODRIVER"] = "dummy"

import math
import random
import pygame

from src.config import TILE_SIZE
from src.animation import Animation, Animator


def _init_pygame():
    """初始化 pygame（headless 模式）。"""
    if not pygame.get_init():
        pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass


# =============================================================================
# 测试 1：帧率步进与循环
# =============================================================================

def test_frame_advance():
    """3 帧动画：update(0.1) 应从帧 0 → 1 → 2 → 0（循环）。"""
    _init_pygame()
    frames = [pygame.Surface((10, 10)) for _ in range(3)]
    anim = Animation(frames, frame_duration=0.1, loop=True)

    assert anim.current_frame_idx == 0, "初始应在帧 0"
    anim.update(0.1)
    assert anim.current_frame_idx == 1, f"第 1 次更新应到帧 1，当前帧 {anim.current_frame_idx}"
    anim.update(0.1)
    assert anim.current_frame_idx == 2, f"第 2 次更新应到帧 2，当前帧 {anim.current_frame_idx}"
    anim.update(0.1)
    assert anim.current_frame_idx == 0, f"循环后应回帧 0，当前帧 {anim.current_frame_idx}"
    assert not anim.finished, "循环动画不应 finished"
    print("[PASS] test_frame_advance")


# =============================================================================
# 测试 2：非循环动画终止
# =============================================================================

def test_non_loop_termination():
    """非循环动画在播放完后设置 finished=True 并钳制在最后一帧。"""
    _init_pygame()
    frames = [pygame.Surface((10, 10)) for _ in range(3)]
    anim = Animation(frames, frame_duration=0.1, loop=False)

    assert not anim.finished
    # 推进 0.4s（3 帧 × 0.1 = 0.3s 应播完）
    anim.update(0.4)
    assert anim.finished, "非循环动画播完后应 finished=True"
    assert anim.current_frame_idx == 2, "应钳制在最后一帧（索引 2）"

    # 再推进应不影响状态
    anim.update(0.5)
    assert anim.finished, "finished 应保持 True"
    assert anim.current_frame_idx == 2, "帧索引应保持最后一帧"
    print("[PASS] test_non_loop_termination")


# =============================================================================
# 测试 3：多状态自动切换（DIG 播完自动回 IDLE）
# =============================================================================

def test_multi_state_auto_switch():
    """Animator 中非循环 DIG 播完后应自动切回 IDLE。"""
    _init_pygame()
    animator = Animator()
    placeholder = pygame.Surface((10, 10))

    idle_anim = Animation([placeholder, placeholder], 0.2, loop=True)
    dig_anim = Animation([placeholder, placeholder, placeholder], 0.1, loop=False)

    animator.add_animation("IDLE", idle_anim)
    animator.add_animation("DIG", dig_anim)
    animator.play("IDLE")

    assert animator.current_state == "IDLE"

    animator.play("DIG")
    assert animator.current_state == "DIG"
    assert animator.state_time == 0.0

    # 更新 0.5s（远超过 DIG 的 3×0.1=0.3s）
    for _ in range(10):
        animator.update(0.05)

    assert animator.current_state == "IDLE", (
        f"DIG 播完应自动切回 IDLE，当前状态 {animator.current_state}"
    )
    print("[PASS] test_multi_state_auto_switch")


# =============================================================================
# 测试 4：状态切换时计时器与帧索引重置
# =============================================================================

def test_state_reset_on_play():
    """切换新状态应重置 state_time 和目标动画的帧索引。"""
    _init_pygame()
    animator = Animator()
    placeholder = pygame.Surface((10, 10))

    walk = Animation([placeholder, placeholder, placeholder], 0.1, loop=False)
    dig = Animation([placeholder, placeholder], 0.2, loop=False)
    idle = Animation([placeholder], 0.5, loop=True)

    animator.add_animation("IDLE", idle)
    animator.add_animation("WALK", walk)
    animator.add_animation("DIG", dig)

    # 推进 WALK 部分
    animator.play("WALK")
    animator.update(0.15)  # 应到帧 1
    assert animator.current_state == "WALK"
    assert animator.state_time > 0
    walk_frame_before = animator.animations["WALK"].current_frame_idx
    assert walk_frame_before >= 1, f"WALK 应已推进到帧 {walk_frame_before}"

    # 切换到 DIG → 应全部重置
    animator.play("DIG")
    assert animator.state_time == 0.0, f"state_time 应重置为 0，当前 {animator.state_time}"
    assert animator.animations["DIG"].current_frame_idx == 0, "DIG 帧索引应重置为 0"
    assert animator.animations["DIG"].timer == 0.0, "DIG timer 应重置为 0"
    print("[PASS] test_state_reset_on_play")


# =============================================================================
# 测试 5：数学弹性降级安全性
# =============================================================================

def test_math_fallback_safety():
    """所有动画状态在退化模式下渲染应无异常（无除零/NaN/崩溃）。"""
    _init_pygame()

    from src.tile_renderer import TileRenderer

    renderer = TileRenderer()
    assert renderer.use_fallback, "无 spritesheet 时应使用退化模式"

    surf = pygame.Surface((TILE_SIZE, TILE_SIZE))

    # 创建完整 Animator
    animator = Animator()
    placeholder = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    specs = [
        ("IDLE", 1, 0.2, True),
        ("WALK_DOWN", 2, 0.1, False),
        ("WALK_UP", 2, 0.1, False),
        ("WALK_LEFT", 2, 0.1, False),
        ("WALK_RIGHT", 2, 0.1, False),
        ("DIG", 3, 0.1, False),
        ("HURT", 4, 0.1, False),
    ]
    for name, count, dur, loop in specs:
        frames = [placeholder.copy() for _ in range(count)]
        animator.add_animation(name, Animation(frames, dur, loop))
    animator.play("IDLE")

    # 对每种状态在多时间点渲染
    for name, _, _, _ in specs:
        animator.play(name)
        for _ in range(10):
            animator.update(0.05)
            try:
                renderer._draw_player_fallback(surf, 0, 0, animator)
                renderer._draw_monster_fallback(surf, 0, 0, animator)
            except Exception as e:
                assert False, (
                    f"状态 '{name}', time {animator.state_time:.2f}: {e}"
                )

    # 测试 None animator（向后兼容）
    try:
        renderer._draw_player_fallback(surf, 0, 0, None)
        renderer._draw_monster_fallback(surf, 0, 0, None)
    except Exception as e:
        assert False, f"None animator 渲染抛出异常: {e}"

    print("[PASS] test_math_fallback_safety")


# =============================================================================
# 测试 6：图集切片正确性
# =============================================================================

def test_from_sheet_slicing():
    """Animation.from_sheet 应正确切割指定区域并保持像素内容。"""
    _init_pygame()

    # 构造 4 列 × 1 行的测试图集（192×48）
    sheet = pygame.Surface((192, 48))
    for col in range(4):
        color = (col * 60, 0, 0)
        rect = pygame.Rect(col * 48, 0, 48, 48)
        pygame.draw.rect(sheet, color, rect)

    # 从列 1 开始切 2 帧
    anim = Animation.from_sheet(sheet, row=0, start_col=1,
                                 frame_count=2, size=48,
                                 duration=0.1, loop=False)

    assert len(anim.frames) == 2, f"应有 2 帧，实际 {len(anim.frames)}"
    assert anim.frames[0].get_width() == 48
    assert anim.frames[0].get_height() == 48

    # 帧 0 应为列 1 = (60, 0, 0)
    pixel0 = anim.frames[0].get_at((0, 0))
    assert pixel0[:3] == (60, 0, 0), f"帧 0 像素 {pixel0[:3]}"

    # 帧 1 应为列 2 = (120, 0, 0)
    pixel1 = anim.frames[1].get_at((0, 0))
    assert pixel1[:3] == (120, 0, 0), f"帧 1 像素 {pixel1[:3]}"

    # 验证 duration 和 loop 参数
    loop_anim = Animation.from_sheet(sheet, 0, 0, 1, 48, 0.2, loop=True)
    assert loop_anim.loop is True
    assert loop_anim.frame_duration == 0.2
    print("[PASS] test_from_sheet_slicing")


# =============================================================================
# 测试 7：向后兼容 — 字符串 extra_info
# =============================================================================

def test_extra_info_string_backward_compat():
    """draw_tile 对 UNCOVERED 传入字符串数字仍能正确渲染。"""
    _init_pygame()

    from src.tile_renderer import TileRenderer

    renderer = TileRenderer()
    surf = pygame.Surface((TILE_SIZE, TILE_SIZE))

    for val in ("3", "8", "0", "-1", "abc", None):
        try:
            renderer.draw_tile(surf, "UNCOVERED", 0, 0, extra_info=val)
        except Exception as e:
            assert False, f"UNCOVERED extra_info={val!r} 抛出异常: {e}"

    print("[PASS] test_extra_info_string_backward_compat")


# =============================================================================
# 测试 8：空帧列表无崩溃
# =============================================================================

def test_animator_no_crash_empty_frames():
    """空帧列表的 Animation/Animator 不应崩溃。"""
    _init_pygame()
    animator = Animator()

    empty = Animation([], 0.1, loop=True)
    animator.add_animation("IDLE", empty)
    animator.play("IDLE")

    try:
        animator.update(0.1)
        frame = animator.get_current_frame()
    except Exception as e:
        assert False, f"空帧列表导致崩溃: {e}"

    assert frame is None, "空帧列表应返回 None"

    # 切换到未注册状态应忽略
    animator.play("NONEXISTENT")
    assert animator.current_state == "IDLE", "未注册状态不应改变当前状态"
    print("[PASS] test_animator_no_crash_empty_frames")


# =============================================================================
# 主入口
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Animation System Unit Tests")
    print("=" * 60)

    test_frame_advance()
    test_non_loop_termination()
    test_multi_state_auto_switch()
    test_state_reset_on_play()
    test_math_fallback_safety()
    test_from_sheet_slicing()
    test_extra_info_string_backward_compat()
    test_animator_no_crash_empty_frames()

    print("=" * 60)
    print("=== ALL 8 ANIMATION TESTS PASSED ===")
    print("=" * 60)
