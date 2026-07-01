"""核心游戏探索界面 — Microsoft Treasure Hunt

将关卡地图、交互控制器、摄像机与输入系统整合，
提供玩家在地下迷宫中移动、开掘、标雷的核心游戏体验。

使用方式::

    screen = GameplayScreen()
    screen.on_enter(data_payload={"continue": False})
    # 在主循环中：
    screen.handle_event(event)
    screen.update(dt)
    screen.render(surface)
"""

import os as _os
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from src.screens.base_screen import BaseScreen
from src.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    HUD_HEIGHT,
    TILE_SIZE,
    GameState,
    BiomeType,
    get_biome_for_level,
    BIOME_BGM,
    BIOME_COLORS,
    TORCH_EXPANSION,
    TORCH,
)
from src.camera import Camera
from src.level_generator import LevelGenerator
from src.config import ACTIVE_MUMMY
from src.interaction_controller import InteractionController
from src.hud import HUD
from src.tile_renderer import TileRenderer
from src.effects import EffectsManager
from src.animation import Animator, Animation
from src.lighting_manager import LightingManager
from src.help_overlay import HelpOverlay
from src.minimap import Minimap
from src.pause_overlay import (
    PauseOverlay,
    ACTION_RESUME,
    ACTION_RESTART,
    ACTION_HELP,
    ACTION_SAVE_EXIT,
)
from src.ai_autopilot import AISolver

# 颜色常量
_COLOR_BG = (30, 41, 59)           # 地下探险深灰蓝
_COLOR_AIM = (255, 60, 60, 180)    # 炸药瞄准 — 半透明红色高亮
_COLOR_DAMAGE_FLASH = (255, 30, 30, 100)  # 受击闪烁半透明红
_COLOR_AWAKENED = (255, 50, 50)     # 木乃伊苏醒飘字颜色


