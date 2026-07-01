"""隐藏奖励关界面 — Microsoft Treasure Hunt

纯收益场景：玩家在 30 秒倒计时内于 8×8 地图上收集金币/宝石，
踩中陷阱不扣血但立即退出，结束后回到主关卡并获得幸运四叶草 Buff。

使用方式::

    screen = BonusLevelScreen()
    screen.on_enter()
    # 在主循环中：
    screen.handle_event(event)
    screen.update(dt)
    screen.render(surface)
"""

import os as _os
import sys as _sys
import random

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from src.screens.base_screen import BaseScreen
from src.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    HUD_HEIGHT,
    YELLOW,
    GameState,
)
from src.map_data import GameMap
from src.interaction_controller import InteractionController
from src.tile_renderer import TileRenderer
from src.help_overlay import HelpOverlay
from src.minimap import Minimap


# =============================================================================
# 常量
# =============================================================================

BONUS_MAP_SIZE = 8          # 8×8 奖励地图
BONUS_TIMER = 30.0          # 30 秒倒计时
BONUS_BG_COLOR = (28, 25, 23)   # 深金色背景
BONUS_COIN_COUNT = 8        # COIN 散落数量
BONUS_GEM_COUNT = 2         # GEM 散落数量
BONUS_TRAP_COUNT = 3        # 陷阱数量


