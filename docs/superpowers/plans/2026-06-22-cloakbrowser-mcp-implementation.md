# CloakBrowser MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python MCP server that lets agents use CloakBrowser in Linux headless, Linux virtual-display, and existing-CDP environments.

**Architecture:** The server uses the official MCP Python SDK v1 FastMCP API, with a small browser core underneath it. `BrowserManager` owns sessions, `BrowserSession` owns page operations, `DirectBackend` launches CloakBrowser directly, and `CdpBackend` connects to an existing `cloakserve` or CDP endpoint.

**Tech Stack:** Python 3.11+ managed by `uv` in the project-local `.venv`, `mcp[cli]>=1.28,<2`, `cloakbrowser>=0.4,<1`, Playwright async API via CloakBrowser, `pyvirtualdisplay>=3,<4`, `pytest`, `pytest-asyncio`.

## Global Constraints

- The repository root is `/Users/shjf/Documents/CloakBrowserMCP`.
- Do not copy CloakBrowser upstream source into this repository.
- Default display mode is `headless`; it must not require `$DISPLAY`.
- `virtual` mode runs headed browser behavior through Xvfb or an existing `$DISPLAY`.
- `cdp` mode connects to an existing CDP endpoint; it does not own long-running `cloakserve` lifecycle in the first version.
- Use TDD: write the failing test, run it, then implement the minimal code.
- Use `uv` for the isolated Python environment. Do not install dependencies with plain `pip`; use `uv sync --extra dev` and run commands through `uv run`.
- Keep the public MCP tool surface to the eight tools in the approved spec.
- Return file paths for screenshots by default, not large base64 payloads.

---

## File Structure

- Create `pyproject.toml`: package metadata, dependencies, pytest config, console script.
- Generate `uv.lock`: project-local locked dependency graph from `uv sync --extra dev`.
- Create `src/cloakbrowser_mcp/__init__.py`: package version export.
- Create `src/cloakbrowser_mcp/models.py`: enums, options, result dataclasses, typed MCP outputs.
- Create `src/cloakbrowser_mcp/errors.py`: actionable exception classes and conversion helper.
- Create `src/cloakbrowser_mcp/display.py`: virtual display manager.
- Create `src/cloakbrowser_mcp/browser.py`: session object, direct/CDP backends, manager.
- Create `src/cloakbrowser_mcp/server.py`: FastMCP instance and tool functions.
- Create `tests/test_models.py`: option normalization and URL construction.
- Create `tests/test_display.py`: virtual display behavior without a real Xvfb process.
- Create `tests/test_browser.py`: fake Playwright session/backend behavior.
- Create `tests/test_server.py`: MCP tool wrapper behavior with a fake manager.
- Create `tests/test_smoke.py`: opt-in real browser smoke tests.
- Create `README.md`: install, Linux modes, MCP configuration, smoke commands.

## Task 1: Project Scaffold And Option Models

**Files:**
- Create: `pyproject.toml`
- Generate: `uv.lock`
- Create: `src/cloakbrowser_mcp/__init__.py`
- Create: `src/cloakbrowser_mcp/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces: `BackendMode`, `DisplayMode`, `StartOptions`, `StartResult`, `OperationResult`, `SnapshotResult`, `ScreenshotResult`.
- Produces: `StartOptions.from_values(...) -> StartOptions`.
- Produces: `StartOptions.resolved_headless() -> bool | None`.
- Produces: `StartOptions.resolved_cdp_url() -> str | None`.

- [ ] **Step 0: Add uv project scaffold**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cloakbrowser-mcp"
version = "0.1.0"
description = "MCP server for controlling CloakBrowser in headless and virtual-display Linux environments."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "cloakbrowser>=0.4,<1",
    "mcp[cli]>=1.28,<2",
    "pyvirtualdisplay>=3,<4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8,<9",
    "pytest-asyncio>=0.23,<2",
]

[project.scripts]
cloakbrowser-mcp = "cloakbrowser_mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/cloakbrowser_mcp"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "smoke: real browser smoke tests",
]
```

