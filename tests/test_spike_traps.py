"""周期地刺 SpikeTrap 单元测试 — Microsoft Treasure Hunt（第 50 课）

Headless 模式通过纯 assert 验证六项关键机制：
1) SpikeTrap 默认状态、初始字段与参数化构造
2) 完整 6 步确定性翻转周期（RETRACTED→EXTENDED→RETRACTED）
3) 玩家步入 EXTENDED 地刺格触发刺伤扣血（护盾优先吸收）
4) 玩家步入 RETRACTED 地刺格完全安全（零伤害）
5) 原地不动开掘泥土驱动地刺翻转并触发驻留刺击受伤
6) LevelGenerator 仅在 Level >= 3 时散放地刺 + 渲染不崩溃

运行：python tests/test_spike_traps.py
或：python -m pytest tests/test_spike_traps.py -v
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.spike_trap import SpikeTrap, RETRACTED, EXTENDED
from src.spike_trap import FLIPPED_OUT, FLIPPED_IN, EVENT_NONE
from src.interaction_controller import InteractionController
from src.map_data import GameMap
from src.player_state import PlayerState
from src.level_generator import LevelGenerator
from src.tile_renderer import TileRenderer
from src.config import SPIKE_TRAP


# ---------------------------------------------------------------------------
# 辅助：构造全裸露最小地图（layer0 == UNCOVERED, layer1/layer2 == NONE）
# ---------------------------------------------------------------------------

def _make_open_map(w=10, h=10):
    m = GameMap(w, h)
    for y in range(h):
        for x in range(w):
            m.layer0[y][x] = "UNCOVERED"
            m.layer1[y][x] = "NONE"
            m.layer2[y][x] = "NONE"
    return m


def _make_ctrl(map_, player=None, start=(0, 0)):
    if player is None:
        player = PlayerState()
    ctrl = InteractionController(map_, player,
                                 start_x=start[0], start_y=start[1])
    ctrl.invincible_timer = 0.0
    return ctrl


# ---------------------------------------------------------------------------
# 测试 1：默认状态与构造
# ---------------------------------------------------------------------------

def test_spike_trap_import_and_default_state():
    """SpikeTrap 默认状态为 RETRACTED、threshold=3、计数器=0。"""
    spike = SpikeTrap(3, 4)
    assert spike.get_state() == RETRACTED, \
        f"默认态应为 RETRACTED，得到 {spike.get_state()}"
    assert spike.get_state_label() == RETRACTED
    assert spike.x == 3 and spike.y == 4
    assert spike.is_retracted() is True
    assert spike.is_extended() is False
    assert spike.turn == 0
    assert spike.get_last_event() == EVENT_NONE
    print("[PASS] test_spike_trap_import_and_default_state")


# ---------------------------------------------------------------------------
# 测试 2：完整 6 步确定性翻转周期
# ---------------------------------------------------------------------------

def test_spike_trap_three_step_cycle():
    """完整 6 步周期：RETRACTED → EXTENDED(第3拍) → RETRACTED(第6拍)。

    每调用一次 ``on_player_move()`` 模拟一次"消耗型操作"，
    在 step_threshold=3 时地刺会精确翻转为 EXTENDED / RETRACTED。
    """
    spike = SpikeTrap(0, 0, step_threshold=3)

    # 第 1 拍：不开火（turn_counter 1/3）
    ev1 = spike.on_player_move()
    assert ev1 == EVENT_NONE, f"第 1 拍应 NONE，得到 {ev1}"
    assert spike.get_state() == RETRACTED
    assert spike.turn == 1

    # 第 2 拍：不开火（turn_counter 2/3）
    ev2 = spike.on_player_move()
    assert ev2 == EVENT_NONE, f"第 2 拍应 NONE，得到 {ev2}"
    assert spike.get_state() == RETRACTED
    assert spike.turn == 2

    # 第 3 拍：弹出（turn_counter 3/3 ⇒ flip EXTENDED，重置为 0）
    ev3 = spike.on_player_move()
    assert ev3 == FLIPPED_OUT, f"第 3 拍应 FLIPPED_OUT，得到 {ev3}"
    assert spike.get_state() == EXTENDED
    assert spike.is_extended() is True
    assert spike.turn == 0
    assert spike.get_last_event() == FLIPPED_OUT

    # 第 4、5 拍：不开火
    assert spike.on_player_move() == EVENT_NONE
    assert spike.on_player_move() == EVENT_NONE
    assert spike.turn == 2
    assert spike.get_state() == EXTENDED

    # 第 6 拍：收回（flip RETRACTED，重置为 0）
    ev6 = spike.on_player_move()
    assert ev6 == FLIPPED_IN, f"第 6 拍应 FLIPPED_IN，得到 {ev6}"
    assert spike.get_state() == RETRACTED
    assert spike.is_retracted() is True
    assert spike.turn == 0
    assert spike.get_last_event() == FLIPPED_IN
    print("[PASS] test_spike_trap_three_step_cycle")


# ---------------------------------------------------------------------------
# 测试 3：玩家步入 EXTENDED 地刺格 → 扣血（护盾优先）
# ---------------------------------------------------------------------------

def test_player_stepping_on_extended_spike_takes_damage():
    """玩家步入状态为 EXTENDED 的地刺格时扣血（护盾优先吸收）。"""
    m = _make_open_map(10, 10)
    p = PlayerState()
    # 无护盾，直接验证红心扣减（刺伤扣 1 血）
    p.current_shields = 0
    p.current_hearts = 3

    spike = SpikeTrap(1, 1, initial_state=EXTENDED)
    ctrl = _make_ctrl(m, p, start=(0, 0))
    ctrl.spike_traps.append(spike)

    # 步入了 EXTENDED 地刺
    result = ctrl.move_player(1, 1)
    assert result == "SUCCESS", f"move_player 应 SUCCESS，得到 {result}"

    # 步入了 EXTENDED 地刺，触发刺伤扣血（无护盾时扣红心）
    assert p.current_hearts == 2, \
        f"红心应由 3 降为 2，得到 {p.current_hearts}"
    assert p.current_shields == 0, \
        f"护盾应保持为 0，得到 {p.current_shields}"
    print("[PASS] test_player_stepping_on_extended_spike_takes_damage")


def test_player_stepping_on_extended_spike_shield_absorbs():
    """玩家步入 EXTENDED 地刺格时，若装备护盾，应优先扣护盾。"""
    m = _make_open_map(10, 10)
    p = PlayerState()
    p.current_shields = 1
    p.current_hearts = 3

    spike = SpikeTrap(1, 1, initial_state=EXTENDED)
    ctrl = _make_ctrl(m, p, start=(0, 0))
    ctrl.spike_traps.append(spike)

    result = ctrl.move_player(1, 1)
    assert result == "SUCCESS"

    # 护盾优先吸收刺伤
    assert p.current_shields == 0, \
        f"护盾应被刺穿降为 0，得到 {p.current_shields}"
    assert p.current_hearts == 3, \
        f"红心应保持为 3（盾吸收了），得到 {p.current_hearts}"
    print("[PASS] test_player_stepping_on_extended_spike_shield_absorbs")


# ---------------------------------------------------------------------------
# 测试 4：玩家步入 RETRACTED 地刺格 → 安全（零伤害）
# ---------------------------------------------------------------------------

def test_player_stepping_on_retracted_spike_is_safe():
    """玩家步入状态为 RETRACTED 的地刺格时完全安全，无扣血。"""
    m = _make_open_map(10, 10)
    p = PlayerState()
    p.current_shields = 1
    p.current_hearts = 3
    # 主动设置 turn_counter=0，仅进入 1 拍不会导致翻转
    spike = SpikeTrap(1, 1, initial_state=RETRACTED)
    assert spike.turn == 0
    ctrl = _make_ctrl(m, p, start=(0, 0))
    ctrl.spike_traps.append(spike)

    result = ctrl.move_player(1, 1)
    assert result == "SUCCESS"
    # 进入 RETRACTED 尖刺格经过 1 拍驱动后仍 RETRACTED，玩家安全
    assert spike.get_state() == RETRACTED, \
        f"进入 1 拍后应仍为 RETRACTED，得到 {spike.get_state()}"
    assert p.current_shields == 1, \
        f"护盾应不变，得到 {p.current_shields}"
    assert p.current_hearts == 3, \
        f"红心应不变，得到 {p.current_hearts}"
    print("[PASS] test_player_stepping_on_retracted_spike_is_safe")


# ---------------------------------------------------------------------------
# 测试 5：原地不动开掘泥土驱动地刺翻转 → 驻留刺击受伤
# ---------------------------------------------------------------------------

def test_player_staying_put_uncovering_triggers_spike_and_damage():
    """玩家原地不动，在旁边开掘泥土时驱动地刺翻转并触发驻留刺击。

    场景：
    - 玩家站在 (0,0)，生命满，+1 护盾。
    - (0,0) 放一个 RETRACTED 地刺，turn_counter == 2（阈值 3，再 1 步翻转）。
    - 玩家在 (0,1) 开掘（uncover_tile），这将驱动地刺步数递增。
    - 预期地刺翻为 EXTENDED，玩家被弹出的尖刺刺伤。
    """
    m = _make_open_map(10, 10)
    # (0,1) 改为 DIRT 以便开掘
    m.layer0[1][0] = "DIRT"

    p = PlayerState()
    # 无护盾，直接扣红心，验证驻留伤害的数值正确性
    p.current_shields = 0
    p.current_hearts = 3

    spike = SpikeTrap(0, 0, initial_state=RETRACTED)
    spike.turn_counter = 2   # 阈值 3 ⇒ 再有 1 步翻转
    ctrl = _make_ctrl(m, p, start=(0, 0))
    ctrl.spike_traps.append(spike)

    # 确认玩家实际站在 (0,0)
    assert ctrl.player_x == 0 and ctrl.player_y == 0
    # 记录反面：玩家原先未受伤
    assert p.current_hearts == 3

    # 原地开掘 (0,1) 的泥土
    result = ctrl.uncover_tile(0, 1)
    assert result is True, "安全格开掘应返回 True"

    # 驻留刺击判定的关键断言
    assert spike.get_state() == EXTENDED, \
        f"原地开掘驱动地刺翻转后应为 EXTENDED，得到 {spike.get_state()}"
    # 无护盾 → 扣红心 3→2
    assert p.current_shields == 0, \
        f"护盾应保持为 0，得到 {p.current_shields}"
    assert p.current_hearts == 2, \
        f"驻留刺击红心 3→2，得到 {p.current_hearts}"
    print("[PASS] test_player_staying_put_uncovering_triggers_spike_and_damage")


# ---------------------------------------------------------------------------
# 测试 6：LevelGenerator 仅在 Level >= 3 时散放 + 渲染不崩溃
# ---------------------------------------------------------------------------

def test_level_scatter_spike_traps_only_from_level_3_and_no_render_crash():
    """LevelGenerator：
    - level < 3 时不放地刺。
    - level >= 3 时至少放 1 个地刺。
    - 渲染器 EXTENDED 态绘制不崩溃。"""
    seed = 20260630
    gen2 = LevelGenerator(seed=seed)
    map2, _, _ = gen2.generate_level(2)
    count2 = sum(1 for y in range(map2.height) for x in range(map2.width)
                 if map2.layer2[y][x] == SPIKE_TRAP)
    assert count2 == 0, f"level 2 不应放 SPIKE_TRAP，得到 {count2} 个"

    gen3 = LevelGenerator(seed=seed)
    map3, _, _ = gen3.generate_level(3)
    spikes3 = [(x, y) for y in range(map3.height) for x in range(map3.width)
               if map3.layer2[y][x] == SPIKE_TRAP]
    assert len(spikes3) >= 1, "level 3 应至少放 1 个 SPIKE_TRAP"

    # 渲染验证（EXTENDED 态 + RETRACTED 态）
    surf = pygame.Surface((480, 480))
    renderer = TileRenderer(tile_size=48)
    for (x, y) in spikes3:
        # 危险态
        renderer.draw_tile(surf, SPIKE_TRAP, x * 48, y * 48,
                           extra_info="EXTENDED")
        # 安全态
        renderer.draw_tile(surf, SPIKE_TRAP, x * 48, y * 48,
                           extra_info="RETRACTED")
        # 默认态（无 extra_info）
        renderer.draw_tile(surf, SPIKE_TRAP, x * 48, y * 48)
    print("[PASS] test_level_scatter_spike_traps_only_from_level_3_and_no_render_crash")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_spike_trap_import_and_default_state()
    test_spike_trap_three_step_cycle()
    test_player_stepping_on_extended_spike_takes_damage()
    test_player_stepping_on_extended_spike_shield_absorbs()
    test_player_stepping_on_retracted_spike_is_safe()
    test_player_staying_put_uncovering_triggers_spike_and_damage()
    test_level_scatter_spike_traps_only_from_level_3_and_no_render_crash()
    print("\n=== ALL SPIKE TRAP TESTS PASSED ===")
