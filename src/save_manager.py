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

    def __init__(self, save_path: str = "save.json"):
        self.save_path = save_path
        self.backup_path = save_path + ".bak"
        self.temp_path = save_path + ".tmp"

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
                "total_gold_earned": 0,
            },
            "settings": {
                "sound_volume": 1.0,
                "music_volume": 1.0,
            },
        }

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

    def save(self, player_data: dict, settings_data: dict = None) -> bool:
        """执行安全保存逻辑。

        1. 组装完整数据字典，填入时间戳。
        2. 计算校验和。
        3. 备份现有存档（如存在）。
        4. 写入临时文件 → 原子替换为目标文件。

        Args:
            player_data: 玩家数据字典
            settings_data: 设置数据字典（可选，默认使用默认设置）

        Returns:
            True 保存成功
        """
        try:
            if settings_data is None:
                settings_data = {
                    "sound_volume": 1.0,
                    "music_volume": 1.0,
                }

            # 组装完整数据
            payload = {
                "version": "1.0.0",
                "timestamp": time.time(),
                "player": player_data,
                "settings": settings_data,
                "checksum": "",  # 占位符，稍后计算
            }

            # 计算校验和并填入
            payload["checksum"] = self.calculate_checksum(payload)

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
                json.dump(payload, f, ensure_ascii=False, indent=2)

            os.replace(self.temp_path, self.save_path)
            return True

        except (OSError, ValueError):
            return False

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
