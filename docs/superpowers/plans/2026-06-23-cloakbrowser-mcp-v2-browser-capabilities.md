# CloakBrowser MCP v2 Browser Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing CloakBrowser MCP server with v2 browser capabilities: richer CloakBrowser launch options, common page operation tools, cookies/storage state tools, and multi-page session management.

**Architecture:** Keep the existing `ToolHandlers -> BrowserManager -> BrowserSession` shape. Add fields to `StartOptions`, forward them through `DirectBackend`, add thin Playwright wrappers on `BrowserSession`, and register new FastMCP tools in `server.py` without breaking the original eight tools.

**Tech Stack:** Python 3.13 in the project-local `uv` environment, `cloakbrowser>=0.4,<1`, Playwright async API exposed by CloakBrowser, FastMCP from `mcp[cli]`, `pytest`, `pytest-asyncio`.

---

## Global Constraints

- Repository root: `/Users/shjf/Documents/CloakBrowserMCP`.
- Preserve all existing public tools and behavior.
- Use `uv run --no-editable ...` for verification.
- Do not copy upstream CloakBrowser source into this repository.
- Do not implement search-engine strategy, network interception, HAR, trace, or download listeners in this version.
- Keep implementation surgical: extend existing files and fake tests rather than restructuring the package.
- Keep `browser_evaluate` available as the escape hatch for uncommon Playwright behavior.

## File Structure

- Modify `src/cloakbrowser_mcp/models.py`: add v2 start fields and result dataclasses.
- Modify `src/cloakbrowser_mcp/errors.py`: add page-id and storage-state errors.
- Modify `src/cloakbrowser_mcp/browser.py`: forward CloakBrowser launch options, add page wrappers, add context/storage tools, maintain page ids.
- Modify `src/cloakbrowser_mcp/server.py`: add handler methods and register read-only annotations for `browser_snapshot`, `browser_get_text`, `browser_get_attribute`, `browser_get_links`, `browser_get_cookies`, `browser_get_storage_state`, and `browser_list_pages`.
- Modify `tests/test_models.py`: cover new `StartOptions` fields and validation.
- Modify `tests/test_browser.py`: extend fake page/context objects and cover new session behavior.
- Modify `tests/test_server.py`: cover handler forwarding and full tool registration.
- Modify `tests/test_smoke.py`: add opt-in smoke coverage for a small subset of read/page tools.
- Modify `README.md`: document v2 tools and examples.

## Task 1: Start Options And Result Models

**Files:**
- Modify: `src/cloakbrowser_mcp/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for v2 start options**

Append to `tests/test_models.py`:

```python
def test_start_options_preserve_cloakbrowser_launch_options(tmp_path):
    storage_state = tmp_path / "state.json"
    options = StartOptions.from_values(
        user_agent="AgentBrowser/1.0",
        viewport={"width": 1440, "height": 900},
        color_scheme="dark",
        geoip=True,
        stealth_args=False,
        args=["--disable-dev-shm-usage"],
        extension_paths=["/tmp/ext"],
        human_preset="careful",
        human_config={"mouse_speed": 0.5},
        storage_state=str(storage_state),
        extra_http_headers={"X-Agent": "cloak"},
        permissions=["geolocation"],
    )

    assert options.user_agent == "AgentBrowser/1.0"
    assert options.viewport == {"width": 1440, "height": 900}
    assert options.no_viewport is False
    assert options.color_scheme == "dark"
    assert options.geoip is True
    assert options.stealth_args is False
    assert options.args == ["--disable-dev-shm-usage"]
    assert options.extension_paths == ["/tmp/ext"]
    assert options.human_preset == "careful"
    assert options.human_config == {"mouse_speed": 0.5}
    assert options.storage_state == str(storage_state)
    assert options.extra_http_headers == {"X-Agent": "cloak"}
    assert options.permissions == ["geolocation"]


def test_no_viewport_and_viewport_conflict():
    with pytest.raises(ValueError, match="no_viewport"):
        StartOptions.from_values(viewport={"width": 1280, "height": 720}, no_viewport=True)


@pytest.mark.parametrize("color_scheme", ["light", "dark", "no-preference"])
def test_supported_color_schemes(color_scheme):
    assert StartOptions.from_values(color_scheme=color_scheme).color_scheme == color_scheme