- [ ] **Step 0b: Create the isolated uv environment**

Run:

```bash
uv sync --extra dev
```

Expected: `uv.lock` and project-local `.venv/` are created.

- [ ] **Step 1: Write the failing model tests**

Create `tests/test_models.py`:

```python
import os

import pytest

from cloakbrowser_mcp.models import BackendMode, DisplayMode, StartOptions


def test_default_start_options_are_direct_headless():
    options = StartOptions.from_values()

    assert options.backend is BackendMode.DIRECT
    assert options.display_mode is DisplayMode.HEADLESS
    assert options.resolved_headless() is True


def test_virtual_mode_uses_direct_backend_and_headed_browser():
    options = StartOptions.from_values(display_mode="virtual")

    assert options.backend is BackendMode.DIRECT
    assert options.display_mode is DisplayMode.VIRTUAL
    assert options.resolved_headless() is False


def test_cdp_display_mode_selects_cdp_backend():
    options = StartOptions.from_values(display_mode="cdp", cdp_url="http://127.0.0.1:9222")

    assert options.backend is BackendMode.CDP
    assert options.display_mode is DisplayMode.CDP
    assert options.resolved_headless() is None


def test_cdp_backend_uses_env_default_url(monkeypatch):
    monkeypatch.setenv("CLOAK_MCP_DEFAULT_CDP_URL", "http://127.0.0.1:9222")

    options = StartOptions.from_values(backend="cdp", fingerprint="seed1")

    assert options.resolved_cdp_url() == "http://127.0.0.1:9222?fingerprint=seed1"


def test_fingerprint_appends_to_existing_query():
    options = StartOptions.from_values(
        backend="cdp",
        cdp_url="http://127.0.0.1:9222?timezone=Asia/Shanghai",
        fingerprint="seed1",
    )

    assert options.resolved_cdp_url() == "http://127.0.0.1:9222?timezone=Asia%2FShanghai&fingerprint=seed1"


def test_cdp_backend_requires_url_or_env(monkeypatch):
    monkeypatch.delenv("CLOAK_MCP_DEFAULT_CDP_URL", raising=False)

    with pytest.raises(ValueError, match="cdp_url"):
        StartOptions.from_values(backend="cdp")


def test_headless_argument_cannot_override_virtual_mode():
    options = StartOptions.from_values(display_mode="virtual", headless=True)

    assert options.resolved_headless() is False
```

- [ ] **Step 2: Run the model tests and verify they fail**

Run:

```bash
uv run pytest tests/test_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cloakbrowser_mcp'`.

- [ ] **Step 3: Add package and option models**

Create `src/cloakbrowser_mcp/__init__.py`:

```python
"""CloakBrowser MCP server package."""

__version__ = "0.1.0"
```

Create `src/cloakbrowser_mcp/models.py`:

