"""顶部 HUD 状态栏渲染 — Microsoft Treasure Hunt

将 PlayerState 的实时数据可视化渲染在屏幕顶部 HUD 区域：
生命值、护盾、金币、关卡数、背包工具、钥匙、武器、Buff。

所有图片资源加载均通过 try-except 包裹，缺失时使用文字/色块降级，
保证绝不因资源缺失而崩溃。
"""

import os as _os
import sys as _sys

# 将 src/ 加入模块搜索路径
_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from src.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    HUD_HEIGHT,
    WHITE,
    BLACK,
    GRAY,
    RED,
    GREEN,
    BLUE,
    YELLOW,
    ORANGE,
    PURPLE,
    CYAN,
    GOLD,
    SILVER,
    DARK_GREEN,
    LIGHT_BLUE,
)
from src.asset_manager import AssetManager
from src.player_state import PlayerState


# =============================================================================
# HUD 区域布局常量
# =============================================================================

# 背景与分割线
HUD_BG_COLOR = (15, 23, 42)
HUD_DIVIDER_COLOR = (51, 65, 85)
HUD_DIVIDER_Y = 95

# 区域 X 坐标范围
AREA_LIFE_X0 = 20
AREA_LIFE_X1 = 250
AREA_GOLD_X0 = 270
AREA_GOLD_X1 = 420
AREA_TOOLS_X0 = 450
AREA_TOOLS_X1 = 650
AREA_KEYS_X0 = 680
AREA_KEYS_X1 = 850
AREA_WEAPON_X0 = 880
AREA_WEAPON_X1 = 1000

# 图标尺寸
ICON_SIZE = 24
HEART_SIZE = 20
SHIELD_SIZE = 20

# 工具图标尺寸
TOOL_ICON_SIZE = 22

# 钥匙图标尺寸
KEY_SIZE = 18


# =============================================================================
# HUD 类
# =============================================================================

