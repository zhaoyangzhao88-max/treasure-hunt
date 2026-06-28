"""UI 共享组件 — Microsoft Treasure Hunt

提供跨屏幕复用的 UI 辅助类（如 Button）。
"""

import pygame

from src.config import (
    GRAY,
    SILVER,
    WHITE,
    BLACK,
    DARK_GREEN,
    GOLD,
)


# =============================================================================
# 按钮辅助类
# =============================================================================

class Button:
    """通用按钮 — 支持三态绘制（正常 / 悬停 / 禁用）与悬停突变检测。

    用法::

        btn = Button("开始", (512, 350), 240, 50, font, DARK_GREEN, GOLD, WHITE)
        just_hovered = btn.update(mouse_pos)   # True = 刚从非悬停进入悬停
        btn.render(surface)
    """

    def __init__(
        self,
        text: str,
        center_pos: tuple,
        width: int,
        height: int,
        font: pygame.font.Font,
        normal_color: tuple = DARK_GREEN,
        hover_color: tuple = GOLD,
        text_color: tuple = WHITE,
    ):
        """构造按钮。

        Args:
            text:          按钮显示文本
            center_pos:    中心坐标 (x, y)
            width:         按钮宽度（像素）
            height:        按钮高度（像素）
            font:          Pygame 字体对象
            normal_color:  正常态背景色 (R, G, B)
            hover_color:   悬停态背景色 (R, G, B)
            text_color:    文字颜色 (R, G, B)
        """
        self.text = text
        self.width = width
        self.height = height
        self.font = font
        self.normal_color = normal_color
        self.hover_color = hover_color
        self.text_color = text_color

        # 根据中心点计算边界矩形
        self.rect = pygame.Rect(0, 0, width, height)
        self.rect.center = center_pos

        self.is_hovered: bool = False
        self.is_enabled: bool = True

    # =========================================================================
    # 状态更新
    # =========================================================================

    def update(self, mouse_pos: tuple) -> bool:
        """每帧调用，传入当前鼠标坐标，更新悬停状态。

        悬停突变检测：当鼠标刚从「非悬停」滑入「悬停」时返回 True，
        提示外层逻辑播放悬停音效。其余情况返回 False。

        Args:
            mouse_pos: 鼠标坐标 (x, y)

        Returns:
            True  — 刚进入悬停（非悬停 → 悬停的状态突变）
            False — 无突变（已在悬停 / 离开悬停 / 禁用）
        """
        if not self.is_enabled:
            # 禁用按钮：强制不悬停，无突变信号
            was_hovered = self.is_hovered
            self.is_hovered = False
            return False

        was_hovered = self.is_hovered
        self.is_hovered = self.rect.collidepoint(mouse_pos)

        # 突变检测：刚从 False 变为 True
        return self.is_hovered and not was_hovered

    # =========================================================================
    # 绘制
    # =========================================================================

    def render(self, surface: pygame.Surface):
        """在指定 Surface 上绘制按钮。

        三态绘制：
        - 禁用：灰色背景 + 淡色文字（半透明叠加）
        - 悬停：hover_color 填充 + 对比色边框
        - 正常：normal_color 填充 + 对比色边框
        """
        if not self.is_enabled:
            # ---- 禁用态 ----
            pygame.draw.rect(surface, GRAY, self.rect)
            pygame.draw.rect(surface, SILVER, self.rect, 2)
            text_surf = self.font.render(self.text, True, SILVER)
            text_rect = text_surf.get_rect(center=self.rect.center)
            surface.blit(text_surf, text_rect)
            return

        if self.is_hovered:
            # ---- 悬停态 ----
            pygame.draw.rect(surface, self.hover_color, self.rect)
            pygame.draw.rect(surface, WHITE, self.rect, 3)
            text_surf = self.font.render(self.text, True, BLACK)
        else:
            # ---- 正常态 ----
            pygame.draw.rect(surface, self.normal_color, self.rect)
            pygame.draw.rect(surface, WHITE, self.rect, 2)
            text_surf = self.font.render(self.text, True, self.text_color)

        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)
