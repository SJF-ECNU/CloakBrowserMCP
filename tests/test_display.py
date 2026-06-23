import pytest

from cloakbrowser_mcp.display import VirtualDisplayManager
from cloakbrowser_mcp.errors import VirtualDisplayUnavailable
from cloakbrowser_mcp.models import DisplayMode


class FakeDisplay:
    def __init__(self, visible, size):
        self.visible = visible
        self.size = size
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


@pytest.mark.asyncio
async def test_headless_mode_does_not_start_virtual_display():
    manager = VirtualDisplayManager(display_factory=FakeDisplay, xvfb_exists=lambda: True)

    handle = await manager.ensure(DisplayMode.HEADLESS)

    assert handle is None


@pytest.mark.asyncio
async def test_virtual_mode_uses_existing_display(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":7")
    manager = VirtualDisplayManager(display_factory=FakeDisplay, xvfb_exists=lambda: True)

    handle = await manager.ensure(DisplayMode.VIRTUAL)

    assert handle is None


@pytest.mark.asyncio
async def test_virtual_mode_starts_xvfb_when_display_missing(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    manager = VirtualDisplayManager(display_factory=FakeDisplay, xvfb_exists=lambda: True)

    handle = await manager.ensure(DisplayMode.VIRTUAL)

    assert handle is not None
    assert handle.display.started is True
    await handle.close()
    assert handle.display.stopped is True


@pytest.mark.asyncio
async def test_virtual_mode_fails_when_xvfb_missing(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    manager = VirtualDisplayManager(display_factory=FakeDisplay, xvfb_exists=lambda: False)

    with pytest.raises(VirtualDisplayUnavailable, match="Xvfb"):
        await manager.ensure(DisplayMode.VIRTUAL)
