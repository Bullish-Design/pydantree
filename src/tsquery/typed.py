"""tsquery.typed — model-only extraction (Product A, Phase 1 validated design).

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

Phase 4 (this session) integrates the node-schema (tscore): Jobs 1/3/4
(model↔grammar, value-shape derivation, capture↔type) and record-level
anchoring. The record value shape map is derived from the schema instead of
the hardcoded JSON v1 map — see `tsquery.shapes` and the `_schema` handling
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


class _Capture:
    """`= capture("left")` binds the field to CST field `left`. No-arg means
    the attr name IS the CST field name."""

    __slots__ = ("field",)

    def __init__(self, field: Optional[str] = None):
        self.field = field


class _SourceMeta:
    """`= source_meta()` injects the match anchor's span (int -> start line,
    Span -> full span). `source_meta(capture="x")` uses capture @x instead."""

    __slots__ = ("capture",)

    def __init__(self, capture: str = ANCHOR):
        self.capture = capture


def capture(field: Optional[str] = None) -> _Capture:
    return _Capture(field)


def source_meta(capture: str = ANCHOR) -> _SourceMeta:
    return _SourceMeta(capture)


class M:
    """The one structural declaration: the ancestor path of node kinds.

    M("module", "expression_statement", "assignment") -> anchored pattern
    (module (expression_statement (assignment ...))).

    record=True switches to key/value record semantics (see module docstring).
    """

    __slots__ = ("path", "record")

    def __init__(self, *path: str, record: bool = False):
        if not path:
            raise ValueError("M() needs at least one node kind")
        self.path = list(path)
        self.record = record


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


@dataclass
class _Derived:
    mode: str                           # "field" | "record"
    query: Optional[Query] = None       # field mode: the one query
    records: Optional[Query] = None     # record mode: outer query
    fields: Optional[Query] = None      # record mode: inner query
    bindings: dict = dc_field(default_factory=dict)
    record_kind: Optional[str] = None   # record mode: the record node kind
    pair_kind: Optional[str] = None     # record mode: the pair/key-value kind


def _unwrap_optional(t):
    origin = get_origin(t)
    if origin in (Union, types.UnionType):
        args = [a for a in get_args(t) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return t


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
    specs = [node(k) for k in m.path]
    cur = specs[-1]  # innermost node: captures + predicates go here

    for fname, f in model_cls.model_fields.items():
        b = bindings[fname]
        if b.span or b.capture is None:
            continue  # span field or derived field (default only)
        field_name = f.default.field if isinstance(f.default, _Capture) \
            and f.default.field else fname
        kind = _kind_from_metadata(f.metadata)
        k = kind.kinds[0] if kind else "_"
        cur.child(field=field_name,
                  node=node(k).capture(fname))
        for p in _predicates_for(fname, f.metadata):
            cur.where(p)

    cur.capture(ANCHOR)
    for s in reversed(specs[:-1]):
        cur = s.child(node=cur)
    q = Query(cur)
    return _Derived("field", q, bindings=bindings)


def _derive_record(model_cls, m: M, bindings) -> _Derived:
    from .dsl import node
    # outer: anchored path with the record node captured
    specs = [node(k) for k in m.path]
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
                    bindings=bindings)


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
        node-schema.json path/dict, a tscore.NodeSchema, or a tsquery.Language
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
        from .schema import schema_derive
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


class Language:
    """A tree_sitter.Language + an optionally-bound node-schema.

    `Language.load(lang, schema=...)` is the Phase-4 way to carry the schema
    next to the grammar; `validate_with(language=..., schema=...)` and
    `extract(..., schema=...)` also accept it directly. When a schema is
    bound it is registered under the language name so later calls that pass
    only the language find it (the "small registry" from the kickoff).
    """

    __slots__ = ("_lang", "_schema")

    def __init__(self, lang, schema=None):
        raw, schema = _resolve_language(lang, schema)
        self._lang = raw
        self._schema = schema
        if schema is not None:
            _SCHEMA_REGISTRY[self._lang.name] = schema

    @classmethod
    def load(cls, lang, schema=None) -> "Language":
        return cls(lang, schema)

    @property
    def schema(self):
        return self._schema

    @property
    def name(self) -> str:
        return self._lang.name

    @property
    def language(self) -> tree_sitter.Language:
        return self._lang


def _load_schema(schema) -> object | None:
    """Accept a node-schema.json path/dict, a tscore.NodeSchema, or None."""
    if schema is None:
        return None
    if hasattr(schema, "node_types"):          # already a NodeSchema
        return schema
    from tscore.schema import NodeSchema
    if isinstance(schema, (str, Path)):
        return NodeSchema.from_node_types_json(schema)
    if isinstance(schema, dict):
        return NodeSchema.from_list(schema.get("node_types", schema))
    raise TypeError(f"cannot build a node-schema from {type(schema)!r}")


def _resolve_language(language, schema=None):
    """Return (tree_sitter.Language, schema_or_None). Resolves the schema
    from (in order): the explicit `schema=` argument; a tsquery.Language
    wrapper; the registry keyed by language name."""
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
        _SCHEMA_REGISTRY[lang.name] = schema
    elif lang.name in _SCHEMA_REGISTRY:
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
                kwargs[fname] = f.default
            continue
        if b.is_list:
            kwargs[fname] = [_text_of(n) for n in nodes]
        else:
            if len(nodes) > 1:
                raise AmbiguousCaptureError(
                    f"field {fname!r} is scalar but capture {b.capture!r} "
                    f"matched {len(nodes)} nodes (nested key collision?)")
            kwargs[fname] = _text_of(nodes[0])
    return kwargs


def _extract_field(model_cls, tree, derived: _Derived, strict):
    from .dsl import Cursor
    q = derived.query.compile(tree.language)
    results: list = []
    errors: list = []
    for m in Cursor(q, derived.query._quant_maps or [], tree).matches():
        caps = {name: m.nodes(name) for name in set(m._caps)}
        try:
            results.append(model_cls(**_build_kwargs(model_cls, derived.bindings,
                                                     caps)))
        except ValidationError as e:
            errors.append((m, f"pydantic ValidationError: {e.errors()}"))
        except CoercionError as e:
            errors.append((m, str(e)))
    if errors and strict:
        raise _ExtractionError(errors, model_cls)
    return results


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
        try:
            kwargs = _record_kwargs(model_cls, derived, recs[0], tree,
                                    record_kind)
            if kwargs is not None:
                results.append(model_cls(**kwargs))
        except ValidationError as e:
            errors.append((recs[0], f"pydantic ValidationError: {e.errors()}"))
        except CoercionError as e:
            errors.append((recs[0], str(e)))
    if errors and strict:
        raise _ExtractionError(errors, model_cls)
    return results


class _ExtractionError(Exception):
    def __init__(self, errors, into):
        self.errors = errors
        self.into = into
        first = errors[0]
        super().__init__(
            f"{len(errors)} match(es) failed to materialize "
            f"{into.__name__}:\n  - {first[1]}")
