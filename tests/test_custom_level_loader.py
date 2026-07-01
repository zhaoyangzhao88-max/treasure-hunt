"""CustomLevelLoader / MalformedMapError 验证脚本 — Microsoft Treasure Hunt

验证第 54 课外部关卡解析引擎的四大核心契约：
1) 合法简写 JSON → 完美 roundtrip 还原为 GameMap 四层网格
2) JSON 解析失败 → MalformedMapError（含 "JSON"）
3) 缺字段 / 几何越界 / 几何不齐 / 未知简写 → MalformedMapError 精准拦截
4) gameplay_screen.on_enter 从 custom_map_path 成功加载并设置 level_num=999

可在 main.py 执行后通过以下命令验证：
    python tests/test_custom_level_loader.py
    python -m pytest tests/test_custom_level_loader.py -v
"""

import json
import os
import sys

# Headless 驱动必须在 pygame.init() 之前
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 初始化 Pygame display + font + mixer（仅一次）
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

from src.custom_level_loader import CHAR_TO_TILE, CustomLevelLoader, MalformedMapError
from src.config import SCREEN_WIDTH, SCREEN_HEIGHT
from src.game_manager import GameManager
from src.asset_manager import AssetManager
from src.screen_manager import ScreenManager  # noqa: F401 — 可作类型引用
from src.config import GameState


# --------------------------------------------------------------------------
# 辅助：构造最小合法 JSON
# --------------------------------------------------------------------------

def _build_valid_6x6_json() -> str:
    """构造符合 loader 契约的 6×6 测试地图简写 JSON。

    地图语义：
      layer0 — 全 DIRT；layer1 — 周壁 W + 内部 NONE
      layer2 — 仅 (4,4) 处放一枚 COIN "c"，其余 NONE
      traps  — (2,2) 处埋雷 1
      start_pos = (1,1)；exit_pos = (4,4)
    """
    W, H = 6, 6
    layer0 = [["D"] * W for _ in range(H)]
    # 障碍：周壁 W; 内部 NONE
    layer1 = []
    for y in range(H):
        row = []
        for x in range(W):
            if x == 0 or y == 0 or x == W - 1 or y == H - 1:
                row.append("W")
            else:
                row.append(".")
        layer1.append(row)
    # 实体：仅 (4,4) 处 c
    layer2 = [["."] * W for _ in range(H)]
    layer2[4][4] = "c"
    # 埋雷：仅 (2,2) 1
    traps = [[0] * W for _ in range(H)]
    traps[2][2] = 1

    return json.dumps(
        {
            "width": W,
            "height": H,
            "start_pos": [1, 1],
            "exit_pos": [4, 4],
            "layer0": layer0,
            "layer1": layer1,
            "layer2": layer2,
            "traps": traps,
        }
    )


def _assert_raises_with_substr(fn, substr: str) -> MalformedMapError:
    """执行 fn()，断言抛出 MalformedMapError 且 message 含 substr。"""
    try:
        fn()
    except MalformedMapError as exc:
        assert substr in str(exc), (
            f"MalformedMapError 应包含 {substr!r}，实际 message={str(exc)!r}"
        )
        return exc
    except Exception as exc:
        raise AssertionError(
            f"期望 MalformedMapError，得到 {type(exc).__name__}: {exc}"
        )
    raise AssertionError("期望 MalformedMapError，但未抛出任何异常")


# --------------------------------------------------------------------------
# 测试一：合法 map roundtrip
# --------------------------------------------------------------------------

