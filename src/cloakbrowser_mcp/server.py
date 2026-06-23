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
        user_agent: str | None = None,
        viewport: dict[str, int] | None = None,
        no_viewport: bool = False,
        color_scheme: str | None = None,
        geoip: bool = False,
        stealth_args: bool = True,
        args: list[str] | None = None,
        extension_paths: list[str] | None = None,
        human_preset: str = "default",
        human_config: dict[str, Any] | None = None,
        storage_state: str | dict[str, Any] | None = None,
        extra_http_headers: dict[str, str] | None = None,
        permissions: list[str] | None = None,
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
            user_agent=user_agent,
            viewport=viewport,
            no_viewport=no_viewport,
            color_scheme=color_scheme,
            geoip=geoip,
            stealth_args=stealth_args,
            args=args,
            extension_paths=extension_paths,
            human_preset=human_preset,
            human_config=human_config,
            storage_state=storage_state,
            extra_http_headers=extra_http_headers,
            permissions=permissions,
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

    async def browser_wait_for_selector(
        self,
        session_id: str,
        selector: str,
        state: str = "visible",
        timeout_ms: int | None = None,
    ) -> dict[str, Any]:
        return (
            await self.manager.get(session_id).wait_for_selector(
                selector,
                state=state,
                timeout_ms=timeout_ms,
            )
        ).to_dict()

    async def browser_press(self, session_id: str, selector: str, key: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).press(selector, key)).to_dict()

    async def browser_hover(self, session_id: str, selector: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).hover(selector)).to_dict()

    async def browser_select_option(
        self,
        session_id: str,
        selector: str,
        value: str,
        frame_selector: str | None = None,
    ) -> dict[str, Any]:
        return (
            await self.manager.get(session_id).select_option(
                selector,
                value,
                frame_selector=frame_selector,
            )
        ).to_dict()

    async def browser_get_text(self, session_id: str, selector: str | None = None) -> dict[str, Any]:
        return (await self.manager.get(session_id).get_text(selector=selector)).to_dict()

    async def browser_get_attribute(self, session_id: str, selector: str, name: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).get_attribute(selector, name)).to_dict()

    async def browser_get_links(
        self,
        session_id: str,
        selector: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return (await self.manager.get(session_id).get_links(selector=selector, limit=limit)).to_dict()

    async def browser_scroll(self, session_id: str, delta_x: int = 0, delta_y: int = 0) -> dict[str, Any]:
        return (await self.manager.get(session_id).scroll(delta_x=delta_x, delta_y=delta_y)).to_dict()

    async def browser_reload(self, session_id: str, wait_until: str = "load") -> dict[str, Any]:
        return (await self.manager.get(session_id).reload(wait_until=wait_until)).to_dict()

    async def browser_go_back(self, session_id: str, wait_until: str = "load") -> dict[str, Any]:
        return (await self.manager.get(session_id).go_back(wait_until=wait_until)).to_dict()

    async def browser_go_forward(self, session_id: str, wait_until: str = "load") -> dict[str, Any]:
        return (await self.manager.get(session_id).go_forward(wait_until=wait_until)).to_dict()

    async def browser_get_cookies(self, session_id: str, urls: list[str] | None = None) -> dict[str, Any]:
        return (await self.manager.get(session_id).get_cookies(urls=urls)).to_dict()

    async def browser_set_cookies(self, session_id: str, cookies: list[dict[str, Any]]) -> dict[str, Any]:
        return (await self.manager.get(session_id).set_cookies(cookies)).to_dict()

    async def browser_clear_cookies(self, session_id: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).clear_cookies()).to_dict()

    async def browser_get_storage_state(self, session_id: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).get_storage_state()).to_dict()

    async def browser_save_storage_state(self, session_id: str, path: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).save_storage_state(path)).to_dict()

    async def browser_new_page(
        self,
        session_id: str,
        url: str | None = None,
        switch: bool = True,
    ) -> dict[str, Any]:
        return (await self.manager.get(session_id).new_page(url=url, switch=switch)).to_dict()

    async def browser_list_pages(self, session_id: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).list_pages()).to_dict()

    async def browser_switch_page(self, session_id: str, page_id: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).switch_page(page_id)).to_dict()

    async def browser_close_page(self, session_id: str, page_id: str | None = None) -> dict[str, Any]:
        return (await self.manager.get(session_id).close_page(page_id=page_id)).to_dict()


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
    mcp.tool(description="Wait for an element selector to reach a page state.")(handlers.browser_wait_for_selector)
    mcp.tool(description="Press a keyboard key while targeting an element.")(handlers.browser_press)
    mcp.tool(description="Hover over an element by CSS selector.")(handlers.browser_hover)
    mcp.tool(description="Select an option value in a select element.")(handlers.browser_select_option)
    mcp.tool(
        description="Return visible text from the page or a selector.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )(handlers.browser_get_text)
    mcp.tool(
        description="Return an element attribute value.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )(handlers.browser_get_attribute)
    mcp.tool(
        description="Return links from the page or a selector.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )(handlers.browser_get_links)
    mcp.tool(description="Scroll the active page by pixel deltas.")(handlers.browser_scroll)
    mcp.tool(description="Reload the active page.")(handlers.browser_reload)
    mcp.tool(description="Navigate the active page back in history.")(handlers.browser_go_back)
    mcp.tool(description="Navigate the active page forward in history.")(handlers.browser_go_forward)
    mcp.tool(
        description="Return browser cookies.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )(handlers.browser_get_cookies)
    mcp.tool(description="Set browser cookies.")(handlers.browser_set_cookies)
    mcp.tool(description="Clear browser cookies.")(handlers.browser_clear_cookies)
    mcp.tool(
        description="Return browser storage state.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )(handlers.browser_get_storage_state)
    mcp.tool(description="Save browser storage state to a file.")(handlers.browser_save_storage_state)
    mcp.tool(description="Open a new page in the session.")(handlers.browser_new_page)
    mcp.tool(
        description="List pages in the session.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )(handlers.browser_list_pages)
    mcp.tool(description="Switch the active page by page ID.")(handlers.browser_switch_page)
    mcp.tool(description="Close a page in the session.")(handlers.browser_close_page)
    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