def test_unsupported_color_scheme_raises():
    with pytest.raises(ValueError, match="color_scheme"):
        StartOptions.from_values(color_scheme="sepia")


def test_profile_dir_and_storage_state_conflict(tmp_path):
    with pytest.raises(ValueError, match="storage_state"):
        StartOptions.from_values(profile_dir=tmp_path / "profile", storage_state="state.json")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --no-editable pytest tests/test_models.py -q
```

Expected: FAIL because `StartOptions.from_values()` does not accept `user_agent`, `viewport`, `color_scheme`, `geoip`, `stealth_args`, `args`, `extension_paths`, `human_preset`, `human_config`, `storage_state`, `extra_http_headers`, `permissions`, or `no_viewport`.

- [ ] **Step 3: Extend `StartOptions`**

Modify `src/cloakbrowser_mcp/models.py`:

```python
from typing import Any, Literal
```

Update `StartOptions` fields:

```python
ColorScheme = Literal["light", "dark", "no-preference"]


@dataclass(slots=True)
class StartOptions:
    backend: BackendMode = BackendMode.DIRECT
    display_mode: DisplayMode = DisplayMode.HEADLESS
    headless: bool | None = None
    proxy: str | None = None
    locale: str | None = None
    timezone: str | None = None
    humanize: bool = False
    profile_dir: Path | None = None
    cdp_url: str | None = None
    fingerprint: str | None = None
    user_agent: str | None = None
    viewport: dict[str, int] | None = None
    no_viewport: bool = False
    color_scheme: ColorScheme | None = None
    geoip: bool = False
    stealth_args: bool = True
    args: list[str] | None = None
    extension_paths: list[str] | None = None
    human_preset: str = "default"
    human_config: dict[str, Any] | None = None
    storage_state: str | dict[str, Any] | None = None
    extra_http_headers: dict[str, str] | None = None
    permissions: list[str] | None = None
```

Add this helper near `_with_fingerprint`:

```python
def _color_scheme_value(value: str | None) -> ColorScheme | None:
    if value is None:
        return None
    allowed = {"light", "dark", "no-preference"}
    if value not in allowed:
        raise ValueError("Unsupported color_scheme {!r}; expected one of: dark, light, no-preference".format(value))
    return value  # type: ignore[return-value]
```

Extend `StartOptions.from_values(...)` signature with the new keyword-only arguments:

```python
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
```

Before returning `cls(...)`, add:

```python
        if viewport is not None and no_viewport:
            raise ValueError("viewport and no_viewport cannot both be set")
        if profile_dir is not None and storage_state is not None:
            raise ValueError("storage_state cannot be used with profile_dir; reuse profile_dir for persistent state")
```

Add the new fields to the returned `StartOptions`:

```python
            user_agent=user_agent,
            viewport=viewport,
            no_viewport=no_viewport,
            color_scheme=_color_scheme_value(color_scheme),
            geoip=geoip,
            stealth_args=stealth_args,
            args=args,
            extension_paths=extension_paths,
            human_preset=human_preset,
            human_config=human_config,
            storage_state=storage_state,
            extra_http_headers=extra_http_headers,
            permissions=permissions,
```

- [ ] **Step 4: Run model tests**

Run:

```bash
uv run --no-editable pytest tests/test_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/cloakbrowser_mcp/models.py tests/test_models.py
git commit -m "feat: add v2 browser start option models"
```

Expected: commit succeeds.

## Task 2: DirectBackend CloakBrowser Launch Forwarding

**Files:**
- Modify: `src/cloakbrowser_mcp/browser.py`
- Modify: `tests/test_browser.py`

- [ ] **Step 1: Write failing tests for direct launch forwarding**

Append to `tests/test_browser.py`:

```python
def recording_context_launcher(context, calls):
    async def _launcher(**kwargs):
        calls.append(kwargs)
        return context

    return _launcher


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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --no-editable pytest tests/test_browser.py::test_direct_backend_forwards_v2_context_options tests/test_browser.py::test_direct_backend_passes_none_viewport_when_no_viewport_is_true -q
```

Expected: FAIL because `DirectBackend._launch_context()` only forwards the original small option set.

- [ ] **Step 3: Add launch kwargs helpers**

In `src/cloakbrowser_mcp/browser.py`, add helper methods to `DirectBackend`:

```python
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
```

Replace both launcher calls in `_launch_context()`:

```python
            return await launcher(
                str(options.profile_dir),
                **self._context_kwargs(options, headless=headless),
            )
