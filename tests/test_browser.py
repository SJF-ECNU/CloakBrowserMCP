from pathlib import Path

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from cloakbrowser_mcp.browser import BrowserManager, BrowserSession, CdpBackend, DirectBackend
from cloakbrowser_mcp.errors import (
    CdpConnectionFailed,
    ElementNotFound,
    ScreenshotFailed,
    SessionNotFound,
    StorageStateFailed,
)
from cloakbrowser_mcp.models import BackendMode, DisplayMode, StartOptions


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.actions = []
        self.fail_selector = False
        self.selector_timeout_error = TimeoutError
        self.fail_screenshot = False
        self.closed = False
        self.close_error = None
        self.goto_error = None

    async def goto(self, url, wait_until="load"):
        self.actions.append(("goto", url, wait_until))
        if self.goto_error is not None:
            raise self.goto_error
        self.url = url

    async def title(self):
        return "Example Domain"

    async def click(self, selector):
        if self.fail_selector:
            raise self.selector_timeout_error("selector timeout")
        self.actions.append(("click", selector))

    async def fill(self, selector, text):
        if self.fail_selector:
            raise self.selector_timeout_error("selector timeout")
        self.actions.append(("fill", selector, text))

    async def wait_for_selector(self, selector, state="visible", timeout=None):
        if self.fail_selector:
            raise self.selector_timeout_error("selector timeout")
        self.actions.append(("wait_for_selector", selector, state, timeout))
        return object()

    async def press(self, selector, key):
        if self.fail_selector:
            raise self.selector_timeout_error("selector timeout")
        self.actions.append(("press", selector, key))

    async def hover(self, selector):
        if self.fail_selector:
            raise self.selector_timeout_error("selector timeout")
        self.actions.append(("hover", selector))

    async def select_option(self, selector, value):
        if self.fail_selector:
            raise self.selector_timeout_error("selector timeout")
        self.actions.append(("select_option", selector, value))
        return [value]

    def frame_locator(self, selector):
        self.actions.append(("frame_locator", selector))
        return FakeFrameLocator(self, selector)

    async def text_content(self, selector):
        if self.fail_selector:
            raise self.selector_timeout_error("selector timeout")
        self.actions.append(("text_content", selector))
        return "Selected text"

    async def get_attribute(self, selector, name):
        if self.fail_selector:
            raise self.selector_timeout_error("selector timeout")
        self.actions.append(("get_attribute", selector, name))
        return "attribute value"

    async def evaluate(self, script):
        self.actions.append(("evaluate", script))
        if script == "() => document.body.innerText":
            return "Example Domain\nText"
        if script == "() => window.scrollBy(0, 500)":
            return None
        if "Array.from" in script and "querySelectorAll" in script:
            return [
                {"text": "One", "href": "https://example.com/one"},
                {"text": "Two", "href": "https://example.com/two"},
                {"text": "Three", "href": "https://example.com/three"},
            ]
        return {"value": 42}

    async def screenshot(self, path, full_page=False):
        if self.fail_screenshot:
            raise RuntimeError("cannot capture")
        Path(path).write_bytes(b"png")
        self.actions.append(("screenshot", path, full_page))

    async def reload(self, wait_until="load"):
        self.actions.append(("reload", wait_until))

    async def go_back(self, wait_until="load"):
        self.actions.append(("go_back", wait_until))
        return None

    async def go_forward(self, wait_until="load"):
        self.actions.append(("go_forward", wait_until))
        return None

    async def close(self):
        self.actions.append(("close",))
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class FakeFrameLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    def locator(self, selector):
        self.page.actions.append(("frame_locator_locator", self.selector, selector))
        return FakeFrameElement(self.page, self.selector, selector)


class FakeFrameElement:
    def __init__(self, page, frame_selector, selector):
        self.page = page
        self.frame_selector = frame_selector
        self.selector = selector

    async def select_option(self, value):
        if self.page.fail_selector:
            raise self.page.selector_timeout_error("selector timeout")
        self.page.actions.append(("frame_select_option", self.frame_selector, self.selector, value))
        return [value]


