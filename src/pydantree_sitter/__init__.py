"""pydantree_sitter — model-only typed extraction over tree-sitter grammars.

The surface is the model:

    class Assignment(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: Annotated[str, Matches(r"^[A-Z][A-Z_]*$")] = capture("left")
        value: Annotated[int, NodeKind("integer")] = capture("right")
        line: int = source_meta()

    lang = Language.load_bundle("bundles/mylang")   # or Language.load(...)
    rows = lang.extractor(Assignment).extract(text)
    rows = Assignment.extract(text, language=lang)   # sugar

The OutputModel class IS the query — the `.scm` is derived and never seen.
The node-schema bridge (`NodeSchema`, `load_bundle`) runs model↔grammar and
capture↔type checks before any text is parsed.

Phase 2 of the 014 refactor: this package folds the old seam
(schema + loader) and the old Product A into ONE light package
(`pydantree-sitter`); the legacy surfaces are glued below until the Phase-4
rewrite shrinks the exports to the target surface.
"""

from .dsl import (
    MatchView,
    NodeSpec,
    NodeView,
    Pred,
    Query,
    QueryBuildError,
    cap,
    node,
)
from .materialize import (
    AmbiguousCaptureError,
    CoercionError,
    Diagnostic,
    Span,
)
from .schema import (
    ChildInfo,
    NodeSchema,
    NodeTypeInfo,
    NodeTypeRef,
    derive_from_node_types,
)
from .typed import (
    M,
    AnyOf,
    Eq,
    ExtractionError,
    Language,
    MatchFailure,
    Matches,
    NodeKind,
    OutputModel,
    SchemaCheckError,
    Unescaped,
    UnsupportedShapeError,
    capture,
    capture_kind,
    source_meta,
)

__version__ = "0.1.0"

__all__ = [
    "OutputModel", "M", "capture", "capture_kind", "source_meta",
    "Matches", "Eq", "AnyOf", "NodeKind", "Unescaped",
    "UnsupportedShapeError", "SchemaCheckError",
    "Language", "Query", "QueryBuildError", "Span", "Diagnostic",
    "AmbiguousCaptureError", "CoercionError", "ExtractionError",
    "MatchFailure",
    "NodeSpec", "NodeView", "MatchView", "Pred", "cap", "node",
    # the seam (the old shared package's schema): the node-schema format + derivations
    "NodeSchema", "NodeTypeInfo", "ChildInfo", "NodeTypeRef",
    "derive_from_node_types",
]