def test_char_to_tile_map_completeness():
    """CHAR_TO_TILE 三层字典应包含任务书要求的全部简写字符。"""
    # Layer0
    for char, full in [
        ("D", "DIRT"),
        ("U", "UNCOVERED"),
    ]:
        assert CHAR_TO_TILE["layer0"][char] == full, (
            f"layer0[{char!r}] 应映射 {full!r}"
        )
    # Layer1
    for char, full in [
        (".", "NONE"),
        ("W", "WALL"),
        ("d", "DIRT_WALL"),
        ("r", "LOCK_RED"),
        ("g", "LOCK_GREEN"),
        ("b", "LOCK_BLUE"),
        ("E", "LOCK_EXIT"),
        ("S", "SPIKE_TRAP"),
    ]:
        assert CHAR_TO_TILE["layer1"][char] == full, (
            f"layer1[{char!r}] 应映射 {full!r}"
        )
    # Layer2
    for char, full in [
        (".", "NONE"),
        ("c", "COIN"),
        ("g", "GEM"),
        ("p", "PICKAXE"),
        ("y", "DYNAMITE"),
        ("m", "MAP"),
        ("h", "HEART"),
        ("s", "SHIELD"),
        ("a", "AMULET"),
        ("w", "ARROW"),
        ("t", "MACHETE"),
        ("M", "MONSTER"),
        ("A", "ACTIVE_MUMMY"),
        ("K", "STAIRS"),
        ("kr", "KEY_RED"),
        ("kg", "KEY_GREEN"),
        ("kb", "KEY_BLUE"),
        ("ke", "KEY_EXIT"),
        ("cb", "CHEST"),
        ("cl", "LOCKED_CHEST"),
    ]:
        assert CHAR_TO_TILE["layer2"][char] == full, (
            f"layer2[{char!r}] 应映射 {full!r}"
        )
    print("[PASS] test_char_to_tile_map_completeness")


def test_valid_map_roundtrip():
    """合法 JSON → 完美 roundtrip：四角 width/height/start_pos/exit_pos 对应；
    layer0 还原为 DIRT 全名；layer1 周壁 WALL 还原；layer2 实体 COIN 还原；
    traps 2,2 埋雷 True。
    """
    loader = CustomLevelLoader()
    game_map, start_pos, exit_pos = loader.load_from_json(
        _build_valid_6x6_json(), is_raw_string=True
    )

    assert game_map.width == 6 and game_map.height == 6, (
        f"尺寸应为 6x6，实际 {game_map.width}x{game_map.height}"
    )
    assert start_pos == (1, 1), f"起点应为 (1,1)，实际 {start_pos}"
    assert exit_pos == (4, 4), f"终点应为 (4,4)，实际 {exit_pos}"

    # layer0：全 DIRT
    assert game_map.layer0[0][0] == "DIRT", "layer0[0][0] 应还原为 DIRT"
    assert game_map.layer0[3][3] == "DIRT", "layer0[3][3] 应还原为 DIRT"

    # layer1：周壁 WALL，内部 NONE
    assert game_map.layer1[0][0] == "WALL", "layer1[0][0] 应还原为 WALL"
    assert game_map.layer1[0][3] == "WALL", "layer1[0][3] 应还原为 WALL"
    assert game_map.layer1[3][3] == "NONE", "layer1[3][3] 应还原为 NONE（内部）"

    # layer2：(4,4) COIN "c"，其余 NONE
    assert game_map.layer2[4][4] == "COIN", "layer2[4][4] 应还原为 COIN"
    assert game_map.layer2[3][3] == "NONE", "layer2[3][3] 应还原为 NONE"

    # traps：仅 (2,2) 处为 True
    assert game_map.traps[2][2] is True, "traps[2][2] 应为 True（埋雷成功还原）"
    assert game_map.traps[0][0] is False, "traps[0][0] 应为 False"
    assert game_map.traps[3][3] is False, "traps[3][3] 应为 False"

    print("[PASS] test_valid_map_roundtrip")


def test_valid_map_roundtrip_via_file(tmp_path=None):
    """将 JSON 写入临时文件后通过 is_raw_string=False 加载，验证路径分支。"""
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        f.write(_build_valid_6x6_json())
        tmp_name = f.name
    try:
        loader = CustomLevelLoader()
        game_map, start_pos, exit_pos = loader.load_from_json(tmp_name)
        assert game_map.width == 6
        assert start_pos == (1, 1)
        assert exit_pos == (4, 4)
        assert game_map.traps[2][2] is True
    finally:
        os.remove(tmp_name)
    print("[PASS] test_valid_map_roundtrip_via_file")


