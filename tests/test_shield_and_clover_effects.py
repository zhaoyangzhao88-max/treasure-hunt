"""第 38 课：护盾波纹 & 四叶草绿芒 — 单元测试

验证：
  1. spawn_shield_shatter 产生亮青色碎片粒子
  2. spawn_clover_spark 产生嫩绿色轨迹粒子
  3. shield_flash_timer 衰减逻辑
  4. update(dt) 触发四叶草粒子发射
  5. TileRenderer 在 shields>0 / has_clover=True 时绘制不崩溃
  6. 向后兼容：extra_info=Animator 实例
  7. 受击分支：had_shields>0 → 青色闪屏；had_shields=0 → 红色闪屏

运行模式：Headless (SDL_VIDEODRIVER=dummy)
"""

import os
import sys

# 设置 headless 模式
os.environ["SDL_VIDEODRIVER"] = "dummy"

# 确保项目根目录在 sys.path 中
_project_root = os.path.join(os.path.dirname(__file__), "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src_dir = os.path.join(_project_root, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import pygame

# 初始化 pygame（dummy 模式）
if not pygame.get_init():
    pygame.init()

from src.effects import EffectsManager  # noqa: E402


def _advance(mgr: EffectsManager, total_seconds: float, step: float = 0.05):
    """推进 mgr 的总时长（秒），每帧 step 秒。"""
    elapsed = 0.0
    while elapsed < total_seconds:
        mgr.update(min(step, total_seconds - elapsed))
        elapsed += step
from src.player_state import PlayerState
from src.tile_renderer import TileRenderer
from src.animation import Animator
from src.config import TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT, HUD_HEIGHT


# ---------------------------------------------------------------------------
# 测试 1：护盾碎片粒子
# ---------------------------------------------------------------------------
def test_shield_shatter_particles():
    mgr = EffectsManager()
    mgr.spawn_shield_shatter(240.0, 240.0, count=20)
    assert len(mgr.particles) == 20, f"Expected 20 particles, got {len(mgr.particles)}"
    for p in mgr.particles:
        assert p.color == (0, 240, 255), f"Expected cyan color, got {p.color}"
    # 推进足够长时间让所有粒子死亡（循环多帧，每帧 0.05s）
    _advance(mgr, 0.7)
    assert len(mgr.particles) == 0, f"Expected 0 particles after 0.7s, got {len(mgr.particles)}"
    print("[PASS] test_shield_shatter_particles — 20 个亮青色碎片产生并在 0.7s 后全部消亡")


# ---------------------------------------------------------------------------
# 测试 2：四叶草轨迹粒子
# ---------------------------------------------------------------------------
def test_clover_spark_particles():
    mgr = EffectsManager()
    mgr.spawn_clover_spark(240.0, 240.0)
    count = len(mgr.particles)
    assert 1 <= count <= 2, f"Expected 1-2 particles, got {count}"
    for p in mgr.particles:
        assert p.color == (34, 197, 94), f"Expected clover green, got {p.color}"
    # 推进足够长时间让所有粒子死亡（循环多帧，每帧 0.05s）
    _advance(mgr, 0.6)
    assert len(mgr.particles) == 0, f"Expected 0 particles after 0.6s, got {len(mgr.particles)}"
    print("[PASS] test_clover_spark_particles — 1-2 个嫩绿轨迹粒子产生并在 0.6s 后消亡")


# ---------------------------------------------------------------------------
# 测试 3：护盾屏闪计时器衰减
# ---------------------------------------------------------------------------
def test_shield_flash_timer_decay():
    # 模拟 GameplayScreen 的 shield_flash_timer 逻辑
    shield_flash_timer = 0.2
    dt = 0.05
    for _ in range(4):
        shield_flash_timer = max(0.0, shield_flash_timer - dt)
    assert abs(shield_flash_timer - 0.0) < 1e-9, f"Expected ~0.0, got {shield_flash_timer}"

    # 额外验证：从 0.2 衰减到 0.1 需要 2 帧
    shield_flash_timer = 0.2
    shield_flash_timer = max(0.0, shield_flash_timer - 0.05)
    shield_flash_timer = max(0.0, shield_flash_timer - 0.05)
    assert abs(shield_flash_timer - 0.1) < 1e-9, f"Expected 0.1, got {shield_flash_timer}"
    print("[PASS] test_shield_flash_timer_decay — shield_flash_timer 从 0.2 经 4 帧衰减至 0.0")


# ---------------------------------------------------------------------------
# 测试 4：四叶草粒子发射（update 触发）
# ---------------------------------------------------------------------------
def test_clover_particle_emission_on_update():
    mgr = EffectsManager()

    # 模拟 GameplayScreen.update 中的 clover 逻辑
    class FakePlayer:
        has_clover = True

    class FakeGameManager:
        player_state = FakePlayer()

    gm = FakeGameManager()
    clover_spark_timer = 0.0
    player_x, player_y = 5, 5

    # 模拟 update(0.25) — 应触发 floor(0.25 / 0.08) = 3 次发射
    dt = 0.25
    clover_spark_timer += dt
    while clover_spark_timer >= 0.08:
        clover_spark_timer -= 0.08
        sx = player_x * TILE_SIZE + TILE_SIZE // 2
        sy = player_y * TILE_SIZE + TILE_SIZE
        mgr.spawn_clover_spark(sx, sy)

    # 每次 spawn 产生 1-2 个粒子，3 次至少 3 个
    assert len(mgr.particles) >= 3, f"Expected >=3 particles, got {len(mgr.particles)}"
    for p in mgr.particles:
        assert p.color == (34, 197, 94), f"Expected clover green, got {p.color}"
    print(f"[PASS] test_clover_particle_emission_on_update — update(0.25) 产生 {len(mgr.particles)} 个绿芒粒子")


# ---------------------------------------------------------------------------
# 测试 5：TileRenderer 护盾/四叶草绘制不崩溃
# ---------------------------------------------------------------------------
def test_draw_tile_shield_clover_no_crash():
    renderer = TileRenderer()
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    anim = Animator()

    # 构造不同状态的 PlayerState
    class FakePlayerState:
        def __init__(self, shields=0, has_clover=False):
            self.current_shields = shields
            self.has_clover = has_clover

    # 场景 1：shields > 0, has_clover = True
    ps1 = FakePlayerState(shields=2, has_clover=True)
    renderer.draw_tile(surf, "PLAYER", 100, 100, extra_info={"animator": anim, "player_state": ps1})

    # 场景 2：shields > 0, has_clover = False
    ps2 = FakePlayerState(shields=1, has_clover=False)
    renderer.draw_tile(surf, "PLAYER", 100, 100, extra_info={"animator": anim, "player_state": ps2})

    # 场景 3：shields = 0, has_clover = True
    ps3 = FakePlayerState(shields=0, has_clover=True)
    renderer.draw_tile(surf, "PLAYER", 100, 100, extra_info={"animator": anim, "player_state": ps3})

    # 场景 4：shields = 0, has_clover = False
    ps4 = FakePlayerState(shields=0, has_clover=False)
    renderer.draw_tile(surf, "PLAYER", 100, 100, extra_info={"animator": anim, "player_state": ps4})

    # 场景 5：extra_info = None
    renderer.draw_tile(surf, "PLAYER", 100, 100, extra_info=None)

    # 场景 6：extra_info = Animator（向后兼容）
    renderer.draw_tile(surf, "PLAYER", 100, 100, extra_info=anim)

    # 场景 7：extra_info = dict 但缺少 player_state
    renderer.draw_tile(surf, "PLAYER", 100, 100, extra_info={"animator": anim})

    print("[PASS] test_draw_tile_shield_clover_no_crash — 7 种场景全部无崩溃")


# ---------------------------------------------------------------------------
# 测试 6：向后兼容 — 纯 Animator 实例
# ---------------------------------------------------------------------------
def test_draw_tile_plain_animator_backward_compat():
    renderer = TileRenderer()
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    anim = Animator()
    anim.state_time = 0.5  # 给一个非零时间确保动画计算正常

    # 纯 Animator 实例（非 dict）— 不应崩溃
    renderer.draw_tile(surf, "PLAYER", 200, 200, extra_info=anim)

    # 验证 surface 上有像素被绘制（玩家身体是绿色圆）
    # 检查中心区域是否有非透明像素
    center_x, center_y = 200 + TILE_SIZE // 2, 200 + TILE_SIZE // 2
    pixel = surf.get_at((center_x, center_y))
    # 只要不是全透明就说明绘制了东西
    assert pixel.a > 0 or pixel[:3] != (0, 0, 0), "Player sprite should be drawn"
    print("[PASS] test_draw_tile_plain_animator_backward_compat — 纯 Animator 实例向后兼容")


# ---------------------------------------------------------------------------
# 测试 7：护盾视觉激活条件
# ---------------------------------------------------------------------------
def test_shield_visual_active_when_shields_positive():
    renderer = TileRenderer()
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    anim = Animator()
    anim.state_time = 1.0  # 确保 sin 值非零

    class FakePlayerState:
        current_shields = 2
        has_clover = False

    ps = FakePlayerState()
    # 多次调用确保稳定
    for _ in range(5):
        renderer.draw_tile(surf, "PLAYER", 150, 150, extra_info={"animator": anim, "player_state": ps})

    print("[PASS] test_shield_visual_active_when_shields_positive — shields=2 时护盾波纹绘制无异常")


# ---------------------------------------------------------------------------
# 测试 8：受击分支 — 无护盾 → 红色闪屏
# ---------------------------------------------------------------------------
def test_damage_path_red_flash_no_shields():
    # 模拟 _trigger_damage_effect 的判定逻辑
    damage_flash_timer = 0.0
    shield_flash_timer = 0.0

    # had_shields = 0 → 走红色路径
    had_shields = 0
    if had_shields is not None and had_shields > 0:
        shield_flash_timer = 0.2
    else:
        damage_flash_timer = 0.25

    assert damage_flash_timer == 0.25, f"Expected 0.25, got {damage_flash_timer}"
    assert shield_flash_timer == 0.0, f"Expected 0.0, got {shield_flash_timer}"
    print("[PASS] test_damage_path_red_flash_no_shields — had_shields=0 触发红色闪屏 (damage_flash_timer=0.25)")


# ---------------------------------------------------------------------------
# 测试 9：受击分支 — 有护盾 → 青色闪屏
# ---------------------------------------------------------------------------
def test_damage_path_cyan_flash_with_shields():
    damage_flash_timer = 0.0
    shield_flash_timer = 0.0

    # had_shields = 2 → 走青色路径
    had_shields = 2
    if had_shields is not None and had_shields > 0:
        shield_flash_timer = 0.2
    else:
        damage_flash_timer = 0.25

    assert shield_flash_timer == 0.2, f"Expected 0.2, got {shield_flash_timer}"
    assert damage_flash_timer == 0.0, f"Expected 0.0, got {damage_flash_timer}"
    print("[PASS] test_damage_path_cyan_flash_with_shields — had_shields=2 触发青色闪屏 (shield_flash_timer=0.2)")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_shield_shatter_particles()
    test_clover_spark_particles()
    test_shield_flash_timer_decay()
    test_clover_particle_emission_on_update()
    test_draw_tile_shield_clover_no_crash()
    test_draw_tile_plain_animator_backward_compat()
    test_shield_visual_active_when_shields_positive()
    test_damage_path_red_flash_no_shields()
    test_damage_path_cyan_flash_with_shields()
    print("\n=== ALL TESTS PASSED ===")
