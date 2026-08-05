"""pydantree_sitter.markers — the model markers (inert data, 014 §4.1).

Every marker is a plain inert value: the metaclass reads them via
`isinstance` (never name-matching) and derives a `MatchSpec` (spec.py).
Nothing here imports the grammar side; the markers carry no behavior.

Surface: M, capture, capture_kind, source_meta, derived, Matches, Eq, AnyOf,
NodeKind, Unescaped.
"""

from __future__ import annotations

from typing import Optional, Union

# --------------------------------------------------------------------------
# capture-name constants
# --------------------------------------------------------------------------

ANCHOR = "__anchor__"       # the match anchor (every emitted pattern captures it)
RECORD_CAP = "record"       # the record node (record-mode outer query)

_MISSING = object()         # sentinel: no value supplied

# the '...' path element (a gap matching ANY depth between kinds)
GAP = object()


# --------------------------------------------------------------------------
# M — the one structural declaration
# --------------------------------------------------------------------------

class M:
    """The ancestor path of node kinds.

    M("module", "expression_statement", "assignment") -> anchored pattern
    (module (expression_statement (assignment ...))).

    Path elements may alternate: M(("if_statement", "while_statement"), ...)
    emits one pattern per kind. A `...` element (the GAP, written `...` or
    Ellipsis) matches ANY depth between the kinds it separates — implemented
    by walking the match anchor's ancestors at materialization (the
    `#has-ancestor?` assessment: it cannot express the anchor's own ancestor
    constraint in a single pattern and cannot bound depth — the walk is
    exact and handles any number of gaps).

    record=True switches to key/value record semantics (see spec.py).
    """

    __slots__ = ("path", "record")

    def __init__(self, *path, record: bool = False):
        if not path:
            raise ValueError("M() needs at least one node kind")
        normalized = []
        for p in path:
            if p is Ellipsis or p == "...":
                normalized.append(GAP)
            elif isinstance(p, str):
                normalized.append(p)
            elif isinstance(p, (tuple, list)) and p and \
                    all(isinstance(k, str) for k in p):
                normalized.append(tuple(p))
            else:
                raise TypeError(
                    f"M() path elements must be kind strings, kind tuples, "
                    f"or '...' — got {p!r}")
        if normalized[0] is GAP or normalized[-1] is GAP:
            raise ValueError(
                "M(): '...' must sit BETWEEN node kinds (a leading/trailing "
                "gap is meaningless)")
        self.path = tuple(normalized)
        self.record = record

    def __repr__(self) -> str:  # pragma: no cover
        shown = ["..." if p is GAP else p for p in self.path]
        return f"M({', '.join(repr(p) for p in shown)}, record={self.record})"


# --------------------------------------------------------------------------
# field markers (the `= marker(...)` defaults)
# --------------------------------------------------------------------------

class _Capture:
    """`= capture("left")` binds the field to CST field `left`; no-arg means
    the attr name IS the CST field name (unmarked fields behave the same —
    bind-by-name in BOTH modes, 014 §4.1)."""

    __slots__ = ("field",)

    def __init__(self, field: Optional[str] = None):
        self.field = field


class _CaptureKind:
    """`= capture_kind("code_span")` binds the field to a CHILD BY NODE KIND
    (for grammars that use positional children — real markdown's inline
    elements and fenced-code children have no CST fields)."""

    __slots__ = ("kind",)

    def __init__(self, kind: str):
        self.kind = kind


class _SourceMeta:
    """`= source_meta()` injects the match anchor's span (int -> start line,
    Span -> full span). `source_meta(capture="x")` uses capture @x instead."""

    __slots__ = ("capture",)

    def __init__(self, capture: str = ANCHOR):
        self.capture = capture


class _Derived:
    """`= derived()` marks a field as COMPUTED: it is excluded from the
    query entirely (the marked form of what used to be an unmarked field in
    field mode — 014 §4.1 symmetry). `derived(value)` supplies the constant
    value; bare `derived()` leaves the field absent (None / pydantic's
    rules)."""

    __slots__ = ("default",)

    def __init__(self, default=_MISSING):
        self.default = default


def capture(field: Optional[str] = None) -> _Capture:
    return _Capture(field)


def capture_kind(kind: str) -> _CaptureKind:
    return _CaptureKind(kind)


def source_meta(capture: str = ANCHOR) -> _SourceMeta:
    return _SourceMeta(capture)


def derived(value=_MISSING) -> _Derived:
    return _Derived(value)


_MARKERS = (_Capture, _CaptureKind, _SourceMeta, _Derived)


# --------------------------------------------------------------------------
# metadata markers (Annotated[...] metadata) + predicates
# --------------------------------------------------------------------------

class NodeKind:
    """Annotated[str, NodeKind("integer")] constrains a capture's node kind.
    A TUPLE alternates: one emitted pattern per kind (F-A3)."""

    __slots__ = ("kinds",)

    def __init__(self, kinds: Union[str, tuple[str, ...], list[str]]):
        if isinstance(kinds, str):
            kinds = (kinds,)
        if not kinds or not all(isinstance(k, str) for k in kinds):
            raise TypeError(f"NodeKind needs kind strings, got {kinds!r}")
        self.kinds = tuple(kinds)

    def __repr__(self) -> str:  # pragma: no cover
        return f"NodeKind({self.kinds!r})"


class Matches:
    """Annotated[str, Matches(r"^[A-Z]+$")] — a `#match?` predicate."""

    __slots__ = ("re",)

    def __init__(self, re: str):
        self.re = re

    def __repr__(self) -> str:  # pragma: no cover
        return f"Matches({self.re!r})"


class Eq:
    """Annotated[str, Eq("=")] — a `#eq?` predicate."""

    __slots__ = ("value",)

    def __init__(self, value: str):
        self.value = value

    def __repr__(self) -> str:  # pragma: no cover
        return f"Eq({self.value!r})"


class AnyOf:
    """Annotated[str, AnyOf("a", "b")] — an `#any-of?` predicate."""

    __slots__ = ("values",)

    def __init__(self, *values: str):
        self.values = tuple(values)

    def __repr__(self) -> str:  # pragma: no cover
        return f"AnyOf({self.values!r})"


class Unescaped:
    """Annotated[str, Unescaped()] — the capture is the string WRAPPER's
    text (escaped strings split across string_content pieces; the wrapper
    decodes as one value), and the materialized value is JSON-unescaped."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover
        return "Unescaped()"


# --------------------------------------------------------------------------
# the escape hatch: a literal .scm query
# --------------------------------------------------------------------------

class RawQuery(str):
    """`__raw_query__ = RawQuery('(module (assignment left: (_) @left))')` —
    a literal .scm compiled verbatim; captures map to fields by name. The
    query DSL is not public; sibling order/negation/multi-anchor joins are
    out of scope and expressed here."""

    __slots__ = ()
