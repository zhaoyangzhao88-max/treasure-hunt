"""多存档插槽选择验证脚本 — Microsoft Treasure Hunt

第 46 课新增：
- SaveManager 槽位路径派生（slot_id / 向后兼容默认 / 自定义路径）
- get_all_slots_summary 空 / 部分占用扫描
- SaveSlotsScreen 路由（Back → MAIN_MENU；空槽 → PLAYING；占用槽 → MAIN_MENU）
- GameManager.bind_save_slot 重载玩家状态与设置
- 渲染无崩溃

轻量级 assert-based 测试，支持 `python tests/test_xxx.py` 单跑 / `python -m pytest` 批跑。
"""

import os
import sys

# 设置 headless 驱动必须在 pygame.init() 之前
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

# 确保能找到 src/ 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame

# 初始化 Pygame（display + font + mixer）— 仅初始化一次
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

from src.save_manager import SaveManager
from src.config import (
    MAX_SAVE_SLOTS,
    DEFAULT_SAVE_SLOT,
    GameState,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
)
from src.game_manager import GameManager
from src.asset_manager import AssetManager


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------

# 存档槽位默认存放在项目根目录（与 save.json 同目录），故测试直接以
# SaveManager(slot_id=...) 写入当前工作目录下的 save_slot_{id}.json，
# 并在每次测试后统一清理这些文件。
_SLOT_FILES = [f"save_slot_{i}.json" for i in range(1, 4)]
_SLOT_BAKS = [f + ".bak" for f in _SLOT_FILES]
_SLOT_TMP = [f + ".tmp" for f in _SLOT_FILES]


def _make_player(level=1, gold=100, runs=1):
    """构造一个最小可序列化的玩家数据字典。"""
    return {
        "max_hearts": 3,
        "current_hearts": 3,
        "max_shields_limit": 1,
        "current_shields": 0,
        "bag_tier_index": 0,
        "highest_level_cleared": level,
        "total_runs": runs,
        "total_monsters_slain": 0,
        "total_gold_earned": gold,
        "gold": 0,
        "tools": {"pickaxe": 0, "dynamite": 0, "map": 0},
        "keys": {"RED": 0, "GREEN": 0, "BLUE": 0, "EXIT": 0},
        "has_amulet": False,
    }


