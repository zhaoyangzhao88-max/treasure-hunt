#!/usr/bin/env python3
"""诊断脚本 — Microsoft Treasure Hunt 黑屏问题全自动诊断工具

运行方式:
    python diagnose_game.py

功能:
    1. 重定向 print/stderr 到内存日志
    2. Monkey-patch GameManager/ScreenManager 拦截转场状态
    3. 模拟 60 帧主循环（含首次切换到 MAIN_MENU）
    4. 生成 run_diagnostics.md 诊断报告
    5. 自动退出 Pygame

用法::
    $ python diagnose_game.py
    # 等 60 帧 → 自动退出 → 查看 run_diagnostics.md
"""

import io
import os
import sys
import time
import traceback
from datetime import datetime

# =============================================================================
# 1. 日志重定向 — 捕获所有 print/stderr
# =============================================================================

_log_buffer: list[str] = []
_original_stdout = sys.stdout
_original_stderr = sys.stderr


class _LogCapture(io.StringIO):
    """StringIO 子类，写入时同时在内存列表和原始流输出（保持终端可见）。

    自动处理 GBK 终端编码问题——无法编码的字符用 ``?`` 替换。
    """

    def __init__(self, stream_type: str = "stdout"):
        super().__init__()
        self._stream_type = stream_type

    def write(self, s: str):
        if s.strip():
            _log_buffer.append(f"[{self._stream_type}] {s.rstrip()}")
        # 用 'replace' 处理终端编码，避免 GBK 上 UnicodeEncodeError
        encoded = s.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8"
        )
        if self._stream_type == "stdout":
            _original_stdout.write(encoded)
            _original_stdout.flush()
        else:
            _original_stderr.write(encoded)
            _original_stderr.flush()

    def flush(self):
        if self._stream_type == "stdout":
            _original_stdout.flush()
        else:
            _original_stderr.flush()


def _start_log_capture():
    """重定向 sys.stdout/sys.stderr 到 _LogCapture。"""
    sys.stdout = _LogCapture("stdout")
    sys.stderr = _LogCapture("stderr")


def _stop_log_capture():
    """恢复原始 stdout/stderr。"""
    sys.stdout = _original_stdout
    sys.stderr = _original_stderr


# =============================================================================
# 2. 数据收集容器
# =============================================================================

class DiagnoseData:
    """所有拦截数据的集中容器。"""

    def __init__(self):
        # 环境信息
        self.system_info: dict = {}

        # 自举注册列表
        self.registered_screens: list[dict] = []
        self.register_errors: list[str] = []

        # 场景切换日志
        self.switch_log: list[dict] = []

        # 帧状态追踪表 (60 帧)
        self.frame_trace: list[dict] = []

        # 捕获的异常回溯
        self.exceptions_caught: list[str] = []

        # 渲染钩子数据
        self.render_fade_data: list[dict] = []

    def add_exception(self, context: str, exc_info: tuple):
        """记录异常回溯。"""
        tb_text = "".join(traceback.format_exception(*exc_info))
        self.exceptions_caught.append(f"--- {context} ---\n{tb_text}")


_diag = DiagnoseData()


# =============================================================================
# 3. Monkey-patch GameManager
# =============================================================================

