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
        resolved_backend = _enum_value(BackendMode, backend, BackendMode.DIRECT)

        if backend is not None and display_mode is not None:
            if resolved_backend is BackendMode.DIRECT and resolved_display is DisplayMode.CDP:
                raise ValueError("backend/display_mode conflict: direct backend cannot use cdp display mode")
            if resolved_backend is BackendMode.CDP and resolved_display is not DisplayMode.CDP:
                raise ValueError("backend/display_mode conflict: cdp backend requires display_mode='cdp'")

        if resolved_display is DisplayMode.CDP:
            resolved_backend = BackendMode.CDP

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
        if self.headless is not None:
            return self.headless
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
