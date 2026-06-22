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
