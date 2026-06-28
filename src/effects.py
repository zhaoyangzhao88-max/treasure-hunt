"""动感特效物理引擎 — Microsoft Treasure Hunt

实现爆破粒子碎屑、浮动战斗文字与屏幕特效管理器。
为游戏提供「Game Juice」层面的动感反馈。

用法::

    manager = EffectsManager()
    manager.spawn_particles(400, 300, (255, 200, 0), 20)
    manager.spawn_text(400, 300, "+10 Gold!", (255, 215, 0))
    # 每帧：
    manager.update(dt)
    manager.render(surface, (camera.offset_x, camera.offset_y))
"""

import os as _os
import sys as _sys
import math
import random

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from config import TILE_SIZE


# =============================================================================
# 粒子类 — 带有重力与空气阻力的物理碎屑
# =============================================================================

class Particle:
    """单个物理粒子，受重力和空气阻力影响。

    Attributes:
        x, y: 世界像素坐标
        vx, vy: 速度（像素/秒）
        color: (R, G, B) 颜色
        size: 绘制半径（像素）
        lifetime: 剩余生命（秒）
        max_lifetime: 初始总寿命（秒）
    """

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 color: tuple, size: int = 4, lifetime: float = 0.8):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.lifetime = lifetime
        self.max_lifetime = lifetime

    def update(self, dt: float) -> bool:
        """推进一帧物理。

        Args:
            dt: 本帧时长（秒），被安全钳制到 [0, 0.25]

        Returns:
            True 表示粒子存活；False 表示寿命耗尽应被移除。
        """
        safe_dt = min(dt, 0.25)

        # 重力加速度（像素/秒²）
        self.vy += 300.0 * safe_dt

        # 空气阻力（速度衰减）
        self.vx *= 0.9
        self.vy *= 0.9

        # 更新位置
        self.x += self.vx * safe_dt
        self.y += self.vy * safe_dt

        # 生命衰减
        self.lifetime -= safe_dt

        return self.lifetime > 0

    def render(self, surface: pygame.Surface, camera_offset: tuple):
        """绘制粒子到屏幕。

        Args:
            surface: 目标 Surface
            camera_offset: (offset_x, offset_y) 摄像机偏移
        """
        sx = int(self.x - camera_offset[0])
        sy = int(self.y - camera_offset[1])

        # 计算生命透明度渐变
        life_ratio = max(0, self.lifetime / self.max_lifetime) if self.max_lifetime > 0 else 1.0
        alpha = int(life_ratio * 255)

        # 创建带 Alpha 的 Surface 并绘制圆点
        size = max(1, int(self.size * life_ratio))
        particle_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            particle_surf,
            (*self.color, alpha),
            (size, size),
            size,
        )
        surface.blit(particle_surf, (sx - size, sy - size))


# =============================================================================
# 浮动文本类 — 徐徐上飘并渐隐的文字
# =============================================================================

class FloatingText:
    """向上漂移并渐隐的浮动文字。

    Attributes:
        x, y: 世界像素坐标
        text: 显示文本内容
        color: (R, G, B) 颜色
        font: pygame.Font 实例
        lifetime: 剩余生命（秒）
        max_lifetime: 初始总寿命（默认 1.0s）
    """

    def __init__(self, x: float, y: float, text: str,
                 color: tuple, font: pygame.font.Font = None,
                 lifetime: float = 1.0, font_size: int = 24):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.font = font or pygame.font.Font(None, font_size)
        self.lifetime = lifetime
        self.max_lifetime = lifetime

    def update(self, dt: float) -> bool:
        """推进一帧动画。

        Args:
            dt: 本帧时长（秒）

        Returns:
            True 表示存活；False 应被移除。
        """
        safe_dt = min(dt, 0.25)

        # 以固定速度上漂
        self.y -= 60.0 * safe_dt

        # 生命衰减
        self.lifetime -= safe_dt

        return self.lifetime > 0

    def render(self, surface: pygame.Surface, camera_offset: tuple):
        """绘制浮动文字到屏幕。

        Args:
            surface: 目标 Surface
            camera_offset: (offset_x, offset_y) 摄像机偏移
        """
        sx = int(self.x - camera_offset[0])
        sy = int(self.y - camera_offset[1])

        # 文字基础渲染
        text_surf = self.font.render(self.text, True, self.color)

        # 生命期末段渐隐计算（剩余 < 40% 时开始淡出）
        fade_threshold = 0.4 * self.max_lifetime
        if self.lifetime < fade_threshold:
            alpha = max(0, int((self.lifetime / fade_threshold) * 255))
            text_surf.set_alpha(alpha)

        # 居中对齐绘制
        rect = text_surf.get_rect(center=(sx, sy))
        surface.blit(text_surf, rect)


