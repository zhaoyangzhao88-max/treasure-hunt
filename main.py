"""
Microsoft Treasure Hunt — 游戏入口主程序

职责：
1. 环境自检（Python 版本、Pygame 可用性）
2. 自适应引擎初始化（自动注册全部 9 个场景界面）
3. 启动前场景注册完整性校验
4. 阻塞式主循环
5. 顶层异常捕获与崩溃日志转储

用法::

    python main.py
"""

import os
import sys
import traceback
from datetime import datetime

# 确保能找到 src/ 模块（允许从项目根目录直接运行）
_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import pygame

# 显式导入 GameState 枚举与全部 9 个场景类（用户要求）
from src.config import GameState
from src.asset_manager import get_resource_path
from src.screens.main_menu_screen import MainMenuScreen
from src.screens.gameplay_screen import GameplayScreen
from src.screens.mummy_shop_screen import MummyShopScreen
from src.screens.bonus_level_screen import BonusLevelScreen
from src.screens.level_complete_screen import LevelCompleteScreen
from src.screens.game_over_screen import GameOverScreen
from src.screens.settings_screen import SettingsScreen
from src.screens.stats_screen import StatsScreen
from src.screens.save_slots_screen import SaveSlotsScreen


# =============================================================================
# 常量
# =============================================================================

REQUIRED_SCREENS: list[tuple[GameState, type]] = [
    (GameState.MAIN_MENU, MainMenuScreen),
    (GameState.PLAYING, GameplayScreen),
    (GameState.BONUS_LEVEL, BonusLevelScreen),
    (GameState.MUMMY_SHOP, MummyShopScreen),
    (GameState.LEVEL_COMPLETE, LevelCompleteScreen),
    (GameState.GAME_OVER, GameOverScreen),
    (GameState.SETTINGS, SettingsScreen),
    (GameState.STATS, StatsScreen),
    (GameState.SAVE_SLOT_SELECT, SaveSlotsScreen),
]
"""所有 GameState 值与其对应场景类的映射关系，用于启动校验。"""

CRASH_LOG_DIR = "crash_logs"
"""崩溃转储目录（相对于工作目录）。"""


# =============================================================================
# 环境自检
# =============================================================================

def check_environment() -> list[tuple[str, str, bool]]:
    """执行启动前环境自检（纯函数，无副作用）。

    Returns:
        检查结果列表，每项为 (检查项名称, 详情, 是否通过) 的三元组。
        当前包含 2 项：Python 版本、Pygame 版本。
    """
    results: list[tuple[str, str, bool]] = []

    # -- Python 版本 --
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 8)
    results.append(("Python 版本", py_ver, py_ok))

    # -- Pygame 版本 --
    pg_ver = pygame.version.ver
    pg_ok = bool(pg_ver)
    results.append(("Pygame 版本", pg_ver, pg_ok))

    # -- 资产目录自检（使用自愈路径解析器，兼容 PyInstaller 打包态） --
    for asset_subdir in ("assets/images", "assets/sounds", "assets/fonts"):
        abs_path = get_resource_path(asset_subdir)
        dir_ok = os.path.isdir(abs_path)
        results.append((f"资产目录 {asset_subdir}", abs_path, dir_ok))

    return results


# =============================================================================
# 场景注册校验
# =============================================================================

def verify_screen_registrations() -> list[str]:
    """校验全部 9 个 Required 场景是否已注册且类型正确。

    要求在调用前已完成 GameManager.get_instance().init_engine()。

    Returns:
        错误消息列表；空列表表示全部校验通过。
    """
    from src.game_manager import GameManager

    mgr = GameManager.get_instance()
    sm = mgr.screen_manager
    if sm is None:
        return ["ScreenManager 未初始化（请先调用 init_engine()）"]

    errors: list[str] = []
    for state, expected_cls in REQUIRED_SCREENS:
        if state not in sm.screens:
            errors.append(f"{state.value}: 未注册场景")
            continue
        inst = sm.screens[state]
        if not isinstance(inst, expected_cls):
            errors.append(
                f"{state.value}: 期望 {expected_cls.__name__}，"
                f"得到 {type(inst).__name__}"
            )
    return errors


# =============================================================================
# 崩溃日志转储
# =============================================================================

def write_crash_log(exc: BaseException) -> str:
    """将未捕获异常写入带时间戳的崩溃日志文件。

    Args:
        exc: 待记录的异常对象。

    Returns:
        写入的日志文件绝对路径。
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(CRASH_LOG_DIR, exist_ok=True)
    log_path = os.path.join(
        os.path.abspath(CRASH_LOG_DIR), f"crash_{timestamp}.log"
    )
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Microsoft Treasure Hunt — Crash Report\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Python: {sys.version}\n")
        f.write(f"Pygame: {pygame.version.ver}\n")
        f.write(f"Exception: {type(exc).__name__}: {exc}\n")
        f.write("-" * 60 + "\n")
        traceback.print_exc(file=f)
    return log_path


# =============================================================================
# 主入口
# =============================================================================

def main():
    """游戏主入口函数。

    流程：
    1. 环境自检 — 任一检查失败则终止
    2. 引擎初始化（含全部 9 个场景的自动注册）
    3. 场景注册完整性校验（仅警告，不阻塞）
    4. 进入阻塞式主循环（外部 quit_game() 或异常可退出）
    """
    # ---- 1. 环境自检 ----
    # 仅 Python 与 Pygame 版本为硬性门槛；资产目录缺失由 AssetManager 优雅降级
    print("[Microsoft Treasure Hunt] 正在启动...")
    all_ok = True
    for name, detail, ok in check_environment():
        icon = "OK" if ok else "FAIL"
        print(f"  [{icon}] {name}: {detail}")
        # 只有前 2 项（Python 版本、Pygame 版本）是硬性门槛
        if not ok and name in ("Python 版本", "Pygame 版本"):
            all_ok = False
    if not all_ok:
        print("环境检查未通过，即将退出。")
        sys.exit(1)

    # ---- 2. 引擎初始化（含场景自举注册） ----
    from src.game_manager import GameManager

    game = GameManager.get_instance()
    game.init_engine()

    # ---- 3. 场景注册校验 ----
    reg_errors = verify_screen_registrations()
    if reg_errors:
        for err in reg_errors:
            print(f"  [WARN] 场景注册 — {err}")
    else:
        count = len(game.screen_manager.screens)
        print(f"  [OK] 场景注册: 全部 {count} 个场景已就绪")

    # ---- 4. 主循环（异常崩溃转储保护） ----
    print("[Microsoft Treasure Hunt] 进入游戏主循环")
    game.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log_path = write_crash_log(exc)
        print(f"[FATAL] 游戏崩溃，详细信息已记录至: {log_path}")
        sys.exit(1)
