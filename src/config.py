"""全局常量与配置文件 — Microsoft Treasure Hunt

集中管理所有静态常量与阶梯数值，供游戏各模块引用。
本文件不依赖任何外部模块，仅使用 Python 标准库。
"""

from enum import Enum

# =============================================================================
# 屏幕与渲染参数
# =============================================================================

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
HUD_HEIGHT = 96
TILE_SIZE = 48
FPS = 60


# =============================================================================
# 游戏状态枚举
# =============================================================================

class GameState(Enum):
    """游戏全局状态机枚举"""
    MAIN_MENU = "main_menu"
    PLAYING = "playing"
    BONUS_LEVEL = "bonus_level"
    MUMMY_SHOP = "mummy_shop"
    LEVEL_COMPLETE = "level_complete"
    GAME_OVER = "game_over"
    SETTINGS = "settings"
    STATS = "stats"
    SAVE_SLOT_SELECT = "save_slot_select"
    MAP_EDITOR = "map_editor"


# =============================================================================
# 地貌（Biome）系统
# =============================================================================

class BiomeType(Enum):
    """地牢地貌类型枚举"""
    GRASSLAND = "grassland"
    DESERT = "desert"
    ICE_CAVE = "ice_cave"
    VOLCANO = "volcano"


def get_biome_for_level(level_num: int) -> BiomeType:
    """根据关卡编号返回对应的地貌类型。

    关卡区间 → 地貌映射：
        1 ~ 5:   GRASSLAND
        6 ~ 10:  DESERT
        11 ~ 15: ICE_CAVE
        16+:     VOLCANO

    Args:
        level_num: 当前关卡编号（从 1 开始）。

    Returns:
        对应的 BiomeType 枚举值。
    """
    if 1 <= level_num <= 5:
        return BiomeType.GRASSLAND
    elif 6 <= level_num <= 10:
        return BiomeType.DESERT
    elif 11 <= level_num <= 15:
        return BiomeType.ICE_CAVE
    else:  # 16+
        return BiomeType.VOLCANO


BIOME_COLORS: dict[BiomeType, dict[str, tuple[int, int, int]]] = {
    BiomeType.GRASSLAND: {
        "DIRT": (120, 80, 50),
        "DIRT_BORDER": (80, 50, 30),
        "UNCOVERED": (34, 139, 34),
        "UNCOVERED_BORDER": (60, 71, 89),
        "WALL": (70, 70, 70),
        "DIRT_WALL": (139, 115, 85),
        "GRID_LINE": (60, 50, 40),
        "BG": (30, 41, 59),
    },
    BiomeType.DESERT: {
        "DIRT": (218, 165, 32),
        "DIRT_BORDER": (80, 50, 30),
        "UNCOVERED": (244, 164, 96),
        "UNCOVERED_BORDER": (60, 71, 89),
        "WALL": (165, 42, 42),
        "DIRT_WALL": (255, 236, 139),
        "GRID_LINE": (180, 140, 40),
        "BG": (60, 40, 20),
    },
    BiomeType.ICE_CAVE: {
        "DIRT": (100, 150, 180),
        "DIRT_BORDER": (80, 50, 30),
        "UNCOVERED": (180, 220, 240),
        "UNCOVERED_BORDER": (60, 71, 89),
        "WALL": (40, 60, 80),
        "DIRT_WALL": (160, 200, 220),
        "GRID_LINE": (100, 140, 160),
        "BG": (20, 30, 50),
    },
    BiomeType.VOLCANO: {
        "DIRT": (80, 40, 30),
        "DIRT_BORDER": (80, 50, 30),
        "UNCOVERED": (60, 20, 20),
        "UNCOVERED_BORDER": (60, 71, 89),
        "WALL": (30, 15, 15),
        "DIRT_WALL": (120, 60, 40),
        "GRID_LINE": (60, 30, 25),
        "BG": (20, 10, 10),
    },
}

BIOME_BGM: dict[BiomeType, str] = {
    BiomeType.GRASSLAND: "grassland_bgm.ogg",
    BiomeType.DESERT: "desert_bgm.ogg",
    BiomeType.ICE_CAVE: "ice_cave_bgm.ogg",
    BiomeType.VOLCANO: "volcano_bgm.ogg",
}


# =============================================================================
# 视野与迷雾（第 55 课 — 地牢战争迷雾 + 火把照明）
# =============================================================================

# 各地貌的基础视野半径（单位：格）。越恶劣的地貌视野越短，强化压迫感。
BIOME_BASE_SIGHT: dict[BiomeType, float] = {
    BiomeType.GRASSLAND: 6.0,
    BiomeType.DESERT:   5.0,
    BiomeType.ICE_CAVE: 3.5,
    BiomeType.VOLCANO:  2.5,
}

