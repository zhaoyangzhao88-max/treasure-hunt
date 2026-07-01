"""排行榜 + 生涯统计联动集成测试 — Microsoft Treasure Hunt

第 43 课新增：
- 写入 Top 5 排序截断与落盘；
- 新游戏按钮 → total_runs 自增并持久化；
- 击杀怪物 → total_monsters_slain 自增；
- 无护身符 Game Over 彻底重置 → runs 回填 + leaderboard 登榜；
- StatsScreen 双分屏（左勋章右排行榜）渲染无崩溃。

轻量级 assert-based 测试，支持 `python tests/test_*.py` 单跑 / `python -m pytest` 批跑。
使用 SDL dummy 驱动避免弹出实体窗口。
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_pygame_ready = False


def _ensure_pygame():
    global _pygame_ready
    if _pygame_ready:
        return
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
    pygame.font.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass
    _pygame_ready = True


_TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")


def _temp_save_path(name):
    os.makedirs(_TEMP_DIR, exist_ok=True)
    return os.path.join(_TEMP_DIR, name)


def _clean_temp(name):
    base = _temp_save_path(name)
    for suffix in ("", ".bak", ".tmp"):
        try:
            os.remove(base + suffix)
        except FileNotFoundError:
            pass


class _SoundStub:
    def play(self, *a, **kw):
        pass


# --------------------------------------------------------------------------
# GameManager 测试会话共享单例
# --------------------------------------------------------------------------

_gm_session = {"gm": None}


def _get_session_game_manager():
    """跨测试用例共享同一个 GameManager，仅初始化一次。

    避免多次 `pygame.display.set_mode` 触发 "Out of memory"。
    """
    if _gm_session["gm"] is not None:
        return _gm_session["gm"]
    from src.game_manager import GameManager
    from src.asset_manager import AssetManager

    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)
    _gm_session["gm"] = gm
    return gm


def _reset_player_state(gm=None):
    gm = gm or _gm_session["gm"]
    ps = gm.player_state
    ps.gold = 0
    ps.current_hearts = 3
    ps.max_hearts = 3
    ps.current_shields = 0
    ps.max_shields = 1
    ps.tools = {"pickaxe": 0, "dynamite": 0, "map": 0}
    ps.keys = {"RED": 0, "GREEN": 0, "BLUE": 0, "EXIT": 0}
    ps.bag_tier_index = 0
    ps.has_amulet = False
    ps.has_machete = False
    ps.arrows = 0
    ps.highest_level_cleared = 0
    ps.total_gold_earned = 0
    ps.total_runs = 0
    ps.total_monsters_slain = 0


def _fresh_save_manager(path):
    from src.save_manager import SaveManager
    sm = SaveManager(path)
    sm.load()
    return sm


# --------------------------------------------------------------------------
# 测试：排行榜排序与截断
# --------------------------------------------------------------------------


def test_add_leaderboard_entry_top5_truncation():
    _ensure_pygame()
    from src.save_manager import SaveManager

    save_path = _temp_save_path("lb_trunc.json")
    _clean_temp("lb_trunc.json")
    try:
        sm = SaveManager(save_path)
        sm.load()

        scores = [100, 500, 200, 400, 300, 150, 50]
        for i, s in enumerate(scores):
            sm.add_leaderboard_entry(i + 1, s)

        lb = sm.load()["leaderboard"]
        top_gold = [e["gold_score"] for e in lb]
        assert len(lb) == 5, f"应严格截断 Top 5，实际长度 {len(lb)}"
        assert top_gold == [500, 400, 300, 200, 150], (
            f"Top 5 应严格降序，实际 {top_gold}"
        )
    finally:
        _clean_temp("lb_trunc.json")

    print("[PASS] test_add_leaderboard_entry_top5_truncation")


def test_add_leaderboard_entry_tie_breaker_by_level():
    _ensure_pygame()
    from src.save_manager import SaveManager

    save_path = _temp_save_path("lb_tie.json")
    _clean_temp("lb_tie.json")
    try:
        sm = SaveManager(save_path)
        sm.load()
        sm.add_leaderboard_entry(3, 1000)
        sm.add_leaderboard_entry(7, 1000)
        sm.add_leaderboard_entry(5, 1000)

        lb = sm.load()["leaderboard"]
        levels = [e["level_reached"] for e in lb]
        assert levels == [7, 5, 3], f"level_reached 降序排序异常，实际 {levels}"
    finally:
        _clean_temp("lb_tie.json")

    print("[PASS] test_add_leaderboard_entry_tie_breaker_by_level")


def test_add_leaderboard_entry_return_semantics():
    _ensure_pygame()
    from src.save_manager import SaveManager

    save_path = _temp_save_path("lb_return.json")
    _clean_temp("lb_return.json")
    try:
        sm = SaveManager(save_path)
        sm.load()
        for s in [500, 400, 300, 200, 150]:
            assert sm.add_leaderboard_entry(1, s) is True, "前 5 次高分入榜应返回 True"
        assert sm.add_leaderboard_entry(1, 50) is False, (
            "第 6 个低分未进 Top 5，应返回 False"
        )
    finally:
        _clean_temp("lb_return.json")

    print("[PASS] test_add_leaderboard_entry_return_semantics")


# --------------------------------------------------------------------------
# 测试：total_runs 新游戏自增
# --------------------------------------------------------------------------


def test_new_game_increments_total_runs():
    _ensure_pygame()
    from src.screens.main_menu_screen import MainMenuScreen
    from src.screens.base_screen import BaseScreen
    from src.config import GameState

    save_path = _temp_save_path("runs_newgame.json")
    _clean_temp("runs_newgame.json")
    try:
        gm = _get_session_game_manager()
        _reset_player_state(gm)
        gm.save_manager = _fresh_save_manager(save_path)

        screen = MainMenuScreen()
        gm.screen_manager.register_screen(GameState.MAIN_MENU, screen)

        class _MockPlaying(BaseScreen):
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
                pass

        mock_playing = _MockPlaying()
        gm.screen_manager.register_screen(GameState.PLAYING, mock_playing)
        gm.screen_manager.switch_screen(GameState.MAIN_MENU)

        screen.sound_click = _SoundStub()
        screen.sound_hover = _SoundStub()

        btn = screen.btn_new_game
        click_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": btn.rect.center},
        )
        screen.handle_event(click_event)

        assert gm.player_state.total_runs == 1, (
            f"total_runs 应自增为 1，实际 {gm.player_state.total_runs}"
        )

        reloaded = gm.save_manager.load()
        assert reloaded["player"]["total_runs"] == 1, (
            f"存档中 total_runs 应持久化为 1，实际 {reloaded['player']['total_runs']}"
        )
    finally:
        _clean_temp("runs_newgame.json")

    print("[PASS] test_new_game_increments_total_runs")


# --------------------------------------------------------------------------
# 测试：击杀怪物 → total_monsters_slain 自增
# --------------------------------------------------------------------------


def test_attack_monster_kill_increments_slain_machete():
    _ensure_pygame()
    from src.map_data import GameMap
    from src.player_state import PlayerState
    from src.interaction_controller import InteractionController

    m = GameMap(8, 8)
    player = PlayerState()
    player.has_machete = True
    ic = InteractionController(m, player, start_x=0, start_y=0)
    m.set_entity(1, 0, "MONSTER")

    result = ic.attack_monster(1, 0)
    assert result is True, "柴刀击杀应返回 True"
    assert player.total_monsters_slain == 1, (
        f"击杀后 total_monsters_slain 应为 1，实际 {player.total_monsters_slain}"
    )
    print("[PASS] test_attack_monster_kill_increments_slain_machete")


def test_attack_monster_kill_increments_slain_bow():
    _ensure_pygame()
    from src.map_data import GameMap
    from src.player_state import PlayerState
    from src.interaction_controller import InteractionController

    m = GameMap(8, 8)
    player = PlayerState()
    player.has_machete = False
    player.arrows = 2
    ic = InteractionController(m, player, start_x=0, start_y=0)
    m.set_entity(1, 0, "MONSTER")

    result = ic.attack_monster(1, 0)
    assert result is True
    assert player.total_monsters_slain == 1, (
        f"弓箭击杀后 total_monsters_slain 应为 1，实际 {player.total_monsters_slain}"
    )
    assert player.arrows == 1, f"弓箭消耗后应余 1，实际 {player.arrows}"
    print("[PASS] test_attack_monster_kill_increments_slain_bow")


def test_attack_active_mummy_kill_increments_slain():
    _ensure_pygame()
    from src.map_data import GameMap
    from src.player_state import PlayerState
    from src.interaction_controller import InteractionController

    m = GameMap(8, 8)
    player = PlayerState()
    player.has_machete = True
    ic = InteractionController(m, player, start_x=0, start_y=0)

    class _FakeMummy:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    mummy = _FakeMummy(1, 0)
    ic.active_mummies.append(mummy)
    m.set_entity(1, 0, "ACTIVE_MUMMY")

    result = ic.attack_active_mummy(1, 0)
    assert result is True, "柴刀击杀活性木乃伊应返回 True"
    assert player.total_monsters_slain == 1, (
        f"击杀后 total_monsters_slain 应为 1，实际 {player.total_monsters_slain}"
    )
    assert mummy not in ic.active_mummies, "活性木乃伊应从活跃列表中移除"
    print("[PASS] test_attack_active_mummy_kill_increments_slain")


# --------------------------------------------------------------------------
# 测试：彻底 Game Over 重置回填 runs + 写入排行榜
# --------------------------------------------------------------------------


def test_full_reset_grows_leaderboard():
    _ensure_pygame()
    from src.screens.game_over_screen import GameOverScreen
    from src.screens.base_screen import BaseScreen
    from src.config import GameState

    save_path = _temp_save_path("go_leader.json")
    _clean_temp("go_leader.json")
    try:
        gm = _get_session_game_manager()
        _reset_player_state(gm)
        gm.save_manager = _fresh_save_manager(save_path)

        screen = GameOverScreen()
        gm.screen_manager.register_screen(GameState.GAME_OVER, screen)

        class _DummyTarget(BaseScreen):
            def __init__(self):
                self.payload = None

            def on_enter(self, data_payload=None):
                self.payload = data_payload

            def on_exit(self):
                pass

            def handle_event(self, event):
                pass

            def update(self, dt):
                pass

            def render(self, surface):
                pass

        target = _DummyTarget()
        gm.screen_manager.register_screen(GameState.PLAYING, target)
        gm.screen_manager.switch_screen(
            GameState.GAME_OVER,
            data_payload={"current_level": 7},
        )

        player = gm.player_state
        player.total_gold_earned = 1234
        player.has_amulet = False
        player.total_runs = 3

        screen._trigger_roguelite_reset(screen.game_manager.player_state)

        assert player.total_runs == 4, (
            f"重置后 total_runs 应为 4，实际 {player.total_runs}"
        )

        lb = gm.save_manager.load()["leaderboard"]
        assert len(lb) >= 1, f"leaderboard 应有新增条目，实际为空 {lb}"
        newest = lb[0]
        assert newest["level_reached"] == 7, (
            f"最新条目 level_reached 应为 7，实际 {newest['level_reached']}"
        )
        assert newest["gold_score"] == 1234, (
            f"最新条目 gold_score 应为 1234，实际 {newest['gold_score']}"
        )
    finally:
        _clean_temp("go_leader.json")

    print("[PASS] test_full_reset_grows_leaderboard")


# --------------------------------------------------------------------------
# 测试：StatsScreen 双分屏渲染无崩溃
# --------------------------------------------------------------------------


def test_stats_screen_render_with_leaderboard():
    _ensure_pygame()
    from src.screens.stats_screen import StatsScreen
    from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT

    save_path = _temp_save_path("stats_render.json")
    _clean_temp("stats_render.json")
    try:
        gm = _get_session_game_manager()
        _reset_player_state(gm)
        gm.save_manager = _fresh_save_manager(save_path)

        pg = gm.player_state
        pg.total_gold_earned = 99999
        pg.total_monsters_slain = 300
        pg.total_runs = 100
        pg.highest_level_cleared = 50

        gm.save_manager.add_leaderboard_entry(7, 7777)
        gm.save_manager.add_leaderboard_entry(3, 3333)
        gm.save_manager.add_leaderboard_entry(12, 12000)

        screen = StatsScreen()
        gm.screen_manager.register_screen(GameState.STATS, screen)
        gm.screen_manager.switch_screen(GameState.STATS)

        assert len(screen.achievement_results) == 4
        assert isinstance(screen.leaderboard, list)
        assert len(screen.leaderboard) >= 3

        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        screen.render(surface)
    finally:
        _clean_temp("stats_render.json")

    print("[PASS] test_stats_screen_render_with_leaderboard")


def test_stats_screen_render_empty_leaderboard():
    _ensure_pygame()
    from src.screens.stats_screen import StatsScreen
    from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT

    save_path = _temp_save_path("stats_empty.json")
    _clean_temp("stats_empty.json")
    try:
        gm = _get_session_game_manager()
        _reset_player_state(gm)
        gm.save_manager = _fresh_save_manager(save_path)

        screen = StatsScreen()
        gm.screen_manager.register_screen(GameState.STATS, screen)
        gm.screen_manager.switch_screen(GameState.STATS)

        assert screen.leaderboard == []

        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        screen.render(surface)
    finally:
        _clean_temp("stats_empty.json")

    print("[PASS] test_stats_screen_render_empty_leaderboard")


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------


if __name__ == "__main__":
    test_add_leaderboard_entry_top5_truncation()
    test_add_leaderboard_entry_tie_breaker_by_level()
    test_add_leaderboard_entry_return_semantics()
    test_new_game_increments_total_runs()
    test_attack_monster_kill_increments_slain_machete()
    test_attack_monster_kill_increments_slain_bow()
    test_attack_active_mummy_kill_increments_slain()
    test_full_reset_grows_leaderboard()
    test_stats_screen_render_with_leaderboard()
    test_stats_screen_render_empty_leaderboard()
    print("\n[ALL PASS] 第 43 课 · 排行榜 + 生涯统计 — 全部集成测试通过")
