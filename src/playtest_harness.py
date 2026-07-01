"""全自动 AI 仿真探险测试沙盒 — Microsoft Treasure Hunt

提供 PlaytestHarness 类，用于无人干预的全自动场景流转测试：
自动驱动主菜单 → AI 探索 → 关卡结算 → 商店购买 → 死亡重置 的全流程循环。

使用方式::

    from src.playtest_harness import PlaytestHarness
    harness = PlaytestHarness(game_manager, max_levels=5)
    result = harness.step_simulation()  # 单步仿真
"""

import pygame

from src.config import GameState


class PlaytestHarness:
    """全自动仿真引擎 — 轮询当前场景并驱动 AI 自动操作。

    通过 step_simulation() 单步推进，根据当前游戏场景自动决策：
    - MAIN_MENU → 模拟点击"开始新游戏"
    - PLAYING → 调用 AI 求解器执行一步
    - LEVEL_COMPLETE → 模拟点击"继续下一关"
    - MUMMY_SHOP → 自动购买物资后离开
    - GAME_OVER → 有护身符复活，无则 Rogue-lite 重置

    Attributes:
        gm: GameManager 单例引用
        max_levels: 最大通关关卡数（达标后退出）
        levels_completed: 已通关卡数累计
        runs_played: 游戏总局数累计
        crashes_detected: 检测到的崩溃次数
        total_gold_collected: 全程累计金币
    """

    def __init__(self, game_manager, max_levels: int = 5):
        """初始化仿真引擎。

        Args:
            game_manager: GameManager 单例实例
            max_levels: 最大通关关卡数，默认 5
        """
        self.gm = game_manager
        self.max_levels = max_levels
        self.levels_completed: int = 0
        self.runs_played: int = 0
        self.crashes_detected: int = 0
        self.total_gold_collected: int = 0
        self._last_level_gold: int = 0

    # =========================================================================
    # 主仿真入口
    # =========================================================================

    def step_simulation(self) -> str:
        """执行一步仿真，根据当前场景自动决策。

        Returns:
            描述本次操作结果的字符串标识：
            - "START_NEW_GAME"   — 从主菜单开始了新游戏
            - "EXPLORING"        — AI 正在探索中
            - "LEVEL_COMPLETED"  — 关卡通关，结算中
            - "SHOPPING"         — 商店购物完毕
            - "DIED_REVIVED"     — 护身符复活
            - "DIED"             — 死亡重置
            - "INIT"             — 初始状态切换至主菜单
            - "UNKNOWN_STATE"    — 未识别状态
            - "MAIN_MENU_BLOCKED" — 主菜单按钮不可用
            - "LEVEL_COMPLETE_BLOCKED" — 结算按钮不可用
        """
        cur_state = self.gm.screen_manager.current_state

        # 初始状态（None）：先切到主菜单
        if cur_state is None:
            self.gm.screen_manager.switch_screen(GameState.MAIN_MENU)
            return "INIT"

        if cur_state == GameState.MAIN_MENU:
            return self._handle_main_menu()
        elif cur_state == GameState.PLAYING:
            return self._handle_playing()
        elif cur_state == GameState.LEVEL_COMPLETE:
            return self._handle_level_complete()
        elif cur_state == GameState.MUMMY_SHOP:
            return self._handle_mummy_shop()
        elif cur_state == GameState.GAME_OVER:
            return self._handle_game_over()

        return "UNKNOWN_STATE"

    # =========================================================================
    # 场景处理器
    # =========================================================================

    def _handle_main_menu(self) -> str:
        """主菜单 → 模拟点击"开始新游戏"。"""
        screen = self.gm.screen_manager.current_screen
        btn = getattr(screen, "btn_new_game", None)
        if btn is not None and btn.is_enabled:
            click_event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": btn.rect.center},
            )
            screen.handle_event(click_event)
            self.runs_played += 1
            return "START_NEW_GAME"
        return "MAIN_MENU_BLOCKED"

    def _handle_playing(self) -> str:
        """游戏探索中 → AI 自动决策并执行一步，手动推进帧逻辑。"""
        screen = self.gm.screen_manager.current_screen

        # 检查 AI 求解器
        ai_solver = getattr(screen, "ai_solver", None)
        if ai_solver is None:
            return "NO_SOLVER"

        ctrl = getattr(screen, "interaction_controller", None)
        if ctrl is None:
            return "NO_CTRL"

        # 记录进入关卡时的金币基数（仅首次）
        if self._last_level_gold == 0:
            self._last_level_gold = self.gm.player_state.gold

        # AI 决策 + 执行
        action = ai_solver.think_next_action(ctrl.player_x, ctrl.player_y)
        screen._execute_ai_action(action)

        # 手动推进帧逻辑（粒子、动画、摄像机等）
        screen.update(0.1)

        return "EXPLORING"

    def _handle_level_complete(self) -> str:
        """关卡结算 → 获取结算数据 → 模拟点击"继续下一关"。"""
        screen = self.gm.screen_manager.current_screen

        # 采集本关金币收益
        if hasattr(screen, "gold_earned"):
            level_gold = screen.gold_earned
            self.total_gold_collected += level_gold

        self.levels_completed += 1

        btn = getattr(screen, "btn_next_level", None)
        if btn is not None and btn.is_enabled:
            click_event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": btn.rect.center},
            )
            screen.handle_event(click_event)
            return "LEVEL_COMPLETED"
        return "LEVEL_COMPLETE_BLOCKED"

    def _handle_mummy_shop(self) -> str:
        """商店 → AI 自动买爆 → 点击"离开商店"。"""
        screen = self.gm.screen_manager.current_screen

        # 自动购物
        self._auto_buy_items(screen)

        # 点击"离开商店"
        for btn in getattr(screen, "buttons", []):
            if getattr(btn, "item_id", None) == "leave" and btn.is_enabled:
                click_event = pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    {"button": 1, "pos": btn.rect.center},
                )
                screen.handle_event(click_event)
                return "SHOPPING"

        return "SHOPPING_NO_LEAVE"

    def _auto_buy_items(self, shop_screen):
        """AI 自动购买策略：铁锹 → 炸药 → 护盾。

        Args:
            shop_screen: MummyShopScreen 实例
        """
        ps = self.gm.player_state

        # 1) 买铁锹：金币 >= 50 且背包未满
        if ps.gold >= 50 and ps.total_tools() < ps.max_capacity():
            shop_screen._buy_item("pickaxe")

        # 2) 买炸药：金币 >= 75 且背包未满
        if ps.gold >= 75 and ps.total_tools() < ps.max_capacity():
            shop_screen._buy_item("dynamite")

        # 3) 买护盾：金币 >= 75 且护盾未满
        if ps.gold >= 75 and ps.current_shields < ps.max_shields:
            shop_screen._buy_item("shield")

    def _handle_game_over(self) -> str:
        """死亡结算 → 有护身符复活 / 无则 Rogue-lite 重置。"""
        screen = self.gm.screen_manager.current_screen
        ps = self.gm.player_state

        if ps.has_amulet:
            # 消耗护身符复活（内部调用时空溯源 + 切至 MUMMY_SHOP）
            screen._handle_revive()
            return "DIED_REVIVED"
        else:
            # Rogue-lite 重置回 Level 1
            screen._handle_restart()
            return "DIED"