def test_valid_map_all_layers_characters():
    """在单张 6×6 地图里写入**所有**简写字符，验证 roundtrip 全套正确。"""
    W, H = 6, 6
    # layer0：首行 D / 次行 U
    layer0 = []
    for y in range(H):
        row = []
        for x in range(W):
            row.append("D" if y < H // 2 else "U")
        layer0.append(row)
    # layer1：用首行循环填充任务书所有简写
    all_layer1_codes = list(CHAR_TO_TILE["layer1"].keys())
    layer1 = []
    for y in range(H):
        row = []
        for x in range(W):
            row.append(all_layer1_codes[(y * W + x) % len(all_layer1_codes)])
        layer1.append(row)
    # layer2：用首行循环填充任务书所有简写
    all_layer2_codes = list(CHAR_TO_TILE["layer2"].keys())
    layer2 = []
    for y in range(H):
        row = []
        for x in range(W):
            row.append(all_layer2_codes[(y * W + x) % len(all_layer2_codes)])
        layer2.append(row)
    traps = [[((x + y) % 2) for x in range(W)] for y in range(H)]

    raw = json.dumps(
        {
            "width": W,
            "height": H,
            "start_pos": [1, 1],
            "exit_pos": [3, 3],
            "layer0": layer0,
            "layer1": layer1,
            "layer2": layer2,
            "traps": traps,
        }
    )

    loader = CustomLevelLoader()
    game_map, _, _ = loader.load_from_json(raw, is_raw_string=True)

    # 抽查 layer1: (0,0) 是 all_layer1_codes[0]
    first_code = all_layer1_codes[0]
    expected_full = CHAR_TO_TILE["layer1"][first_code]
    assert game_map.layer1[0][0] == expected_full

    # 抽查 layer2: 检查每个代码都有对应还原
    for y in range(H):
        for x in range(W):
            code = all_layer2_codes[(y * W + x) % len(all_layer2_codes)]
            assert game_map.layer2[y][x] == CHAR_TO_TILE["layer2"][code]
            assert game_map.traps[y][x] == bool((x + y) % 2)

    print("[PASS] test_valid_map_all_layers_characters")


# --------------------------------------------------------------------------
# 测试二：残缺 JSON → MalformedMapError（含字段信息）
# --------------------------------------------------------------------------

def test_invalid_json_decode_error():
    """非法 JSON 字符串 → MalformedMapError，message 含 "JSON"。"""
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json("{ width: 6, broken", is_raw_string=True),
        "JSON",
    )
    print("[PASS] test_invalid_json_decode_error")


def test_missing_field_exit_pos():
    """合法形状但缺失 exit_pos 字段 → MalformedMapError 含 "exit_pos"。"""
    W, H = 6, 6
    raw = json.dumps(
        {
            "width": W,
            "height": H,
            "start_pos": [1, 1],
            # 缺失 exit_pos
            "layer0": [["D"] * W for _ in range(H)],
            "layer1": [["."] * W for _ in range(H)],
            "layer2": [["."] * W for _ in range(H)],
            "traps": [[0] * W for _ in range(H)],
        }
    )
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "exit_pos",
    )
    print("[PASS] test_missing_field_exit_pos")


def test_missing_multiple_fields():
    """缺失任一必填字段即应抛错，按清单顺序拦截。"""
    loader = CustomLevelLoader()
    # 缺失 width 优先
    raw_missing_width = json.dumps(
        {
            # 缺失 width
            "height": 6,
            "start_pos": [1, 1],
            "exit_pos": [3, 3],
            "layer0": [["D"] * 6 for _ in range(6)],
            "layer1": [["."] * 6 for _ in range(6)],
            "layer2": [["."] * 6 for _ in range(6)],
            "traps": [[0] * 6 for _ in range(6)],
        }
    )
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw_missing_width, is_raw_string=True),
        "width",
    )

    # 缺失 start_pos
    raw_missing_start = json.dumps(
        {
            "width": 6,
            "height": 6,
            # 缺失 start_pos
            "exit_pos": [3, 3],
            "layer0": [["D"] * 6 for _ in range(6)],
            "layer1": [["."] * 6 for _ in range(6)],
            "layer2": [["."] * 6 for _ in range(6)],
            "traps": [[0] * 6 for _ in range(6)],
        }
    )
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw_missing_start, is_raw_string=True),
        "start_pos",
    )

    print("[PASS] test_missing_multiple_fields")