class FakeClosable:
    def __init__(self, *, close_error=None):
        self.closed = False
        self.close_calls = 0
        self.close_error = close_error

    async def close(self):
        self.close_calls += 1
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class FakeBackend:
    def __init__(self, session):
        self.session = session
        self.options = None

    async def start(self, options):
        self.options = options
        return self.session


class FakeDisplayHandle(FakeClosable):
    pass


class FakeDisplayManager:
    def __init__(self, handle=None):
        self.handle = handle
        self.display_modes = []

    async def ensure(self, display_mode):
        self.display_modes.append(display_mode)
        return self.handle


class FakeDirectContext(FakeClosable):
    def __init__(self, *, fail_new_page=False):
        super().__init__()
        self.fail_new_page = fail_new_page
        self.new_page_calls = 0
        self.pages = []
        self.cookies_value = [{"name": "sid", "value": "123", "domain": "example.com", "path": "/"}]
        self.added_cookies = []
        self.cleared_cookies = False

    async def new_page(self):
        self.new_page_calls += 1
        if self.fail_new_page:
            raise RuntimeError("page failed")
        page = FakePage()
        self.pages.append(page)
        return page

    async def cookies(self, urls=None):
        return self.cookies_value

    async def add_cookies(self, cookies):
        self.added_cookies.extend(cookies)

    async def clear_cookies(self):
        self.cleared_cookies = True

    async def storage_state(self, path=None):
        state = {"cookies": self.cookies_value, "origins": []}
        if path:
            Path(path).write_text('{"cookies": [], "origins": []}', encoding="utf-8")
        return state


class FakeCdpContext(FakeClosable):
    def __init__(self, pages=None, *, fail_new_page=False):
        super().__init__()
        self.pages = list(pages or [])
        self.fail_new_page = fail_new_page

    async def new_page(self):
        if self.fail_new_page:
            raise RuntimeError("page failed")
        page = FakePage()
        self.pages.append(page)
        return page


class FakeCdpBrowser(FakeClosable):
    def __init__(self, contexts=None, *, new_context=None):
        super().__init__()
        self.contexts = list(contexts or [])
        self._new_context = new_context or FakeCdpContext()

    async def new_context(self):
        self.contexts.append(self._new_context)
        return self._new_context


class FakeChromium:
    def __init__(self, *, browser=None, connect_error=None):
        self.browser = browser
        self.connect_error = connect_error
        self.urls = []

    async def connect_over_cdp(self, url):
        self.urls.append(url)
        if self.connect_error is not None:
            raise self.connect_error
        return self.browser


class FakePlaywright:
    def __init__(self, chromium, *, stop_error=None):
        self.chromium = chromium
        self.stopped = False
        self.stop_calls = 0
        self.stop_error = stop_error

    async def stop(self):
        self.stop_calls += 1
        self.stopped = True
        if self.stop_error is not None:
            raise self.stop_error


def fake_playwright_factory(playwright):
    async def _factory():
        return playwright

    return _factory


@pytest.mark.asyncio
async def test_session_navigates_and_returns_title(tmp_path):
    page = FakePage()
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    result = await session.navigate("https://example.com", wait_until="domcontentloaded")

    assert result == {"session_id": "s1", "url": "https://example.com", "title": "Example Domain"}
    assert page.actions == [("goto", "https://example.com", "domcontentloaded")]


@pytest.mark.asyncio
async def test_session_click_wraps_selector_timeout(tmp_path):
    page = FakePage()
    page.fail_selector = True
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    with pytest.raises(ElementNotFound, match="button.submit"):
        await session.click("button.submit")


@pytest.mark.asyncio
async def test_session_click_wraps_playwright_selector_timeout(tmp_path):
    page = FakePage()
    page.fail_selector = True
    page.selector_timeout_error = PlaywrightTimeoutError
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    with pytest.raises(ElementNotFound, match="button.submit"):
        await session.click("button.submit")


