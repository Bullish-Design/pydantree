"""pydantree_sitter.typed — model-only extraction (Product A, Phase 1 validated design).

Mechanical port of `spike-a2/typed.py`: the OutputModel class IS the query.

    class Assignment(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str  = capture("left")        # attr name = capture name
        value: int = capture("right")
        line: int  = source_meta()

    rows = Assignment.extract(text, language=tree_sitter_python)

Record mode handles order-independent key/value documents:

    class Person(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        age: int
        ...

Phase 4 (this session) integrates the node-schema (pydantree_sitter): Jobs 1/3/4
(model↔grammar, value-shape derivation, capture↔type) and record-level
anchoring. The record value shape map is derived from the schema instead of
the hardcoded JSON v1 map — see `pydantree_sitter.shapes` and the `_schema` handling
below.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import ForwardRef
from dataclasses import dataclass, field as dc_field
from typing import Annotated, Optional, Union, get_args, get_origin

import pydantic
import tree_sitter
from pydantic import BaseModel, ValidationError
from pydantic.fields import PydanticUndefined
from pydantic._internal._model_construction import ModelMetaclass

from .dsl import QueryBuildError, Query  # noqa: F401  (re-exported surface)
from .materialize import (
    AmbiguousCaptureError,
    CoercionError,
    Span,
    _text_of,
)

ANCHOR = "__anchor__"
RECORD_CAP = "record"


# --------------------------------------------------------------------------
# Markers
# --------------------------------------------------------------------------

class Matches:
    """Annotated[str, Matches(re)] -> (#match? @cap re)."""

    __slots__ = ("re",)

    def __init__(self, re: str):
        self.re = re


class Eq:
    """Annotated[... , Eq(value)] -> (#eq? @cap value)."""

    __slots__ = ("value",)

    def __init__(self, value: str):
        self.value = value


class AnyOf:
    """Annotated[... , AnyOf(a, b, ...)] -> (#any-of? @cap a b ...)."""

    __slots__ = ("values",)

    def __init__(self, *values: str):
        self.values = values


class NodeKind:
    """Annotated[... , NodeKind("integer")] -> constrain the matched node kind.

    A tuple means alternation: NodeKind(("true", "false")) emits one pattern
    per kind, all capturing the same name (tree-sitter has no inline |)."""

    __slots__ = ("kinds",)

    def __init__(self, kinds):
        self.kinds = kinds if isinstance(kinds, tuple) else (kinds,)


class Unescaped:
    """Annotated[str, Unescaped()] — decode the grammar string literal's
    escape sequences (Phase 5 polish; JSON first: \\n, \\t, \\", \\\\,
    \\uXXXX — exactly what the json/cfg grammars' escape_sequence rules
    produce). The captured node must be a string WRAPPER's content (the
    schema check enforces a string-wrapper shape); the decode is applied to
    the captured text at materialization.

    NOTE: this is new annotation vocabulary — the Phase-4 surface is frozen;
    treat it as a go-with-changes finding, not a license to expand.
    """

    __slots__ = ()

    def __init__(self):
        pass


def _has_unescaped(metadata) -> bool:
    return any(m.__class__.__name__ == "Unescaped" for m in metadata)


def _unescape_json_string(text: str) -> str:
    """Decode a grammar string literal's content (JSON escape syntax first:
    \\n \\t \\" \\\\ \\uXXXX — the json/cfg escape_sequence rules). Accepts
    either the string WRAPPER's full text (with quotes: `"A\nB"` — the
    Unescaped() shape captures the wrapper wholesale so escapes can't split
    across string_content pieces) or the bare content. Falls back to a manual
    decode when the strict JSON round-trip fails (a grammar lenient about raw
    newlines)."""
    import json as _json
    try:
        if text.startswith('"') and text.endswith('"') and len(text) >= 2:
            return _json.loads(text)
        return _json.loads('"' + text + '"')
    except ValueError:
        pass
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        text = text[1:-1]
    out: list[str] = []
    i = 0
    mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"',
               "\\": "\\", "b": "\b", "f": "\f", "/": "/"}
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
                continue
            if nxt == "u" and i + 5 <= len(text):
                try:
                    out.append(chr(int(text[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            out.append(text[i])
            i += 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


class _Capture:
    """`= capture("left")` binds the field to CST field `left`. No-arg means
    the attr name IS the CST field name."""

    __slots__ = ("field",)

    def __init__(self, field: Optional[str] = None):
        self.field = field


class _CaptureKind:
    """`= capture_kind("code_span")` binds the field to a CHILD BY NODE KIND
    (Phase-6.5, surfaced by the real markdown grammars — they use positional
    children, not CST fields, so the field-keyed `capture()` cannot name
    them). The emitted pattern is `(anchor (code_span) @field)` — the
    capture's kind is checked against the anchor's possible children (Job 1)
    and the field type against the kind's own types (Job 4)."""

    __slots__ = ("kind",)

    def __init__(self, kind: str):
        self.kind = kind


class _SourceMeta:
    """`= source_meta()` injects the match anchor's span (int -> start line,
    Span -> full span). `source_meta(capture="x")` uses capture @x instead."""

    __slots__ = ("capture",)

    def __init__(self, capture: str = ANCHOR):
        self.capture = capture


def capture(field: Optional[str] = None) -> _Capture:
    return _Capture(field)


def capture_kind(kind: str) -> _CaptureKind:
    """`= capture_kind("code_span")` — capture a CHILD by node kind (for
    grammars that use positional children — real markdown's inline elements
    and fenced-code children have no CST fields)."""
    return _CaptureKind(kind)


def source_meta(capture: str = ANCHOR) -> _SourceMeta:
    return _SourceMeta(capture)


class M:
    """The one structural declaration: the ancestor path of node kinds.

    M("module", "expression_statement", "assignment") -> anchored pattern
    (module (expression_statement (assignment ...))).

    A `"..."` element (Phase 5) matches ANY depth between the kinds it
    separates — descendant matching: M("module", ..., "assignment") is
    every assignment anywhere under a module. Implemented by walking the
    match anchor's ancestors at materialization (the `#has-ancestor?`
    assessment: it cannot express the anchor's own ancestor constraint in a
    single pattern and cannot bound depth — the walk is exact and handles
    any number of gaps); Job 1 checks the path against the schema as a
    possible descent (child chain) with possible-descendant checks across
    the gaps.

    record=True switches to key/value record semantics (see module docstring).
    """

    __slots__ = ("path", "record")

    def __init__(self, *path: str, record: bool = False):
        if not path:
            raise ValueError("M() needs at least one node kind")
        # the '...' descendant gap: accept the Python Ellipsis literal OR the
        # string "..." (normalize to the string)
        path = [p if p is not Ellipsis and p != "..." else "..."
                for p in path]
        if path[0] == "..." or path[-1] == "...":
            raise ValueError(
                "M(): '...' must sit BETWEEN node kinds (a leading/trailing "
                "gap is meaningless)")
        self.path = list(path)
        self.record = record


def _split_path(path: list[str]) -> tuple[list[str], list[str]]:
    """Split an M() path on the LAST '...' into (prefix, suffix). The suffix
    is the direct-child chain ending at the anchor (what the emitted query
    nests); the prefix is enforced by walking the anchor's ancestors at
    materialization. No '...' -> ([] , path)."""
    try:
        idx = len(path) - 1 - path[::-1].index("...")
    except ValueError:
        return [], path
    return path[:idx], path[idx + 1:]


class UnsupportedShapeError(CoercionError):
    """A pydantic type has no value-shape mapping in the bound grammar."""


# --------------------------------------------------------------------------
# SchemaBindError — a schema check failed (Job 1/3/4)
# --------------------------------------------------------------------------

class SchemaCheckError(CoercionError):
    """A model↔grammar or capture↔type check failed against the node-schema.

    Raised at `validate_with(language, schema=...)` or at class creation when
    a schema is bound — BEFORE any text is parsed. Carries the schema entry
    (node kind, field, supertype) that the model conflicts with."""

    def __init__(self, message: str, *, schema_entry: str | None = None,
                 model: type | None = None):
        self.schema_entry = schema_entry
        self.model = model
        super().__init__(message)


# --------------------------------------------------------------------------
# Derivation
# --------------------------------------------------------------------------

@dataclass
class _Binding:
    """Resolved field binding (built at class creation)."""
    capture: Optional[str] = None       # capture name feeding this field
    span: Optional[str] = None          # anchor capture for source_meta
    is_list: bool = False
    node_kinds: tuple = ()              # NodeKind override (or derived)
    kinds_derived: bool = False         # kinds came from the schema, not NodeKind
    has_predicate: bool = False         # record-mode: absence filters the record
    nested: Optional[type] = None       # field type is another OutputModel
    kind_capture: Optional[str] = None  # Phase-6.5: capture a CHILD BY KIND


@dataclass
class _Derived:
    mode: str                           # "field" | "record"
    query: Optional[Query] = None       # field mode: the one query
    records: Optional[Query] = None     # record mode: outer query
    fields: Optional[Query] = None      # record mode: inner query
    bindings: dict = dc_field(default_factory=dict)
    record_kind: Optional[str] = None   # record mode: the record node kind
    pair_kind: Optional[str] = None     # record mode: the pair/key-value kind
    match_path: Optional[list] = None   # the M() path when it has '...' gaps


def _unwrap_optional(t):
    origin = get_origin(t)
    if origin in (Union, types.UnionType):
        args = [a for a in get_args(t) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return t


def _is_optional(t) -> bool:
    """Is `None` among the annotation's union members (the type is
    Optional)? Phase 6.5: a field-mode capture with an Optional type is
    query-optional — the derived pattern emits `?` so matches without the
    field still materialize (None), instead of silently excluding them."""
    origin = get_origin(t)
    if origin in (Union, types.UnionType):
        return any(a is type(None) for a in get_args(t))
    return False


def _field_is_query_optional(f) -> bool:
    """A field-mode capture is query-optional iff the model can materialize
    WITHOUT the field: an Optional annotation, or a REAL default. A
    `= capture(...)` / `= capture_kind(...)` / `= source_meta()` marker is NOT
    a default (pydantic's `is_required()` treats any default as non-required,
    so the marker would wrongly make `port: int = capture("arg")` optional).
    Phase 8: `_CaptureKind` was missing from the marker tuple — every
    capture_kind field emitted `?` (required capture_kind children matched
    vacuously, then failed materialization with "field required"; surfaced
    over real bash's positional heredoc children)."""
    if _is_optional(f.annotation):
        return True
    d = f.default
    return d is not PydanticUndefined and not isinstance(
        d, (_Capture, _CaptureKind, _SourceMeta))


def _kind_from_metadata(metadata) -> Optional[NodeKind]:
    for m in metadata:
        if isinstance(m, NodeKind):
            return m
    return None


def _predicates_for(cap_name: str, metadata) -> list:
    from .dsl import cap
    preds = []
    for m in metadata:
        if isinstance(m, Matches):
            preds.append(cap(cap_name).matches(m.re))
        elif isinstance(m, Eq):
            preds.append(cap(cap_name).eq(m.value))
        elif isinstance(m, AnyOf):
            preds.append(cap(cap_name).any_of(*m.values))
    return preds


def _derive(model_cls) -> _Derived:
    m: M = model_cls.__match__
    bindings: dict[str, _Binding] = {}
    for fname, f in model_cls.model_fields.items():
        if isinstance(f.annotation, ForwardRef) or \
                not isinstance(f.annotation, type) and \
                get_origin(f.annotation) is None:
            raise CoercionError(
                f"field {fname!r}: annotation {f.annotation!r} could not be "
                f"resolved (pydantic left a ForwardRef). This usually means a "
                f"name in the annotation (e.g. Annotated, or a marker class) "
                f"is not importable in the module where {model_cls.__name__} "
                f"is defined.")
        d = f.default
        if isinstance(d, _SourceMeta):
            bindings[fname] = _Binding(span=d.capture)
            continue
        if m.record:
            # capture name = the record key (attr name, or capture("key") override)
            key = d.field if isinstance(d, _Capture) and d.field else fname
            bindings[fname] = _Binding(capture=key)
        elif isinstance(d, _CaptureKind):
            bindings[fname] = _Binding(capture=fname, kind_capture=d.kind)
        else:
            # field mode: a capture exists ONLY if the user wrote = capture(...)
            if isinstance(d, _Capture):
                bindings[fname] = _Binding(capture=fname)
            else:
                bindings[fname] = _Binding(capture=None)  # derived field
        target = _unwrap_optional(f.annotation)
        bindings[fname].is_list = get_origin(target) is list
        kind = _kind_from_metadata(f.metadata)
        if kind is not None:
            bindings[fname].node_kinds = kind.kinds
        bindings[fname].has_predicate = any(
            isinstance(x, (Matches, Eq, AnyOf)) for x in f.metadata)
        nested = _unwrap_optional(f.annotation)
        if isinstance(nested, type) and issubclass(nested, OutputModel):
            bindings[fname].nested = nested

    if m.record:
        return _derive_record(model_cls, m, bindings)
    return _derive_field(model_cls, m, bindings)


def _derive_field(model_cls, m: M, bindings) -> _Derived:
    from .dsl import node
    _prefix, suffix = _split_path(m.path)
    specs = [node(k) for k in suffix]
    cur = specs[-1]  # innermost node: captures + predicates go here

    for fname, f in model_cls.model_fields.items():
        b = bindings[fname]
        if b.span or b.capture is None:
            continue  # span field or derived field (default only)
        field_name = f.default.field if isinstance(f.default, _Capture) \
            and f.default.field else fname
        kind = _kind_from_metadata(f.metadata)
        k = kind.kinds[0] if kind else "_"
        # a capture the model can materialize WITHOUT the field (an Optional
        # type or a REAL default) is query-optional: `?` matches both shapes —
        # the field present (captured) and absent (the match still succeeds,
        # the binding falls back to the default / None). This fixes the
        # Phase-6 finding: `return_type: str | None = capture(...)` used to
        # emit `return_type:(_)` and silently exclude every node without the
        # field (real rust `fn no_return() {}`).
        optional = _field_is_query_optional(f)
        if b.kind_capture is not None:
            # a child-by-kind capture (markdown's positional children)
            cur.child(node=node(b.kind_capture).capture(fname),
                      quant="?" if optional else "")
        else:
            cur.child(field=field_name,
                      node=node(k).capture(fname),
                      quant="?" if optional else "")
        for p in _predicates_for(fname, f.metadata):
            cur.where(p)

    cur.capture(ANCHOR)
    for s in reversed(specs[:-1]):
        cur = s.child(node=cur)
    q = Query(cur)
    return _Derived("field", q, bindings=bindings,
                    match_path=m.path if "..." in m.path else None)


def _derive_record(model_cls, m: M, bindings) -> _Derived:
    from .dsl import node
    # outer: anchored path with the record node captured (the suffix chain;
    # a '...' prefix is enforced by the ancestor walk at materialization)
    _prefix, suffix = _split_path(m.path)
    specs = [node(k) for k in suffix]
    cur = specs[-1].capture(RECORD_CAP)
    for s in reversed(specs[:-1]):
        cur = s.child(node=cur)

    # inner: one pattern set per capture field (key eq -> value shape)
    patterns: list = []
    for fname, f in model_cls.model_fields.items():
        b = bindings[fname]
        if b.span:
            continue
        if b.capture is None:
            continue
        key = b.capture
        for vs in _value_specs(f.annotation, key, f.metadata):
            spec = (node("pair")
                    .child(field="key",
                           node=node("string")
                           .child(node("string_content").capture("key")))
                    .child(field="value", node=vs)
                    .where(_dsl_cap("key").eq(key)))
            for p in _predicates_for(key, f.metadata):
                spec.where(p)
            patterns.append(spec)

    return _Derived(mode="record",
                    query=None,
                    records=Query(cur),
                    fields=Query(*patterns),
                    bindings=bindings,
                    match_path=m.path if "..." in m.path else None)


def _match_ancestor_path(node, path: list[str]) -> bool:
    """Does the anchor's ancestor chain satisfy the M() path, with '...'
    allowing any depth between the kinds it separates? Consumes path
    elements right-to-left while walking the anchor's parents; a gap lets
    intermediate ancestors pass through. The anchor's own kind (path[-1]) is
    already guaranteed by the query."""
    ptr = len(path) - 2
    gap = False
    parent = node.parent
    while parent is not None:
        if ptr >= 0 and path[ptr] == "...":
            ptr -= 1
            gap = True
            continue
        if ptr < 0:
            return True
        if parent.type == path[ptr]:
            ptr -= 1
            gap = False
        elif not gap:
            return False
        parent = parent.parent
    return ptr < 0


def _dsl_cap(name: str):
    from .dsl import cap
    return cap(name)


# --------------------------------------------------------------------------
# value-shape derivation (Phase 4: schema-derived; falls back to the
# hardcoded JSON v1 map when no schema is bound — the Phase-1 behavior)
# --------------------------------------------------------------------------

def _value_specs(target, cap_name: str, metadata) -> list:
    """Value-node shape for a record-mode field (JSON grammar v1).

    Returns one NodeSpec per emitted pattern (bool -> 2). Nested OutputModel
    fields capture the value node wholesale (wildcard)."""
    from .dsl import node
    base = _unwrap_optional(target)
    if isinstance(base, type) and base is not type(None) \
            and hasattr(base, "_derived_cache"):
        return [node(None).capture(cap_name)]   # (_) @field
    kind = _kind_from_metadata(metadata)
    if kind is not None:
        return [node(k).capture(cap_name) for k in kind.kinds]
    if _has_unescaped(metadata):
        # Unescaped(): capture the string WRAPPER wholesale (escaped strings
        # split across string_content pieces; the wrapper decodes as one value)
        return [node("string").capture(cap_name)]
    base = _unwrap_optional(target)
    origin = get_origin(base)
    if origin is list:
        elem = get_args(base)[0] if get_args(base) else str
        elem = _unwrap_optional(elem)
        if elem is str:
            return [node("array").child(
                node("string").child(node("string_content").capture(cap_name)))]
        if elem in (int, float):
            return [node("array").child(node("number").capture(cap_name))]
        raise UnsupportedShapeError(
            f"list[{getattr(elem, '__name__', elem)}] has no JSON v1 shape "
            f"(use Annotated[..., NodeKind(...)] to declare it)")
    if base is str:
        return [node("string").child(node("string_content").capture(cap_name))]
    if base in (int, float):
        return [node("number").capture(cap_name)]
    if base is bool:
        return [node("true").capture(cap_name),
                node("false").capture(cap_name)]
    raise UnsupportedShapeError(
        f"field type {base!r} has no JSON v1 shape (use "
        f"Annotated[..., NodeKind(...)])")


# --------------------------------------------------------------------------
# The metaclass: derive + validate at class creation
# --------------------------------------------------------------------------

class DerivingMeta(ModelMetaclass):
    def __new__(mcls, name, bases, ns, **kwargs):
        cls = super().__new__(mcls, name, bases, ns, **kwargs)
        if ns.get("__match__") is not None:
            cls._derived_cache = _derive(cls)
            cls._binding_warnings = _binding_warnings(cls)
        return cls


def _binding_warnings(model_cls) -> list[str]:
    warnings: list[str] = []
    derived = model_cls._derived_cache
    for fname, b in derived.bindings.items():
        f = model_cls.model_fields[fname]
        if b.span:
            continue
        if b.capture is None:
            if f.is_required():
                warnings.append(
                    f"field {fname!r} has no capture binding and no default — "
                    f"it will always raise ValidationError (add = capture(...) "
                    f"or a default)")
    return warnings


# --------------------------------------------------------------------------
# OutputModel: the public surface
# --------------------------------------------------------------------------

class OutputModel(BaseModel, metaclass=DerivingMeta):
    """A typed extraction target. The class IS the query declaration."""

    __match__ = None

    # -- entry points ------------------------------------------------------

    @classmethod
    def extract(cls, text, language=None, *, strict: bool = True,
                schema=None) -> list:
        """Extract typed rows from `text`. With a node-schema (a
        node-schema.json path/dict, a pydantree_sitter.NodeSchema, or a pydantree_sitter.Language
        carrying one), the Jobs 1/3/4 checks run and the query is rebuilt for
        the grammar (derived value shapes, record-level anchoring, derived
        kind constraints) before any match is materialized."""
        lang, schema = _resolve_language(language, schema)
        derived = cls._resolve_derived(schema, lang.name)
        if not isinstance(text, bytes):
            text = text.encode("utf-8")
        tree = tree_sitter.Parser(lang).parse(text)
        return cls._extract_tree(tree, derived, strict=strict)

    @classmethod
    def extract_tree(cls, tree: tree_sitter.Tree, *, strict: bool = True,
                     schema=None) -> list:
        lang_name = getattr(tree.language, "name", None)
        derived = cls._resolve_derived(schema, lang_name)
        return cls._extract_tree(tree, derived, strict=strict)

    @classmethod
    def _extract_tree(cls, tree, derived: _Derived, *, strict: bool) -> list:
        for w in cls._binding_warnings:
            print(f"  [model-warning] {cls.__name__}: {w}", file=sys.stderr)
        if derived.mode == "record":
            return _extract_record(cls, tree, derived, strict, derived.record_kind)
        return _extract_field(cls, tree, derived, strict)

    @classmethod
    def _resolve_derived(cls, schema, lang_name: str | None) -> _Derived:
        """The derived query for the bound schema (cached per grammar), or the
        base schema-less derivation when no schema is in play."""
        if schema is None:
            return cls._derived_cache
        from .model_schema import schema_derive
        return schema_derive(cls, schema, lang_name or "?")

    @classmethod
    def compiled_source(cls, *, schema=None, language=None) -> str:
        """The derived .scm (for diagnostics/tests). With a schema bound,
        shows the schema-rebuilt query."""
        if schema is None and language is None:
            d = cls._derived_cache
            if d.mode == "record":
                return d.records.source + "\n\n-- inner --\n\n" + d.fields.source
            return d.query.source
        if language is not None:
            lang, schema = _resolve_language(language, schema)
            d = cls._resolve_derived(schema, lang.name)
        else:
            d = cls._resolve_derived(schema, None)
        if d.mode == "record":
            return d.records.source + "\n\n-- inner --\n\n" + d.fields.source
        return d.query.source

    @classmethod
    def validate_with(cls, language, schema=None) -> None:
        """Compile the derived query against a grammar now (import-time-ish
        grammar validation, since node kinds/fields are grammar-specific).

        With a node-schema, ALSO runs the model↔grammar and capture↔type
        checks (Jobs 1/3/4) and rebuilds the query for the grammar — every
        planted Phase-4 failure surfaces here, before any text is parsed.
        """
        lang, schema = _resolve_language(language, schema)
        d = cls._resolve_derived(schema, lang.name)
        if d.mode == "record":
            d.records.compile(lang)
            d.fields.compile(lang)
        else:
            d.query.compile(lang)


# --------------------------------------------------------------------------
# language resolution + the schema registry (Phase 4)
# --------------------------------------------------------------------------

_SCHEMA_REGISTRY: dict[str, object] = {}


def _maybe_register(name: str | None, schema: object) -> None:
    """The opt-in name-keyed registry (Phase 6: made explicit). A language
    with NO name must not be registered — the Phase-6 leak: wheel-loaded
    languages report `name=None`, so a bundle's schema registered under None
    silently applied to EVERY schema-less consumer of any nameless language.
    Per-Language-instance binding is the default; registering is the opt-in
    convenience for callers who pass bare languages later."""
    if name is None:
        return
    _SCHEMA_REGISTRY[name] = schema


class Language:
    """A tree_sitter.Language + an optionally-bound node-schema.

    `Language.load(lang, schema=...)` is the Phase-4 way to carry the schema
    next to the grammar; `validate_with(language=..., schema=...)` and
    `extract(..., schema=...)` also accept it directly. The schema is bound
    to THIS instance (Phase 6: the name-keyed global registry is gone — a
    bound schema previously leaked into every later schema-less consumer of
    the same language name, and a nameless language leaked into all of them).
    `register=True` opts into the name-keyed convenience: the schema is also
    placed in the registry so LATER calls passing the BARE language (not this
    wrapper) find it. Requires a named language (a nameless one is refused).
    """

    __slots__ = ("_lang", "_schema")

    def __init__(self, lang, schema=None, *, register: bool = False):
        raw, schema = _resolve_language(lang, schema, register=register)
        self._lang = raw
        self._schema = schema

    @classmethod
    def load(cls, lang, schema=None, *, register: bool = False) -> "Language":
        return cls(lang, schema, register=register)

    @classmethod
    def load_bundle(cls, dir) -> "Language":
        """Consume a packaged grammar bundle (BuildResult.package() output)
        in one call: grammar.so + node-schema.json + metadata via pydantree_sitter's
        shared loader — no pydantree_sitter_grammar in the process, checks bound."""
        from pydantree_sitter.loader import load_bundle as _load_bundle
        bundle = _load_bundle(dir)
        return cls(bundle.language, schema=bundle.schema)

    @property
    def schema(self):
        return self._schema

    @property
    def name(self) -> str:
        return self._lang.name

    @property
    def language(self) -> tree_sitter.Language:
        return self._lang

    # -- parsing (Phase 5: incremental reparse) ----------------------------

    def parse(self, source: str | bytes) -> tree_sitter.Tree:
        """Parse `source` from scratch with the bound grammar."""
        if isinstance(source, str):
            source = source.encode("utf-8")
        return tree_sitter.Parser(self._lang).parse(source)

    def reparse(self, old_tree: tree_sitter.Tree, source: str | bytes,
                old_source: str | bytes | None = None) -> tree_sitter.Tree:
        """Incremental reparse (the 0.26 API, wrapped): ``Parser.parse(new
        source, old_tree)``. The binding applies the edit internally from the
        old tree's byte ranges — callers just re-give the full new source
        (CONCEPT §5.6: 'available, we do not wrap it' — Phase 5 wraps it).

        Returns a new tree whose unchanged subtrees are shared with
        `old_tree` (tree-sitter's incremental machinery).
        """
        if isinstance(source, str):
            source = source.encode("utf-8")
        return tree_sitter.Parser(self._lang).parse(source, old_tree)


def _load_schema(schema) -> object | None:
    """Accept a node-schema.json path/dict, a pydantree_sitter.NodeSchema, or None."""
    if schema is None:
        return None
    if hasattr(schema, "node_types"):          # already a NodeSchema
        return schema
    from pydantree_sitter.schema import NodeSchema
    if isinstance(schema, (str, Path)):
        return NodeSchema.from_node_types_json(schema)
    if isinstance(schema, dict):
        return NodeSchema.from_list(schema.get("node_types", schema))
    raise TypeError(f"cannot build a node-schema from {type(schema)!r}")


def _resolve_language(language, schema=None, *, register: bool = False):
    """Return (tree_sitter.Language, schema_or_None). Resolves the schema
    from (in order): the explicit `schema=` argument; a pydantree_sitter.Language
    wrapper's bound schema; the opt-in registry keyed by language name (only
    entries placed via Language.load(..., register=True) — Phase 6: the
    automatic name-keyed lookup is gone, so a schema bound for one consumer
    can never silently apply to a later schema-less consumer of the same
    language, and a nameless language can never collide)."""
    if isinstance(language, Language):
        schema = schema if schema is not None else language._schema
        language = language._lang
    if isinstance(language, tree_sitter.Language):
        lang = language
    elif callable(language):                   # tree_sitter_python.language
        lang = tree_sitter.Language(language())
    elif hasattr(language, "language") and callable(language.language):
        lang = tree_sitter.Language(language.language())
    else:
        lang = tree_sitter.Language(language)  # a bare PyCapsule
    if schema is not None:
        schema = _load_schema(schema)
        if register:
            _maybe_register(lang.name, schema)
    elif lang.name is not None and lang.name in _SCHEMA_REGISTRY:
        schema = _SCHEMA_REGISTRY[lang.name]
    return lang, schema


# --------------------------------------------------------------------------
# Materialization (fresh copy of the spike-a semantics, keyed on bindings)
# --------------------------------------------------------------------------

def _build_kwargs(model_cls, bindings, captures, anchor_nodes=None):
    kwargs: dict = {}
    for fname, f in model_cls.model_fields.items():
        b = bindings[fname]
        if b.span:
            nodes = captures.get(b.span) or []
            if not nodes:
                raise CoercionError(
                    f"field {fname!r}: source_meta(capture={b.span!r}) but no "
                    f"such capture in the match")
            node = nodes[0]
            target = _unwrap_optional(f.annotation)
            if target is int:
                kwargs[fname] = node.start_point.row + 1
            else:
                kwargs[fname] = Span.from_node(node)
            continue
        if b.capture is None:
            if not f.is_required():
                kwargs[fname] = f.default
            continue  # required-with-no-binding -> pydantic raises
        nodes = captures.get(b.capture, [])
        if b.nested is not None:
            # values are already materialized OutputModel instances
            if not nodes:
                if b.is_list:
                    kwargs[fname] = []
                elif not f.is_required():
                    kwargs[fname] = f.default
                continue
            kwargs[fname] = nodes if b.is_list else nodes[0]
            continue
        if not nodes:
            if b.is_list:
                kwargs[fname] = []
            elif not f.is_required():
                # a marker default (= capture(...) / capture_kind(...)) means
                # "absent -> None", not the marker object
                kwargs[fname] = None if isinstance(
                    f.default, (_Capture, _CaptureKind)) else f.default
            elif _is_optional(f.annotation):
                kwargs[fname] = None
            continue
        if b.is_list:
            if _has_unescaped(f.metadata):
                kwargs[fname] = [_unescape_json_string(_text_of(n))
                                 for n in nodes]
            else:
                kwargs[fname] = [_text_of(n) for n in nodes]
        else:
            if len(nodes) > 1:
                raise AmbiguousCaptureError(
                    f"field {fname!r} is scalar but capture {b.capture!r} "
                    f"matched {len(nodes)} nodes (nested key collision?)")
            text = _text_of(nodes[0])
            kwargs[fname] = _unescape_json_string(text) \
                if _has_unescaped(f.metadata) else text
    return kwargs


def _extract_field(model_cls, tree, derived: _Derived, strict):
    from .dsl import Cursor
    q = derived.query.compile(tree.language)
    results: list = []
    errors: list = []
    has_lists = any(b.is_list for b in derived.bindings.values())
    if has_lists:
        # field-mode lists (Phase 5): one match per repeated-field occurrence
        # sharing the same anchor — merge by anchor node id (the record-mode
        # anchor-merge machinery, reused), dedup scalar captures by node id.
        groups: dict = {}
        order: list = []
        for m in Cursor(q, derived.query._quant_maps or [], tree).matches():
            caps = {name: m.nodes(name) for name in set(m._caps)}
            anc = caps.get(ANCHOR)
            if not anc:
                groups.setdefault(0, []).append(caps)
                order.append(0)
                continue
            g = groups.setdefault(anc[0].id, [])
            if anc[0].id not in order:
                order.append(anc[0].id)
            g.append(caps)
        for anc_id in order:
            merged: dict = {}
            for caps in groups[anc_id]:
                for name, nodes in caps.items():
                    merged.setdefault(name, []).extend(nodes)
            for fname, b in derived.bindings.items():
                if b.span or b.is_list:
                    continue
                nodes = merged.get(b.capture, [])
                if len(nodes) > 1:
                    merged[b.capture] = _dedup_by_id(nodes)
            try:
                results.append(model_cls(**
                                          _build_kwargs(model_cls,
                                                        derived.bindings,
                                                        merged)))
            except ValidationError as e:
                errors.append(_failure(None,
                                       f"pydantic ValidationError: {e.errors()}",
                                       anchor=_first_anchor(merged),
                                       pydantic_errors=e.errors()))
            except CoercionError as e:
                errors.append(_failure(None, str(e),
                                       anchor=_first_anchor(merged)))
        if errors and strict:
            raise ExtractionError(errors, model_cls)
        return results
    for m in Cursor(q, derived.query._quant_maps or [], tree).matches():
        caps = {name: m.nodes(name) for name in set(m._caps)}
        if derived.match_path is not None:
            anc = caps.get(ANCHOR)
            if not anc or not _match_ancestor_path(anc[0], derived.match_path):
                continue  # a '...' path: the anchor's ancestors miss the chain
        try:
            results.append(model_cls(**_build_kwargs(model_cls, derived.bindings,
                                                     caps)))
        except ValidationError as e:
            errors.append(_failure(m, f"pydantic ValidationError: {e.errors()}",
                                   pydantic_errors=e.errors()))
        except CoercionError as e:
            errors.append(_failure(m, str(e)))
    if errors and strict:
        raise ExtractionError(errors, model_cls)
    return results


def _dedup_by_id(nodes) -> list:
    """Dedupe capture nodes by their stable C node id (across matches the
    bindings may hand out distinct Python wrappers for the same node)."""
    seen: set = set()
    out = []
    for n in nodes:
        if n.id not in seen:
            seen.add(n.id)
            out.append(n)
    return out


def _first_anchor(caps: dict):
    return (caps.get(ANCHOR) or caps.get(RECORD_CAP) or [None])[0]


def _record_kwargs(model_cls, derived: _Derived, rec, tree,
                  record_kind=None):
    """Merge a record node's field captures into model kwargs (incl. nested).

    With record-level anchoring (`record_kind` set — the schema-derived
    inner query names the record node and captures @__anchor__), only matches
    anchored at `rec` itself contribute: pairs inside NESTED record nodes are
    dropped. This kills the AmbiguousCaptureError nested-collision class
    (spike-a §3) at the query level instead of flagging it at extract.
    """
    from .dsl import Cursor
    fld_q = derived.fields.compile(tree.language)
    merged: dict[str, list] = {}
    for fm in Cursor(fld_q, derived.fields._quant_maps or [], tree) \
            .matches_on(rec):
        if record_kind is not None:
            anc = fm.nodes(ANCHOR)
            if not anc or anc[0].id != rec.id:
                continue  # a nested record's pair — not a record-level key
        for cname in set(fm._caps):
            if cname == ANCHOR:
                continue
            merged.setdefault(cname, []).extend(fm.nodes(cname))
    # record-level predicate semantics: a predicate field that did not match
    # (absent) filters the WHOLE record, like the field-mode query engine.
    filtered = any(
        b.capture is not None and b.has_predicate and not merged.get(b.capture)
        for b in derived.bindings.values())
    if filtered:
        return None
    merged.setdefault(ANCHOR, [rec])
    # nested OutputModel fields: materialize the value node with the nested
    # model's own record machinery
    for fname, b in derived.bindings.items():
        if b.nested is None:
            continue
        nodes = merged.get(b.capture, [])
        out = []
        for n in nodes:
            inner = _record_kwargs(b.nested, b.nested._derived_cache, n, tree,
                                   record_kind)
            if inner is not None:
                out.append(b.nested(**inner))
        merged[b.capture] = out
    return _build_kwargs(model_cls, derived.bindings, merged)


def _extract_record(model_cls, tree, derived: _Derived, strict, record_kind=None):
    from .dsl import Cursor
    rec_q = derived.records.compile(tree.language)
    results: list = []
    errors: list = []
    for rm in Cursor(rec_q, derived.records._quant_maps or [], tree).matches():
        recs = rm.nodes(RECORD_CAP)
        if not recs:
            continue
        if derived.match_path is not None and \
                not _match_ancestor_path(recs[0], derived.match_path):
            continue  # a '...' path: the record's ancestors miss the chain
        try:
            kwargs = _record_kwargs(model_cls, derived, recs[0], tree,
                                    record_kind)
            if kwargs is not None:
                results.append(model_cls(**kwargs))
        except ValidationError as e:
            errors.append(_failure(rm, f"pydantic ValidationError: {e.errors()}",
                                   anchor=recs[0], pydantic_errors=e.errors()))
        except CoercionError as e:
            errors.append(_failure(rm, str(e), anchor=recs[0]))
    if errors and strict:
        raise ExtractionError(errors, model_cls)
    return results


@dataclass
class MatchFailure:
    """One failed match, with per-match detail (spike-a §4 gap 1, Phase 5).

    Carries the match's pattern index, its anchor node (the match site), the
    Span-typed source range, the offending snippet, and the structured
    pydantic errors when the failure was a validation error — so an
    ExtractionError can report every failing match, not just the first.
    """

    pattern: int
    anchor: object | None
    span: "Span | None"
    snippet: str
    detail: str
    pydantic_errors: list | None = None


class ExtractionError(Exception):
    """One or more matches failed to materialize; `.failures` carries
    per-match detail (pattern index, anchor span, snippet, pydantic errors)
    instead of only the first error (spike-a §4 gap 1)."""

    def __init__(self, failures: list[MatchFailure], into):
        self.failures = failures
        self.into = into
        lines = [
            f"{len(failures)} match(es) failed to materialize "
            f"{into.__name__}:"]
        for f in failures:
            where = f"line {f.span.line}" if f.span is not None else "?"
            lines.append(
                f"  - pattern {f.pattern} @ {where} {f.snippet!r}: {f.detail}")
        super().__init__("\n".join(lines))


# compatibility alias (the pre-Phase-5 name; tests/older code may import it)
_ExtractionError = ExtractionError


def _failure(match, detail: str, *, anchor=None,
             pydantic_errors=None) -> MatchFailure:
    """Build a MatchFailure from a MatchView (or a record node anchor)."""
    from .materialize import Span
    node = anchor
    if node is None:
        ns = match.nodes(ANCHOR) or match.nodes(RECORD_CAP)
        node = ns[0] if ns else None
    span = Span.from_node(node) if node is not None else None
    snippet = span.text if span is not None else ""
    return MatchFailure(pattern=getattr(match, "pi", 0), anchor=node,
                        span=span, snippet=snippet, detail=detail,
                        pydantic_errors=pydantic_errors)
