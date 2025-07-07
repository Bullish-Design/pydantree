from __future__ import annotations

__version__ = "0.1.0"

# Core exports
from .core.base import BaseCodeNode
from .core.classes import PyClass
from .core.functions import PyFunction
from .core.assignments import PyAssignment
from .core.builders import PyClassBuilder, PyFunctionBuilder
from .core.file import PyFile
from .core.imports import PyImport
from .core.statements import PyStatement


# Configuration
from .config.settings import PydantreeConfig

# Factory functions
from .utils.factory import from_graphsitter, builder_for

# Main API class
from .api import PydantreeAPI

__all__ = [
    # Core models
    "BaseCodeNode",
    "PyClass",
    "PyFunction",
    "PyAssignment",
    "PyFile",
    "PyImport",
    "PyStatement",
    # Builders
    "PyClassBuilder",
    "PyFunctionBuilder",
    # Configuration
    "PydantreeConfig",
    # Utilities
    "from_graphsitter",
    "builder_for",
    # Main API
    "PydantreeAPI",
]
