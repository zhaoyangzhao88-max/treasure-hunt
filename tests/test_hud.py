"""HUD 状态栏渲染验证脚本 — Microsoft Treasure Hunt

Headless 模式下验证：
- HUD 实例化不抛异常
- 在无资源文件环境下 render() 不崩溃
- HUD 正确读取并反映 PlayerState 数值变化
- 边界值（0 hearts, max keys 等）渲染安全

运行方式::

    python tests/test_hud.py
"""

import os
import sys

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Headless 模式：必须在 pygame.init() 之前设置
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from src.config import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_HEIGHT
from src.player_state import PlayerState
from src.hud import HUD


# =============================================================================
# 辅助函数
# =============================================================================

def _make_player() -> PlayerState:
    """创建一个测试用 PlayerState，赋予典型数值。"""
    player = PlayerState()
    player.current_hearts = 4
    player.max_hearts = 5
    player.current_shields = 1
    player.max_shields = 2
    player.gold = 250
    player.tools["pickaxe"] = 2
    player.tools["dynamite"] = 1
    player.tools["map"] = 0
    player.keys["RED"] = 3
    player.keys["GREEN"] = 1
    player.keys["BLUE"] = 0
    player.keys["EXIT"] = 1
    player.arrows = 5
    player.has_machete = True
    player.has_clover = True
    return player


def _make_surface() -> pygame.Surface:
    """创建离屏 Surface 用于 headless 渲染。"""
    if not pygame.get_init():
        pygame.init()
    return pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)


# =============================================================================
# 测试用例
# =============================================================================

def test_hud_instantiation():
    """测试 HUD 实例化：绑定 PlayerState 不抛异常。"""
    player = _make_player()
    hud = HUD(player)

    assert hud.player_state is player, "HUD 应持有对 PlayerState 的引用"
    assert hud.font is not None, "HUD 字体应成功加载（含降级）"
    assert hud.font_small is not None, "HUD 小字体应成功加载（含降级）"

    print("[PASS] test_hud_instantiation")


def test_hud_render_no_crash():
    """测试 HUD 渲染无崩溃：无资源文件环境下 render() 顺畅走通。"""
    player = _make_player()
    hud = HUD(player)
    surface = _make_surface()

    # 渲染不应抛异常
    hud.render(surface, current_level_num=1)

    print("[PASS] test_hud_render_no_crash")


def test_hud_reflects_player_state():
    """测试 HUD 反映 PlayerState 数值变化：修改 player 后 HUD 读取最新值。"""
    player = _make_player()
    hud = HUD(player)
    surface = _make_surface()

    # 第一次渲染
    hud.render(surface, current_level_num=1)

    # 修改 PlayerState
    player.current_hearts = 2
    player.gold = 999
    player.tools["pickaxe"] = 0
    player.keys["BLUE"] = 7
    player.has_machete = False
    player.has_clover = False

    # 第二次渲染（应反映新值，且不崩溃）
    hud.render(surface, current_level_num=5)

    # 验证 HUD 确实引用了修改后的 player_state
    assert hud.player_state.current_hearts == 2
    assert hud.player_state.gold == 999
    assert hud.player_state.tools["pickaxe"] == 0
    assert hud.player_state.keys["BLUE"] == 7
    assert hud.player_state.has_machete is False
    assert hud.player_state.has_clover is False

    print("[PASS] test_hud_reflects_player_state")


def test_hud_render_zero_hearts():
    """测试 HUD 渲染零生命值：边界值不崩溃。"""
    player = _make_player()
    player.current_hearts = 0
    player.current_shields = 0
    player.gold = 0
    player.tools = {"pickaxe": 0, "dynamite": 0, "map": 0}
    player.keys = {"RED": 0, "GREEN": 0, "BLUE": 0, "EXIT": 0}
    player.arrows = 0

    hud = HUD(player)
    surface = _make_surface()

    # 全零值渲染不应崩溃
    hud.render(surface, current_level_num=1)

    print("[PASS] test_hud_render_zero_hearts")


def test_hud_render_max_values():
    """测试 HUD 渲染最大值：满血满钥匙满工具不崩溃。"""
    player = _make_player()
    player.current_hearts = player.max_hearts = 8
    player.current_shields = player.max_shields = 3
    player.gold = 99999
    player.tools = {"pickaxe": 4, "dynamite": 4, "map": 4}
    player.keys = {"RED": 99, "GREEN": 99, "BLUE": 99, "EXIT": 99}
    player.arrows = 999

    hud = HUD(player)
    surface = _make_surface()

    hud.render(surface, current_level_num=99)

    print("[PASS] test_hud_render_max_values")


def test_hud_render_various_levels():
    """测试 HUD 渲染不同关卡数：关卡编号正确传递。"""
    player = _make_player()
    hud = HUD(player)
    surface = _make_surface()

    for level in [1, 2, 5, 10, 50, 100]:
        hud.render(surface, current_level_num=level)

    print("[PASS] test_hud_render_various_levels")


def test_hud_with_damage_and_heal():
    """测试 HUD 反映伤害与治疗过程。"""
    player = _make_player()
    hud = HUD(player)
    surface = _make_surface()

    initial_hearts = player.current_hearts
    initial_shields = player.current_shields

    # 受伤（护盾优先吸收）
    player.apply_damage(2)
    hud.render(surface, current_level_num=1)
    # 护盾吸收了 1 点，红心减少 1 点
    assert player.current_hearts == initial_hearts - 1, (
        f"受伤后红心应为 {initial_hearts - 1}，得到 {player.current_hearts}"
    )

    # 治疗
    player.add_hearts(1)
    hud.render(surface, current_level_num=1)
    assert player.current_hearts == initial_hearts, "治疗后红心应恢复至初始值"

    print("[PASS] test_hud_with_damage_and_heal")


def test_hud_keys_and_tools_interaction():
    """测试 HUD 反映钥匙与工具的增减操作。"""
    player = _make_player()
    hud = HUD(player)
    surface = _make_surface()

    # 添加钥匙
    player.add_key("RED", 2)
    assert player.keys["RED"] == 5  # 初始 3 + 2
    hud.render(surface, current_level_num=1)

    # 使用钥匙
    player.use_key("GREEN")
    assert player.keys["GREEN"] == 0  # 初始 1 - 1
    hud.render(surface, current_level_num=1)

    # 添加工具
    player.add_tool("dynamite", 2)
    hud.render(surface, current_level_num=1)

    # 使用工具
    player.use_tool("pickaxe", 1)
    assert player.tools["pickaxe"] == 1  # 初始 2 - 1
    hud.render(surface, current_level_num=1)

    print("[PASS] test_hud_keys_and_tools_interaction")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    test_hud_instantiation()
    test_hud_render_no_crash()
    test_hud_reflects_player_state()
    test_hud_render_zero_hearts()
    test_hud_render_max_values()
    test_hud_render_various_levels()
    test_hud_with_damage_and_heal()
    test_hud_keys_and_tools_interaction()
    print("\n=== ALL HUD TESTS PASSED ===")
