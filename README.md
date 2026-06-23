# CloakBrowser MCP

Python MCP server for giving agents a CloakBrowser-backed browser in Linux headless, Linux virtual-display, or existing CDP environments.

## Install

```bash
uv sync --extra dev --no-editable
```

The package depends on `cloakbrowser>=0.4,<1` and the official MCP Python SDK `mcp[cli]>=1.28,<2`.

For local verification after dependency changes, reinstall the package into the uv environment:

```bash
uv sync --extra dev --no-editable --reinstall-package cloakbrowser-mcp
```

## Run As MCP Stdio Server

```bash
uv run --no-editable cloakbrowser-mcp
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

Unit tests and default smoke skip behavior:

```bash
uv run --no-editable pytest -q
```

Real headless smoke:

```bash
CLOAK_MCP_RUN_SMOKE=1 uv run --no-editable pytest tests/test_smoke.py -q
```

Virtual display smoke:

```bash
CLOAK_MCP_RUN_VIRTUAL_SMOKE=1 uv run --no-editable pytest tests/test_smoke.py -q
```

CDP smoke:

```bash
CLOAK_MCP_SMOKE_CDP_URL=http://127.0.0.1:9222 uv run --no-editable pytest tests/test_smoke.py -q
```
