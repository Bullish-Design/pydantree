"""Schema-backed typed nodes for tree-sitter grammars.

Generate a node universe from ``node-types.json`` or build one with
``Grammar.load(language, schema)``. Narrow generated classes with Pydantic
annotations and resolve them through ``Grammar.parse(source).find(cls)``.
"""

# The typed node universe is the public surface.
# ruff: noqa: RUF022

from .errors import (
    ExtractionError,
    PydantreeSitterError,
    SchemaCheckError,
    SchemaDataError,
    SchemaDistributionError,
    SchemaDriftError,
    SchemaMissingError,
    ShapeError,
)
from .generate import build_namespace, generate_module
from .grammar import Grammar
from .nodes import Node
from .pattern import Edit, Pattern, PatternMatch, ReplaceResult
from .schema import NodeSchema
from .span import Span

__version__ = "0.4.0"


def load_bundle(directory):
    """Load a schema-backed bundle as a typed :class:`Grammar`."""
    return Grammar.load_bundle(directory)

__all__ = [
    "Node",
    "Grammar",
    "Span",
    "generate_module",
    "build_namespace",
    "load_bundle",
    "NodeSchema",
    "PydantreeSitterError",
    "SchemaCheckError",
    "SchemaDataError",
    "SchemaDriftError",
    "SchemaDistributionError",
    "SchemaMissingError",
    "ShapeError",
    "ExtractionError",
    "Pattern",
    "PatternMatch",
    "Edit",
    "ReplaceResult",
]