class BonusLevelScreen(BaseScreen):
    """隐藏奖励关场景 — 30 秒倒计时金币收集 + 陷阱无伤退场。"""

    def __init__(self):
        self.game_manager = None
        self.screen_manager = None

        self.game_map: GameMap | None = None
        self.interaction_controller: InteractionController | None = None

        self.timer: float = BONUS_TIMER
        self.player_x: int = 0
        self.player_y: int = 0
        self.bonus_active: bool = False

        # 玩法指南蒙层（默认关闭）
        self.show_help: bool = False
        self.help_overlay: HelpOverlay | None = None

        # 实时小地图（默认关闭，Tab 开启）
        self.show_minimap: bool = False
        self.minimap: Minimap | None = None

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_enter(self, data_payload: dict = None):
        """进入奖励关 — 满血治疗、生成 8×8 地图、启动倒计时。"""
        from src.game_manager import GameManager

        self.game_manager = GameManager.get_instance()
        self.screen_manager = self.game_manager.screen_manager
        player = self.game_manager.player_state

        # 1) 瞬间满血治疗
        player.current_hearts = player.max_hearts

        # 2) 重置倒计时状态
        self.timer = BONUS_TIMER
        self.bonus_active = True

        # 3) 生成 8×8 全 UNCOVERED 奖励地图
        self.game_map = GameMap(BONUS_MAP_SIZE, BONUS_MAP_SIZE)
        for y in range(BONUS_MAP_SIZE):
            for x in range(BONUS_MAP_SIZE):
                self.game_map.layer0[y][x] = "UNCOVERED"

        # 4) 散落实体（排除起点 (0, 0)）
        candidates = [(x, y) for x in range(BONUS_MAP_SIZE)
                      for y in range(BONUS_MAP_SIZE) if (x, y) != (0, 0)]
        rng = random.Random()

        chosen = rng.sample(candidates, BONUS_COIN_COUNT + BONUS_GEM_COUNT)
        coin_spots = chosen[:BONUS_COIN_COUNT]
        gem_spots = chosen[BONUS_COIN_COUNT:]

        for cx, cy in coin_spots:
            self.game_map.set_entity(cx, cy, "COIN")
        for gx, gy in gem_spots:
            self.game_map.set_entity(gx, gy, "GEM")

        # 5) 放置陷阱（不占 layer2，仅 traps 矩阵）
        remaining = [c for c in candidates
                     if c not in coin_spots and c not in gem_spots]
        trap_spots = rng.sample(remaining, min(BONUS_TRAP_COUNT, len(remaining)))
        for tx, ty in trap_spots:
            self.game_map.traps[ty][tx] = True

        # 6) 初始化瓦片渲染器（使用动态格子大小）
        game_area_height = SCREEN_HEIGHT - HUD_HEIGHT
        self._cell_size = min(SCREEN_WIDTH, game_area_height) // BONUS_MAP_SIZE
        self.tile_renderer = TileRenderer(tile_size=self._cell_size)

        # 7) 初始化交互控制器（起点 (0, 0)）
        self.interaction_controller = InteractionController(
            self.game_map, player,
            start_x=0, start_y=0,
        )
        self.player_x = 0
        self.player_y = 0

        # 7) 初始化玩法指南蒙层
        self.help_overlay = HelpOverlay()
        self.show_help = False

        # 7.5) 初始化小地图
        self.minimap = Minimap(self.game_map, player)

        # 8) 预载音效（尝试加载金币叮当声，退化静默处理）
        try:
            self._coin_sound = self.game_manager.asset_manager.get_sound("coin")
        except Exception:
            self._coin_sound = None

        # 8) 启动奖励关背景音乐
        from src.audio_manager import AudioManager
        AudioManager.get_instance().play_bgm("bonus_bgm.ogg")

    def on_exit(self):
        """离开奖励关时释放引用。"""
        self.game_manager = None
        self.screen_manager = None
        self.game_map = None
        self.interaction_controller = None
        self.tile_renderer = None
        self.show_minimap = False
        self.minimap = None

    # =========================================================================
    # 事件处理
    # =========================================================================

    def handle_event(self, event: pygame.event.Event):
        """处理键盘移动（WASD / 方向键）。"""
        if not self.bonus_active or self.interaction_controller is None:
            return

        # ── H / F1 切换帮助蒙层（最高优先级）──────────────
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_h, pygame.K_F1):
            self.show_help = not self.show_help
            return
        # 帮助开启时，冻结一切方向移动与其它按键
        if self.show_help:
            return

        # ── Tab 切换小地图 ────────────────────────────────
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            # 帮助蒙层开启时，强制关闭小地图
            if self.show_help:
                self.show_minimap = False
            else:
                self.show_minimap = not self.show_minimap
            return

        if event.type != pygame.KEYDOWN:
            return

        # 计算目标坐标
        px, py = self.player_x, self.player_y
        if event.key in (pygame.K_LEFT, pygame.K_a):
            tx, ty = px - 1, py
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            tx, ty = px + 1, py
        elif event.key in (pygame.K_UP, pygame.K_w):
            tx, ty = px, py - 1
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            tx, ty = px, py + 1
        else:
            return

        result = self.interaction_controller.move_player(tx, ty)
        if result == "SUCCESS":
            # 更新本地坐标
            self.player_x, self.player_y = tx, ty

            # 播放金币音效（退化静默）
            if self._coin_sound:
                try:
                    self._coin_sound.play()
                except Exception:
                    pass

            # 踩雷判定（不扣血，立即退出）
            if self.game_map.traps[self.player_y][self.player_x]:
                self._exit_bonus_level()

    # =========================================================================
    # 帧循环
    # =========================================================================

    def update(self, dt: float):
        """倒计时更新 — 归零时自动结束奖励关。"""
        if not self.bonus_active:
            return

        # 帮助蒙层开启时，冻结倒计时（玩家查规则不损失夺宝时间）
        if self.show_help:
            return

        self.timer -= dt
        if self.timer <= 0:
            self.timer = 0
            self._exit_bonus_level()

    def render(self, surface: pygame.Surface):
        """绘制奖励关画面 — 倒计时 + 8×8 网格 + 玩家。"""
        if self.game_map is None or self.tile_renderer is None:
            return

        surface.fill(BONUS_BG_COLOR)

        # ---- 顶部倒计时 ----
        font_size = 36
        try:
            font = pygame.font.SysFont("arial", font_size, bold=True)
        except Exception:
            font = pygame.font.Font(None, font_size)

        timer_text = f"BONUS LEVEL — TIME LEFT: {self.timer:.1f}s"
        color = YELLOW if self.timer > 5.0 else (255, 0, 0)  # 最后 5 秒变红
        label = font.render(timer_text, True, color)
        label_x = (SCREEN_WIDTH - label.get_width()) // 2
        surface.blit(label, (label_x, 10))

        # ---- 8×8 地图渲染（使用 TileRenderer）----
        cs = self._cell_size
        grid_pixel_w = cs * BONUS_MAP_SIZE
        grid_pixel_h = cs * BONUS_MAP_SIZE
        game_area_height = SCREEN_HEIGHT - HUD_HEIGHT
        offset_x = (SCREEN_WIDTH - grid_pixel_w) // 2
        offset_y = HUD_HEIGHT + (game_area_height - grid_pixel_h) // 2

        for row in range(BONUS_MAP_SIZE):
            for col in range(BONUS_MAP_SIZE):
                tile_x = offset_x + col * cs
                tile_y = offset_y + row * cs

                # 地面底色（UNCOVERED 风格）
                self.tile_renderer.draw_tile(surface, "UNCOVERED", tile_x, tile_y)

                # 实体覆盖（COIN / GEM 等）
                entity = self.game_map.layer2[row][col]
                if entity != "NONE":
                    self.tile_renderer.draw_tile(surface, entity, tile_x, tile_y)

                # 陷阱不显示（隐蔽）

        # ---- 绘制玩家 ----
        px, py = self.player_x, self.player_y
        player_x = offset_x + px * cs
        player_y = offset_y + py * cs
        self.tile_renderer.draw_tile(surface, "PLAYER", player_x, player_y)

        # ---- 小地图（玩家上方、帮助蒙层之下）— 半透明叠加 ----
        if self.show_minimap and self.minimap is not None:
            self.minimap.render(surface, self.player_x, self.player_y,
                                self.timer)

        # ---- 玩法指南蒙层（最顶层）----
        if self.show_help and self.help_overlay is not None:
            self.help_overlay.render(surface)

    # =========================================================================
    # 内部辅助
    # =========================================================================

    def _exit_bonus_level(self):
        """结束奖励关 — 赋予四叶草 Buff 并返回主关卡。"""
        self.bonus_active = False

        # 赋予幸运四叶草 Buff
        self.game_manager.player_state.has_clover = True

        # 切换回主关卡（恢复挂起现场）
        self.game_manager.screen_manager.switch_screen(
            GameState.PLAYING, {"resume": True}
        )
