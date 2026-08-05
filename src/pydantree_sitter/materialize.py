"""pydantree_sitter.materialize — capture -> OutputModel materialization (Product A,
concept §5.4). Mechanical port of `spike-a/materialize.py`.

Design (verified against pydantic 2.13 / tree-sitter 0.26):

  * Pydantic v2 lax mode is the coercion engine: we hand the materializer
    raw capture TEXT to `Model(**kwargs)` and let pydantic coerce
    "1920" -> int, "98.5" -> float, "true" -> bool, "admin" -> enum.
  * Field <-> capture binding is by name: field `name` <- capture @name,
    unless the field declares `= capture("other")`. `= source_meta()` fields
    are injected from a capture's span (int -> start line; Span -> whole span).
  * Missing capture: a field with a real default gets it; Optional-without-
    default and required fields surface as pydantic ValidationError.
  * Repeated captures -> list: a `list[X]` field collects every node captured
    under its capture name. (0.26 note: quantified sub-nodes do NOT accumulate
    captures in one match — the record extractor merges captures across
    matches sharing a record anchor.)
  * Multiple nodes feeding one scalar field = AmbiguousCaptureError (a nested
    structure with the same key as a wanted field) — Phase 4 replaces the
    nested-collision class with record-level anchoring (see typed.py).
"""

from __future__ import annotations

import sys
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError
from pydantic.fields import PydanticUndefined

import tree_sitter


# --------------------------------------------------------------------------
# Output model + binding markers
# --------------------------------------------------------------------------

class OutputModel(BaseModel):
    """Base class for extraction targets. Fields map to captures by name."""


class Span:
    """A source span (line/column, 1-based lines)."""
    __slots__ = ("line", "column", "end_line", "end_column",
                 "start_byte", "end_byte", "text")

    def __init__(self, line, column, end_line, end_column,
                 start_byte, end_byte, text):
        self.line = line
        self.column = column
        self.end_line = end_line
        self.end_column = end_column
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.text = text

    @classmethod
    def from_node(cls, node: tree_sitter.Node) -> "Span":
        r = node.range
        text = node.text.decode("utf-8", "replace") if node.text else ""
        return cls(r.start_point.row + 1, r.start_point.column,
                   r.end_point.row + 1, r.end_point.column,
                   r.start_byte, r.end_byte, text)

    def __repr__(self) -> str:  # pragma: no cover
        return (f"Span({self.line}:{self.column}-"
                f"{self.end_line}:{self.end_column} {self.text!r})")


class Diagnostic:
    """One ERROR/MISSING node in a parse (CONCEPT §5.6, Phase 5).

    `kind` is "ERROR" or "MISSING"; `node_type` is the offending node's type
    (ERROR) or the kind the parser expected (MISSING); `expected` mirrors
    node_type for MISSING nodes and is None for ERRORs (tree-sitter always
    returns a tree with these nodes instead of throwing); `span` is the
    Span-typed source range and `snippet` the offending text.
    """

    __slots__ = ("kind", "node_type", "expected", "span", "snippet")

    def __init__(self, kind: str, node_type: str, span: "Span",
                 snippet: str):
        self.kind = kind
        self.node_type = node_type
        self.expected = node_type if kind == "MISSING" else None
        self.span = span
        self.snippet = snippet

    def __repr__(self) -> str:  # pragma: no cover
        return (f"Diagnostic({self.kind}, {self.node_type!r}, "
                f"line {self.span.line}, {self.snippet!r})")


class _CaptureMarker:
    """`field = capture("other")` — bind a field to a differently-named capture."""

    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name


class _SourceMeta:
    """`field = source_meta(capture="root")` — inject span/position data."""

    __slots__ = ("capture",)

    def __init__(self, capture: str = "root"):
        self.capture = capture


def capture(name: str) -> _CaptureMarker:
    return _CaptureMarker(name)


