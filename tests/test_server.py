import pytest

from cloakbrowser_mcp.models import OperationResult, ScreenshotResult, SnapshotResult, StartResult
from cloakbrowser_mcp.server import ToolHandlers, create_server


class FakeSession:
    async def navigate(self, url, wait_until="load"):
        return {"session_id": "s1", "url": url, "title": "Example Domain"}

    async def click(self, selector):
        return OperationResult(ok=True, session_id="s1", message=f"clicked {selector}")

    async def type_text(self, selector, text):
        return OperationResult(ok=True, session_id="s1", message=f"typed {selector}")

    async def evaluate(self, script):
        return {"script": script}

    async def snapshot(self):
        return SnapshotResult(session_id="s1", url="https://example.com", title="Example Domain", text="Example")

    async def screenshot(self, full_page=False):
        return ScreenshotResult(session_id="s1", path="/tmp/s1.png")


class FakeManager:
    def __init__(self):
        self.started_options = None
        self.session = FakeSession()
        self.closed = []

    async def start(self, options):
        self.started_options = options
        return StartResult(session_id="s1", backend=options.backend.value, display_mode=options.display_mode.value)

    def get(self, session_id):
        assert session_id == "s1"
        return self.session

    async def close(self, session_id):
        self.closed.append(session_id)
        return OperationResult(ok=True, session_id=session_id)


@pytest.mark.asyncio
async def test_browser_start_passes_options_to_manager():
    manager = FakeManager()
    handlers = ToolHandlers(manager)

    result = await handlers.browser_start(display_mode="virtual", proxy="http://proxy:8080")

    assert result == {"session_id": "s1", "backend": "direct", "display_mode": "virtual"}
    assert manager.started_options.proxy == "http://proxy:8080"


@pytest.mark.asyncio
async def test_page_tools_return_dicts():
    handlers = ToolHandlers(FakeManager())

    assert await handlers.browser_navigate("s1", "https://example.com") == {
        "session_id": "s1",
        "url": "https://example.com",
        "title": "Example Domain",
    }
    assert (await handlers.browser_click("s1", "button"))["ok"] is True
    assert (await handlers.browser_type("s1", "#q", "hello"))["ok"] is True
    assert await handlers.browser_evaluate("s1", "() => 42") == {"script": "() => 42"}
    assert (await handlers.browser_snapshot("s1"))["text"] == "Example"
    assert (await handlers.browser_screenshot("s1"))["path"] == "/tmp/s1.png"


@pytest.mark.asyncio
async def test_browser_close_delegates_to_manager():
    manager = FakeManager()
    handlers = ToolHandlers(manager)

    result = await handlers.browser_close("s1")

    assert result["ok"] is True
    assert manager.closed == ["s1"]


@pytest.mark.asyncio
async def test_create_server_registers_only_approved_tools():
    server = create_server(FakeManager())

    assert [tool.name for tool in await server.list_tools()] == [
        "browser_start",
        "browser_navigate",
        "browser_click",
        "browser_type",
        "browser_evaluate",
        "browser_snapshot",
        "browser_screenshot",
        "browser_close",
    ]