@pytest.mark.asyncio
async def test_session_type_uses_fill(tmp_path):
    page = FakePage()
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    result = await session.type_text("#q", "hello")

    assert result.to_dict()["ok"] is True
    assert ("fill", "#q", "hello") in page.actions


@pytest.mark.asyncio
async def test_session_type_wraps_playwright_selector_timeout(tmp_path):
    page = FakePage()
    page.fail_selector = True
    page.selector_timeout_error = PlaywrightTimeoutError
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    with pytest.raises(ElementNotFound, match="#q"):
        await session.type_text("#q", "hello")


@pytest.mark.asyncio
async def test_session_snapshot_reads_page_text(tmp_path):
    page = FakePage()
    page.url = "https://example.com"
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    snapshot = await session.snapshot()

    assert snapshot.to_dict() == {
        "session_id": "s1",
        "url": "https://example.com",
        "title": "Example Domain",
        "text": "Example Domain\nText",
    }


@pytest.mark.asyncio
async def test_session_page_operation_methods(tmp_path):
    page = FakePage()
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    assert (await session.wait_for_selector("#ready", state="attached", timeout_ms=500)).ok is True
    assert (await session.press("#q", "Enter")).ok is True
    assert (await session.hover(".menu")).ok is True
    assert (await session.select_option("select", "medium")).values == ["medium"]
    assert (await session.get_text("#result")).text == "Selected text"
    assert (await session.get_attribute("a", "href")).value == "attribute value"
    assert (await session.scroll(delta_x=0, delta_y=500)).ok is True
    assert (await session.reload(wait_until="domcontentloaded")).title == "Example Domain"
    assert (await session.go_back(wait_until="load")).message == "no history entry"
    assert (await session.go_forward(wait_until="load")).message == "no history entry"

    assert ("wait_for_selector", "#ready", "attached", 500) in page.actions
    assert ("press", "#q", "Enter") in page.actions
    assert ("hover", ".menu") in page.actions
    assert ("select_option", "select", "medium") in page.actions
    assert ("evaluate", "() => window.scrollBy(0, 500)") in page.actions
    assert ("reload", "domcontentloaded") in page.actions


@pytest.mark.asyncio
async def test_session_select_option_can_target_frame_selector(tmp_path):
    page = FakePage()
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    result = await session.select_option("select", "medium", frame_selector="iframe#iframeResult")

    assert result.values == ["medium"]
    assert ("frame_locator", "iframe#iframeResult") in page.actions
    assert ("frame_locator_locator", "iframe#iframeResult", "select") in page.actions
    assert ("frame_select_option", "iframe#iframeResult", "select", "medium") in page.actions


@pytest.mark.asyncio
async def test_session_get_text_without_selector_reads_body_text(tmp_path):
    page = FakePage()
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    result = await session.get_text()

    assert result.text == "Example Domain\nText"


@pytest.mark.asyncio
async def test_session_get_links_limits_results(tmp_path):
    page = FakePage()
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    links = await session.get_links(limit=2)
    evaluate_script = page.actions[-1][1]

    assert len(links.links) == 2
    assert links.links[0] == {"text": "One", "href": "https://example.com/one"}
    assert "const selector = null;" in evaluate_script
    assert "None" not in evaluate_script


@pytest.mark.asyncio
async def test_session_get_links_rejects_non_int_limit_before_evaluate(tmp_path):
    page = FakePage()
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    with pytest.raises(ValueError, match="limit"):
        await session.get_links(limit="2); window.evil = true; //")  # type: ignore[arg-type]

    assert page.actions == []


@pytest.mark.asyncio
async def test_session_context_state_methods(tmp_path):
    context = FakeDirectContext()
    page = await context.new_page()
    session = BrowserSession("s1", page, context, None, tmp_path, "direct", "headless")

    assert (await session.get_cookies()).cookies == context.cookies_value
    assert (
        await session.set_cookies([{"name": "token", "value": "abc", "domain": "example.com", "path": "/"}])
    ).ok is True
    assert context.added_cookies[0]["name"] == "token"
    assert (await session.clear_cookies()).ok is True
    assert context.cleared_cookies is True
    assert (await session.get_storage_state()).state == {"cookies": context.cookies_value, "origins": []}

    state_path = tmp_path / "state.json"
    result = await session.save_storage_state(state_path)

    assert result.path == str(state_path)
    assert state_path.exists()


