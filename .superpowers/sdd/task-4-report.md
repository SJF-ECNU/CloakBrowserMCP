## Task 4 Report

### Scope and assumptions
- The task brief is the contract: implement `src/cloakbrowser_mcp/server.py`, add `tests/test_server.py`, and expose exactly 8 FastMCP tools.
- Existing browser lifecycle code in `BrowserManager`, `BrowserSession`, and the result models was treated as stable and reused as-is.
- `pyproject.toml` already pointed the console script at `cloakbrowser_mcp.server:main`, so there was no reason to modify it.

### Repository investigation
- Used the existing `graphify-out/graph.json` and queried the repo graph for `BrowserManager`, `BrowserSession`, `StartOptions`, and the result models.
- Confirmed the relevant boundary:
  - `BrowserManager.start()` returns `StartResult`
  - `BrowserManager.get()` returns a `BrowserSession`
  - `BrowserManager.close()` returns `OperationResult`
  - `BrowserSession` already provides `navigate`, `click`, `type_text`, `evaluate`, `snapshot`, and `screenshot`
- This made the server layer a thin adapter only: parse start options, delegate to manager/session methods, and convert dataclass results with `to_dict()`.

### RED phase
- Added `tests/test_server.py` with:
  - `test_browser_start_passes_options_to_manager`
  - `test_page_tools_return_dicts`
  - `test_browser_close_delegates_to_manager`
  - `test_create_server_registers_only_approved_tools`
- Ran:
  - `uv run --no-editable pytest tests/test_server.py -q`
- Confirmed RED with:
  - `ModuleNotFoundError: No module named 'cloakbrowser_mcp.server'`

### Implementation
- Added `src/cloakbrowser_mcp/server.py` with:
  - `ToolHandlers(manager)`
  - `browser_start`
  - `browser_navigate`
  - `browser_click`
  - `browser_type`
  - `browser_evaluate`
  - `browser_snapshot`
  - `browser_screenshot`
  - `browser_close`
  - `create_server(manager: BrowserManager | None = None) -> FastMCP`
  - `main() -> None`
- Kept the implementation deliberately thin:
  - `browser_start` uses `StartOptions.from_values(...)`
  - dataclass result objects are converted through `to_dict()`
  - `navigate` and `evaluate` return the underlying session values directly
  - snapshot and screenshot tools are marked read-only with `ToolAnnotations(readOnlyHint=True)`
- Registered exactly these 8 tool names on `FastMCP`:
  - `browser_start`
  - `browser_navigate`
  - `browser_click`
  - `browser_type`
  - `browser_evaluate`
  - `browser_snapshot`
  - `browser_screenshot`
  - `browser_close`

### GREEN verification
- Refreshed the non-editable install as required:
  - `uv sync --extra dev --no-editable --reinstall-package cloakbrowser-mcp`
- Focused server verification:
  - `uv run --no-editable pytest tests/test_server.py -q`
  - Result: `4 passed in 0.22s`
- Full required unit verification:
  - `uv run --no-editable pytest tests/test_models.py tests/test_display.py tests/test_browser.py tests/test_server.py -q`
  - Result: `35 passed in 0.24s`
- Console entrypoint import verification:
  - `uv run --no-editable python -c "from cloakbrowser_mcp.server import create_server; print(type(create_server()).__name__)"`
  - Result: `FastMCP`

### Notes / residual concerns
- The server tests validate handler delegation and tool registration shape, but they do not execute an MCP transport round-trip over stdio. That matches the task brief and keeps the scope surgical.
- `FastMCP.list_tools()` is async in the installed MCP version; the registration test was adjusted to await it instead of assuming a synchronous API.
