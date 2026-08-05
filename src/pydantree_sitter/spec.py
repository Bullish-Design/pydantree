"""pydantree_sitter.spec — the pure model declaration (014 §4.1).

`derive_spec(model_cls)` turns a model class into a `MatchSpec` — inert,
language-independent data (no queries, no compiled state, no grammar
knowledge). The only cache is a per-class memo of the spec itself (safe:
language-independent).

The metaclass calls `derive_spec` PER CLASS (walking the MRO for
`__match__`/`__raw_query__` but always re-deriving with the subclass's own
fields — the `ns.get("__match__")` inheritance wart is fixed here).

Class-creation checks stay here (they need no grammar): unresolvable
annotations, marker conflicts, `ShapeError` for unmappable record shapes and
for nested models in field mode (rejected legibly per §4.5, documented
TODO). Everything needing a grammar moves to bind (compiler.py).
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field as dc_field
from typing import (
    Annotated,
    ForwardRef,
    Literal,
    Optional,
    Union,
    get_args,
    get_origin,
)

import pydantic
from pydantic import BaseModel, ValidationError
from pydantic.fields import PydanticUndefined
from pydantic._internal._model_construction import ModelMetaclass

from .errors import ShapeError
from .markers import (
    ANCHOR,
    GAP,
    M,
    _MISSING,
    AnyOf,
    Eq,
    Matches,
    NodeKind,
    RawQuery,
    Unescaped,
    _Capture,
    _CaptureKind,
    _Derived,
    _MARKERS,
    _SourceMeta,
    capture,
    capture_kind,
    derived,
    source_meta,
)

__all__ = [
    "GAP", "PathStep", "FieldBinding", "MatchSpec", "derive_spec",
    "OutputModel", "DerivingMeta",
    "capture", "capture_kind", "source_meta", "derived",
]

# ---------------------------------------------------------------------------
# the declaration types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PathStep:
    """One M() path element; `kinds` has len>1 for alternation (D11)."""

    kinds: tuple[str, ...]


@dataclass(frozen=True)
class FieldBinding:
    """One resolved field's binding (pure data; predicates are the inert
    marker objects, not emitted Preds)."""

    name: str
    source: Literal["cst_field", "child_kind", "record_key", "meta"]
    key: str                       # CST field / child kind / record key / meta capture
    kinds: tuple[str, ...] = ()    # NodeKind override; () = infer from map
    predicates: tuple = ()         # Matches/Eq/AnyOf markers, inert data
    optional: bool = False
    is_list: bool = False
    nested: Optional[type] = None  # OutputModel subclass (issubclass check)
    unescape: bool = False
    is_meta: bool = False
    explicit_key: bool = False
    # True when the key came from capture('x')/capture_kind('x') — a real
    # CST field / kind name, NOT the bare attr name (A3/REVIEW 018: raw
    # queries can only be schema-checked for explicit keys).

    @property
    def has_predicate(self) -> bool:
        return bool(self.predicates)

    @property
    def capture_name(self) -> str:
        """The capture name in the emitted query: field mode captures under
        the FIELD name (the key is the CST field / child kind); record mode
        captures under the RECORD KEY; meta reads the anchor capture."""
        if self.source in ("cst_field", "child_kind"):
            return self.name
        return self.key


@dataclass(frozen=True)
class MatchSpec:
    """The whole declaration: the anchored ancestor path, the record flag,
    and the field bindings. `raw_query` is mutually exclusive with `path`
    (D11: `__raw_query__` is a literal .scm whose captures map to fields by
    name). `record_pair` pins the pair kind for record mode (REVIEW 018
    §4.3)."""

    path: tuple[PathStep | object, ...]  # PathStep | GAP
    record: bool = False
    record_pair: Optional[str] = None
    raw_query: Optional[str] = None
    bindings: tuple[FieldBinding, ...] = ()

    @property
    def has_gap(self) -> bool:
        return any(p is GAP for p in self.path)

    @property
    def anchor_kind(self) -> Optional[str]:
        """The anchor's kind (the last path step) — None for raw queries."""
        if self.raw_query is not None:
            return None
        last = self.path[-1]
        if isinstance(last, PathStep):
            return last.kinds[0]
        return None


