"""全局主控游戏管理器 — Microsoft Treasure Hunt

顶层协调者，以单例模式运行整个游戏：
- init_engine(): 初始化 Pygame + 全部 Manager 系统
- run(): 主循环 — dt 钳制 → 事件分发 → 逻辑更新 → 画面渲染
- quit_game(): 优雅退出

使用方式::

    game = GameManager.get_instance()
    game.init_engine()
    game.run()       # 阻塞式主循环
    game.quit_game()
"""

import os
import sys

# 将 src/ 加入模块搜索路径，保证 `import config` 等语句跨工作目录可用
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from asset_manager import AssetManager
from audio_manager import AudioManager
from save_manager import SaveManager
from screen_manager import ScreenManager
from player_state import PlayerState


# dt 钳制上限 — 防止卡顿时角色/光标穿墙（见 docs/10 §2.3.2）
MAX_DT = 0.25  # 秒


class GameManager:
    """全局游戏管理器（单例） — 持有所有子系统引用，驱动主循环。

    通过 get_instance() 获取全局唯一实例；不要直接实例化。
    """

    _instance: "GameManager | None" = None

    def __init__(self):
        self.screen: pygame.Surface | None = None
        self.clock: pygame.time.Clock | None = None
        self.asset_manager: AssetManager | None = None
        self.audio_manager: AudioManager | None = None
        self.save_manager: SaveManager | None = None
        self.screen_manager: ScreenManager | None = None
        self.player_state: PlayerState | None = None
        self.suspended_level_state: dict | None = None
        self.settings_data: dict | None = None
        self.running: bool = False

    # =========================================================================
    # 单例访问
    # =========================================================================

    @classmethod
    def get_instance(cls) -> "GameManager":
        """获取或创建全局唯一 GameManager 实例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =========================================================================
    # 引擎初始化
    # =========================================================================

    def init_engine(self, headless: bool = False):
        """初始化 Pygame 核心与全部子系统。

        Args:
            headless: 测试环境设为 True，使用 NOFRAME 标志创建无窗口 Surface；
                      正式运行设为 False，以配置的分辨率 + 标题栏显示窗口。
        """
        pygame.init()

        if headless:
            self.screen = pygame.display.set_mode(
                (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME
            )
        else:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
            pygame.display.set_caption("Microsoft Treasure Hunt")

        self.clock = pygame.time.Clock()

        # 初始化核心子系统
        self.asset_manager = AssetManager.get_instance()
        self.audio_manager = AudioManager.get_instance()
        self.save_manager = SaveManager()
        self.screen_manager = ScreenManager()

        # 初始化玩家状态：尝试从存档加载，失败则保留默认 PlayerState
        self.player_state = PlayerState()
        data = None
        try:
            data = self.save_manager.load()
            if data and "player" in data:
                self.player_state = self._hydrate_player(data["player"])
        except Exception:
            # 存档加载异常时保留默认 PlayerState，不中断启动流程
            pass

        # 提取全局设置
        self.settings_data = {"sound_volume": 1.0, "music_volume": 1.0}
        if data and "settings" in data:
            self.settings_data = data["settings"]

        # 同步音量到 AudioManager（确保混音器状态与持久化设置一致）
        self.audio_manager.set_music_volume(self.settings_data.get("music_volume", 1.0))
        self.audio_manager.set_sfx_volume(self.settings_data.get("sound_volume", 1.0))

        self.running = True

        # ---- 自举装载：实例化并注册全部 7 个场景界面 ----
        self._register_all_screens()

    # =========================================================================
    # 主循环
    # =========================================================================

    def run(self):
        """阻塞式主循环 — 持续运行直到 self.running 被置为 False。

        每帧流程：
        1. 计算 dt（秒），钳制到 [0.0, MAX_DT]
        2. 分发 pygame 事件：QUIT → running=False，其余交给 current_screen
        3. 逻辑更新：current_screen.update(dt)
        4. 画面渲染：current_screen.render(screen) + display.flip()
        """
        while self.running:
            # ---- dt 计算与钳制 ----
            dt_ms = self.clock.tick(FPS)
            dt = dt_ms / 1000.0
            if dt > MAX_DT:
                dt = MAX_DT

            # ---- 事件分发 ----
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                if self.screen_manager.current_screen is not None:
                    self.screen_manager.current_screen.handle_event(event)

            # ---- 逻辑更新与画面渲染 ----
            if self.screen_manager.current_screen is not None:
                self.screen_manager.current_screen.update(dt)
                self.screen_manager.current_screen.render(self.screen)

            pygame.display.flip()

    # =========================================================================
    # 关闭与退出
    # =========================================================================

    def quit_game(self):
        """优雅退出 — 停止主循环并清理 Pygame 资源。"""
        self.running = False
        pygame.quit()

    # =========================================================================
    # 自举装载（惰性场景注册）
    # =========================================================================

    def _register_all_screens(self):
        """自举装载：惰性导入全部 7 个场景类并注册到 ScreenManager。

        在 init_engine() 末尾自动调用。方法体内使用惰性 import 以避免
        与各 screen 模块中 ``from src.game_manager import GameManager``
        产生循环引用（各 screen 在 on_enter() 中延迟导入 GameManager）。
        """
        # 惰性导入 — 在方法体内而非模块级，避开循环引用
        from src.screens.main_menu_screen import MainMenuScreen             # noqa: E402
        from src.screens.gameplay_screen import GameplayScreen              # noqa: E402
        from src.screens.mummy_shop_screen import MummyShopScreen          # noqa: E402
        from src.screens.bonus_level_screen import BonusLevelScreen        # noqa: E402
        from src.screens.level_complete_screen import LevelCompleteScreen  # noqa: E402
        from src.screens.game_over_screen import GameOverScreen            # noqa: E402
        from src.screens.settings_screen import SettingsScreen             # noqa: E402
        from src.config import GameState                                   # noqa: E402

        mappings = [
            (GameState.MAIN_MENU, MainMenuScreen()),
            (GameState.PLAYING, GameplayScreen()),
            (GameState.BONUS_LEVEL, BonusLevelScreen()),
            (GameState.MUMMY_SHOP, MummyShopScreen()),
            (GameState.LEVEL_COMPLETE, LevelCompleteScreen()),
            (GameState.GAME_OVER, GameOverScreen()),
            (GameState.SETTINGS, SettingsScreen()),
        ]
        for state, instance in mappings:
            self.screen_manager.register_screen(state, instance)

    # =========================================================================
    # 内部辅助
    # =========================================================================

    @staticmethod
    def _hydrate_player(player_data: dict) -> PlayerState:
        """从存档字典回填 PlayerState 字段。

        未识别的字段静默忽略；字段缺失时保留 PlayerState 默认值。

        Args:
            player_data: save.json 中 "player" 键对应的字典。

        Returns:
            回填后的 PlayerState 实例。
        """
        state = PlayerState()

        # ---- 生命 / 护盾 ----
        if "max_hearts" in player_data and player_data["max_hearts"] is not None:
            state.max_hearts = int(player_data["max_hearts"])
        if "current_hearts" in player_data and player_data["current_hearts"] is not None:
            state.current_hearts = int(player_data["current_hearts"])
        if "max_shields" in player_data and player_data["max_shields"] is not None:
            state.max_shields = int(player_data["max_shields"])
        if "current_shields" in player_data and player_data["current_shields"] is not None:
            state.current_shields = int(player_data["current_shields"])

        # ---- 经济 ----
        if "gold" in player_data and player_data["gold"] is not None:
            state.gold = int(player_data["gold"])

        # ---- 生涯统计 ----
        if "highest_level_cleared" in player_data and player_data["highest_level_cleared"] is not None:
            state.highest_level_cleared = int(player_data["highest_level_cleared"])
        if "total_gold_earned" in player_data and player_data["total_gold_earned"] is not None:
            state.total_gold_earned = int(player_data["total_gold_earned"])

        # ---- 背包工具 ----
        if "tools" in player_data and isinstance(player_data["tools"], dict):
            for tool_name in ("pickaxe", "dynamite", "map"):
                if tool_name in player_data["tools"]:
                    state.tools[tool_name] = int(player_data["tools"][tool_name])
        if "bag_tier_index" in player_data and player_data["bag_tier_index"] is not None:
            state.bag_tier_index = int(player_data["bag_tier_index"])

        # ---- 钥匙 ----
        if "keys" in player_data and isinstance(player_data["keys"], dict):
            for color in ("RED", "GREEN", "BLUE", "EXIT"):
                if color in player_data["keys"]:
                    state.keys[color] = int(player_data["keys"][color])

        # ---- 临时状态 ----
        if "arrows" in player_data and player_data["arrows"] is not None:
            state.arrows = int(player_data["arrows"])
        if "has_machete" in player_data:
            state.has_machete = bool(player_data["has_machete"])
        if "has_amulet" in player_data:
            state.has_amulet = bool(player_data["has_amulet"])
        if "has_clover" in player_data:
            state.has_clover = bool(player_data["has_clover"])

        return state
