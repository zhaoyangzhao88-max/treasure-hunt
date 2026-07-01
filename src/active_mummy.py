"""主动追逐木乃伊类 (ActiveMummy) — Microsoft Treasure Hunt

实现一个基于回合触发、A* 路径规划的主动追逐型敌人：

- **SLEEP 状态**：休眠，静止不动。当玩家进入半径 ``alert_radius = 5`` 的曼哈顿距离内，
  切换为 **CHASE 状态**（在本类内触发低吼音效，由调用方播放飘字）。
- **CHASE 状态**：每回合调用 ``a_star_search`` 计算到玩家的曼哈顿最短路径，
  移动一步沿路径靠近玩家。

本类职责单一 — 只负责寻路与移动决策，不自行触发伤害或视觉特效。
伤害 / 飘字 / 屏闪 / 安全弹回 统一在 ``InteractionController`` 层处理，
有利于保持解耦与集中管控。

用法::

    mummy = ActiveMummy(x=6, y=0)
    new_x, new_y = mummy.update_action_turn(player_x, player_y, game_map)
    # 更新后检查 mummy.state 若刚变 CHASE，由控制器层触发飘字 "Awakened!"
"""

from __future__ import annotations

import os as _os
import sys as _sys

# 将 src/ 加入搜索路径，确保 `import pathfinding` 在各种工作目录下可用
_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

from pathfinding import a_star_search  # noqa: E402

# 苏醒半径（曼哈顿距离） —— 玩家进入此范围时木乃伊苏醒
ALERT_RADIUS = 5


class ActiveMummy:
    """活性木乃伊状态机 + A* 追击决策。

    网格坐标 (x, y) 由外部控制器同步到 ``GameMap.layer2``：
    - 位置更新后调用 ``game_map.set_entity(x, y, "ACTIVE_MUMMY")`` 重绘。
    - 死亡后调用 ``game_map.set_entity(x, y, "NONE")`` 清场。

    Attributes:
        x, y:         当前网格坐标。
        state:        "SLEEP" / "CHASE"。
        alert_radius: 触发苏醒的曼哈顿距离（常量 5）。
    """

    def __init__(self, x: int, y: int):
        self.x: int = x
        self.y: int = y
        self.state: str = "SLEEP"
        self.alert_radius: int = ALERT_RADIUS

    def update_action_turn(self, player_x: int, player_y: int, game_map
                           ) -> tuple[int, int]:
        """推进一个回合的决策：苏醒判定 → 追击步进。

        Args:
            player_x:  玩家当前网格 X。
            player_y:  玩家当前网格 Y。
            game_map:   GameMap 实例，用于 A* 寻路的 ``is_walkable`` 查询。

        Returns:
            木乃伊更新后的坐标 ``(x, y)``。
            - 仍沉睡：返回当前坐标（不动）。
            - 刚苏醒：返回当前坐标（仅触发掘音，不位移）。
            - 顺时针追击：返回路径第一个节点的新坐标。
            - 无路径：返回当前坐标（原地等待）。
        """
        dist = abs(self.x - player_x) + abs(self.y - player_y)

        # ── 状态切换：SLEEP → CHASE ─────────────────────
        if self.state == "SLEEP":
            if dist <= self.alert_radius:
                self.state = "CHASE"
                # 播放低吼音效（静默容错 — 资源缺失或混音器未初始化时自然不发声）
                self._play_growl_sound()
                # 位移发生在下一个回合，此处保持不动
                return (self.x, self.y)
            return (self.x, self.y)

        # ── 追击步进 ─────────────────────────────────────
        if self.state == "CHASE":
            # 若玩家恰好在曼哈顿距离 5 格之外唤醒，直到进入攻击范围也不会走动，
            # 但为了体现"追杀"语义：一旦进入 CHASE 立即跑向玩家
            path = a_star_search(game_map, (self.x, self.y),
                                 (player_x, player_y))
            if path:
                # 沿路径前进一步
                next_step = path[0]
                step_x, step_y = next_step
                # 若下一步会走到玩家身上，仍返回该坐标；碰撞判定由控制器处理
                self.x = step_x
                self.y = step_y
                return (self.x, self.y)

            # 不可达 → 原地等待
            return (self.x, self.y)

        return (self.x, self.y)

    @staticmethod
    def _play_growl_sound() -> None:
        """播放木乃伊苏醒的低吼音效。

        容错设计 — 在任何层级失败都不抛异常（DummySound / 混音器未初始化 / 文件缺失），
        与项目整体"缺失资产绝不崩溃"原则一致。
        """
        try:
            from src.asset_manager import AssetManager
            AssetManager.get_instance().get_sound("mummy_growl").play()
        except Exception:
            # 怠躯静默 — 资源缺失时无视
            pass


def _run_standalone_test():
    """简易独立测试。"""
    import os
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    _src_dir = os.path.dirname(os.path.abspath(__file__))
    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)
    from map_data import GameMap

    # 唤醒与追击测试
    gm = GameMap(20, 20)
    for y in range(20):
        for x in range(20):
            gm.layer0[y][x] = "UNCOVERED"
            gm.layer1[y][x] = "NONE"

    m = ActiveMummy(6, 0)
    # 玩家距 6 > 5，不应苏醒
    m.update_action_turn(0, 0, gm)
    assert m.state == "SLEEP", f"Expected SLEEP, got {m.state}"

    # 玩家距 5 → 苏醒
    m.update_action_turn(1, 0, gm)
    assert m.state == "CHASE", f"Expected CHASE, got {m.state}"

    # 追击一步：玩家 (1,0)，木乃伊 (6,0) → 路径 [(5,0),(4,0),...]
    m.update_action_turn(2, 0, gm)
    assert (m.x, m.y) == (5, 0), f"Expected (5,0), got ({m.x},{m.y})"

    print(f"[PASS] Mummy state={m.state} pos=({m.x},{m.y})")
    print("=== ActiveMummy STANDALONE TESTS PASSED ===")


if __name__ == "__main__":
    _run_standalone_test()
