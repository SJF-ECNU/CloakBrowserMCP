import os
from pathlib import Path

import pytest

from cloakbrowser_mcp.browser import BrowserManager
from cloakbrowser_mcp.models import StartOptions


pytestmark = pytest.mark.smoke


def _smoke_enabled(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


@pytest.mark.asyncio
async def test_real_headless_example_dot_com_smoke():
    if not _smoke_enabled("CLOAK_MCP_RUN_SMOKE"):
        pytest.skip("Set CLOAK_MCP_RUN_SMOKE=1 to run real browser smoke tests")

    manager = BrowserManager()
    result = await manager.start(StartOptions.from_values(display_mode="headless"))
    try:
        nav = await manager.get(result.session_id).navigate("https://example.com", wait_until="domcontentloaded")
        snapshot = await manager.get(result.session_id).snapshot()
        screenshot = await manager.get(result.session_id).screenshot()

        assert "Example" in nav["title"]
        assert "Example Domain" in snapshot.text
        assert Path(screenshot.path).exists()
    finally:
        await manager.close_all()


@pytest.mark.asyncio
async def test_real_virtual_example_dot_com_smoke():
    if not _smoke_enabled("CLOAK_MCP_RUN_VIRTUAL_SMOKE"):
        pytest.skip("Set CLOAK_MCP_RUN_VIRTUAL_SMOKE=1 to run Xvfb smoke tests")

    manager = BrowserManager()
    result = await manager.start(StartOptions.from_values(display_mode="virtual"))
    try:
        nav = await manager.get(result.session_id).navigate("https://example.com", wait_until="domcontentloaded")
        assert "Example" in nav["title"]
    finally:
        await manager.close_all()


@pytest.mark.asyncio
async def test_real_cdp_example_dot_com_smoke():
    cdp_url = os.environ.get("CLOAK_MCP_SMOKE_CDP_URL")
    if not cdp_url:
        pytest.skip("Set CLOAK_MCP_SMOKE_CDP_URL to run CDP smoke tests")

    manager = BrowserManager()
    result = await manager.start(StartOptions.from_values(backend="cdp", cdp_url=cdp_url, fingerprint="smoke"))
    try:
        nav = await manager.get(result.session_id).navigate("https://example.com", wait_until="domcontentloaded")
        assert "Example" in nav["title"]
    finally:
        await manager.close_all()
