"""可视化地图编辑器 — Microsoft Treasure Hunt

第 57 课：在可视化 12x12 网格画板上用鼠标刷涂地形/障碍/实体/陷阱，
一键导出符合 CustomLevelLoader Schema 的 custom_map.json。

关键约束：
- 导出 JSON 必须与 CHAR_TO_TILE 编码完全逆向对称（TILE_TO_CHAR）
- 导出文件由 CustomLevelLoader.load_from_json() 100% 重建
"""

import json

import pygame

from src.config import SCREEN_WIDTH, SCREEN_HEIGHT, GameState, GOLD, WHITE, BLACK
from src.screens.base_screen import BaseScreen
from src.ui_helpers import Button


# =============================================================================
# 常量
# =============================================================================

GRID_SIZE = 12              # 12x12 网格
CELL_SIZE = 40              # 每格像素

# 画板区域（左侧）
GRID_OFFSET_X = 40
GRID_OFFSET_Y = 180
GRID_PIXEL_W = GRID_SIZE * CELL_SIZE   # 480
GRID_PIXEL_H = GRID_SIZE * CELL_SIZE

# 调色盘区域（右侧）
PALETTE_OFFSET_X = 560
PALETTE_OFFSET_Y = 180
PALETTE_COLS = 3
SLOT_W = 120
SLOT_H = 48
SLOT_GAP_X = 6
SLOT_GAP_Y = 6

# 底部按钮
BTN_W = 180
BTN_H = 44
BTN_Y = 680

# 调色盘背景色
PALETTE_BG = (35, 40, 55)
PALETTE_SEL_BG = (60, 70, 90)
PALETTE_BORDER = (60, 65, 80)
PALETTE_SEL_BORDER = GOLD

# 画板网格线色
GRID_LINE_COLOR = (60, 60, 80)

# =============================================================================
# 笔刷定义
# =============================================================================
# 每项：(显示名, tile_type, layer)
# layer: 0=terrain, 1=obstacle, 2=entity, "traps"=隐藏陷阱标记
BRUSHES = [
    ("泥土",     "DIRT",       0),
    ("已揭开",   "UNCOVERED",   0),
    ("墙壁",     "WALL",       1),
    ("土墙",     "DIRT_WALL",   1),
    ("红锁",     "LOCK_RED",   1),
    ("绿锁",     "LOCK_GREEN", 1),
    ("蓝锁",     "LOCK_BLUE",  1),
    ("出口锁",   "LOCK_EXIT",   1),
    ("地刺",     "SPIKE_TRAP",  1),
    ("陷阱标记", None,          "traps"),
    ("金币",     "COIN",        2),
    ("宝石",     "GEM",         2),
    ("镐子",     "PICKAXE",     2),
    ("炸药",     "DYNAMITE",    2),
    ("地图",     "MAP",         2),
    ("红心",     "HEART",       2),
    ("护盾",     "SHIELD",      2),
    ("护身符",   "AMULET",      2),
    ("怪物",     "MONSTER",     2),
]


