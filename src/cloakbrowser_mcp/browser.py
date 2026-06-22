from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .errors import ElementNotFound, ScreenshotFailed
from .models import OperationResult, ScreenshotResult, SnapshotResult


class BrowserSession:
    def __init__(
        self,
        session_id: str,
        page: Any,
        context: Any,
        browser: Any | None,
        screenshot_dir: str | Path | None,
        backend: str,
        display_mode: str,
    ) -> None:
        self.session_id = session_id
        self.page = page
        self.context = context
        self.browser = browser
        self.backend = backend
        self.display_mode = display_mode
        self.screenshot_dir = Path(screenshot_dir or Path(tempfile.gettempdir()) / "cloakbrowser-mcp")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def navigate(self, url: str, wait_until: str = "load") -> dict[str, str]:
        await self.page.goto(url, wait_until=wait_until)
        title = await self.page.title()
        return {"session_id": self.session_id, "url": self.page.url, "title": title}

    async def click(self, selector: str) -> OperationResult:
        try:
            await self.page.click(selector)
        except (TimeoutError, PlaywrightTimeoutError) as exc:
            raise ElementNotFound(f"Element not found for selector {selector!r}") from exc
        return OperationResult(ok=True, session_id=self.session_id)

    async def type_text(self, selector: str, text: str) -> OperationResult:
        try:
            await self.page.fill(selector, text)
        except (TimeoutError, PlaywrightTimeoutError) as exc:
            raise ElementNotFound(f"Element not found for selector {selector!r}") from exc
        return OperationResult(ok=True, session_id=self.session_id)

    async def evaluate(self, script: str) -> Any:
        return await self.page.evaluate(script)

    async def snapshot(self) -> SnapshotResult:
        title = await self.page.title()
        text = await self.page.evaluate("() => document.body.innerText")
        return SnapshotResult(session_id=self.session_id, url=self.page.url, title=title, text=text)

    async def screenshot(self, full_page: bool = False) -> ScreenshotResult:
        path = self.screenshot_dir / f"{self.session_id}-{uuid.uuid4().hex}.png"
        try:
            await self.page.screenshot(path=str(path), full_page=full_page)
        except Exception as exc:
            raise ScreenshotFailed(f"Screenshot failed for session {self.session_id} at {self.page.url}") from exc
        return ScreenshotResult(session_id=self.session_id, path=str(path))

    async def close(self) -> None:
        if self.context is not None:
            await self.context.close()
        if self.browser is not None:
            await self.browser.close()