def _clean_all():
    """清理测试产生的全部槽位文件（当前工作目录）。"""
    for path in _SLOT_FILES + _SLOT_BAKS + _SLOT_TMP:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def _reset_game_manager():
    """重置 GameManager 单例并初始化引擎，返回 gm。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)
    return gm


class _SoundStub:
    def play(self, *a, **kw):
        pass


# --------------------------------------------------------------------------
# SaveManager 槽位路径派生
# --------------------------------------------------------------------------

def test_save_manager_slot_path_derivation():
    """slot_id=2 应派生出 save_slot_2.json 及对应 backup/temp 路径。"""
    sm = SaveManager(slot_id=2)
    assert sm.save_path == "save_slot_2.json", sm.save_path
    assert sm.backup_path == "save_slot_2.json.bak"
    assert sm.temp_path == "save_slot_2.json.tmp"
    print("[PASS] test_save_manager_slot_path_derivation")


def test_save_manager_backward_compat_default():
    """不传参应保持向后兼容，默认走 save.json。"""
    sm = SaveManager()
    assert sm.save_path == "save.json", sm.save_path
    assert sm.backup_path == "save.json.bak"
    assert sm.temp_path == "save.json.tmp"
    print("[PASS] test_save_manager_backward_compat_default")


def test_save_manager_custom_path_unchanged():
    """显式传 save_path 应直接使用，不受 slot_id 逻辑影响。"""
    sm = SaveManager(save_path="custom.json")
    assert sm.save_path == "custom.json"
    print("[PASS] test_save_manager_custom_path_unchanged")


# --------------------------------------------------------------------------
# get_all_slots_summary
# --------------------------------------------------------------------------

def test_get_all_slots_summary_partial():
    """写槽 1 与槽 3，留槽 2 空 → exists True/False/True，字段正确。"""
    _clean_all()
    try:
        sm1 = SaveManager(_SLOT_FILES[0])
        sm1.save(_make_player(level=5, gold=500, runs=3))

        sm3 = SaveManager(_SLOT_FILES[2])
        sm3.save(_make_player(level=10, gold=2000, runs=7))

        summary = SaveManager.get_all_slots_summary(MAX_SAVE_SLOTS)
        assert len(summary) == MAX_SAVE_SLOTS, len(summary)

        # 槽 1 已占用
        assert summary[0]["slot_id"] == 1
        assert summary[0]["exists"] is True
        assert summary[0]["level"] == 5
        assert summary[0]["gold"] == 500
        assert summary[0]["total_runs"] == 3

        # 槽 2 空（文件不存在）
        assert summary[1]["slot_id"] == 2
        assert summary[1]["exists"] is False
        assert summary[1]["level"] is None

        # 槽 3 已占用
        assert summary[2]["slot_id"] == 3
        assert summary[2]["exists"] is True
        assert summary[2]["level"] == 10
        assert summary[2]["gold"] == 2000
        assert summary[2]["total_runs"] == 7

        print("[PASS] test_get_all_slots_summary_partial")
    finally:
        _clean_all()


# --------------------------------------------------------------------------
# SaveSlotsScreen 路由与绑定
# --------------------------------------------------------------------------

def test_save_slots_screen_routes_to_main_menu():
    """点击 Back 按钮应切回 MAIN_MENU。"""
    _clean_all()
    gm = _reset_game_manager()
    try:
        from src.screens.save_slots_screen import SaveSlotsScreen

        screen = SaveSlotsScreen()
        gm.screen_manager.register_screen(GameState.SAVE_SLOT_SELECT, screen)
        gm.screen_manager.switch_screen(GameState.SAVE_SLOT_SELECT)

        screen.sound_hover = _SoundStub()
        screen.sound_click = _SoundStub()

        # 模拟点击 Back 按钮中心
        btn = screen.btn_back
        click = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": btn.rect.center},
        )
        screen.handle_event(click)

        assert gm.screen_manager.current_state == GameState.MAIN_MENU, (
            gm.screen_manager.current_state
        )
        print("[PASS] test_save_slots_screen_routes_to_main_menu")
    finally:
        _clean_all()


def test_save_slots_screen_click_empty_slot_binds_and_plays():
    """点击空槽应绑定该槽位并导航到 PLAYING 开新局。"""
    _clean_all()
    gm = _reset_game_manager()
    try:
        from src.screens.save_slots_screen import SaveSlotsScreen

        # 确保所有槽位为空（不写任何文件）
        screen = SaveSlotsScreen()
        gm.screen_manager.register_screen(GameState.SAVE_SLOT_SELECT, screen)
        gm.screen_manager.switch_screen(GameState.SAVE_SLOT_SELECT)

        # 点击第一个槽（空槽）
        rect = screen.slot_rects[0]
        click = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": rect.center},
        )
        screen.handle_event(click)

        # 验证：save_manager 已绑定到槽位 1
        assert gm.save_manager.save_path == "save_slot_1.json", (
            gm.save_manager.save_path
        )
        # 验证：导航到 PLAYING
        assert gm.screen_manager.current_state == GameState.PLAYING, (
            gm.screen_manager.current_state
        )
        print("[PASS] test_save_slots_screen_click_empty_slot_binds_and_plays")
    finally:
        _clean_all()


def test_save_slots_screen_click_occupied_slot_routes_to_main_menu():
    """预写槽 1，点击槽 1 → 绑定槽 1 且回 MAIN_MENU。"""
    _clean_all()
    gm = _reset_game_manager()
    try:
        # 预写槽 1
        sm = SaveManager(_SLOT_FILES[0])
        sm.save(_make_player(level=3, gold=300, runs=2))

        from src.screens.save_slots_screen import SaveSlotsScreen

        screen = SaveSlotsScreen()
        gm.screen_manager.register_screen(GameState.SAVE_SLOT_SELECT, screen)
        gm.screen_manager.switch_screen(GameState.SAVE_SLOT_SELECT)

        # 点击槽 1（已占用）
        rect = screen.slot_rects[0]
        click = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": rect.center},
        )
        screen.handle_event(click)

        assert gm.save_manager.save_path == "save_slot_1.json"
        assert gm.screen_manager.current_state == GameState.MAIN_MENU, (
            gm.screen_manager.current_state
        )
        print("[PASS] test_save_slots_screen_click_occupied_slot_routes_to_main_menu")
    finally:
        _clean_all()


def test_save_slots_screen_render_no_exception():
    """混合占用/空槽下 render 不应抛异常。"""
    _clean_all()
    gm = _reset_game_manager()
    try:
        # 槽 1 与槽 3 占用，槽 2 空
        SaveManager(_SLOT_FILES[0]).save(_make_player(level=2, gold=200, runs=1))
        SaveManager(_SLOT_FILES[2]).save(_make_player(level=8, gold=800, runs=5))

        from src.screens.save_slots_screen import SaveSlotsScreen

        screen = SaveSlotsScreen()
        gm.screen_manager.register_screen(GameState.SAVE_SLOT_SELECT, screen)
        gm.screen_manager.switch_screen(GameState.SAVE_SLOT_SELECT)

        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        screen.render(surface)  # 不应抛异常
        print("[PASS] test_save_slots_screen_render_no_exception")
    finally:
        _clean_all()


# --------------------------------------------------------------------------
# GameManager.bind_save_slot
# --------------------------------------------------------------------------

def test_game_manager_bind_save_slot():
    """写槽 3 后绑定，save_path 后缀与 player_state 字段应正确重载。"""
    _clean_all()
    gm = _reset_game_manager()
    try:
        sm = SaveManager(_SLOT_FILES[2])
        player = _make_player(level=15, gold=5000, runs=20)
        sm.save(player)

        gm.bind_save_slot(3)

        assert gm.save_manager.save_path.endswith("save_slot_3.json")
        assert gm.player_state.highest_level_cleared == 15
        assert gm.player_state.total_gold_earned == 5000
        assert gm.player_state.total_runs == 20
        print("[PASS] test_game_manager_bind_save_slot")
    finally:
        _clean_all()


def test_game_manager_bind_save_slot_reloads_settings():
    """绑定槽位后 settings_data 应同步。"""
    _clean_all()
    gm = _reset_game_manager()
    try:
        sm = SaveManager(_SLOT_FILES[1])
        sm.save(_make_player(), {"sound_volume": 0.5, "music_volume": 0.3})

        gm.bind_save_slot(2)

        assert gm.settings_data["sound_volume"] == 0.5
        assert gm.settings_data["music_volume"] == 0.3
        print("[PASS] test_game_manager_bind_save_slot_reloads_settings")
    finally:
        _clean_all()


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------

if __name__ == "__main__":
    test_save_manager_slot_path_derivation()
    test_save_manager_backward_compat_default()
    test_save_manager_custom_path_unchanged()
    test_get_all_slots_summary_partial()
    test_save_slots_screen_routes_to_main_menu()
    test_save_slots_screen_click_empty_slot_binds_and_plays()
    test_save_slots_screen_click_occupied_slot_routes_to_main_menu()
    test_save_slots_screen_render_no_exception()
    test_game_manager_bind_save_slot()
    test_game_manager_bind_save_slot_reloads_settings()
    print("\n[ALL PASS] 第 46 课 · 多存档插槽选择 — 全部测试通过")