@pytest.mark.asyncio
async def test_session_page_management(tmp_path):
    context = FakeDirectContext()
    first_page = await context.new_page()
    session = BrowserSession("s1", first_page, context, None, tmp_path, "direct", "headless")

    pages = await session.list_pages()
    assert len(pages.pages) == 1
    assert pages.pages[0]["is_active"] is True

    new_page = await session.new_page(url="https://example.com/two", switch=True)
    assert new_page.url == "https://example.com/two"
    assert session.page.url == "https://example.com/two"

    pages = await session.list_pages()
    assert len(pages.pages) == 2
    assert sum(1 for page_info in pages.pages if page_info["is_active"]) == 1

    await session.switch_page(pages.pages[0]["page_id"])
    assert session.page is first_page

    result = await session.close_page(new_page.page_id)
    assert result.ok is True
    assert ("close",) in context.pages[1].actions


@pytest.mark.asyncio
async def test_session_new_page_navigation_failure_cleans_unregistered_page(tmp_path):
    context = FakeDirectContext()
    first_page = await context.new_page()
    session = BrowserSession("s1", first_page, context, None, tmp_path, "direct", "headless")
    original_page_id = session._active_page_id
    original_pages = dict(session._pages)

    failed_page = FakePage()
    failed_page.goto_error = RuntimeError("navigation failed")

    async def new_failed_page():
        context.new_page_calls += 1
        context.pages.append(failed_page)
        return failed_page

    context.new_page = new_failed_page

    with pytest.raises(RuntimeError, match="navigation failed"):
        await session.new_page(url="https://example.com/fail", switch=True)

    assert session._pages == original_pages
    assert session._active_page_id == original_page_id
    assert session.page is first_page
    assert failed_page.closed is True


@pytest.mark.asyncio
async def test_session_close_active_page_selects_remaining_page(tmp_path):
    context = FakeDirectContext()
    first_page = await context.new_page()
    session = BrowserSession("s1", first_page, context, None, tmp_path, "direct", "headless")
    new_page = await session.new_page(url="https://example.com/two", switch=True)

    result = await session.close_page(new_page.page_id)

    assert result.ok is True
    assert session.page is first_page
    pages = await session.list_pages()
    assert len(pages.pages) == 1
    assert pages.pages[0]["is_active"] is True


@pytest.mark.asyncio
async def test_session_close_last_page_creates_replacement_page(tmp_path):
    context = FakeDirectContext()
    first_page = await context.new_page()
    session = BrowserSession("s1", first_page, context, None, tmp_path, "direct", "headless")

    result = await session.close_page()

    assert result.ok is True
    assert first_page.closed is True
    assert ("close",) in first_page.actions
    assert len(context.pages) == 2
    assert session.page is context.pages[1]
    pages = await session.list_pages()
    assert len(pages.pages) == 1
    assert pages.pages[0]["is_active"] is True


@pytest.mark.asyncio
async def test_session_close_last_page_replacement_failure_preserves_registry(tmp_path):
    context = FakeDirectContext()
    first_page = await context.new_page()
    session = BrowserSession("s1", first_page, context, None, tmp_path, "direct", "headless")
    original_page_id = session._active_page_id
    context.fail_new_page = True

    with pytest.raises(RuntimeError, match="page failed"):
        await session.close_page()

    assert session._pages == {original_page_id: first_page}
    assert session._active_page_id == original_page_id
    assert session.page is first_page
    assert first_page.closed is False


