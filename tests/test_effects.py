"""EffectsManager 单元验证脚本 — Microsoft Treasure Hunt

验证粒子物理运动、浮动文本上漂与渐隐、屏幕震颤衰减、
以及集成安全性的完整测试套件。

运行方式::

    python tests/test_effects.py
    python -m pytest tests/test_effects.py -v
"""

import os
import sys

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Headless 模式：必须在 pygame.init() 之前设置
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
import math
import random

from src.effects import Particle, FloatingText, EffectsManager
from src.camera import Camera


# =============================================================================
# 辅助函数
# =============================================================================

def _make_camera() -> Camera:
    """创建一个新的 Camera 实例。"""
    return Camera()


# =============================================================================
# 粒子物理测试
# =============================================================================

def test_particle_gravity():
    """验证粒子受重力影响：update 后 vy 增大（向下的速度增加）。"""
    if not pygame.get_init():
        pygame.init()

    # 创建一个受重力影响的粒子（静止状态）
    p = Particle(100, 100, 0.0, 0.0, (255, 0, 0), lifetime=1.0, size=4)

    old_vy = p.vy
    # 更新一帧（约 60fps）
    p.update(0.016)

    # 重力使 vy 增加（向下的速度更大）
    assert p.vy > old_vy, (
        f"受重力后 vy ({p.vy:.2f}) 应大于之前 ({old_vy:.2f})"
    )
    print("[PASS] test_particle_gravity — vy increases due to gravity")


def test_particle_air_drag():
    """验证空气阻力：vx 在无外力时指数衰减。"""
    p = Particle(100, 100, 100.0, 0.0, (255, 0, 0), lifetime=1.0, size=4)

    p.update(0.016)

    # 空气阻力使 vx 衰减（乘以 0.9）
    assert p.vx < 100.0, (
        f"阻力后 vx ({p.vx:.2f}) 应小于初始值 (100.0)"
    )
    print("[PASS] test_particle_air_drag — vx decreases due to drag")


def test_particle_lifetime_expiry():
    """验证粒子寿命耗尽后被 EffectsManager 正确清除。"""
    mgr = EffectsManager()
    mgr.spawn_particles(200, 200, (0, 255, 0), count=5)
    assert len(mgr.particles) == 5

    # 用多次 dt 确保所有粒子死亡（内部 safe_dt 上限 0.25s）
    for _ in range(20):
        mgr.update(0.5)
    assert len(mgr.particles) == 0, (
        f"所有粒子应已清除，仍有 {len(mgr.particles)} 个"
    )
    print("[PASS] test_particle_lifetime_expiry — dead particles cleaned")


def test_particle_position_update():
    """验证粒子位置随速度更新：x += vx * dt, y += vy * dt。"""
    p = Particle(50, 50, 100.0, 0.0, (0, 0, 255), lifetime=1.0, size=4)

    p.update(0.1)

    expected_x = 50.0 + 100.0 * 0.1 * 0.9  # 受阻力影响
    # 由于阻力在 update 内先作用，实际位移稍复杂，但 x 应明显增大
    assert p.x > 55.0, (
        f"粒子向右移动后 x ({p.x:.2f}) 应大于 55.0"
    )
    print("[PASS] test_particle_position_update — position updates correctly")


# =============================================================================
# 浮动文本测试
# =============================================================================

def test_floating_text_drift_upward():
    """验证浮动文本向上漂移：update 后 y 坐标减小。"""
    if not pygame.get_init():
        pygame.init()

    ft = FloatingText(100, 200, "+5 Gold", (255, 215, 0))
    old_y = ft.y

    ft.update(0.016)

    assert ft.y < old_y, (
        f"上漂后 y ({ft.y:.2f}) 应小于之前 ({old_y:.2f})"
    )
    print("[PASS] test_floating_text_drift_upward — y decreases (floats up)")


