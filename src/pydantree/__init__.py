"""Pydantree package."""

from .registry import InvalidLayoutNameError, WorkshopLayout
from pydantree.runtime import WorkshopEventLogger, resolve_tool_versions

try:
    from pydantree._version import __version__
except Exception:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["WorkshopEventLogger", "resolve_tool_versions", "InvalidLayoutNameError", "WorkshopLayout", "__version__"]