class GameplayScreen(BaseScreen):
    """核心探索场景 — 集成地图、控制器、摄像机与输入。

    生命周期：
    - on_enter: 解析 data_payload，生成关卡，初始化所有子系统
    - handle_event: 处理键盘移动 + 鼠标点击开掘/标雷/炸药
    - update: 更新摄像机随动 + 特效物理
    - render: 绘制地图瓦片、特效、玩家、HUD
    """

    def __init__(self):
        self.game_manager = None
        self.screen_manager = None

        self.game_map = None
        self.interaction_controller: InteractionController | None = None
        self.camera: Camera | None = None
        self.tile_renderer: TileRenderer | None = None
        self.hud: HUD | None = None
        self.effects_manager: EffectsManager | None = None

        self.current_level_num: int = 1
        self.current_biome: BiomeType | None = None
        self.map_width_px: int = 0
        self.map_height_px: int = 0

        self.input_mode: str = "EXPLORE"
        self.damage_flash_timer: float = 0.0
        self.player_animator: Animator | None = None

        # 玩法指南蒙层（默认关闭）
        self.show_help: bool = False
        self.help_overlay: HelpOverlay | None = None

        # 实时小地图（默认关闭，Tab 开启）
        self.show_minimap: bool = False
        self.minimap: Minimap | None = None

        # 暂停蒙层与关卡初始快照（「重新开始本关」沙盒重置锚点）
        self.show_paused: bool = False
        self.pause_overlay: PauseOverlay | None = None
        self.level_start_player_snapshot: dict | None = None
        self._saved_input_mode: str = "EXPLORE"

        # AI 自动驾驶（P 键切换）
        self.autoplay_mode: bool = False
        self.ai_tick_timer: float = 0.0
        self.ai_tick_interval: float = 0.25

        # 第 59 课：胜利/死亡路由状态标志（防单帧重复跳转）
        self.level_completed: bool = False
        self.is_dead: bool = False
        self.exit_pos: tuple[int, int] | None = None

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_enter(self, data_payload: dict = None):
        """进入探索场景 — 生成关卡并初始化子系统。

        Args:
            data_payload: 跨屏数据负载。
                若包含 continue=True 且 highest_level_cleared > 0，
                则从该关卡继续；否则开启新进度（level 1）。
        """
        from src.game_manager import GameManager

        self.game_manager = GameManager.get_instance()
        self.screen_manager = self.game_manager.screen_manager

        # 第 55 课：火把视野加成管理器（跨关在 on_enter 中按需创建或 reset，
        # 进入奖励关时保持实例不置 None，回来仍走 reset 清 0）
        if not hasattr(self, "lighting_manager") or self.lighting_manager is None:
            self.lighting_manager = LightingManager()
        self.lighting_manager.reset()

        data_payload = data_payload or {}

        # 初始化瓦片渲染器（统一管理 Spritesheet 切片与退化渲染）
        self.tile_renderer = TileRenderer()

        # 初始化玩家动画状态机
        self.player_animator = self._create_player_animator()

        # 初始化特效管理器
        self.effects_manager = EffectsManager()
        self.damage_flash_timer = 0.0
        self.shield_flash_timer = 0.0
        self.clover_spark_timer = 0.0

        # 初始化玩法指南蒙层
        self.help_overlay = HelpOverlay()
        self.show_help = False

        # ---- 从奖励关恢复 ----
        if data_payload.get("resume") and self.game_manager.suspended_level_state is not None:
            s = self.game_manager.suspended_level_state
            self.game_map = s["game_map"]
            self.current_level_num = s["level_num"]
            self.map_width_px = self.game_map.width * TILE_SIZE
            self.map_height_px = self.game_map.height * TILE_SIZE
            self.interaction_controller = InteractionController(
                self.game_map,
                self.game_manager.player_state,
                start_x=s["player_x"],
                start_y=s["player_y"],
            )
            # AI 自动驾驶求解器（恢复分支）
            self.autoplay_mode = False
            self.ai_tick_timer = 0.0
            self.ai_solver = AISolver(
                self.game_map,
                self.game_manager.player_state,
                self.interaction_controller,
            )
            # 对接活性木乃伊（恢复分支）
            self.interaction_controller.link_active_mummies_from_map()
            self.hud = HUD(self.game_manager.player_state)
            self.input_mode = "EXPLORE"
            self.camera = Camera()
            self.camera.offset_x = s["camera_offset_x"]
            self.camera.offset_y = s["camera_offset_y"]
            self.game_manager.suspended_level_state = None
            self.shield_flash_timer = 0.0
            self.clover_spark_timer = 0.0

            # ---- 第 55 课：恢复分支的 lighting_manager 状态保留 ----
            # torch_expansion 在奖励关期间依旧有效，不在此处 reset（主关进入时已统一 reset）
            if not hasattr(self, "lighting_manager") or self.lighting_manager is None:
                self.lighting_manager = LightingManager()

            # ---- 初始化玩法指南蒙层 ----
            self.help_overlay = HelpOverlay()
            self.show_help = False

            # ---- 初始化小地图（恢复分支） ----
            self.minimap = Minimap(
                self.game_map,
                self.game_manager.player_state,
            )

            # 第 59 课：在恢复分支中从地图扫描 LOCK_EXIT 作为出口坐标
            self.exit_pos = None
            for _y in range(self.game_map.height):
                for _x in range(self.game_map.width):
                    if self.game_map.layer1[_y][_x] == "LOCK_EXIT":
                        self.exit_pos = (_x, _y)
                        break
                if self.exit_pos is not None:
                    break
            self.level_completed = False
            self.is_dead = False

            # ---- 计算地貌并配置渲染器与 BGM ----
            biome = get_biome_for_level(self.current_level_num)
            self.current_biome = biome
            self.tile_renderer.set_biome(biome)
            from src.audio_manager import AudioManager
            AudioManager.get_instance().play_bgm(BIOME_BGM[biome])
            return

        # ------------------------------------------------------------------
        # 第 54 课：外部自定义关卡路由（优先于程序化生成）
        # ------------------------------------------------------------------
        custom_map_path = data_payload.get("custom_map_path")
        _custom_loaded = False
        start_pos: tuple[int, int] | None = None
        exit_pos: tuple[int, int] | None = None

        if custom_map_path:
            from src.asset_manager import get_resource_path
            from src.custom_level_loader import CustomLevelLoader, MalformedMapError

            full_path = get_resource_path(custom_map_path)
            try:
                loader = CustomLevelLoader()
                self.game_map, start_pos, exit_pos = loader.load_from_json(full_path)
                self.current_level_num = 999  # 自制关专属编号
                _custom_loaded = True
            except (
                MalformedMapError,
                FileNotFoundError,
                OSError,
                UnicodeDecodeError,
            ) as exc:
                # 恶劣降级：绝不卡死——回退到 level 1 程序化生成
                print(
                    f"[CRITICAL] 自定义地图加载失败，降级到程序化生成："
                    f"{type(exc).__name__}: {exc}"
                )
                # 后续 Standard 路径会重新计算 current_level_num 与 game_map。

        if not _custom_loaded:
            # 解析关卡编号
            continue_game = data_payload.get("continue", False)
            highest_cleared = data_payload.get("highest_level_cleared", 0)

            if continue_game and highest_cleared > 0:
                self.current_level_num = highest_cleared
            else:
                self.current_level_num = 1

        # 计算地貌并配置渲染器（level_num=999 会落入 VOLCANO 兜底）
        current_biome = get_biome_for_level(self.current_level_num)
        self.current_biome = current_biome
        self.tile_renderer.set_biome(current_biome)

        # 跨关清空临时道具（弓箭、柴刀、钥匙、四叶草）
        # 防护性校验：若在测试沙盒中 player_state 未被实例化，跳过清除防止崩溃
        if self.game_manager.player_state is not None:
            self.game_manager.player_state.purge_temporary_items()

        # 生成关卡（仅当外部自定义关卡未成功加载时）
        if not _custom_loaded:
            generator = LevelGenerator(seed=self.current_level_num)
            self.game_map, start_pos, exit_pos = generator.generate_level(self.current_level_num)

        # 第 59 课：保存出口坐标供胜利判定使用
        self.exit_pos = exit_pos
        self.level_completed = False
        self.is_dead = False

        # 计算地图像素尺寸
        self.map_width_px = self.game_map.width * TILE_SIZE
        self.map_height_px = self.game_map.height * TILE_SIZE

        # 初始化交互控制器
        self.interaction_controller = InteractionController(
            self.game_map,
            self.game_manager.player_state,
            start_x=start_pos[0],
            start_y=start_pos[1],
        )

        # AI 自动驾驶求解器（正常分支）
        self.autoplay_mode = False
        self.ai_tick_timer = 0.0
        self.ai_solver = AISolver(
            self.game_map,
            self.game_manager.player_state,
            self.interaction_controller,
        )

        # 初始化 HUD 状态栏
        self.hud = HUD(self.game_manager.player_state)

        # 对接活性木乃伊：扫描地图 layer2 中的 ACTIVE_MUMMY，创建对应实例
        self.interaction_controller.link_active_mummies_from_map()

        # 第 50 课：对接周期地刺 —— 扫描 layer2 中的 SPIKE_TRAP 并实例化
        self.interaction_controller.link_spike_traps_from_map()

        # 输入模式："EXPLORE"（默认探索）/ "DYNAMITE"（炸药瞄准）
        self.input_mode = "EXPLORE"

        # 初始化摄像机 — 直接 snap 到玩家初始像素中心
        self.camera = Camera()
        player_px_x = start_pos[0] * TILE_SIZE + TILE_SIZE // 2
        player_px_y = start_pos[1] * TILE_SIZE + TILE_SIZE // 2
        # 直接定位（无平滑）到玩家中心
        self.camera.offset_x = player_px_x - SCREEN_WIDTH / 2
        self.camera.offset_y = player_px_y - HUD_HEIGHT - (SCREEN_HEIGHT - HUD_HEIGHT) / 2
        # 钳制一次，防止小地图时偏移为负
        max_x = max(0, self.map_width_px - SCREEN_WIDTH)
        max_y = max(0, self.map_height_px - (SCREEN_HEIGHT - HUD_HEIGHT))
        self.camera.offset_x = max(0, min(self.camera.offset_x, max_x))
        self.camera.offset_y = max(0, min(self.camera.offset_y, max_y))

        # ---- 启动地貌专属 BGM ----
        from src.audio_manager import AudioManager
        AudioManager.get_instance().play_bgm(BIOME_BGM[self.current_biome])

        # ---- 初始化小地图 ----
        self.minimap = Minimap(
            self.game_map,
            self.game_manager.player_state,
        )

        # 仅首次进入本关时打下玩家快照（resume 分支已在前面 return，
        # 再次进入本关的 resume / 重载绝不重复打快照，保持锚点稳定）
        if not data_payload or not data_payload.get("resume", False):
            if self.game_manager.player_state is not None:
                self.level_start_player_snapshot = (
                    self.game_manager.player_state.get_snapshot()
                )

    def on_exit(self):
        """离开探索场景时释放引用。"""
        self.game_manager = None
        self.screen_manager = None
        self.game_map = None
        self.interaction_controller = None
        self.camera = None
        self.tile_renderer = None
        self.hud = None
        self.player_animator = None
        self.effects_manager = None
        self.show_minimap = False
        self.minimap = None
        self.show_paused = False
        self.pause_overlay = None
        self.level_start_player_snapshot = None
        self.autoplay_mode = False
        self.ai_solver = None

    # =========================================================================
    # 玩家动画状态机
    # =========================================================================

    def _create_player_animator(self) -> Animator:
        """创建并配置玩家 Animator 多状态动画控制器。

        若 TileRenderer 已成功加载 Spritesheet，尝试从图集切片；
        否则（退化模式）注册虚拟占位帧 — 状态切换仍会推进
        ``state_time``，供退化模式的数学弹性动效使用。
        """
        animator = Animator()
        placeholder = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)

        # 定义所有动画状态：(状态名, 帧数, 帧时长, 循环)
        specs = [
            ("IDLE",        1,  0.2,  True),
            ("WALK_DOWN",   2,  0.1,  False),
            ("WALK_UP",     2,  0.1,  False),
            ("WALK_LEFT",   2,  0.1,  False),
            ("WALK_RIGHT",  2,  0.1,  False),
            ("DIG",         3,  0.1,  False),
            ("HURT",        4,  0.1,  False),
        ]

        if self.tile_renderer is not None and not self.tile_renderer.use_fallback:
            # Spritesheet 模式：尝试从图集切片真实帧（资产存在时激活）
            try:
                from src.asset_manager import AssetManager
                asset_mgr = AssetManager.get_instance()
                sheet = asset_mgr.get_image("spritesheet", size=None)
                if sheet.get_width() > TILE_SIZE * 2:
                    for name, count, dur, loop in specs:
                        anim = Animation.from_sheet(
                            sheet, row=0, start_col=0,
                            frame_count=count, size=TILE_SIZE,
                            duration=dur, loop=loop,
                        )
                        animator.add_animation(name, anim)
                    animator.play("IDLE")
                    return animator
            except Exception:
                pass

        # 退化模式：注册占位虚拟帧（仅驱动 state_time）
        for name, count, dur, loop in specs:
            frames = [placeholder.copy() for _ in range(count)]
            animator.add_animation(name, Animation(frames, dur, loop))

        animator.play("IDLE")
        return animator

    # =========================================================================
    # 事件处理
    # =========================================================================

    def handle_event(self, event: pygame.event.Event):
        """分发输入事件：键盘移动 + 鼠标点击 + 暂停蒙层交互。

        优先级链：ESC 切暂停（最高）→ 暂停态输入冻结 → H/F1 切帮助 →
        帮助态冻结 → 原有 gameplay 输入分发
        """
        # ── ESC 切换暂停蒙层（最高优先级）────────────────────
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.show_help:
                # 帮助开启时 ESC 先关闭帮助（与 H/F1 切换语义一致）
                self.show_help = False
                try:
                    if self.game_manager and self.game_manager.asset_manager:
                        self.game_manager.asset_manager.play_sound("ui_close")
                except Exception:
                    pass
                return
            self._toggle_pause()
            return

        # ── 暂停态：冻结一切 gameplay 输入 ──────────────────
        if self.show_paused:
            # 仅分发 MOUSEMOTION 给按钮推进悬停
            if event.type == pygame.MOUSEMOTION and self.pause_overlay is not None:
                try:
                    if self.game_manager and self.game_manager.asset_manager:
                        if self.pause_overlay.update(event.pos):
                            self.game_manager.asset_manager.play_sound("ui_hover")
                except Exception:
                    self.pause_overlay.update(event.pos)
                return
            # 鼠标左键释放：派发给按钮命中测试
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.pause_overlay is not None:
                    action = self.pause_overlay.button_action_at(event.pos)
                    if action:
                        self._dispatch_pause_action(action)
                return
            # 其它全部拦截（WASD / 鼠标点击格网 / Tab / B / M 全部忽略）
            return

        # ── H / F1 切换帮助蒙层 ──────────────────────────────
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_h, pygame.K_F1):
            self.show_help = not self.show_help
            try:
                if self.game_manager is not None and self.game_manager.asset_manager is not None:
                    self.game_manager.asset_manager.play_sound("ui_open")
            except Exception:
                pass
            return
        # 帮助开启时，冻结一切其它输入
        if self.show_help:
            return

        # ── P 切换自动驾驶 ──────────────────────────────
        if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
            if not self.show_paused:
                self.autoplay_mode = not self.autoplay_mode
                try:
                    if self.game_manager and self.game_manager.asset_manager:
                        self.game_manager.asset_manager.play_sound(
                            "ui_open" if self.autoplay_mode else "ui_close")
                except Exception:
                    pass
            return

        if event.type == pygame.KEYDOWN:
            self._handle_keydown(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_click(event)
        elif event.type == pygame.MOUSEWHEEL:
            self._handle_scroll_wheel(event)

    def _handle_keydown(self, event: pygame.event.Event):
        """处理方向键 / WASD 移动 + 主动工具快捷键。"""
        if self.interaction_controller is None or self.game_map is None:
            return
        # 自动驾驶接管：冻结 WASD / B / M 等 gameplay 键（Tab 在 handle_event 上层已处理）
        if self.autoplay_mode:
            return

        # ── Tab 切换小地图 ────────────────────────────────
        if event.key == pygame.K_TAB:
            # 帮助蒙层开启时，强制关闭小地图
            if self.show_help:
                self.show_minimap = False
            else:
                self.show_minimap = not self.show_minimap
            return

        if event.key in (pygame.K_b, pygame.K_2):
            if self.interaction_controller.player.tools.get("dynamite", 0) > 0:
                self.input_mode = "DYNAMITE"
            return

        if event.key in (pygame.K_m, pygame.K_3):
            self.interaction_controller.use_map()
            return

        # ── 方向键 / WASD 移动 ──────────────────────────────
        px = self.interaction_controller.player_x
        py = self.interaction_controller.player_y

        direction = None
        if event.key in (pygame.K_LEFT, pygame.K_a):
            tx, ty = px - 1, py
            direction = "LEFT"
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            tx, ty = px + 1, py
            direction = "RIGHT"
        elif event.key in (pygame.K_UP, pygame.K_w):
            tx, ty = px, py - 1
            direction = "UP"
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            tx, ty = px, py + 1
            direction = "DOWN"
        else:
            return

        # 步入收集：检查目标格实体（在 _collect_entity 清除前记录）
        collected_entity = None
        if self.game_map.is_in_bounds(tx, ty):
            collected_entity = self.game_map.layer2[ty][tx]

        result = self.interaction_controller.move_player(tx, ty)

        # 动画：成功移动时触发行走动画
        if result in ("SUCCESS", "ENTER_BONUS") and direction and self.player_animator:
            self.player_animator.play(f"WALK_{direction}")

        # 步入楼梯 → 挂起主关卡，切换至奖励关
        if result == "ENTER_BONUS":
            state_payload = {
                "game_map": self.game_map,
                "level_num": self.current_level_num,
                "player_x": self.interaction_controller.player_x,
                "player_y": self.interaction_controller.player_y,
                "camera_offset_x": self.camera.offset_x,
                "camera_offset_y": self.camera.offset_y,
            }
            self.game_manager.suspended_level_state = state_payload
            self.game_manager.screen_manager.switch_screen(GameState.BONUS_LEVEL)
            return

        # 收集联动特效
        if result == "SUCCESS" and collected_entity and collected_entity != "NONE":
            self._trigger_collection_effect(tx, ty, collected_entity)

        # 怪物击杀/受击联动特效
        if result == "MONSTER_DAMAGED_PLAYER":
            self._trigger_damage_effect(tx, ty)

    def _handle_mouse_click(self, event: pygame.event.Event):
        """处理鼠标点击：根据 input_mode 分发左键行为。"""
        if self.camera is None or self.interaction_controller is None or self.game_map is None:
            return
        # 自动驾驶接管：屏蔽鼠标点击开掘 / 标雷 / HUD 工具
        if self.autoplay_mode:
            return

        # 小地图开启时，临时屏蔽鼠标点击开掘，防点击出图意外
        if self.show_minimap:
            return

        # ── HUD 区域点击拦截 ──────────────────────────────────
        if event.pos[1] < HUD_HEIGHT and self.hud is not None:
            tool_hit = self.hud.handle_click(event.pos)
            if tool_hit == "dynamite":
                # 切换炸药瞄准模式（仅当玩家有炸药时）
                if self.interaction_controller.player.tools.get("dynamite", 0) > 0:
                    self.input_mode = "DYNAMITE" if self.input_mode != "DYNAMITE" else "EXPLORE"
            elif tool_hit == "map":
                self.interaction_controller.use_map()
            # 无论是否命中工具，只要点击在 HUD 区域就拦截（不传递到网格）
            return

        grid_x, grid_y = self.camera.screen_to_grid(event.pos[0], event.pos[1])
        if grid_x == -1 and grid_y == -1:
            return

        if not self.game_map.is_in_bounds(grid_x, grid_y):
            return

        if event.button == 1:
            if self.input_mode == "DYNAMITE":
                # ── 炸药瞄准模式：爆破联动 ──────────────────────
                self._trigger_dynamite_effect(grid_x, grid_y)
                self.interaction_controller.use_dynamite(grid_x, grid_y)
                self.input_mode = "EXPLORE"
            else:
                # ── 默认探索模式 ─────────────────────────────────
                entity = self.game_map.layer2[grid_y][grid_x]

                # 若点击相邻怪物格，触发战斗
                if entity == "MONSTER":
                    px = self.interaction_controller.player_x
                    py = self.interaction_controller.player_y
                    if max(abs(grid_x - px), abs(grid_y - py)) <= 1:
                        result = self.interaction_controller.attack_monster(grid_x, grid_y)
                        if result:
                            self.game_manager.asset_manager.play_sound("attack")
                        else:
                            self.game_manager.asset_manager.play_sound("player_hurt")
                            # 怪物受击联动
                            self._trigger_damage_effect(grid_x, grid_y)
                        return

                # 若点击相邻活性木乃伊，触发消灭判定
                if entity == "ACTIVE_MUMMY":
                    px = self.interaction_controller.player_x
                    py = self.interaction_controller.player_y
                    if max(abs(grid_x - px), abs(grid_y - py)) <= 1:
                        result = self.interaction_controller.attack_active_mummy(
                            grid_x, grid_y
                        )
                        if result:
                            self.game_manager.asset_manager.play_sound("attack")
                        else:
                            self.game_manager.asset_manager.play_sound("player_hurt")
                            self._trigger_damage_effect(grid_x, grid_y)
                        return

                # 若点击相邻上锁宝箱，触发开锁判定
                if entity == "LOCKED_CHEST":
                    px = self.interaction_controller.player_x
                    py = self.interaction_controller.player_y
                    if max(abs(grid_x - px), abs(grid_y - py)) <= 1:
                        result = self.interaction_controller.unlock_chest(grid_x, grid_y)
                        if result:
                            self.game_manager.asset_manager.play_sound("chest_unlock")
                        else:
                            self.game_manager.asset_manager.play_sound("player_hurt")
                        return

                # ── 开掘联动 ────────────────────────────────────
                was_dirt = self.game_map.layer0[grid_y][grid_x] == "DIRT"
                has_trap = self.game_map.traps[grid_y][grid_x]

                # 保存受击前血量用于判定
                p = self.interaction_controller.player
                prev_hearts = p.current_hearts
                prev_shields = p.current_shields

                # 执行开掘
                self.interaction_controller.uncover_tile(grid_x, grid_y)

                if was_dirt:
                    tile_world_x = grid_x * TILE_SIZE + TILE_SIZE // 2
                    tile_world_y = grid_y * TILE_SIZE + TILE_SIZE // 2

                    if has_trap:
                        # 陷阱受击联动（含 HURT 动画）
                        self._trigger_damage_effect(grid_x, grid_y, had_shields=prev_shields)
                    else:
                        # 开掘动画
                        if self.player_animator:
                            self.player_animator.play("DIG")
                        # 轻度尘土粒子（开掘泥土）
                        self.effects_manager.spawn_particles(
                            tile_world_x, tile_world_y, (139, 119, 80), count=6
                        )
                # 若为已揭开数字格，执行 Chording
                elif (self.game_map.layer0[grid_y][grid_x] == "UNCOVERED"
                      and self.game_map.get_adjacent_traps_count(grid_x, grid_y) > 0):
                    self.interaction_controller.trigger_chording(grid_x, grid_y)
        elif event.button == 3:
            # 右键：插/拔红旗（任何模式下均可用）
            self.interaction_controller.toggle_flag(grid_x, grid_y)

    def _handle_scroll_wheel(self, event: pygame.event.Event):
        """处理鼠标滚轮事件：上下滚动循环切换 EXPLORE ↔ DYNAMITE 模式。

        仅在玩家持有炸药时切换，无炸药时忽略滚轮。
        """
        if self.interaction_controller is None:
            return
        if self.interaction_controller.player.tools.get("dynamite", 0) <= 0:
            return
        # 双向切换：EXPLORE → DYNAMITE → EXPLORE
        self.input_mode = "DYNAMITE" if self.input_mode != "DYNAMITE" else "EXPLORE"

    # =========================================================================
    # 暂停菜单与时停重置路由
    # =========================================================================

    def _toggle_pause(self):
        """切换暂停态：进入暂停时保存并冻结状态，恢复时还原。

        进入暂停会强制把 input_mode 压到 EXPLORE、关闭帮助蒙层，
        并通过 _saved_input_mode 记录原先的模式以便恢复。
        """
        self.show_paused = not self.show_paused
        if self.show_paused:
            # 进入暂停：保存当前状态
            self._saved_input_mode = self.input_mode
            self.input_mode = "EXPLORE"
            self.show_help = False
            if self.pause_overlay is None:
                self.pause_overlay = PauseOverlay()
            try:
                if self.game_manager and self.game_manager.asset_manager:
                    self.game_manager.asset_manager.play_sound("pause_open")
            except Exception:
                pass
        else:
            # 恢复：还原先前保存的模式
            self.input_mode = getattr(self, "_saved_input_mode", "EXPLORE")
            try:
                if self.game_manager and self.game_manager.asset_manager:
                    self.game_manager.asset_manager.play_sound("pause_close")
            except Exception:
                pass

    def _dispatch_pause_action(self, action: str):
        """暂停按钮路由分发（供 handle_event 与单元测试直接调用）。

        Args:
            action: ACTION_RESUME / ACTION_RESTART / ACTION_HELP / ACTION_SAVE_EXIT
        """
        if action == ACTION_RESUME:
            self._toggle_pause()                       # show_paused → False
        elif action == ACTION_RESTART:
            self._restart_level()
        elif action == ACTION_HELP:
            self.show_paused = False
            self.input_mode = getattr(self, "_saved_input_mode", "EXPLORE")
            self.show_help = True
        elif action == ACTION_SAVE_EXIT:
            self._save_and_exit()

    def _restart_level(self):
        """安全重装本关：还原玩家快照 + 重生成地图 + 重连控制器 + 摄像机对齐。

        这套「时光倒流」机制利用 on_enter 时打下的 level_start_player_snapshot，
        让玩家局内消耗品/状态精确还原，并重新生成一张全新可解的地图，
        实现关卡沙盒级别的安全重置。
        """
        if self.game_manager is None or self.game_map is None:
            return

        # 1) 还原玩家快照
        if self.level_start_player_snapshot is not None:
            self.game_manager.player_state.load_snapshot(
                self.level_start_player_snapshot
            )

        # 2) 重生成全新可解地图（真随机种子，避免与旧地图相同）
        generator = LevelGenerator(seed=None)
        self.game_map, start_pos, exit_pos = generator.generate_level(self.current_level_num)
        self.exit_pos = exit_pos
        self.level_completed = False
        self.is_dead = False

        # 3) 重连 InteractionController 并定位到 start_pos
        self.map_width_px = self.game_map.width * TILE_SIZE
        self.map_height_px = self.game_map.height * TILE_SIZE
        self.interaction_controller = InteractionController(
            self.game_map,
            self.game_manager.player_state,
            start_x=start_pos[0],
            start_y=start_pos[1],
        )
        self.interaction_controller.link_active_mummies_from_map()

        # 4) 摄像机对齐新起点（同 on_enter 的 snap 逻辑）
        player_px_x = start_pos[0] * TILE_SIZE + TILE_SIZE // 2
        player_px_y = start_pos[1] * TILE_SIZE + TILE_SIZE // 2
        self.camera.offset_x = player_px_x - SCREEN_WIDTH / 2
        self.camera.offset_y = player_px_y - HUD_HEIGHT - (SCREEN_HEIGHT - HUD_HEIGHT) / 2
        max_x = max(0, self.map_width_px - SCREEN_WIDTH)
        max_y = max(0, self.map_height_px - (SCREEN_HEIGHT - HUD_HEIGHT))
        self.camera.offset_x = max(0, min(self.camera.offset_x, max_x))
        self.camera.offset_y = max(0, min(self.camera.offset_y, max_y))

        # 5) 特效池清屏 + 重置各闪屏计时器 + 重建 HUD/Minimap + 退出暂停
        if self.effects_manager is not None:
            self.effects_manager.clear()
        self.input_mode = "EXPLORE"
        self.damage_flash_timer = 0.0
        self.shield_flash_timer = 0.0
        self.clover_spark_timer = 0.0
        self.hud = HUD(self.game_manager.player_state)
        self.minimap = Minimap(
            self.game_map,
            self.game_manager.player_state,
        )
        self.show_paused = False

        # 6) 播放关卡重置音效（退化静默）
        try:
            from src.audio_manager import AudioManager
            AudioManager.get_instance().play_sfx("level_reset")
        except Exception:
            pass

    def _save_and_exit(self):
        """安全持久化落盘并切回主菜单。

        构造与 GameManager._hydrate_player 同键名体系的 player 字典，
        交给 SaveManager.save 原子写入，再切回主菜单。任一环节出错均静默降级，
        确保玩家不会卡在探索场景。
        """
        if self.game_manager is None:
            return

        ps = self.game_manager.player_state
        player_dict = {
            "max_hearts": ps.max_hearts,
            "current_hearts": ps.current_hearts,
            "max_shields": ps.max_shields,
            "current_shields": ps.current_shields,
            "bag_tier_index": ps.bag_tier_index,
            "highest_level_cleared": ps.highest_level_cleared,
            "total_runs": ps.total_runs,
            "total_monsters_slain": ps.total_monsters_slain,
            "total_gold_earned": ps.total_gold_earned,
            "gold": ps.gold,
            "tools": dict(ps.tools),
            "keys": dict(ps.keys),
            "has_amulet": ps.has_amulet,
            "arrows": ps.arrows,
            "has_machete": ps.has_machete,
            "has_clover": ps.has_clover,
        }
        settings_dict = getattr(self.game_manager, "settings_data", None)
        try:
            self.game_manager.save_manager.save(player_dict, settings_dict)
        except Exception:
            pass

        self.game_manager.screen_manager.switch_screen(GameState.MAIN_MENU)

    # =========================================================================
    # Game Juice 联动特效
    # =========================================================================

    def _trigger_dynamite_effect(self, grid_x: int, grid_y: int):
        """爆破联动：屏幕震颤 + 灰烬/火花粒子 + BOOM! 文字。"""
        center_x = grid_x * TILE_SIZE + TILE_SIZE // 2
        center_y = grid_y * TILE_SIZE + TILE_SIZE // 2

        # 屏幕震颤（0.4s，10px 振幅）
        self.camera.trigger_shake(0.4, 10.0)

        # 灰烬粒子（深灰褐色）
        self.effects_manager.spawn_particles(center_x, center_y, (100, 70, 40), count=15)
        # 橙黄火花粒子
        self.effects_manager.spawn_particles(center_x, center_y, (255, 165, 0), count=10)

        # BOOM! 浮动文字
        self.effects_manager.spawn_text(
            center_x, center_y - 30, "BOOM!", (255, 215, 0), font_size=28
        )

    def _trigger_damage_effect(self, grid_x: int, grid_y: int, had_shields: int = None):
        """受击联动：根据受击前是否有护盾，触发截然不同的视效分支。

        Args:
            grid_x, grid_y: 触发伤害的网格坐标。
            had_shields: 受击前的护盾数量（由调用方传入 prev_shields）。
                          为 None 时回退到当前护盾判定（向后兼容）。
        """
        # 受击动画
        if self.player_animator:
            self.player_animator.play("HURT")

        tile_world_x = grid_x * TILE_SIZE + TILE_SIZE // 2
        tile_world_y = grid_y * TILE_SIZE + TILE_SIZE // 2

        # 判定：优先使用传入的 had_shields，否则回退到当前值
        shield_was_active = had_shields if had_shields is not None else (
            self.interaction_controller.player.current_shields > 0
        )

        if shield_was_active:
            # ── 护盾抵挡路径：青色闪屏 + 碎片爆发 + 护盾飘字 ──
            self.shield_flash_timer = 0.2
            self.camera.trigger_shake(0.2, 5.0)
            self.effects_manager.spawn_shield_shatter(tile_world_x, tile_world_y, count=20)
            self.effects_manager.spawn_text(
                tile_world_x, tile_world_y - 20, "-1 Shield", (0, 240, 255), font_size=22
            )
        else:
            # ── 血肉受伤路径：红色闪屏 + 溅血粒子 + 血量飘字 ──
            self.damage_flash_timer = 0.25
            self.camera.trigger_shake(0.2, 5.0)
            self.effects_manager.spawn_particles(
                tile_world_x, tile_world_y, (180, 20, 20), count=12
            )
            self.effects_manager.spawn_text(
                tile_world_x, tile_world_y - 20, "-1 Heart", (255, 60, 60), font_size=22
            )

    def _trigger_collection_effect(self, grid_x: int, grid_y: int, entity: str):
        """道具收集联动：头顶升起对应浮动文字。

        Args:
            grid_x, grid_y: 收集发生时的网格坐标。
            entity: 收集的实体类型字符串。
        """
        world_x = grid_x * TILE_SIZE + TILE_SIZE // 2
        world_y = grid_y * TILE_SIZE + TILE_SIZE // 2
        text_y_offset = world_y - TILE_SIZE // 2

        collection_map = {
            "COIN": ("+1 Gold", (255, 215, 0)),
            "GEM": ("+10 Gold", (255, 215, 0)),
            "PICKAXE": ("+1 Shovel", (180, 180, 180)),
            "DYNAMITE": ("+1 Bomb", (200, 60, 60)),
            "MAP": ("+1 Map", (230, 210, 170)),
            "HEART": ("+1 Heart", (200, 30, 30)),
            "SHIELD": ("+1 Shield", (30, 80, 200)),
            "AMULET": ("Amulet!", (140, 40, 180)),
            "ARROW": ("Arrows +1", (160, 120, 60)),
            "MACHETE": ("Machete!", (30, 160, 50)),
            "CHEST": ("Treasure!", (255, 215, 0)),
            "STAIRS": ("Stairs!", (200, 180, 30)),
            "TORCH": ("+1.5 Light Radius!", (255, 140, 0)),
        }

        # 第 55 课：火把拾取 —— 累加视野加成 + 橙红火苗粒子 + 浮动文字
        if entity == "TORCH" and self.lighting_manager is not None:
            self.lighting_manager.torch_expansion += TORCH_EXPANSION
            cx = grid_x * TILE_SIZE + TILE_SIZE // 2
            cy = grid_y * TILE_SIZE + TILE_SIZE // 2
            self.effects_manager.spawn_particles(
                cx, cy, (255, 120, 0), count=18)
            self.effects_manager.spawn_text(
                cx, cy - TILE_SIZE // 2,
                "+1.5 Light Radius!", (255, 160, 30), font_size=20)
            # 实体销毁已在 interaction_controller._collect_entity 中完成
            return

        entry = collection_map.get(entity)
        if entry:
            text, color = entry
            self.effects_manager.spawn_text(world_x, text_y_offset, text, color, font_size=20)

    # =========================================================================
    # AI 自动驾驶 — 动作分发器
    # =========================================================================

    def _execute_ai_action(self, action):
        """将 AISolver 返回的三元组翻译为实际控制器调用。

        Args:
            action: (action_type, (tx, ty)|None, extra_data|None)
        """
        if not action or action[0] == "NO_OP":
            return
        action_type, target, extra = action
        ctrl = self.interaction_controller
        if ctrl is None or self.game_map is None:
            return
        if target is not None and not self.game_map.is_in_bounds(target[0], target[1]):
            return

        if action_type == "FLAG":
            ctrl.toggle_flag(target[0], target[1])
        elif action_type == "UNCOVER":
            ctrl.uncover_tile(target[0], target[1])
        elif action_type == "MOVE":
            ctrl.move_player(target[0], target[1])
        elif action_type == "USE_TOOL":
            ctrl.interact_with_adjacent_obstacle(target[0], target[1])

    # =========================================================================
    # 第 59 课：胜利 / 死亡判定触发器
    # =========================================================================

    def check_victory_condition(self) -> None:
        """检测玩家是否抵达已解锁的出口并触发 LEVEL_COMPLETE 跳转。

        条件：
        - 玩家坐标 (px, py) == self.exit_pos
        - 出口处的障碍已被清除（layer1 == "NONE"，原 LOCK_EXIT 已被钥匙移除）

        触发后设置 level_completed = True 防止单帧重复跳转。
        """
        if self.level_completed or self.is_dead:
            return
        if self.game_manager is None or self.game_manager.player_state is None:
            return
        if self.game_map is None or self.interaction_controller is None:
            return
        if self.exit_pos is None:
            return

        px = self.interaction_controller.player_x
        py = self.interaction_controller.player_y

        if (px, py) != self.exit_pos:
            return

        # 二次校验：出口障碍已被钥匙清除
        if self.game_map.layer1[py][px] != "NONE":
            return

        self.level_completed = True
        payload = {
            "completed_level": self.current_level_num,
            "gold_earned": self.game_manager.player_state.gold,
            "remaining_hearts": self.game_manager.player_state.current_hearts,
            "remaining_shields": self.game_manager.player_state.current_shields,
        }
        self.game_manager.screen_manager.switch_screen(
            GameState.LEVEL_COMPLETE, payload
        )

    def check_death_condition(self) -> None:
        """检测玩家生命值归零并触发 GAME_OVER 跳转。

        条件：
        - player_state.current_hearts <= 0

        触发后设置 is_dead = True 防止单帧重复跳转。
        先于 check_victory_condition 调用，确保死亡优先。
        """
        if self.level_completed or self.is_dead:
            return
        if self.game_manager is None or self.game_manager.player_state is None:
            return

        if self.game_manager.player_state.current_hearts <= 0:
            self.is_dead = True
            self.game_manager.screen_manager.switch_screen(
                GameState.GAME_OVER,
                {"current_level": self.current_level_num}
            )

    # =========================================================================
    # 帧循环
    # =========================================================================

    def update(self, dt: float):
        """逻辑更新 — 动画状态机 + 摄像机随动 + 特效物理 + 受击闪烁计时。"""
        # 推进玩家动画状态机（每帧）
        if self.player_animator is not None:
            self.player_animator.update(dt)

        if self.camera is None or self.interaction_controller is None:
            return

        # 暂停态：冻结 gameplay 逻辑（玩家移动、特效、闪烁、摄像机随动全部时停），
        # 仅推进按钮悬停状态。必须在 show_help 冻结之前，保证暂停比帮助优先。
        if self.show_paused:
            if self.pause_overlay is not None:
                try:
                    if self.game_manager and self.game_manager.asset_manager:
                        if self.pause_overlay.update(pygame.mouse.get_pos()):
                            self.game_manager.asset_manager.play_sound("ui_hover")
                except Exception:
                    self.pause_overlay.update(pygame.mouse.get_pos())
            return

        # 帮助蒙层开启时 冻结逻辑更新（玩家移动、特效、闪烁、摄像机随动全部时停）
        if self.show_help:
            return

        # 将玩家网格坐标换算为像素中心位置
        px = self.interaction_controller.player_x
        py = self.interaction_controller.player_y
        player_px_x = px * TILE_SIZE + TILE_SIZE // 2
        player_px_y = py * TILE_SIZE + TILE_SIZE // 2

        # 同步小地图玩家坐标
        if self.minimap is not None:
            self.minimap.player_x = px
            self.minimap.player_y = py

        self.camera.update(
            player_px_x, player_px_y,
            self.map_width_px, self.map_height_px,
            dt,
        )

        # 特效管理器推进
        if self.effects_manager is not None:
            self.effects_manager.update(dt)

        # 活性木乃伊：无敌窗口衰减 + 苏醒飘字
        ctrl = self.interaction_controller
        if ctrl is not None:
            ctrl.tick_invincible(dt)
            # 检测刚苏醒的木乃伊 → 飘字 "Awakened!" + 屏闪
            for m in ctrl.active_mummies:
                if m.state == "CHASE" and not getattr(m, "_awakened_marked", False):
                    m._awakened_marked = True
                    mx = m.x * TILE_SIZE + TILE_SIZE // 2
                    my = m.y * TILE_SIZE + TILE_SIZE // 2
                    self.effects_manager.spawn_text(
                        mx, my - TILE_SIZE // 2, "Awakened!", _COLOR_AWAKENED, font_size=28
                    )
                    self.camera.trigger_shake(0.2, 4.0)

        # AI 自动驾驶 tick（每 0.25s 决策一次）
        if (self.autoplay_mode and self.ai_solver is not None
                and not self.show_paused and not self.show_help
                and self.interaction_controller is not None
                and self.game_map is not None):
            self.ai_tick_timer += dt
            if self.ai_tick_timer >= self.ai_tick_interval:
                self.ai_tick_timer -= self.ai_tick_interval
                ctrl = self.interaction_controller
                action = self.ai_solver.think_next_action(
                    ctrl.player_x, ctrl.player_y)
                self._execute_ai_action(action)

        # 受击闪烁计时衰减
        if self.damage_flash_timer > 0:
            self.damage_flash_timer = max(0.0, self.damage_flash_timer - dt)

        # 护盾碎裂青色屏闪衰减
        if self.shield_flash_timer > 0:
            self.shield_flash_timer = max(0.0, self.shield_flash_timer - dt)

        # 四叶草绿芒轨迹定时喷吐（每 0.08s 一次）
        if (self.game_manager is not None
                and self.game_manager.player_state is not None
                and self.game_manager.player_state.has_clover):
            self.clover_spark_timer += dt
            while self.clover_spark_timer >= 0.08:
                self.clover_spark_timer -= 0.08
                px = self.interaction_controller.player_x
                py = self.interaction_controller.player_y
                sx = px * TILE_SIZE + TILE_SIZE // 2
                sy = py * TILE_SIZE + TILE_SIZE  # 脚底位置
                self.effects_manager.spawn_clover_spark(sx, sy)

        # 第 59 课：死亡判定优先于胜利判定
        self.check_death_condition()
        self.check_victory_condition()

    def render(self, surface: pygame.Surface):
        """画面绘制 — 地图瓦片 → 特效 → HUD → 受击闪幕。"""
        if self.game_map is None or self.camera is None:
            return

        # 填充背景（使用地貌主题色）
        surface.fill(BIOME_COLORS[self.current_biome]["BG"])

        # 获取最终渲染偏移（含震颤）
        render_offset_x, render_offset_y = self.camera.get_render_offset()

        # 获取裁剪范围
        cols, rows = self.game_map.width, self.game_map.height
        start_col, end_col, start_row, end_row = self.camera.get_visible_tile_bounds(cols, rows)

        # 1) 绘制可见瓦片（分层覆盖：地形 → 障碍 → 实体 → 红旗）
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                self._render_tile(surface, col, row, render_offset_x, render_offset_y)

        # 1.5) 绘制地貌色调网格线
        grid_color = BIOME_COLORS[self.current_biome]["GRID_LINE"]
        for col in range(start_col, end_col + 1):
            gx = col * TILE_SIZE - int(render_offset_x)
            if gx < 0 or gx > SCREEN_WIDTH:
                continue
            pygame.draw.line(surface, grid_color, (gx, HUD_HEIGHT), (gx, SCREEN_HEIGHT), 1)
        for row in range(start_row, end_row + 1):
            gy = row * TILE_SIZE - int(render_offset_y) + HUD_HEIGHT
            if gy < HUD_HEIGHT or gy > SCREEN_HEIGHT:
                continue
            pygame.draw.line(surface, grid_color, (0, gy), (SCREEN_WIDTH, gy), 1)

        # 2) 绘制玩家
        self._render_player(surface, render_offset_x, render_offset_y)

        # 3) 绘制特效（粒子 + 浮动文本）在地图上方
        if self.effects_manager is not None:
            self.effects_manager.render(surface, (render_offset_x, render_offset_y))

        # 4) 绘制炸药瞄准光标（DYNAMITE 模式下）
        if self.input_mode == "DYNAMITE":
            self._draw_aim_cursor(surface, render_offset_x, render_offset_y)

        # 5) 受击闪烁遮罩（红色血肉受伤 / 青色护盾抵挡 / 木乃伊撞击屏闪）
        if self.damage_flash_timer > 0:
            flash_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT - HUD_HEIGHT),
                                         pygame.SRCALPHA)
            flash_surf.fill(_COLOR_DAMAGE_FLASH)
            surface.blit(flash_surf, (0, HUD_HEIGHT))

        # 活性木乃伊撞击屏闪（控制器 screen_flash_duration 控制的短时闪屏）
        ctrl = self.interaction_controller
        if (ctrl is not None and ctrl.screen_flash_color is not None
                and ctrl.screen_flash_duration > 0):
            flash_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT - HUD_HEIGHT),
                                         pygame.SRCALPHA)
            intensity = min(255, int(ctrl.screen_flash_duration / 0.15 * 80))
            flash_surf.fill((*ctrl.screen_flash_color, intensity))
            surface.blit(flash_surf, (0, HUD_HEIGHT))
        if self.shield_flash_timer > 0:
            shield_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT - HUD_HEIGHT),
                                          pygame.SRCALPHA)
            shield_alpha = int(self.shield_flash_timer / 0.2 * 80)
            shield_surf.fill((0, 240, 255, min(120, shield_alpha)))
            surface.blit(shield_surf, (0, HUD_HEIGHT))

        # 6) 绘制 HUD 数据状态栏（最顶层）
        if self.hud is not None:
            self.hud.render(surface, self.current_level_num)

        # 6.5) 自动驾驶状态指示（闪烁文字，左下角）
        if self.autoplay_mode and self.player_animator is not None:
            blink_on = (int(self.player_animator.state_time * 4) % 2) == 0
            if blink_on:
                try:
                    _ai_font = pygame.font.SysFont(None, 28)
                    _dot = _ai_font.render("●", True, (255, 230, 80))
                    _text = _ai_font.render(
                        " AUTO-PILOT ACTIVE", True, (255, 230, 80))
                    _x, _y = 16, SCREEN_HEIGHT - 28
                    surface.blit(_dot, (_x, _y))
                    surface.blit(_text, (_x + _dot.get_width() + 2, _y))
                except Exception:
                    pass

        # 7) 绘制小地图（HUD 之上、帮助蒙层之下）— 半透明叠加
        if (self.show_minimap and self.minimap is not None
                and self.interaction_controller is not None
                and self.player_animator is not None):
            self.minimap.render(
                surface,
                self.interaction_controller.player_x,
                self.interaction_controller.player_y,
                self.player_animator.state_time,
            )

        # 8) 玩法指南蒙层（HUD 之上）
        if self.show_help and self.help_overlay is not None:
            self.help_overlay.render(surface)

        # 9) 暂停蒙层（最最顶层 — 覆盖 HUD / 小地图 / 帮助蒙层）
        if self.show_paused and self.pause_overlay is not None:
            self.pause_overlay.render(surface)

    def _render_tile(self, surface: pygame.Surface, col: int, row: int,
                     render_offset_x: float, render_offset_y: float):
        """使用 TileRenderer 绘制单个瓦片（分层叠加）。

        第 55 课起叠加战争迷雾：根据该瓦片相对玩家的实时光照强度，
        在最后渲染阶段覆盖对应的半透明黑色遮罩（alpha ∈ (0,255)），
        使视野外一片漆黑、半影区线性淡出。
        """
        # 计算屏幕坐标（左上角像素）— 使用含震颤的渲染偏移
        screen_x = col * TILE_SIZE - int(render_offset_x)
        screen_y = row * TILE_SIZE - int(render_offset_y) + HUD_HEIGHT

        # 跳过完全在视口外的瓦片
        if (screen_x + TILE_SIZE < 0 or screen_x > SCREEN_WIDTH
                or screen_y + TILE_SIZE < HUD_HEIGHT or screen_y > SCREEN_HEIGHT):
            return

        terrain = self.game_map.layer0[row][col]
        obstacle = self.game_map.layer1[row][col]
        entity = self.game_map.layer2[row][col]

        # 第 55 课：计算该瓦片相对玩家的实时光照强度（0.0 ~ 1.0）
        light_intensity = 1.0
        if self.lighting_manager is not None and self.interaction_controller is not None:
            px = self.interaction_controller.player_x
            py = self.interaction_controller.player_y
            sight_radius = self.lighting_manager.get_sight_radius(self.current_biome)
            light_intensity = self.lighting_manager.calculate_tile_lighting(
                col, row, px, py, sight_radius)

        # 1) 绘制地形层（DIRT / UNCOVERED）
        extra_info = None
        if terrain == "UNCOVERED":
            trap_count = self.game_map.get_adjacent_traps_count(col, row)
            if trap_count > 0:
                extra_info = str(trap_count)
        self.tile_renderer.draw_tile(surface, terrain, screen_x, screen_y,
                                     extra_info=extra_info,
                                     light_intensity=light_intensity)

        # 2) 障碍物层覆盖
        if obstacle != "NONE":
            self.tile_renderer.draw_tile(surface, obstacle, screen_x, screen_y,
                                         light_intensity=light_intensity)

        # 3) 实体道具层覆盖
        if entity != "NONE":
            self.tile_renderer.draw_tile(surface, entity, screen_x, screen_y,
                                         light_intensity=light_intensity)

        # 4) 红旗覆盖
        if self.game_map.flags[row][col]:
            self.tile_renderer.draw_tile(surface, "FLAG", screen_x, screen_y,
                                         light_intensity=light_intensity)

    def _render_player(self, surface: pygame.Surface,
                       render_offset_x: float, render_offset_y: float):
        """使用 TileRenderer 绘制玩家角色。"""
        if self.interaction_controller is None:
            return

        px = self.interaction_controller.player_x
        py = self.interaction_controller.player_y

        # 世界像素坐标 → 屏幕坐标（计算瓦片左上角）
        screen_x = px * TILE_SIZE - int(render_offset_x)
        screen_y = py * TILE_SIZE - int(render_offset_y) + HUD_HEIGHT

        # 仅当玩家在可见区域时绘制
        if (screen_x + TILE_SIZE >= 0 and screen_x <= SCREEN_WIDTH
                and screen_y + TILE_SIZE >= HUD_HEIGHT and screen_y <= SCREEN_HEIGHT):
            extra = {"animator": self.player_animator}
            if self.game_manager is not None:
                extra["player_state"] = self.game_manager.player_state
            self.tile_renderer.draw_tile(
                surface, "PLAYER", screen_x, screen_y,
                extra_info=extra,
            )

    def _draw_aim_cursor(self, surface: pygame.Surface,
                         render_offset_x: float, render_offset_y: float):
        """绘制炸药瞄准光标：在鼠标悬停瓦片周围高亮 3x3 爆炸范围。"""
        if self.camera is None:
            return

        # 获取鼠标屏幕位置
        mouse_x, mouse_y = pygame.mouse.get_pos()

        # 转换为网格坐标
        grid_x, grid_y = self.camera.screen_to_grid(mouse_x, mouse_y)
        if grid_x == -1 and grid_y == -1:
            return  # 鼠标在 HUD 区域

        if not self.game_map.is_in_bounds(grid_x, grid_y):
            return

        # 绘制 3x3 爆炸范围高亮
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                tx, ty = grid_x + dx, grid_y + dy
                if not self.game_map.is_in_bounds(tx, ty):
                    continue

                # 计算该瓦片的屏幕坐标
                screen_x = tx * TILE_SIZE - int(render_offset_x)
                screen_y = ty * TILE_SIZE - int(render_offset_y) + HUD_HEIGHT

                # 绘制半透明红色高亮矩形
                highlight_surface = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                highlight_surface.fill(_COLOR_AIM)
                surface.blit(highlight_surface, (screen_x, screen_y))

                # 绘制红色边框十字准星
                border_rect = pygame.Rect(screen_x, screen_y, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(surface, (255, 30, 30), border_rect, 2)
