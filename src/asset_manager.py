"""集中式资产管理器 — Microsoft Treasure Hunt

统一管理图片、音效、字体的加载、缓存与优雅退化。
保证"资源缺失绝不崩溃游戏" — 任何加载失败都有安全的回退方案。
"""

import os
import pygame


# =============================================================================
# 哑音类 — Pygame Sound 的静默替代品
# =============================================================================

class DummySound:
    """当音频系统未初始化或资源缺失时使用的静默占位类。

    接口与 pygame.mixer.Sound 一致，全部方法静默 no-op。
    """

    def play(self, *args, **kwargs):
        pass

    def stop(self):
        pass

    def set_volume(self, vol):
        pass

    def get_volume(self) -> float:
        return 0.0


# =============================================================================
# 资产管理器（单例）
# =============================================================================

class AssetManager:
    """集中式资源加载 + 缓存 + 降级管理器。

    使用单例模式，通过 get_instance() 获取全局唯一实例。
    """

    _instance = None

    def __init__(self, root: str = "assets/"):
        self.root = os.path.abspath(root)
        self._images = {}
        self._tilesheets = {}
        self._sounds = {}
        self._fonts = {}

    @classmethod
    def get_instance(cls, root: str = "assets/") -> "AssetManager":
        """获取或创建单例实例"""
        if cls._instance is None:
            cls._instance = cls(root)
        return cls._instance

    # =========================================================================
    # 清空缓存
    # =========================================================================

    def clear_cache(self):
        """清空所有内存缓存字典"""
        self._images.clear()
        self._tilesheets.clear()
        self._sounds.clear()
        self._fonts.clear()

    # =========================================================================
    # 图片加载
    # =========================================================================

    def get_image(self, rel_path: str, size: tuple = None) -> pygame.Surface:
        """加载图片精灵（懒加载 + 缓存 + 退化）。

        Args:
            rel_path: 相对于 assets/images/ 的文件路径
            size: 可选，指定返回尺寸 (width, height)

        Returns:
            成功返回加载后的 Surface；失败返回品红占位 Surface
        """
        cache_key = rel_path
        if cache_key in self._images:
            return self._images[cache_key]

        full_path = os.path.join(self.root, "images", rel_path)

        try:
            surface = pygame.image.load(full_path)
            if surface.get_alpha() is not None:
                surface = surface.convert_alpha()
            else:
                surface = surface.convert()
        except (pygame.error, FileNotFoundError, OSError):
            print(f"WARNING: Failed to load image '{rel_path}', using placeholder.")
            surface = self._create_placeholder_surface(size or (48, 48))

        self._images[cache_key] = surface
        return surface

    # =========================================================================
    # 音效加载
    # =========================================================================

    def get_sound(self, rel_path: str):
        """加载音效（懒加载 + 缓存 + 退化）。

        返回的 Sound 实例会自动应用 GameManager 中当前的 sfx_volume 设置，
        确保音量调节实时生效（包括从缓存命中时重新应用）。

        Args:
            rel_path: 相对于 assets/sounds/ 的文件路径

        Returns:
            成功返回 pygame.mixer.Sound；失败返回 DummySound
        """
        cache_key = rel_path
        if cache_key in self._sounds:
            sound = self._sounds[cache_key]
            self._apply_settings_volume(sound)
            return sound

        # 混音器未初始化 → 退化
        if not pygame.mixer.get_init():
            print(f"WARNING: Mixer not initialized, returning DummySound for '{rel_path}'.")
            sound = DummySound()
            self._sounds[cache_key] = sound
            return sound

        full_path = os.path.join(self.root, "sounds", rel_path)

        try:
            sound = pygame.mixer.Sound(full_path)
        except (pygame.error, FileNotFoundError, OSError):
            print(f"WARNING: Failed to load sound '{rel_path}', returning DummySound.")
            sound = DummySound()

        self._apply_settings_volume(sound)
        self._sounds[cache_key] = sound
        return sound

    def _apply_settings_volume(self, sound):
        """从 GameManager 全局设置中读取 sfx_volume 并应用到音效实例。

        安全在任何生命周期阶段调用：
        - GameManager 未初始化 → 静默跳过
        - settings_data 为 None → 使用默认音量 1.0
        """
        try:
            from src.game_manager import GameManager
            gm = GameManager.get_instance()
            if gm and gm.settings_data is not None:
                vol = gm.settings_data.get("sound_volume", 1.0)
                sound.set_volume(vol)
            else:
                sound.set_volume(1.0)
        except Exception:
            pass

    # =========================================================================
    # 字体加载
    # =========================================================================

    def get_font(self, font_name: str, size: int):
        """加载字体（懒加载 + 缓存 + 退化）。

        Args:
            font_name: 字体文件名或系统字体名
            size: 字号

        Returns:
            成功返回 Font 实例；失败降级为系统内置字体
        """
        cache_key = f"{font_name}_{size}"
        if cache_key in self._fonts:
            return self._fonts[cache_key]

        # 尝试加载字体文件（或系统字体名）
        font_paths_to_try = [
            os.path.join(self.root, "fonts", font_name),
            os.path.join(self.root, "fonts", font_name + ".ttf"),
            os.path.join(self.root, "fonts", font_name + ".otf"),
        ]

        font = None
        for path in font_paths_to_try:
            if os.path.isfile(path):
                try:
                    font = pygame.font.Font(path, size)
                    break
                except (pygame.error, OSError):
                    continue

        if font is None:
            print(f"WARNING: Failed to load font '{font_name}', falling back to built-in font.")
            # NOTE: pygame 2.6.1 on Windows has a bug in SysFont() font scanning;
            #       use Font(None) to get the built-in freesansbold font instead.
            font = pygame.font.Font(None, size)

        self._fonts[cache_key] = font
        return font

    # =========================================================================
    # 内部辅助
    # =========================================================================

    def _create_placeholder_surface(self, size: tuple) -> pygame.Surface:
        """创建品红占位 Surface（带对比色边框），代表缺失精灵"""
        surface = pygame.Surface(size, pygame.SRCALPHA)
        surface.fill((255, 0, 255, 255))  # 品红底色
        # 绘制对比色（绿色）边框
        border_rect = surface.get_rect()
        pygame.draw.rect(surface, (0, 255, 0), border_rect, 2)
        return surface