@pytest.mark.asyncio
async def test_session_close_last_page_close_failure_cleans_replacement(tmp_path):
    context = FakeDirectContext()
    first_page = await context.new_page()
    close_error = RuntimeError("close failed")
    first_page.close_error = close_error
    session = BrowserSession("s1", first_page, context, None, tmp_path, "direct", "headless")
    original_page_id = session._active_page_id

    with pytest.raises(RuntimeError, match="close failed") as excinfo:
        await session.close_page()

    assert excinfo.value is close_error
    assert len(context.pages) == 2
    replacement_page = context.pages[1]
    assert replacement_page.closed is True
    assert session._pages == {original_page_id: first_page}
    assert session._active_page_id == original_page_id
    assert session.page is first_page
    assert first_page.closed is False


@pytest.mark.asyncio
async def test_session_save_storage_state_wraps_parent_creation_failure(tmp_path):
    context = FakeDirectContext()
    page = await context.new_page()
    session = BrowserSession("s1", page, context, None, tmp_path, "direct", "headless")
    blocked_parent = tmp_path / "state-parent"
    blocked_parent.write_text("not a directory", encoding="utf-8")

    with pytest.raises(StorageStateFailed, match="Failed to write storage state"):
        await session.save_storage_state(blocked_parent / "state.json")


@pytest.mark.asyncio
async def test_session_scroll_rejects_non_int_deltas_before_evaluate(tmp_path):
    page = FakePage()
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    with pytest.raises(ValueError, match="delta_x"):
        await session.scroll(delta_x="0); window.evil = true; //", delta_y=500)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="delta_y"):
        await session.scroll(delta_x=0, delta_y="500); window.evil = true; //")  # type: ignore[arg-type]

    assert page.actions == []


@pytest.mark.asyncio
async def test_session_screenshot_writes_unique_file(tmp_path):
    page = FakePage()
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    result = await session.screenshot(full_page=True)

    assert Path(result.path).exists()
    assert Path(result.path).read_bytes() == b"png"
    assert page.actions[-1][2] is True


@pytest.mark.asyncio
async def test_session_screenshot_wraps_failures(tmp_path):
    page = FakePage()
    page.fail_screenshot = True
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    with pytest.raises(ScreenshotFailed, match="s1"):
        await session.screenshot()


@pytest.mark.asyncio
async def test_session_close_closes_context_then_browser(tmp_path):
    context = FakeClosable()
    browser = FakeClosable()
    session = BrowserSession("s1", FakePage(), context, browser, tmp_path, "direct", "headless")

    await session.close()

    assert context.closed is True
    assert browser.closed is True


@pytest.mark.asyncio
async def test_session_close_stops_playwright_and_closes_display_after_context_close_failure(tmp_path):
    cleanup_error = RuntimeError("context close failed")
    context = FakeClosable(close_error=cleanup_error)
    browser = FakeClosable()
    display_handle = FakeDisplayHandle()
    playwright = FakePlaywright(FakeChromium(), stop_error=None)
    session = BrowserSession(
        "s1",
        FakePage(),
        context,
        browser,
        tmp_path,
        "cdp",
        "cdp",
        display_handle=display_handle,
        playwright=playwright,
    )

    with pytest.raises(RuntimeError, match="context close failed") as excinfo:
        await session.close()

    assert excinfo.value is cleanup_error
    assert context.close_calls == 1
    assert browser.close_calls == 1
    assert playwright.stop_calls == 1
    assert display_handle.close_calls == 1


@pytest.mark.asyncio
async def test_manager_starts_session_with_selected_backend(tmp_path):
    session = BrowserSession("fixed", FakePage(), FakeClosable(), None, tmp_path, "direct", "headless")
    direct = FakeBackend(session)
    manager = BrowserManager(direct_backend=direct, cdp_backend=FakeBackend(session))

    result = await manager.start(StartOptions.from_values())

    assert result.session_id == "fixed"
    assert result.backend == "direct"
    assert manager.get("fixed") is session
    assert direct.options.backend is BackendMode.DIRECT