def test_geometry_row_count_mismatch():
    """行数 != height → MalformedMapError，message 含 "geometry"。"""
    raw = json.dumps(
        {
            "width": 6,
            "height": 6,  # 声称 6 行
            "start_pos": [1, 1],
            "exit_pos": [3, 3],
            "layer0": [["D"] * 6 for _ in range(5)],  # 实际 5 行
            "layer1": [["."] * 6 for _ in range(5)],
            "layer2": [["."] * 6 for _ in range(5)],
            "traps": [[0] * 6 for _ in range(5)],
        }
    )
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "geometry",
    )
    print("[PASS] test_geometry_row_count_mismatch")


def test_geometry_column_count_mismatch():
    """某行列数 != width → MalformedMapError，message 含 "geometry"。"""
    raw = json.dumps(
        {
            "width": 6,  # 声称 6 列
            "height": 6,
            "start_pos": [1, 1],
            "exit_pos": [3, 3],
            "layer0": [
                ["D"] * 6,
                ["D"] * 5,  # 第 1 行只有 5 列
                ["D"] * 6,
                ["D"] * 6,
                ["D"] * 6,
                ["D"] * 6,
            ],
            "layer1": [["."] * 6 for _ in range(6)],
            "layer2": [["."] * 6 for _ in range(6)],
            "traps": [[0] * 6 for _ in range(6)],
        }
    )
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "geometry",
    )
    print("[PASS] test_geometry_column_count_mismatch")


def test_width_out_of_range_low():
    """width=4（< 5）→ MalformedMapError 含 "[5, 50]"。"""
    W, H = 4, 6
    raw = json.dumps(
        {
            "width": W,
            "height": H,
            "start_pos": [1, 1],
            "exit_pos": [2, 2],
            "layer0": [["D"] * W for _ in range(H)],
            "layer1": [["."] * W for _ in range(H)],
            "layer2": [["."] * W for _ in range(H)],
            "traps": [[0] * W for _ in range(H)],
        }
    )
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "[5, 50]",
    )
    print("[PASS] test_width_out_of_range_low")


def test_width_out_of_range_high():
    """width=51（> 50）→ MalformedMapError。"""
    W, H = 51, 6
    raw = json.dumps(
        {
            "width": W,
            "height": H,
            "start_pos": [1, 1],
            "exit_pos": [3, 3],
            "layer0": [["D"] * W for _ in range(H)],
            "layer1": [["."] * W for _ in range(H)],
            "layer2": [["."] * W for _ in range(H)],
            "traps": [[0] * W for _ in range(H)],
        }
    )
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "[5, 50]",
    )
    print("[PASS] test_width_out_of_range_high")


def test_start_pos_out_of_bounds():
    """起点越界（x=10，但 width=6）→ MalformedMapError 含字段名。"""
    W, H = 6, 6
    raw = json.dumps(
        {
            "width": W,
            "height": H,
            "start_pos": [10, 1],  # 越界
            "exit_pos": [3, 3],
            "layer0": [["D"] * W for _ in range(H)],
            "layer1": [["."] * W for _ in range(H)],
            "layer2": [["."] * W for _ in range(H)],
            "traps": [[0] * W for _ in range(H)],
        }
    )
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "start_pos",
    )
    print("[PASS] test_start_pos_out_of_bounds")


