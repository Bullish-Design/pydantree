"""tscore — the tiny shared package (the artifact seam between tsgrammar (B)
and tsquery (A)).

`tscore.schema` — the grammar node-schema (the bridge artifact, concept §7):
the schema format, the CLI-byproduct derivation, and the hand-port of the
CLI's node_types.rs (`_ir_derive`, deleted in the 014 refactor Phase 3 —
until then it lives here). `tscore.loader` — the artifact-loading contract
(the one place a compiled grammar becomes a tree_sitter.Language). Both B
and A import tscore; A never imports B.
"""

from .schema import (
    ChildInfo,
    NodeSchema,
    NodeTypeInfo,
    NodeTypeRef,
    derive_from_ir,
    derive_from_node_types,
)

__all__ = [
    "ChildInfo",
    "NodeSchema",
    "NodeTypeInfo",
    "NodeTypeRef",
    "derive_from_ir",
    "derive_from_node_types",
]
