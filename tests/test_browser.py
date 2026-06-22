from pathlib import Path

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from cloakbrowser_mcp.browser import BrowserSession
from cloakbrowser_mcp.errors import ElementNotFound, ScreenshotFailed


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
