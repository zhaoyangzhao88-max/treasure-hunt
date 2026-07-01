"""死亡结算界面 — Microsoft Treasure Hunt

玩家死亡后展示的结算场景：
- 有护身符：消耗护身符复活，回到上一个商店，清空消耗品
- 无护身符：Rogue-lite 重置，保留永久升级，金币/工具/关卡归零
- 自动安全落盘，确保永久属性不丢失
"""

import os as _os
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from src.screens.base_screen import BaseScreen
from src.ui_helpers import Button
from src.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    GameState,
    WHITE,
    BLACK,
    RED,
    GRAY,
    YELLOW,
    DARK_GREEN,
    GOLD,
)


# =============================================================================
# 颜色常量
# =============================================================================

_COLOR_BG = (15, 23, 42)           # 深蓝黑背景
_COLOR_TITLE = (255, 0, 0)         # 红色大标题
_COLOR_AMULET_TEXT = (255, 255, 100)  # 有护身符说明 - 淡黄色
_COLOR_NO_AMULET_TEXT = (128, 128, 128)  # 无护身符说明 - 灰色


# =============================================================================
# 死亡结算场景
# =============================================================================

class GameOverScreen(BaseScreen):
    """死亡结算界面 — 有护身符复活 / 无护身符 Rogue-lite 重置。

    生命周期：
    - on_enter: 解析死亡关卡 → 根据有无护身符构建按钮组 → 加载死亡音乐
    - handle_event: 鼠标悬停 + 点击判定
    - update: no-op
    - render: 深蓝背景 + 标题 + 说明文字 + 按钮
    """

    def __init__(self):
        """初始化死亡界面（不含资源加载 — 由 on_enter 负责）。"""
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None

        self.current_level: int = 2
        self.has_amulet: bool = False

        self.buttons: list[Button] = []
        self.font_title = None
        self.font_info = None
        self.sound_click = None

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_enter(self, data_payload: dict = None):
        """进入死亡界面 — 解析数据载荷、构建按钮组、加载音效。

        Args:
            data_payload: 前一屏幕传入的数据。
                若包含 current_level: int，代表玩家死亡时所在的关卡。
        """
        from src.game_manager import GameManager

        # None guard
        data_payload = data_payload or {}

        self.game_manager = GameManager.get_instance()
        self.screen_manager = self.game_manager.screen_manager
        self.asset_manager = self.game_manager.asset_manager

        # ---- 解析数据载荷 ----
        self.current_level = data_payload.get("current_level", 2)

        # ---- 获取全局玩家状态 ----
        player = self.game_manager.player_state
        self.has_amulet = player.has_amulet

        # ---- 初始化字体 ----
        self.font_title = self.asset_manager.get_font("default", 72)
        self.font_info = self.asset_manager.get_font("default", 28)

        # ---- 构建按钮组 ----
        center_x = SCREEN_WIDTH // 2
        btn_width = 360
        btn_height = 52

        if self.has_amulet:
            # 有护身符：复活 + 不复活重头开始
            self.btn_revive = Button(
                text="消耗护身符复活 (Consume Amulet & Revive)",
                center_pos=(center_x, 420),
                width=btn_width,
                height=btn_height,
                font=self.font_info,
                normal_color=DARK_GREEN,
                hover_color=GOLD,
                text_color=WHITE,
            )
            self.btn_revive.action = "revive"

            self.btn_no_revive = Button(
                text="不复活，重头开始 (Don't Revive, Restart)",
                center_pos=(center_x, 500),
                width=btn_width,
                height=btn_height,
                font=self.font_info,
                normal_color=DARK_GREEN,
                hover_color=GOLD,
                text_color=WHITE,
            )
            self.btn_no_revive.action = "no_revive"

            self.buttons = [self.btn_revive, self.btn_no_revive]
        else:
            # 无护身符：重整旗鼓 + 返回主菜单
            self.btn_restart = Button(
                text="重整旗鼓 (Restart from Level 1)",
                center_pos=(center_x, 420),
                width=btn_width,
                height=btn_height,
                font=self.font_info,
                normal_color=DARK_GREEN,
                hover_color=GOLD,
                text_color=WHITE,
            )
            self.btn_restart.action = "restart"

            self.btn_exit = Button(
                text="返回主菜单 (Exit to Main Menu)",
                center_pos=(center_x, 500),
                width=btn_width,
                height=btn_height,
                font=self.font_info,
                normal_color=DARK_GREEN,
                hover_color=GOLD,
                text_color=WHITE,
            )
            self.btn_exit.action = "exit_menu"

            self.buttons = [self.btn_restart, self.btn_exit]

        # ---- 预载音效 ----
        self.sound_click = self.asset_manager.get_sound("click.wav")

        # ---- 启动死亡界面背景音乐 ----
        from src.audio_manager import AudioManager
        AudioManager.get_instance().play_bgm("gameover_bgm.ogg")

    def on_exit(self):
        """离开死亡界面时释放临时引用。"""
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None
        self.buttons = []
        self.font_title = None
        self.font_info = None
        self.sound_click = None

    # =========================================================================
    # 事件处理
    # =========================================================================

    def handle_event(self, event: pygame.event.Event):
        """分发鼠标事件：悬停检测 + 点击处理。"""
        if event.type == pygame.MOUSEMOTION:
            for button in self.buttons:
                button.update(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if not button.is_enabled:
                    continue
                if not button.rect.collidepoint(event.pos):
                    continue

                action = getattr(button, "action", None)

                if action == "revive":
                    self._handle_revive()
                elif action == "no_revive":
                    self._handle_no_revive()
                elif action == "restart":
                    self._handle_restart()
                elif action == "exit_menu":
                    self._handle_exit_menu()

    # =========================================================================
    # 按钮响应
    # =========================================================================

    def _handle_revive(self):
        """消耗护身符复活：满血、清空消耗品、时空溯源、跳转商店。"""
        if self.sound_click is not None:
            self.sound_click.play()

        player = self.game_manager.player_state

        # 1) 消耗护身符
        player.has_amulet = False
        player.amulets_count += 1

        # 2) 满血治疗
        player.current_hearts = player.max_hearts

        # 3) 罚没装备（清空临时道具与消耗品）
        # 说明：PlayerState.tools 使用字典键 "pickaxe"/"dynamite"/"map"
        player.tools["pickaxe"] = 0
        player.tools["dynamite"] = 0
        player.tools["map"] = 0
        player.purge_temporary_items()

        # 4) 时空溯源算法计算
        next_level = self._calculate_respawn_level(self.current_level)

        # 5) 自动安全落盘
        self.game_manager.save_manager.save(
            self._build_player_dict(player),
            {
                "sound_volume": 1.0,
                "music_volume": 1.0,
            },
        )

        # 6) 跳转至 MUMMY_SHOP
        self.screen_manager.switch_screen(
            GameState.MUMMY_SHOP,
            data_payload={"next_level": next_level},
        )

    def _handle_no_revive(self):
        """不复活，重头开始：Rogue-lite 重置，跳转 PLAYING 关卡 1。"""
        if self.sound_click is not None:
            self.sound_click.play()

        player = self.game_manager.player_state
        self._trigger_roguelite_reset(player)

        self.screen_manager.switch_screen(
            GameState.PLAYING,
            data_payload={"level_num": 1, "continue": False},
        )

    def _handle_restart(self):
        """重整旗鼓：Rogue-lite 重置，跳转 PLAYING 关卡 1。"""
        if self.sound_click is not None:
            self.sound_click.play()

        player = self.game_manager.player_state
        self._trigger_roguelite_reset(player)

        self.screen_manager.switch_screen(
            GameState.PLAYING,
            data_payload={"level_num": 1, "continue": False},
        )

    def _handle_exit_menu(self):
        """返回主菜单：Rogue-lite 重置，跳转 MAIN_MENU。"""
        if self.sound_click is not None:
            self.sound_click.play()

        player = self.game_manager.player_state
        self._trigger_roguelite_reset(player)

        self.screen_manager.switch_screen(GameState.MAIN_MENU)

    # =========================================================================
    # Rogue-lite 重置
    # =========================================================================

    def _trigger_roguelite_reset(self, player):
        """触发全局 Rogue-lite 重置：保留永久升级，重置其他所有属性。

        Args:
            player: 全局 PlayerState 实例
        """
        # 1) 保留永久升级属性 + 生涯统计 + 成就记录
        saved_max_hearts = player.max_hearts
        saved_bag_tier = player.bag_tier_index
        saved_runs = player.total_runs
        saved_gold_earned = player.total_gold_earned
        saved_badges = list(getattr(player, "unlocked_badges", []) or [])

        # 2) 全局重置
        player.__init__()

        # 3) 回填永久属性 + 生涯统计 + 成就记录（新一局 +1 计入探险次数）
        player.max_hearts = saved_max_hearts
        player.current_hearts = saved_max_hearts
        player.bag_tier_index = saved_bag_tier
        player.total_runs = saved_runs + 1
        player.total_gold_earned = saved_gold_earned
        player.unlocked_badges = saved_badges

        # 4) 自动落盘保存
        self.game_manager.save_manager.save(
            self._build_player_dict(player),
            {
                "sound_volume": 1.0,
                "music_volume": 1.0,
            },
        )

        # 成就评估（runs 可能解锁 Persistent Pioneer）
        try:
            am = self.game_manager.achievement_manager
            if am is not None:
                am.check_unlocks()
        except Exception:
            pass

        # 5) 彻底死亡（无护身符）：把本局战绩登入本地 Top 5 排行榜
        self.game_manager.save_manager.add_leaderboard_entry(
            self.current_level,
            player.total_gold_earned,
        )

    # =========================================================================
    # 时空溯源算法
    # =========================================================================

    @staticmethod
    def _calculate_respawn_level(death_level: int) -> int:
        """计算复活后应进入的关卡数。

        算法：
        - 若死亡关卡 L <= 6，shop_completed_level = 1
        - 否则，shop_completed_level = ((L - 2) // 5) * 5
        - 下一个目标关卡 = shop_completed_level + 1

        Args:
            death_level: 玩家死亡时所在的关卡数

        Returns:
            复活后应进入的关卡数
        """
        if death_level <= 6:
            shop_completed_level = 1
        else:
            shop_completed_level = ((death_level - 2) // 5) * 5
        return shop_completed_level + 1

    # =========================================================================
    # 帧循环
    # =========================================================================

    def update(self, dt: float):
        """死亡界面无帧间逻辑，no-op。"""
        pass

    def render(self, surface: pygame.Surface):
        """画面绘制 — 深蓝背景 + 标题 + 说明文字 + 按钮。"""
        # ---- 背景填充 ----
        surface.fill(_COLOR_BG)

        center_x = SCREEN_WIDTH // 2

        # ---- 大标题 ----
        if self.font_title is not None:
            title_surf = self.font_title.render("GAME OVER", True, _COLOR_TITLE)
            title_rect = title_surf.get_rect(center=(center_x, 120))
            surface.blit(title_surf, title_rect)

        # ---- 说明文字 ----
        if self.font_info is not None:
            if self.has_amulet:
                desc = "Amulet of Rebirth is active! You can return to the last shop."
                desc_color = _COLOR_AMULET_TEXT
            else:
                desc = "You have fallen. Progress reset, but permanent upgrades are preserved."
                desc_color = _COLOR_NO_AMULET_TEXT

            desc_surf = self.font_info.render(desc, True, desc_color)
            desc_rect = desc_surf.get_rect(center=(center_x, 220))
            surface.blit(desc_surf, desc_rect)

            # 死亡关卡信息
            death_info = f"You died at Level {self.current_level}"
            death_surf = self.font_info.render(death_info, True, GRAY)
            death_rect = death_surf.get_rect(center=(center_x, 270))
            surface.blit(death_surf, death_rect)

        # ---- 按钮 ----
        for button in self.buttons:
            button.render(surface)

    # =========================================================================
    # 内部辅助
    # =========================================================================

    @staticmethod
    def _build_player_dict(ps) -> dict:
        """将 PlayerState 序列化为 SaveManager 期望的 player 字典格式。

        Args:
            ps: PlayerState 实例

        Returns:
            序列化后的 player 数据字典
        """
        return {
            "max_hearts": ps.max_hearts,
            "current_hearts": ps.current_hearts,
            "max_shields_limit": ps.max_shields,
            "current_shields": ps.current_shields,
            "bag_tier_index": ps.bag_tier_index,
            "highest_level_cleared": ps.highest_level_cleared,
            "total_runs": ps.total_runs,
            "total_monsters_slain": ps.total_monsters_slain,
            "total_gold_earned": ps.total_gold_earned,
            "gold": ps.gold,
            "tools": dict(ps.tools),
            "keys": dict(ps.keys),
            "has_amulet": ps.has_amulet,
            "unlocked_badges": list(getattr(ps, "unlocked_badges", []) or []),
        }
