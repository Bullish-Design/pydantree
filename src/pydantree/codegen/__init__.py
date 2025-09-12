# pydantree/codegen/__init__.py
"""Automatic generation of typed TSNode subclasses from Tree-sitter grammars."""

from .generator import (
    CodeGenerator,
    NameResolver,
    InheritanceAnalyzer,
    generate_from_node_types,
    validate_node_types_json,
)

__all__ = [
    "CodeGenerator",
    "NameResolver",
    "InheritanceAnalyzer",
    "generate_from_node_types",
    "validate_node_types_json",
]