```

and:

```python
        return await launcher(**self._context_kwargs(options, headless=headless))
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
uv run --no-editable pytest tests/test_browser.py::test_direct_backend_forwards_v2_context_options tests/test_browser.py::test_direct_backend_passes_none_viewport_when_no_viewport_is_true -q
```

Expected: PASS.

- [ ] **Step 5: Run existing backend tests**

Run:

```bash
uv run --no-editable pytest tests/test_browser.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add src/cloakbrowser_mcp/browser.py tests/test_browser.py
git commit -m "feat: forward CloakBrowser launch options"
```

Expected: commit succeeds.

## Task 3: Page Operation Tools In BrowserSession

**Files:**
- Modify: `src/cloakbrowser_mcp/models.py`
- Modify: `src/cloakbrowser_mcp/browser.py`
- Modify: `tests/test_browser.py`

- [ ] **Step 1: Add failing fake-page tests**

Extend `FakePage` in `tests/test_browser.py` with methods used by the tests:

```python
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

    async def reload(self, wait_until="load"):
        self.actions.append(("reload", wait_until))

    async def go_back(self, wait_until="load"):
        self.actions.append(("go_back", wait_until))
        return None

    async def go_forward(self, wait_until="load"):
        self.actions.append(("go_forward", wait_until))
        return None
```

Append tests:

```python
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

    assert len(links.links) == 2
    assert links.links[0] == {"text": "One", "href": "https://example.com/one"}
```

Update `FakePage.evaluate()`:

```python
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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --no-editable pytest tests/test_browser.py::test_session_page_operation_methods tests/test_browser.py::test_session_get_text_without_selector_reads_body_text tests/test_browser.py::test_session_get_links_limits_results -q
```

Expected: FAIL because `BrowserSession` does not expose the new methods and model result classes do not exist.

- [ ] **Step 3: Add result dataclasses**

Add to `src/cloakbrowser_mcp/models.py`:

```python
@dataclass(slots=True)
class TextResult:
    session_id: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AttributeResult:
    session_id: str
    value: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SelectResult:
    session_id: str
    values: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LinksResult:
    session_id: str
    links: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PageNavigationResult:
    session_id: str
    url: str
    title: str
    message: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 4: Add `BrowserSession` page methods**

Update imports in `src/cloakbrowser_mcp/browser.py`:

```python
from .models import (
    AttributeResult,
    BackendMode,
    DisplayMode,
    LinksResult,
    OperationResult,
    PageNavigationResult,
    ScreenshotResult,
    SelectResult,
    SnapshotResult,
    StartOptions,
    StartResult,
    TextResult,
)
```

Add methods to `BrowserSession`:

