"""MummyShopScreen 卡片式 UI 与购买微特效验证脚本 — Microsoft Treasure Hunt

测试第 40 课升级：
- EffectsManager 局部实例化
- 3 列卡片网格布局与 Rect 计算
- 购买触发金色粒子 + 绿色漂浮文字 + 金币抖动
- 特效帧更新与衰减
- 卡片按钮点击区边界
- 渲染无崩溃
"""

import os
import sys

# 设置 headless 驱动必须在 pygame.init() 之前
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# 确保能找到 src/ 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 初始化 Pygame（display + font + mixer）— 仅初始化一次
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

from src.screens.mummy_shop_screen import MummyShopScreen, SHOP_ITEMS, _COL_X_POSITIONS, _CARD_WIDTH, _CARD_HEIGHT, _CARD_START_Y
from src.screens.base_screen import BaseScreen
from src.game_manager import GameManager
from src.asset_manager import AssetManager
from src.effects import EffectsManager
from src.tile_renderer import TileRenderer
from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT, HARD_CAP_HEARTS, HEART_UPGRADE_PRICES


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------

def _reset_game_manager():
    """重置 GameManager 和 AssetManager 单例，并初始化引擎。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)
    # 重置 player_state 为干净的初始状态
    gm.player_state.gold = 0
    gm.player_state.current_hearts = 3
    gm.player_state.max_hearts = 3
    gm.player_state.current_shields = 0
    gm.player_state.max_shields = 1
    gm.player_state.tools = {"pickaxe": 0, "dynamite": 0, "map": 0}
    gm.player_state.keys = {"RED": 0, "GREEN": 0, "BLUE": 0, "EXIT": 0}
    gm.player_state.bag_tier_index = 0
    gm.player_state.has_amulet = False
    gm.player_state.highest_level_cleared = 0
    gm.player_state.total_gold_earned = 0
    return gm


def _find_button_by_item_id(screen, item_id: str):
    """根据 item_id 查找对应的按钮。"""
    for btn in screen.buttons:
        if getattr(btn, "item_id", None) == item_id:
            return btn
    return None


def _click_button(screen, btn):
    """模拟点击按钮。"""
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    screen.handle_event(click_event)


# ==========================================================================
# 测试
# ==========================================================================

def test_effects_manager_instantiated():
    """on_enter 应成功实例化 EffectsManager、TileRenderer，且金币抖动为 0。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    # 验证 effects_manager 已实例化
    assert isinstance(screen.effects_manager, EffectsManager), (
        f"effects_manager 应是 EffectsManager 实例，得到 {type(screen.effects_manager)}"
    )

    # 验证 tile_renderer 已实例化
    assert isinstance(screen.tile_renderer, TileRenderer), (
        f"tile_renderer 应是 TileRenderer 实例，得到 {type(screen.tile_renderer)}"
    )

    # 验证金币抖动初始值为 0
    assert screen.gold_shake_timer == 0.0, (
        f"gold_shake_timer 初始应为 0.0，得到 {screen.gold_shake_timer}"
    )

    # 验证 particles / floating_texts 初始为空列表
    assert screen.effects_manager.particles == [], "粒子池初始应为空"
    assert screen.effects_manager.floating_texts == [], "漂浮文字池初始应为空"

    print("[PASS] test_effects_manager_instantiated")