```python
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class BackendMode(str, Enum):
    DIRECT = "direct"
    CDP = "cdp"


class DisplayMode(str, Enum):
    HEADLESS = "headless"
    VIRTUAL = "virtual"
    CDP = "cdp"


def _enum_value(enum_type: type[Enum], value: str | Enum | None, default: Enum) -> Enum:
    if value is None:
        return default
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"Unsupported value {value!r}; expected one of: {allowed}") from exc


def _with_fingerprint(url: str, fingerprint: str | None) -> str:
    if not fingerprint:
        return url
    parts = urlsplit(url)
    query_items = parse_qsl(parts.query, keep_blank_values=False)
    query_items = [(key, value) for key, value in query_items if key != "fingerprint"]
    query_items.append(("fingerprint", fingerprint))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))


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

    @classmethod
    def from_values(
        cls,
        *,
        backend: str | BackendMode | None = None,
        display_mode: str | DisplayMode | None = None,
        headless: bool | None = None,
        proxy: str | None = None,
        locale: str | None = None,
        timezone: str | None = None,
        humanize: bool = False,
        profile_dir: str | Path | None = None,
        cdp_url: str | None = None,
        fingerprint: str | None = None,
    ) -> "StartOptions":
        default_display = DisplayMode(os.environ.get("CLOAK_MCP_DEFAULT_DISPLAY_MODE", DisplayMode.HEADLESS.value))
        resolved_display = _enum_value(DisplayMode, display_mode, default_display)
        default_backend = BackendMode.CDP if resolved_display is DisplayMode.CDP else BackendMode.DIRECT
        resolved_backend = _enum_value(BackendMode, backend, default_backend)
        if resolved_backend is BackendMode.CDP:
            resolved_display = DisplayMode.CDP
            cdp_url = cdp_url or os.environ.get("CLOAK_MCP_DEFAULT_CDP_URL")
            if not cdp_url:
                raise ValueError("cdp_url is required when backend='cdp'")
        return cls(
            backend=resolved_backend,
            display_mode=resolved_display,
            headless=headless,
            proxy=proxy,
            locale=locale,
            timezone=timezone,
            humanize=humanize,
            profile_dir=Path(profile_dir) if profile_dir else None,
            cdp_url=cdp_url,
            fingerprint=fingerprint,
        )

    def resolved_headless(self) -> bool | None:
        if self.backend is BackendMode.CDP or self.display_mode is DisplayMode.CDP:
            return None
        if self.display_mode is DisplayMode.VIRTUAL:
            return False
        return True

    def resolved_cdp_url(self) -> str | None:
        if self.backend is not BackendMode.CDP:
            return None
        if not self.cdp_url:
            raise ValueError("cdp_url is required when backend='cdp'")
        return _with_fingerprint(self.cdp_url, self.fingerprint)


@dataclass(slots=True)
class StartResult:
    session_id: str
    backend: str
    display_mode: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OperationResult:
    ok: bool
    session_id: str
    message: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SnapshotResult:
    session_id: str
    url: str
    title: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScreenshotResult:
    session_id: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 4: Run the model tests and verify they pass**

Run:

```bash
uv run pytest tests/test_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add pyproject.toml uv.lock src/cloakbrowser_mcp/__init__.py src/cloakbrowser_mcp/models.py tests/test_models.py
git commit -m "feat: add mcp option models"
```

## Task 2: Errors, BrowserSession, And Fake Page Operations

**Files:**
- Create: `src/cloakbrowser_mcp/errors.py`
- Create: `src/cloakbrowser_mcp/browser.py`
- Create: `tests/test_browser.py`

**Interfaces:**
- Produces: `BrowserMcpError`, `SessionNotFound`, `VirtualDisplayUnavailable`, `CdpConnectionFailed`, `ElementNotFound`, `ActionTimeout`, `ScreenshotFailed`.
- Produces: `BrowserSession.navigate(url, wait_until) -> dict`.
- Produces: `BrowserSession.click(selector) -> OperationResult`.
- Produces: `BrowserSession.type_text(selector, text) -> OperationResult`.
- Produces: `BrowserSession.evaluate(script) -> Any`.
- Produces: `BrowserSession.snapshot() -> SnapshotResult`.
- Produces: `BrowserSession.screenshot(full_page=False) -> ScreenshotResult`.
- Produces: `BrowserSession.close() -> None`.

- [ ] **Step 1: Write failing fake browser session tests**

Create `tests/test_browser.py`:

```python
from pathlib import Path

import pytest

