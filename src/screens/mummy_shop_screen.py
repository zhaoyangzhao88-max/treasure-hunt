"""贪婪木乃伊商店界面 — Microsoft Treasure Hunt

玩家通关特定关卡后进入商店，用金币购买消耗品和永久升级。
- 消耗品：铁锹、炸药、地图、护盾（受背包容量/护盾上限约束）
- 永久升级：重生护身符、生命上限、背包容量（阶梯价格）
- 每次购买后自动落盘，离开时跳回 PLAYING 继续下一关

第 40 课升级：3 列卡片式网格布局 + 购买金币微特效。
"""

import os as _os
import random as _random
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from src.screens.base_screen import BaseScreen
from src.ui_helpers import Button
from src.effects import EffectsManager
from src.tile_renderer import TileRenderer
from src.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    GameState,
    WHITE,
    BLACK,
    GOLD,
    GREEN,
    LIGHT_BLUE,
    DARK_GREEN,
    GRAY,
    HEART_UPGRADE_PRICES,
    BAG_UPGRADE_PRICES,
    BAG_CAPACITY_TIERS,
    HARD_CAP_HEARTS,
)


# =============================================================================
# 颜色常量
# =============================================================================

_COLOR_BG = (15, 23, 42)           # 深蓝黑背景
_COLOR_TITLE = (255, 215, 0)        # 金色大标题
_COLOR_PROMPT = (200, 200, 200)     # 提示语 - 银灰
_COLOR_GOLD = (255, 215, 0)         # 金币显示 - 金色
_COLOR_ITEM_NAME = (255, 255, 255)  # 商品名 - 白色
_COLOR_ITEM_INFO = (173, 216, 230) # 商品状况 - 淡蓝色
_COLOR_PRICE = (255, 215, 0)        # 价格 - 金色
_COLOR_DISABLED = (128, 128, 128)   # 禁用态 - 灰色
_COLOR_CARD_BG = (30, 41, 59)       # 卡片深蓝背景
_COLOR_CARD_BORDER = (100, 116, 139) # 卡片边框色
_COLOR_COLUMN_TITLE = (148, 163, 184) # 列标题色
_COLOR_SUCCESS_TEXT = (34, 197, 94)  # 成功购买绿色


# =============================================================================
# 卡片布局常量
# =============================================================================

_CARD_WIDTH = 240
_CARD_HEIGHT = 200
_CARD_GAP_Y = 30        # 卡片行间距（垂直）
_CARD_START_Y = 220     # 首行卡片 Y
_COL_X_POSITIONS = [140, 420, 700]  # 3 列中心 X
_COLUMN_TITLES = [
    "Tool Supplies",
    "Survival",
    "Permanent Upgrades",
]


# =============================================================================
# 商品配置
# =============================================================================

# 每个商品：id, 显示名, 类型(consumable/permanent), 价格计算函数, 描述
# 价格计算函数接收 player_state 返回 int（0 表示不可购买）


def _pickaxe_price(ps):
    return 50


def _dynamite_price(ps):
    return 75


def _map_price(ps):
    return 100


def _shield_price(ps):
    return ps.max_shields * 75


def _amulet_price(ps):
    return 100  # 简化版：固定 100


def _max_hearts_price(ps):
    return HEART_UPGRADE_PRICES.get(ps.max_hearts, 0)


def _bag_capacity_price(ps):
    return BAG_UPGRADE_PRICES.get(ps.bag_tier_index, 0)


