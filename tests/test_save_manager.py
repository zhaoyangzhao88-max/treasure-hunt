"""SaveManager 验证脚本 — Microsoft Treasure Hunt

轻量级 assert-based 测试，通过 `python tests/test_save_manager.py` 直接运行。
测试使用临时文件路径，不影响真实存档。
"""

import sys
import os
import json
import shutil

# 确保能找到 src/ 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.save_manager import SaveManager

# --------------------------------------------------------------------------
# 测试用的临时文件
# --------------------------------------------------------------------------
TEST_DIR = os.path.join(os.path.dirname(__file__), "temp")
TEST_SAVE = os.path.join(TEST_DIR, "test_save.json")


def setup():
    """创建测试目录"""
    os.makedirs(TEST_DIR, exist_ok=True)


def teardown():
    """清理测试文件"""
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)


def test_default_data():
    """验证 get_default_data 返回正确结构"""
    mgr = SaveManager(TEST_SAVE)
    data = mgr.get_default_data()
    assert data["version"] == "1.0.0"
    assert data["timestamp"] == 0.0
    assert data["checksum"] == ""
    assert data["player"]["max_hearts"] == 3
    assert data["player"]["max_shields_limit"] == 1
    assert data["player"]["bag_tier_index"] == 0
    assert data["player"]["highest_level_cleared"] == 0
    assert data["player"]["total_runs"] == 0
    assert data["player"]["total_gold_earned"] == 0
    assert data["settings"]["sound_volume"] == 1.0
    assert data["settings"]["music_volume"] == 1.0
    print("[PASS] test_default_data")


def test_checksum_calculation():
    """验证 calculate_checksum 计算一致"""
    mgr = SaveManager(TEST_SAVE)
    data = mgr.get_default_data()
    data["timestamp"] = 100.0
    data["checksum"] = ""

    cs1 = mgr.calculate_checksum(data)
    cs2 = mgr.calculate_checksum(data)
    assert cs1 == cs2, "同一数据校验和应一致"
    assert len(cs1) == 64, "SHA256 hexdigest 应为 64 字符"
    print("[PASS] test_checksum_calculation")


def test_save_and_load():
    """验证正常保存与加载能正确还原数据"""
    setup()
    try:
        mgr = SaveManager(TEST_SAVE)
        player = mgr.get_default_data()["player"]
        player["max_hearts"] = 5
        player["total_gold_earned"] = 1234
        settings = {"sound_volume": 0.8, "music_volume": 0.6}

        ok = mgr.save(player, settings)
        assert ok is True, "save() 应返回 True"

        loaded = mgr.load()
        assert loaded["player"]["max_hearts"] == 5
        assert loaded["player"]["total_gold_earned"] == 1234
        assert loaded["settings"]["sound_volume"] == 0.8
        assert loaded["settings"]["music_volume"] == 0.6
        assert loaded["version"] == "1.0.0"

        # 校验码正确通过（load 内部已验证）
        print("[PASS] test_save_and_load")
    finally:
        teardown()


def test_backup_generation():
    """验证正常保存后备份文件正确生成且内容一致"""
    setup()
    try:
        mgr = SaveManager(TEST_SAVE)
        player = mgr.get_default_data()["player"]

        # 第一次保存
        mgr.save(player, mgr.get_default_data()["settings"])
        assert os.path.exists(TEST_SAVE), "主存档应存在"

        # 修改数据，第二次保存
        player["max_hearts"] = 6
        mgr.save(player, mgr.get_default_data()["settings"])

        # 验证备份文件存在
        assert os.path.exists(TEST_SAVE + ".bak"), ".bak 备份文件应存在"

        # 验证备份内容对应第一次保存的数据
        with open(TEST_SAVE + ".bak", "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        assert backup_data["player"]["max_hearts"] == 3, "备份应为第一次保存的数据"

        # 验证主存档是最新的
        with open(TEST_SAVE, "r", encoding="utf-8") as f:
            main_data = json.load(f)
        assert main_data["player"]["max_hearts"] == 6, "主存档应为最新数据"

        # 验证 tmp 文件不存在（已被原子替换）
        assert not os.path.exists(TEST_SAVE + ".tmp"), "tmp 临时文件应已被替换"

        print("[PASS] test_backup_generation")
    finally:
        teardown()


def test_tamper_detection_and_rollback():
    """验证篡改检测后从备份回滚"""
    setup()
    try:
        mgr = SaveManager(TEST_SAVE)
        player = mgr.get_default_data()["player"]
        settings = mgr.get_default_data()["settings"]

        # 第一次保存（(max_hearts=3）
        mgr.save(player, settings)

        # 修改数据，第二次保存（max_hearts=4）
        player["max_hearts"] = 4
        mgr.save(player, settings)

        # 篡改主存档
        with open(TEST_SAVE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["player"]["gold_cheat"] = 99999  # 添加非法字段不更新 checksum
        with open(TEST_SAVE, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # load 应检测到篡改，回滚到备份（max_hearts=3）
        loaded = mgr.load()
        assert loaded["player"]["max_hearts"] == 3, f"应从备份回滚得到 3，得到 {loaded['player']['max_hearts']}"
        assert "gold_cheat" not in loaded["player"], "不应包含被篡改的内容"

        print("[PASS] test_tamper_detection_and_rollback")
    finally:
        teardown()


def test_tampered_backup_falls_back_to_default():
    """验证备份也损坏时重置为默认存档"""
    setup()
    try:
        mgr = SaveManager(TEST_SAVE)

        # 两个文件都是损坏的
        with open(TEST_SAVE, "w", encoding="utf-8") as f:
            f.write("CORRUPTED")
        with open(TEST_SAVE + ".bak", "w", encoding="utf-8") as f:
            f.write("ALSO CORRUPTED")

        loaded = mgr.load()
        assert loaded["version"] == "1.0.0"
        assert loaded["player"]["max_hearts"] == 3, "应重置为默认值"
        assert loaded["player"]["total_gold_earned"] == 0

        # 验证已写入新默认存档
        assert os.path.exists(TEST_SAVE), "默认存档应已写入"

        print("[PASS] test_tampered_backup_falls_back_to_default")
    finally:
        teardown()


def test_no_file_loads_default():
    """验证文件不存在时自动加载默认格式"""
    setup()
    try:
        mgr = SaveManager(TEST_SAVE)
        assert not os.path.exists(TEST_SAVE), "测试前提：文件不应存在"

        loaded = mgr.load()
        assert loaded["version"] == "1.0.0"
        assert loaded["player"]["max_hearts"] == 3
        assert loaded["settings"]["sound_volume"] == 1.0

        # 验证已写入默认存档
        assert os.path.exists(TEST_SAVE), "加载后已写入默认存档"

        print("[PASS] test_no_file_loads_default")
    finally:
        teardown()


if __name__ == "__main__":
    test_default_data()
    test_checksum_calculation()
    test_no_file_loads_default()
    test_save_and_load()
    test_backup_generation()
    test_tamper_detection_and_rollback()
    test_tampered_backup_falls_back_to_default()
    print("\n=== ALL TESTS PASSED ===")
