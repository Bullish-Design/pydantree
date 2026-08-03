"""tscore — the tiny shared package (the artifact seam between tsgrammar (B)
and tsquery (A)).

One module, no more: `tscore.schema` — the grammar node-schema (the bridge
artifact, concept §7). Both B and A import it; A never imports B.
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
