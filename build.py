"""Microsoft Treasure Hunt — 一键全自动打包流水线脚本

职责：
1. 安全测试自检 — 运行全量 pytest，有失败则终止打包
2. 跨平台资产分隔符适配 — Windows 用分号，Unix 用冒号
3. 调用 PyInstaller 编译为单文件（onefile + noconsole）发布包

用法::

    python build.py

输出::

    dist/MicrosoftTreasureHunt.exe  (Windows)
    dist/MicrosoftTreasureHunt      (Linux / macOS)
"""

import os
import subprocess
import sys


# =============================================================================
# 项目根目录（本文件所在目录）
# =============================================================================

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


# =============================================================================
# 1. 安全测试自检
# =============================================================================

def run_test_gate() -> bool:
    """运行全量 pytest，返回是否全部通过。

    使用 subprocess 而非 pytest.main() 直接调用，
    避免 pytest 与主进程的 sys.argv / sys.path 状态冲突。
    """
    print("=" * 60)
    print("[Build] Step 1: 运行安全测试自检 (pytest tests/) ...")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/"],
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        print("\n[Build][FAIL] 测试未通过 — 终止打包，请先修复失败测试。")
        return False

    print("\n[Build][OK] 全部测试通过 — 进入打包阶段。\n")
    return True


# =============================================================================
# 2. 跨平台资产分隔符适配
# =============================================================================

def get_add_data_param() -> str:
    """根据当前操作系统返回 PyInstaller --add-data 参数值。

    Windows 系统使用分号 ``;`` 分隔源路径与目标路径；
    Linux / macOS 等 Unix 系统使用冒号 ``:`` 分隔。
    """
    separator = ";" if sys.platform == "win32" else ":"
    add_data_param = f"assets{separator}assets"
    print(f"[Build] 检测到平台: {sys.platform} — 使用分隔符 '{separator}'")
    print(f"[Build] --add-data 参数: {add_data_param}")
    return add_data_param


# =============================================================================
# 3. 调用 PyInstaller 编译
# =============================================================================

def run_pyinstaller(add_data_param: str) -> bool:
    """调用 PyInstaller 单文件打包。

    Args:
        add_data_param: 资产目录的 --add-data 参数值。

    Returns:
        打包是否成功。
    """
    print("=" * 60)
    print("[Build] Step 2: 调用 PyInstaller 编译单文件发布包 ...")
    print("=" * 60)

    try:
        import PyInstaller.__main__
    except ModuleNotFoundError:
        print(
            "\n[Build][FAIL] 未检测到 PyInstaller — "
            "请先执行: pip install pyinstaller"
        )
        return False

    args = [
        "main.py",
        "--onefile",
        "--noconsole",
        f"--add-data={add_data_param}",
        "--paths=src",
        "--name=MicrosoftTreasureHunt",
    ]

    print(f"[Build] PyInstaller 参数: {args}\n")

    try:
        PyInstaller.__main__.run(args)
    except SystemExit as exc:
        # PyInstaller 内部通过 sys.exit() 退出；code=0 表示成功
        if exc.code != 0 and exc.code is not None:
            print(f"\n[Build][FAIL] PyInstaller 退出码: {exc.code}")
            return False

    return True


# =============================================================================
# 主流程
# =============================================================================

def main():
    """一键打包主流程：测试自检 → 跨平台适配 → PyInstaller 编译。"""
    print("[Microsoft Treasure Hunt] 一键打包流水线启动\n")

    # 1. 安全测试自检
    if not run_test_gate():
        sys.exit(1)

    # 2. 跨平台资产分隔符适配
    add_data_param = get_add_data_param()

    # 3. 调用 PyInstaller 编译
    if not run_pyinstaller(add_data_param):
        sys.exit(1)

    # 4. 发布提示
    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    print("\n" + "=" * 60)
    print("[Build][SUCCESS] 打包完成！")
    print(f"[Build] 发布包目录: {dist_dir}")
    if sys.platform == "win32":
        print(f"[Build] 可执行文件: {os.path.join(dist_dir, 'MicrosoftTreasureHunt.exe')}")
    else:
        print(f"[Build] 可执行文件: {os.path.join(dist_dir, 'MicrosoftTreasureHunt')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