def source_meta(capture: str = "root") -> _SourceMeta:
    return _SourceMeta(capture)


class CoercionError(ValueError):
    """A capture could not be mapped onto the model (pre-pydantic checks)."""


class AmbiguousCaptureError(CoercionError):
    """A scalar field got multiple capture nodes (e.g. nested key collision)."""


# --------------------------------------------------------------------------
# Binding checks (cheap, no grammar introspection)
# --------------------------------------------------------------------------

def _unwrap_optional(t: Any) -> Any:
    origin = get_origin(t)
    if origin in (Union,):
        args = [a for a in get_args(t) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return t


def binding_warnings(query, model: type[BaseModel], *,
                     record_mode: bool = False,
                     span_query=None) -> list[str]:
    """Warn before parsing when the model and query disagree on captures.

    `span_query` is the query that must provide source_meta captures (in
    record mode this is the OUTER record query, not the field query).
    """
    warnings: list[str] = []
    query_caps = query.capture_names()
    span_caps = (span_query or query).capture_names()
    for name, field in model.model_fields.items():
        marker = field.default
        cap_name = marker.name if isinstance(marker, _CaptureMarker) else name
        if isinstance(marker, _SourceMeta):
            if marker.capture not in span_caps:
                warnings.append(
                    f"field {name!r}: source_meta(capture={marker.capture!r}) "
                    f"but the query never captures {marker.capture!r}")
            continue
        if cap_name not in query_caps:
            warnings.append(
                f"field {name!r} feeds from capture {cap_name!r} which the "
                f"query never captures — it will always be missing")
            continue
        if record_mode:
            # captures are merged across matches sharing a record anchor, so
            # quantifier-vs-type checks do not apply
            continue
        target = _unwrap_optional(field.annotation)
        is_list = get_origin(target) is list
        quant = query.quantifier_for(cap_name)
        if is_list and quant not in ("*", "+"):
            warnings.append(
                f"field {name!r} is a list but capture {cap_name!r} is "
                f"not repeated (quantifier {quant!r}) — it will hold at most "
                f"one element")
        elif not is_list and quant in ("*", "+"):
            warnings.append(
                f"field {name!r} is scalar but capture {cap_name!r} is "
                f"repeated (quantifier {quant!r}) — extra captures are dropped")
    return warnings


# --------------------------------------------------------------------------
# Materialization core
# --------------------------------------------------------------------------

def _text_of(node: tree_sitter.Node) -> str:
    b = node.text
    if b is None:
        raise CoercionError(
            f"captured {node.type} node has no text (missing node?) at "
            f"{node.byte_range}")
    return b.decode("utf-8", "replace")


def build_kwargs(captures: dict[str, list[tree_sitter.Node]],
                 model: type[BaseModel],
                 source: bytes = b"") -> dict[str, Any]:
    """Map a capture dict onto model kwargs (raw text; pydantic coerces)."""
    kwargs: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        marker = field.default

        # source_meta injection
        if isinstance(marker, _SourceMeta):
            nodes = captures.get(marker.capture)
            if not nodes:
                raise CoercionError(
                    f"field {name!r}: source_meta(capture={marker.capture!r}) "
                    f"but the capture dict has no {marker.capture!r} — the "
                    f"span source is not being captured")
            node = nodes[0]
            target = _unwrap_optional(field.annotation)
            if target is int:
                kwargs[name] = node.start_point.row + 1
            else:
                kwargs[name] = Span.from_node(node)
            continue

        cap_name = marker.name if isinstance(marker, _CaptureMarker) else name
        nodes = captures.get(cap_name, [])

        target = _unwrap_optional(field.annotation)
        origin = get_origin(target)

        # missing capture
        if not nodes:
            if origin is list:
                kwargs[name] = []  # repeated capture, zero occurrences
                continue
            if not isinstance(marker, (_CaptureMarker, _SourceMeta)) \
                    and field.default is not PydanticUndefined:
                kwargs[name] = field.default
            continue  # otherwise: pydantic raises "field required" if needed

        if origin is list:
            kwargs[name] = [_text_of(n) for n in nodes]
        else:
            if len(nodes) > 1:
                raise AmbiguousCaptureError(
                    f"field {name!r} is scalar but capture {cap_name!r} "
                    f"matched {len(nodes)} nodes: "
                    f"{[_text_of(n)[:20] for n in nodes]!r} (nested "
                    f"structure with a colliding key?)")
            kwargs[name] = _text_of(nodes[0])
    return kwargs


def _warn(msg: str) -> None:
    print(f"  [binding-warning] {msg}", file=sys.stderr)


# --------------------------------------------------------------------------
# Two extraction modes
# --------------------------------------------------------------------------

def materialize_matches(query, tree: tree_sitter.Tree, into: type[BaseModel],
                        *, strict: bool = True) -> list:
    """Typed mode: run the query over the tree, build `into` instances."""
    from .dsl import Cursor
    compiled = query.compile(tree.language)
    for w in binding_warnings(query, into):
        _warn(w)
    cursor = Cursor(compiled, query._quant_maps or [], tree)

    results: list = []
    errors: list[tuple[int, str, object]] = []
    for m in cursor.matches():
        raw = {name: m.nodes(name) for name in set(m._caps)}
        try:
            kwargs = build_kwargs(raw, into, cursor._source)
            results.append(into(**kwargs))
        except ValidationError as e:
            errors.append((m.pi, f"pattern {m.pi}", e))
        except CoercionError as e:
            errors.append((m.pi, str(e), None))
    if errors and strict:
        raise ExtractionError(errors, into)
    return results


class ExtractionError(Exception):
    """One or more matches failed to materialize."""

    def __init__(self, errors: list, into: type):
        self.errors = errors
        self.into = into
        first = errors[0]
        detail = first[2] if (len(first) > 2 and first[2] is not None) \
            else first[1]
        lines = [
            f"{len(errors)} match(es) failed to materialize {into.__name__}:",
            f"  - {detail}",
        ]
        super().__init__("\n".join(lines))


def extract_records(tree: tree_sitter.Tree, record_query, field_query,
                    into: type[BaseModel], *,
                    record_capture: str = "record",
                    strict: bool = True) -> list:
    """Record mode: outer query finds record nodes; the inner query runs
    scoped to each record; captures are merged across the record's matches
    (order-independent, missing keys allowed) and materialized into `into`."""
    from .dsl import Cursor
    rec_compiled = record_query.compile(tree.language)
    fld_compiled = field_query.compile(tree.language)
    for w in binding_warnings(field_query, into, record_mode=True,
                              span_query=record_query):
        _warn(w)

    results: list = []
    errors: list[tuple[Any, str, object]] = []
    outer = Cursor(rec_compiled, record_query._quant_maps or [], tree)
    for rm in outer.matches():
        rec_nodes = rm.nodes(record_capture)
        if not rec_nodes:
            continue
        rec = rec_nodes[0]
        merged: dict[str, list[tree_sitter.Node]] = {}
        # seed source_meta captures with the record node so span fields work
        for fname, field in into.model_fields.items():
            if isinstance(field.default, _SourceMeta):
                merged.setdefault(field.default.capture, [rec])
        for fm in Cursor(fld_compiled, field_query._quant_maps or [], tree) \
                .matches_on(rec):
            for cname in set(fm._caps):
                merged.setdefault(cname, []).extend(fm.nodes(cname))
        try:
            kwargs = build_kwargs(merged, into)
            results.append(into(**kwargs))
        except ValidationError as e:
            errors.append((rec, f"pydantic ValidationError: {e.errors()}", e))
        except CoercionError as e:
            errors.append((rec, str(e), None))
    if errors and strict:
        raise ExtractionError(errors, into)
    return results
