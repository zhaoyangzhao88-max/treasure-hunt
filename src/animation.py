"""帧动画与多状态动画控制器 — Microsoft Treasure Hunt

提供帧序列播放（Animation）和多状态切换（Animator）两级能力，
支持精灵图集横向切片、非循环自动终止、以及状态间的自动 IDLE 回退。

典型用法::

    # 创建并注册动画状态
    animator = Animator()
    walk = Animation.from_sheet(sheet, row=0, start_col=0, frame_count=4)
    animator.add_animation("WALK", walk)
    animator.add_animation("IDLE", Animation([surface], 0.5, loop=True))

    # 帧循环中更新
    animator.play("WALK")
    animator.update(dt)
    frame = animator.get_current_frame()
"""

import os as _os
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from config import TILE_SIZE


class Animation:
    """单条帧动画片段 — 帧序列 + 计时器 + 循环控制。

    Args:
        frames: pygame Surface 列表，每帧一张。
        frame_duration: 每帧持续秒数（默认 0.1）。
        loop: 是否循环播放（默认 True）。
    """

    def __init__(self, frames: list[pygame.Surface],
                 frame_duration: float = 0.1,
                 loop: bool = True):
        self.frames = frames
        self.frame_duration = frame_duration
        self.loop = loop

        self.timer: float = 0.0
        self.current_frame_idx: int = 0
        self.finished: bool = False

    # =========================================================================
    # 更新与查询
    # =========================================================================

    def update(self, dt: float) -> None:
        """按时间增量推进帧索引。

        Args:
            dt: 距上一帧的秒数。
        """
        if self.finished or not self.frames:
            return

        self.timer += dt
        threshold = self.frame_duration

        while self.timer >= threshold > 0:
            self.timer -= threshold
            self.current_frame_idx += 1

            if self.current_frame_idx >= len(self.frames):
                if self.loop:
                    self.current_frame_idx = 0
                else:
                    self.current_frame_idx = len(self.frames) - 1
                    self.finished = True
                    self.timer = 0.0
                    break

    def get_current_frame(self) -> pygame.Surface | None:
        """返回当前帧的 Surface，无帧时返回 None。"""
        if not self.frames:
            return None
        return self.frames[self.current_frame_idx]

    def reset(self) -> None:
        """将动画重置到第一帧。"""
        self.timer = 0.0
        self.current_frame_idx = 0
        self.finished = False

    # =========================================================================
    # 图集切片工厂
    # =========================================================================

    @staticmethod
    def from_sheet(sheet: pygame.Surface, row: int,
                   start_col: int, frame_count: int,
                   size: int = TILE_SIZE,
                   duration: float = 0.1,
                   loop: bool = True) -> 'Animation':
        """从精灵图集的指定行横向切割连续帧。

        Args:
            sheet: 完整精灵图集 Surface。
            row: 图集中的行号（第几行）。
            start_col: 起始列号。
            frame_count: 总共切几帧。
            size: 每帧像素边长（默认 TILE_SIZE=48）。
            duration: 每帧持续秒数。
            loop: 是否循环播放。

        Returns:
            包含切割帧的 Animation 实例。
        """
        frames: list[pygame.Surface] = []
        for i in range(frame_count):
            rect = pygame.Rect(
                (start_col + i) * size, row * size, size, size
            )
            try:
                frame = sheet.subsurface(rect).copy()
                frames.append(frame)
            except Exception:
                continue
        return Animation(frames, duration, loop)


class Animator:
    """多状态动画控制器 — 管理一组命名动画并自动处理状态切换。

    在帧循环中每帧调用 ``update(dt)``，控制器会自动：
    - 推进当前状态的帧计时器
    - 当非循环动画播放完毕后自动切回 ``"IDLE"``
    - 追踪当前状态的已持续秒数（``state_time``），供数学动画降级使用

    Attributes:
        animations: 状态名 → Animation 实例的映射。
        current_state: 当前激活状态名（默认 ``"IDLE"``）。
        state_time: 进入当前状态以来的秒数。
    """

    def __init__(self):
        self.animations: dict[str, Animation] = {}
        self.current_state: str = "IDLE"
        self.state_time: float = 0.0

    # =========================================================================
    # 注册与切换
    # =========================================================================

    def add_animation(self, state: str, anim: Animation) -> None:
        """注册一个状态动画。

        Args:
            state: 状态名（如 ``"IDLE"``, ``"WALK_RIGHT"``）。
            anim: 对应的 Animation 实例。
        """
        self.animations[state] = anim

    def play(self, state: str) -> None:
        """切换至指定状态并重置其动画进度。

        若目标状态未注册，调用静默忽略。
        若新状态与当前相同，重置该状态动画使其重新播放。

        Args:
            state: 目标状态名。
        """
        if state not in self.animations:
            return

        self.current_state = state
        self.state_time = 0.0
        self.animations[state].reset()

    # =========================================================================
    # 帧更新
    # =========================================================================

    def update(self, dt: float) -> None:
        """推进当前状态动画计时，检测并执行非循环动画的自动 IDLE 回退。

        Args:
            dt: 距上一帧的秒数。
        """
        self.state_time += dt

        anim = self.animations.get(self.current_state)
        if anim is not None:
            anim.update(dt)
            # 非循环动画播完 → 自动回退 IDLE
            if anim.finished and self.current_state != "IDLE":
                self._switch_to_idle()

    def _switch_to_idle(self) -> None:
        """内部 — 无条件切回 IDLE 并重置 IDLE 动画。"""
        self.current_state = "IDLE"
        self.state_time = 0.0
        idle_anim = self.animations.get("IDLE")
        if idle_anim is not None:
            idle_anim.reset()

    # =========================================================================
    # 查询
    # =========================================================================

    def get_current_frame(self) -> pygame.Surface | None:
        """返回当前状态动画的当前帧 Surface。"""
        anim = self.animations.get(self.current_state)
        if anim is None:
            return None
        return anim.get_current_frame()