```python
    async def wait_for_selector(self, selector: str, state: str = "visible", timeout_ms: int | None = None) -> OperationResult:
        try:
            await self.page.wait_for_selector(selector, state=state, timeout=timeout_ms)
        except (TimeoutError, PlaywrightTimeoutError) as exc:
            raise ElementNotFound(f"Element not found for selector {selector!r} while waiting for state {state!r}") from exc
        return OperationResult(ok=True, session_id=self.session_id)

    async def press(self, selector: str, key: str) -> OperationResult:
        try:
            await self.page.press(selector, key)
        except (TimeoutError, PlaywrightTimeoutError) as exc:
            raise ElementNotFound(f"Element not found for selector {selector!r} while pressing {key!r}") from exc
        return OperationResult(ok=True, session_id=self.session_id)

    async def hover(self, selector: str) -> OperationResult:
        try:
            await self.page.hover(selector)
        except (TimeoutError, PlaywrightTimeoutError) as exc:
            raise ElementNotFound(f"Element not found for selector {selector!r} while hovering") from exc
        return OperationResult(ok=True, session_id=self.session_id)

    async def select_option(self, selector: str, value: str) -> SelectResult:
        try:
            values = await self.page.select_option(selector, value)
        except (TimeoutError, PlaywrightTimeoutError) as exc:
            raise ElementNotFound(f"Element not found for selector {selector!r} while selecting option") from exc
        return SelectResult(session_id=self.session_id, values=list(values or []))

    async def get_text(self, selector: str | None = None) -> TextResult:
        if selector is None:
            text = await self.page.evaluate("() => document.body.innerText")
        else:
            try:
                text = await self.page.text_content(selector)
            except (TimeoutError, PlaywrightTimeoutError) as exc:
                raise ElementNotFound(f"Element not found for selector {selector!r} while reading text") from exc
        return TextResult(session_id=self.session_id, text=text or "")

    async def get_attribute(self, selector: str, name: str) -> AttributeResult:
        try:
            value = await self.page.get_attribute(selector, name)
        except (TimeoutError, PlaywrightTimeoutError) as exc:
            raise ElementNotFound(f"Element not found for selector {selector!r} while reading attribute {name!r}") from exc
        return AttributeResult(session_id=self.session_id, value=value)

    async def get_links(self, selector: str | None = None, limit: int = 50) -> LinksResult:
        root = selector or "body"
        script = f"""() => Array.from(document.querySelectorAll({root!r} + ' a, ' + ({root!r} === 'body' ? 'a' : '')))
            .filter((el, index, arr) => arr.indexOf(el) === index)
            .slice(0, {limit})
            .map((el) => ({{text: el.innerText || el.textContent || '', href: el.href || ''}}))"""
        links = await self.page.evaluate(script)
        return LinksResult(session_id=self.session_id, links=list(links or []))

    async def scroll(self, delta_x: int = 0, delta_y: int = 0) -> OperationResult:
        await self.page.evaluate(f"() => window.scrollBy({delta_x}, {delta_y})")
        return OperationResult(ok=True, session_id=self.session_id)

    async def reload(self, wait_until: str = "load") -> PageNavigationResult:
        await self.page.reload(wait_until=wait_until)
        return await self._page_navigation_result()

    async def go_back(self, wait_until: str = "load") -> PageNavigationResult:
        response = await self.page.go_back(wait_until=wait_until)
        return await self._page_navigation_result("no history entry" if response is None else "ok")

    async def go_forward(self, wait_until: str = "load") -> PageNavigationResult:
        response = await self.page.go_forward(wait_until=wait_until)
        return await self._page_navigation_result("no history entry" if response is None else "ok")

    async def _page_navigation_result(self, message: str = "ok") -> PageNavigationResult:
        title = await self.page.title()
        return PageNavigationResult(session_id=self.session_id, url=self.page.url, title=title, message=message)
```

- [ ] **Step 5: Run targeted tests**

Run:

```bash
uv run --no-editable pytest tests/test_browser.py::test_session_page_operation_methods tests/test_browser.py::test_session_get_text_without_selector_reads_body_text tests/test_browser.py::test_session_get_links_limits_results -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add src/cloakbrowser_mcp/models.py src/cloakbrowser_mcp/browser.py tests/test_browser.py
git commit -m "feat: add page operation session methods"
```

Expected: commit succeeds.

## Task 4: Cookies, Storage State, And Page IDs

**Files:**
- Modify: `src/cloakbrowser_mcp/models.py`
- Modify: `src/cloakbrowser_mcp/errors.py`
- Modify: `src/cloakbrowser_mcp/browser.py`
- Modify: `tests/test_browser.py`

- [ ] **Step 1: Extend fake context for state tests**

Update `FakeDirectContext` in `tests/test_browser.py`:

```python
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
```

Add `close()` to `FakePage`:

```python
    async def close(self):
        self.actions.append(("close",))
```

- [ ] **Step 2: Write failing state and page-id tests**

Append to `tests/test_browser.py`:

```python
@pytest.mark.asyncio
async def test_session_context_state_methods(tmp_path):
    context = FakeDirectContext()
    page = await context.new_page()
    session = BrowserSession("s1", page, context, None, tmp_path, "direct", "headless")

    assert (await session.get_cookies()).cookies == context.cookies_value
    assert (await session.set_cookies([{"name": "token", "value": "abc", "domain": "example.com", "path": "/"}])).ok is True
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
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run --no-editable pytest tests/test_browser.py::test_session_context_state_methods tests/test_browser.py::test_session_page_management -q
```

Expected: FAIL because context state result classes and page-id session methods do not exist.

