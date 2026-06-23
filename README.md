# CloakBrowser MCP

CloakBrowser MCP is a Python MCP server that lets agents control a
CloakBrowser-backed browser from Linux servers, CI jobs, and other environments
where a normal desktop browser is not available.

It is designed for three runtime modes:

- headless Linux browsing with no `$DISPLAY`
- virtual-display browsing through Xvfb when headed browser behavior is needed
- CDP connection to an existing CloakBrowser or Chromium-compatible endpoint

The server exposes browser automation tools over MCP stdio, so clients such as
Claude Code can start a session, navigate, inspect pages, interact with forms,
manage cookies/storage, and work with multiple tabs.

## Features

- 28 MCP tools for browser sessions, page interaction, cookies, storage state,
  and multi-page workflows.
- Works in headless Linux environments by default.
- Optional Xvfb support for virtual display sessions.
- Optional CDP backend for connecting to an existing browser service.
- CloakBrowser launch options for user agent, viewport, proxy, locale,
  timezone, geolocation, humanization, extensions, headers, permissions, and
  persistent profile/state.
- iframe-aware select support through `browser_select_option(...,
  frame_selector="iframe#...")`.
- `uv`-managed local development and deployment.

## Requirements

- Python 3.11 or newer
- `uv`
- Linux, macOS, or another platform supported by the Python dependencies
- For virtual display mode on Linux: `Xvfb`

Install `uv` if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For virtual display mode on Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y xvfb
```

If the runtime does not already have browser binaries available, install the
Playwright Chromium browser used by the underlying stack:

```bash
uv run python -m playwright install chromium
```

## Installation

Clone the repository and create an isolated `uv` environment:

```bash
git clone https://github.com/SJF-ECNU/CloakBrowserMCP.git
cd CloakBrowserMCP
uv sync --extra dev --no-editable
```

The project depends on:

- `cloakbrowser>=0.4,<1`
- `mcp[cli]>=1.28,<2`
- `pyvirtualdisplay>=3,<4`

After changing source code, rebuild the installed package used by MCP clients:

```bash
uv sync --extra dev --no-editable --reinstall-package cloakbrowser-mcp
```

## Run the MCP Server

Start the stdio MCP server:

```bash
uv run --no-editable cloakbrowser-mcp
```

The process communicates over stdio. It is normally launched by an MCP client
rather than run manually in a terminal.

## Claude Code Setup

From the repository root, register the server:

```bash
claude mcp add --scope user cloakbrowser -- \
  uv --project "$PWD" run --no-editable cloakbrowser-mcp