def test_exit_pos_out_of_bounds():
    """终点越界 → MalformedMapError 含 "exit_pos"。"""
    W, H = 6, 6
    raw = json.dumps(
        {
            "width": W,
            "height": H,
            "start_pos": [1, 1],
            "exit_pos": [3, 10],  # 越界
            "layer0": [["D"] * W for _ in range(H)],
            "layer1": [["."] * W for _ in range(H)],
            "layer2": [["."] * W for _ in range(H)],
            "traps": [[0] * W for _ in range(H)],
        }
    )
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "exit_pos",
    )
    print("[PASS] test_exit_pos_out_of_bounds")


def test_unknown_tile_code():
    """layer0 中出现未知简写 "Z" → MalformedMapError 含 "Unknown tile code"。"""
    # 先合法构建，再篡改 layer0[0][0] 为 "Z"
    data = json.loads(_build_valid_6x6_json())
    data["layer0"][0][0] = "Z"
    raw = json.dumps(data)

    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "Unknown tile code",
    )
    print("[PASS] test_unknown_tile_code")


def test_unknown_layer1_tile_code():
    """layer1 中出现未知简写 "Z" → MalformedMapError。"""
    data = json.loads(_build_valid_6x6_json())
    data["layer1"][1][1] = "Z"  # 内部点，避免被周壁覆盖
    raw = json.dumps(data)
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "Unknown tile code",
    )
    print("[PASS] test_unknown_layer1_tile_code")


def test_unknown_layer2_tile_code():
    """layer2 中出现未知简写 "Z" → MalformedMapError。"""
    data = json.loads(_build_valid_6x6_json())
    data["layer2"][1][1] = "Z"
    raw = json.dumps(data)
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "Unknown tile code",
    )
    print("[PASS] test_unknown_layer2_tile_code")


def test_trap_invalid_flag():
    """traps 中放了非 0/1（如 2）→ MalformedMapError。"""
    data = json.loads(_build_valid_6x6_json())
    data["traps"][1][1] = 2  # 非法 trap 标志
    raw = json.dumps(data)
    loader = CustomLevelLoader()
    _assert_raises_with_substr(
        lambda: loader.load_from_json(raw, is_raw_string=True),
        "trap",
    )
    print("[PASS] test_trap_invalid_flag")


def test_file_not_found_does_not_crash_gameplay_screen():
    """加载不存在的文件 → GameplayScreen 不应崩溃，应安全降级。"""
    from src.screens.gameplay_screen import GameplayScreen

    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    screen = GameplayScreen()
    gm.screen_manager.register_screen(GameState.PLAYING, screen)
    gm.screen_manager.switch_screen(
        GameState.PLAYING,
        data_payload={"custom_map_path": "nonexistent_file.json"},
    )

    # 没崩 + 降级到 LevelGenerator 生成标准关地图（level_num=1）
    assert screen.game_map is not None, "降级后 game_map 仍应存在"
    assert screen.current_level_num == 1, (
        f"降级后 current_level_num 应为 1，实际为 {screen.current_level_num}"
    )

    print("[PASS] test_file_not_found_does_not_crash_gameplay_screen")


# --------------------------------------------------------------------------
# 集成测试：GameplayScreen 能从 custom_map_path 成功加载合法地图
# --------------------------------------------------------------------------

def _make_mock_custom_map_6x6() -> tuple:
    loader = CustomLevelLoader()
    return loader.load_from_json(_build_valid_6x6_json(), is_raw_string=True)