- [ ] **Step 4: Add errors and result dataclasses**

Add to `src/cloakbrowser_mcp/errors.py`:

```python
class PageNotFound(BrowserMcpError):
    code = "PageNotFound"


class StorageStateFailed(BrowserMcpError):
    code = "StorageStateFailed"
```

Add to `src/cloakbrowser_mcp/models.py`:

```python
@dataclass(slots=True)
class CookiesResult:
    session_id: str
    cookies: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StorageStateResult:
    session_id: str
    state: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StorageStateFileResult:
    session_id: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PageInfoResult:
    session_id: str
    page_id: str
    url: str
    title: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PagesResult:
    session_id: str
    pages: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 5: Add page registry to `BrowserSession`**

In `BrowserSession.__init__`, after screenshot directory creation:

```python
        self._pages: dict[str, Any] = {}
        self._active_page_id = self._register_page(page)
```

Add helpers and context methods:

```python
    def _register_page(self, page: Any) -> str:
        for page_id, known_page in self._pages.items():
            if known_page is page:
                return page_id
        page_id = uuid.uuid4().hex
        self._pages[page_id] = page
        return page_id

    def _get_page(self, page_id: str) -> Any:
        try:
            return self._pages[page_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._pages)) or "none"
            raise PageNotFound(f"Unknown page {page_id!r}; available pages: {available}") from exc

    async def _page_info(self, page_id: str, page: Any) -> dict[str, Any]:
        return {
            "page_id": page_id,
            "url": page.url,
            "title": await page.title(),
            "is_active": page is self.page,
        }

    async def get_cookies(self, urls: list[str] | None = None) -> CookiesResult:
        cookies = await self.context.cookies(urls)
        return CookiesResult(session_id=self.session_id, cookies=list(cookies or []))

    async def set_cookies(self, cookies: list[dict[str, Any]]) -> OperationResult:
        await self.context.add_cookies(cookies)
        return OperationResult(ok=True, session_id=self.session_id)

    async def clear_cookies(self) -> OperationResult:
        await self.context.clear_cookies()
        return OperationResult(ok=True, session_id=self.session_id)

    async def get_storage_state(self) -> StorageStateResult:
        state = await self.context.storage_state()
        return StorageStateResult(session_id=self.session_id, state=state)

    async def save_storage_state(self, path: str | Path) -> StorageStateFileResult:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            await self.context.storage_state(path=str(output))
        except Exception as exc:
            raise StorageStateFailed(f"Failed to write storage state to {output}") from exc
        return StorageStateFileResult(session_id=self.session_id, path=str(output))

    async def new_page(self, url: str | None = None, switch: bool = True) -> PageInfoResult:
        page = await self.context.new_page()
        page_id = self._register_page(page)
        if url is not None:
            await page.goto(url, wait_until="load")
        if switch:
            self.page = page
            self._active_page_id = page_id
        return PageInfoResult(session_id=self.session_id, page_id=page_id, url=page.url, title=await page.title())

    async def list_pages(self) -> PagesResult:
        return PagesResult(
            session_id=self.session_id,
            pages=[await self._page_info(page_id, page) for page_id, page in self._pages.items()],
        )

    async def switch_page(self, page_id: str) -> PageInfoResult:
        page = self._get_page(page_id)
        self.page = page
        self._active_page_id = page_id
        return PageInfoResult(session_id=self.session_id, page_id=page_id, url=page.url, title=await page.title())

    async def close_page(self, page_id: str | None = None) -> OperationResult:
        target_page_id = page_id or self._active_page_id
        page = self._get_page(target_page_id)
        await page.close()
        self._pages.pop(target_page_id, None)
        if not self._pages:
            new_page = await self.context.new_page()
            new_page_id = self._register_page(new_page)
            self.page = new_page
            self._active_page_id = new_page_id
        elif page is self.page:
            self._active_page_id, self.page = next(iter(self._pages.items()))
        return OperationResult(ok=True, session_id=self.session_id)