class HUD:
    """顶部状态栏渲染器 — 从 PlayerState 读取数据并渲染到 Surface。"""

    def __init__(self, player_state):
        """
        Args:
            player_state: PlayerState 实例，HUD 从中读取所有显示数据。
        """
        self.player_state = player_state
        self.asset_manager = AssetManager.get_instance()

        # 创建安全的降级 PlayerState（当绑定时为 None 时使用）
        if self.player_state is None:
            self._fallback_player = PlayerState()
        else:
            self._fallback_player = None

        # 确保 font 模块已初始化（headless 环境下 SysFont 需要）
        if not pygame.font.get_init():
            pygame.font.init()

        # 加载字体（失败时 asset_manager 会降级到系统默认字体）
        self.font = self._safe_get_font("arial", 18)
        self.font_small = self._safe_get_font("arial", 14)
        self.font_tiny = self._safe_get_font("arial", 12)

        # 尝试加载图标资源（全部包裹在 try-except 中，缺失则保留 None）
        self._load_icons()

    @property
    def _player(self):
        """安全获取 PlayerState：绑定时返回绑定值，否则返回降级实例。"""
        return self.player_state if self.player_state is not None else self._fallback_player

    def _safe_get_font(self, font_name: str, size: int):
        """安全加载字体，失败返回 None。"""
        try:
            return self.asset_manager.get_font(font_name, size)
        except Exception:
            return None

    def _load_icons(self):
        """懒加载所有图标资源，失败时对应属性为 None。"""
        # 心形图标
        self.heart_full = self._safe_load_image("hud/heart_full.png", (HEART_SIZE, HEART_SIZE))
        self.heart_empty = self._safe_load_image("hud/heart_empty.png", (HEART_SIZE, HEART_SIZE))

        # 护盾图标
        self.shield_full = self._safe_load_image("hud/shield_full.png", (SHIELD_SIZE, SHIELD_SIZE))
        self.shield_empty = self._safe_load_image("hud/shield_empty.png", (SHIELD_SIZE, SHIELD_SIZE))

        # 金币图标
        self.coin_icon = self._safe_load_image("hud/hud_coin.png", (ICON_SIZE, ICON_SIZE))

        # 钥匙图标
        self.key_red = self._safe_load_image("hud/hud_key_red.png", (KEY_SIZE, KEY_SIZE))
        self.key_green = self._safe_load_image("hud/hud_key_green.png", (KEY_SIZE, KEY_SIZE))
        self.key_blue = self._safe_load_image("hud/hud_key_blue.png", (KEY_SIZE, KEY_SIZE))
        self.key_exit = self._safe_load_image("hud/hud_key_exit.png", (KEY_SIZE, KEY_SIZE))

        # 工具图标
        self.icon_pickaxe = self._safe_load_image("hud/hud_pickaxe.png", (TOOL_ICON_SIZE, TOOL_ICON_SIZE))
        self.icon_dynamite = self._safe_load_image("hud/hud_dynamite.png", (TOOL_ICON_SIZE, TOOL_ICON_SIZE))
        self.icon_map = self._safe_load_image("hud/hud_map.png", (TOOL_ICON_SIZE, TOOL_ICON_SIZE))

        # 武器与 Buff 图标
        self.icon_arrow = self._safe_load_image("hud/hud_arrow.png", (ICON_SIZE, ICON_SIZE))
        self.icon_machete = self._safe_load_image("hud/hud_machete.png", (ICON_SIZE, ICON_SIZE))
        self.icon_clover = self._safe_load_image("hud/hud_clover.png", (ICON_SIZE, ICON_SIZE))

    def _safe_load_image(self, rel_path: str, size: tuple = None):
        """安全加载图片，失败返回 None。"""
        try:
            return self.asset_manager.get_image(rel_path, size)
        except Exception:
            return None

    # =========================================================================
    # 主渲染入口
    # =========================================================================

    def render(self, surface: pygame.Surface, current_level_num: int):
        """渲染整个 HUD 状态栏。

        Args:
            surface: 目标 Surface（通常是屏幕 Surface）。
            current_level_num: 当前关卡编号。
        """
        # 绘制背景
        hud_rect = pygame.Rect(0, 0, SCREEN_WIDTH, HUD_HEIGHT)
        pygame.draw.rect(surface, HUD_BG_COLOR, hud_rect)

        # 绘制分割线
        pygame.draw.line(
            surface, HUD_DIVIDER_COLOR,
            (0, HUD_DIVIDER_Y), (SCREEN_WIDTH, HUD_DIVIDER_Y),
            1,
        )

        # 渲染各区域
        self._render_life_and_shield(surface)
        self._render_gold_and_level(surface, current_level_num)
        self._render_tools(surface)
        self._render_keys(surface)
        self._render_weapons_and_buffs(surface)

    # =========================================================================
    # 区域 1：生命值与护盾（左侧 X:20-250）
    # =========================================================================

    def _render_life_and_shield(self, surface: pygame.Surface):
        """绘制生命值心形与护盾图标。"""
        x = AREA_LIFE_X0
        y = 12

        # --- 生命值 ---
        # 标签
        if self.font_small:
            label_life = self.font_small.render("HP", True, RED)
            surface.blit(label_life, (x, y + 2))
        x += 30

        player = self._player
        for i in range(player.max_hearts):
            if i < player.current_hearts:
                icon = self.heart_full
                color = RED
            else:
                icon = self.heart_empty
                color = (128, 0, 0)

            if icon is not None:
                surface.blit(icon, (x + i * (HEART_SIZE + 2), y))
            else:
                # 降级：画红色/暗红色小方块
                rect = pygame.Rect(x + i * (HEART_SIZE + 2), y, HEART_SIZE, HEART_SIZE)
                if i < player.current_hearts:
                    pygame.draw.rect(surface, RED, rect)
                else:
                    pygame.draw.rect(surface, (128, 0, 0), rect, 2)

        # --- 护盾 ---
        x = AREA_LIFE_X0
        y = 42

        if self.font_small:
            label_shield = self.font_small.render("Shield", True, CYAN)
            surface.blit(label_shield, (x, y + 2))
        x += 55

        for i in range(player.max_shields):
            if i < player.current_shields:
                icon = self.shield_full
                color = CYAN
            else:
                icon = self.shield_empty
                color = (0, 100, 128)

            if icon is not None:
                surface.blit(icon, (x + i * (SHIELD_SIZE + 2), y))
            else:
                rect = pygame.Rect(x + i * (SHIELD_SIZE + 2), y, SHIELD_SIZE, SHIELD_SIZE)
                if i < player.current_shields:
                    pygame.draw.rect(surface, CYAN, rect)
                else:
                    pygame.draw.rect(surface, (0, 100, 128), rect, 2)

    # =========================================================================
    # 区域 2：金币与关卡数（中左 X:270-420）
    # =========================================================================

    def _render_gold_and_level(self, surface: pygame.Surface, current_level_num: int):
        """绘制关卡数与金币数量。"""
        x = AREA_GOLD_X0
        y = 12

        # --- 关卡数 ---
        if self.font:
            level_text = self.font.render(f"LEVEL {current_level_num}", True, WHITE)
            surface.blit(level_text, (x, y))

        # --- 金币 ---
        y = 42
        if self.coin_icon is not None:
            surface.blit(self.coin_icon, (x, y))
            coin_x = x + ICON_SIZE + 6
        else:
            # 降级：画金色小圆圈代表硬币
            pygame.draw.circle(surface, GOLD, (x + ICON_SIZE // 2, y + ICON_SIZE // 2), ICON_SIZE // 2)
            coin_x = x + ICON_SIZE + 6

        player = self._player
        if self.font:
            gold_text = self.font.render(f"{player.gold}", True, GOLD)
            surface.blit(gold_text, (coin_x, y + 2))

    # =========================================================================
    # 区域 3：背包与工具数量（中部 X:450-650）
    # =========================================================================

    def _render_tools(self, surface: pygame.Surface):
        """绘制铁锹、炸药、地图工具数量及背包上限。"""
        x = AREA_TOOLS_X0
        y = 12

        player = self._player
        max_cap = player.max_capacity()

        # 标签
        if self.font_small:
            label_tools = self.font_small.render("Tools", True, ORANGE)
            surface.blit(label_tools, (x, y))
        y += 22

        # 工具列表：(显示名, 数量, 图标, 颜色)
        tools_info = [
            ("P", player.tools.get("pickaxe", 0), self.icon_pickaxe, ORANGE),
            ("D", player.tools.get("dynamite", 0), self.icon_dynamite, RED),
            ("M", player.tools.get("map", 0), self.icon_map, GREEN),
        ]

        for i, (letter, count, icon, color) in enumerate(tools_info):
            tx = x + i * 60

            if icon is not None:
                surface.blit(icon, (tx, y))
                num_x = tx + TOOL_ICON_SIZE + 4
            else:
                # 降级：画带字母的色块
                rect = pygame.Rect(tx, y, TOOL_ICON_SIZE, TOOL_ICON_SIZE)
                pygame.draw.rect(surface, color, rect, 2)
                if self.font_tiny:
                    letter_surf = self.font_tiny.render(letter, True, color)
                    surface.blit(letter_surf, (tx + 5, y + 4))
                num_x = tx + TOOL_ICON_SIZE + 4

            # 数量
            if self.font:
                count_text = self.font.render(f"{count}", True, WHITE)
                surface.blit(count_text, (num_x, y + 2))

        # 背包上限提示
        y = 68
        total = player.total_tools()
        if self.font_tiny:
            cap_text = self.font_tiny.render(f"Bag: {total}/{max_cap}", True, GRAY)
            surface.blit(cap_text, (x, y))

    # =========================================================================
    # 区域 4：彩色钥匙包（中右 X:680-850）
    # =========================================================================

    def _render_keys(self, surface: pygame.Surface):
        """绘制红/绿/蓝钥匙及金色出口钥匙数量。"""
        x = AREA_KEYS_X0
        y = 12

        player = self._player

        # 标签
        if self.font_small:
            label_keys = self.font_small.render("Keys", True, YELLOW)
            surface.blit(label_keys, (x, y))
        y += 22

        # 钥匙列表：(颜色名, 数量, 图标, 颜色值)
        keys_info = [
            ("R", player.keys.get("RED", 0), self.key_red, RED),
            ("G", player.keys.get("GREEN", 0), self.key_green, GREEN),
            ("B", player.keys.get("BLUE", 0), self.key_blue, BLUE),
            ("EXIT", player.keys.get("EXIT", 0), self.key_exit, GOLD),
        ]

        for i, (prefix, count, icon, color) in enumerate(keys_info):
            if i < 3:
                kx = x + i * 40
            else:
                kx = x + 3 * 40 + 10  # EXIT 钥匙稍微隔开

            if icon is not None:
                surface.blit(icon, (kx, y))
                num_x = kx + KEY_SIZE + 2
            else:
                # 降级：画彩色小菱形
                cx = kx + KEY_SIZE // 2
                cy = y + KEY_SIZE // 2
                diamond = [
                    (cx, cy - KEY_SIZE // 2),
                    (cx + KEY_SIZE // 2, cy),
                    (cx, cy + KEY_SIZE // 2),
                    (cx - KEY_SIZE // 2, cy),
                ]
                pygame.draw.polygon(surface, color, diamond)
                num_x = kx + KEY_SIZE + 2

            # 数量
            if self.font:
                count_text = self.font.render(f"{count}", True, color)
                surface.blit(count_text, (num_x, y + 2))

    # =========================================================================
    # 区域 5：武器与 Buff（右侧 X:880-1000）
    # =========================================================================

    def _render_weapons_and_buffs(self, surface: pygame.Surface):
        """绘制弓箭数量、柴刀激活标志、四叶草 Buff 标志。"""
        x = AREA_WEAPON_X0
        y = 12

        player = self._player

        # --- 弓箭 ---
        if self.icon_arrow is not None:
            surface.blit(self.icon_arrow, (x, y))
            arrow_x = x + ICON_SIZE + 4
        else:
            # 降级：画简易箭矢形状
            pygame.draw.line(surface, SILVER, (x + 5, y + 12), (x + 20, y + 12), 2)
            pygame.draw.polygon(surface, SILVER, [(x + 20, y + 8), (x + 24, y + 12), (x + 20, y + 16)])
            arrow_x = x + ICON_SIZE + 4

        if self.font:
            arrow_text = self.font.render(f"A:{player.arrows}", True, SILVER)
            surface.blit(arrow_text, (arrow_x, y + 2))

        # --- 柴刀 ---
        y = 42
        if player.has_machete:
            if self.icon_machete is not None:
                surface.blit(self.icon_machete, (x, y))
            else:
                # 降级：画发光的灰色柴刀形状
                rect = pygame.Rect(x, y, ICON_SIZE, ICON_SIZE)
                pygame.draw.rect(surface, SILVER, rect, 1)
                pygame.draw.line(surface, WHITE, (x + 4, y + 12), (x + 20, y + 8), 2)
            if self.font_tiny:
                machete_label = self.font_tiny.render("ON", True, GREEN)
                surface.blit(machete_label, (x + ICON_SIZE + 2, y + 4))
        else:
            # 未激活：灰色不透明渲染
            if self.icon_machete is not None:
                # 创建半透明副本
                dim = self.icon_machete.copy()
                dim.set_alpha(64)
                surface.blit(dim, (x, y))
            else:
                rect = pygame.Rect(x, y, ICON_SIZE, ICON_SIZE)
                pygame.draw.rect(surface, (64, 64, 64), rect, 1)
                if self.font_tiny:
                    off_label = self.font_tiny.render("OFF", True, (80, 80, 80))
                    surface.blit(off_label, (x + 2, y + 4))

        # --- 四叶草 Buff ---
        y = 68
        if player.has_clover:
            if self.icon_clover is not None:
                surface.blit(self.icon_clover, (x, y))
            else:
                # 降级：画绿色四叶草（四个小圆）
                cx = x + ICON_SIZE // 2
                cy = y + ICON_SIZE // 2
                r = 4
                pygame.draw.circle(surface, GREEN, (cx - r, cy - r), r)
                pygame.draw.circle(surface, GREEN, (cx + r, cy - r), r)
                pygame.draw.circle(surface, GREEN, (cx - r, cy + r), r)
                pygame.draw.circle(surface, GREEN, (cx + r, cy + r), r)
            if self.font_tiny:
                clover_label = self.font_tiny.render("LUCK", True, GREEN)
                surface.blit(clover_label, (x + ICON_SIZE + 2, y + 4))