def _patch_screen_manager_instance(sm):
    """对 ScreenManager 的 *实例* 注入诊断拦截钩子（避免类级修补的导入歧义问题）。

    在 init_engine() 之后、switch_screen() 之前调用，直接替换实例方法。
    """
    _orig_switch = sm.switch_screen
    def _patched_switch(new_state, data_payload=None):
        entry = {
            "target_state": new_state.value if hasattr(new_state, 'value') else str(new_state),
            "payload_keys": list(data_payload.keys()) if data_payload else [],
            "pre_transition_state": sm.transition_state,
            "pre_current_state": sm.current_state.value if sm.current_state else None,
        }
        _diag.switch_log.append(entry)
        try:
            _orig_switch(new_state, data_payload)
        except Exception as e:
            _diag.add_exception(f"switch_screen({new_state})", sys.exc_info())
            raise
    sm.switch_screen = _patched_switch

    _orig_update = sm.update
    def _patched_update(dt: float):
        pre_state = sm.transition_state
        pre_timer = sm.fade_timer
        hd = sm.fade_duration / 2.0
        if pre_state == "FADING_OUT":
            frac = max(0.0, min(1.0, pre_timer / hd if hd > 0 else 1.0))
            pre_alpha = int(frac * 255)
        elif pre_state == "FADING_IN":
            frac = max(0.0, min(1.0, pre_timer / hd if hd > 0 else 1.0))
            pre_alpha = int((1.0 - frac) * 255)
        else:
            pre_alpha = 0
        try:
            _orig_update(dt)
        except Exception as e:
            _diag.add_exception(f"ScreenManager.update(dt={dt:.4f})", sys.exc_info())
            sm.transition_state = "NONE"
            sm.fade_timer = 0.0
        current_screen_name = type(sm.current_screen).__name__ if sm.current_screen else "None"
        _diag.render_fade_data.append({
            "screen": current_screen_name,
            "transition_state": sm.transition_state,
            "fade_timer": round(sm.fade_timer, 4),
            "pre_alpha": pre_alpha,
            "post_alpha": 0,
        })
    sm.update = _patched_update

    _orig_render = sm.render
    def _patched_render(surface):
        try:
            _orig_render(surface)
        except Exception as e:
            _diag.add_exception(f"ScreenManager.render", sys.exc_info())
            return
        if sm.transition_state != "NONE":
            hd = sm.fade_duration / 2.0
            frac = max(0.0, min(1.0, sm.fade_timer / hd if hd > 0 else 1.0))
            if sm.transition_state == "FADING_OUT":
                alpha = int(frac * 255)
            else:
                alpha = int((1.0 - frac) * 255)
            alpha = max(0, min(255, alpha))
        else:
            alpha = 0
        if _diag.render_fade_data:
            _diag.render_fade_data[-1]["post_alpha"] = alpha
            _diag.render_fade_data[-1]["black_overlay_rendered"] = (alpha > 0)
    sm.render = _patched_render


def _safe_get_display_driver() -> str:
    """安全获取显示驱动名称。"""
    try:
        import pygame
        return pygame.display.get_driver()
    except Exception:
        return "unknown"


def _safe_mixer_check() -> bool:
    """安全检查混音器状态。"""
    try:
        import pygame
        return pygame.mixer.get_init() is not None
    except Exception:
        return False


def _scan_registered_screens(gm):
    """扫描 GameManager 的 ScreenManager 已注册场景列表。"""
    try:
        sm = gm.screen_manager
        if sm is not None:
            from src.config import GameState
            for gs in GameState:
                registered = gs in sm.screens
                screen_type = type(sm.screens[gs]).__name__ if registered else "N/A"
                _diag.registered_screens.append({
                    "state": gs.value,
                    "registered": registered,
                    "type": screen_type,
                })
    except Exception as e:
        _diag.register_errors.append(f"scan screens exception: {e}")
    _diag.system_info["engine_initialized"] = True
    _diag.system_info["display_driver"] = _safe_get_display_driver()
    _diag.system_info["mixer_initialized"] = _safe_mixer_check()


def _patch_menu_render(menu_screen):
    """修补 MainMenuScreen 实例的 render 方法——记录调用计数。"""
    _orig_render = menu_screen.render
    def _patched_render(surface):
        _diag.system_info["menu_render_called_count"] = \
            _diag.system_info.get("menu_render_called_count", 0) + 1
        _orig_render(surface)
    menu_screen.render = _patched_render


# =============================================================================
# 4. 模拟 60 帧主循环
# =============================================================================