# 半影区过渡宽度（单位：格）：视野半径 ~ (半径 + 此值) 之间做线性淡化。
FOG_PENUMBRA: float = 1.5

# 每捡到一个火把 "TORCH"，视野半径的永久格数加成。
TORCH_EXPANSION: float = 1.5

# 火把实体类型常量（散落于关卡 map 的 layer2 中，与 "COIN"/"GEM" 等平级）。
TORCH = "TORCH"


# =============================================================================
# 背包系统
# =============================================================================

INITIAL_BAG_CAPACITY = 2

BAG_CAPACITY_TIERS = [2, 4, 6, 8, 10, 15, 20, 25, 30]

# 升级价格：从当前阶梯索引升级到下一阶梯所需金币
# 索引 0→1 表示从 tier[0]=2 扩容到 tier[1]=4，以此类推
BAG_UPGRADE_PRICES = {
    0: 100,
    1: 200,
    2: 350,
    3: 500,
    4: 750,
    5: 1000,
    6: 1500,
    7: 2000,
}

# =============================================================================
# 红心（生命）系统
# =============================================================================

INITIAL_HEARTS = 3
HARD_CAP_HEARTS = 8

# 升级价格：当前红心数 → 下一级红心数所需金币
HEART_UPGRADE_PRICES = {
    3: 200,
    4: 350,
    5: 500,
    6: 750,
    7: 1000,
}

# =============================================================================
# 护盾系统
# =============================================================================

INITIAL_SHIELDS = 0
HARD_CAP_SHIELDS = 3

# =============================================================================
# 重生护身符
# =============================================================================

AMULET_BASE_PRICE = 1000
AMULET_PRICE_MULTIPLIER = 2


# =============================================================================
# 消耗品基础售价
# =============================================================================

SHOVEL_BASE_PRICE = 50
BOMB_BASE_PRICE = 75
MAP_BASE_PRICE = 100


# =============================================================================
# 颜色常量 (R, G, B) — Pygame 直接可用
# =============================================================================

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)
BROWN = (139, 69, 19)
DARK_GREEN = (0, 100, 0)
LIGHT_BLUE = (173, 216, 230)
GOLD = (255, 215, 0)
SILVER = (192, 192, 192)
TRANSPARENT = (0, 0, 0)  # 用于 colorkey 透明色

# =============================================================================
# 多存档插槽系统（第 46 课）
# =============================================================================

MAX_SAVE_SLOTS = 3
"""存档槽位上限"""

SAVE_SLOT_FILE = "save_slot_{id}.json"
"""存档槽位文件模板"""

DEFAULT_SAVE_SLOT = 1
"""默认存档槽位编号"""


# =============================================================================
# 活性木乃伊 AI（第 41 课）
# =============================================================================

# layer2 实体类型：主动追逐型木乃伊（A* 寻路 + 回合触发）
ACTIVE_MUMMY = "ACTIVE_MUMMY"

# 活性木乃伊散布规则
ACTIVE_MUMMY_MIN_LEVEL = 5       # 仅当关卡 >= 5 时散布
ACTIVE_MUMMY_SPAWN_CHANCE = 0.3  # 每个怪物候选格 30% 概率替换为活性木乃伊
ACTIVE_MUMMY_ALERT_RADIUS = 5    # 苏醒半径（曼哈顿距离）


# =============================================================================
# 法老王首领 Boss（第 49 课）
# =============================================================================

# layer2 实体类型：法老王首领（3 血 / 受击召唤 / 死亡掉落终点钥匙）
MUMMY_KING = "MUMMY_KING"

# Boss 规则常量
MUMMY_KING_ALERT_RADIUS = 6     # 苏醒半径（曼哈顿距离，比普通木乃伊大 1）
MUMMY_KING_MAX_HEARTS = 3      # Boss 初始生命值（每击扣 1，共 3 次）
BOSS_LEVEL_INTERVAL = 10        # 关卡编号为该值的整数倍时为 Boss 关（10 / 20 / ...）


# =============================================================================
# 周期地刺陷阱 SpikeTrap（第 50 课）
# =============================================================================

# layer2 实体类型：翻转地刺（3 步一周期，步行进入 / 原地开掘 驱动翻转）
SPIKE_TRAP = "SPIKE_TRAP"

# 地刺散布规则
SPIKE_TRAP_MIN_LEVEL = 3       # 仅当关卡 >= 3 时散布
SPIKE_TRAP_DENSITY = 0.04      # 候选地面 4% 概率放置
SPIKE_TRAP_STEP_THRESHOLD = 3  # 3 步翻转阈值