```

Update imports in `browser.py` for the new result classes and errors.

- [ ] **Step 6: Run targeted tests**

Run:

```bash
uv run --no-editable pytest tests/test_browser.py::test_session_context_state_methods tests/test_browser.py::test_session_page_management -q
```

Expected: PASS.

- [ ] **Step 7: Run all browser tests**

Run:

```bash
uv run --no-editable pytest tests/test_browser.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add src/cloakbrowser_mcp/models.py src/cloakbrowser_mcp/errors.py src/cloakbrowser_mcp/browser.py tests/test_browser.py
git commit -m "feat: add browser context and page state tools"
```

Expected: commit succeeds.

## Task 5: FastMCP Tool Registration

**Files:**
- Modify: `src/cloakbrowser_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Extend fake session**

Add methods to `FakeSession` in `tests/test_server.py`:

```python
    async def wait_for_selector(self, selector, state="visible", timeout_ms=None):
        return OperationResult(ok=True, session_id="s1", message=f"waited {selector}")

    async def press(self, selector, key):
        return OperationResult(ok=True, session_id="s1", message=f"pressed {key}")

    async def hover(self, selector):
        return OperationResult(ok=True, session_id="s1", message=f"hovered {selector}")

    async def select_option(self, selector, value):
        from cloakbrowser_mcp.models import SelectResult

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

        return PageNavigationResult(session_id="s1", url="https://example.com", title="Example", message="no history entry")

    async def go_forward(self, wait_until="load"):
        from cloakbrowser_mcp.models import PageNavigationResult

        return PageNavigationResult(session_id="s1", url="https://example.com", title="Example", message="no history entry")

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

        return PagesResult(session_id="s1", pages=[{"page_id": "p1", "url": "about:blank", "title": "Example", "is_active": True}])

    async def switch_page(self, page_id):
        from cloakbrowser_mcp.models import PageInfoResult

        return PageInfoResult(session_id="s1", page_id=page_id, url="about:blank", title="Example")

    async def close_page(self, page_id=None):
        return OperationResult(ok=True, session_id="s1")
```

- [ ] **Step 2: Write failing server tests**

Update expected tool list in `test_create_server_registers_only_approved_tools()`:

```python
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
```

Add handler forwarding test:

```python
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
```

Update read-only annotation test:

```python
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
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run --no-editable pytest tests/test_server.py -q
```

Expected: FAIL because handler methods and tool registrations do not exist.

- [ ] **Step 4: Add handler methods and start parameters**

In `src/cloakbrowser_mcp/server.py`, extend `browser_start(...)` signature with the Task 1 fields and pass them to `StartOptions.from_values(...)`.

Add these `ToolHandlers` methods:

```python
    async def browser_wait_for_selector(self, session_id: str, selector: str, state: str = "visible", timeout_ms: int | None = None) -> dict[str, Any]:
        return (await self.manager.get(session_id).wait_for_selector(selector, state=state, timeout_ms=timeout_ms)).to_dict()

    async def browser_press(self, session_id: str, selector: str, key: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).press(selector, key)).to_dict()

    async def browser_hover(self, session_id: str, selector: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).hover(selector)).to_dict()

    async def browser_select_option(self, session_id: str, selector: str, value: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).select_option(selector, value)).to_dict()

    async def browser_get_text(self, session_id: str, selector: str | None = None) -> dict[str, Any]:
        return (await self.manager.get(session_id).get_text(selector)).to_dict()

    async def browser_get_attribute(self, session_id: str, selector: str, name: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).get_attribute(selector, name)).to_dict()

    async def browser_get_links(self, session_id: str, selector: str | None = None, limit: int = 50) -> dict[str, Any]:
        return (await self.manager.get(session_id).get_links(selector, limit=limit)).to_dict()

    async def browser_scroll(self, session_id: str, delta_x: int = 0, delta_y: int = 0) -> dict[str, Any]:
        return (await self.manager.get(session_id).scroll(delta_x=delta_x, delta_y=delta_y)).to_dict()

    async def browser_reload(self, session_id: str, wait_until: str = "load") -> dict[str, Any]:
        return (await self.manager.get(session_id).reload(wait_until=wait_until)).to_dict()

    async def browser_go_back(self, session_id: str, wait_until: str = "load") -> dict[str, Any]:
        return (await self.manager.get(session_id).go_back(wait_until=wait_until)).to_dict()

    async def browser_go_forward(self, session_id: str, wait_until: str = "load") -> dict[str, Any]:
        return (await self.manager.get(session_id).go_forward(wait_until=wait_until)).to_dict()

    async def browser_get_cookies(self, session_id: str, urls: list[str] | None = None) -> dict[str, Any]:
        return (await self.manager.get(session_id).get_cookies(urls)).to_dict()

    async def browser_set_cookies(self, session_id: str, cookies: list[dict[str, Any]]) -> dict[str, Any]:
        return (await self.manager.get(session_id).set_cookies(cookies)).to_dict()

    async def browser_clear_cookies(self, session_id: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).clear_cookies()).to_dict()

    async def browser_get_storage_state(self, session_id: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).get_storage_state()).to_dict()

    async def browser_save_storage_state(self, session_id: str, path: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).save_storage_state(path)).to_dict()

    async def browser_new_page(self, session_id: str, url: str | None = None, switch: bool = True) -> dict[str, Any]:
        return (await self.manager.get(session_id).new_page(url=url, switch=switch)).to_dict()

    async def browser_list_pages(self, session_id: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).list_pages()).to_dict()

    async def browser_switch_page(self, session_id: str, page_id: str) -> dict[str, Any]:
        return (await self.manager.get(session_id).switch_page(page_id)).to_dict()

    async def browser_close_page(self, session_id: str, page_id: str | None = None) -> dict[str, Any]:
        return (await self.manager.get(session_id).close_page(page_id)).to_dict()
```