def _simulate_60_frames():
    """模拟运行 60 帧，记录每帧状态。"""
    import pygame
    from src.game_manager import GameManager
    from src.config import FPS, SCREEN_WIDTH, SCREEN_HEIGHT, GameState

    gm = GameManager.get_instance()

    # ---- 4a. 初始化引擎（非 headless，打开真实窗口） ----
    _print_ascii("[DIAG] Initializing engine...")
    try:
        gm.init_engine(headless=False)
    except Exception as e:
        _diag.add_exception("GameManager.init_engine()", sys.exc_info())
        _print_ascii(f"[DIAG] FATAL: Engine init failed: {e}")
        return False

    _print_ascii(f"[DIAG] Engine initialized. Display driver: {_safe_get_display_driver()}")
    _print_ascii(f"[DIAG] Mixer state: {'Ready' if _safe_mixer_check() else 'Unavailable'}")

    # 扫描注册列表
    _scan_registered_screens(gm)

    # ---- 4b. 实例级修补 ScreenManager + 修补 MainMenuScreen ----
    _patch_screen_manager_instance(gm.screen_manager)

    # ---- 4c. 首次切换到 MAIN_MENU ----
    _print_ascii("[DIAG] Switching to MAIN_MENU...")
    try:
        gm.screen_manager.switch_screen(GameState.MAIN_MENU)
    except Exception as e:
        _diag.add_exception("switch_screen(MAIN_MENU) initial", sys.exc_info())
        _print_ascii(f"[DIAG] FATAL: Initial screen switch failed: {e}")
        return False

    # ---- 修补 MainMenuScreen.render 实例 ----
    if gm.screen_manager.current_screen is not None:
        _patch_menu_render(gm.screen_manager.current_screen)

    # ---- 4c. 记录初始窗口状态（帧0） ----
    _diag.system_info["screen_size"] = f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}"
    _diag.system_info["window_caption"] = pygame.display.get_caption()[0]

    # ---- 4d. 60 帧模拟循环 ----
    _print_ascii("[DIAG] Starting 60-frame simulation loop...")
    dt_sum = 0.0
    frame_count = 0

    for frame in range(60):
        frame_num = frame + 1
        dt_ms = gm.clock.tick(FPS)
        dt = dt_ms / 1000.0
        dt_sum += dt
        frame_count += 1

        # 清空事件队列（不处理具体事件，避免意外关闭）
        pygame.event.pump()

        # 捕获 update/render 过程中的异常
        update_ok = True
        render_ok = True
        exc_in_frame = []

        try:
            # ScreenManager.update 内部已包 try-except，但要防外部异常
            gm.screen_manager.update(dt)
        except Exception as e:
            update_ok = False
            tb = traceback.format_exc()
            exc_in_frame.append(f"update异常: {type(e).__name__}: {e}\n{tb}")

        try:
            gm.screen_manager.render(gm.screen)
            if frame_num <= 2:
                # 前 2 帧尝试 flip（确认窗口显示）
                pygame.display.flip()
        except Exception as e:
            render_ok = False
            tb = traceback.format_exc()
            exc_in_frame.append(f"render异常: {type(e).__name__}: {e}\n{tb}")

        # 收集帧状态
        sm = gm.screen_manager
        screen_name = type(sm.current_screen).__name__ if sm.current_screen else "None"

        # 计算帧 alpha（与 render 钩子冗余校验）
        alpha_val = 0
        if sm.transition_state != "NONE":
            hd = sm.fade_duration / 2.0
            frac = max(0.0, min(1.0, sm.fade_timer / hd if hd > 0 else 1.0))
            if sm.transition_state == "FADING_OUT":
                alpha_val = int(frac * 255)
            else:
                alpha_val = int((1.0 - frac) * 255)
            alpha_val = max(0, min(255, alpha_val))

        frame_entry = {
            "frame": frame_num,
            "screen": screen_name,
            "transition_state": sm.transition_state,
            "fade_timer": round(sm.fade_timer, 4),
            "alpha": alpha_val,
            "dt": round(dt, 4),
            "update_ok": update_ok,
            "render_ok": render_ok,
            "exceptions": exc_in_frame if exc_in_frame else None,
        }
        _diag.frame_trace.append(frame_entry)

        # 将 render_fade_data 中的对应条目与帧号关联
        if _diag.render_fade_data:
            _diag.render_fade_data[-1]["frame"] = frame_num

        if frame_num <= 3 or frame_num % 10 == 0:
            print(f"[DIAG] Frame {frame_num:2d}: "
                  f"screen={screen_name:20s} "
                  f"t_state={sm.transition_state:10s} "
                  f"timer={sm.fade_timer:.4f} "
                  f"alpha={alpha_val:3d} "
                  f"{'!!' if exc_in_frame else 'OK'}")

    # 平均 FPS
    avg_fps = frame_count / dt_sum if dt_sum > 0 else 0
    _diag.system_info["avg_fps"] = round(avg_fps, 1)
    _diag.system_info["total_frames_simulated"] = frame_count
    print(f"[DIAG] 模拟完成。平均 FPS: {avg_fps:.1f}")
    return True


# =============================================================================
# 5. 生成 Markdown 诊断报告
# =============================================================================