# 商品列表定义 — 按 3 列分组排序
# 第一列：工具补给 (pickaxe, dynamite, map)
# 第二列：生存防御 (shield, amulet)
# 第三列：属性永久升级 (max_hearts, bag_capacity)
SHOP_ITEMS = [
    {
        "id": "pickaxe",
        "name": "Pickaxe (铁锹)",
        "type": "consumable",
        "price_fn": _pickaxe_price,
        "desc": "Dig through dirt walls",
        "tile_type": "PICKAXE",
        "col": 0,
    },
    {
        "id": "dynamite",
        "name": "Dynamite (炸药)",
        "type": "consumable",
        "price_fn": _dynamite_price,
        "desc": "Blast 3x3 areas",
        "tile_type": "DYNAMITE",
        "col": 0,
    },
    {
        "id": "map",
        "name": "Map (地图)",
        "type": "consumable",
        "price_fn": _map_price,
        "desc": "Reveal 5x5 area",
        "tile_type": "MAP",
        "col": 0,
    },
    {
        "id": "shield",
        "name": "Shield (护盾)",
        "type": "consumable",
        "price_fn": _shield_price,
        "desc": "Block one hit (full refill)",
        "tile_type": "SHIELD",
        "col": 1,
    },
    {
        "id": "amulet",
        "name": "Amulet (护身符)",
        "type": "permanent",
        "price_fn": _amulet_price,
        "desc": "Revive once on death",
        "tile_type": "AMULET",
        "col": 1,
    },
    {
        "id": "max_hearts",
        "name": "+1 Max Heart (生命上限)",
        "type": "permanent",
        "price_fn": _max_hearts_price,
        "desc": "Permanent HP upgrade",
        "tile_type": "HEART",
        "col": 2,
    },
    {
        "id": "bag_capacity",
        "name": "+1 Bag Tier (背包容量)",
        "type": "permanent",
        "price_fn": _bag_capacity_price,
        "desc": "Increase tool capacity",
        "tile_type": "CHEST",
        "col": 2,
    },
]


# =============================================================================
# 商店场景
# =============================================================================

