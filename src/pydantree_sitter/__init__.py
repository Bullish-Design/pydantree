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

from .agreement import GrammarAgreement
from .binding import Extractor, Language
from .errors import (
    AmbiguousCaptureError,
    BundleError,
    ExtractionError,
    PatternBuildError,
    PatternError,
    PatternResolutionError,
    PatternRewriteError,
    PydantreeSitterError,
    QueryBuildError,
    SchemaCheckError,
    ShapeError,
    UnsupportedLanguageError,
    TreeLanguageError,
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

# 022 §12: importing these names must NEVER require the `pattern` extra.
# `pattern.py` imports `ast_grep_py` inside `Pattern.__init__`, so this line
# is safe without ast-grep-py installed — only CONSTRUCTING a Pattern needs
# it, and the missing extra is then a PatternError naming what to install.
from .pattern import (
    Edit,
    Pattern,
    PatternMatch,
    ReplaceResult,
    register_bundle_language,
    registered_languages,
)
from .rules import Rule
from .syntax import SYNTAX_CHECKS, check_json, check_python, syntax_check_for
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
    # structural pattern matching + rewrite (022) — the `pattern` extra
    "Pattern", "PatternMatch", "Rule", "Edit", "ReplaceResult",
    "GrammarAgreement", "register_bundle_language", "registered_languages",
    # the third-parser seam: what the LANGUAGE calls valid, not tree-sitter
    "SYNTAX_CHECKS", "syntax_check_for", "check_python", "check_json",
    "PatternError", "PatternBuildError", "PatternResolutionError",
    "PatternRewriteError", "UnsupportedLanguageError", "TreeLanguageError",
]