class MapEditorScreen(BaseScreen):
    """可视化地图编辑器 — 12x12 网格 + 19 刷调色盘 + 一键 JSON 导出。"""

    def __init__(self):
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None

        self.grid = self._create_empty_grid()
        self.start_pos = (1, 1)
        self.exit_pos = (10, 10)
        # 默认出口锁
        ex, ey = self.exit_pos
        self.grid["layer1"][ey][ex] = "LOCK_EXIT"

        self.selected_brush_index = 0   # 初始笔刷：DIRT
        self.is_drawing = False
        self.last_draw_cell = None

        self.buttons: list[Button] = []
        self.btn_export: Button | None = None
        self.btn_clear: Button | None = None
        self.btn_back: Button | None = None

        self.tile_renderer = None
        self.effects = None
        self.font_title = None
        self.font_small = None
        self.font_button = None

    # =========================================================================
    # 网格工具
    # =========================================================================

    @staticmethod
    def _create_empty_grid() -> dict:
        """返回一个全新空网格（全部 DIRT / NONE / False）。"""
        return {
            "layer0": [["DIRT" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)],
            "layer1": [["NONE" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)],
            "layer2": [["NONE" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)],
            "traps": [[False for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)],
        }

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_enter(self, data_payload: dict = None):
        from src.game_manager import GameManager
        from src.tile_renderer import TileRenderer
        from src.effects import EffectsManager

        self.game_manager = GameManager.get_instance()
        self.asset_manager = self.game_manager.asset_manager
        self.screen_manager = self.game_manager.screen_manager

        self.tile_renderer = TileRenderer(tile_size=CELL_SIZE)
        self.effects = EffectsManager()

        self.font_title = self.asset_manager.get_font("default", 32)
        self.font_small = self.asset_manager.get_font("default", 16)
        self.font_button = self.asset_manager.get_font("default", 24)

        # 底部三个功能按钮
        center_x = SCREEN_WIDTH // 2
        self.btn_export = Button(
            text="导出地图 (Export)",
            center_pos=(center_x - BTN_W - 20, BTN_Y),
            width=BTN_W, height=BTN_H,
            font=self.font_button,
            normal_color=(30, 80, 40),
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_clear = Button(
            text="清空画布 (Clear)",
            center_pos=(center_x, BTN_Y),
            width=BTN_W, height=BTN_H,
            font=self.font_button,
            normal_color=(80, 40, 30),
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.btn_back = Button(
            text="返回菜单 (Back)",
            center_pos=(center_x + BTN_W + 20, BTN_Y),
            width=BTN_W, height=BTN_H,
            font=self.font_button,
            normal_color=(50, 50, 70),
            hover_color=GOLD,
            text_color=WHITE,
        )
        self.buttons = [self.btn_export, self.btn_clear, self.btn_back]

    def on_exit(self):
        self.game_manager = None
        self.screen_manager = None
        self.asset_manager = None
        self.buttons = []
        self.btn_export = None
        self.btn_clear = None
        self.btn_back = None
        self.tile_renderer = None
        if self.effects:
            self.effects.clear()
            self.effects = None
        self.font_title = None
        self.font_small = None
        self.font_button = None

    # =========================================================================
    # 事件处理
    # =========================================================================

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEMOTION:
            for btn in self.buttons:
                btn.update(event.pos)
            # 拖拽刷涂
            if self.is_drawing:
                cell = self._get_cell_from_mouse(event.pos)
                if cell is not None and cell != self.last_draw_cell:
                    self.last_draw_cell = cell
                    self._apply_brush(cell[0], cell[1])

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # --- 功能按钮 ---
            if self.btn_export.is_enabled and self.btn_export.rect.collidepoint(event.pos):
                self._export_map()
                return
            if self.btn_clear.is_enabled and self.btn_clear.rect.collidepoint(event.pos):
                self._clear_grid()
                return
            if self.btn_back.is_enabled and self.btn_back.rect.collidepoint(event.pos):
                self.screen_manager.switch_screen(GameState.MAIN_MENU)
                return

            # --- 调色盘点选 ---
            slot = self._get_palette_slot_from_mouse(event.pos)
            if slot is not None:
                self.selected_brush_index = slot
                return

            # --- 画板点击 ---
            cell = self._get_cell_from_mouse(event.pos)
            if cell is not None:
                self.is_drawing = True
                self.last_draw_cell = cell
                self._apply_brush(cell[0], cell[1])

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            # 右键擦除
            cell = self._get_cell_from_mouse(event.pos)
            if cell is not None:
                self._erase_cell(cell[0], cell[1])

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.is_drawing = False
            self.last_draw_cell = None

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.is_drawing:
                self.is_drawing = False
                self.last_draw_cell = None
            else:
                self.screen_manager.switch_screen(GameState.MAIN_MENU)

    # =========================================================================
    # 帧循环
    # =========================================================================

    def update(self, dt: float):
        if self.effects:
            self.effects.update(dt)

    def render(self, surface: pygame.Surface):
        surface.fill((20, 20, 35))

        # 标题
        if self.font_title:
            title = self.font_title.render("VISUAL MAP EDITOR (12x12)", True, GOLD)
            trect = title.get_rect(center=(SCREEN_WIDTH // 2, 120))
            surface.blit(title, trect)

        self._render_grid(surface)
        self._render_palette(surface)
        self._render_buttons(surface)

        # 特效层（无 camera_offset）
        if self.effects:
            self.effects.render(surface, (0, 0))

    # =========================================================================
    # 渲染子流程
    # =========================================================================

    def _render_grid(self, surface: pygame.Surface):
        """绘制 12x12 网格画板。"""
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                px = GRID_OFFSET_X + col * CELL_SIZE
                py = GRID_OFFSET_Y + row * CELL_SIZE

                # 地形层（layer0）
                tile0 = self.grid["layer0"][row][col]
                if self.tile_renderer:
                    self.tile_renderer.draw_tile(surface, tile0, px, py)

                # 障碍层（layer1）
                tile1 = self.grid["layer1"][row][col]
                if tile1 != "NONE" and self.tile_renderer:
                    self.tile_renderer.draw_tile(surface, tile1, px, py)

                # 实体层（layer2）
                tile2 = self.grid["layer2"][row][col]
                if tile2 != "NONE" and self.tile_renderer:
                    self.tile_renderer.draw_tile(surface, tile2, px, py)

                # 叠加层：陷阱标记
                if self.grid["traps"][row][col]:
                    # 红色小三角（右上角）
                    pygame.draw.polygon(surface, (255, 50, 50), [
                        (px + CELL_SIZE, py),
                        (px + CELL_SIZE, py + 10),
                        (px + CELL_SIZE - 10, py),
                    ])

                # 叠加层：起点标记
                if (col, row) == self.start_pos and self.font_small:
                    label = self.font_small.render("SPAWN", True, (100, 255, 100))
                    surface.blit(label, (px + 2, py + CELL_SIZE - 14))

                # 叠加层：终点标记
                if (col, row) == self.exit_pos and self.font_small:
                    label = self.font_small.render("EXIT", True, GOLD)
                    surface.blit(label, (px + CELL_SIZE - 36, py + 2))

        # 网格线
        for i in range(GRID_SIZE + 1):
            x = GRID_OFFSET_X + i * CELL_SIZE
            pygame.draw.line(surface, GRID_LINE_COLOR,
                             (x, GRID_OFFSET_Y),
                             (x, GRID_OFFSET_Y + GRID_PIXEL_H), 1)
            y = GRID_OFFSET_Y + i * CELL_SIZE
            pygame.draw.line(surface, GRID_LINE_COLOR,
                             (GRID_OFFSET_X, y),
                             (GRID_OFFSET_X + GRID_PIXEL_W, y), 1)

    def _render_palette(self, surface: pygame.Surface):
        """绘制右侧 3x7 调色盘。"""
        # 标题
        if self.font_small:
            title = self.font_small.render("BRUSH PALETTE", True, (200, 200, 220))
            surface.blit(title, (PALETTE_OFFSET_X, PALETTE_OFFSET_Y - 24))

        for i, (name, tile_type, layer) in enumerate(BRUSHES):
            col = i % PALETTE_COLS
            row = i // PALETTE_COLS
            sx = PALETTE_OFFSET_X + col * (SLOT_W + SLOT_GAP_X)
            sy = PALETTE_OFFSET_Y + row * (SLOT_H + SLOT_GAP_Y)
            rect = pygame.Rect(sx, sy, SLOT_W, SLOT_H)

            is_sel = (i == self.selected_brush_index)
            bg = PALETTE_SEL_BG if is_sel else PALETTE_BG
            border = PALETTE_SEL_BORDER if is_sel else PALETTE_BORDER

            pygame.draw.rect(surface, bg, rect)
            pygame.draw.rect(surface, border, rect, 2)

            # 微缩预览图标（左侧 32x32 区域）
            icon_r = pygame.Rect(sx + 6, sy + 8, 32, 32)
            if tile_type is not None and layer != "traps" and self.tile_renderer:
                self.tile_renderer.draw_tile(surface, tile_type,
                                             icon_r.x, icon_r.y)
            elif layer == "traps":
                # 陷阱特殊图标
                pygame.draw.rect(surface, (40, 30, 40), icon_r)
                pygame.draw.polygon(surface, (255, 50, 50), [
                    (icon_r.right, icon_r.top),
                    (icon_r.right, icon_r.top + 12),
                    (icon_r.right - 12, icon_r.top),
                ])

            # 名称标签
            if self.font_small:
                label = self.font_small.render(name, True, WHITE)
                surface.blit(label, (sx + 44, sy + 14))

    def _render_buttons(self, surface: pygame.Surface):
        """绘制底部三个功能按钮。"""
        for btn in self.buttons:
            btn.render(surface)

    # =========================================================================
    # 笔刷与操作
    # =========================================================================

    def _apply_brush(self, col: int, row: int):
        """在 (col, row) 格应用当前选中的笔刷。"""
        if not (0 <= col < GRID_SIZE and 0 <= row < GRID_SIZE):
            return

        _name, tile_type, layer = BRUSHES[self.selected_brush_index]

        if layer == "traps":
            # 陷阱标记
            self.grid["traps"][row][col] = True
        elif layer == 0:
            self.grid["layer0"][row][col] = tile_type
        elif layer == 1:
            self.grid["layer1"][row][col] = tile_type
        elif layer == 2:
            self.grid["layer2"][row][col] = tile_type

    def _erase_cell(self, col: int, row: int):
        """右键擦除：清空 (col, row) 格所有层。"""
        if not (0 <= col < GRID_SIZE and 0 <= row < GRID_SIZE):
            return
        self.grid["layer0"][row][col] = "DIRT"
        self.grid["layer1"][row][col] = "NONE"
        self.grid["layer2"][row][col] = "NONE"
        self.grid["traps"][row][col] = False

    # =========================================================================
    # 坐标查询
    # =========================================================================

    def _get_cell_from_mouse(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        """将鼠标坐标转换为网格 (col, row)；超出画板返回 None。"""
        mx, my = pos
        col = (mx - GRID_OFFSET_X) // CELL_SIZE
        row = (my - GRID_OFFSET_Y) // CELL_SIZE
        if 0 <= col < GRID_SIZE and 0 <= row < GRID_SIZE:
            return int(col), int(row)
        return None

    def _get_palette_slot_from_mouse(self, pos: tuple[int, int]) -> int | None:
        """将鼠标坐标转换为调色盘笔刷索引；未命中返回 None。"""
        mx, my = pos
        for i in range(len(BRUSHES)):
            col = i % PALETTE_COLS
            row = i // PALETTE_COLS
            sx = PALETTE_OFFSET_X + col * (SLOT_W + SLOT_GAP_X)
            sy = PALETTE_OFFSET_Y + row * (SLOT_H + SLOT_GAP_Y)
            if sx <= mx <= sx + SLOT_W and sy <= my <= sy + SLOT_H:
                return i
        return None

    # =========================================================================
    # 导出与清空
    # =========================================================================

    def _export_map(self):
        """将当前网格编码为 JSON 并写入 custom_map.json。"""
        from src.custom_level_loader import TILE_TO_CHAR, TRAP_TO_INT

        t2c_l0 = TILE_TO_CHAR["layer0"]
        t2c_l1 = TILE_TO_CHAR["layer1"]
        t2c_l2 = TILE_TO_CHAR["layer2"]

        export_data = {
            "width": GRID_SIZE,
            "height": GRID_SIZE,
            "start_pos": [int(self.start_pos[0]), int(self.start_pos[1])],
            "exit_pos": [int(self.exit_pos[0]), int(self.exit_pos[1])],
            "layer0": [],
            "layer1": [],
            "layer2": [],
            "traps": [],
        }

        for row in range(GRID_SIZE):
            l0_row = []
            l1_row = []
            l2_row = []
            tr_row = []
            for col in range(GRID_SIZE):
                l0_row.append(t2c_l0.get(self.grid["layer0"][row][col], "D"))
                l1_row.append(t2c_l1.get(self.grid["layer1"][row][col], "."))
                l2_row.append(t2c_l2.get(self.grid["layer2"][row][col], "."))
                tr_row.append(TRAP_TO_INT.get(self.grid["traps"][row][col], 0))
            export_data["layer0"].append(l0_row)
            export_data["layer1"].append(l1_row)
            export_data["layer2"].append(l2_row)
            export_data["traps"].append(tr_row)

        # 写入路径使用 os.path.abspath 保证可写（绝对不用 get_resource_path）
        import os as _os_write
        filepath = _os_write.path.abspath("custom_map.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

        # 庆祝特效
        if self.effects:
            cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            self.effects.spawn_particles(cx, cy, GOLD, 30)
            self.effects.spawn_text(cx, cy - 30, "Map Exported!", GOLD, 28)

    def _clear_grid(self):
        """清空所有层并重置起终点。"""
        self.grid = self._create_empty_grid()
        self.start_pos = (1, 1)
        self.exit_pos = (10, 10)
        ex, ey = self.exit_pos
        self.grid["layer1"][ey][ex] = "LOCK_EXIT"
