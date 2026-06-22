from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"

_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "src" / "cloakbrowser_mcp"
__path__ = [str(_PACKAGE_DIR)]
