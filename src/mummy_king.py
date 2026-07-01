"""法老王首领类 (MummyKing) — Microsoft Treasure Hunt 第 49 课

在 ``ActiveMummy`` 活性木乃伊基础上扩展的首领级敌人：

- **3 滴血**：每次被柴刀 / 弓箭命中扣减 1 点生命，3 次命中后死亡。
- **苏醒半径 6**：比普通木乃伊（5）多 1 格，更早进入 CHASE。
- **受击 100% 召唤爪牙**：每次受击（只要未死亡）必在相邻 4 正交空地中
  召唤一只 ``ActiveMummy``，由控制器层执行。
- **回合召唤**：进入 CHASE 后每 5 回合自动召唤一只爪牙。
- **死亡掉落终点钥匙**：生命归零时，控制器将其所在格 layer2 改写为
  ``"KEY_EXIT"``，玩家拾取后方可开启出口门。

本类职责单一 — 只负责寻路 / 移动决策 / 召唤计数器，
实际召唤、伤害、掉落钥匙统一在 ``InteractionController`` 层处理，
与 ``ActiveMummy`` 保持同一解耦边界。

用法::

    king = MummyKing(x=8, y=8)
    new_x, new_y = king.update_action_turn(player_x, player_y, game_map)
    # 控制器根据 king.should_summon_this_turn() 决定是否召唤
"""

from __future__ import annotations

import os as _os
import sys as _sys

# 将 src/ 加入搜索路径，确保 `import pathfinding` 在各种工作目录下可用
_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

from active_mummy import ActiveMummy  # noqa: E402
from pathfinding import a_star_search  # noqa: E402
from config import MUMMY_KING_ALERT_RADIUS, MUMMY_KING_MAX_HEARTS  # noqa: E402

# 回合召唤阈值 —— 进入 CHASE 后每这么多回合自动召唤一只爪牙
SUMMON_TURN_INTERVAL = 5


class MummyKing(ActiveMummy):
    """法老王首领状态机 + A* 追击决策 + 召唤计数器。

    继承 ``ActiveMummy`` 的 ``x / y / state / _play_growl_sound``，
    扩展生命值、召唤计数器与更大的苏醒半径。

    Attributes:
        hearts:            当前生命值（默认 3）。
        turns_since_summon: 进入 CHASE 后距上次召唤的回合数。
    """

    def __init__(self, x: int, y: int):
        super().__init__(x, y)
        # 覆盖父类默认苏醒半径（5 → 6）
        self.alert_radius: int = MUMMY_KING_ALERT_RADIUS
        # 首领生命值
        self.hearts: int = MUMMY_KING_MAX_HEARTS
        # 回合召唤计数器
        self.turns_since_summon: int = 0

    def update_action_turn(self, player_x: int, player_y: int, game_map
                           ) -> tuple[int, int]:
        """推进一个回合的决策：苏醒判定 → 追击步进 → 召唤计数。

        与 ``ActiveMummy.update_action_turn`` 结构一致，
        在 CHASE 追击后递增 ``turns_since_summon``，
        由控制器层通过 ``should_summon_this_turn()`` 判定是否召唤。

        Returns:
            首领更新后的坐标 ``(x, y)``。
        """
        dist = abs(self.x - player_x) + abs(self.y - player_y)

        # ── 状态切换：SLEEP → CHASE ─────────────────────
        if self.state == "SLEEP":
            if dist <= self.alert_radius:
                self.state = "CHASE"
                # 播放低吼音效（容错 — 资源缺失或混音器未初始化时自然不发声）
                self._play_growl_sound()
                # 位移发生在下一个回合，此处保持不动
                return (self.x, self.y)
            return (self.x, self.y)

        # ── 追击步进 + 召唤计数 ─────────────────────────
        if self.state == "CHASE":
            path = a_star_search(game_map, (self.x, self.y),
                                 (player_x, player_y))
            if path:
                # 沿路径前进一步
                self.x, self.y = path[0]
            # 每回合递增召唤计数器（受击召唤由控制器直接触发）
            self.turns_since_summon += 1
            return (self.x, self.y)

        return (self.x, self.y)

    def should_summon_this_turn(self) -> bool:
        """是否满足回合召唤条件（进入 CHASE 后每 5 回合一次）。"""
        return self.turns_since_summon >= SUMMON_TURN_INTERVAL

    def reset_summon_counter(self) -> None:
        """重置回合召唤计数器（召唤成功后由控制器调用）。"""
        self.turns_since_summon = 0


def _run_standalone_test():
    """简易独立测试。"""
    _os.environ["SDL_VIDEODRIVER"] = "dummy"
    from map_data import GameMap

    # 构造 20×20 空地
    gm = GameMap(20, 20)
    for y in range(20):
        for x in range(20):
            gm.layer0[y][x] = "UNCOVERED"
            gm.layer1[y][x] = "NONE"

    king = MummyKing(10, 0)
    assert king.hearts == 3, f"Expected 3 hearts, got {king.hearts}"
    assert king.alert_radius == 6, f"Expected radius 6, got {king.alert_radius}"

    # 玩家距 10 > 6，不应苏醒
    king.update_action_turn(0, 0, gm)
    assert king.state == "SLEEP", f"Expected SLEEP, got {king.state}"

    # 玩家距 6 → 苏醒
    king.update_action_turn(4, 0, gm)
    assert king.state == "CHASE", f"Expected CHASE, got {king.state}"
    assert (king.x, king.y) == (10, 0), "苏醒回合不应位移"

    # 追击一步：玩家 (4,0)，king (10,0) → 路径首节点 (9,0)
    king.update_action_turn(4, 0, gm)
    assert (king.x, king.y) == (9, 0), f"Expected (9,0), got ({king.x},{king.y})"

    # 召唤计数器递增
    assert king.turns_since_summon == 1, f"Expected 1, got {king.turns_since_summon}"

    print(f"[PASS] MummyKing state={king.state} pos=({king.x},{king.y}) hearts={king.hearts}")
    print("=== MummyKing STANDALONE TESTS PASSED ===")


if __name__ == "__main__":
    _run_standalone_test()