- [ ] **Step 5: Register tools**

In `create_server()`, register the new methods after the original eight tools. Use `ToolAnnotations(readOnlyHint=True)` only for read tools:

```python
    mcp.tool(description="Wait for an element by CSS selector.")(handlers.browser_wait_for_selector)
    mcp.tool(description="Press a keyboard key on an element by CSS selector.")(handlers.browser_press)
    mcp.tool(description="Hover an element by CSS selector.")(handlers.browser_hover)
    mcp.tool(description="Select an option in a select element by CSS selector.")(handlers.browser_select_option)
    mcp.tool(description="Return text for an element or the whole page.", annotations=ToolAnnotations(readOnlyHint=True))(handlers.browser_get_text)
    mcp.tool(description="Return an element attribute value.", annotations=ToolAnnotations(readOnlyHint=True))(handlers.browser_get_attribute)
    mcp.tool(description="Return page links.", annotations=ToolAnnotations(readOnlyHint=True))(handlers.browser_get_links)
    mcp.tool(description="Scroll the current page.")(handlers.browser_scroll)
    mcp.tool(description="Reload the current page.")(handlers.browser_reload)
    mcp.tool(description="Go back in page history.")(handlers.browser_go_back)
    mcp.tool(description="Go forward in page history.")(handlers.browser_go_forward)
    mcp.tool(description="Return browser context cookies.", annotations=ToolAnnotations(readOnlyHint=True))(handlers.browser_get_cookies)
    mcp.tool(description="Set browser context cookies.")(handlers.browser_set_cookies)
    mcp.tool(description="Clear browser context cookies.")(handlers.browser_clear_cookies)
    mcp.tool(description="Return browser context storage state.", annotations=ToolAnnotations(readOnlyHint=True))(handlers.browser_get_storage_state)
    mcp.tool(description="Save browser context storage state to a file.")(handlers.browser_save_storage_state)
    mcp.tool(description="Open a new page in the browser context.")(handlers.browser_new_page)
    mcp.tool(description="List pages in the browser session.", annotations=ToolAnnotations(readOnlyHint=True))(handlers.browser_list_pages)
    mcp.tool(description="Switch the active page in the browser session.")(handlers.browser_switch_page)
    mcp.tool(description="Close a page in the browser session.")(handlers.browser_close_page)
```

- [ ] **Step 6: Run server tests**

Run:

```bash
uv run --no-editable pytest tests/test_server.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
git add src/cloakbrowser_mcp/server.py tests/test_server.py
git commit -m "feat: register v2 browser MCP tools"
```

Expected: commit succeeds.

## Task 6: README And Tool Schema Verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_smoke.py`

- [ ] **Step 1: Add README v2 section**

Update `README.md` `## Tools` section to list all tools grouped by category:

```markdown
## Tools

Session:

- `browser_start`
- `browser_close`

Page basics:

- `browser_navigate`
- `browser_click`
- `browser_type`
- `browser_evaluate`
- `browser_snapshot`
- `browser_screenshot`

Page operations:

- `browser_wait_for_selector`
- `browser_press`
- `browser_hover`
- `browser_select_option`
- `browser_get_text`
- `browser_get_attribute`
- `browser_get_links`
- `browser_scroll`
- `browser_reload`
- `browser_go_back`
- `browser_go_forward`

Context and pages:

- `browser_get_cookies`
- `browser_set_cookies`
- `browser_clear_cookies`
- `browser_get_storage_state`
- `browser_save_storage_state`
- `browser_new_page`
- `browser_list_pages`
- `browser_switch_page`
- `browser_close_page`
```

Add launch example:

Add this Markdown snippet to `README.md`:

~~~markdown
## Rich Launch Options

```json
{
  "display_mode": "headless",
  "user_agent": "AgentBrowser/1.0",
  "viewport": {"width": 1440, "height": 900},
  "color_scheme": "dark",
  "geoip": false,
  "humanize": true,
  "human_preset": "careful",
  "storage_state": "/tmp/cloak-state.json"
}
```
~~~

- [ ] **Step 2: Add optional smoke assertions**

In `tests/test_smoke.py`, in the real headless smoke path, after navigation, add:

```python
    text = await session.get_text()
    assert "Example Domain" in text.text

    links = await session.get_links(limit=5)
    assert isinstance(links.links, list)
```

If `tests/test_smoke.py` currently uses handlers instead of `BrowserSession`, call the matching handler methods and assert dict keys:

```python
    text = await handlers.browser_get_text(session_id)
    assert "Example Domain" in text["text"]

    links = await handlers.browser_get_links(session_id, limit=5)
    assert isinstance(links["links"], list)
```

- [ ] **Step 3: Verify tool list from FastMCP**

Run:

```bash
uv run --no-editable python - <<'PY'
import asyncio
from cloakbrowser_mcp.server import create_server

async def main():
    server = create_server()
    tools = await server.list_tools()
    for tool in tools:
        print(tool.name)
    print("count", len(tools))

asyncio.run(main())
PY
```

Expected output includes `browser_get_storage_state`, `browser_list_pages`, and ends with:

```text
count 28
```

- [ ] **Step 4: Run full tests**

Run:

```bash
uv run --no-editable pytest -q
```

Expected: PASS, with existing smoke skips unless real-browser environment variables are set.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add README.md tests/test_smoke.py
git commit -m "docs: document v2 browser MCP tools"
```

Expected: commit succeeds.

## Task 7: Final Package Verification And Claude Code Reload Notes

**Files:**
- No source file changes expected.

- [ ] **Step 1: Reinstall package into uv environment**

Run:

```bash
uv sync --extra dev --no-editable --reinstall-package cloakbrowser-mcp
```

Expected: command exits 0.

- [ ] **Step 2: Verify console script starts far enough to expose stdio**

Run:

```bash
timeout 3 uv run --no-editable cloakbrowser-mcp
```

Expected: process starts and exits by timeout with status 124. No Python import traceback should appear.

- [ ] **Step 3: Verify full test suite again**

Run:

```bash
uv run --no-editable pytest -q
```

Expected: PASS.

- [ ] **Step 4: Inspect git history and status**

Run:

```bash
git status --short --branch
git log --oneline --decorate -8
```

Expected: working tree clean except the active branch marker; log shows task commits on `codex/cloakbrowser-mcp-v2-browser-capabilities`.

- [ ] **Step 5: Note Claude Code reload requirement**

Record in the final implementation summary:

```text
Claude Code may need an MCP reconnect or restart to refresh the tool schema because the globally registered command points at this project but the client caches tool metadata per MCP connection.
```

Do not edit Claude Code config in this task unless the user asks for it.

## Self-Review

- Spec coverage: Task 1 covers richer launch fields, Task 2 covers CloakBrowser forwarding, Task 3 covers page operations, Task 4 covers cookies/storage/multi-page state, Task 5 covers MCP registration, Task 6 covers docs and schema checks, Task 7 covers final verification.
- Placeholder scan: no deferred implementation markers remain in this plan.
- Type consistency: `browser_get_storage_state` is read-only and returns JSON state; `browser_save_storage_state` writes to a path and is not read-only. `no_viewport=True` maps to `viewport=None` only in DirectBackend.
