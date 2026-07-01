"""周期地刺陷阱状态机 — Microsoft Treasure Hunt（第 50 课）

玩家在消耗型操作（移动 / 开掘 / Chording）时驱动计数，
每 step_threshold 步翻转一次 RETRACTED <-> EXTENDED。

SpikeTrap 不处理渲染与音效，仅维护纯状态与拍子；
上层 InteractionController 读取事件后决定表现层反馈。
"""

import os as _os
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)


# 状态常量
RETRACTED = "RETRACTED"    # 安全态：缩回地面，玩家可安全踩踏
EXTENDED = "EXTENDED"      # 危险态：尖刺弹出，在格玩家受伤

# 事件常量（on_player_move 返回值）
FLIPPED_OUT = "FLIPPED_OUT"  # 本次调用触发了弹出（RETRACTED -> EXTENDED）
FLIPPED_IN = "FLIPPED_IN"    # 本次调用触发了收回（EXTENDED -> RETRACTED）
EVENT_NONE = "NONE"          # 本次调用未触发状态变化


class SpikeTrap:
    """周期地刺状态机。

    地刺会根据玩家"消耗型动作"的累计步数自动翻转：
    - 每累计 step_threshold 步，翻转一次 RETRACTED <-> EXTENDED。
    - 每拍返回事件字符串，上层可用于音效派发与驻留刺击判定。

    音效派发由上层 InteractionController 负责，本类不持有音频引用。
    """

    def __init__(self, x: int, y: int,
                 initial_state: str = RETRACTED,
                 step_threshold: int = 3):
        """
        Args:
            x, y: 地刺在地图上的格子坐标。
            initial_state: 初始状态（默认 RETRACTED 安全）。
            step_threshold: 翻转阈值步数（默认 3 步一周期）。
        """
        self.x = x
        self.y = y
        self.state = initial_state
        self.turn_counter = 0
        self.step_threshold = step_threshold
        self.last_event = EVENT_NONE

    def on_player_move(self) -> str:
        """玩家执行一次消耗型动作（移动一步 / 开掘一格 / Chording 结算）时调用。

        1) ``turn_counter += 1``
        2) 若 ``turn_counter >= step_threshold``：
           - 翻转状态 ``RETRACTED <-> EXTENDED``
           - 重置计数器
           - 返回 ``FLIPPED_OUT`` 或 ``FLIPPED_IN``
        3) 否则返回 ``EVENT_NONE``。

        Returns:
            ``FLIPPED_OUT`` / ``FLIPPED_IN`` / ``EVENT_NONE``
        """
        self.turn_counter += 1
        if self.turn_counter >= self.step_threshold:
            self.turn_counter = 0
            if self.state == RETRACTED:
                self.state = EXTENDED
                self.last_event = FLIPPED_OUT
                return FLIPPED_OUT
            else:
                self.state = RETRACTED
                self.last_event = FLIPPED_IN
                return FLIPPED_IN
        self.last_event = EVENT_NONE
        return EVENT_NONE

    def get_state(self) -> str:
        """当前状态：RETRACTED 或 EXTENDED。"""
        return self.state

    def get_state_label(self) -> str:
        """与 ``get_state()`` 同义，便于渲染层按统一接口调用。"""
        return self.state

    def get_last_event(self) -> str:
        """最近一次 ``on_player_move()`` 的事件返回值。"""
        return self.last_event

    def is_extended(self) -> bool:
        return self.state == EXTENDED

    def is_retracted(self) -> bool:
        return self.state == RETRACTED

    @property
    def turn(self) -> int:
        """当前计数器拍子值（0 .. step_threshold-1）。"""
        return self.turn_counter

    def __repr__(self) -> str:
        return (f"SpikeTrap({self.x},{self.y}|{self.state}"
                f"|step={self.turn_counter}/{self.step_threshold})")
