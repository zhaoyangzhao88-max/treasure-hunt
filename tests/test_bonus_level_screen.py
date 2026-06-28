"""隐藏奖励关界面与挂起/恢复机制验证脚本 — Microsoft Treasure Hunt

Headless 模式下验证：
- GameplayScreen 的现场挂起与恢复（地图、关卡号、坐标、摄像机）
- BonusLevelScreen 的满血治疗与四叶草赋予
- BonusLevelScreen 的踩雷无伤退出

运行方式::

    python tests/test_bonus_level_screen.py
"""

import os
import sys

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Headless 模式：必须在 pygame.init() 之前设置
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from src.config import GameState
from src.player_state import PlayerState
from src.game_manager import GameManager
from src.screens.gameplay_screen import GameplayScreen
from src.screens.bonus_level_screen import BonusLevelScreen


# =============================================================================
# 桩替身
# =============================================================================

class FakeScreenManager:
    """最小 ScreenManager 桩 — 记录 switch_screen 调用，不执行实际跳转。"""
    def __init__(self):
        self.last_state = None
        self.last_payload = None
        self.current_screen = None

    def switch_screen(self, new_state, data_payload=None):
        self.last_state = new_state
        self.last_payload = data_payload


# =============================================================================
# 辅助函数
# =============================================================================

def _reset_gm():
    """重置 GameManager 单例为测试用干净状态。"""
    if not pygame.get_init():
        pygame.init()
    gm = GameManager.get_instance()
    gm.player_state = PlayerState()
    gm.screen_manager = FakeScreenManager()
    gm.suspended_level_state = None
    gm.asset_manager = None
    gm.save_manager = None
    return gm


# =============================================================================
# 测试 1：现场挂起与恢复
# =============================================================================

def test_suspend_and_resume():
    """GameplayScreen 能正确挂起主关卡现场，并在收到 resume 信号后完全恢复。"""
    _reset_gm()
    screen = GameplayScreen()

    # 初始化 GameplayScreen（以继续第 3 关的方式）
    screen.on_enter(data_payload={
        "continue": True,
        "highest_level_cleared": 3,
    })

    # 手动构造挂起状态（模拟踩中 STAIRS 后的 payload）
    gm = GameManager.get_instance()
    original_map = screen.game_map
    original_offset_x = screen.camera.offset_x
    original_offset_y = screen.camera.offset_y

    gm.suspended_level_state = {
        "game_map": original_map,
        "level_num": 3,
        "player_x": 2,
        "player_y": 3,
        "camera_offset_x": 100.0,
        "camera_offset_y": 50.0,
    }

    # 调用 on_enter 触发恢复
    screen.on_enter({"resume": True})

    # ---- 断言 ----
    assert screen.current_level_num == 3, (
        f"关卡号应为 3，得到 {screen.current_level_num}"
    )
    assert screen.interaction_controller.player_x == 2, (
        f"player_x 应为 2，得到 {screen.interaction_controller.player_x}"
    )
    assert screen.interaction_controller.player_y == 3, (
        f"player_y 应为 3，得到 {screen.interaction_controller.player_y}"
    )
    # 摄像机偏移精确恢复
    assert abs(screen.camera.offset_x - 100.0) < 1e-6, (
        f"camera.offset_x 应为 100.0，得到 {screen.camera.offset_x}"
    )
    assert abs(screen.camera.offset_y - 50.0) < 1e-6, (
        f"camera.offset_y 应为 50.0，得到 {screen.camera.offset_y}"
    )
    # 挂起区被安全清空
    assert gm.suspended_level_state is None, (
        "suspended_level_state 应在恢复后被清空"
    )
    # 地图引用一致
    assert screen.game_map is original_map, (
        "恢复后的 game_map 应与挂起时为同一对象"
    )

    print("[PASS] test_suspend_and_resume")


# =============================================================================
# 测试 2：满血治疗与四叶草赋予
# =============================================================================

def test_bonus_full_heal_and_clover():
    """BonusLevelScreen 进入时瞬间满血治疗，退出时正确赋予四叶草 Buff。"""
    gm = _reset_gm()
    gm.player_state.current_hearts = 1
    gm.player_state.max_hearts = 4

    screen = BonusLevelScreen()
    screen.on_enter()

    # ---- 断言：瞬间满血 ----
    assert gm.player_state.current_hearts == 4, (
        f"满血治疗应为 4 心，得到 {gm.player_state.current_hearts}"
    )

    # ---- 触发倒计时归零 ----
    screen.update(31.0)

    # ---- 断言：四叶草赋予 ----
    assert gm.player_state.has_clover is True, (
        "奖励关结束后玩家应拥有四叶草 Buff"
    )
    # 断言跳转参数正确
    assert gm.screen_manager.last_state == GameState.PLAYING, (
        f"应跳转至 PLAYING，得到 {gm.screen_manager.last_state}"
    )
    assert gm.screen_manager.last_payload == {"resume": True}, (
        f"跳转 payload 应为 {{'resume': True}}，得到 {gm.screen_manager.last_payload}"
    )

    print("[PASS] test_bonus_full_heal_and_clover")


# =============================================================================
# 测试 3：踩雷无伤退出
# =============================================================================

def test_bonus_trap_no_damage():
    """奖励关中踩中陷阱不扣血，立即结束并赋予四叶草。"""
    gm = _reset_gm()
    gm.player_state.max_hearts = 4
    gm.player_state.current_hearts = 4

    screen = BonusLevelScreen()
    screen.on_enter()

    # 在玩家右邻格 (1, 0) 放置隐蔽陷阱
    screen.game_map.traps[0][1] = True

    # 模拟按 → 键走入陷阱
    right_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RIGHT})
    screen.handle_event(right_event)

    # ---- 断言 ----
    # 奖励关应已结束
    assert screen.bonus_active is False, "踩雷后奖励关应结束"

    # 不扣血
    assert gm.player_state.current_hearts == 4, (
        f"踩雷不应扣血，应有 4 心，得到 {gm.player_state.current_hearts}"
    )

    # 四叶草仍被赋予
    assert gm.player_state.has_clover is True, (
        "踩雷退出后仍应获得四叶草 Buff"
    )

    # 跳转回 PLAYING
    assert gm.screen_manager.last_state == GameState.PLAYING, (
        f"应跳转至 PLAYING，得到 {gm.screen_manager.last_state}"
    )

    print("[PASS] test_bonus_trap_no_damage")


# =============================================================================
# 主入口
# =============================================================================

if __name__ == "__main__":
    test_suspend_and_resume()
    test_bonus_full_heal_and_clover()
    test_bonus_trap_no_damage()
    print("\n[ALL PASS] 全部 3 项测试通过！")
