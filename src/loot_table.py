"""程序化加权掉落表与多级宝箱物资生成 — Microsoft Treasure Hunt

提供 LootTable 类，支持：
1. get_random_loot() — 加权随机掉落，含动态健康救济与关卡缩放
2. generate_chest_loot() — 宝箱多物资包生成（普通宝箱/上锁宝箱双分支）
"""

import os as _os
import sys as _sys
import random

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)


class LootTable:
    """加权掉落表 — 单例友好，亦可独立实例化。

    核心算法基于权重字典的 random.choices，支持：
    - 动态健康救济：残血时大幅提升红心权重
    - 关卡缩放：高稀有度物品随关卡提升权重
    """

    # 基础掉落权重（总和 = 100）
    BASE_WEIGHTS: dict[str, int] = {
        "COIN": 40,
        "GEM": 10,
        "PICKAXE": 20,
        "DYNAMITE": 15,
        "MAP": 10,
        "HEART": 3,
        "SHIELD": 2,
    }

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def get_random_loot(self, level_num: int,
                        current_hearts: int | None = None,
                        max_hearts: int | None = None) -> str:
        """根据权重随机返回一种实体掉落类型。

        Args:
            level_num: 当前关卡编号（>= 1）。
            current_hearts: 当前玩家红心数（可选）。
            max_hearts: 玩家红心上限（可选）。

        Returns:
            实体类型字符串，如 "COIN"、"HEART" 等。
        """
        weights = dict(self.BASE_WEIGHTS)

        # ── 动态健康救济（Dynamic Pity） ──────────────────────────────
        # 若玩家残血（≤1）且未满血，强行将 HEART 权重提升至 25，
        # 其余物品同比例压缩至合计 75。
        if (current_hearts is not None and max_hearts is not None
                and current_hearts <= 1 and current_hearts < max_hearts):
            weights["HEART"] = 25
            non_heart_total = sum(v for k, v in weights.items() if k != "HEART")
            if non_heart_total > 0:
                scale = 75.0 / non_heart_total
                for k in list(weights.keys()):
                    if k != "HEART":
                        weights[k] = max(1, int(weights[k] * scale))

        # ── 关卡缩放 ──────────────────────────────────────────────
        # GEM 权重随关卡增加（每关 +50%，上限 10×）
        gem_boost = min(10.0, 1.0 + (level_num - 1) * 0.5)
        weights["GEM"] = max(1, int(weights["GEM"] * gem_boost))

        # SHIELD 权重随关卡增加（每关 +30%，上限 8×）
        shield_boost = min(8.0, 1.0 + (level_num - 1) * 0.3)
        weights["SHIELD"] = max(1, int(weights["SHIELD"] * shield_boost))

        # 抽取
        items = list(weights.keys())
        item_weights = list(weights.values())
        return self._rng.choices(items, weights=item_weights, k=1)[0]

    def generate_chest_loot(self, is_locked: bool) -> list[tuple[str, int]]:
        """生成宝箱内的多重物资列表。

        Args:
            is_locked: True 表示上锁宝箱，False 表示普通宝箱。

        Returns:
            物资元组列表，每个元组为 (实体类型, 数量)。
        """
        if is_locked:
            # 上锁宝箱：3 份物资，高金币 + 宝石 + 20% 史诗道具
            loot: list[tuple[str, int]] = [
                ("COIN", self._rng.randint(50, 150)),
                ("GEM", self._rng.randint(1, 3)),
            ]
            # 20% 概率获得史诗道具
            if self._rng.random() < 0.20:
                epic = self._rng.choice(["AMULET", "MACHETE"])
                loot.append((epic, 1))
            else:
                # 保底：额外炸药或铁锹
                fallback = self._rng.choice(["DYNAMITE", "PICKAXE"])
                loot.append((fallback, self._rng.randint(1, 2)))
            return loot
        else:
            # 普通宝箱：2 份物资
            return [
                ("COIN", self._rng.randint(25, 75)),
                ("PICKAXE", 1),
            ]
