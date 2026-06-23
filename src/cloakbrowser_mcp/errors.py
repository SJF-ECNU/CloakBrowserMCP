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


class PageNotFound(BrowserMcpError):
    code = "PageNotFound"


class StorageStateFailed(BrowserMcpError):
    code = "StorageStateFailed"
