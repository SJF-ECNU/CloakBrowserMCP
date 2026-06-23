from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .display import VirtualDisplayManager
from .errors import CdpConnectionFailed, ElementNotFound, ScreenshotFailed, SessionNotFound
from .models import BackendMode, OperationResult, ScreenshotResult, SnapshotResult, StartOptions, StartResult


async def _run_cleanup_steps(*steps: tuple[bool, Any]) -> Exception | None:
    first_error = None
    for should_run, closer in steps:
        if not should_run:
            continue
        try:
            await closer()
        except Exception as exc:
            if first_error is None:
                first_error = exc
    return first_error


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
        display_handle: Any | None = None,
        playwright: Any | None = None,
        owns_context: bool = True,
        owns_browser: bool = True,
    ) -> None:
        self.session_id = session_id
        self.page = page
        self.context = context
        self.browser = browser
        self.backend = backend
        self.display_mode = display_mode
        self.display_handle = display_handle
        self.playwright = playwright
        self.owns_context = owns_context
        self.owns_browser = owns_browser
        self.screenshot_dir = Path(
            screenshot_dir
            or os.environ.get("CLOAK_MCP_SCREENSHOT_DIR")
            or Path(tempfile.gettempdir()) / "cloakbrowser-mcp"
        )
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
        cleanup_error = await _run_cleanup_steps(
            (self.owns_context and self.context is not None, self.context.close if self.context is not None else None),
            (self.owns_browser and self.browser is not None, self.browser.close if self.browser is not None else None),
            (self.playwright is not None, self.playwright.stop if self.playwright is not None else None),
            (
                self.display_handle is not None,
                self.display_handle.close if self.display_handle is not None else None,
            ),
        )
        if cleanup_error is not None:
            raise cleanup_error


class DirectBackend:
    def __init__(
        self,
        *,
        display_manager: VirtualDisplayManager | None = None,
        context_launcher: Any | None = None,
        persistent_context_launcher: Any | None = None,
    ) -> None:
        self.display_manager = display_manager or VirtualDisplayManager()
        self.context_launcher = context_launcher
        self.persistent_context_launcher = persistent_context_launcher

    async def start(self, options: StartOptions) -> BrowserSession:
        display_handle = await self.display_manager.ensure(options.display_mode)
        headless = options.resolved_headless()
        context = None
        try:
            context = await self._launch_context(options, headless=headless)
            page = await context.new_page()
        except Exception:
            await _run_cleanup_steps(
                (context is not None, context.close if context is not None else None),
                (display_handle is not None, display_handle.close if display_handle is not None else None),
            )
            raise
        return BrowserSession(
            uuid.uuid4().hex,
            page,
            context,
            None,
            None,
            options.backend.value,
            options.display_mode.value,
            display_handle,
        )

    def _context_kwargs(self, options: StartOptions, *, headless: bool | None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "headless": headless if headless is not None else True,
            "proxy": options.proxy,
            "locale": options.locale,
            "timezone": options.timezone,
            "humanize": options.humanize,
            "geoip": options.geoip,
            "stealth_args": options.stealth_args,
        }
        optional_values = {
            "user_agent": options.user_agent,
            "color_scheme": options.color_scheme,
            "args": options.args,
            "extension_paths": options.extension_paths,
            "human_preset": options.human_preset,
            "human_config": options.human_config,
            "storage_state": options.storage_state,
            "extra_http_headers": options.extra_http_headers,
            "permissions": options.permissions,
        }
        for key, value in optional_values.items():
            if value is not None:
                kwargs[key] = value
        if options.viewport is not None:
            kwargs["viewport"] = options.viewport
        elif options.no_viewport:
            kwargs["viewport"] = None
        return kwargs

    async def _launch_context(self, options: StartOptions, *, headless: bool | None) -> Any:
        if options.profile_dir:
            launcher = self.persistent_context_launcher
            if launcher is None:
                from cloakbrowser import launch_persistent_context_async

                launcher = launch_persistent_context_async
            return await launcher(
                str(options.profile_dir),
                **self._context_kwargs(options, headless=headless),
            )
        launcher = self.context_launcher
        if launcher is None:
            from cloakbrowser import launch_context_async

            launcher = launch_context_async
        return await launcher(**self._context_kwargs(options, headless=headless))


class CdpBackend:
    def __init__(self, *, playwright_factory: Any | None = None) -> None:
        self.playwright_factory = playwright_factory

    async def start(self, options: StartOptions) -> BrowserSession:
        cdp_url = options.resolved_cdp_url()
        playwright = None
        browser = None
        context = None
        owns_context = False
        try:
            playwright = await self._start_playwright()
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            if browser.contexts:
                context = browser.contexts[0]
            else:
                context = await browser.new_context()
                owns_context = True
            page = context.pages[0] if context.pages else await context.new_page()
        except Exception as exc:
            await self._cleanup_failed_start(playwright=playwright, context=context, owns_context=owns_context)
            raise CdpConnectionFailed(f"Failed to connect to CDP endpoint {cdp_url!r}") from exc
        return BrowserSession(
            uuid.uuid4().hex,
            page,
            context,
            browser,
            None,
            "cdp",
            "cdp",
            playwright=playwright,
            owns_context=owns_context,
            owns_browser=False,
        )

    async def _start_playwright(self) -> Any:
        if self.playwright_factory is not None:
            return await self.playwright_factory()
        from playwright.async_api import async_playwright

        return await async_playwright().start()

    async def _cleanup_failed_start(self, *, playwright: Any | None, context: Any | None, owns_context: bool) -> None:
        await _run_cleanup_steps(
            (owns_context and context is not None, context.close if context is not None else None),
            (playwright is not None, playwright.stop if playwright is not None else None),
        )


class BrowserManager:
    def __init__(
        self,
        *,
        direct_backend: Any | None = None,
        cdp_backend: Any | None = None,
    ) -> None:
        self._direct_backend = direct_backend or DirectBackend()
        self._cdp_backend = cdp_backend or CdpBackend()
        self._sessions: dict[str, BrowserSession] = {}

    async def start(self, options: StartOptions) -> StartResult:
        backend = self._cdp_backend if options.backend is BackendMode.CDP else self._direct_backend
        session = await backend.start(options)
        self._sessions[session.session_id] = session
        return StartResult(session_id=session.session_id, backend=session.backend, display_mode=session.display_mode)

    def get(self, session_id: str) -> BrowserSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._sessions)) or "none"
            raise SessionNotFound(f"Unknown session {session_id!r}; available sessions: {available}") from exc

    async def close(self, session_id: str) -> OperationResult:
        session = self.get(session_id)
        try:
            await session.close()
        finally:
            self._sessions.pop(session_id, None)
        return OperationResult(ok=True, session_id=session_id)

    async def close_all(self) -> None:
        first_error = None
        for session_id, session in list(self._sessions.items()):
            try:
                await session.close()
            except Exception as exc:
                if first_error is None:
                    first_error = exc
            finally:
                self._sessions.pop(session_id, None)
        if first_error is not None:
            raise first_error
