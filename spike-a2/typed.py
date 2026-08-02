"""Model-only extraction (spike-a2): the OutputModel class IS the query.

The user-facing surface is just the model:

    class Assignment(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str  = capture("left")        # attr name = capture name
        value: int = capture("right")
        line: int  = source_meta()

    rows = Assignment.extract(text, language=tree_sitter_python)

Everything else (the .scm, the query, the binding) is derived and emitted
internally. Field-name == capture-name, pydantic type == coercion + value
shape, Optional/default == missing handling, list[X] == repeated capture,
source_meta() == span injection, Annotated metadata == predicates (#match?,
#eq?, #any-of?) and node-kind constraints.

Record mode handles order-independent key/value documents:

    class Person(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        age: int
        tags: list[str]
        nickname: str | None = None
        active: bool = False
        line: int = source_meta()

The record VALUE shape map below is JSON-grammar-shaped v1; the node-schema
bridge (Phase 4) would derive it from the grammar instead.
"""

from __future__ import annotations

import sys
from typing import ForwardRef
import types
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Annotated, Optional, Union, get_args, get_origin

import pydantic
import tree_sitter
from pydantic import BaseModel, ValidationError
from pydantic.fields import PydanticUndefined
from pydantic._internal._model_construction import ModelMetaclass

# reuse the proven emitter/materializer from the Phase-1 spike (sys.path hack
# because the directory name has a hyphen)
_SPIKE_A = Path(__file__).resolve().parent.parent / "spike-a"
sys.path.insert(0, str(_SPIKE_A))
import dsl                                   # noqa: E402
from materialize import (AmbiguousCaptureError, CoercionError,  # noqa: E402
                         Span, _text_of)

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
    """A pydantic type has no JSON-v1 value shape mapping."""


# --------------------------------------------------------------------------
# Derivation
# --------------------------------------------------------------------------

@dataclass
class _Binding:
    """Resolved field binding (built at class creation)."""
    capture: Optional[str] = None       # capture name feeding this field
    span: Optional[str] = None          # anchor capture for source_meta
    is_list: bool = False
    node_kinds: tuple = ()              # for diagnostics
    has_predicate: bool = False         # record-mode: absence filters the record
    nested: Optional[type] = None       # field type is another OutputModel


@dataclass
class _Derived:
    mode: str                           # "field" | "record"
    query: dsl.Query                    # field mode: the one query
    records: Optional[dsl.Query] = None  # record mode: outer query
    fields: Optional[dsl.Query] = None   # record mode: inner query
    bindings: dict = dc_field(default_factory=dict)


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


def _predicates_for(cap_name: str, metadata) -> list[dsl.Pred]:
    preds: list[dsl.Pred] = []
    for m in metadata:
        if isinstance(m, Matches):
            preds.append(dsl.cap(cap_name).matches(m.re))
        elif isinstance(m, Eq):
            preds.append(dsl.cap(cap_name).eq(m.value))
        elif isinstance(m, AnyOf):
            preds.append(dsl.cap(cap_name).any_of(*m.values))
    return preds


def _json_value_specs(target, cap_name: str, metadata) -> list[dsl.NodeSpec]:
    """Value-node shape for a record-mode field (JSON grammar v1).

    Returns one NodeSpec per emitted pattern (bool -> 2). Nested OutputModel
    fields capture the value node wholesale (wildcard)."""
    base = _unwrap_optional(target)
    if isinstance(base, type) and base is not type(None) \
            and hasattr(base, "_derived_cache"):
        return [dsl.node(None).capture(cap_name)]   # (_) @field
    kind = _kind_from_metadata(metadata)
    if kind is not None:
        return [dsl.node(k).capture(cap_name) for k in kind.kinds]
    base = _unwrap_optional(target)
    origin = get_origin(base)
    if origin is list:
        elem = get_args(base)[0] if get_args(base) else str
        elem = _unwrap_optional(elem)
        if elem is str:
            return [dsl.node("array").child(
                dsl.node("string").child(dsl.node("string_content").capture(cap_name)))]
        if elem in (int, float):
            return [dsl.node("array").child(dsl.node("number").capture(cap_name))]
        raise UnsupportedShapeError(
            f"list[{getattr(elem, '__name__', elem)}] has no JSON v1 shape "
            f"(use Annotated[..., NodeKind(...)] to declare it)")
    if base is str:
        return [dsl.node("string").child(dsl.node("string_content").capture(cap_name))]
    if base in (int, float):
        return [dsl.node("number").capture(cap_name)]
    if base is bool:
        return [dsl.node("true").capture(cap_name),
                dsl.node("false").capture(cap_name)]
    raise UnsupportedShapeError(
        f"field type {base!r} has no JSON v1 shape (use "
        f"Annotated[..., NodeKind(...)])")


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
            # capture name = the JSON key (attr name, or capture("key") override)
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
    specs = [dsl.node(k) for k in m.path]
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
                  node=dsl.node(k).capture(fname))
        for p in _predicates_for(fname, f.metadata):
            cur.where(p)

    cur.capture(ANCHOR)
    for s in reversed(specs[:-1]):
        cur = s.child(node=cur)
    q = dsl.Query(cur)
    return _Derived("field", q, bindings=bindings)