@pytest.mark.asyncio
async def test_manager_uses_cdp_backend(tmp_path):
    session = BrowserSession("cdp1", FakePage(), FakeClosable(), None, tmp_path, "cdp", "cdp")
    cdp = FakeBackend(session)
    manager = BrowserManager(direct_backend=FakeBackend(session), cdp_backend=cdp)

    result = await manager.start(StartOptions.from_values(backend="cdp", cdp_url="http://127.0.0.1:9222"))

    assert result.session_id == "cdp1"
    assert result.backend == "cdp"
    assert cdp.options.display_mode is DisplayMode.CDP


@pytest.mark.asyncio
async def test_manager_close_removes_session(tmp_path):
    context = FakeClosable()
    session = BrowserSession("s1", FakePage(), context, None, tmp_path, "direct", "headless")
    manager = BrowserManager(direct_backend=FakeBackend(session), cdp_backend=FakeBackend(session))
    await manager.start(StartOptions.from_values())

    result = await manager.close("s1")

    assert result.ok is True
    assert context.closed is True
    with pytest.raises(SessionNotFound):
        manager.get("s1")


@pytest.mark.asyncio
async def test_manager_close_all_closes_remaining_sessions_after_failure(tmp_path):
    first_error = RuntimeError("first close failed")
    first_context = FakeClosable(close_error=first_error)
    second_context = FakeClosable()
    manager = BrowserManager()
    manager._sessions["s1"] = BrowserSession("s1", FakePage(), first_context, None, tmp_path, "direct", "headless")
    manager._sessions["s2"] = BrowserSession("s2", FakePage(), second_context, None, tmp_path, "direct", "headless")

    with pytest.raises(RuntimeError, match="first close failed") as excinfo:
        await manager.close_all()

    assert excinfo.value is first_error
    assert first_context.close_calls == 1
    assert second_context.close_calls == 1
    assert manager._sessions == {}


@pytest.mark.asyncio
async def test_cdp_session_close_does_not_close_borrowed_context_or_browser(tmp_path):
    existing_page = FakePage()
    existing_context = FakeCdpContext(pages=[existing_page])
    browser = FakeCdpBrowser(contexts=[existing_context])
    playwright = FakePlaywright(FakeChromium(browser=browser))
    backend = CdpBackend(playwright_factory=fake_playwright_factory(playwright))

    session = await backend.start(StartOptions.from_values(backend="cdp", cdp_url="http://127.0.0.1:9222"))
    await session.close()

    assert session.page is existing_page
    assert session.context is existing_context
    assert existing_context.closed is False
    assert browser.closed is False
    assert playwright.stopped is True


@pytest.mark.asyncio
async def test_cdp_start_failure_stops_playwright_and_closes_created_context():
    created_context = FakeCdpContext(fail_new_page=True)
    browser = FakeCdpBrowser(new_context=created_context)
    playwright = FakePlaywright(FakeChromium(browser=browser))
    backend = CdpBackend(playwright_factory=fake_playwright_factory(playwright))

    with pytest.raises(CdpConnectionFailed, match="127.0.0.1:9222"):
        await backend.start(StartOptions.from_values(backend="cdp", cdp_url="http://127.0.0.1:9222"))

    assert created_context.closed is True
    assert playwright.stopped is True


@pytest.mark.asyncio
async def test_cdp_start_failure_preserves_original_exception_when_cleanup_raises():
    created_context = FakeCdpContext(fail_new_page=True)
    created_context.close_error = RuntimeError("context close failed")
    browser = FakeCdpBrowser(new_context=created_context)
    playwright = FakePlaywright(
        FakeChromium(browser=browser),
        stop_error=RuntimeError("playwright stop failed"),
    )
    backend = CdpBackend(playwright_factory=fake_playwright_factory(playwright))

    with pytest.raises(CdpConnectionFailed, match="127.0.0.1:9222") as excinfo:
        await backend.start(StartOptions.from_values(backend="cdp", cdp_url="http://127.0.0.1:9222"))

    assert isinstance(excinfo.value.__cause__, RuntimeError)
    assert str(excinfo.value.__cause__) == "page failed"
    assert created_context.close_calls == 1
    assert playwright.stop_calls == 1


