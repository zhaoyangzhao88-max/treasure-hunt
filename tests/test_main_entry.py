"""入口主程序引导自检验证脚本 — Microsoft Treasure Hunt

验证目标：
1. check_environment() 返回正确的 (name, detail, ok) 三元组格式
2. Python 版本检查 (>= 3.8) 通过
3. Pygame 版本检查通过
4. REQUIRED_SCREENS 精确覆盖全部 9 个 GameState 枚举值（无遗漏无多余）
5. init_engine 后全部 9 个场景均已注册且类型正确
6. write_crash_log() 正确写入包含异常详细信息的 .log 文件
7. 未调用 init_engine 时 verify_screen_registrations() 返回错误
"""

import os
import sys

# 设置 headless 驱动必须在 pygame.init() 之前
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 初始化 Pygame（display + font + mixer，与 test_game_manager.py 一致）
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

# 从 main.py 导入待测函数与常量
from main import (
    check_environment,
    verify_screen_registrations,
    write_crash_log,
    REQUIRED_SCREENS,
    CRASH_LOG_DIR,
)
from src.config import GameState
from src.game_manager import GameManager


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------

def _reset_singletons():
    """重置全部单例以获得干净的测试环境。"""
    GameManager._instance = None
    from src.asset_manager import AssetManager
    AssetManager._instance = None


def _cleanup_crash_logs():
    """移除测试期间产生的临时崩溃日志文件。"""
    if not os.path.isdir(CRASH_LOG_DIR):
        return
    for fname in os.listdir(CRASH_LOG_DIR):
        if fname.startswith("crash_") and fname.endswith(".log"):
            try:
                os.remove(os.path.join(CRASH_LOG_DIR, fname))
            except OSError:
                pass
    try:
        os.rmdir(CRASH_LOG_DIR)
    except OSError:
        pass


# ==========================================================================
# 测试 1: check_environment 返回值格式
# ==========================================================================

def test_check_environment_returns_tuples():
    """check_environment() 应返回 list[tuple[str, str, bool]]，至少 2 项。"""
    results = check_environment()

    assert isinstance(results, list), f"应为 list，得到 {type(results)}"
    assert len(results) >= 2, f"应至少 2 项检查，得到 {len(results)}"

    for item in results:
        assert isinstance(item, tuple), f"每项应为 tuple，得到 {type(item)}"
        assert len(item) == 3, f"每项应有 3 个元素，得到 {len(item)}"
        name, detail, ok = item
        assert isinstance(name, str), f"name 应为 str，得到 {type(name)}"
        assert isinstance(detail, str), f"detail 应为 str，得到 {type(detail)}"
        assert isinstance(ok, bool), f"ok 应为 bool，得到 {type(ok)}"

    print("[PASS] test_check_environment_returns_tuples")


# ==========================================================================
# 测试 2: Python 版本检查
# ==========================================================================

def test_python_version_check():
    """Python 版本检查应通过（要求 >= 3.8）。"""
    results = check_environment()
    py_entry = next(r for r in results if "Python" in r[0])
    name, detail, ok = py_entry
    assert ok is True, f"Python 版本检查失败: {name}={detail}"

    print("[PASS] test_python_version_check")


# ==========================================================================
# 测试 3: Pygame 检查
# ==========================================================================

def test_pygame_check():
    """Pygame 检查应通过（pygame 可导入且版本非空）。"""
    results = check_environment()
    pg_entry = next(r for r in results if "Pygame" in r[0])
    name, detail, ok = pg_entry
    assert ok is True, f"Pygame 检查失败: {name}={detail}"
    assert len(detail) > 0, "Pygame 版本号不应为空"

    print("[PASS] test_pygame_check")


# ==========================================================================
# 测试 4: REQUIRED_SCREENS 覆盖所有 9 个 GameState
# ==========================================================================

