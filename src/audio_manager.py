"""全局音频管理器 — Microsoft Treasure Hunt

集中管理所有 ``pygame.mixer.music`` 的访问（BGM），提供去重播放、淡入淡出、
静默沙盒模式，并将 SFX 的播放委托给 ``AssetManager``。

使用方式::

    mgr = AudioManager.get_instance()
    mgr.play_bgm("menu_bgm.ogg")         # 启动主菜单 BGM（自动防重叠）
    mgr.stop_bgm(fade_ms=500)            # 淡出停止
    mgr.play_sfx("click.wav")            # 播放音效（委托给 AssetManager）
    mgr.set_music_volume(0.5)            # 音乐音量即时生效
"""

import os
import pygame


class AudioManager:
    """全局音频管理器（单例）— BGM 调度 + SFX 桥接。

    通过 ``get_instance()`` 获取全局唯一实例。所有 ``pygame.mixer.music``
    调用都经过 ``_mixer_ok()`` 安全检查，混音器未初始化时静默退化。
    """

    _instance: "AudioManager | None" = None

    def __init__(self):
        self.current_bgm: str | None = None
        """当前正在播放的 BGM 相对路径（例如 "menu_bgm.ogg"），供防重放判定使用。"""

        self.music_volume: float = 1.0
        """音乐音量 [0.0, 1.0]，通过 set_music_volume() 设置。"""

        self.sfx_volume: float = 1.0
        """音效音量 [0.0, 1.0]，通过 set_sfx_volume() 设置。"""

    # =========================================================================
    # 单例访问
    # =========================================================================

    @classmethod
    def get_instance(cls) -> "AudioManager":
        """获取或创建全局唯一 AudioManager 实例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =========================================================================
    # 内部沙盒检测
    # =========================================================================

    @staticmethod
    def _mixer_ok() -> bool:
        """检测 ``pygame.mixer`` 是否可用。

        Returns:
            True 混音器已就绪；False 混音器未初始化或发生异常。
        """
        try:
            return pygame.mixer.get_init() is not None
        except pygame.error:
            return False

    # =========================================================================
    # 背景音乐 API
    # =========================================================================

    def play_bgm(self, rel_path: str, loop: bool = True, fade_ms: int = 1000):
        """播放背景音乐，带防重叠保护与静默降级。

        Args:
            rel_path: 相对于 ``assets/sounds/`` 的文件路径，如 ``"menu_bgm.ogg"``。
            loop: 是否循环播放，默认 True。
            fade_ms: 淡入毫秒数，默认 1000ms。
        """
        # ---- 防重复保护：相同曲目正在播放 → 跳过 ----
        if self.current_bgm == rel_path:
            return

        # ---- 混音器不可用 → 静默记录状态 ----
        if not self._mixer_ok():
            self.current_bgm = rel_path
            return

        # ---- 安全加载与播放 ----
        try:
            from src.asset_manager import AssetManager

            full_path = os.path.join(
                AssetManager.get_instance().root, "sounds", rel_path
            )
            pygame.mixer.music.load(full_path)
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(loops=-1 if loop else 0, fade_ms=fade_ms)
            self.current_bgm = rel_path
        except (pygame.error, FileNotFoundError, OSError) as e:
            print(f"WARNING: Failed to play BGM '{rel_path}': {e}")
            self.current_bgm = None

    def stop_bgm(self, fade_ms: int = 500):
        """停止背景音乐，可选择淡出。

        Args:
            fade_ms: 淡出毫秒数，默认 500ms。
        """
        if not self._mixer_ok():
            self.current_bgm = None
            return
        try:
            pygame.mixer.music.fadeout(fade_ms)
        except pygame.error:
            pass
        self.current_bgm = None

    def pause_bgm(self):
        """暂停当前 BGM（不改变 ``current_bgm``）。"""
        if self._mixer_ok():
            try:
                pygame.mixer.music.pause()
            except pygame.error:
                pass

    def resume_bgm(self):
        """恢复暂停的 BGM。"""
        if self._mixer_ok():
            try:
                pygame.mixer.music.unpause()
            except pygame.error:
                pass

    # =========================================================================
    # 音效 API（委托给 AssetManager）
    # =========================================================================

    def play_sfx(self, rel_path: str):
        """播放音效，委托给 ``AssetManager.get_sound().play()``。

        Args:
            rel_path: 相对于 ``assets/sounds/`` 的文件路径，如 ``"click.wav"``。
        """
        if not self._mixer_ok():
            return
        try:
            from src.asset_manager import AssetManager

            AssetManager.get_instance().get_sound(rel_path).play()
        except Exception:
            pass

    # =========================================================================
    # 音量 API
    # =========================================================================

    def set_music_volume(self, volume: float):
        """设置音乐音量，钳制在 [0.0, 1.0] 并即时应用到混音器。

        Args:
            volume: 目标音量值，越界值会被钳制。
        """
        self.music_volume = max(0.0, min(1.0, volume))
        if self._mixer_ok():
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except pygame.error:
                pass

    def set_sfx_volume(self, volume: float):
        """设置音效音量，钳制在 [0.0, 1.0]。

        注意：SFX 实际音量由 ``AssetManager._apply_settings_volume()``
        在每次 ``get_sound()`` 调用时从 ``GameManager.settings_data``
        读取。此方法仅更新内部记录；调用方需确保 ``settings_data``
        同步（参见 ``SettingsScreen`` 的处理方式）。

        Args:
            volume: 目标音量值，越界值会被钳制。
        """
        self.sfx_volume = max(0.0, min(1.0, volume))
