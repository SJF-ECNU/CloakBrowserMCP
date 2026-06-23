import pytest

from cloakbrowser_mcp.models import OperationResult, ScreenshotResult, SnapshotResult, StartResult
from cloakbrowser_mcp.server import ToolHandlers, create_server


class FakeSession:
    def __init__(self):
        self.calls = []

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

    async def wait_for_selector(self, selector, state="visible", timeout_ms=None):
        return OperationResult(ok=True, session_id="s1", message=f"waited {selector}")

    async def press(self, selector, key):
        return OperationResult(ok=True, session_id="s1", message=f"pressed {key}")

    async def hover(self, selector):
        return OperationResult(ok=True, session_id="s1", message=f"hovered {selector}")

    async def select_option(self, selector, value, frame_selector=None):
        from cloakbrowser_mcp.models import SelectResult

        self.calls.append(("select_option", selector, value, frame_selector))
        return SelectResult(session_id="s1", values=[value])

    async def get_text(self, selector=None):
        from cloakbrowser_mcp.models import TextResult

        return TextResult(session_id="s1", text="Example")

    async def get_attribute(self, selector, name):
        from cloakbrowser_mcp.models import AttributeResult

        return AttributeResult(session_id="s1", value="value")

    async def get_links(self, selector=None, limit=50):
        from cloakbrowser_mcp.models import LinksResult

        return LinksResult(session_id="s1", links=[{"text": "Example", "href": "https://example.com"}])

    async def scroll(self, delta_x=0, delta_y=0):
        return OperationResult(ok=True, session_id="s1")

    async def reload(self, wait_until="load"):
        from cloakbrowser_mcp.models import PageNavigationResult

        return PageNavigationResult(session_id="s1", url="https://example.com", title="Example")

    async def go_back(self, wait_until="load"):
        from cloakbrowser_mcp.models import PageNavigationResult

        return PageNavigationResult(
            session_id="s1", url="https://example.com", title="Example", message="no history entry"
        )

    async def go_forward(self, wait_until="load"):
        from cloakbrowser_mcp.models import PageNavigationResult

        return PageNavigationResult(
            session_id="s1", url="https://example.com", title="Example", message="no history entry"
        )

    async def get_cookies(self, urls=None):
        from cloakbrowser_mcp.models import CookiesResult

        return CookiesResult(session_id="s1", cookies=[])

    async def set_cookies(self, cookies):
        return OperationResult(ok=True, session_id="s1")

    async def clear_cookies(self):
        return OperationResult(ok=True, session_id="s1")

    async def get_storage_state(self):
        from cloakbrowser_mcp.models import StorageStateResult

        return StorageStateResult(session_id="s1", state={"cookies": [], "origins": []})

    async def save_storage_state(self, path):
        from cloakbrowser_mcp.models import StorageStateFileResult

        return StorageStateFileResult(session_id="s1", path=path)

    async def new_page(self, url=None, switch=True):
        from cloakbrowser_mcp.models import PageInfoResult

        return PageInfoResult(session_id="s1", page_id="p1", url=url or "about:blank", title="Example")

    async def list_pages(self):
        from cloakbrowser_mcp.models import PagesResult

        return PagesResult(
            session_id="s1",
            pages=[{"page_id": "p1", "url": "about:blank", "title": "Example", "is_active": True}],
        )

    async def switch_page(self, page_id):
        from cloakbrowser_mcp.models import PageInfoResult

        return PageInfoResult(session_id="s1", page_id=page_id, url="about:blank", title="Example")

    async def close_page(self, page_id=None):
        return OperationResult(ok=True, session_id="s1")


class FakeManager:
    def __init__(self):
        self.started_options = None
        self.session = FakeSession()
        self.closed = []
        self.close_all_calls = 0

    async def start(self, options):
        self.started_options = options
        return StartResult(session_id="s1", backend=options.backend.value, display_mode=options.display_mode.value)

    def get(self, session_id):
        assert session_id == "s1"
        return self.session

    async def close(self, session_id):
        self.closed.append(session_id)
        return OperationResult(ok=True, session_id=session_id)

    async def close_all(self):
        self.close_all_calls += 1


@pytest.mark.asyncio
async def test_browser_start_passes_options_to_manager():
    manager = FakeManager()
    handlers = ToolHandlers(manager)

    result = await handlers.browser_start(display_mode="virtual", proxy="http://proxy:8080")

    assert result == {"session_id": "s1", "backend": "direct", "display_mode": "virtual"}
    assert manager.started_options.proxy == "http://proxy:8080"