class MummyShopScreen(BaseScreen):
    """贪婪木乃伊商店 — 消耗品 + 永久升级购买（卡片式 UI + 微特效）。

    生命周期：
    - on_enter: 解析 next_level → 初始化按钮 → 刷新购买状态
    - handle_event: 鼠标悬停 + 点击购买/离开
    - update: 推进特效引擎 + 递减金币抖动
    - render: 深蓝背景 → 卡片网格 → 按钮 → 特效覆层
    """

    def __init__(self):
        """初始化商店界面（不含资源加载 — 由 on_enter 负责）。"""
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None

        self.next_level_num: int = 2
        self.buttons: list[Button] = []
        self.font_title = None
        self.font_info = None
        self.font_price = None
        self.sound_click = None
        self.sound_buy = None

        # 第 40 课新增
        self.effects_manager: EffectsManager | None = None
        self.tile_renderer: TileRenderer | None = None
        self.gold_shake_timer: float = 0.0
        self._card_rects: dict[str, pygame.Rect] = {}  # item_id → card rect

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_enter(self, data_payload: dict = None):
        """进入商店界面 — 解析 next_level、初始化按钮、刷新购买状态。

        Args:
            data_payload: LevelCompleteScreen 传入的数据。
                若包含 next_level: int，则离开商店后跳转到该关卡。
        """
        from src.game_manager import GameManager

        # None guard
        data_payload = data_payload or {}
        self.next_level_num = data_payload.get("next_level", 2)

        self.game_manager = GameManager.get_instance()
        self.screen_manager = self.game_manager.screen_manager
        self.asset_manager = self.game_manager.asset_manager

        # ---- 初始化字体 ----
        self.font_title = self.asset_manager.get_font("default", 56)
        self.font_info = self.asset_manager.get_font("default", 24)
        self.font_price = self.asset_manager.get_font("default", 22)

        # ---- 预载音效 ----
        self.sound_click = self.asset_manager.get_sound("click.wav")
        self.sound_buy = self.asset_manager.get_sound("buy.wav")

        # ---- 初始化特效引擎与瓦片渲染器（第 40 课） ----
        self.effects_manager = EffectsManager()
        self.tile_renderer = TileRenderer()
        self.gold_shake_timer = 0.0

        # ---- 初始化按钮 ----
        self.refresh_shop_buttons()

        # ---- 启动商店背景音乐 ----
        from src.audio_manager import AudioManager
        AudioManager.get_instance().play_bgm("shop_bgm.ogg")

    def on_exit(self):
        """离开商店界面时释放临时引用。"""
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None
        self.buttons = []
        self.font_title = None
        self.font_info = None
        self.font_price = None
        self.sound_click = None
        self.sound_buy = None
        # 第 40 课新增清理
        self.effects_manager = None
        self.tile_renderer = None
        self.gold_shake_timer = 0.0
        self._card_rects = {}

    # =========================================================================
    # 按钮刷新
    # =========================================================================

    def refresh_shop_buttons(self):
        """根据当前 player_state 刷新所有 Buy 按钮状态及卡片矩形。

        3 列卡片网格布局：
        - 第 0 列 (X=140): pickaxe, dynamite, map
        - 第 1 列 (X=420): shield, amulet
        - 第 2 列 (X=700): max_hearts, bag_capacity
        """
        ps = self.game_manager.player_state
        self.buttons = []
        self._card_rects = {}

        btn_width = 160
        btn_height = 42

        # 按列遍历
        for col_idx, items in self._items_by_column():
            col_x = _COL_X_POSITIONS[col_idx]
            for row_idx, item in enumerate(items):
                card_rect = pygame.Rect(
                    col_x - _CARD_WIDTH // 2,
                    _CARD_START_Y + row_idx * (_CARD_HEIGHT + _CARD_GAP_Y),
                    _CARD_WIDTH,
                    _CARD_HEIGHT,
                )
                self._card_rects[item["id"]] = card_rect

                # Buy 按钮锚定在卡片底部
                btn_center_y = card_rect.bottom - 30
                enabled = self._can_buy_item(item)
                btn = Button(
                    text="Buy",
                    center_pos=(col_x, btn_center_y),
                    width=btn_width,
                    height=btn_height,
                    font=self.font_info,
                    normal_color=DARK_GREEN,
                    hover_color=GOLD,
                    text_color=WHITE,
                )
                btn.is_enabled = enabled
                btn.item_id = item["id"]
                self.buttons.append(btn)

        # 离开商店按钮
        btn_leave = Button(
            text="Leave Shop (离开商店)",
            center_pos=(SCREEN_WIDTH // 2, 700),
            width=260,
            height=50,
            font=self.font_info,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        btn_leave.item_id = "leave"
        self.buttons.append(btn_leave)

    def _items_by_column(self):
        """生成 (col_index, items_in_col) 迭代器。"""
        for col_idx in range(3):
            items = [it for it in SHOP_ITEMS if it["col"] == col_idx]
            yield col_idx, items

    # =========================================================================
    # 购买判定与执行
    # =========================================================================

    def _can_buy_item(self, item: dict) -> bool:
        """判定商品是否可购买。

        Args:
            item: 商品配置字典

        Returns:
            True 可购买，False 不可购买（置灰）
        """
        ps = self.game_manager.player_state
        price = item["price_fn"](ps)

        if price <= 0:
            return False

        if ps.gold < price:
            return False

        item_id = item["id"]

        if item_id == "pickaxe":
            return ps.total_tools() + 1 <= ps.max_capacity()
        elif item_id == "dynamite":
            return ps.total_tools() + 1 <= ps.max_capacity()
        elif item_id == "map":
            return ps.total_tools() + 1 <= ps.max_capacity()
        elif item_id == "shield":
            return ps.current_shields < ps.max_shields
        elif item_id == "amulet":
            return not ps.has_amulet
        elif item_id == "max_hearts":
            return ps.max_hearts < HARD_CAP_HEARTS
        elif item_id == "bag_capacity":
            return ps.bag_tier_index < len(BAG_CAPACITY_TIERS) - 1

        return False

    def _buy_item(self, item_id: str):
        """执行购买逻辑。

        扣除金币 → 调用 PlayerState 方法 → 触发特效 → 自动落盘 → 刷新按钮。

        Args:
            item_id: 商品 id
        """
        # 查找商品配置
        item = None
        for it in SHOP_ITEMS:
            if it["id"] == item_id:
                item = it
                break
        if item is None:
            return

        ps = self.game_manager.player_state
        price = item["price_fn"](ps)

        # 再次确认可购买（防止竞态）
        if not self._can_buy_item(item):
            return

        if item_id == "pickaxe":
            ps.gold -= price
            if not ps.add_tool("pickaxe", 1):
                ps.gold += price  # 回退
                return

        elif item_id == "dynamite":
            ps.gold -= price
            if not ps.add_tool("dynamite", 1):
                ps.gold += price
                return

        elif item_id == "map":
            ps.gold -= price
            if not ps.add_tool("map", 1):
                ps.gold += price
                return

        elif item_id == "shield":
            ps.gold -= price
            ps.current_shields = ps.max_shields

        elif item_id == "amulet":
            ps.gold -= price
            ps.has_amulet = True

        elif item_id == "max_hearts":
            if not ps.buy_upgrade("max_hearts"):
                return

        elif item_id == "bag_capacity":
            if not ps.buy_upgrade("bag_capacity"):
                return

        # ---- 触发购买成功特效（第 40 课） ----
        card_rect = self._card_rects.get(item_id)
        if card_rect is not None:
            self._purchase_success_effects(card_rect, item["name"])

        # ---- 自动落盘 ----
        self.game_manager.save_manager.save(
            self._build_player_dict(ps),
            {
                "sound_volume": 1.0,
                "music_volume": 1.0,
            },
        )

        # ---- 刷新按钮状态 ----
        self.refresh_shop_buttons()

    # =========================================================================
    # 购买成功特效（第 40 课）
    # =========================================================================

    def _purchase_success_effects(self, card_rect: pygame.Rect, item_name: str):
        """在卡片中央触发金色粒子爆散 + 绿色漂浮文字 + 金币抖动。

        Args:
            card_rect: 商品卡片矩形
            item_name: 商品显示名（用于漂浮文字）
        """
        cx = card_rect.centerx
        cy = card_rect.centery

        # 1) 金色粒子碎屑爆发（15 个）
        self.effects_manager.spawn_particles(
            cx, cy, color=(255, 215, 0), count=15
        )

        # 2) 绿色漂浮文字
        self.effects_manager.spawn_text(
            cx, cy, f"+1 {item_name}", color=_COLOR_SUCCESS_TEXT
        )

        # 3) 激活金币余额抖动
        self.gold_shake_timer = 0.15

        # 4) 播放购买音效
        from src.audio_manager import AudioManager
        AudioManager.get_instance().play_sfx("buy.wav")

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

                item_id = getattr(button, "item_id", None)

                if item_id == "leave":
                    # ---- 离开商店 ----
                    if self.sound_click is not None:
                        self.sound_click.play()
                    self.screen_manager.switch_screen(
                        GameState.PLAYING,
                        data_payload={
                            "level_num": self.next_level_num,
                            "continue": True,
                        },
                    )

                elif item_id is not None:
                    # ---- 购买商品 ----
                    self._buy_item(item_id)

    # =========================================================================
    # 帧循环
    # =========================================================================

    def update(self, dt: float):
        """推进特效引擎 + 递减金币抖动计时器。"""
        if self.effects_manager is not None:
            self.effects_manager.update(dt)
        if self.gold_shake_timer > 0:
            self.gold_shake_timer -= dt

    def render(self, surface: pygame.Surface):
        """画面绘制 — 深蓝背景 → 卡片网格 → 按钮 → 特效覆层。"""
        # ---- 背景填充 ----
        surface.fill(_COLOR_BG)

        center_x = SCREEN_WIDTH // 2

        # ---- 大标题 ----
        if self.font_title is not None:
            title_surf = self.font_title.render("GREEDY MUMMY'S SHOP", True, _COLOR_TITLE)
            title_rect = title_surf.get_rect(center=(center_x, 50))
            surface.blit(title_surf, title_rect)

        # ---- 提示语 ----
        if self.font_info is not None:
            prompt_surf = self.font_info.render(
                "Trade your coins for precious treasures...", True, _COLOR_PROMPT
            )
            prompt_rect = prompt_surf.get_rect(center=(center_x, 100))
            surface.blit(prompt_surf, prompt_rect)

        # ---- 带抖动的金币余额 ----
        self._render_gold_balance(surface, center_x)

        # ---- 列标题 ----
        self._render_column_titles(surface)

        # ---- 商品卡片 ----
        self._render_cards(surface)

        # ---- 按钮 ----
        for button in self.buttons:
            button.render(surface)

        # ---- 特效覆层（最后渲染，浮于卡片上方） ----
        if self.effects_manager is not None:
            self.effects_manager.render(surface, (0.0, 0.0))

    def _render_gold_balance(self, surface: pygame.Surface, center_x: int):
        """绘制带噪声抖动的金币余额。"""
        if self.font_info is None:
            return
        ps = self.game_manager.player_state

        # 噪声抖动计算
        if self.gold_shake_timer > 0:
            offset_x = _random.randint(-3, 3)
            offset_y = _random.randint(-3, 3)
        else:
            offset_x = 0
            offset_y = 0

        gold_surf = self.font_info.render(
            f"Your Gold: {ps.gold} Coins", True, _COLOR_GOLD
        )
        # 绘制在 (140 + offset_x, 140 + offset_y) — 用户指定位置
        gold_rect = gold_surf.get_rect(topleft=(140 + offset_x, 140 + offset_y))
        surface.blit(gold_surf, gold_rect)

    def _render_column_titles(self, surface: pygame.Surface):
        """绘制 3 列标题文字。"""
        if self.font_info is None:
            return
        for col_idx, title in enumerate(_COLUMN_TITLES):
            col_x = _COL_X_POSITIONS[col_idx]
            title_surf = self.font_info.render(title, True, _COLOR_COLUMN_TITLE)
            title_rect = title_surf.get_rect(center=(col_x, _CARD_START_Y - 25))
            surface.blit(title_surf, title_rect)

    def _render_cards(self, surface: pygame.Surface):
        """绘制 3 列商品卡片（含瓦片图标、名称、价格、状态）。"""
        if self.font_info is None or self.tile_renderer is None:
            return

        ps = self.game_manager.player_state

        for item in SHOP_ITEMS:
            card_rect = self._card_rects.get(item["id"])
            if card_rect is None:
                continue
            self._render_single_card(surface, item, ps, card_rect)

    def _render_single_card(
        self,
        surface: pygame.Surface,
        item: dict,
        ps,
        card_rect: pygame.Rect,
    ):
        """绘制单个商品卡片。"""
        # 卡片背景（圆角矩形）
        pygame.draw.rect(surface, _COLOR_CARD_BG, card_rect, border_radius=12)
        # 卡片边框
        pygame.draw.rect(
            surface, _COLOR_CARD_BORDER, card_rect, width=2, border_radius=12
        )

        # 瓦片图标（左上角偏移 12,12）
        icon_x = card_rect.x + 12
        icon_y = card_rect.y + 12
        self.tile_renderer.draw_tile(
            surface, item["tile_type"], icon_x, icon_y, None
        )

        # 商品名称（图标右侧）
        name_x = icon_x + 56
        name_y = icon_y + 4
        name_surf = self.font_info.render(item["name"], True, _COLOR_ITEM_NAME)
        surface.blit(name_surf, (name_x, name_y))

        # 价格（金色，卡片中下部）
        price = item["price_fn"](ps)
        price_surf = self.font_price.render(f"{price} Gold", True, _COLOR_PRICE)
        price_rect = price_surf.get_rect(
            centerx=card_rect.centerx, top=card_rect.y + 80
        )
        surface.blit(price_surf, price_rect)

        # 状态/拥有量（淡蓝色，卡片底部上方）
        status_text = self._get_item_status(item, ps, price)
        status_surf = self.font_price.render(status_text, True, _COLOR_ITEM_INFO)
        status_rect = status_surf.get_rect(
            centerx=card_rect.centerx, top=card_rect.y + 115
        )
        surface.blit(status_surf, status_rect)

    @staticmethod
    def _get_item_status(item: dict, ps, price: int) -> str:
        """生成商品状态描述文字。"""
        item_id = item["id"]

        if item_id == "pickaxe":
            return f"Owned: {ps.tools['pickaxe']} | Cap: {ps.total_tools()}/{ps.max_capacity()}"
        elif item_id == "dynamite":
            return f"Owned: {ps.tools['dynamite']} | Cap: {ps.total_tools()}/{ps.max_capacity()}"
        elif item_id == "map":
            return f"Owned: {ps.tools['map']} | Cap: {ps.total_tools()}/{ps.max_capacity()}"
        elif item_id == "shield":
            return f"Vitals: {ps.current_shields}/{ps.max_shields}"
        elif item_id == "amulet":
            return "Status: Owned" if ps.has_amulet else "Status: Not owned"
        elif item_id == "max_hearts":
            return f"Max HP: {ps.max_hearts}/{HARD_CAP_HEARTS}"
        elif item_id == "bag_capacity":
            return f"Tier: {ps.bag_tier_index} (Cap: {ps.max_capacity()})"

        return ""

    # =========================================================================
    # 内部辅助
    # =========================================================================

    @staticmethod
    def _build_player_dict(ps) -> dict:
        """将 PlayerState 序列化为 SaveManager 期望的 player 字典格式。

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
