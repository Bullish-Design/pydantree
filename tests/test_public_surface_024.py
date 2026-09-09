"""The 0.3 typed-node-universe public surface is intentionally small."""

import pydantree_sitter as p


def test_typed_node_universe_public_surface() -> None:
    assert p.__all__ == [
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
