"""第 48 课：即时成就解锁弹窗 + 音效联动机制 — 单元测试（Headless）

验证：
- 时序 X 轴 Lerp 三阶段位移（SLIDE_IN → STAY → SLIDE_OUT → FINISHED）
- 单次解锁防重播 + 持久化一致性（Atomic JSON）
- 跨场景顶层渲染安全（切换 current_screen 不死锁不崩溃）

使用临时目录隔离 save.json，避免污染项目真实存档。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

import pygame

# Headless 环境
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

# 把项目根加入 sys.path
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import pytest

from src.asset_manager import AssetManager
from src.config import SCREEN_HEIGHT, SCREEN_WIDTH, GameState
from src.game_manager import GameManager
from src.screens.base_screen import BaseScreen


# ---------------------------------------------------------------------------
# 测试脚手架
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_save_dir(tmp_path):
    """使用临时目录隔离存档。返回临时根目录。"""
    return tmp_path


class _MockSound:
    def __init__(self):
        self.play_count = 0

    def play(self, *a, **kw):
        self.play_count += 1


class _RecordingMainMenu(BaseScreen):
    """用于跨场景测试的 MAIN_MENU 模拟屏。"""

    def __init__(self):
        self.enter_payload = None

    def on_enter(self, data_payload=None):
        self.enter_payload = data_payload

    def on_exit(self):
        pass

    def handle_event(self, event):
        pass

    def update(self, dt):
        pass

    def render(self, surface):
        if surface is not None:
            surface.fill((0, 0, 0))


class _RecordingStats(BaseScreen):
    def __init__(self):
        self.enter_payload = None

    def on_enter(self, data_payload=None):
        self.enter_payload = data_payload

    def on_exit(self):
        pass

    def handle_event(self, event):
        pass

    def update(self, dt):
        pass

    def render(self, surface):
        if surface is not None:
            surface.fill((10, 10, 10))


@pytest.fixture
def gm(tmp_save_dir):
    """初始化 GameManager（Headless），临时目录隔离存档。"""
    # 注意：SaveManager 默认写 ./save.json；用 chdir 隔离
    os.chdir(tmp_save_dir)

    # 重置单例
    GameManager._instance = None
    AssetManager._instance = None

    pygame.init()
    try:
        pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME)
    except Exception:
        pass
    try:
        pygame.font.init()
    except Exception:
        pass
    try:
        pygame.mixer.init()
    except Exception:
        pass

    gm = GameManager.get_instance()
    gm.init_engine(headless=True)
    return gm


def _make_save_path(tmp_path, name="save.json"):
    return str(tmp_path / name)


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 测试 1：三阶段 Lerp 位移
# ---------------------------------------------------------------------------

def test_popup_x_slide_timing_and_state_machine(gm):
    """验证题目指定的三阶段 X 轴 Lerp 位移：

    - 初始 x=1024.0, state=SLIDE_IN
    - update(0.2) 后 704 < x < 1024，仍在滑入
    - update(0.3) 累计 0.5s >= 0.4 → state=STAY, x=704.0
    - update(3.1) → state=SLIDE_OUT
    - update(0.5) → state=FINISHED
    """
    from src.achievement_manager import AchievementPopup

    popup = AchievementPopup("Mummy Hunter", "GOLD")

    # T0 初始状态
    assert popup.x == 1024.0, f"初始 X 应为 1024.0，得到 {popup.x}"
    assert popup.state == "SLIDE_IN", f"初始状态应为 SLIDE_IN，得到 {popup.state}"

    # 推进到 0.2s（半程）
    popup.update(0.2)
    assert popup.state == "SLIDE_IN", f"0.2s 后仍在 SLIDE_IN，得到 {popup.state}"
    assert 704 < popup.x < 1024, f"滑入中 X 应在 (704,1024)，得到 {popup.x}"

    # 再推进 0.3s → 累计 0.5s >= 0.4
    popup.update(0.3)
    assert popup.state == "STAY", f"累计 0.5s 应转到 STAY，得到 {popup.state}"
    assert popup.x == 704.0, f"STAY 时 X 应卡在 704.0，得到 {popup.x}"

    # 再推进 3.1s
    popup.update(3.1)
    assert popup.state == "SLIDE_OUT", f"STAY 到期应转到 SLIDE_OUT，得到 {popup.state}"

    # 再推进 0.5s
    popup.update(0.5)
    assert popup.state == "FINISHED", f"SLIDE_OUT 到期应转到 FINISHED，得到 {popup.state}"


def test_popup_render_smoke_all_states(gm):
    """验证全状态调用 render() 不死锁、不抛异常。"""
    from src.achievement_manager import AchievementPopup

    popup = AchievementPopup("Gold Rush", "GOLD")
    states_seen = set()
    for _ in range(200):
        popup.update(0.1)
        popup.render(gm.screen)
        states_seen.add(popup.state)
        if popup.state == "FINISHED":
            break
    assert "FINISHED" in states_seen


def test_popup_tier_colors_render_without_crash(gm):
    """各段位（含未知/空值）均不崩溃。"""
    from src.achievement_manager import AchievementPopup

    for tier in ("BRONZE", "SILVER", "GOLD", "LOCKED", "", "UNKNOWN"):
        name = "Abyss Conqueror" if tier else ""
        popup = AchievementPopup(name, tier)
        popup.update(0.05)
        popup.render(gm.screen)


# ---------------------------------------------------------------------------
# 测试 2：单次解锁防重播 + 落盘一致性
# ---------------------------------------------------------------------------

def _assert_no_save_file(tmp_path):
    assert not (tmp_path / "save.json").exists(), "测试起始不应存在 save.json"


def test_single_unlock_anti_repeat_and_persistence(tmp_save_dir, gm):
    """模拟玩家累计 10 杀（mummy_hunter_bronze 阈值=10）：

    - 10 杀后 check_unlocks → active_popup 非空
    - unlocked_badges 写入 "mummy_hunter_bronze"
    - 落盘 JSON 中 player.unlocked_badges 包含该 ID
    - 再次 check_unlocks → active_popup 已被清空（FINISHED 后）否则绝不重复弹
    """
    from src.achievement_manager import AchievementManager


    # 重置状态
    gm.player_state.total_monsters_slain = 0
    gm.player_state.unlocked_badges = []
    gm.achievement_manager = AchievementManager(gm)

    # 模拟累计 10 杀后调用一次判定
    gm.player_state.total_monsters_slain = 10
    gm.achievement_manager.check_unlocks()

    # 应弹出且徽章被写入内存
    assert gm.achievement_manager.active_popup is not None, (
        "达成 mummy_hunter_bronze 时应弹出通知"
    )
    assert "mummy_hunter_bronze" in gm.player_state.unlocked_badges
    assert gm.achievement_manager.active_popup.state in {"SLIDE_IN", "STAY"}

    # 落盘一致性：save.json 中应包含该徽章
    save_path = _make_save_path(tmp_save_dir)
    assert os.path.exists(save_path), "落盘应已生成 save.json"
    saved = _read_json(save_path)
    assert "mummy_hunter_bronze" in saved["player"]["unlocked_badges"], (
        f"save.json 应记录徽章，实际为 {saved['player']['unlocked_badges']}"
    )

    # 再次调用 check_unlocks（达成后不重复弹）：先把弹窗走完，再验证 Not弹窗
    popup = gm.achievement_manager.active_popup
    while popup.state != "FINISHED":
        popup.update(0.2)
    gm.achievement_manager.update(0.0)  # 让管理器推进完成逻辑
    assert gm.achievement_manager.active_popup is None

    # 强制再 check 一次，绝对不会再弹
    gm.achievement_manager.check_unlocks()
    assert gm.achievement_manager.active_popup is None, (
        "同一徽章绝不允许重复弹窗"
    )


def test_gold_rush_silver_boundary(tmp_save_dir, gm):
    """Gold Rush 白银阈值 20000：
    - 19999 金未达成、20000 金刚刚好解锁
    """
    from src.achievement_manager import AchievementManager


    # 19999 金 —— 仅解锁青铜，不解锁白银
    gm.player_state.total_gold_earned = 19999
    gm.player_state.unlocked_badges = []
    am = AchievementManager(gm)
    am.check_unlocks()
    assert "gold_rush_bronze" in gm.player_state.unlocked_badges
    assert "gold_rush_silver" not in gm.player_state.unlocked_badges
    assert am.active_popup is not None

    # 清空弹窗把状态耗尽完成
    while am.active_popup.state != "FINISHED":
        am.active_popup.update(0.2)
    am.update(0.0)

    # 推进到 20000 金 —— 仅解锁白银
    gm.player_state.total_gold_earned = 20000
    am.check_unlocks()
    assert "gold_rush_silver" in gm.player_state.unlocked_badges
    assert am.active_popup is not None


def test_persistent_pioneer_gold_requires_80_runs(tmp_save_dir, gm):
    """Persistent Pioneer 黄金阈值=80。"""
    from src.achievement_manager import AchievementManager


    gm.player_state.total_runs = 79
    gm.player_state.unlocked_badges = []
    am = AchievementManager(gm)
    am.check_unlocks()
    assert "persistent_pioneer_bronze" in gm.player_state.unlocked_badges
    assert "persistent_pioneer_silver" in gm.player_state.unlocked_badges
    assert "persistent_pioneer_gold" not in gm.player_state.unlocked_badges

    while am.active_popup.state != "FINISHED":
        am.active_popup.update(0.2)
    am.update(0.0)

    gm.player_state.total_runs = 80
    am.check_unlocks()
    assert "persistent_pioneer_gold" in gm.player_state.unlocked_badges


# ---------------------------------------------------------------------------
# 测试 3：跨场景顶层渲染安全
# ---------------------------------------------------------------------------

def test_cross_screen_top_level_render_safety(gm, tmp_save_dir):
    """弹窗播放中切换 current_screen，状态机仍正常推进，渲染不死锁。"""
    from src.achievement_manager import AchievementPopup

    # 强制塞入一个弹窗
    gm.achievement_manager.active_popup = AchievementPopup("Gold Rush", "GOLD")

    # 注册模拟屏
    gm.screen_manager.register_screen(GameState.MAIN_MENU, _RecordingMainMenu())
    gm.screen_manager.register_screen(GameState.STATS, _RecordingStats())

    # 跑 3 帧（PLAYING）
    for _ in range(3):
        gm.achievement_manager.update(1 / 60)
        gm.achievement_manager.render(gm.screen)
        assert gm.achievement_manager.active_popup is not None

    # 切换到 STATS 再跑 3 帧
    gm.screen_manager.switch_screen(GameState.STATS)
    for _ in range(3):
        gm.achievement_manager.update(1 / 60)
        gm.achievement_manager.render(gm.screen)

    # 切换到 MAIN_MENU 跑完剩余帧直到 FINISHED
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)
    max_iter = 600  # 安全上限
    it = 0
    while gm.achievement_manager.active_popup is not None and it < max_iter:
        gm.achievement_manager.update(1 / 60)
        gm.achievement_manager.render(gm.screen)
        it += 1

    assert gm.achievement_manager.active_popup is None, (
        f"状态机应在跨场景切换后正常推进至 FINISHED（迭代 {it} 次）"
    )


def test_overlay_ahead_of_flip_in_run_loop(gm, tmp_save_dir):
    """验证 run() 主循环可驱动弹窗完整生命周期（不真实阻塞）。

    不真正进入 while running，而是回放 run() 关键步骤几帧。
    """
    from src.achievement_manager import AchievementPopup

    gm.achievement_manager.active_popup = AchievementPopup("Abyss Conqueror", "SILVER")

    # 模拟 run() 内的一段：每帧渲染顶层覆盖层
    max_iter = 600
    it = 0
    while gm.achievement_manager.active_popup is not None and it < max_iter:
        gm.achievement_manager.update(1 / 60)
        gm.achievement_manager.render(gm.screen)
        it += 1
        # 这里省略 pygame.display.flip()，因为 headless 已 NOFRAME
    assert it < max_iter


def test_silently_degrade_on_uninitialized_manager(gm, tmp_save_dir):
    """GameManager.achievement_manager 为 None 时，调用方不应崩溃。"""
    gm.achievement_manager = None

    class MockEvent:
        type = pygame.MOUSEBUTTONDOWN
        button = 1
        pos = (0, 0)

    # 模拟 injection 点保护逻辑
    try:
        if gm.achievement_manager is not None:
            gm.achievement_manager.check_unlocks()
    except Exception as e:
        pytest.fail(f"None 守卫应能保护，但抛出 {e}")


def test_silent_catch_up_for_returning_player(tmp_save_dir, gm):
    """init_engine 时静默回标老玩家已达成项，且不产生弹窗。

    写入一个已达成但未解锁的存档后，init_engine 后 unlocked_badges 应被回标，
    且不应产生 active_popup（因为全部已解锁）。"""
    from src.achievement_manager import AchievementManager

    # 手动构造一个存档
    save_path = _make_save_path(tmp_save_dir)
    payload = {
        "version": "1.0.0",
        "timestamp": 0.0,
        "player": {
            "max_hearts": 3,
            "current_hearts": 3,
            "max_shields_limit": 1,
            "current_shields": 0,
            "bag_tier_index": 0,
            "highest_level_cleared": 10,
            "total_runs": 0,
            "total_monsters_slain": 0,
            "total_gold_earned": 0,
            "gold": 0,
            "tools": {"pickaxe": 0, "dynamite": 0, "map": 0},
            "keys": {"RED": 0, "GREEN": 0, "BLUE": 0, "EXIT": 0},
            "has_amulet": False,
            "unlocked_badges": [],
        },
        "settings": {"sound_volume": 1.0, "music_volume": 1.0},
        "leaderboard": [],
        "checksum": "",
    }
    # 必须计算校验和
    from src.save_manager import SaveManager

    payload["checksum"] = SaveManager().calculate_checksum(payload)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 重新 Init
    GameManager._instance = None
    AssetManager._instance = None
    gm2 = GameManager.get_instance()
    gm2.init_engine(headless=True)

    # highest_level_cleared=10 应已静默达成 Abyss Conqueror 青铜 (5) 和白银 (15? 否，10<15)
    assert "abyss_conqueror_bronze" in gm2.player_state.unlocked_badges
    assert "abyss_conqueror_silver" not in gm2.player_state.unlocked_badges
    # 静默回标不应引起弹窗
    assert gm2.achievement_manager.active_popup is None


# ---------------------------------------------------------------------------
# 独立运行支持
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
