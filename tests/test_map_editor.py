"""测试第 57 课 — 可视化地图编辑器 MapEditorScreen

测试覆盖：
- 初始状态验证（默认网格、起点/终点、LOCK_EXIT）
- 调色盘点选笔刷切换
- 画笔拖拽涂抹（左键按下 + 移动）
- 一键导出 → CustomLevelLoader 逆向闭环一致性
- 一键清空重置

运行方式：
    python tests/test_map_editor.py
    python -m pytest tests/test_map_editor.py -v
"""

import os
import sys

# 1) 设置 headless 驱动（必须在 pygame.init 之前）
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# 2) 确保项目根可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 3) 初始化 Pygame 子系统
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

from src.game_manager import GameManager
from src.asset_manager import AssetManager
from src.config import GameState
from src.screens.map_editor_screen import (
    MapEditorScreen,
    GRID_SIZE,
    CELL_SIZE,
    GRID_OFFSET_X,
    GRID_OFFSET_Y,
    BRUSHES,
    PALETTE_OFFSET_X,
    PALETTE_OFFSET_Y,
    PALETTE_COLS,
    SLOT_W,
    SLOT_H,
    SLOT_GAP_X,
    SLOT_GAP_Y,
)
from src.custom_level_loader import CustomLevelLoader


# =============================================================================
# 辅助函数
# =============================================================================

def _fresh_editor() -> MapEditorScreen:
    """创建干净的 GameManager + MapEditorScreen 实例。"""
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)
    screen = MapEditorScreen()
    gm.screen_manager.register_screen(GameState.MAP_EDITOR, screen)
    gm.screen_manager.switch_screen(GameState.MAP_EDITOR)
    return screen


# =============================================================================
# 测试 1：初始状态
# =============================================================================

def test_initial_state():
    """验证编辑器初始状态：默认 DIRT 填充、NONE 障碍、起点/终点坐标。"""
    screen = _fresh_editor()

    # 起点终点
    assert screen.start_pos == (1, 1), f"起点应为 (1,1)，实际 {screen.start_pos}"
    assert screen.exit_pos == (10, 10), f"终点应为 (10,10)，实际 {screen.exit_pos}"

    # LOCK_EXIT 在终点格
    assert screen.grid["layer1"][10][10] == "LOCK_EXIT", (
        "终点格 layer1 应为 LOCK_EXIT"
    )

    # 初始笔刷为 DIRT（索引 0）
    assert screen.selected_brush_index == 0, (
        f"初始笔刷索引应为 0，实际 {screen.selected_brush_index}"
    )

    # 默认全 DIRT / NONE / False
    assert screen.grid["layer0"][0][0] == "DIRT"
    assert screen.grid["layer1"][0][0] == "NONE"
    assert screen.grid["layer2"][0][0] == "NONE"
    assert screen.grid["traps"][0][0] is False

    print("[PASS] test_initial_state")


# =============================================================================
# 测试 2：调色盘点选切换笔刷
# =============================================================================

def test_palette_click_selects_brush():
    """点击调色盘不同位置，验证 selected_brush_index 精确切换。"""
    screen = _fresh_editor()

    # 点击调色盘第 5 格 (索引 5 → LOCK_GREEN)
    target_1 = 5
    col = target_1 % PALETTE_COLS
    row = target_1 // PALETTE_COLS
    sx = PALETTE_OFFSET_X + col * (SLOT_W + SLOT_GAP_X) + SLOT_W // 2
    sy = PALETTE_OFFSET_Y + row * (SLOT_H + SLOT_GAP_Y) + SLOT_H // 2

    ev = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (sx, sy)}
    )
    screen.handle_event(ev)
    assert screen.selected_brush_index == target_1, (
        f"点击调色盘索引 {target_1} 后应为 {target_1}，实际 {screen.selected_brush_index}"
    )

    # 再点击调色盘第 2 格 (索引 2 → WALL)
    target_2 = 2
    col = target_2 % PALETTE_COLS
    row = target_2 // PALETTE_COLS
    sx2 = PALETTE_OFFSET_X + col * (SLOT_W + SLOT_GAP_X) + SLOT_W // 2
    sy2 = PALETTE_OFFSET_Y + row * (SLOT_H + SLOT_GAP_Y) + SLOT_H // 2

    ev2 = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (sx2, sy2)}
    )
    screen.handle_event(ev2)
    assert screen.selected_brush_index == target_2, (
        f"点击调色盘索引 {target_2} 后应为 {target_2}，实际 {screen.selected_brush_index}"
    )

    print("[PASS] test_palette_click_selects_brush")


# =============================================================================
# 测试 3：画笔涂抹
# =============================================================================

