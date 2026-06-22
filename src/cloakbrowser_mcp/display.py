from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from typing import Callable, Protocol

from .errors import VirtualDisplayUnavailable
from .models import DisplayMode


class DisplayLike(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...


@dataclass(slots=True)
class VirtualDisplayHandle:
    display: DisplayLike

    async def close(self) -> None:
        await asyncio.to_thread(self.display.stop)


def _default_display_factory(visible: bool, size: tuple[int, int]) -> DisplayLike:
    from pyvirtualdisplay.display import Display

    return Display(visible=visible, size=size)


class VirtualDisplayManager:
    def __init__(
        self,
        *,
        display_factory: Callable[[bool, tuple[int, int]], DisplayLike] = _default_display_factory,
        xvfb_exists: Callable[[], bool] | None = None,
    ) -> None:
        self._display_factory = display_factory
        self._xvfb_exists = xvfb_exists or (lambda: shutil.which("Xvfb") is not None)

    async def ensure(self, display_mode: DisplayMode) -> VirtualDisplayHandle | None:
        if display_mode is not DisplayMode.VIRTUAL:
            return None
        if os.environ.get("DISPLAY"):
            return None
        if not self._xvfb_exists():
            raise VirtualDisplayUnavailable("Xvfb is required for display_mode='virtual'")
        display = self._display_factory(False, (1920, 1080))
        await asyncio.to_thread(display.start)
        return VirtualDisplayHandle(display)
