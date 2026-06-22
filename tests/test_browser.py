from pathlib import Path

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from cloakbrowser_mcp.browser import BrowserManager, BrowserSession, CdpBackend
from cloakbrowser_mcp.errors import CdpConnectionFailed, ElementNotFound, ScreenshotFailed, SessionNotFound
from cloakbrowser_mcp.models import BackendMode, DisplayMode, StartOptions


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.actions = []
        self.fail_selector = False
        self.selector_timeout_error = TimeoutError
        self.fail_screenshot = False

    async def goto(self, url, wait_until="load"):
        self.actions.append(("goto", url, wait_until))
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

    async def evaluate(self, script):
        self.actions.append(("evaluate", script))
        if script == "() => document.body.innerText":
            return "Example Domain\nText"
        return {"value": 42}

    async def screenshot(self, path, full_page=False):
        if self.fail_screenshot:
            raise RuntimeError("cannot capture")
        Path(path).write_bytes(b"png")
        self.actions.append(("screenshot", path, full_page))


class FakeClosable:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class FakeBackend:
    def __init__(self, session):
        self.session = session
        self.options = None

    async def start(self, options):
        self.options = options
        return self.session


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
    def __init__(self, chromium):
        self.chromium = chromium
        self.stopped = False

    async def stop(self):
        self.stopped = True


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