def test_card_rects_calculated():
    """卡片 Rect 应为每个商品计算正确，3 列 X 坐标与行 Y 坐标对齐。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    # 验证 7 个商品的 card_rect 都存在
    for item in SHOP_ITEMS:
        assert item["id"] in screen._card_rects, (
            f"{item['id']} 的 card_rect 应存在于 _card_rects 中"
        )

    # 宽度验证
    for item_id, rect in screen._card_rects.items():
        assert rect.width == _CARD_WIDTH, (
            f"{item_id} 卡片宽度应为 {_CARD_WIDTH}，得到 {rect.width}"
        )
        assert rect.height == _CARD_HEIGHT, (
            f"{item_id} 卡片高度应为 {_CARD_HEIGHT}，得到 {rect.height}"
        )

    # 列 X 坐标验证（每列中心 X = _COL_X_POSITIONS[col]）
    for item in SHOP_ITEMS:
        rect = screen._card_rects[item["id"]]
        expected_center_x = _COL_X_POSITIONS[item["col"]]
        assert rect.centerx == expected_center_x, (
            f"{item['id']} (col={item['col']}) 中心 X 应为 {expected_center_x}，"
            f"得到 {rect.centerx}"
        )

    # 行 Y 坐标验证：同一列内行索引递增应等于 _CARD_HEIGHT + 30
    gap = _CARD_HEIGHT + 30
    for col_idx in range(3):
        items_in_col = [it for it in SHOP_ITEMS if it["col"] == col_idx]
        for row_idx, item in enumerate(items_in_col):
            rect = screen._card_rects[item["id"]]
            expected_y = _CARD_START_Y + row_idx * gap
            assert rect.y == expected_y, (
                f"{item['id']} (col={col_idx}, row={row_idx}) Y 应为 {expected_y}，"
                f"得到 {rect.y}"
            )

    print("[PASS] test_card_rects_calculated")


def test_purchase_triggers_effects():
    """购买 max_hearts 触发 15 个金色粒子 + 1 个绿色漂浮文字 + 金币抖动。"""
    gm = _reset_game_manager()
    save_calls = []
    gm.save_manager.save = lambda p, s=None: (save_calls.append(1), True)[1]

    # 赋予充裕金币 + 初始状态
    gm.player_state.gold = 1000
    gm.player_state.max_hearts = 3
    gm.player_state.current_hearts = 3

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    # 找到 max_hearts Buy 按钮并点击
    btn = _find_button_by_item_id(screen, "max_hearts")
    assert btn is not None, "应存在 max_hearts Buy 按钮"
    assert btn.is_enabled is True, "max_hearts 按钮应可点击"

    # 记录购买前价格
    max_hearts_price = HEART_UPGRADE_PRICES.get(3, 0)  # 200
    initial_gold = gm.player_state.gold

    _click_button(screen, btn)

    # ---- 断言金币减少 ----
    assert gm.player_state.max_hearts == 4, (
        f"max_hearts 应为 4，得到 {gm.player_state.max_hearts}"
    )
    assert gm.player_state.gold == initial_gold - max_hearts_price, (
        f"金币应减少 {max_hearts_price}，"
        f"初始 {initial_gold}，现在 {gm.player_state.gold}"
    )

    # ---- 断言 15 个金色粒子 ----
    particles = screen.effects_manager.particles
    assert len(particles) == 15, (
        f"粒子数应为 15，得到 {len(particles)}"
    )
    # 验证粒子颜色为金色 (255, 215, 0)
    gold_particles = [p for p in particles if p.color == (255, 215, 0)]
    assert len(gold_particles) == 15, (
        f"金色粒子数应为 15，得到 {len(gold_particles)}"
    )

    # ---- 断言 1 个绿色漂浮文字 ----
    texts = screen.effects_manager.floating_texts
    assert len(texts) == 1, f"漂浮文字数应为 1，得到 {len(texts)}"
    ft = texts[0]
    assert ft.color == (34, 197, 94), (
        f"漂浮文字颜色应为 (34,197,94)，得到 {ft.color}"
    )
    # 漂浮文字内容应包含 "+1" 和商品名
    assert "+1" in ft.text, f"漂浮文字应包含 '+1'，得到 '{ft.text}'"
    assert "Max Heart" in ft.text, (
        f"漂浮文字应包含 'Max Heart'，得到 '{ft.text}'"
    )

    # ---- 断言金币抖动计时器 ----
    assert screen.gold_shake_timer == 0.15, (
        f"gold_shake_timer 应为 0.15，得到 {screen.gold_shake_timer}"
    )

    # ---- 断言 save 被调用 ----
    assert len(save_calls) == 1, f"save() 应被调用 1 次，实际 {len(save_calls)} 次"

    print("[PASS] test_purchase_triggers_effects")


def test_effects_update_decay():
    """update(0.1) 后粒子 lifetime 衰减且金币抖动递减。"""
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    gm.player_state.gold = 1000
    gm.player_state.max_hearts = 3

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    # 购买触发特效
    btn = _find_button_by_item_id(screen, "max_hearts")
    assert btn is not None and btn.is_enabled

    # 购买 2 次以确保 max_hearts 还能继续升级（从价格表看 3→4 是 200, 4→5 是 350）
    # 但金币只够买一次（1000 gold, first upgrade costs 200），我们改为购买 shield
    # shield price = max_shields * 75 = 75; 购买后不满，不能再买
    # 回到正题：我们触发 max_hearts 购买一次
    _click_button(screen, btn)

    # 记录初始粒子信息
    initial_particles = screen.effects_manager.particles[:]
    initial_lifetimes = [p.lifetime for p in initial_particles]
    assert len(initial_particles) > 0, "应有粒子存在"
    max_initial_lifetime = max(initial_lifetimes)

    # 记录初始 gold_shake_timer
    initial_shake = screen.gold_shake_timer
    assert initial_shake == 0.15

    # 推进时间
    screen.update(0.1)

    # 验证粒子 lifetime 衰减
    new_particles = screen.effects_manager.particles
    # 粒子应存活（因为初始 lifetime 最小 0.4，减去 0.1 仍 > 0）
    assert len(new_particles) > 0, "粒子应仍然存活"
    for p in new_particles:
        assert p.lifetime < max_initial_lifetime, (
            f"粒子 lifetime 应衰减，得到 {p.lifetime}（初始最大 {max_initial_lifetime}）"
        )
        assert p.lifetime > 0, f"粒子应存活，得到 {p.lifetime}"

    # 验证 gold_shake_timer 递减（0.15 - 0.1 ≈ 0.05）
    assert abs(screen.gold_shake_timer - 0.05) < 1e-6, (
        f"gold_shake_timer 应递减为 ~0.05，得到 {screen.gold_shake_timer}"
    )

    print("[PASS] test_effects_update_decay")


def test_card_button_click_regions():
    """卡片 Buy 按钮的 collidepoint 应正确响应对应商品的购买。"""
    gm = _reset_game_manager()
    save_calls = []
    gm.save_manager.save = lambda p, s=None: (save_calls.append(1), True)[1]

    # 给予充裕金币
    gm.player_state.gold = 2000
    gm.player_state.bag_tier_index = 0
    gm.player_state.tools = {"pickaxe": 0, "dynamite": 0, "map": 0}
    gm.player_state.max_shields = 1
    gm.player_state.current_shields = 0

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    # 购买 shield（价格 75，能购买）
    btn_shield = _find_button_by_item_id(screen, "shield")
    assert btn_shield is not None and btn_shield.is_enabled, "shield 按钮应可用"

    # 模拟鼠标点击按钮中心
    click_pos = btn_shield.rect.center
    assert btn_shield.rect.collidepoint(click_pos), "按钮中心应在其 rect 内"

    initial_shields = gm.player_state.current_shields
    _click_button(screen, btn_shield)

    # 验证护盾满充
    assert gm.player_state.current_shields == gm.player_state.max_shields, (
        f"护盾应满充，得到 {gm.player_state.current_shields}/{gm.player_state.max_shields}"
    )
    # 验证金币减少
    assert gm.player_state.gold < 2000, "金币应减少"
    # 验证 save 被调用
    assert len(save_calls) == 1, f"save 应被调用 1 次，得到 {len(save_calls)} 次"

    print("[PASS] test_card_button_click_regions")


def test_render_no_crash():
    """render 应不抛异常（含特效存在时）。"""
    # 防御性恢复：应对前序测试可能已调用 pygame.quit()
    if not pygame.font.get_init():
        pygame.font.init()
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.NOFRAME)
    gm = _reset_game_manager()
    gm.save_manager.save = lambda p, s=None: True

    gm.player_state.gold = 1000
    gm.player_state.max_hearts = 3

    screen = MummyShopScreen()
    gm.screen_manager.register_screen(GameState.MUMMY_SHOP, screen)
    gm.screen_manager.switch_screen(GameState.MUMMY_SHOP, {"next_level": 3})

    # 购买以产生特效，然后尝试渲染（特效存在下）
    btn = _find_button_by_item_id(screen, "max_hearts")
    if btn is not None and btn.is_enabled:
        _click_button(screen, btn)

    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    # 这里应不抛异常
    screen.render(surface)

    print("[PASS] test_render_no_crash")


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        test_effects_manager_instantiated()
        test_card_rects_calculated()
        test_purchase_triggers_effects()
        test_effects_update_decay()
        test_card_button_click_regions()
        test_render_no_crash()

        print("\n=== ALL TESTS PASSED ===")
    finally:
        # 仅重置单例，不调用 pygame.quit()
        GameManager._instance = None
        AssetManager._instance = None
