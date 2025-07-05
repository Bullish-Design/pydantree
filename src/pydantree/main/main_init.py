from __future__ import annotations

__version__ = "0.1.0"

# Core exports
from .core.base import BaseCodeNode
from .core.classes import PyClass
from .core.functions import PyFunction
from .core.assignments import PyAssignment
from .core.builders import PyClassBuilder, PyFunctionBuilder

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