def test_required_screens_covers_all_states():
    """REQUIRED_SCREENS 应覆盖除 MAP_EDITOR 外的全部 GameState 枚举值。"""
    registered_states = {state for state, _ in REQUIRED_SCREENS}
    # MAP_EDITOR 不在 REQUIRED_SCREENS 中（由 game_manager.py 单独注册）
    all_states = {s for s in GameState if s != GameState.MAP_EDITOR}

    missing = all_states - registered_states
    extra = registered_states - all_states

    assert not missing, f"REQUIRED_SCREENS 缺少: {[s.value for s in sorted(missing, key=lambda s: s.value)]}"
    assert not extra, f"REQUIRED_SCREENS 含额外值: {[s.value for s in sorted(extra, key=lambda s: s.value)]}"
    assert len(REQUIRED_SCREENS) == len(all_states), (
        f"应恰好 {len(all_states)} 项，得到 {len(REQUIRED_SCREENS)}"
    )

    print("[PASS] test_required_screens_covers_all_states")


# ==========================================================================
# 测试 5: init_engine 后全部 9 个场景已注册
# ==========================================================================

def test_all_screens_registered_after_init():
    """init_engine(headless=True) 后，全部 10 个场景已注册且类型正确。"""
    _reset_singletons()
    mgr = GameManager.get_instance()
    mgr.init_engine(headless=True)

    errors = verify_screen_registrations()
    assert len(errors) == 0, f"场景注册错误: {errors}"

    assert len(mgr.screen_manager.screens) == 10, (
        f"ScreenManager 包含 {len(mgr.screen_manager.screens)} 个场景，期望 10"
    )

    print("[PASS] test_all_screens_registered_after_init")


# ==========================================================================
# 测试 6: 崩溃日志转储
# ==========================================================================

def test_crash_dump_writes_log():
    """write_crash_log() 应写入包含异常类型与回溯的 .log 文件。"""
    _cleanup_crash_logs()

    test_msg = "测试崩溃转储"
    try:
        raise ValueError(test_msg)
    except ValueError as exc:
        log_path = write_crash_log(exc)

    assert os.path.exists(log_path), f"日志文件应存在: {log_path}"
    assert log_path.endswith(".log"), f"扩展名应为 .log，得到 {log_path}"
    assert CRASH_LOG_DIR in log_path, f"路径应包含 {CRASH_LOG_DIR}"

    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 内容校验
    assert "Crash Report" in content, "日志应含标题"
    assert "Traceback" in content or "traceback" in content, "日志应含回溯信息"
    assert "ValueError" in content, "日志应含异常类型"
    assert test_msg in content, "日志应含异常消息"
    assert "Python" in content, "日志应含 Python 版本"
    assert "Pygame" in content, "日志应含 Pygame 版本"

    # 清理文件
    os.remove(log_path)

    print("[PASS] test_crash_dump_writes_log")


# ==========================================================================
# 测试 7: 未初始化时 verify_screen_registrations 应报错
# ==========================================================================

def test_verify_without_init():
    """未调用 init_engine 时，verify_screen_registrations() 应返回错误。"""
    _reset_singletons()
    GameManager.get_instance()  # 创建实例但不 init

    errors = verify_screen_registrations()
    assert len(errors) >= 1, "未初始化时应返回至少 1 个错误"

    print("[PASS] test_verify_without_init")


# ==========================================================================
# 清理
# ==========================================================================

def teardown():
    """清理单例与 Pygame 资源。"""
    GameManager._instance = None
    from src.asset_manager import AssetManager
    AssetManager._instance = None
    pygame.quit()


# ==========================================================================
# 入口
# ==========================================================================

if __name__ == "__main__":
    try:
        test_check_environment_returns_tuples()
        test_python_version_check()
        test_pygame_check()
        test_required_screens_covers_all_states()
        test_all_screens_registered_after_init()
        test_crash_dump_writes_log()
        test_verify_without_init()
        print("\n=== ALL TESTS PASSED ===")
    finally:
        teardown()
        _cleanup_crash_logs()
