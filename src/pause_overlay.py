"""暂停菜单蒙层 — Microsoft Treasure Hunt

提供游戏内时停面板：半透明遮罩 + 暗灰对话框 + 4 个垂直按钮
（继续 / 重新开始 / 查看帮助 / 保存并退出），供 GameplayScreen 叠加渲染。

使用方式::

    overlay = PauseOverlay()
    overlay.update(mouse_pos)        # 每帧推进悬停状态
    overlay.render(surface)          # 叠加绘制
    action = overlay.button_action_at(mouse_pos)  # 命中测试
"""

import os as _os
import sys as _sys

# 将 src/ 加入模块搜索路径，使 `import config` 在任何工作目录下都能找到
_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

import pygame

from config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    HUD_HEIGHT,
    WHITE,
    BLACK,
    DARK_GREEN,
    GOLD,
)
from ui_helpers import Button


# 按钮动作常量（GameplayScreen 用于路由分发与单元测试直接调用）
ACTION_RESUME = "resume"
ACTION_RESTART = "restart"
ACTION_HELP = "help"
ACTION_SAVE_EXIT = "save_exit"


class PauseOverlay:
    """暂停时停蒙层对话框。

    几何布局（按任务书硬性规定）：
    - 半透明遮罩覆盖 (0, HUD_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT - HUD_HEIGHT)，Alpha=200
    - 暗灰面板 (332, 180, 360, 360)，框线色 (100, 116, 139)
    - 标题 "★ GAME PAUSED ★" 居中 Y=210，亮金色 (251, 191, 36)
    - 4 个垂直按钮水平居中，Y 分别在 260/330/400/470，宽 260 高 40
    """

    # 几何常量
    _PANEL_X = 332
    _PANEL_Y = 180
    _PANEL_W = 360
    _PANEL_H = 360
    _BUTTON_W = 260
    _BUTTON_H = 40
    _BUTTON_CX = SCREEN_WIDTH // 2            # 512
    _BUTTON_Y = (260, 330, 400, 470)

    # 颜色
    _PANEL_BORDER = (100, 116, 139)           # 浅钢蓝框线
    _PANEL_FILL = (30, 41, 59)                # 暗灰蓝填充
    _TITLE_COLOR = (251, 191, 36)             # 亮金色标题

    def __init__(self):
        """创建 4 个垂直排列的按钮 + 标题字体。"""
        # 标题字体（退化时回退到 default font）
        try:
            self._title_font = pygame.font.Font(None, 40)
            self._button_font = pygame.font.Font(None, 24)
        except Exception:
            self._title_font = pygame.font.SysFont("arial", 40)
            self._button_font = pygame.font.SysFont("arial", 24)

        self._buttons: list[tuple[Button, str]] = []
        labels = [
            ("继续游戏 (Resume)", ACTION_RESUME),
            ("重新开始本关 (Restart Level)", ACTION_RESTART),
            ("查看帮助 (Help & Controls)", ACTION_HELP),
            ("保存并退出 (Save & Exit)", ACTION_SAVE_EXIT),
        ]
        for (label, action), y in zip(labels, self._BUTTON_Y):
            btn = Button(
                text=label,
                center_pos=(self._BUTTON_CX, y),
                width=self._BUTTON_W,
                height=self._BUTTON_H,
                font=self._button_font,
                normal_color=DARK_GREEN,
                hover_color=GOLD,
                text_color=WHITE,
            )
            self._buttons.append((btn, action))

    @property
    def buttons(self) -> list[Button]:
        """以纯量按钮列表形式暴露（供渲染/测试使用）。"""
        return [btn for btn, _ in self._buttons]

    def update(self, mouse_pos: tuple) -> bool:
        """每帧推进按钮悬停，返回任意按钮刚进入悬停的突变信号。

        Args:
            mouse_pos: 当前鼠标坐标 (x, y)

        Returns:
            任一按钮刚从非悬停进入悬停时返回 True（供外层播 hover 音效）
        """
        any_hover_enter = False
        for btn, _ in self._buttons:
            if btn.update(mouse_pos):
                any_hover_enter = True
        return any_hover_enter

    def button_action_at(self, pos: tuple) -> str | None:
        """命中测试：返回指定像素命中的按钮动作常量，未命中返回 None。

        Args:
            pos: 待测像素坐标 (x, y)

        Returns:
            命中按钮对应的 ACTION_* 常量；未命中 / 按钮禁用返回 None
        """
        for btn, action in self._buttons:
            if btn.is_enabled and btn.rect.collidepoint(pos):
                return action
        return None

    def render(self, surface: pygame.Surface):
        """在半透明遮罩之上绘制暗灰面板 + 标题 + 4 个按钮。"""
        # 1) 半透明黑色遮罩（只覆盖 HUD 以下的游戏区）
        scrim_rect = pygame.Rect(0, HUD_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT - HUD_HEIGHT)
        scrim = pygame.Surface(scrim_rect.size, pygame.SRCALPHA)
        scrim.fill((0, 0, 0, 200))               # alpha=200 时停状态
        surface.blit(scrim, scrim_rect.topleft)

        # 2) 暗灰对话框容器（带浅色框线）
        panel_rect = pygame.Rect(self._PANEL_X, self._PANEL_Y,
                                 self._PANEL_W, self._PANEL_H)
        pygame.draw.rect(surface, self._PANEL_FILL, panel_rect)
        pygame.draw.rect(surface, self._PANEL_BORDER, panel_rect, 3)

        # 3) 标题 "★ GAME PAUSED ★" 居中 Y=210
        title_surf = self._title_font.render("★ GAME PAUSED ★", True, self._TITLE_COLOR)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, 210))
        surface.blit(title_surf, title_rect)

        # 4) 遍历绘制 4 个按钮
        for btn, _ in self._buttons:
            btn.render(surface)
