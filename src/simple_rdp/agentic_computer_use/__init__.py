# Lazy imports to avoid requiring google-adk at import time
# These are only imported when explicitly used
from typing import Any

__all__ = ["AgenticTool", "wrap_client_methods_for_google_adk", "AdkExternalCompaction"]


def __getattr__(name: str) -> Any:
    if name == "AgenticTool":
        from .google_adk import AgenticTool

        return AgenticTool
    if name == "wrap_client_methods_for_google_adk":
        from .google_adk import wrap_client_methods_for_google_adk

        return wrap_client_methods_for_google_adk
    if name == "AdkExternalCompaction":
        from .google_adk import AdkExternalCompaction

        return AdkExternalCompaction
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