def test_drag_draw_paints_cell():
    """选择 WALL 刷，点击网格 → 验证 layer1 写入；拖动 → 验证连续涂抹。"""
    screen = _fresh_editor()

    # 选择 WALL 笔刷（索引 2）
    screen.selected_brush_index = 2

    # 点击网格 (2, 3)
    cx = GRID_OFFSET_X + 2 * CELL_SIZE + CELL_SIZE // 2
    cy = GRID_OFFSET_Y + 3 * CELL_SIZE + CELL_SIZE // 2
    down_ev = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (cx, cy)}
    )
    screen.handle_event(down_ev)

    assert screen.grid["layer1"][3][2] == "WALL", (
        "笔刷点击后 layer1[3][2] 应为 WALL"
    )
    assert screen.is_drawing is True, "左键按下后 is_drawing 应为 True"

    # 拖动到 (5, 3) — 去重保护，必须换格
    dx = GRID_OFFSET_X + 5 * CELL_SIZE + CELL_SIZE // 2
    dy = GRID_OFFSET_Y + 3 * CELL_SIZE + CELL_SIZE // 2
    move_ev = pygame.event.Event(
        pygame.MOUSEMOTION, {"pos": (dx, dy)}
    )
    screen.handle_event(move_ev)

    assert screen.grid["layer1"][3][5] == "WALL", (
        "拖动画笔后 layer1[3][5] 应为 WALL"
    )

    # 释放鼠标
    up_ev = pygame.event.Event(
        pygame.MOUSEBUTTONUP, {"button": 1, "pos": (dx, dy)}
    )
    screen.handle_event(up_ev)
    assert screen.is_drawing is False, "鼠标释放后 is_drawing 应为 False"

    print("[PASS] test_drag_draw_paints_cell")


# =============================================================================
# 测试 4：导出逆向闭环
# =============================================================================

def test_export_round_trip():
    """刷入瓦片 → 导出 JSON → CustomLevelLoader 加载 → 验证 100% 对称。"""
    import json as _json

    screen = _fresh_editor()

    # 在网格中设置已知瓦片
    screen.grid["layer0"][2][2] = "UNCOVERED"
    screen.grid["layer1"][3][4] = "WALL"
    screen.grid["layer2"][5][6] = "COIN"
    screen.grid["traps"][1][1] = True
    screen.grid["layer0"][0][0] = "UNCOVERED"

    # 导出
    screen._export_map()

    # 验证文件存在
    from src.asset_manager import get_resource_path
    export_path = get_resource_path("custom_map.json")
    assert os.path.exists(export_path), f"导出文件 {export_path} 应当存在"

    try:
        # 用 CustomLevelLoader 加载回放
        loader = CustomLevelLoader()
        game_map, start_pos, exit_pos = loader.load_from_json(export_path)

        # 元数据验证
        assert start_pos == (1, 1), f"起点应为 (1,1)，实际 {start_pos}"
        assert exit_pos == (10, 10), f"终点应为 (10,10)，实际 {exit_pos}"
        assert game_map.width == 12, f"宽度应为 12，实际 {game_map.width}"
        assert game_map.height == 12, f"高度应为 12，实际 {game_map.height}"

        # 瓦片对称性验证
        assert game_map.layer0[2][2] == "UNCOVERED", (
            f"layer0[2][2] 应为 UNCOVERED，实际 {game_map.layer0[2][2]}"
        )
        assert game_map.layer0[0][0] == "UNCOVERED", (
            f"layer0[0][0] 应为 UNCOVERED，实际 {game_map.layer0[0][0]}"
        )
        assert game_map.layer1[3][4] == "WALL", (
            f"layer1[3][4] 应为 WALL，实际 {game_map.layer1[3][4]}"
        )
        assert game_map.layer2[5][6] == "COIN", (
            f"layer2[5][6] 应为 COIN，实际 {game_map.layer2[5][6]}"
        )
        assert game_map.traps[1][1] is True, (
            f"traps[1][1] 应为 True，实际 {game_map.traps[1][1]}"
        )
    finally:
        # 清理导出文件
        if os.path.exists(export_path):
            os.remove(export_path)

    print("[PASS] test_export_round_trip")


# =============================================================================
# 测试 5：清空画布
# =============================================================================

def test_clear_resets_grid():
    """修改网格后调用 _clear_grid()，验证全部回弹为默认值。"""
    screen = _fresh_editor()

    # 先修改若干格
    screen.grid["layer0"][0][0] = "UNCOVERED"
    screen.grid["layer1"][2][2] = "WALL"
    screen.grid["layer2"][3][3] = "COIN"
    screen.grid["traps"][4][4] = True

    # 执行清空
    screen._clear_grid()

    # 验证回弹
    assert screen.grid["layer0"][0][0] == "DIRT", (
        f"清空后 layer0[0][0] 应为 DIRT，实际 {screen.grid['layer0'][0][0]}"
    )
    assert screen.grid["layer1"][2][2] == "NONE", (
        "清空后 layer1[2][2] 应为 NONE"
    )
    assert screen.grid["layer2"][3][3] == "NONE", (
        "清空后 layer2[3][3] 应为 NONE"
    )
    assert screen.grid["traps"][4][4] is False, (
        "清空后 traps[4][4] 应为 False"
    )

    # 起终点重置
    assert screen.start_pos == (1, 1), f"清空后起点应为 (1,1)，实际 {screen.start_pos}"
    assert screen.exit_pos == (10, 10), f"清空后终点应为 (10,10)，实际 {screen.exit_pos}"

    # LOCK_EXIT 恢复
    assert screen.grid["layer1"][10][10] == "LOCK_EXIT", (
        "清空后终点格 LOCK_EXIT 应恢复"
    )

    print("[PASS] test_clear_resets_grid")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    try:
        test_initial_state()
        test_palette_click_selects_brush()
        test_drag_draw_paints_cell()
        test_export_round_trip()
        test_clear_resets_grid()
        print("\n=== ALL MAP EDITOR TESTS PASSED ===")
    finally:
        GameManager._instance = None
        AssetManager._instance = None
