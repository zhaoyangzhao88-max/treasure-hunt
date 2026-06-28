"""单元测试 — 设置与选项界面 (SettingsScreen)

覆盖：
- 进入时设置初始化
- 音乐/音效音量增减与临界值钳制
- 全屏切换
- 保存并返回主菜单
- on_exit 清空引用
- 渲染无异常
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
pygame.font.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

from src.screens.settings_screen import SettingsScreen
from src.screens.base_screen import BaseScreen
from src.game_manager import GameManager
from src.asset_manager import AssetManager
from src.save_manager import SaveManager
from src.config import GameState, SCREEN_WIDTH, SCREEN_HEIGHT


# =============================================================================
# 辅助函数
# =============================================================================

def _reset_game_manager(settings=None):
    """重置 GameManager 和 AssetManager 单例，返回全新的 GameManager。

    Args:
        settings: 可选的设置字典，将写入 save.json 供 SettingsScreen.on_enter 读取。
                  默认为 {"sound_volume": 0.5, "music_volume": 0.7}。
    """
    GameManager._instance = None
    AssetManager._instance = None
    gm = GameManager.get_instance()
    gm.init_engine(headless=True)

    # 预写入测试用设置值，使 SettingsScreen.on_enter 通过 save_manager.load() 读到
    if settings is None:
        settings = {"sound_volume": 0.5, "music_volume": 0.7}
    gm.save_manager.save(gm.save_manager.load().get("player", {}), settings)

    # 同步内存中的 settings_data
    gm.settings_data = settings
    return gm


def _click_button(screen, button):
    """模拟左键点击指定按钮。"""
    if button is None:
        return
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": button.rect.center},
    )
    screen.handle_event(click_event)


# =============================================================================
# Mock 屏幕（用于验证路由）
# =============================================================================

class MockMainMenu(BaseScreen):
    """用于接收 SETTINGS → MAIN_MENU 路由的 Mock 屏幕。"""
    def __init__(self):
        self.enter_payload = None
    def on_enter(self, data_payload=None):
        self.enter_payload = data_payload
    def on_exit(self):
        pass
    def handle_event(self, event):
        pass
    def update(self, dt):
        pass
    def render(self, surface):
        pass


# =============================================================================
# 测试用例
# =============================================================================

class TestSettingsScreen:
    """SettingsScreen 完整功能测试。"""

    def test_on_enter_loads_settings(self):
        """进入设置界面时从 GameManager.settings_data 正确读取设置。"""
        gm = _reset_game_manager()
        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        # 验证音量值从 gm.settings_data 正确加载
        # 注意：on_enter 中通过 save_manager.load() 读取设置，
        # 这里 settings_data 是在 _reset_game_manager 中注入的
        assert screen.sound_volume == 0.5, f"Expected 0.5, got {screen.sound_volume}"
        assert screen.music_volume == 0.7, f"Expected 0.7, got {screen.music_volume}"

    def test_music_volume_increment(self):
        """点击音乐 [+] 按钮应增加 0.1。"""
        gm = _reset_game_manager()
        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        initial = screen.music_volume
        _click_button(screen, screen.btn_music_plus)
        assert screen.music_volume == pytest.approx(initial + 0.1), (
            f"Expected {initial + 0.1}, got {screen.music_volume}"
        )

    def test_music_volume_decrement(self):
        """点击音乐 [−] 按钮应减少 0.1。"""
        gm = _reset_game_manager()
        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        initial = screen.music_volume
        _click_button(screen, screen.btn_music_minus)
        assert screen.music_volume == pytest.approx(initial - 0.1), (
            f"Expected {initial - 0.1}, got {screen.music_volume}"
        )

    def test_sfx_volume_increment(self):
        """点击音效 [+] 按钮应增加 0.1。"""
        gm = _reset_game_manager()
        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        initial = screen.sound_volume
        _click_button(screen, screen.btn_sfx_plus)
        assert screen.sound_volume == pytest.approx(initial + 0.1), (
            f"Expected {initial + 0.1}, got {screen.sound_volume}"
        )

    def test_sfx_volume_decrement(self):
        """点击音效 [−] 按钮应减少 0.1。"""
        gm = _reset_game_manager()
        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        initial = screen.sound_volume
        _click_button(screen, screen.btn_sfx_minus)
        assert screen.sound_volume == pytest.approx(initial - 0.1), (
            f"Expected {initial - 0.1}, got {screen.sound_volume}"
        )

    def test_volume_clamping_upper(self):
        """连续点击 [+] 超过上限时音量不超过 1.0。"""
        gm = _reset_game_manager()
        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        # 手动设为接近上限
        screen.music_volume = 0.95

        # 连续点击 12 次（应有 1 次达到上限，其余被钳制）
        for _ in range(12):
            _click_button(screen, screen.btn_music_plus)

        # 断言不超过硬上限 1.0
        assert screen.music_volume <= 1.0, (
            f"Volume exceeded cap: {screen.music_volume}"
        )
        assert screen.music_volume == 1.0, (
            f"Expected 1.0, got {screen.music_volume}"
        )

    def test_volume_clamping_lower(self):
        """连续点击 [−] 超过下限时音量不低于 0.0。"""
        gm = _reset_game_manager()
        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        # 手动设为接近下限
        screen.music_volume = 0.05

        # 连续点击 12 次（应有 1 次达到下限，其余被钳制）
        for _ in range(12):
            _click_button(screen, screen.btn_music_minus)

        # 断言不低于硬下限 0.0
        assert screen.music_volume >= 0.0, (
            f"Volume below floor: {screen.music_volume}"
        )
        assert screen.music_volume == 0.0, (
            f"Expected 0.0, got {screen.music_volume}"
        )

    def test_back_to_menu_saves_and_routes(self):
        """Back 按钮执行存盘并切换到 MAIN_MENU。"""
        gm = _reset_game_manager()

        # Mock save
        save_calls = []
        original_save = gm.save_manager.save
        def mock_save(player_data, settings_data=None):
            save_calls.append({
                "player": player_data,
                "settings": settings_data,
            })
            return True
        gm.save_manager.save = mock_save

        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        # 注册 Mock MainMenu 接收路由
        mock_menu = MockMainMenu()
        gm.screen_manager.register_screen(GameState.MAIN_MENU, mock_menu)

        # 模拟修改音量
        screen.music_volume = 0.3
        screen.sound_volume = 0.6

        # 点击 Back 按钮
        _click_button(screen, screen.btn_back)

        # 断言调用了 save()
        assert len(save_calls) == 1, "save() was not called"
        saved_settings = save_calls[0]["settings"]
        assert saved_settings["music_volume"] == 0.3, (
            f"Expected 0.3, got {saved_settings['music_volume']}"
        )
        assert saved_settings["sound_volume"] == 0.6, (
            f"Expected 0.6, got {saved_settings['sound_volume']}"
        )

        # 断言状态机已切换
        assert gm.screen_manager.current_state == GameState.MAIN_MENU, (
            f"Expected MAIN_MENU, got {gm.screen_manager.current_state}"
        )

        # 恢复原始 save 方法
        gm.save_manager.save = original_save

    def test_fullscreen_toggle(self):
        """全屏按钮切换 is_fullscreen 状态并更新按钮文本。"""
        gm = _reset_game_manager()
        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        initial_state = screen.is_fullscreen

        # Mock toggle_fullscreen 以绕过 headless 模式限制
        original_toggle = pygame.display.toggle_fullscreen
        pygame.display.toggle_fullscreen = lambda: None

        # 点击全屏按钮
        _click_button(screen, screen.btn_fullscreen)

        # 全屏状态应翻转
        assert screen.is_fullscreen == (not initial_state), (
            f"Fullscreen state did not toggle. "
            f"Was {initial_state}, now {screen.is_fullscreen}"
        )

        # 按钮文本应更新
        expected_text = (
            "Fullscreen: ON" if screen.is_fullscreen else "Fullscreen: OFF"
        )
        assert screen.btn_fullscreen.text == expected_text, (
            f"Expected '{expected_text}', got '{screen.btn_fullscreen.text}'"
        )

        # 恢复原始函数
        pygame.display.toggle_fullscreen = original_toggle

    def test_render_no_exception(self):
        """render() 不抛出异常。"""
        gm = _reset_game_manager()
        # 创建测试用 Surface
        test_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        try:
            screen.render(test_surface)
        except Exception as e:
            assert False, f"render() raised an exception: {e}"

    def test_on_exit_clears_refs(self):
        """on_exit 后所有实例属性应清空。"""
        gm = _reset_game_manager()
        screen = SettingsScreen()
        gm.screen_manager.register_screen(GameState.SETTINGS, screen)
        gm.screen_manager.switch_screen(GameState.SETTINGS)

        # 确保 on_enter 已执行
        assert screen.font_title is not None

        # 调用 on_exit
        screen.on_exit()

        # 验证核心引用已清空
        assert screen.game_manager is None
        assert screen.screen_manager is None
        assert screen.asset_manager is None
        assert screen.save_manager is None
        assert screen.buttons == []
        assert screen.font_title is None
        assert screen.font_label is None
        assert screen.font_button is None
        assert screen.btn_music_minus is None
        assert screen.btn_music_plus is None
        assert screen.btn_sfx_minus is None
        assert screen.btn_sfx_plus is None
        assert screen.btn_fullscreen is None
        assert screen.btn_back is None


# =============================================================================
# 单独运行入口
# =============================================================================
if __name__ == "__main__":
    # 命令行运行时自动执行全部测试
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