from cloakbrowser_mcp.browser import BrowserSession
from cloakbrowser_mcp.errors import ElementNotFound, ScreenshotFailed


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.actions = []
        self.fail_selector = False
        self.fail_screenshot = False

    async def goto(self, url, wait_until="load"):
        self.actions.append(("goto", url, wait_until))
        self.url = url

    async def title(self):
        return "Example Domain"

    async def click(self, selector):
        if self.fail_selector:
            raise TimeoutError("selector timeout")
        self.actions.append(("click", selector))

    async def fill(self, selector, text):
        if self.fail_selector:
            raise TimeoutError("selector timeout")
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
async def test_session_type_uses_fill(tmp_path):
    page = FakePage()
    session = BrowserSession("s1", page, FakeClosable(), None, tmp_path, "direct", "headless")

    result = await session.type_text("#q", "hello")

    assert result.to_dict()["ok"] is True
    assert ("fill", "#q", "hello") in page.actions


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
```

- [ ] **Step 2: Run the browser tests and verify they fail**

Run:

```bash
uv run pytest tests/test_browser.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `cloakbrowser_mcp.browser` or missing `BrowserSession`.

- [ ] **Step 3: Add errors and BrowserSession**

Create `src/cloakbrowser_mcp/errors.py`:

```python
from __future__ import annotations


class BrowserMcpError(Exception):
    code = "BrowserMcpError"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class SessionNotFound(BrowserMcpError):
    code = "SessionNotFound"


class VirtualDisplayUnavailable(BrowserMcpError):
    code = "VirtualDisplayUnavailable"


class CdpConnectionFailed(BrowserMcpError):
    code = "CdpConnectionFailed"


class ElementNotFound(BrowserMcpError):
    code = "ElementNotFound"


class ActionTimeout(BrowserMcpError):
    code = "ActionTimeout"


class ScreenshotFailed(BrowserMcpError):
    code = "ScreenshotFailed"
```

Create `src/cloakbrowser_mcp/browser.py`:

```python
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

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
        except TimeoutError as exc:
            raise ElementNotFound(f"Element not found for selector {selector!r}") from exc
        return OperationResult(ok=True, session_id=self.session_id)

    async def type_text(self, selector: str, text: str) -> OperationResult:
        try:
            await self.page.fill(selector, text)
        except TimeoutError as exc:
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
```

- [ ] **Step 4: Run Task 2 tests and existing tests**

Run:

```bash
uv run pytest tests/test_models.py tests/test_browser.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/cloakbrowser_mcp/errors.py src/cloakbrowser_mcp/browser.py tests/test_browser.py
git commit -m "feat: add browser session operations"
```

## Task 3: Backends, Virtual Display, And BrowserManager

**Files:**
- Create: `src/cloakbrowser_mcp/display.py`
- Modify: `src/cloakbrowser_mcp/browser.py`
- Create: `tests/test_display.py`
- Modify: `tests/test_browser.py`

**Interfaces:**
- Produces: `VirtualDisplayManager.ensure(display_mode: DisplayMode) -> VirtualDisplayHandle | None`.
- Produces: `DirectBackend.start(options: StartOptions) -> BrowserSession`.
- Produces: `CdpBackend.start(options: StartOptions) -> BrowserSession`.
- Produces: `BrowserManager.start(options: StartOptions) -> StartResult`.
- Produces: `BrowserManager.get(session_id) -> BrowserSession`.
- Produces: `BrowserManager.close(session_id) -> OperationResult`.
- Produces: `BrowserManager.close_all() -> None`.

- [ ] **Step 1: Write failing display and manager tests**

Create `tests/test_display.py`:

```python
import os

import pytest

from cloakbrowser_mcp.display import VirtualDisplayManager
from cloakbrowser_mcp.errors import VirtualDisplayUnavailable
from cloakbrowser_mcp.models import DisplayMode


class FakeDisplay:
    def __init__(self, visible, size):
        self.visible = visible
        self.size = size
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


@pytest.mark.asyncio
async def test_headless_mode_does_not_start_virtual_display():
    manager = VirtualDisplayManager(display_factory=FakeDisplay, xvfb_exists=lambda: True)

    handle = await manager.ensure(DisplayMode.HEADLESS)

    assert handle is None


@pytest.mark.asyncio
async def test_virtual_mode_uses_existing_display(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":7")
    manager = VirtualDisplayManager(display_factory=FakeDisplay, xvfb_exists=lambda: True)

    handle = await manager.ensure(DisplayMode.VIRTUAL)

    assert handle is None


@pytest.mark.asyncio
async def test_virtual_mode_starts_xvfb_when_display_missing(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    manager = VirtualDisplayManager(display_factory=FakeDisplay, xvfb_exists=lambda: True)

    handle = await manager.ensure(DisplayMode.VIRTUAL)

    assert handle is not None
    assert handle.display.started is True
    await handle.close()
    assert handle.display.stopped is True


@pytest.mark.asyncio
async def test_virtual_mode_fails_when_xvfb_missing(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    manager = VirtualDisplayManager(display_factory=FakeDisplay, xvfb_exists=lambda: False)

    with pytest.raises(VirtualDisplayUnavailable, match="Xvfb"):
        await manager.ensure(DisplayMode.VIRTUAL)
```