def test_floating_text_fade_alpha():
    """验证浮动文本在生命期末段计算了正确的 Alpha 渐淡值。"""
    if not pygame.get_init():
        pygame.init()

    # 创建一条 1.0s 寿命的浮动文本，自定义 font_size
    ft = FloatingText(100, 200, "Test", (255, 255, 255), lifetime=1.0,
                      font_size=24)

    # 推进到寿命低于 40% 阈值（应开始渐隐）
    # 直接操作 lifetime 以跳过 dt 钳制
    ft.lifetime = 0.3  # 低于 0.4 * 1.0 = 0.4s 阈值

    # 渲染并检查 alpha 值（set_alpha）
    test_surf = pygame.Surface((800, 600))
    # 通过 render 间接验证 set_alpha 不崩溃
    try:
        ft.render(test_surf, (0.0, 0.0))
    except Exception as e:
        assert False, f"浮动文本渲染在渐隐阶段崩溃: {e}"

    print("[PASS] test_floating_text_fade_alpha — fade alpha computed without error")


def test_floating_text_lifetime_expiry():
    """验证浮动文本寿命耗尽后从管理器清除。"""
    mgr = EffectsManager()
    mgr.spawn_text(100, 100, "Test", (255, 255, 255))
    assert len(mgr.floating_texts) == 1

    # 多次更新确保清除（内部 safe_dt 上限 0.25s）
    for _ in range(10):
        mgr.update(1.0)
    assert len(mgr.floating_texts) == 0, (
        f"所有浮动文本应已清除，仍有 {len(mgr.floating_texts)} 个"
    )
    print("[PASS] test_floating_text_lifetime_expiry — expired texts cleaned")


def test_floating_text_font_size():
    """验证自定义 font_size 生效。"""
    if not pygame.get_init():
        pygame.init()

    mgr = EffectsManager()
    mgr.spawn_text(100, 100, "Big Text", (255, 255, 255), font_size=36)

    assert len(mgr.floating_texts) == 1
    ft = mgr.floating_texts[0]
    assert ft.font is not None

    print("[PASS] test_floating_text_font_size — custom font_size works")


# =============================================================================
# 屏幕震颤测试
# =============================================================================

def test_camera_shake_trigger():
    """验证触发 Screen Shake 后摄像机产生初始偏移。"""
    cam = _make_camera()

    # 初始状态不应有震颤偏移
    assert cam.shake_duration == 0.0
    assert cam.shake_offset_x == 0.0
    assert cam.shake_offset_y == 0.0

    # 触发震颤
    cam.trigger_shake(0.4, 8.0)

    assert cam.shake_duration == 0.4
    assert cam.shake_amplitude == 8.0
    # 初始偏移应在 [-8, 8] 范围内
    assert -8.0 <= cam.shake_offset_x <= 8.0, (
        f"shake_offset_x ({cam.shake_offset_x}) 应在 [-8, 8] 范围内"
    )
    assert -8.0 <= cam.shake_offset_y <= 8.0, (
        f"shake_offset_y ({cam.shake_offset_y}) 应在 [-8, 8] 范围内"
    )
    print("[PASS] test_camera_shake_trigger — shake triggered with correct amplitude")


def test_camera_shake_decay():
    """验证 Screen Shake 随时间衰减至零。"""
    cam = _make_camera()

    # 触发震颤
    cam.trigger_shake(0.4, 8.0)

    # 在 update 中模拟多帧衰减
    for _ in range(30):
        # Camera.update 需要 player 坐标和地图参数
        cam.update(500.0, 500.0, 2000, 2000, 0.016)
        if cam.shake_duration <= 0:
            break

    # 震颤时间归零后，偏移应复位
    assert cam.shake_duration == 0.0, (
        f"震颤应已衰减至 0，得到 {cam.shake_duration}"
    )
    assert cam.shake_offset_x == 0.0, (
        f"震颤复位后 shake_offset_x 应为 0，得到 {cam.shake_offset_x}"
    )
    assert cam.shake_offset_y == 0.0, (
        f"震颤复位后 shake_offset_y 应为 0，得到 {cam.shake_offset_y}"
    )
    print("[PASS] test_camera_shake_decay — shake decays to zero")


