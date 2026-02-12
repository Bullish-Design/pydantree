"""Pydantree package."""

__all__ = ["__version__"]

try:
    from pydantree._version import __version__
except Exception:  # pragma: no cover
    __version__ = "0.0.0"