def _generate_report():
    """将 _diag 中的所有数据格式化为 run_diagnostics.md。"""
    import pygame

    lines = []
    _w = lambda s="": lines.append(s)

    # ===== 标题 =====
    _w("# Microsoft Treasure Hunt — 黑屏诊断报告")
    _w()
    _w(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _w(f"**模拟帧数**: {_diag.system_info.get('total_frames_simulated', 0)}")
    _w()

    # ===== 1. 系统环境 =====
    _w("## 1️⃣ 系统环境")
    _w()
    _w("| 项目 | 值 |")
    _w("|------|-----|")
    _w(f"| 操作系统 | {sys.platform} / {os.name} |")
    _w(f"| Python 版本 | {sys.version.split()[0]} |")
    _w(f"| Pygame 版本 | {pygame.version.ver} |")
    _w(f"| SDL 版本 | {'.'.join(str(x) for x in pygame.get_sdl_version())} |")
    _w(f"| 显示驱动 | {_diag.system_info.get('display_driver', 'N/A')} |")
    _w(f"| 混音器就绪 | {_diag.system_info.get('mixer_initialized', False)} |")
    _w(f"| 窗口尺寸 | {_diag.system_info.get('screen_size', 'N/A')} |")
    _w(f"| 窗口标题 | {_diag.system_info.get('window_caption', 'N/A')} |")
    _w(f"| 引擎初始化成功 | {_diag.system_info.get('engine_initialized', False)} |")
    _w(f"| 平均 FPS | {_diag.system_info.get('avg_fps', 'N/A')} |")
    _w()

    # ===== 2. 自举注册列表 =====
    _w("## 2️⃣ 自举注册列表")
    _w()
    registered_count = sum(1 for r in _diag.registered_screens if r["registered"])
    _w(f"**注册状态**: {registered_count}/{len(_diag.registered_screens)} 场景已注册")
    _w()
    _w("| GameState | 已注册 | 实例类型 |")
    _w("|-----------|--------|---------|")
    for r in _diag.registered_screens:
        status_icon = "✅" if r["registered"] else "❌"
        _w(f"| {r['state']} | {status_icon} | {r['type']} |")
    if _diag.register_errors:
        _w()
        _w("### 注册异常")
        for err in _diag.register_errors:
            _w(f"- `{err}`")
    _w()

    # ===== 3. 场景切换日志 =====
    _w("## 3️⃣ 场景切换记录")
    _w()
    if _diag.switch_log:
        _w("| # | 目标状态 | Payload Keys | 切换前 transition_state | 切换前 current_state |")
        _w("|---|----------|--------------|------------------------|---------------------|")
        for i, sw in enumerate(_diag.switch_log):
            _w(f"| {i + 1} | {sw['target_state']} | {sw['payload_keys']} | {sw['pre_transition_state']} | {sw['pre_current_state']} |")
    else:
        _w("*(无场景切换记录)*")
    _w()

    # ===== 4. 帧状态追踪表 =====
    _w("## 4️⃣ 帧状态追踪表")
    _w()
    _w("| 帧号 | 活跃场景 | transition_state | fade_timer | 遮罩 Alpha | dt(ms) | update正常 | render正常 | 异常 |")
    _w("|------|---------|-----------------|-----------|-----------|--------|-----------|-----------|------|")
    for fe in _diag.frame_trace:
        exc_mark = "⚠️" if fe["exceptions"] else "—"
        _w(f"| {fe['frame']:3d} | {fe['screen']:20s} | {fe['transition_state']:10s} | {fe['fade_timer']:.4f} | "
          f"{fe['alpha']:3d} | {fe['dt']*1000:.1f} | {'✓' if fe['update_ok'] else '✗'} | "
          f"{'✓' if fe['render_ok'] else '✗'} | {exc_mark} |")
    _w()

    # ===== 5. Render 遮罩详细数据 =====
    _w("## 5️⃣ Render 遮罩 Alpha 详细记录")
    _w()
    _w("（每帧 update 后 + render 后的冗余校验）")
    _w()
    _w("| # | Frame | 场景 | transition_state | fade_timer | pre_alpha | post_alpha | 黑罩渲染 |")
    _w("|---|-------|------|-----------------|-----------|----------|-----------|---------|")
    for i, rd in enumerate(_diag.render_fade_data):
        frame_str = str(rd.get("frame", "?"))
        overlay_str = "✅" if rd.get("black_overlay_rendered") else ("—" if rd["post_alpha"] == 0 else "?")
        _w(f"| {i + 1} | {frame_str:>3s} | {rd['screen']:20s} | {rd['transition_state']:10s} | "
          f"{rd['fade_timer']:.4f} | {rd['pre_alpha']:3d} | {rd['post_alpha']:3d} | {overlay_str} |")
    _w()

    # ===== 6. 捕获的异常与警告 =====
    _w("## 6️⃣ 捕获的异常与警告")
    _w()
    all_logs = [l for l in _log_buffer if "WARNING" in l or "ERROR" in l or "[CRITICAL]" in l]
    if all_logs:
        _w("### 日志中的警告/错误")
        _w()
        _w("```")
        for log in all_logs:
            _w(log)
        _w("```")
        _w()
    if _diag.exceptions_caught:
        _w("### 异常回溯")
        _w()
        for exc in _diag.exceptions_caught:
            _w("```")
            _w(exc)
            _w("```")
            _w()
    if not all_logs and not _diag.exceptions_caught:
        _w("*(未捕获到任何异常或警告)*")
        _w()

    # ===== 7. 菜单渲染统计 =====
    _w("## 7️⃣ 菜单渲染统计")
    _w()
    menu_count = _diag.system_info.get("menu_render_called_count", 0)
    _w(f"- `MainMenuScreen.render` 被调用次数: {menu_count}")
    # 检查最后一帧的场景
    if _diag.frame_trace:
        last_frame = _diag.frame_trace[-1]
        menu_active = "MainMenuScreen" in last_frame["screen"]
        _w(f"- 最后一帧活跃场景: {last_frame['screen']}")
        _w(f"- 菜单是否为活跃场景: {'✅ 是' if menu_active else '❌ 否，可能根本未渲染菜单'}")
    _w()

    # ===== 8. 诊断结论 =====
    _w("## 8️⃣ 诊断结论")
    _w()
    _w("### 观测摘要")
    _w()
    # 自动分析
    conclusions = []

    # 检查转场状态
    final_ts = _diag.frame_trace[-1]["transition_state"] if _diag.frame_trace else "N/A"
    if final_ts != "NONE":
        conclusions.append(f"⚠️ **转场状态异常**: 最后一帧 transition_state = {final_ts}，非正常 NONE。"
                           "转场可能未完成导致黑罩残留。")
    else:
        conclusions.append("✅ **转场状态正常**: 末帧 transition_state = NONE，转场已完成。")

    # 检查 alpha
    final_alpha = _diag.frame_trace[-1]["alpha"] if _diag.frame_trace else 255
    if final_alpha > 0:
        conclusions.append(f"⚠️ **遮罩残影**: 末帧 alpha = {final_alpha}，黑罩未完全消失。")
    else:
        conclusions.append("✅ **遮罩正常**: 末帧 alpha = 0，黑罩已消退。")

    # 检查注册
    reg_count = sum(1 for r in _diag.registered_screens if r["registered"])
    if reg_count < 10:
        conclusions.append(f"❌ **场景注册不全**: 仅 {reg_count}/10 场景注册成功。")
    else:
        conclusions.append("✅ **场景注册**: 全部 10 场景注册成功。")

    # 检查异常
    if _diag.exceptions_caught:
        conclusions.append(f"⚠️ **运行期异常**: 捕获到 {len(_diag.exceptions_caught)} 个异常，请查看 §6。")

    # 检查菜单渲染
    if menu_count == 0:
        conclusions.append("❌ **菜单未渲染**: MainMenuScreen.render 从未被调用！"
                           "主循环可能未正确路由到 MainMenuScreen。")
    elif menu_count > 0:
        conclusions.append(f"✅ **菜单渲染**: MainMenuScreen.render 被调用 {menu_count} 次。")

    # 检查帧数
    total_frames = _diag.system_info.get("total_frames_simulated", 0)
    if total_frames < 60:
        conclusions.append(f"⚠️ **帧数不足**: 仅模拟 {total_frames}/60 帧，循环可能被异常中断。")

    # 检查切换日志
    if not _diag.switch_log:
        conclusions.append("❌ **无场景切换**: switch_screen 从未调用，引擎处于无活跃场景状态。")

    for c in conclusions:
        _w(f"- {c}")
    _w()

    _w("### 黑屏根因推测")
    _w()
    if final_ts == "FADING_OUT" and final_alpha >= 255:
        _w("**最可能原因**: 转场卡在 FADING_OUT 态。建议检查 `fade_duration` 是否被意外修改，"
           "或 `_complete_transition_immediately` 是否在某处抛异常。")
    elif menu_count == 0 and _diag.switch_log:
        _w("**最可能原因**: switch_screen 调用后场景未激活，`current_screen` 仍为 None。"
           "可能 `register_screen` 或 `on_enter` 中抛出了被静默吞掉的异常。")
    elif menu_count > 0 and final_alpha == 0:
        _w("**最可能原因**: 转场和菜单渲染均正常，但 MainMenuScreen.render 的内容（背景填充/标题/按钮）"
           "未被正确显示到窗口。可能原因：")
        _w("1. `display.flip()` 被吞掉或帧缓存被覆盖")
        _w("2. PyInstaller 打包后字体/图片资源路径异常导致字体渲染失败（fill(BLACK)后无内容）")
        _w("3. `pygame.display.set_mode` 创建了黑色初始表面且未被覆盖")
    elif _diag.exceptions_caught:
        _w("**最可能原因**: 运行期存在未处理异常（见 §6），导致渲染管线中断。")
    else:
        _w("当前诊断数据不足确定根因。建议增加更多帧或检查 PyInstaller 打包后的资源路径。")

    _w()

    # ===== 9. 完整日志 =====
    _w("## 9️⃣ 完整运行日志")
    _w()
    _w("```")
    for log in _log_buffer:
        _w(log)
    _w("```")
    _w()

    # 写入文件
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_diagnostics.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n[DIAG] 诊断报告已写入: {report_path}")
    return report_path


# =============================================================================
# 6. 主入口
# =============================================================================

def _print_ascii(msg: str):
    """使用 ASCII 安全的编码打印到终端，避免 GBK 终端上 UnicodeEncodeError。"""
    encoded = (msg + "\n").encode(sys.stdout.encoding or "utf-8", errors="replace")
    _original_stdout.write(encoded.decode(sys.stdout.encoding or "utf-8"))
    _original_stdout.flush()


def main():
    """诊断流程编排入口。"""
    # 使用 ASCII-only 输出，避免 GBK 终端报错
    _print_ascii("=" * 60)
    _print_ascii("  Microsoft Treasure Hunt - Black Screen Diagnostic Tool")
    _print_ascii("=" * 60)
    _print_ascii("")

    # ---- 6a. 启动日志重定向 ----
    _start_log_capture()

    # ---- 6b. 导入 pygame（必须在补丁之前） ----
    global pygame
    import pygame

    # 收集初始环境信息
    _diag.system_info["platform"] = sys.platform
    _diag.system_info["python_version"] = sys.version.split()[0]
    _diag.system_info["pygame_version"] = pygame.version.ver
    try:
        _diag.system_info["sdl_version"] = ".".join(str(x) for x in pygame.get_sdl_version())
    except Exception:
        _diag.system_info["sdl_version"] = "unknown"
    _diag.system_info["cwd"] = os.getcwd()
    _diag.system_info["script_dir"] = os.path.dirname(os.path.abspath(__file__))

    # ---- 6c. 模拟 60 帧（内含实例级修补） ----
    success = _simulate_60_frames()
    if not success:
        _print_ascii("[DIAG] Simulation exited abnormally, still generating partial report...")

    # ---- 6e. 生成报告 ----
    report_path = _generate_report()

    # ---- 6f. 停止日志重定向 + 退出 Pygame ----
    _stop_log_capture()
    try:
        pygame.quit()
    except Exception:
        pass

    # ---- 6g. 打印前 15 帧摘要 ----
    _print_ascii("")
    _print_ascii("=" * 60)
    _print_ascii("  First 15 Frame Status Summary")
    _print_ascii("=" * 60)
    _print_ascii("")
    header = f"{'Frame':>4s} | {'Screen':20s} | {'Transition':10s} | {'fade_timer':>10s} | {'Alpha':>5s} | {'Exc':>4s}"
    _print_ascii(header)
    _print_ascii("-" * 65)
    for fe in _diag.frame_trace[:15]:
        exc_mark = "!!" if fe["exceptions"] else "--"
        line = (f"{fe['frame']:4d} | {fe['screen']:20s} | {fe['transition_state']:10s} | "
                f"{fe['fade_timer']:10.4f} | {fe['alpha']:5d} | {exc_mark:>4s}")
        _print_ascii(line)
    _print_ascii("")
    _print_ascii(f"[OK] Diagnostic report generated: {report_path}")
    _print_ascii("    Please share this report content with the developer for analysis.")
    _print_ascii("")

    return 0


if __name__ == "__main__":
    sys.exit(main())