def test_gameplay_screen_loads_custom_map():
    """给 on_enter 注入合法 custom_map_path，断言 level_num=999，玩家坐标匹配。

    注意：gameplay_screen.on_enter 内部以
        from src.custom_level_loader import CustomLevelLoader, MalformedMapError
    动态导入，因此 patch 目标必须是 loader 模块顶层名
    （``src.custom_level_loader.CustomLevelLoader``），
    而非 gameplay_screen 模块（后者在 import 之前没有该属性）。
    """
    from unittest.mock import patch
    from src.screens.gameplay_screen import GameplayScreen

    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    fake_game_map, fake_start, fake_exit = _make_mock_custom_map_6x6()

    # Mock 整个 CustomLevelLoader 类（patch 到定义处）
    with patch(
        "src.custom_level_loader.CustomLevelLoader"
    ) as MockLoaderCls, patch(
        "src.asset_manager.get_resource_path", return_value="/tmp/mock.json"
    ):
        MockLoaderCls.return_value.load_from_json.return_value = (
            fake_game_map,
            fake_start,
            fake_exit,
        )

        screen = GameplayScreen()
        gm.screen_manager.register_screen(GameState.PLAYING, screen)
        gm.screen_manager.switch_screen(
            GameState.PLAYING,
            data_payload={"custom_map_path": "custom_map.json"},
        )

    # 断言核心指标
    assert screen.current_level_num == 999, (
        f"自定义地图专属编号应为 999，实际为 {screen.current_level_num}"
    )
    assert screen.game_map is fake_game_map, "game_map 应引用 loader 返回的对象"
    # 玩家初始坐标应紧接 InteractionController 的 start_x/y
    assert screen.interaction_controller is not None, "交互控制器应初始化"
    assert (screen.interaction_controller.player_x, screen.interaction_controller.player_y) == fake_start, (
        f"玩家初始坐标应为 {fake_start}，实际为 "
        f"({screen.interaction_controller.player_x}, {screen.interaction_controller.player_y})"
    )
    # 摄像机也应对齐玩家中心
    assert screen.camera is not None, "摄像机应初始化"

    print("[PASS] test_gameplay_screen_loads_custom_map")


def test_gameplay_screen_degrades_on_malformed_custom_map():
    """loader 抛 MalformedMapError → gameplay_screen 降级到 LevelGenerator + level_num=1。"""
    from unittest.mock import patch
    from src.screens.gameplay_screen import GameplayScreen

    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    def raise_malformed(*args, **kwargs):
        raise MalformedMapError("Invalid JSON format: test")

    with patch(
        "src.custom_level_loader.CustomLevelLoader"
    ) as MockLoaderCls, patch(
        "src.asset_manager.get_resource_path", return_value="/tmp/mock.json"
    ):
        MockLoaderCls.return_value.load_from_json.side_effect = raise_malformed

        screen = GameplayScreen()
        gm.screen_manager.register_screen(GameState.PLAYING, screen)
        gm.screen_manager.switch_screen(
            GameState.PLAYING,
            data_payload={"custom_map_path": "custom_map.json"},
        )

    # 降级标准：必须生成 level 1 加标准地图对象
    assert screen.game_map is not None, "降级后 game_map 必须存在"
    assert screen.current_level_num == 1, (
        f"降级后 current_level_num 应为 1，实际为 {screen.current_level_num}"
    )
    assert screen.interaction_controller is not None, "降级后控制器必须就位"

    print("[PASS] test_gameplay_screen_degrades_on_malformed_custom_map")


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        # 第一组：合法地图 roundtrip
        test_char_to_tile_map_completeness()
        test_valid_map_roundtrip()
        test_valid_map_roundtrip_via_file()
        test_valid_map_all_layers_characters()

        # 第二组：残缺拦截
        test_invalid_json_decode_error()
        test_missing_field_exit_pos()
        test_missing_multiple_fields()
        test_geometry_row_count_mismatch()
        test_geometry_column_count_mismatch()
        test_width_out_of_range_low()
        test_width_out_of_range_high()
        test_start_pos_out_of_bounds()
        test_exit_pos_out_of_bounds()
        test_unknown_tile_code()
        test_unknown_layer1_tile_code()
        test_unknown_layer2_tile_code()
        test_trap_invalid_flag()

        # 第三组：GameplayScreen 集成
        test_file_not_found_does_not_crash_gameplay_screen()
        test_gameplay_screen_loads_custom_map()
        test_gameplay_screen_degrades_on_malformed_custom_map()

        print("\n=== ALL TESTS PASSED ===")
    finally:
        GameManager._instance = None
        AssetManager._instance = None
