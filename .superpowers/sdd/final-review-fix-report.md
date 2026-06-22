## Final review fix report

### Scope
- Hook `BrowserManager.close_all()` into FastMCP lifespan shutdown.
- Reject explicit `backend` / `display_mode` conflicts in `StartOptions.from_values()`.
- Make `BrowserManager.close_all()` best-effort and re-raise the first close error after cleanup.
- Remove `readOnlyHint` from `browser_screenshot` while keeping `browser_snapshot` read-only.

### RED result
- Command: `uv run --no-editable pytest -q tests/test_models.py tests/test_browser.py tests/test_server.py`
- Result before reinstalling the package after test additions:
  - `6 failed, 31 passed`
  - Failures matched the expected findings:
    - 3 parameter-conflict cases did not raise.
    - `close_all()` stopped after the first failure.
    - server lifespan cleanup was not wired.
    - `browser_screenshot` was still read-only.

### Fix summary
- `src/cloakbrowser_mcp/models.py`
  - Added explicit conflict validation for `backend` and `display_mode`.
  - Preserved existing implicit CDP behavior for `display_mode="cdp"` and `backend="cdp"`.
- `src/cloakbrowser_mcp/browser.py`
  - Changed `close_all()` to attempt all session closes, always remove sessions, and re-raise the first exception.
- `src/cloakbrowser_mcp/server.py`
  - Added FastMCP lifespan cleanup that calls `manager.close_all()` on shutdown.
  - Removed the screenshot tool's read-only annotation.

### Verification
- `uv sync --extra dev --no-editable --reinstall-package cloakbrowser-mcp`
- `uv run --no-editable pytest -q`
  - `41 passed, 3 skipped`
- `uv run --no-editable python - <<'PY' ... create_server().list_tools() ... PY`
  - Reported exactly `8` tools:
    - `browser_start`
    - `browser_navigate`
    - `browser_click`
    - `browser_type`
    - `browser_evaluate`
    - `browser_snapshot`
    - `browser_screenshot`
    - `browser_close`
