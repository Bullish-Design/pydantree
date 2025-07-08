"""pydantree – Typed Tree‑sitter wrapper with graph operations.

This package exposes:

Core primitives:
* **TSNode / TSPoint** – Pydantic models mirroring tree‑sitter metadata
* **Parser** – wrapper around `tree_sitter.Parser` returning validated models
* **ParsedDocument** – incremental‑parsing with text + tree sync

Code generation:
* **generate_from_node_types** – create typed subclasses from node-types.json
* **NodeTypesBootstrap** – ensure generated classes are loaded

Collections and graph operations:
* **NodeGroup** – lazy, set-theoretic collections of nodes
* **GraphBuilder** – convert NodeGroup to rustworkx graphs for analysis
* **PatternMatcher** – VF2 isomorphism matching for AST patterns

High-level views:
* **PyModule / PyFunction / PyClass** – semantic Python wrappers
* **QuerySet** – chainable selectors with Django-inspired API
* **PyTransformer** – visitor pattern for codemods

The goal is typed, incrementally-editable AST objects with advanced
querying and graph analysis capabilities.
"""

from __future__ import annotations

from .core import TSNode, TSPoint
from .parser import Parser
from .incremental import ParsedDocument
from .codegen import generate_from_node_types
from .loader import NodeTypesBootstrap
from .nodegroup import (
    NodeGroup,
    NodeSelector,
    TypeSelector,
    ClassSelector,
    PredicateSelector,
    TextSelector,
    nodes,
    from_tree,
    empty,
)
from .views import (
    PyView,
    PyModule,
    PyFunction,
    PyClass,
    PyImport,
    QuerySet,
    PyTransformer,
    parse_python,
    parse_python_file,
    find_functions,
    find_classes,
)

# Graph operations (optional - requires rustworkx)
try:
    from .graph import (
        GraphBuilder,
        PatternMatcher,
        GraphAnalyzer,
        build_tree_graph,
        build_pattern_graph,
        find_pattern_matches,
    )

    _HAS_GRAPH = True
except ImportError:
    _HAS_GRAPH = False


__all__ = [
    # Core
    "TSNode",
    "TSPoint",
    "Parser",
    "ParsedDocument",
    # Code generation
    "generate_from_node_types",
    "NodeTypesBootstrap",
    # Collections
    "NodeGroup",
    "NodeSelector",
    "TypeSelector",
    "ClassSelector",
    "PredicateSelector",
    "TextSelector",
    "nodes",
    "from_tree",
    "empty",
    # Views
    "PyView",
    "PyModule",
    "PyFunction",
    "PyClass",
    "PyImport",
    "QuerySet",
    "PyTransformer",
    "parse_python",
    "parse_python_file",
    "find_functions",
    "find_classes",
]

# Add graph operations to __all__ if available
if _HAS_GRAPH:
    __all__.extend(
        [
            "GraphBuilder",
            "PatternMatcher",
            "GraphAnalyzer",
            "build_tree_graph",
            "build_pattern_graph",
            "find_pattern_matches",
        ]
    )

__version__ = "0.2.0"
