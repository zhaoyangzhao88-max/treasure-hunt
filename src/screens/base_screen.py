"""屏幕生命周期基类 — Microsoft Treasure Hunt

定义所有屏幕界面必须实现的抽象契约：
- on_enter / on_exit：生命周期钩子，支持跨屏数据传递
- handle_event / update / render：主循环三阶段分发

具体屏幕（主菜单、游戏中、商店、暂停等）继承此类并重写全部方法。
"""

from abc import ABC, abstractmethod

import pygame


class BaseScreen(ABC):
    """屏幕基类 — 所有屏幕的抽象模板。

    子类必须实现全部五个抽象方法，ScreenManager 通过此接口统一驱动各屏幕。
    """

    @abstractmethod
    def on_enter(self, data_payload: dict = None):
        """进入界面时执行。支持接收前一界面传来的任意键值对数据。

        Args:
            data_payload: 前一屏幕通过 switch_screen(data_payload=...) 传入的数据。
                          首次进入或无前屏时收到 None。
        """

    @abstractmethod
    def on_exit(self):
        """离开界面时执行。子类应在此释放临时资源或取消定时任务。"""

    @abstractmethod
    def handle_event(self, event: pygame.event.Event):
        """处理传入的 Pygame 基础事件。

        Args:
            event: pygame.event.get() 返回的单个事件对象。
        """

    @abstractmethod
    def update(self, dt: float):
        """逻辑更新，使用 dt 作为加权步长。

        Args:
            dt: 本帧时间间隔（秒），已由 GameManager 钳制到 [0.0, 0.25]。
        """

    @abstractmethod
    def render(self, surface: pygame.Surface):
        """画面绘制。

        Args:
            surface: 主渲染表面（通常为 GameManager.screen）。
        """
