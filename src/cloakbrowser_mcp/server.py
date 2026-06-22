from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .browser import BrowserManager
from .models import StartOptions


class ToolHandlers:
    def __init__(self, manager: BrowserManager) -> None:
        self.manager = manager

    async def browser_start(
        self,
        backend: str | None = None,
        display_mode: str | None = None,
        headless: bool | None = None,
        proxy: str | None = None,
        locale: str | None = None,
        timezone: str | None = None,
        humanize: bool = False,
        profile_dir: str | None = None,
        cdp_url: str | None = None,
        fingerprint: str | None = None,
    ) -> dict[str, Any]:
        options = StartOptions.from_values(
            backend=backend,
            display_mode=display_mode,
            headless=headless,
            proxy=proxy,
            locale=locale,
            timezone=timezone,
            humanize=humanize,
            profile_dir=profile_dir,
            cdp_url=cdp_url,
            fingerprint=fingerprint,
        )
        return (await self.manager.start(options)).to_dict()

    async def browser_navigate(self, session_id: str, url: str, wait_until: str = "load") -> dict[str, Any]:
        return await self.manager.get(session_id).navigate(url, wait_until=wait_until)

    async def browser_click(self, session_id: str, selector: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).click(selector)).to_dict()

    async def browser_type(self, session_id: str, selector: str, text: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).type_text(selector, text)).to_dict()

    async def browser_evaluate(self, session_id: str, script: str) -> Any:
        return await self.manager.get(session_id).evaluate(script)

    async def browser_snapshot(self, session_id: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).snapshot()).to_dict()

    async def browser_screenshot(self, session_id: str, full_page: bool = False) -> dict[str, Any]:
        return (await self.manager.get(session_id).screenshot(full_page=full_page)).to_dict()

    async def browser_close(self, session_id: str) -> dict[str, Any]:
        return (await self.manager.close(session_id)).to_dict()


def _server_lifespan(manager: BrowserManager):
    @asynccontextmanager
    async def _lifespan(_: FastMCP):
        try:
            yield
        finally:
            await manager.close_all()

    return _lifespan


def create_server(manager: BrowserManager | None = None) -> FastMCP:
    manager = manager or BrowserManager()
    handlers = ToolHandlers(manager)
    mcp = FastMCP("CloakBrowser MCP", lifespan=_server_lifespan(manager))

    mcp.tool(description="Start a CloakBrowser session. Default mode is direct headless Linux browsing.")(
        handlers.browser_start
    )
    mcp.tool(description="Navigate the session page to a URL.")(handlers.browser_navigate)
    mcp.tool(description="Click an element by CSS selector.")(handlers.browser_click)
    mcp.tool(description="Type text into an element by CSS selector.")(handlers.browser_type)
    mcp.tool(description="Evaluate JavaScript in the current page.")(handlers.browser_evaluate)
    mcp.tool(
        description="Return page URL, title, and visible text.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )(handlers.browser_snapshot)
    mcp.tool(
        description="Capture a PNG screenshot and return its filesystem path.",
    )(handlers.browser_screenshot)
    mcp.tool(description="Close a browser session and release resources.")(handlers.browser_close)
    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
