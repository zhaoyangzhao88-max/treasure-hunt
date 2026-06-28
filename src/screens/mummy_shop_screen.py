"""贪婪木乃伊商店界面 — Microsoft Treasure Hunt

玩家通关特定关卡后进入商店，用金币购买消耗品和永久升级。
- 消耗品：铁锹、炸药、地图、护盾（受背包容量/护盾上限约束）
- 永久升级：重生护身符、生命上限、背包容量（阶梯价格）
- 每次购买后自动落盘，离开时跳回 PLAYING 继续下一关
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
    return 100  # 简化版：固定 100（spec 设计值，config.AMULET_BASE_PRICE=1000 不采用）

def _max_hearts_price(ps):
    return HEART_UPGRADE_PRICES.get(ps.max_hearts, 0)

def _bag_capacity_price(ps):
    return BAG_UPGRADE_PRICES.get(ps.bag_tier_index, 0)


# 商品列表定义
SHOP_ITEMS = [
    {
        "id": "pickaxe",
        "name": "Pickaxe (铁锹)",
        "type": "consumable",
        "price_fn": _pickaxe_price,
        "desc": "Dig through dirt walls",
    },
    {
        "id": "dynamite",
        "name": "Dynamite (炸药)",
        "type": "consumable",
        "price_fn": _dynamite_price,
        "desc": "Blast 3x3 areas",
    },
    {
        "id": "map",
        "name": "Map (地图)",
        "type": "consumable",
        "price_fn": _map_price,
        "desc": "Reveal 5x5 area",
    },
    {
        "id": "shield",
        "name": "Shield (护盾)",
        "type": "consumable",
        "price_fn": _shield_price,
        "desc": "Block one hit (full refill)",
    },
    {
        "id": "amulet",
        "name": "Amulet (护身符)",
        "type": "permanent",
        "price_fn": _amulet_price,
        "desc": "Revive once on death",
    },
    {
        "id": "max_hearts",
        "name": "+1 Max Heart (生命上限)",
        "type": "permanent",
        "price_fn": _max_hearts_price,
        "desc": "Permanent HP upgrade",
    },
    {
        "id": "bag_capacity",
        "name": "+1 Bag Tier (背包容量)",
        "type": "permanent",
        "price_fn": _bag_capacity_price,
        "desc": "Increase tool capacity",
    },
]


# =============================================================================
# 商店场景
# =============================================================================

class MummyShopScreen(BaseScreen):
    """贪婪木乃伊商店 — 消耗品 + 永久升级购买。

    生命周期：
    - on_enter: 解析 next_level → 初始化按钮 → 刷新购买状态
    - handle_event: 鼠标悬停 + 点击购买/离开
    - update: no-op
    - render: 深蓝背景 + 标题 + 余额 + 商品列表 + 按钮
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
        self.sound_click = None
        self.sound_buy = None

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
        self.font_info = self.asset_manager.get_font("default", 28)

        # ---- 预载音效 ----
        self.sound_click = self.asset_manager.get_sound("click.wav")
        self.sound_buy = self.asset_manager.get_sound("buy.wav")

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
        self.sound_click = None
        self.sound_buy = None

    # =========================================================================
    # 按钮刷新
    # =========================================================================

    def refresh_shop_buttons(self):
        """根据当前 player_state 刷新所有 Buy 按钮的 is_enabled 状态。

        每次购买成功后调用，确保按钮置灰状态与余额、容量同步。
        """
        ps = self.game_manager.player_state
        self.buttons = []

        # 布局参数
        left_col_x = 320      # 左列 Buy 按钮中心 X
        right_col_x = 740     # 右列 Buy 按钮中心 X
        btn_width = 160
        btn_height = 44
        start_y = 200
        row_gap = 60

        # 左列：消耗品 (4 个)
        left_items = SHOP_ITEMS[:4]
        for i, item in enumerate(left_items):
            enabled = self._can_buy_item(item)
            btn = Button(
                text="Buy",
                center_pos=(left_col_x, start_y + i * row_gap),
                width=btn_width,
                height=btn_height,
                font=self.font_info,
                normal_color=DARK_GREEN,
                hover_color=GOLD,
                text_color=WHITE,
            )
            btn.is_enabled = enabled
            # 将商品 id 附加到按钮对象，供 handle_event 识别
            btn.item_id = item["id"]
            self.buttons.append(btn)

        # 右列：永久升级 (3 个)
        right_items = SHOP_ITEMS[4:]
        for i, item in enumerate(right_items):
            enabled = self._can_buy_item(item)
            btn = Button(
                text="Buy",
                center_pos=(right_col_x, start_y + i * row_gap),
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
            text="离开商店 (Leave Shop)",
            center_pos=(SCREEN_WIDTH // 2, 640),
            width=280,
            height=52,
            font=self.font_info,
            normal_color=DARK_GREEN,
            hover_color=GOLD,
            text_color=WHITE,
        )
        btn_leave.item_id = "leave"
        self.buttons.append(btn_leave)

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

        扣除金币 → 调用 PlayerState 方法 → 自动落盘 → 刷新按钮。

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
            # 工具：手动扣金币 + add_tool，失败则回退
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
            # 护盾：满充
            ps.gold -= price
            ps.current_shields = ps.max_shields

        elif item_id == "amulet":
            # 护身符：一次性
            ps.gold -= price
            ps.has_amulet = True

        elif item_id == "max_hearts":
            # 永久升级：buy_upgrade 内部扣金币，但已通过 _can_buy 检查了价格
            # 注意：buy_upgrade 内部会再扣一次金币，所以这里不手动扣
            # 但 _can_buy_item 只检查 gold >= price，不扣金币
            # 所以直接调用 buy_upgrade 即可
            if not ps.buy_upgrade("max_hearts"):
                return  # 购买失败（不应发生，因为已检查过）

        elif item_id == "bag_capacity":
            if not ps.buy_upgrade("bag_capacity"):
                return

        # ---- 自动落盘 ----
        self.game_manager.save_manager.save(
            self._build_player_dict(ps),
            {
                "sound_volume": 1.0,
                "music_volume": 1.0,
            },
        )

        # ---- 播放购买音效 ----
        if self.sound_buy is not None:
            self.sound_buy.play()

        # ---- 刷新按钮状态 ----
        self.refresh_shop_buttons()

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
        """商店界面无帧间逻辑，no-op。"""
        pass

    def render(self, surface: pygame.Surface):
        """画面绘制 — 深蓝背景 + 标题 + 余额 + 商品列表 + 按钮。"""
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

        # ---- 玩家余额 ----
        if self.font_info is not None:
            ps = self.game_manager.player_state
            gold_surf = self.font_info.render(
                f"Your Gold: {ps.gold} Coins", True, _COLOR_GOLD
            )
            gold_rect = gold_surf.get_rect(center=(center_x, 140))
            surface.blit(gold_surf, gold_rect)

        # ---- 商品列表 ----
        if self.font_info is not None:
            self._render_shop_items(surface)

        # ---- 按钮 ----
        for button in self.buttons:
            button.render(surface)

    def _render_shop_items(self, surface: pygame.Surface):
        """绘制商品列表文字信息。"""
        ps = self.game_manager.player_state
        start_y = 200
        row_gap = 60
        left_text_x = 60     # 左列文字起始 X
        right_text_x = 480   # 右列文字起始 X

        for i, item in enumerate(SHOP_ITEMS):
            price = item["price_fn"](ps)
            x = left_text_x if i < 4 else right_text_x
            y = start_y + (i % 4) * row_gap

            # 商品名称
            name_surf = self.font_info.render(item["name"], True, _COLOR_ITEM_NAME)
            surface.blit(name_surf, (x, y))

            # 当前数量/状况 + 价格
            info_text = self._get_item_status(item, ps, price)
            info_surf = self.font_info.render(info_text, True, _COLOR_ITEM_INFO)
            surface.blit(info_surf, (x, y + 24))

            # 价格标注
            price_surf = self.font_info.render(f"[{price} Gold]", True, _COLOR_PRICE)
            price_rect = price_surf.get_rect(right=x + 400, top=y + 24)
            surface.blit(price_surf, price_rect)

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
            "total_runs": 0,
            "total_gold_earned": ps.total_gold_earned,
            "gold": ps.gold,
            "tools": dict(ps.tools),
            "keys": dict(ps.keys),
            "has_amulet": ps.has_amulet,
        }
