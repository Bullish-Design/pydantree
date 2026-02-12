"""Registry helpers for resolving canonical workshop paths by logical names."""

from .layout import (
    InvalidLayoutNameError,
    RepositoryRootNotFoundError,
    WorkshopLayout,
    resolve_repository_root,
)

__all__ = [
    "InvalidLayoutNameError",
    "RepositoryRootNotFoundError",
    "WorkshopLayout",
    "resolve_repository_root",
]
