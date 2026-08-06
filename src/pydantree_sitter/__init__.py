"""pydantree_sitter — model-only typed extraction over tree-sitter grammars.

The surface is the model:

    class Assignment(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: Annotated[str, Matches(r"^[A-Z][A-Z_]*$")] = capture("left")
        value: Annotated[int, NodeKind("integer")] = capture("right")
        line: int = source_meta()

    lang = Language.load_bundle("bundles/mylang")   # or Language.from_module(...)
    ext  = lang.extractor(Assignment)                # ALL checks run here, once
    rows = ext.extract(text)
    rows = Assignment.extract(text, language=lang)   # sugar

The OutputModel class IS the query — the `.scm` is derived and never seen.
The node-schema bridge (`NodeSchema`, `load_bundle`) runs model↔grammar and
capture↔type checks at bind time; value shapes are declared data
(`ValueMap`) — never silent name-regex inference (`propose_value_map` is the
draft generator). `__raw_query__ = RawQuery('(module ...)')` is the escape
hatch: a literal .scm whose captures map to fields by name (the query DSL is
not public; sibling order/negation/multi-anchor joins live there).
"""

from .binding import Extractor, Language
from .errors import (
    AmbiguousCaptureError,
    BundleError,
    ExtractionError,
    PydantreeSitterError,
    QueryBuildError,
    SchemaCheckError,
    ShapeError,
)
from .loader import load_bundle
from .markers import (
    M,
    AnyOf,
    Eq,
    Matches,
    NodeKind,
    RawQuery,
    Unescaped,
    capture,
    capture_kind,
    derived,
    source_meta,
)
from .materialize import MatchFailure, Span
from .schema import (
    ChildInfo,
    NodeSchema,
    NodeTypeInfo,
    NodeTypeRef,
    derive_from_node_types,
)
from .spec import OutputModel
from .valuemap import JSON_VALUE_MAP, ValueMap, propose_value_map

__version__ = "0.2.0"

__all__ = [
    # the model surface
    "OutputModel", "M", "capture", "capture_kind", "source_meta", "derived",
    "Matches", "Eq", "AnyOf", "NodeKind", "Unescaped", "RawQuery",
    # the bind
    "Language", "Extractor", "Span",
    # the schema seam + declared value shapes
    "NodeSchema", "NodeTypeInfo", "ChildInfo", "NodeTypeRef",
    "ValueMap", "JSON_VALUE_MAP", "propose_value_map", "load_bundle",
    # errors (the taxonomy, §1.3)
    "PydantreeSitterError", "SchemaCheckError", "ShapeError",
    "QueryBuildError", "ExtractionError", "AmbiguousCaptureError",
    "BundleError", "MatchFailure",
]
