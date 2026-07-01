#!/usr/bin/env python
"""一键终端运行全自动 AI 仿真探险测试与冒烟压力测试。

用法::

    # 默认跑 3 关
    python run_autoplay_test.py

    # 跑 5 关
    python run_autoplay_test.py --levels 5
"""

import argparse
import os
import sys
import traceback


def _print_banner():
    """打印启动横幅。"""
    print("=" * 62)
    print("  Microsoft Treasure Hunt — AI Autoplay Stress Test")
    print("=" * 62)


def _print_green(msg: str):
    """打印绿色成功消息。"""
    print(f"\033[92m[SUCCESS] {msg}\033[0m")


def _print_red(msg: str):
    """打印红色错误消息。"""
    print(f"\033[91m[  FAIL] {msg}\033[0m")


def _print_gold(msg: str):
    """打印金色完成消息。"""
    print(f"\033[93m[FINISH ] {msg}\033[0m")


def _print_cyan(msg: str):
    """打印青色信息消息。"""
    print(f"\033[96m[  INFO] {msg}\033[0m")


def main():
    parser = argparse.ArgumentParser(
        description="Microsoft Treasure Hunt — AI Autoplay Stress Test"
    )
    parser.add_argument(
        "--levels",
        type=int,
        default=3,
        help="Number of levels to play through (default: 3)",
    )
    args = parser.parse_args()
    max_levels = args.levels

    _print_banner()
    _print_cyan(f"Target: {max_levels} level(s)")

    # ---- Headless 初始化 ----
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
    pygame.font.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from src.game_manager import GameManager
    from src.playtest_harness import PlaytestHarness
    from src.config import GameState

    # 重置单例
    GameManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    # 确保从主菜单开始
    gm.screen_manager.switch_screen(GameState.MAIN_MENU)

    # 实例化仿真引擎
    harness = PlaytestHarness(gm, max_levels=max_levels)

    # ---- 应力主循环 ----
    max_frames = 1500
    frame_count = 0
    prev_level_completed = 0

    _print_cyan("Starting stress loop...")

    for frame_count in range(1, max_frames + 1):
        try:
            result = harness.step_simulation()

            # === 关卡通关节奏 ===
            if result == "LEVEL_COMPLETED":
                _print_green(
                    f"Level {harness.levels_completed} "
                    f"Cleared! (Total gold: {harness.total_gold_collected})"
                )

            # === 死亡事件 ===
            elif result == "DIED":
                _print_red(
                    f"Player fallen. Restarting from Level 1. "
                    f"(Run #{harness.runs_played})"
                )

            elif result == "DIED_REVIVED":
                _print_red(
                    f"Player fallen — Amulet consumed. Reviving at previous shop."
                )

            # === 成功条件：通关数达到目标 ===
            if harness.levels_completed >= max_levels:
                _print_gold(
                    f"AI completed the playthrough successfully "
                    f"without any crashes. "
                    f"(Levels: {harness.levels_completed}, "
                    f"Runs: {harness.runs_played}, "
                    f"Gold: {harness.total_gold_collected})"
                )
                _print_cyan(f"Total simulation frames: {frame_count}")
                sys.exit(0)

        except Exception:
            _print_red(f"Crash detected at frame {frame_count + 1}!")
            traceback.print_exc()
            # 写入崩溃日志
            crash_log = f"crash_report_frame_{frame_count + 1}.log"
            with open(crash_log, "w", encoding="utf-8") as f:
                f.write(f"Frame: {frame_count + 1}\n")
                f.write(f"State: {gm.screen_manager.current_state}\n")
                traceback.print_exc(file=f)
            _print_red(f"Crash log written to {crash_log}")
            sys.exit(1)

    # ---- 超时退出 ----
    _print_red(
        f"Timeout: {max_frames} frames exhausted "
        f"(cleared {harness.levels_completed}/{max_levels} levels)."
    )
    _print_cyan(
        f"Stats — Runs: {harness.runs_played}, "
        f"Gold: {harness.total_gold_collected}"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