# ---------------------------------------------------------------------------
# type helpers
# ---------------------------------------------------------------------------


def unwrap_optional(t):
    origin = get_origin(t)
    if origin in (Union, types.UnionType):
        args = [a for a in get_args(t) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return t


def is_optional(t) -> bool:
    origin = get_origin(t)
    if origin in (Union, types.UnionType):
        return any(a is type(None) for a in get_args(t))
    return False


def _field_is_query_optional(f) -> bool:
    """A capture is query-optional iff the model can materialize WITHOUT the
    field: an Optional annotation, or a REAL default. A marker default
    (`= capture(...)` etc.) is NOT a default — pydantic's `is_required()`
    treats any default as non-required, so the marker would wrongly make a
    required field optional."""
    if is_optional(f.annotation):
        return True
    d = f.default
    return d is not PydanticUndefined and not isinstance(d, _MARKERS)


def _kind_override(metadata) -> tuple[str, ...]:
    for m in metadata:
        if isinstance(m, NodeKind):
            return m.kinds
    return ()


def _predicate_markers(metadata) -> tuple:
    return tuple(m for m in metadata if isinstance(m, (Matches, Eq, AnyOf)))


def _name(t) -> str:
    return getattr(t, "__name__", str(t))


# ---------------------------------------------------------------------------
# the derivation (pure)
# ---------------------------------------------------------------------------

def _resolve_annotation(model_cls, fname, annotation):
    if isinstance(annotation, ForwardRef):
        annotation = _try_resolve_forward_ref(model_cls, annotation)
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        args = tuple(_try_resolve_forward_ref(model_cls, a)
                     if isinstance(a, ForwardRef) else a
                     for a in get_args(annotation))
        annotation = args[0] if len(args) == 1 else Union[args]
    if isinstance(annotation, ForwardRef) or \
            (not isinstance(annotation, type) and get_origin(annotation) is None):
        raise ShapeError(
            f"field {fname!r}: annotation {annotation!r} could not be "
            f"resolved (pydantic left a ForwardRef). This usually means a "
            f"name in the annotation (e.g. Annotated, or a marker class, or "
            f"a nested model defined in a function) is not importable in "
            f"the module where {model_cls.__name__} is defined — define it "
            f"at module level, or disable `from __future__ import annotations` "
            f"for local nested models.")
    return annotation


def _try_resolve_forward_ref(model_cls, ref):
    """Best-effort resolution of a ForwardRef against the model's module
    namespace (pydantic leaves one when `from __future__ import annotations`
    is on and the name is module-level — e.g. "Address | None", "A | B").
    Real eval against the module's globals (A9 — the old string-partition
    hack only handled single `| None` unions)."""
    name = getattr(ref, "__forward_arg__", None)
    if not name:
        return ref
    module = sys.modules.get(model_cls.__module__)
    if module is None:
        return ref
    try:
        return eval(name, vars(module))
    except Exception:
        return ref


def _field_binding(model_cls, fname, f, record: bool) -> FieldBinding | None:
    """Resolve one field to a FieldBinding; None = derived() (excluded)."""
    annotation = _resolve_annotation(model_cls, fname, f.annotation)
    metadata = f.metadata
    d = f.default

    target = unwrap_optional(annotation)
    is_list = get_origin(target) is list
    elem = target
    if is_list:
        args = get_args(target)
        elem = unwrap_optional(args[0]) if args else str
    nested = elem if isinstance(elem, type) and elem is not type(None) \
        and issubclass(elem, OutputModel) else None

    # ---- the marker / unmarked resolution (bind-by-name in BOTH modes) ----
    if isinstance(d, _SourceMeta):
        source, key = "meta", d.capture
    elif isinstance(d, _CaptureKind):
        source, key = "child_kind", d.kind
    elif isinstance(d, _Capture):
        source = "record_key" if record else "cst_field"
        key = d.field or fname
    elif isinstance(d, _Derived):
        return None                              # computed: not in the query
    else:                                        # unmarked: bind-by-name
        source = "record_key" if record else "cst_field"
        key = fname
    explicit_key = isinstance(d, _CaptureKind) or \
        (isinstance(d, _Capture) and d.field is not None)

    kinds = _kind_override(metadata)
    predicates = _predicate_markers(metadata)
    optional = _field_is_query_optional(f)
    unescape = any(isinstance(m, Unescaped) for m in metadata)

    if nested is not None and not record and source == "cst_field":
        # §4.5 decision: nested materialization in field mode is NOT
        # implemented — reject legibly at class creation (the examples don't
        # use it; leave a documented TODO for real need).
        raise ShapeError(
            f"field {fname!r}: a nested {OutputModel.__name__} field in "
            f"field mode is not supported (nested models materialize in "
            f"record mode only) — mark the field {derived()}() to exclude "
            f"it from the query, or use record mode.")

    return FieldBinding(
        name=fname,
        source=source,
        key=key,
        kinds=kinds,
        predicates=predicates,
        optional=optional,
        is_list=is_list,
        nested=nested,
        unescape=unescape,
        is_meta=source == "meta",
        explicit_key=explicit_key,
    )


def derive_spec(model_cls: type["OutputModel"]) -> MatchSpec:
    """The pure declaration: model class -> MatchSpec.

    A pure function of `model_fields` + `__match__` / `__raw_query__`; no
    queries, no caches beyond the per-class memo the metaclass installs.
    """
    match: M | None = None
    raw_query: str | None = None
    for base in model_cls.__mro__:
        if match is None and getattr(base, "__match__", None) is not None:
            match = base.__match__
        if raw_query is None and getattr(base, "__raw_query__", None) is not None:
            raw_query = base.__raw_query__
    if match is None and raw_query is None:
        raise ShapeError(
            f"{model_cls.__name__} is not an extraction model: it needs "
            f"__match__ = M(...) (or __raw_query__ = RawQuery('...')).")

    bindings: list[FieldBinding] = []
    for fname, f in model_cls.model_fields.items():
        b = _field_binding(model_cls, fname, f, record=bool(match and match.record))
        if b is not None:
            bindings.append(b)

    if raw_query is not None:
        if not isinstance(raw_query, (str, RawQuery)):
            raise ShapeError(
                f"__raw_query__ must be a .scm string, got {type(raw_query)}")
        if match is not None:
            raise ShapeError(
                "a model declares BOTH __match__ and __raw_query__ — "
                "they are mutually exclusive")
        return MatchSpec(path=(), record=False, raw_query=str(raw_query),
                         bindings=tuple(bindings))

    path = tuple(PathStep((k,)) if isinstance(k, str) else
                 (PathStep(k) if isinstance(k, tuple) else k)
                 for k in match.path)
    return MatchSpec(path=path, record=match.record,
                     record_pair=match.record_pair,
                     bindings=tuple(bindings))


def binding_warnings(model_cls: type["OutputModel"]) -> list[str]:
    """Warnings for bindings that can never materialize (the port of the
    legacy quantifier-vs-type check, 014 §4.1). Surfaced once at bind via
    warnings.warn — never prints. Only a field with NO binding and no
    value can never materialize: an unmarked field is bound by name in BOTH
    modes; a derived(value) field carries its value."""
    warnings: list[str] = []
    spec = model_cls._match_spec
    bound = {b.name for b in spec.bindings}
    from .markers import _Derived as _D
    for fname, f in model_cls.model_fields.items():
        if fname in bound:
            continue
        if isinstance(f.default, _D):
            if f.default.default is _MISSING:
                warnings.append(
                    f"field {fname!r} is derived() with no value — a match "
                    f"without it will raise ValidationError (use "
                    f"derived(value) or remove the marker)")
        elif f.default is PydanticUndefined:
            warnings.append(
                f"field {fname!r} has no binding and no default — a match "
                f"without it will raise ValidationError")
    return warnings


# ---------------------------------------------------------------------------
# the metaclass + OutputModel
# ---------------------------------------------------------------------------

class DerivingMeta(ModelMetaclass):
    """Derive the MatchSpec PER CLASS: walk the MRO for `__match__` /
    `__raw_query__`, but always re-derive with the subclass's own fields
    (a subclass adding fields inherits the base's path but not its
    bindings)."""

    def __new__(mcls, name, bases, ns, **kwargs):
        cls = super().__new__(mcls, name, bases, ns, **kwargs)
        has_decl = any(
            getattr(base, "__match__", None) is not None or
            getattr(base, "__raw_query__", None) is not None
            for base in cls.__mro__)
        if has_decl:
            cls._match_spec = derive_spec(cls)
            cls._binding_warnings = tuple(binding_warnings(cls))
        else:
            # REVIEW 020 minor: a subclass with no declaration used to have
            # NO _match_spec attribute — binding surfaced a raw
            # AttributeError. Installing None lets compile_spec raise the
            # friendly ShapeError ("not an extraction model").
            cls._match_spec = None
        return cls


class OutputModel(BaseModel, metaclass=DerivingMeta):
    """A typed extraction target. The class IS the query declaration.

        class Assignment(OutputModel):
            __match__ = M("module", "expression_statement", "assignment")
            name: str = capture("left")
            value: Annotated[int, NodeKind("integer")] = capture("right")

        lang = Language.load_bundle("bundles/mylang")
        rows = lang.extractor(Assignment).extract(text)

    `Model.extract(text, language=...)` is sugar for
    `language.extractor(Model).extract(text)` (the explicit bind runs all
    checks once — binding.py).
    """

    __match__ = None
    __raw_query__ = None

    # -- entry points (sugar; the real work is the Extractor) ---------------

    @classmethod
    def extract(cls, text, language=None, *, strict: bool = True,
                schema=None):
        ext = _sugar_extractor(cls, language, schema, strict=strict)
        return ext.extract(text)

    @classmethod
    def extract_tree(cls, tree, *, strict: bool = True, schema=None,
                     language=None):
        """Extract over an already-parsed tree. Without a `language=`, a
        transient Language is built from the tree's grammar (with `schema=`
        when given) — the schema-less JSON fallback applies for records."""
        from .binding import Language, _language_for, _transient_language
        if language is None:
            lang = Language.load(tree.language, schema=schema)
        else:
            lang = _language_for(language)
            if schema is not None and lang.schema is None:
                lang = _transient_language(lang, schema=schema)
        return lang.extractor(cls, strict=strict).extract_tree(tree)

    @classmethod
    def validate_with(cls, language, schema=None) -> None:
        """Compat sugar: bind the model to `language` (running all checks).
        `language` may be a Language or a bare module/language."""
        _sugar_extractor(cls, language, schema, strict=True)

    @classmethod
    def compiled_source(cls, *, schema=None, language=None) -> str:
        """The derived .scm (diagnostics). Without a language, the emitted
        source is shown without compiling (schema-less wildcard form, or the
        schema-constrained form with `schema=`); with a language, the bound
        Extractor's query source."""
        from .compiler import emitted_source
        if language is None:
            return emitted_source(cls, schema=schema)   # check=False (A4):
            # the diagnostic never raises the SchemaCheckError you called
            # it to inspect
        from .binding import Language, _language_for, _transient_language
        lang = _language_for(language)
        if schema is not None and lang.schema is None:
            lang = _transient_language(lang, schema=schema)
        return lang.extractor(cls).query_source

    # -- declaration accessors ----------------------------------------------

    @classmethod
    def _spec(cls) -> MatchSpec:
        return cls._match_spec


def _sugar_extractor(model_cls, language, schema, *, strict: bool):
    """The sugar path: normalize `language` (Language, module, capsule, or
    None) + an optional explicit `schema=` into a Language and bind."""
    from .binding import Language, _language_for, _transient_language
    lang = _language_for(language)
    if lang is None:
        if schema is not None:
            raise ShapeError(
                f"extract(..., schema=...) needs a language too — pass "
                f"language= (a Language, a grammar module, or a "
                f"tree_sitter.Language)")
        raise ShapeError(
            f"{model_cls.__name__}.extract needs language= (a Language, a "
            f"grammar module, or a tree_sitter.Language) — "
            f"e.g. lang.extractor({model_cls.__name__}).extract(text)")
    if schema is not None and lang.schema is None:
        lang = _transient_language(lang, schema=schema)
    return lang.extractor(model_cls, strict=strict)