# =============================================================================
# 效果管理器 — 统筹所有粒子和浮动文本
# =============================================================================

class EffectsManager:
    """全局特效管理器，维护粒子与浮动文本对象池。

    每帧调用 update(dt) 推进物理和动画，再调用 render()
    将所有特效绘制到屏幕。
    """

    def __init__(self):
        self.particles: list[Particle] = []
        self.floating_texts: list[FloatingText] = []
        # 默认字体
        self._font = None

    def _get_font(self) -> pygame.font.Font:
        """懒加载默认字体。"""
        if self._font is None:
            self._font = pygame.font.Font(None, 24)
        return self._font

    # ------------------------------------------------------------------
    # 生成接口
    # ------------------------------------------------------------------

    def spawn_particles(self, x: float, y: float, color: tuple,
                        count: int = 15):
        """在指定世界坐标产生一波碎屑粒子喷射。

        Args:
            x, y: 世界像素坐标
            color: (R, G, B) 颜色
            count: 粒子数量（默认 15）
        """
        for _ in range(count):
            # 随机方向（角度制 0~360°）
            angle = random.uniform(0, 2 * math.pi)
            # 随机速率 80~200 像素/秒
            speed = random.uniform(80.0, 200.0)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 80.0  # 略微向上偏
            size = random.randint(2, 5)
            lifetime = random.uniform(0.4, 0.9)

            particle = Particle(x, y, vx, vy, color, size, lifetime)
            self.particles.append(particle)

    def spawn_text(self, x: float, y: float, text: str, color: tuple,
                   font_size: int = 24):
        """在指定世界坐标生成一条浮动文本。

        Args:
            x, y: 世界像素坐标
            text: 显示文本
            color: (R, G, B) 颜色
            font_size: 字号（默认 24）
        """
        # 根据 font_size 决定使用缓存字体还是新建字体
        if font_size == 24:
            font = self._get_font()
        else:
            font = pygame.font.Font(None, font_size)
        ft = FloatingText(x, y, text, color, font=font)
        self.floating_texts.append(ft)

    # ------------------------------------------------------------------
    # 帧循环
    # ------------------------------------------------------------------

    def update(self, dt: float):
        """更新所有特效，移除已死亡效果。"""
        # 更新粒子，过滤死亡
        alive_particles = []
        for p in self.particles:
            if p.update(dt):
                alive_particles.append(p)
        self.particles = alive_particles

        # 更新浮动文字，过滤死亡
        alive_texts = []
        for ft in self.floating_texts:
            if ft.update(dt):
                alive_texts.append(ft)
        self.floating_texts = alive_texts

    def render(self, surface: pygame.Surface, camera_offset: tuple):
        """绘制所有特效到指定表面。

        Args:
            surface: 目标 Surface
            camera_offset: (offset_x, offset_y) 摄像机偏移
        """
        for p in self.particles:
            p.render(surface, camera_offset)

        for ft in self.floating_texts:
            ft.render(surface, camera_offset)

    def clear(self):
        """立即清空所有特效。"""
        self.particles.clear()
        self.floating_texts.clear()
