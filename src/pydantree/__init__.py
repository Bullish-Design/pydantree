# pydantree/__init__.py
"""
Pydantree: A high-performance, multi-language AST analysis platform.

This library provides a typed, Pydantic-validated wrapper around Tree-sitter
for robust static analysis, code transformation, and batch processing.

Key Modules:
- `pydantree.core`: Core data structures like TSNode and parsers.
- `pydantree.languages`: Language-specific abstractions and implementations.
- `pydantree.processing`: Tools for batch processing and node collections.
- `pydantree.export`: A unified engine for exporting ASTs and analysis results.
- `pydantree.graph`: AST-to-graph conversion and analysis capabilities.
"""

# Load and register built-in languages
from . import languages

from .core.nodes import TSNode, TraversalOrder
from .core.parsers import Parser, parse_file
from .languages.base import (
    Language,
    SemanticNode,
    SemanticRole,
    create_language,
    get_language,
)
from .languages.registry import (
    get_global_registry,
    detect_language,
    get_supported_languages,
    LanguageFeature,
)
from .processing.collections import NodeGroup, nodes, from_tree

try:
    from ._version import __version__
except ImportError:
    __version__ = "1.0.0"

__all__ = [
    # Core
    "TSNode",
    "TraversalOrder",
    "Parser",
    "parse_file",
    # Languages
    "Language",
    "SemanticNode",
    "SemanticRole",
    "create_language",
    "get_language",
    "get_global_registry",
    "detect_language",
    "get_supported_languages",
    "LanguageFeature",
    # Processing
    "NodeGroup",
    "nodes",
    "from_tree",
    # Version
    "__version__",
]