```

Then restart Claude Code or reconnect MCP servers. Run `/mcp` in Claude Code and
confirm that `cloakbrowser` is connected.

If you edit the server code, reinstall the package and reconnect Claude Code:

```bash
uv sync --extra dev --no-editable --reinstall-package cloakbrowser-mcp
```

Claude Code may cache MCP tool schemas for the lifetime of a connection, so a
restart/reconnect is recommended after tool signature changes.

## Generic MCP Client Config

For clients that read JSON MCP configuration, use an entry like this:

```json
{
  "mcpServers": {
    "cloakbrowser": {
      "command": "uv",
      "args": [
        "--project",
        "/absolute/path/to/CloakBrowserMCP",
        "run",
        "--no-editable",
        "cloakbrowser-mcp"
      ]
    }
  }
}
```

Replace `/absolute/path/to/CloakBrowserMCP` with the local checkout path.

## Browser Modes

### Headless Mode

This is the default and is the best choice for Linux servers without a display:

```json
{
  "display_mode": "headless"
}
```

### Virtual Display Mode

Use this when a target site requires headed browser behavior. If `$DISPLAY` is
already set, the server uses it. Otherwise it starts Xvfb.

```json
{
  "display_mode": "virtual"
}
```

### CDP Mode

Use CDP mode to connect to an existing browser or CloakBrowser service:

```json
{
  "backend": "cdp",
  "cdp_url": "http://127.0.0.1:9222",
  "fingerprint": "agent-session-1"
}
```

You can also set a default CDP URL:

```bash
export CLOAK_MCP_DEFAULT_CDP_URL=http://127.0.0.1:9222
```

## Tool Overview

Session tools:

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

Context and page management:

- `browser_get_cookies`
- `browser_set_cookies`
- `browser_clear_cookies`
- `browser_get_storage_state`
- `browser_save_storage_state`
- `browser_new_page`
- `browser_list_pages`
- `browser_switch_page`
- `browser_close_page`

## Common Workflows

### Start and Navigate

```json
{
  "tool": "browser_start",
  "arguments": {
    "display_mode": "headless",
    "viewport": {"width": 1440, "height": 900},
    "locale": "en-US",
    "timezone": "UTC"
  }
}
```

Then navigate:

```json
{
  "tool": "browser_navigate",
  "arguments": {
    "session_id": "<session_id>",
    "url": "https://example.com",
    "wait_until": "domcontentloaded"
  }
}
```

### Inspect a Page

Use `browser_snapshot` for URL, title, and visible text. Use `browser_get_text`
for all visible text or a selector-specific text extraction:

```json
{
  "tool": "browser_get_text",
  "arguments": {
    "session_id": "<session_id>",
    "selector": "main"
  }
}
```

### Search or Fill a Form

```json
{
  "tool": "browser_type",
  "arguments": {
    "session_id": "<session_id>",
    "selector": "input[name=q]",
    "text": "CloakBrowser MCP"
  }
}
```

```json
{
  "tool": "browser_press",
  "arguments": {
    "session_id": "<session_id>",
    "selector": "input[name=q]",
    "key": "Enter"
  }
}
```

### Select an Option inside an iframe

For a normal page-level `<select>`, omit `frame_selector`. For a select inside
an iframe, pass the iframe selector separately:

```json
{
  "tool": "browser_select_option",
  "arguments": {
    "session_id": "<session_id>",
    "selector": "#size",
    "value": "medium",
    "frame_selector": "iframe#preview"
  }
}
```

### Reuse Login State

Save storage state:

```json
{
  "tool": "browser_save_storage_state",
  "arguments": {
    "session_id": "<session_id>",
    "path": "/tmp/cloak-state.json"
  }
}
```

Start a new session with that state:

```json
{
  "tool": "browser_start",
  "arguments": {
    "storage_state": "/tmp/cloak-state.json"
  }
}
```

For durable browser profiles, use `profile_dir` instead. `profile_dir` and
`storage_state` are mutually exclusive.

## `browser_start` Options

| Option | Type | Notes |
| --- | --- | --- |
| `backend` | string | `direct` or `cdp`. Defaults to `direct`. |
| `display_mode` | string | `headless`, `virtual`, or `cdp`. Defaults to `headless`. |
| `headless` | bool/null | Overrides headless behavior for direct mode. |
| `proxy` | string/null | Proxy URL forwarded to CloakBrowser. |
| `locale` | string/null | Browser locale, for example `en-US`. |
| `timezone` | string/null | Browser timezone, for example `UTC`. |
| `humanize` | bool | Enables CloakBrowser humanized behavior. |
| `profile_dir` | string/null | Persistent profile directory. |
| `cdp_url` | string/null | Required for CDP mode unless env var is set. |
| `fingerprint` | string/null | Added to the CDP URL as a `fingerprint` query parameter. |
| `user_agent` | string/null | Custom user agent. |
| `viewport` | object/null | Example: `{"width": 1440, "height": 900}`. |
| `no_viewport` | bool | Sets Playwright viewport to `null`. |
| `color_scheme` | string/null | `light`, `dark`, or `no-preference`. |
| `geoip` | bool | Forwards CloakBrowser geoip option. |
| `stealth_args` | bool | Defaults to `true`. |
| `args` | array/null | Extra browser launch args. |
| `extension_paths` | array/null | Browser extension paths. |
| `human_preset` | string | CloakBrowser humanization preset. |
| `human_config` | object/null | CloakBrowser humanization config. |
| `storage_state` | string/object/null | Storage state path or object. |
| `extra_http_headers` | object/null | Extra HTTP headers. |
| `permissions` | array/null | Browser context permissions. |

Environment variables:

- `CLOAK_MCP_DEFAULT_DISPLAY_MODE`: default display mode when not provided
- `CLOAK_MCP_DEFAULT_CDP_URL`: default CDP endpoint
- `CLOAK_MCP_SCREENSHOT_DIR`: screenshot output directory

## Development

Install development dependencies:

```bash
uv sync --extra dev
```

Run tests against the source tree:

```bash
PYTHONPATH=src uv run pytest -q
```

Run tests against the installed package:

```bash
uv sync --extra dev --no-editable --reinstall-package cloakbrowser-mcp
uv run --no-editable pytest -q
```

Real browser smoke tests are opt-in:

```bash
CLOAK_MCP_RUN_SMOKE=1 uv run --no-editable pytest tests/test_smoke.py -q
```

Virtual display smoke:

```bash
CLOAK_MCP_RUN_VIRTUAL_SMOKE=1 uv run --no-editable pytest tests/test_smoke.py -q
```

CDP smoke:

```bash
CLOAK_MCP_SMOKE_CDP_URL=http://127.0.0.1:9222 \
  uv run --no-editable pytest tests/test_smoke.py -q
```

## Security Notes

Browser automation can access web pages, cookies, local files referenced by the
browser profile, and authenticated sessions. Run the MCP server in an
environment appropriate for the trust level of the agent and target websites.

Avoid sharing persistent `profile_dir` or `storage_state` files with untrusted
agents.

## License

MIT. See [LICENSE](LICENSE).
