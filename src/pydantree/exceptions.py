from __future__ import annotations


class PydantreeException(Exception):
    """Base exception for all library errors."""
    pass


class ValidationError(PydantreeException):
    """Raised when input validation fails."""
    pass


class CodeStructureError(PydantreeException):
    """Raised when code structure is invalid."""
    pass


class GraphSitterIntegrationError(PydantreeException):
    """Raised when GraphSitter integration fails."""
    pass


class BuilderError(PydantreeException):
    """Raised during builder pattern construction."""
    pass
