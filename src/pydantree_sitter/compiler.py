"""pydantree_sitter.compiler — MatchSpec + Language -> _Compiled (014 §4.2/4.4).

The ONE compiler: every extraction path (field mode, record mode, raw
queries, nested records) runs through it. Schema presence changes what the
compiler checks/infers, never which pipeline runs (D4): with a bound schema
it runs the Jobs (model↔grammar path/capture checks, capture↔type checks)
and constrains emitted kinds; without one it emits the portable wildcard
form (record mode over the documented JSON family + JSON_VALUE_MAP).

Value shapes come from a `ValueMap` (D6) — declared data, never name-regex
inference in the trusted path; `propose_value_map` is the draft generator.

The compiled state lives on the Extractor (binding.py), NOT on the model
class or a global registry (D5).
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any, Optional, get_args, get_origin

from .emit import Query, cap, node
from .errors import QueryBuildError, SchemaCheckError, ShapeError
from .markers import ANCHOR, GAP, RECORD_CAP, AnyOf, Eq, Matches
from .spec import FieldBinding, MatchSpec, unwrap_optional
from .valuemap import (
    JSON_KINDS,
    JSON_VALUE_MAP,
    ValueMap,
    array_kinds_for,
    propose_value_map,
    scalar_kinds_for,
    wrapper_kinds_for,
)


@dataclass
class _Compiled:
    """The bind's compiled state: queries + bindings + the checks' result.

    `query` (field mode / raw) or `records` + `fields` (record mode) are
    emit.Query objects (compiled at bind against the bind Language — the
    F-A1 lifetime fix: no class-level compiled cache). `nested_extractors`
    maps nested field name -> the nested model's Extractor (F-A2: one
    compiler, sub-extractors bound at bind time).
    """

    model: type
    spec: MatchSpec
    value_map: ValueMap
    schema: Any = None
    bindings: tuple = ()
    match_path: Optional[tuple] = None     # the M() path (with GAPs), for the matcher
    query: Any = None                      # field mode / raw: the one query
    records: Any = None                    # record mode: outer query
    fields: Any = None                     # record mode: inner query
    record_kind: Optional[str] = None
    pair_kind: Optional[str] = None
    nested_extractors: dict = dc_field(default_factory=dict)

    @property
    def quant_maps(self):
        return self.query._quant_maps if self.query is not None else None

    @property
    def records_quant_maps(self):
        return self.records._quant_maps if self.records is not None else None

    @property
    def fields_quant_maps(self):
        return self.fields._quant_maps if self.fields is not None else None

    @property
    def query_source(self) -> str:
        if self.query is not None:
            return self.query.source
        if self.records is not None and self.fields is not None:
            return (self.records.source + "\n\n-- inner --\n\n"
                    + self.fields.source)
        return ""


def compile_spec(model_cls, language, *, value_map: ValueMap) -> _Compiled:
    """Compile a model against a Language (all checks run HERE, once)."""
    spec: MatchSpec | None = model_cls._match_spec
    if spec is None:
        # REVIEW 020: a subclass without __match__/__raw_query__ used to
        # surface a raw AttributeError at bind; the metaclass now installs
        # _match_spec = None so the FRIENDLY error is the one you see.
        raise ShapeError(
            f"{model_cls.__name__} is not an extraction model: it needs "
            f"__match__ = M(...) (or __raw_query__ = RawQuery('...')).")
    schema = language.schema

    if spec.raw_query is not None:
        return _compile_raw(model_cls, spec, language, value_map)

    compiled = _Compiled(
        model=model_cls, spec=spec, value_map=value_map, schema=schema,
        bindings=spec.bindings,
        match_path=spec.path if spec.has_gap else None)

    if schema is not None:
        _check_path(model_cls, spec, schema)

    if spec.record:
        _compile_record(compiled, language)
    else:
        _compile_field(compiled, language)

    # nested record models: compile each sub-extractor against the SAME
    # Language (recursive — one compiler, no schema-less interleaving, F-A2)
    for b in spec.bindings:
        if b.nested is not None:
            compiled.nested_extractors[b.name] = \
                language.extractor(b.nested, strict=True)

    _bind_compile(compiled, language)
    return compiled


def _bind_compile(compiled: _Compiled, language) -> None:
    lang = language._lang
    if compiled.query is not None:
        compiled.query.compile(lang)
    if compiled.records is not None:
        compiled.records.compile(lang)
    if compiled.fields is not None:
        compiled.fields.compile(lang)


def emitted_source(model_cls, schema=None, *, check: bool = False) -> str:
    """The emitted .scm WITHOUT a bind (diagnostics): the schema-less
    wildcard form, or the schema-constrained form when `schema` is given.
    The compile step (tree_sitter.Query) is skipped — this is the source
    only. `check=False` by default (A4): the diagnostic must not raise the
    very SchemaCheckError you called it to inspect; pass check=True to
    run the schema checks."""
    spec = model_cls._match_spec
    if spec is None:
        raise ShapeError(
            f"{model_cls.__name__} is not an extraction model: it needs "
            f"__match__ = M(...) (or __raw_query__ = RawQuery('...')).")
    compiled = _Compiled(model=model_cls, spec=spec, value_map=JSON_VALUE_MAP,
                         schema=schema, bindings=spec.bindings,
                         match_path=spec.path if spec.has_gap else None)
    if schema is not None and check:
        _check_path(model_cls, spec, schema)
    if spec.raw_query is not None:
        return spec.raw_query
    if spec.record:
        _compile_record(compiled, None, check=check)
    else:
        _compile_field(compiled, None, check=check)
    return compiled.query_source


# ---------------------------------------------------------------------------
# raw queries (D11: __raw_query__ — the escape hatch)
# ---------------------------------------------------------------------------

def _compile_raw(model_cls, spec: MatchSpec, language, value_map: ValueMap):
    compiled = _Compiled(model=model_cls, spec=spec, value_map=value_map,
                         schema=language.schema, bindings=spec.bindings)
    compiled.query = Query.raw(spec.raw_query)
    fields = {b.name for b in spec.bindings}
    # capture-name -> field mapping is checked at compile (bind): unknown
    # captures are a bind-time error listing the model's fields
    compiled.query._raw_fields = fields
    compiled.query.compile(language._lang)   # compile ONCE, at bind
    # A3 (REVIEW 018 §4.1b): the escape hatch keeps SOME of the
    # differentiator — explicit capture('field')/capture_kind('kind') keys
    # are capture↔type checked schema-wide (no anchor kind to pin, so the
    # check is: the field/kind exists on SOME kind and the type coerces
    # for at least one possible kind)
    if language.schema is not None:
        _check_raw_bindings(model_cls, spec, language.schema, value_map,
                            spec.bindings)
    return compiled


def _check_raw_bindings(model_cls, spec: MatchSpec, schema, vm: ValueMap,
                        bindings) -> None:
    """A3: capture↔type checks for raw-query captures. We know a capture's
    CST field only when the key is explicit (`capture('left')` /
    `capture_kind('kind')`); without an anchored path the check is
    schema-wide: the field/kind must exist on SOME kind, and the Python
    type must coerce for at least one of that field's possible kinds.
    Unmarked captures (key == field name — the capture name, not a CST
    field) stay capture-name-only checked."""
    annotations = {b.name: _annotation(model_cls, b) for b in bindings}
    for b in bindings:
        if b.is_meta or not b.explicit_key:
            continue            # unmarked: the key is the capture name, not
                                # a CST field — capture-name-only checked
        f = model_cls.model_fields[b.name]
        if b.source == "cst_field":
            host_kinds = [k for k in schema.kinds()
                          if schema.has_field(k, b.key)]
            if not host_kinds:
                _raise(model_cls,
                       f"__raw_query__ capture({b.key!r}) on field "
                       f"{b.name!r}: no kind in the grammar has a CST "
                       f"field {b.key!r} (raw queries can't pin the anchor "
                       f"kind — the capture key must be a real field)",
                       entry=b.key)
            possible = schema.expand(
                r.type for k in host_kinds for r in
                schema.field_types(k, b.key))
        elif b.source == "child_kind":
            host_kinds = [k for k in schema.kinds()
                          if b.key in schema.possible_children(k)]
            if not host_kinds:
                _raise(model_cls,
                       f"__raw_query__ capture_kind({b.key!r}) on field "
                       f"{b.name!r}: kind {b.key!r} occurs as no kind's "
                       f"child in the grammar", entry=b.key)
            possible = schema.expand([b.key])
        else:
            continue
        _check_type(model_cls, schema, vm, b, f, possible, b.key)


# ---------------------------------------------------------------------------
# Job 1 — the __match__ path against the schema
# ---------------------------------------------------------------------------

def _model_site(model_cls) -> str:
    import inspect
    try:
        return f"{inspect.getsourcefile(model_cls)}:{inspect.getsourcelines(model_cls)[1]}"
    except (OSError, TypeError):
        return f"{model_cls.__module__}.{model_cls.__qualname__}"


def _raise(model_cls, msg: str, *, entry: str) -> None:
    raise SchemaCheckError(
        f"{model_cls.__name__} ({_model_site(model_cls)}): {msg}",
        schema_entry=entry, model=model_cls)


def _check_path(model_cls, spec: MatchSpec, schema) -> None:
    for step in spec.path:
        if step is GAP:
            continue
        for kind in step.kinds:
            t = schema.get(kind)
            if t is None:
                _raise(model_cls, f"__match__ kind {kind!r} does not exist in "
                                  f"the grammar's node schema (schema has "
                                  f"{sorted(schema.named_kinds())})", entry=kind)
            if not t.named:
                _raise(model_cls, f"__match__ kind {kind!r} is not a named "
                                  f"node in the grammar", entry=kind)
    prev = None
    gap = False
    for step in spec.path:
        if step is GAP:
            gap = True
            continue
        for kind in step.kinds:
            if prev is not None:
                possible = schema.is_possible_descendant(prev, kind) if gap \
                    else schema.is_possible_descent(prev, kind)
                if not possible:
                    kind_of = "a descendant of" if gap else "a child of"
                    _raise(
                        model_cls,
                        f"__match__ chain {spec.path!r}: {kind!r} cannot "
                        f"occur as {kind_of} {prev!r} in the grammar "
                        f"(possible children of {prev!r}: "
                        f"{sorted(schema.possible_children(prev))})",
                        entry=f"{prev} -> {kind}")
            prev = kind
            gap = False


# ---------------------------------------------------------------------------
# field mode
# ---------------------------------------------------------------------------

def _field_quant(b: FieldBinding, annotation) -> str:
    """The emitted quantifier for a field-mode capture: `?` for an optional
    scalar AND for LIST fields (zero-or-more), "" otherwise (exactly one).

    For a list field `?` means zero-or-more via the anchor-merge machinery
    (A2/REVIEW 020): the repeated child is fielded, tree-sitter yields ONE
    match per occurrence, and the matcher merges them by anchor — so an
    anchor with NO occurrences still matches (a function with no args no
    longer disappears; the old "" required exactly one and silently dropped
    the whole row), while N occurrences collect all N. (`*` cannot be used:
    tree-sitter captures only ONE node per `*`-quantified capture — verified
    empirically.)"""
    if get_origin(unwrap_optional(annotation)) is list:
        return "?"
    return "?" if b.optional else ""


def _capture_spec(k: str, b: FieldBinding, vm):
    """The captured node for a field-mode binding. A plain `str` field over a
    string-WRAPPER kind captures the wrapper's INNER content (record mode's
    shape — the value without quotes/escapes; REVIEW 020 minor); Unescaped()
    captures the wrapper wholesale (the raw text, decoded at
    materialization)."""
    inner = vm.wrappers.get(k) if vm is not None else None
    if inner and not b.unescape:
        return node(k).child(node(inner).capture(b.name))
    return node(k).capture(b.name)


def _compile_field(compiled: _Compiled, language, *, check: bool = True) -> None:

    spec = compiled.spec
    schema = compiled.schema
    model_cls = compiled.model
    bindings = spec.bindings
    annotations = {b.name: _annotation(model_cls, b) for b in bindings}

    suffix, _prefix = _split_suffix(spec.path)
    anchor_kinds = suffix[-1].kinds

    # per-binding emission kinds: NodeKind override (one pattern per kind —
    # F-A3) or the schema-inferred kind, else the wildcard
    field_kinds: dict[str, tuple] = {}
    for b in bindings:
        if b.is_meta:
            continue
        if b.kinds:
            field_kinds[b.name] = b.kinds
        elif schema is not None and b.source in ("cst_field", "child_kind"):
            field_kinds[b.name] = _infer_field_kind(
                schema, compiled.value_map, anchor_kinds, b,
                annotations[b.name])
        else:
            field_kinds[b.name] = ("_",)

    patterns = []
    for steps, chosen in _combinations(suffix, field_kinds):
        cur = node(steps[-1])
        for b in bindings:
            if b.is_meta:
                continue
            k = chosen[b.name]
            quant = _field_quant(b, annotations[b.name])
            if b.source == "child_kind":
                cur.child(node=node(b.key).capture(b.name), quant=quant)
            else:
                cur.child(field=b.key,
                          node=_capture_spec(k, b, compiled.value_map),
                          quant=quant)
            for p in _preds_for(b):
                cur.where(p)
        cur.capture(ANCHOR)
        for s in reversed(steps[:-1]):
            cur = node(s).child(node=cur)
        patterns.append(cur)

    compiled.query = Query(*patterns)
    if schema is not None and check:
        _check_field_bindings(compiled.model, spec, schema,
                              compiled.value_map, anchor_kinds,
                              bindings, annotations)


def _split_suffix(path: tuple) -> tuple[tuple, tuple]:
    """(suffix, prefix) — suffix is the direct-child chain ending at the
    anchor (what the emitted query nests); prefix is the ancestor walk. The
    LAST gap separates them."""
    steps = list(path)
    last_gap = max(i for i, p in enumerate(steps) if p is GAP) \
        if any(p is GAP for p in steps) else -1
    return tuple(steps[last_gap + 1:]), tuple(steps[:last_gap])


def _combinations(suffix: tuple, field_kinds: dict):
    """Cartesian product of suffix-step kind choices x field-kind choices."""
    import itertools
    step_choices = [s.kinds if len(s.kinds) > 1 else (s.kinds[0],)
                    for s in suffix]
    field_names = list(field_kinds)
    field_choices = [field_kinds[n] for n in field_names]
    for step_combo in itertools.product(*step_choices):
        for field_combo in itertools.product(*field_choices):
            yield tuple(step_combo), dict(zip(field_names, field_combo))


def _infer_field_kind(schema, vm: ValueMap, anchor_kinds: tuple, b: FieldBinding,
                      annotation) -> tuple:
    """The schema-inferred kind: the single compatible kind (the §2.2 'int
    defaults to numeric kinds' answer), else the wildcard. With alternation
    anchors the possible kinds are the UNION over all anchors (A4/REVIEW
    020 — the old `anchor_kinds[0]`-only inference under-checked the second
    alternative)."""
    possible: set = set()
    for anchor in anchor_kinds:
        possible |= _possible_for(schema, anchor, b)
    compatible = {k for k in possible
                  if _kind_coerces(schema, vm, annotation, k)}
    if len(compatible) == 1:
        return tuple(compatible)
    return ("_",)


def _possible_for(schema, anchor_kind: str, b: FieldBinding) -> set:
    if b.source == "cst_field":
        return schema.expand(
            r.type for r in schema.field_types(anchor_kind, b.key))
    if b.source == "child_kind":
        return {b.key}
    return set()


def _check_field_bindings(model_cls, spec, schema, vm: ValueMap, anchor_kinds,
                          bindings, annotations) -> None:
    """Job 3/4 for field mode. With alternation anchors EVERY anchor kind is
    checked (one emitted pattern per kind — A4/REVIEW 020: the old
    anchor_kinds[0]-only check let an invalid second alternative escape the
    actionable SchemaCheckError and fail later as a raw QueryBuildError)."""
    for b in bindings:
        if b.is_meta:
            continue
        f = model_cls.model_fields[b.name]
        if b.source == "child_kind":
            bad = [a for a in anchor_kinds
                   if b.key not in schema.possible_children(a)]
            if bad:
                _raise(model_cls,
                       f"capture_kind({b.key!r}) on field {b.name!r}: kind "
                       f"{b.key!r} cannot occur as a child of {bad[0]!r} in "
                       f"the grammar (possible children: "
                       f"{sorted(schema.possible_children(bad[0]))})",
                       entry=f"{bad[0]} -> {b.key}")
            _check_type(model_cls, schema, vm, b, f, {b.key},
                        f"{anchor_kinds} child {b.key}", field_mode=True)
            continue
        missing = [a for a in anchor_kinds
                   if not schema.has_field(a, b.key)]
        if missing:
            _raise(model_cls,
                   f"capture({b.key!r}) on field {b.name!r}: kind "
                   f"{missing[0]!r} has no CST field {b.key!r} (its fields: "
                   f"{sorted((schema.get(missing[0]).fields or {}))})",
                   entry=f"{missing[0]}.{b.key}")
        possible: set = set()
        for a in anchor_kinds:
            possible |= schema.expand(r.type for r in
                                     schema.field_types(a, b.key))
        _check_type(model_cls, schema, vm, b, f, possible,
                    f"{anchor_kinds}.{b.key}", field_mode=True)


def _check_type(model_cls, schema, vm: ValueMap, b, f, possible: set,
                where: str, *, field_mode: bool = False) -> None:
    """Job 4: a capture's possible node kinds vs the Python type."""
    target = unwrap_optional(f.annotation)
    if b.kinds:
        for k in b.kinds:
            if not _kind_coerces(schema, vm, target, k):
                _raise(model_cls,
                       f"field {b.name!r}: NodeKind({b.kinds!r}) constrains "
                       f"the capture to kind(s) that cannot feed a "
                       f"{_name(target)} field (schema entry: {where})",
                       entry=f"NodeKind({b.kinds}) vs {_name(target)}")
        return
    origin = get_origin(target)
    if origin is list:
        if field_mode:
            elem = unwrap_optional(get_args(target)[0]) \
                if get_args(target) else str
            if not any(_kind_coerces(schema, vm, elem, k) for k in possible):
                _raise(model_cls,
                       f"field {b.name!r} is list[{_name(elem)}] but the "
                       f"{where} capture can only ever yield "
                       f"{sorted(possible) or 'none'} (schema entry: {where})",
                       entry=where)
        return
    if target not in (str, int, float, bool):
        return  # opaque types (enums, custom) — runtime coercion decides
    if not any(_kind_coerces(schema, vm, target, k) for k in possible):
        _raise(model_cls,
               f"field {b.name!r} is {_name(target)} but the {where} capture "
               f"can only ever yield kinds that do not coerce to it: "
               f"{sorted(possible) or 'none'} (schema entry: {where})",
               entry=where)
    if b.unescape:
        wrappers = [k for k in possible
                    if _text_shape(schema, k) is not None
                    and _text_shape(schema, k)[0] is not None]
        if not wrappers:
            _raise(model_cls,
                   f"field {b.name!r}: Unescaped() requires a string-WRAPPER "
                   f"capture (a grammar string literal whose content carries "
                   f"escapes), but the {where} capture can only yield "
                   f"{sorted(possible) or 'none'} (schema entry: {where})",
                   entry=where)


def _kind_coerces(schema, vm: ValueMap, target, kind: str) -> bool:
    """Does `kind` coerce to `target`? (ValueMap-backed; supertypes
    expanded.) The committed ValueMap is authoritative (D6) — the name-regex
    heuristic is consulted only for kinds the map does not declare."""
    expanded = schema.expand([kind])
    base = target
    origin = get_origin(base)
    if origin is list:
        args = get_args(base)
        base = unwrap_optional(args[0]) if args else str
    if base is int:
        return any(_scalar_of(schema, vm, k) == "int" for k in expanded)
    if base is float:
        return any(_scalar_of(schema, vm, k) in ("float", "int") for k in expanded)
    if base is bool:
        return any(_scalar_of(schema, vm, k) == "bool" for k in expanded)
    if base is str:
        # text-yielding = a structural text shape OR a ValueMap declaration
        # (scalar "str" / wrapper kind) — mirrors record-mode emission
        # (_scalar_shapes: scalar_kinds_for(vm, str) + wrapper_kinds_for(vm))
        return any(
            _text_shape(schema, k) is not None
            or (vm is not None
                and (k in vm.wrappers or vm.scalars.get(k) == "str"))
            for k in expanded)
    return True


# memoized draft ValueMap: recomputed per call was the silent cost of the
# old checker (propose_value_map walks the whole schema every time). Keyed by
# id() because NodeSchema is not hashable (pydantic v2 non-frozen) — the
# cache holds the schema object itself so its id cannot be reused by a
# different schema (a stale draft for the wrong grammar is a wrong check).
# A lock makes the memo safe to share across threads (REVIEW 020 minor — the
# caches were unsynchronized).
_PROPOSED_CACHE: dict[int, tuple[object, "ValueMap"]] = {}
_PROPOSED_LOCK = __import__("threading").Lock()


def _proposed(schema) -> "ValueMap":
    """The draft (name-regex) ValueMap for `schema`, computed once per
    schema object. Declared-data fallback ONLY — kinds the committed map
    declares never reach this."""
    key = id(schema)
    with _PROPOSED_LOCK:
        cached = _PROPOSED_CACHE.get(key)
        if cached is None or cached[0] is not schema:
            cached = (schema, propose_value_map(schema))
            _PROPOSED_CACHE[key] = cached
        return cached[1]


def _scalar_of(schema, vm: ValueMap | None, kind: str) -> Optional[str]:
    """A kind's scalar meaning for the CHECK path: the committed ValueMap
    first (D6 — declared data wins), the draft heuristic only for kinds the
    map does not declare. Emission uses the same (schema, ValueMap), so the
    checker and the emitter cannot disagree."""
    if vm is not None and kind in vm.scalars:
        return vm.scalars[kind]
    return _proposed(schema).scalars.get(kind)


def _text_shape(schema, kind: str):
    """A text-yielding shape for `kind`: a direct text leaf, or a wrapper
    whose children include one (heredoc_body -> heredoc_content). ONE level
    only — grammar reference graphs are cyclic, so deep recursion would
    loop. The captured node is the kind itself — its whole text is the value."""
    t = schema.get(kind)
    if t is None or schema.is_supertype(kind):
        return None
    if t.fields:
        return None
    if t.children is None:
        return (None, kind)
    for r in t.children.types:
        if r.named and _is_text_leaf(schema, r.type):
            return (kind, r.type)
    return None


def _is_text_leaf(schema, kind: str) -> bool:
    t = schema.get(kind)
    return t is not None and not schema.is_supertype(kind) and not t.fields \
        and (t.children is None or not t.children.types)


def _name(t) -> str:
    return getattr(t, "__name__", str(t))


def _annotation(model_cls, b: FieldBinding):
    return model_cls.model_fields[b.name].annotation


# ---------------------------------------------------------------------------
# record mode
# ---------------------------------------------------------------------------

def _compile_record(compiled: _Compiled, language, *, check: bool = True) -> None:

    spec = compiled.spec
    schema = compiled.schema
    model_cls = compiled.model
    bindings = spec.bindings
    annotations = {b.name: _annotation(model_cls, b) for b in bindings}

    suffix, _prefix = _split_suffix(spec.path)
    record_kind = suffix[-1].kinds[0]
    compiled.record_kind = record_kind

    vm = compiled.value_map
    if schema is not None:
        pair_kind = _find_pair_kind(schema, record_kind, model_cls,
                                    spec.record_pair)
        compiled.pair_kind = pair_kind
        key_shapes = _key_shapes(schema, pair_kind)
        if not key_shapes:
            raise ShapeError(
                f"record mode over {record_kind!r}: the pair kind "
                f"{pair_kind!r} has no text-yielding key shape in the "
                f"node schema")
        value_kinds = schema.expand(
            r.type for r in schema.field_types(pair_kind, "value"))
    else:
        # schema-less record mode = JSON_VALUE_MAP + the documented JSON
        # kinds (stated in valuemap.py; no silent name-regex inference)
        pair_kind = "pair"
        compiled.pair_kind = pair_kind
        key_shapes = [("string", "string_content")]
        value_kinds = set(JSON_KINDS)

    # ---- outer query: the anchored path capturing the record node --------
    cur = node(record_kind).capture(RECORD_CAP)
    for s in reversed(suffix[:-1]):
        cur = node(s.kinds[0]).child(node=cur)
    compiled.records = Query(cur)

    # ---- inner query: one anchored pattern per field ----------------------
    patterns = []
    for b in bindings:
        if b.is_meta:
            continue
        for vs in _value_shapes(b, schema, vm, value_kinds, pair_kind,
                                annotations[b.name]):
            spec_node = (node(record_kind)
                         .child(node(pair_kind)
                                .child(field="key", node=_key_spec(key_shapes))
                                .child(field="value", node=vs)
                                .where(cap("key").eq(b.key)))
                         .capture(ANCHOR))
            for p in _preds_for(b):
                spec_node.where(p)
            patterns.append(spec_node)
    compiled.fields = Query(*patterns) if patterns else None

    if schema is not None and check:
        _check_record_bindings(model_cls, schema, vm, pair_kind, value_kinds,
                               bindings)


def _find_pair_kind(schema, record_kind: str, model_cls=None,
                    record_pair: str | None = None) -> str:
    """The record's pair kind: a child of `record_kind` with both 'key' and
    'value' fields. Deterministic-and-explicit (REVIEW 018 §4.3): with
    several candidates the compiler RAISES, naming them, instead of
    silently picking the alphabetically first — pass `record_pair=` in
    M(...) to pin it."""
    children = schema.expand(r.type for r in schema.children_types(record_kind))
    candidates = [k for k in sorted(children)
                  if schema.has_field(k, "value") and schema.has_field(k, "key")]
    if record_pair is not None:
        if record_pair not in candidates:
            raise ShapeError(
                f"record mode over {record_kind!r}: record_pair={record_pair!r} "
                f"is not a child kind of {record_kind!r} with both 'key' "
                f"and 'value' fields (candidates: {candidates or 'none'})")
        return record_pair
    if not candidates:
        raise ShapeError(
            f"record mode over {record_kind!r}: no child kind of "
            f"{record_kind!r} has both 'key' and 'value' fields in the "
            f"grammar's node schema (children: {sorted(children) or 'none'})")
    if len(candidates) > 1:
        raise ShapeError(
            f"record mode over {record_kind!r}: several child kinds have "
            f"both 'key' and 'value' fields ({candidates}) — pin one with "
            f"M(..., record=True, record_pair=<kind>)")
    return candidates[0]


def _key_shapes(schema, pair_kind: str):
    """(wrapper_or_None, leaf) pairs for the pair's key node: a text-yielding
    leaf, or a wrapper whose children include a text leaf (JSON: string ->
    string_content; config: identifier)."""
    kinds = schema.expand(r.type for r in schema.field_types(pair_kind, "key"))
    out = []
    for k in sorted(kinds):
        t = schema.get(k)
        if t is None or schema.is_supertype(k):
            continue
        if t.fields:
            continue
        if t.children is None:
            if t.named:
                out.append((None, k))
            continue
        leaves = [r.type for r in t.children.types
                  if r.named and _leaf_shape(schema, r.type)]
        if leaves:
            for preferred in ("string_content", "content", "text"):
                if preferred in leaves:
                    out.append((k, preferred))
                    break
            else:
                out.append((k, leaves[0]))
    return out


def _leaf_shape(schema, kind: str):
    t = schema.get(kind)
    if t is None or schema.is_supertype(kind):
        return None
    if t.fields:
        return None
    if t.children is not None and t.children.types:
        return None
    return kind


def _key_spec(key_shapes):
    wrapper, leaf = key_shapes[0]
    if wrapper is not None:
        return node(wrapper).child(node(leaf).capture("key"))
    return node(leaf).capture("key")


def _value_shapes(b: FieldBinding, schema, vm: ValueMap, value_kinds: set,
                  pair_kind: str, annotation) -> list:
    """The value-node shapes for a record field: (schema, ValueMap)-driven,
    one pattern per kind (F-A3 dies here too)."""

    if b.nested is not None:
        return [node(None).capture(b.key)]           # the value node wholesale
    if b.kinds:
        return [node(k).capture(b.key) for k in b.kinds]
    if b.unescape:
        return _unescape_shapes(b, schema, vm, value_kinds, pair_kind)
    origin = get_origin(annotation)
    if origin is list:
        return _list_shapes(b, schema, vm, value_kinds, pair_kind, annotation)
    return _scalar_shapes(b, schema, vm, value_kinds, pair_kind, annotation)


def _base_target(annotation):
    return unwrap_optional(annotation)


def _scalar_shapes(b, schema, vm, value_kinds, pair_kind, annotation):
    base = _base_target(annotation)
    shapes = []
    for k in [k for k in scalar_kinds_for(vm, base) if k in value_kinds]:
        shapes.append(node(k).capture(b.key))
    for w in wrapper_kinds_for(vm):
        if w in value_kinds:
            shapes.append(node(w).child(
                node(vm.wrappers[w]).capture(b.key)))
    if not shapes and value_kinds:
        raise ShapeError(
            f"field {b.name!r} has no value shape in grammar "
            f"{schema.name if schema is not None else '?'}: the value kinds "
            f"under {pair_kind!r} ({sorted(value_kinds) or 'none'}) contain "
            f"no {_name(base)}-compatible kind (schema entry: "
            f"{pair_kind!r} value field; use Annotated[..., NodeKind(...)] "
            f"to declare it)")
    return shapes


def _list_shapes(b, schema, vm, value_kinds, pair_kind, annotation):
    args = get_args(annotation)
    elem = unwrap_optional(args[0]) if args else str
    shapes = []
    for arr in array_kinds_for(schema, vm, annotation):
        if arr not in value_kinds:
            continue
        if unwrap_optional(elem) is str:
            for k in [k for k in scalar_kinds_for(vm, str)
                      if k in value_kinds]:
                shapes.append(node(arr).child(node(k).capture(b.key)))
            for w in wrapper_kinds_for(vm):
                shapes.append(node(arr).child(
                    node(w).child(node(vm.wrappers[w]).capture(b.key))))
        else:
            for k in [k for k in scalar_kinds_for(vm, unwrap_optional(elem))
                      if k in value_kinds]:
                shapes.append(node(arr).child(node(k).capture(b.key)))
    if not shapes and value_kinds:
        raise ShapeError(
            f"field {b.name!r} is list[{_name(unwrap_optional(elem))}] but "
            f"the value kinds under {pair_kind!r} "
            f"({sorted(value_kinds) or 'none'}) contain no array-like kind "
            f"whose elements express it (schema entry: {pair_kind!r} value "
            f"field)")
    return shapes


def _unescape_shapes(b, schema, vm, value_kinds, pair_kind):
    shapes = []
    for w in wrapper_kinds_for(vm):
        if w in value_kinds:
            shapes.append(node(w).capture(b.key))  # the wrapper wholesale
    if not shapes and value_kinds:
        raise ShapeError(
            f"field {b.name!r}: Unescaped() requires a string-WRAPPER value "
            f"shape, but the value kinds under {pair_kind!r} "
            f"({sorted(value_kinds) or 'none'}) contain no string wrapper")
    return shapes


def _check_record_bindings(model_cls, schema, vm: ValueMap, pair_kind,
                           value_kinds, bindings) -> None:
    for b in bindings:
        if b.is_meta:
            continue
        f = model_cls.model_fields[b.name]
        _check_type(model_cls, schema, vm, b, f, value_kinds,
                    f"value-under-{pair_kind}")


def _preds_for(b: FieldBinding):
    """Predicates apply to the VALUE capture (record mode: the value node;
    field mode: the captured field node). Marker identity is isinstance
    (F-A13)."""
    out = []
    for m in b.predicates:
        if isinstance(m, Matches):
            out.append(cap(b.capture_name).matches(m.re))
        elif isinstance(m, Eq):
            out.append(cap(b.capture_name).eq(m.value))
        elif isinstance(m, AnyOf):
            out.append(cap(b.capture_name).any_of(*m.values))
    return out