Append these tests to `tests/test_browser.py`:

```python
from cloakbrowser_mcp.browser import BrowserManager
from cloakbrowser_mcp.errors import SessionNotFound
from cloakbrowser_mcp.models import BackendMode, DisplayMode, StartOptions


class FakeBackend:
    def __init__(self, session):
        self.session = session
        self.options = None

    async def start(self, options):
        self.options = options
        return self.session


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
```

- [ ] **Step 2: Run the display and manager tests and verify they fail**

Run:

```bash
uv run pytest tests/test_display.py tests/test_browser.py -q
```

Expected: FAIL with missing `VirtualDisplayManager` and `BrowserManager`.

- [ ] **Step 3: Implement display manager, backends, and manager**

Create `src/cloakbrowser_mcp/display.py`:

```python
from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from typing import Callable, Protocol

from .errors import VirtualDisplayUnavailable
from .models import DisplayMode


class DisplayLike(Protocol):
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


@dataclass(slots=True)
class VirtualDisplayHandle:
    display: DisplayLike

    async def close(self) -> None:
        await asyncio.to_thread(self.display.stop)


def _default_display_factory(visible: bool, size: tuple[int, int]) -> DisplayLike:
    from pyvirtualdisplay.display import Display

    return Display(visible=visible, size=size)


class VirtualDisplayManager:
    def __init__(
        self,
        *,
        display_factory: Callable[[bool, tuple[int, int]], DisplayLike] = _default_display_factory,
        xvfb_exists: Callable[[], bool] | None = None,
    ) -> None:
        self._display_factory = display_factory
        self._xvfb_exists = xvfb_exists or (lambda: shutil.which("Xvfb") is not None)

    async def ensure(self, display_mode: DisplayMode) -> VirtualDisplayHandle | None:
        if display_mode is not DisplayMode.VIRTUAL:
            return None
        if os.environ.get("DISPLAY"):
            return None
        if not self._xvfb_exists():
            raise VirtualDisplayUnavailable("Xvfb is required for display_mode='virtual'")
        display = self._display_factory(False, (1920, 1080))
        await asyncio.to_thread(display.start)
        return VirtualDisplayHandle(display)
```

Replace `src/cloakbrowser_mcp/browser.py` with:

```python
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .display import VirtualDisplayManager
from .errors import CdpConnectionFailed, ElementNotFound, ScreenshotFailed, SessionNotFound
from .models import BackendMode, OperationResult, ScreenshotResult, SnapshotResult, StartOptions, StartResult


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
    ) -> None:
        self.session_id = session_id
        self.page = page
        self.context = context
        self.browser = browser
        self.backend = backend
        self.display_mode = display_mode
        self.display_handle = display_handle
        self.screenshot_dir = Path(screenshot_dir or os.environ.get("CLOAK_MCP_SCREENSHOT_DIR") or Path(tempfile.gettempdir()) / "cloakbrowser-mcp")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def navigate(self, url: str, wait_until: str = "load") -> dict[str, str]:
        await self.page.goto(url, wait_until=wait_until)
        title = await self.page.title()
        return {"session_id": self.session_id, "url": self.page.url, "title": title}

    async def click(self, selector: str) -> OperationResult:
        try:
            await self.page.click(selector)
        except TimeoutError as exc:
            raise ElementNotFound(f"Element not found for selector {selector!r}") from exc
        return OperationResult(ok=True, session_id=self.session_id)

    async def type_text(self, selector: str, text: str) -> OperationResult:
        try:
            await self.page.fill(selector, text)
        except TimeoutError as exc:
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
        try:
            if self.context is not None:
                await self.context.close()
            if self.browser is not None:
                await self.browser.close()
        finally:
            if self.display_handle is not None:
                await self.display_handle.close()


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
        context = await self._launch_context(options, headless=headless)
        page = await context.new_page()
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

    async def _launch_context(self, options: StartOptions, *, headless: bool | None) -> Any:
        if options.profile_dir:
            launcher = self.persistent_context_launcher
            if launcher is None:
                from cloakbrowser import launch_persistent_context_async

                launcher = launch_persistent_context_async
            return await launcher(
                str(options.profile_dir),
                headless=headless if headless is not None else True,
                proxy=options.proxy,
                locale=options.locale,
                timezone=options.timezone,
                humanize=options.humanize,
            )
        launcher = self.context_launcher
        if launcher is None:
            from cloakbrowser import launch_context_async

            launcher = launch_context_async
        return await launcher(
            headless=headless if headless is not None else True,
            proxy=options.proxy,
            locale=options.locale,
            timezone=options.timezone,
            humanize=options.humanize,
        )


class CdpBackend:
    def __init__(self, *, playwright_factory: Any | None = None) -> None:
        self.playwright_factory = playwright_factory

    async def start(self, options: StartOptions) -> BrowserSession:
        cdp_url = options.resolved_cdp_url()
        try:
            playwright = await self._start_playwright()
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
        except Exception as exc:
            raise CdpConnectionFailed(f"Failed to connect to CDP endpoint {cdp_url!r}") from exc
        session = BrowserSession(uuid.uuid4().hex, page, context, browser, None, "cdp", "cdp")
        session._playwright = playwright
        return session

    async def _start_playwright(self) -> Any:
        if self.playwright_factory is not None:
            return await self.playwright_factory()
        from playwright.async_api import async_playwright

        return await async_playwright().start()


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
        for session_id in list(self._sessions):
            await self.close(session_id)
```

- [ ] **Step 4: Run all current tests**

Run:

```bash
uv run pytest tests/test_models.py tests/test_display.py tests/test_browser.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/cloakbrowser_mcp/display.py src/cloakbrowser_mcp/browser.py tests/test_display.py tests/test_browser.py
git commit -m "feat: add browser backends and manager"
```

## Task 4: FastMCP Server Tools

**Files:**
- Create: `src/cloakbrowser_mcp/server.py`
- Create: `tests/test_server.py`

**Interfaces:**
- Produces: `create_server(manager: BrowserManager | None = None) -> FastMCP`.
- Produces: exported async tool functions through FastMCP registration.
- Produces: `main() -> None` console entry point using `mcp.run()`.

- [ ] **Step 1: Write failing server tool tests**

Create `tests/test_server.py`:

```python
import pytest

from cloakbrowser_mcp.models import OperationResult, ScreenshotResult, SnapshotResult, StartResult
from cloakbrowser_mcp.server import ToolHandlers


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
```

- [ ] **Step 2: Run the server tests and verify they fail**

Run:

```bash
uv run pytest tests/test_server.py -q
```

Expected: FAIL with missing `cloakbrowser_mcp.server`.

- [ ] **Step 3: Implement FastMCP server and handlers**

Create `src/cloakbrowser_mcp/server.py`:

```python
from __future__ import annotations

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


def create_server(manager: BrowserManager | None = None) -> FastMCP:
    handlers = ToolHandlers(manager or BrowserManager())
    mcp = FastMCP("CloakBrowser MCP")

    mcp.tool(description="Start a CloakBrowser session. Default mode is direct headless Linux browsing.")(handlers.browser_start)
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
        annotations=ToolAnnotations(readOnlyHint=True),
    )(handlers.browser_screenshot)
    mcp.tool(description="Close a browser session and release resources.")(handlers.browser_close)
    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run server tests and all unit tests**

Run:

```bash
uv run pytest tests/test_models.py tests/test_display.py tests/test_browser.py tests/test_server.py -q
```

Expected: PASS.

- [ ] **Step 5: Verify the console entrypoint imports**

Run:

```bash
uv run python -c "from cloakbrowser_mcp.server import create_server; print(type(create_server()).__name__)"
```

Expected output includes:

```text
FastMCP
```

- [ ] **Step 6: Commit Task 4**

```bash
git add src/cloakbrowser_mcp/server.py tests/test_server.py pyproject.toml
git commit -m "feat: expose cloakbrowser mcp tools"
```

## Task 5: Smoke Tests And README

**Files:**
- Create: `tests/test_smoke.py`
- Create: `README.md`
- Modify: `src/cloakbrowser_mcp/browser.py`

**Interfaces:**
- Produces: opt-in smoke tests controlled by environment variables.
- Produces: user-facing run instructions for Linux headless, virtual display, and CDP.

- [ ] **Step 1: Write opt-in smoke tests**

Create `tests/test_smoke.py`:

```python
import os
from pathlib import Path

import pytest

from cloakbrowser_mcp.browser import BrowserManager
from cloakbrowser_mcp.models import StartOptions


pytestmark = pytest.mark.smoke