def _derive_record(model_cls, m: M, bindings) -> _Derived:
    # outer: anchored path with the record node captured
    specs = [dsl.node(k) for k in m.path]
    cur = specs[-1].capture(RECORD_CAP)
    for s in reversed(specs[:-1]):
        cur = s.child(node=cur)

    # inner: one pattern set per capture field (key eq -> value shape)
    patterns: list[dsl.NodeSpec] = []
    for fname, f in model_cls.model_fields.items():
        b = bindings[fname]
        if b.span:
            continue
        if b.capture is None:
            continue
        key = b.capture
        for vs in _json_value_specs(f.annotation, key, f.metadata):
            spec = (dsl.node("pair")
                    .child(field="key",
                           node=dsl.node("string")
                           .child(dsl.node("string_content").capture("key")))
                    .child(field="value", node=vs)
                    .where(dsl.cap("key").eq(key)))
            for p in _predicates_for(key, f.metadata):
                spec.where(p)
            patterns.append(spec)

    return _Derived(mode="record",
                    query=None,
                    records=dsl.Query(cur),
                    fields=dsl.Query(*patterns),
                    bindings=bindings)


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
    def extract(cls, text, language=None, *, strict: bool = True) -> list:
        lang = _resolve_language(language)
        if not isinstance(text, bytes):
            text = text.encode("utf-8")
        tree = tree_sitter.Parser(lang).parse(text)
        return cls.extract_tree(tree, strict=strict)

    @classmethod
    def extract_tree(cls, tree: tree_sitter.Tree, *, strict: bool = True) -> list:
        derived: _Derived = cls._derived_cache
        for w in cls._binding_warnings:
            print(f"  [model-warning] {cls.__name__}: {w}", file=sys.stderr)
        if derived.mode == "record":
            return _extract_record(cls, tree, derived, strict)
        return _extract_field(cls, tree, derived, strict)

    @classmethod
    def compiled_source(cls) -> str:
        """The derived .scm (for diagnostics/tests)."""
        d = cls._derived_cache
        if d.mode == "record":
            return d.records.source + "\n\n-- inner --\n\n" + d.fields.source
        return d.query.source

    @classmethod
    def validate_with(cls, language) -> None:
        """Compile the derived query against a grammar now (import-time-ish
        grammar validation, since node kinds/fields are grammar-specific)."""
        lang = _resolve_language(language)
        d = cls._derived_cache
        if d.mode == "record":
            d.records.compile(lang)
            d.fields.compile(lang)
        else:
            d.query.compile(lang)


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
    q = derived.query.compile(tree.language)
    results: list = []
    errors: list = []
    for m in dsl.Cursor(q, derived.query._quant_maps or [], tree).matches():
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


def _record_kwargs(model_cls, derived: _Derived, rec, tree):
    """Merge a record node's field captures into model kwargs (incl. nested)."""
    fld_q = derived.fields.compile(tree.language)
    merged: dict[str, list] = {}
    for fm in dsl.Cursor(fld_q, derived.fields._quant_maps or [], tree) \
            .matches_on(rec):
        for cname in set(fm._caps):
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
            inner = _record_kwargs(b.nested, b.nested._derived_cache, n, tree)
            if inner is not None:
                out.append(b.nested(**inner))
        merged[b.capture] = out
    return _build_kwargs(model_cls, derived.bindings, merged)


def _extract_record(model_cls, tree, derived: _Derived, strict):
    rec_q = derived.records.compile(tree.language)
    results: list = []
    errors: list = []
    for rm in dsl.Cursor(rec_q, derived.records._quant_maps or [], tree).matches():
        recs = rm.nodes(RECORD_CAP)
        if not recs:
            continue
        try:
            kwargs = _record_kwargs(model_cls, derived, recs[0], tree)
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


# --------------------------------------------------------------------------
# language resolution
# --------------------------------------------------------------------------

def _resolve_language(language):
    if isinstance(language, tree_sitter.Language):
        return language
    if callable(language):                   # tree_sitter_python.language
        return tree_sitter.Language(language())
    if hasattr(language, "language") and callable(language.language):
        return tree_sitter.Language(language.language())
    return tree_sitter.Language(language)    # a bare PyCapsule
