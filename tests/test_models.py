import os

import pytest

from cloakbrowser_mcp.models import BackendMode, DisplayMode, StartOptions


def test_default_start_options_are_direct_headless():
    options = StartOptions.from_values()

    assert options.backend is BackendMode.DIRECT
    assert options.display_mode is DisplayMode.HEADLESS
    assert options.resolved_headless() is True


def test_explicit_headless_false_in_direct_mode():
    options = StartOptions.from_values(headless=False)

    assert options.backend is BackendMode.DIRECT
    assert options.resolved_headless() is False


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


@pytest.mark.parametrize(
    ("backend", "display_mode"),
    [
        ("direct", "cdp"),
        ("cdp", "headless"),
        ("cdp", "virtual"),
    ],
)
def test_explicit_backend_and_display_mode_conflicts_raise(backend, display_mode):
    with pytest.raises(ValueError, match="conflict"):
        StartOptions.from_values(
            backend=backend,
            display_mode=display_mode,
            cdp_url="http://127.0.0.1:9222",
        )


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