@pytest.mark.asyncio
async def test_browser_start_passes_task1_options_to_start_options():
    manager = FakeManager()
    handlers = ToolHandlers(manager)

    await handlers.browser_start(
        user_agent="CloakBrowser/1.0",
        viewport={"width": 1280, "height": 720},
        geoip=True,
        stealth_args=False,
        extra_http_headers={"X-Test": "1"},
        permissions=["geolocation"],
    )

    assert manager.started_options.user_agent == "CloakBrowser/1.0"
    assert manager.started_options.viewport == {"width": 1280, "height": 720}
    assert manager.started_options.geoip is True
    assert manager.started_options.stealth_args is False
    assert manager.started_options.extra_http_headers == {"X-Test": "1"}
    assert manager.started_options.permissions == ["geolocation"]


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
async def test_v2_tool_handlers_return_dicts():
    handlers = ToolHandlers(FakeManager())

    assert (await handlers.browser_wait_for_selector("s1", "#ready"))["ok"] is True
    assert (await handlers.browser_press("s1", "#q", "Enter"))["ok"] is True
    assert (await handlers.browser_hover("s1", ".menu"))["ok"] is True
    assert (await handlers.browser_select_option("s1", "select", "medium"))["values"] == ["medium"]
    assert (await handlers.browser_get_text("s1"))["text"] == "Example"
    assert (await handlers.browser_get_attribute("s1", "a", "href"))["value"] == "value"
    assert (await handlers.browser_get_links("s1"))["links"][0]["href"] == "https://example.com"
    assert (await handlers.browser_scroll("s1", delta_y=500))["ok"] is True
    assert (await handlers.browser_reload("s1"))["title"] == "Example"
    assert (await handlers.browser_go_back("s1"))["message"] == "no history entry"
    assert (await handlers.browser_go_forward("s1"))["message"] == "no history entry"
    assert (await handlers.browser_get_cookies("s1"))["cookies"] == []
    assert (await handlers.browser_set_cookies("s1", []))["ok"] is True
    assert (await handlers.browser_clear_cookies("s1"))["ok"] is True
    assert (await handlers.browser_get_storage_state("s1"))["state"] == {"cookies": [], "origins": []}
    assert (await handlers.browser_save_storage_state("s1", "/tmp/state.json"))["path"] == "/tmp/state.json"
    assert (await handlers.browser_new_page("s1", url="https://example.com"))["page_id"] == "p1"
    assert (await handlers.browser_list_pages("s1"))["pages"][0]["is_active"] is True
    assert (await handlers.browser_switch_page("s1", "p1"))["page_id"] == "p1"
    assert (await handlers.browser_close_page("s1"))["ok"] is True


@pytest.mark.asyncio
async def test_select_option_handler_forwards_frame_selector():
    manager = FakeManager()
    handlers = ToolHandlers(manager)

    result = await handlers.browser_select_option(
        "s1",
        "select",
        "medium",
        frame_selector="iframe#iframeResult",
    )

    assert result["values"] == ["medium"]
    assert manager.session.calls[-1] == (
        "select_option",
        "select",
        "medium",
        "iframe#iframeResult",
    )


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
        "browser_wait_for_selector",
        "browser_press",
        "browser_hover",
        "browser_select_option",
        "browser_get_text",
        "browser_get_attribute",
        "browser_get_links",
        "browser_scroll",
        "browser_reload",
        "browser_go_back",
        "browser_go_forward",
        "browser_get_cookies",
        "browser_set_cookies",
        "browser_clear_cookies",
        "browser_get_storage_state",
        "browser_save_storage_state",
        "browser_new_page",
        "browser_list_pages",
        "browser_switch_page",
        "browser_close_page",
    ]


@pytest.mark.asyncio
async def test_create_server_closes_all_sessions_on_lifespan_exit():
    manager = FakeManager()
    server = create_server(manager)

    async with server._mcp_server.lifespan(server._mcp_server):
        assert manager.close_all_calls == 0

    assert manager.close_all_calls == 1


@pytest.mark.asyncio
async def test_create_server_marks_snapshot_read_only_but_not_screenshot():
    server = create_server(FakeManager())
    tools = {tool.name: tool for tool in await server.list_tools()}

    for name in [
        "browser_snapshot",
        "browser_get_text",
        "browser_get_attribute",
        "browser_get_links",
        "browser_get_cookies",
        "browser_get_storage_state",
        "browser_list_pages",
    ]:
        assert tools[name].annotations.readOnlyHint is True

    for name in [
        "browser_screenshot",
        "browser_click",
        "browser_type",
        "browser_press",
        "browser_hover",
        "browser_select_option",
        "browser_scroll",
        "browser_reload",
        "browser_set_cookies",
        "browser_save_storage_state",
        "browser_new_page",
    ]:
        assert tools[name].annotations is None


@pytest.mark.asyncio
async def test_select_option_schema_includes_optional_frame_selector():
    server = create_server(FakeManager())
    tools = {tool.name: tool for tool in await server.list_tools()}
    schema = tools["browser_select_option"].inputSchema

    assert "frame_selector" in schema["properties"]
    assert "frame_selector" not in schema["required"]