def _smoke_enabled(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


@pytest.mark.asyncio
async def test_real_headless_example_dot_com_smoke():
    if not _smoke_enabled("CLOAK_MCP_RUN_SMOKE"):
        pytest.skip("Set CLOAK_MCP_RUN_SMOKE=1 to run real browser smoke tests")

    manager = BrowserManager()
    result = await manager.start(StartOptions.from_values(display_mode="headless"))
    try:
        nav = await manager.get(result.session_id).navigate("https://example.com", wait_until="domcontentloaded")
        snapshot = await manager.get(result.session_id).snapshot()
        screenshot = await manager.get(result.session_id).screenshot()

        assert "Example" in nav["title"]
        assert "Example Domain" in snapshot.text
        assert Path(screenshot.path).exists()
    finally:
        await manager.close_all()


@pytest.mark.asyncio
async def test_real_virtual_example_dot_com_smoke():
    if not _smoke_enabled("CLOAK_MCP_RUN_VIRTUAL_SMOKE"):
        pytest.skip("Set CLOAK_MCP_RUN_VIRTUAL_SMOKE=1 to run Xvfb smoke tests")

    manager = BrowserManager()
    result = await manager.start(StartOptions.from_values(display_mode="virtual"))
    try:
        nav = await manager.get(result.session_id).navigate("https://example.com", wait_until="domcontentloaded")
        assert "Example" in nav["title"]
    finally:
        await manager.close_all()


@pytest.mark.asyncio
async def test_real_cdp_example_dot_com_smoke():
    cdp_url = os.environ.get("CLOAK_MCP_SMOKE_CDP_URL")
    if not cdp_url:
        pytest.skip("Set CLOAK_MCP_SMOKE_CDP_URL to run CDP smoke tests")

    manager = BrowserManager()
    result = await manager.start(StartOptions.from_values(backend="cdp", cdp_url=cdp_url, fingerprint="smoke"))
    try:
        nav = await manager.get(result.session_id).navigate("https://example.com", wait_until="domcontentloaded")
        assert "Example" in nav["title"]
    finally:
        await manager.close_all()
```

- [ ] **Step 2: Run smoke tests without env and verify they skip**

Run:

```bash
uv run pytest tests/test_smoke.py -q
```

Expected: 3 skipped.

- [ ] **Step 3: Patch CDP session cleanup to stop Playwright**

Modify `BrowserSession.close()` in `src/cloakbrowser_mcp/browser.py`:

```python
    async def close(self) -> None:
        try:
            if self.context is not None:
                await self.context.close()
            if self.browser is not None:
                await self.browser.close()
            playwright = getattr(self, "_playwright", None)
            if playwright is not None:
                await playwright.stop()
        finally:
            if self.display_handle is not None:
                await self.display_handle.close()
```

- [ ] **Step 4: Add README**

Create `README.md`:

```markdown
# CloakBrowser MCP

Python MCP server for giving agents a CloakBrowser-backed browser in Linux headless, Linux virtual-display, or existing CDP environments.

## Install

```bash
uv sync --extra dev
```

The package depends on `cloakbrowser>=0.4,<1` and the official MCP Python SDK `mcp[cli]>=1.28,<2`.

## Run As MCP Stdio Server

```bash
uv run cloakbrowser-mcp
```

The default mode is direct headless browsing and does not require `$DISPLAY`.

## Browser Modes

- `display_mode="headless"`: default Linux mode, uses `headless=True`.
- `display_mode="virtual"`: uses Xvfb or an existing `$DISPLAY`, launches headed browser behavior.
- `backend="cdp"` or `display_mode="cdp"`: connects to an existing `cloakserve` or CDP endpoint.

## Tools

- `browser_start`
- `browser_navigate`
- `browser_click`
- `browser_type`
- `browser_evaluate`
- `browser_snapshot`
- `browser_screenshot`
- `browser_close`

## Linux Virtual Display

Install Xvfb in the runtime image or server:

```bash
apt-get update && apt-get install -y xvfb
```

Then start a session with:

```json
{"display_mode": "virtual"}
```

## CDP / cloakserve

Run `cloakserve` separately, then connect:

```json
{
  "backend": "cdp",
  "cdp_url": "http://127.0.0.1:9222",
  "fingerprint": "agent-session-1"
}
```

## Tests

Unit tests:

```bash
uv run pytest -q
```

Real headless smoke:

```bash
CLOAK_MCP_RUN_SMOKE=1 uv run pytest tests/test_smoke.py -q
```

Virtual display smoke:

```bash
CLOAK_MCP_RUN_VIRTUAL_SMOKE=1 uv run pytest tests/test_smoke.py -q
```

CDP smoke:

```bash
CLOAK_MCP_SMOKE_CDP_URL=http://127.0.0.1:9222 uv run pytest tests/test_smoke.py -q
```
```

- [ ] **Step 5: Run the full non-smoke suite**

Run:

```bash
uv run pytest -q
```

Expected: unit tests pass and smoke tests skip unless env vars are set.

- [ ] **Step 6: Commit Task 5**

```bash
git add src/cloakbrowser_mcp/browser.py tests/test_smoke.py README.md
git commit -m "test: add browser smoke coverage"
```

## Task 6: Final Verification

**Files:**
- No new files expected.

**Interfaces:**
- Verifies the repository is installable and all default tests pass.

- [ ] **Step 1: Sync the isolated uv environment**

Run:

```bash
uv sync --extra dev
```

Expected: install succeeds.

- [ ] **Step 2: Run all default tests**

Run:

```bash
uv run pytest -q
```

Expected: all unit tests pass; smoke tests skip unless their environment variables are set.

- [ ] **Step 3: Verify MCP entrypoint is discoverable**

Run:

```bash
uv run python -c "from cloakbrowser_mcp.server import create_server; print(type(create_server()).__name__)"
```

Expected:

```text
FastMCP
```

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: no modified tracked files. Untracked `graphify-out/` and `.DS_Store` may remain if they were not intentionally cleaned or ignored.

## Plan Self-Review

- Spec coverage: direct headless, virtual display, CDP, eight MCP tools, session lifecycle, screenshots, and smoke tests are mapped to tasks.
- Placeholder scan: no unfinished placeholder text is present.
- Type consistency: `StartOptions`, `BrowserSession`, `BrowserManager`, and `ToolHandlers` names match across tasks.
- Scope check: first version connects to existing `cloakserve` but does not manage a long-running `cloakserve` process.