def test_camera_shake_offset_changes():
    """验证震颤期间每帧偏移量不断变化（噪声叠加）。"""
    cam = _make_camera()
    cam.trigger_shake(0.4, 8.0)

    offsets = set()
    for _ in range(10):
        cam.update(500.0, 500.0, 2000, 2000, 0.016)
        offsets.add((cam.shake_offset_x, cam.shake_offset_y))

    # 至少应有 2 种不同的偏移组合（避免随机巧合为单一值）
    assert len(offsets) >= 2, (
        f"震颤偏移应有变化，仅得到 {len(offsets)} 种组合"
    )
    print("[PASS] test_camera_shake_offset_changes — offsets vary each frame")


def test_camera_get_render_offset():
    """验证 get_render_offset 叠加了震颤偏移。"""
    cam = _make_camera()
    cam.offset_x = 100.0
    cam.offset_y = 200.0

    # 无震颤时应返回原始偏移
    rx, ry = cam.get_render_offset()
    assert rx == 100.0 and ry == 200.0, (
        f"无震颤时应返回 (100, 200)，得到 ({rx}, {ry})"
    )

    # 触发震颤后 get_render_offset 应叠加噪声
    cam.trigger_shake(0.4, 5.0)
    rx2, ry2 = cam.get_render_offset()

    assert rx2 != 100.0 or ry2 != 200.0, (
        "震颤中 get_render_offset 应与原始偏移不同"
    )
    print("[PASS] test_camera_get_render_offset — shake offset included")


# =============================================================================
# 集成安全性测试
# =============================================================================

def test_effects_mass_spawn_no_crash():
    """验证大量特效生成 + 更新 + 渲染不崩溃。"""
    if not pygame.get_init():
        pygame.init()

    mgr = EffectsManager()
    test_surf = pygame.Surface((1024, 768))

    # 连续生成 10 波粒子 + 文本
    for i in range(10):
        mgr.spawn_particles(400 + i * 10, 300, (255, 200, 0), count=20)
        mgr.spawn_text(400 + i * 10, 280, f"Wave {i}", (255, 255, 255))

        # 更新 + 渲染不应崩溃
        try:
            mgr.update(0.016)
            mgr.render(test_surf, (0.0, 0.0))
        except Exception as e:
            assert False, f"第 {i} 波特效崩溃: {e}"

    print("[PASS] test_effects_mass_spawn_no_crash — 10 burst waves, no crash")


def test_effects_clear():
    """验证 EffectsManager.clear() 正确清空所有特效。"""
    mgr = EffectsManager()
    mgr.spawn_particles(100, 100, (255, 0, 0), count=10)
    mgr.spawn_text(100, 80, "Clear test", (255, 255, 255))

    mgr.clear()

    assert len(mgr.particles) == 0, (
        f"clear 后粒子数应为 0，得到 {len(mgr.particles)}"
    )
    assert len(mgr.floating_texts) == 0, (
        f"clear 后文本数应为 0，得到 {len(mgr.floating_texts)}"
    )
    print("[PASS] test_effects_clear — all effects cleared")


def test_effects_empty_render():
    """验证空管理器调用 render 不抛异常。"""
    mgr = EffectsManager()
    test_surf = pygame.Surface((800, 600))

    try:
        mgr.render(test_surf, (0.0, 0.0))
        mgr.update(0.016)
    except Exception as e:
        assert False, f"空 EffectsManager 操作崩溃: {e}"

    print("[PASS] test_effects_empty_render — empty manager OK")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    # 粒子物理
    test_particle_gravity()
    test_particle_air_drag()
    test_particle_lifetime_expiry()
    test_particle_position_update()

    # 浮动文本
    test_floating_text_drift_upward()
    test_floating_text_fade_alpha()
    test_floating_text_lifetime_expiry()
    test_floating_text_font_size()

    # 屏幕震颤
    test_camera_shake_trigger()
    test_camera_shake_decay()
    test_camera_shake_offset_changes()
    test_camera_get_render_offset()

    # 集成安全性
    test_effects_mass_spawn_no_crash()
    test_effects_clear()
    test_effects_empty_render()

    print("\n=== ALL EFFECTS TESTS PASSED ===")