def fake_context_launcher(context):
    async def _launcher(**kwargs):
        return context

    return _launcher


def recording_context_launcher(context, calls):
    async def _launcher(**kwargs):
        calls.append(kwargs)
        return context

    return _launcher


@pytest.mark.asyncio
async def test_direct_start_failure_closes_created_context_and_display_handle():
    display_handle = FakeDisplayHandle()
    display_manager = FakeDisplayManager(display_handle)
    context = FakeDirectContext(fail_new_page=True)
    backend = DirectBackend(
        display_manager=display_manager,
        context_launcher=fake_context_launcher(context),
    )

    with pytest.raises(RuntimeError, match="page failed"):
        await backend.start(StartOptions.from_values(display_mode="virtual"))

    assert display_manager.display_modes == [DisplayMode.VIRTUAL]
    assert context.closed is True
    assert display_handle.closed is True


@pytest.mark.asyncio
async def test_direct_backend_forwards_v2_context_options():
    calls = []
    context = FakeDirectContext()
    backend = DirectBackend(context_launcher=recording_context_launcher(context, calls))

    await backend.start(
        StartOptions.from_values(
            user_agent="AgentBrowser/1.0",
            viewport={"width": 1440, "height": 900},
            color_scheme="dark",
            geoip=True,
            stealth_args=False,
            args=["--disable-dev-shm-usage"],
            extension_paths=["/tmp/ext"],
            humanize=True,
            human_preset="careful",
            human_config={"mouse_speed": 0.5},
            storage_state="state.json",
            extra_http_headers={"X-Agent": "cloak"},
            permissions=["geolocation"],
        )
    )

    assert calls == [
        {
            "headless": True,
            "proxy": None,
            "locale": None,
            "timezone": None,
            "humanize": True,
            "user_agent": "AgentBrowser/1.0",
            "viewport": {"width": 1440, "height": 900},
            "color_scheme": "dark",
            "geoip": True,
            "stealth_args": False,
            "args": ["--disable-dev-shm-usage"],
            "extension_paths": ["/tmp/ext"],
            "human_preset": "careful",
            "human_config": {"mouse_speed": 0.5},
            "storage_state": "state.json",
            "extra_http_headers": {"X-Agent": "cloak"},
            "permissions": ["geolocation"],
        }
    ]


@pytest.mark.asyncio
async def test_direct_backend_passes_none_viewport_when_no_viewport_is_true():
    calls = []
    context = FakeDirectContext()
    backend = DirectBackend(context_launcher=recording_context_launcher(context, calls))

    await backend.start(StartOptions.from_values(no_viewport=True))

    assert calls[0]["viewport"] is None


@pytest.mark.asyncio
async def test_direct_start_failure_preserves_original_exception_when_cleanup_raises():
    display_handle = FakeDisplayHandle(close_error=RuntimeError("display close failed"))
    display_manager = FakeDisplayManager(display_handle)
    context = FakeDirectContext(fail_new_page=True)
    context.close_error = RuntimeError("context close failed")
    backend = DirectBackend(
        display_manager=display_manager,
        context_launcher=fake_context_launcher(context),
    )

    with pytest.raises(RuntimeError, match="page failed") as excinfo:
        await backend.start(StartOptions.from_values(display_mode="virtual"))

    assert str(excinfo.value) == "page failed"
    assert context.close_calls == 1
    assert display_handle.close_calls == 1


@pytest.mark.asyncio
async def test_cdp_connect_failure_stops_playwright_client():
    playwright = FakePlaywright(FakeChromium(connect_error=RuntimeError("connect failed")))
    backend = CdpBackend(playwright_factory=fake_playwright_factory(playwright))

    with pytest.raises(CdpConnectionFailed, match="127.0.0.1:9222"):
        await backend.start(StartOptions.from_values(backend="cdp", cdp_url="http://127.0.0.1:9222"))

    assert playwright.stopped is True
