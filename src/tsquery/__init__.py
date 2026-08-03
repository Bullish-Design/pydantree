"""tsquery — Product A: model-only typed extraction over tree-sitter grammars.

The surface is the model:

    class Assignment(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: Annotated[str, Matches(r"^[A-Z][A-Z_]*$")] = capture("left")
        value: Annotated[int, NodeKind("integer")] = capture("right")
        line: int = source_meta()

    rows = Assignment.extract(text, language=tree_sitter_python)

The OutputModel class IS the query — the `.scm` is derived and never seen.
Phase 4 adds the node-schema bridge (tscore): `validate_with(language,
schema=...)` runs model↔grammar and capture↔type checks before any text is
parsed, and the record value-shape map is derived from the grammar.
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
    OutputModel as _MaterializeOutputModel,
    capture as _m_capture,
    source_meta as _m_source_meta,
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
]
