"""本地存档管理器 — Microsoft Treasure Hunt

提供安全读写 save.json 的能力：原子写入、备份回滚、SHA256 防篡改校验、
损坏自动重置为默认存档。仅使用 Python 标准库。
"""

import os
import json
import hashlib
import time


class SaveManager:
    """本地存档管理器

    默认存档路径为 `save.json`，可通过构造参数自定义路径。
    """

    def __init__(self, save_path: str = None, slot_id: int = None):
        if save_path is not None:
            self.save_path = save_path
        elif slot_id is not None:
            self.save_path = f"save_slot_{slot_id}.json"
        else:
            self.save_path = "save.json"
        self.backup_path = self.save_path + ".bak"
        self.temp_path = self.save_path + ".tmp"

    # =========================================================================
    # 默认数据结构
    # =========================================================================

    def get_default_data(self) -> dict:
        """返回干净的默认存档结构字典"""
        return {
            "version": "1.0.0",
            "timestamp": 0.0,
            "checksum": "",
            "player": {
                "max_hearts": 3,
                "max_shields_limit": 1,
                "bag_tier_index": 0,
                "highest_level_cleared": 0,
                "total_runs": 0,
                "total_monsters_slain": 0,
                "total_gold_earned": 0,
                "unlocked_badges": [],
            },
            "settings": {
                "sound_volume": 1.0,
                "music_volume": 1.0,
            },
            "leaderboard": [],
        }

    @staticmethod
    def get_all_slots_summary(max_slots: int = 3) -> list:
        """扫描所有存档槽位并返回摘要列表。

        每个槽位返回一个 dict：
            {slot_id, exists, level, gold, total_runs, date}
        不存在的槽位 exists=False，其余字段为 None。

        单个槽位的扫描异常不会阻断整体，会被吞掉并以 exists=False 兜底。

        Args:
            max_slots: 扫描的槽位数上限（默认 3）

        Returns:
            长度等于 max_slots 的摘要字典列表
        """
        summary = []
        for slot_id in range(1, max_slots + 1):
            entry = {
                "slot_id": slot_id,
                "exists": False,
                "level": None,
                "gold": None,
                "total_runs": None,
                "date": None,
            }
            try:
                mgr = SaveManager(slot_id=slot_id)
                # 先校验文件是否真实存在，避免 load() 为缺失槽创建默认存档文件
                if not os.path.exists(mgr.save_path):
                    summary.append(entry)
                    continue
                data = mgr.load()
                if data and "player" in data:
                    entry["exists"] = True
                    player = data["player"]
                    entry["level"] = player.get("highest_level_cleared", 0)
                    entry["gold"] = player.get("total_gold_earned", 0)
                    entry["total_runs"] = player.get("total_runs", 0)
                    raw_date = data.get("timestamp", 0)
                    if raw_date:
                        entry["date"] = time.strftime(
                            "%Y-%m-%d", time.localtime(raw_date)
                        )
            except Exception:
                # 任何槽扫描失败不阻断整体，保留 exists=False 兜底
                pass
            summary.append(entry)
        return summary

    # =========================================================================
    # 校验和计算
    # =========================================================================

    def calculate_checksum(self, data: dict) -> str:
        """计算数据校验和。

        复制传入字典，剔除 "checksum" 键，对 JSON 字符串做 SHA256。

        Args:
            data: 待计算的数据字典

        Returns:
            SHA256 十六进制字符串
        """
        snapshot = data.copy()
        snapshot.pop("checksum", None)
        raw = json.dumps(snapshot, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # =========================================================================
    # 安全保存
    # =========================================================================

    def _write_top_level(self, full_data: dict) -> bool:
        """将已组装好的顶级存档字典原子写入磁盘。

        逻辑：填时间戳 → 计算 SHA256 校验和 → 备份现有存档 →
        写临时文件 → ``os.replace`` 原子替换。

        Args:
            full_data: 完整顶级存档字典（会就地填入 timestamp 与 checksum）

        Returns:
            True 写入成功
        """
        try:
            full_data.setdefault("version", "1.0.0")
            full_data["timestamp"] = time.time()
            full_data["checksum"] = self.calculate_checksum(full_data)

            # 备份现有存档（如果存在）
            if os.path.exists(self.save_path):
                try:
                    with open(self.save_path, "r", encoding="utf-8") as f:
                        existing = f.read()
                    with open(self.backup_path, "w", encoding="utf-8") as f:
                        f.write(existing)
                except OSError:
                    pass  # 备份失败不阻断主流程

            # 原子写入：先写临时文件，再替换
            with open(self.temp_path, "w", encoding="utf-8") as f:
                json.dump(full_data, f, ensure_ascii=False, indent=2)

            os.replace(self.temp_path, self.save_path)
            return True
        except (OSError, ValueError):
            return False

    def save(self, player_data: dict, settings_data: dict = None) -> bool:
        """执行安全保存逻辑。

        1. 组装完整数据字典。
        2. 委托 :meth:`_write_top_level` 填入时间戳、计算校验和、备份 + 原子写入。

        Args:
            player_data: 玩家数据字典
            settings_data: 设置数据字典（可选，默认使用默认设置）

        Returns:
            True 保存成功
        """
        if settings_data is None:
            settings_data = {
                "sound_volume": 1.0,
                "music_volume": 1.0,
            }
        payload = {
            "version": "1.0.0",
            "timestamp": 0.0,  # 占位符，_write_top_level 会覆盖
            "player": player_data,
            "settings": settings_data,
            "checksum": "",     # 占位符，_write_top_level 会计算
        }
        return self._write_top_level(payload)

    # =========================================================================
    # 排行榜
    # =========================================================================

    def add_leaderboard_entry(self, level_reached: int, gold_score: int) -> bool:
        """把一条新战绩写入本地 Top 5 排行榜。

        读出完整存档，追加新条目，按 gold_score 降序、若同分按 level_reached 降序
        排序，截断取前 5，重算校验并原子写入。

        Args:
            level_reached: 单局到达的最高关卡数
            gold_score: 单局生涯累计金币（终局落盘的分值）

        Returns:
            True 新条目最终留在 Top 5 内且成功落盘；False 表示落榜或写入失败
        """
        data = self.load()
        entries = list(data.get("leaderboard") or [])
        new_entry = {
            "level_reached": int(level_reached),
            "gold_score": int(gold_score),
            "date": time.strftime("%Y-%m-%d"),
        }
        entries.append(new_entry)
        entries.sort(key=lambda e: (e["gold_score"], e["level_reached"]), reverse=True)
        top5 = entries[:5]
        data["leaderboard"] = top5
        persisted = self._write_top_level(data)
        # 稳健的值比较：避免依赖 list.sort()/切片后的对象身份（load() 重建列表时身份会断裂）
        kept = (
            any(
                e["level_reached"] == new_entry["level_reached"]
                and e["gold_score"] == new_entry["gold_score"]
                and e["date"] == new_entry["date"]
                for e in top5
            )
            and len(top5) > 0
        )
        return bool(persisted and kept)

    # =========================================================================
    # 安全加载
    # =========================================================================

    def load(self) -> dict:
        """执行安全读取逻辑。

        降级恢复链：
        1. 主存档 save.json → 校验 checksum
        2. 失败 → 备份 save.json.bak → 校验 checksum → 有效则恢复
        3. 均失败 → 重置为默认数据并写入

        Returns:
            存档数据字典
        """
        # ---- 尝试主存档 ----
        data = self._try_read_and_validate(self.save_path)
        if data is not None:
            return data

        # ---- 尝试备份 ----
        data = self._try_read_and_validate(self.backup_path)
        if data is not None:
            # 备份有效，恢复为主存档
            try:
                with open(self.backup_path, "r", encoding="utf-8") as f:
                    backup_content = f.read()
                with open(self.save_path, "w", encoding="utf-8") as f:
                    f.write(backup_content)
            except OSError:
                pass
            return data

        # ---- 均损坏，重置为默认 ----
        default = self.get_default_data()
        default["timestamp"] = time.time()
        default["checksum"] = self.calculate_checksum(default)
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        return default

    def _try_read_and_validate(self, path: str) -> dict | None:
        """尝试读取文件并校验 checksum。

        Args:
            path: 文件路径

        Returns:
            校验通过返回数据字典，否则返回 None
        """
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            stored_checksum = data.get("checksum", "")
            expected = self.calculate_checksum(data)
            if stored_checksum == expected:
                return data
            return None
        except (OSError, ValueError, json.JSONDecodeError):
            return None
