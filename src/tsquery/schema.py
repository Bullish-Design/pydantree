"""tsquery.schema — Jobs 1 & 4: model↔grammar and capture↔type validation
against the node-schema (the Phase-4 bridge's A-side checks).

Two entry points, both running BEFORE any text is parsed:

  * `check_model_schema(model_cls, schema)` — Jobs 1 + 4:
    - the `__match__` ancestor chain is a *possible descent* in the schema
      (every step parent→child exists in the schema's children/fields, with
      supertypes expanded);
    - every capture's CST field exists on its node kind;
    - a capture's possible node kinds must intersect the field's Python type
      (numeric kinds ↔ int/float, boolean kinds ↔ bool, array kinds ↔ list,
      text-yielding kinds ↔ str) — the spike-a2 §2.2 question, decided by
      the schema;
    - `NodeKind(...)` overrides are themselves validated against the type.
    Each failure raises `SchemaCheckError` citing the schema entry (node kind
    / field / supertype) and the model's definition site.

  * `schema_derive(model_cls, schema, language_name)` — rebuild the model's
    query for the bound grammar: Job 3 value shapes in record mode (the
    hardcoded JSON map is replaced by `tsquery.shapes.shape_for`),
    record-level anchoring (inner queries name the record node so nested
    pairs can't collide — the spike-a §3 fix), and derived kind constraints
    in field mode (an `int` capture defaults to the grammar's numeric kinds).
    Cached per model per grammar name.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass

from .dsl import Query, cap, node
from .shapes import (
    _kind_set_for,
    _value_kinds,
    compatible_kinds,
    is_boolean_kind,
    is_float_kind,
    is_numeric_kind,
    text_shapes_for,
)
from .typed import (
    ANCHOR,
    M,
    SchemaCheckError,
    UnsupportedShapeError,
    _Binding,
    _Derived,
    _predicates_for,
    _unwrap_optional,
)


def _model_site(model_cls) -> str:
    try:
        return f"{inspect.getsourcefile(model_cls)}:{inspect.getsourcelines(model_cls)[1]}"
    except (OSError, TypeError):
        return f"{model_cls.__module__}.{model_cls.__qualname__}"


def _raise(model_cls, msg: str, *, entry: str) -> None:
    raise SchemaCheckError(
        f"{model_cls.__name__} ({_model_site(model_cls)}): {msg}",
        schema_entry=entry, model=model_cls)


# ---------------------------------------------------------------------------
# Job 1 — the __match__ chain and capture fields
# ---------------------------------------------------------------------------

def check_model_schema(model_cls, schema) -> None:
    """Run Jobs 1 + 4 for a model against a node-schema (no parsing)."""
    m: M = model_cls.__match__
    d: _Derived = model_cls._derived_cache

    # every path element is a real named kind ('...' is the descendant gap)
    for i, kind in enumerate(m.path):
        if kind == "...":
            continue
        t = schema.get(kind)
        if t is None:
            _raise(model_cls, f"__match__ kind {kind!r} does not exist in "
                              f"the grammar's node schema (schema has "
                              f"{sorted(schema.named_kinds())})", entry=kind)
        if not t.named:
            _raise(model_cls, f"__match__ kind {kind!r} is not a named node "
                              f"in the grammar", entry=kind)

    # the ancestor chain is a possible descent — with '...' gaps allowed to
    # span ANY depth (checked as a possible descendant instead of a child)
    prev = None
    gap = False
    for el in m.path:
        if el == "...":
            gap = True
            continue
        if prev is not None:
            possible = schema.is_possible_descendant(prev, el) if gap \
                else schema.is_possible_descent(prev, el)
            if not possible:
                kind_of = "a descendant of" if gap else "a child of"
                _raise(
                    model_cls,
                    f"__match__ chain {m.path!r}: {el!r} cannot occur as "
                    f"{kind_of} {prev!r} in the grammar (possible children "
                    f"of {prev!r}: "
                    f"{sorted(schema.possible_children(prev))})",
                    entry=f"{prev} -> {el}")
        prev = el
        gap = False

    if d.mode == "field":
        _check_field_mode(model_cls, schema, d)
    else:
        _check_record_mode(model_cls, schema, d)


def _check_field_mode(model_cls, schema, d: _Derived) -> None:
    m: M = model_cls.__match__
    anchor_kind = m.path[-1]
    for fname, b in d.bindings.items():
        f = model_cls.model_fields[fname]
        if b.span or b.capture is None:
            continue
        field_name = f.default.field if hasattr(f.default, "field") \
            and f.default.field else fname
        if not schema.has_field(anchor_kind, field_name):
            _raise(model_cls,
                   f"capture({field_name!r}) on field {fname!r}: kind "
                   f"{anchor_kind!r} has no CST field {field_name!r} (its "
                   f"fields: {sorted((schema.get(anchor_kind).fields or {}))})",
                   entry=f"{anchor_kind}.{field_name}")
        possible = schema.expand(r.type for r in
                                 schema.field_types(anchor_kind, field_name))
        _check_capture_type(model_cls, schema, fname, f.annotation,
                            f.metadata, possible, field_name, field_mode=True)


def _check_record_mode(model_cls, schema, d: _Derived) -> None:
    m: M = model_cls.__match__
    record_kind = m.path[-1]
    pair_kind = find_pair_kind(schema, record_kind, model_cls)
    value_kinds = _value_kinds(schema, pair_kind)
    for fname, b in d.bindings.items():
        f = model_cls.model_fields[fname]
        if b.span or b.capture is None:
            continue
        _check_capture_type(model_cls, schema, fname, f.annotation,
                            f.metadata, value_kinds, f"value-under-{pair_kind}")


# ---------------------------------------------------------------------------
# Job 4 — capture possible-kinds vs the field's Python type
# ---------------------------------------------------------------------------

def _check_capture_type(model_cls, schema, fname, annotation, metadata,
                        possible: set[str], where: str,
                        field_mode: bool = False) -> None:
    """Compare a capture's possible node kinds against the Python type.

    `field_mode=True` changes list[X] semantics: a field-mode list capture is
    the REPEATED field's occurrences (the field nodes themselves are the
    elements, one match each) — so list[X] is compatible when the field's
    kinds coerce to X, NOT when they are array-like (the record-mode value
    shape)."""
    override = None
    for meta in metadata:
        if meta.__class__.__name__ == "NodeKind":
            override = meta.kinds
            break

    target = _unwrap_optional(annotation)
    from typing import get_args, get_origin
    is_list = get_origin(target) is list

    if override is not None:
        # the NodeKind override is itself validated against the type
        for k in override:
            if not _kind_ok(schema, target, k):
                _raise(
                    model_cls,
                    f"field {fname!r}: NodeKind({override!r}) constrains the "
                    f"capture to kind(s) that cannot feed a {_name(target)} "
                    f"field — the {where} capture can only yield "
                    f"{sorted(override)} (numeric kinds in this grammar: "
                    f"{sorted(k for k in schema.kinds() if is_numeric_kind(k))}; "
                    f"boolean kinds: "
                    f"{sorted(k for k in schema.kinds() if is_boolean_kind(k))})",
                    entry=f"NodeKind({override}) vs {_name(target)}")
        return

    if get_origin(target) is list:
        if field_mode:
            # list[X] field-mode capture: the repeated field's nodes are the
            # elements — X-compatible when the field's kinds coerce to X
            elem = _unwrap_optional(get_args(target)[0]) \
                if get_args(target) else str
            if not _element_ok(schema, elem, possible):
                _raise(
                    model_cls,
                    f"field {fname!r} is list[{_name(elem)}] but the {where} "
                    f"capture can only ever yield {sorted(possible) or 'none'} "
                    f"(schema entry: {where})",
                    entry=where)
        else:
            compatible = compatible_kinds(schema, target, kinds=possible)
            if not compatible:
                _raise(
                    model_cls,
                    f"field {fname!r} is list[{_name(_unwrap_optional(get_args(target)[0]) if get_args(target) else str)}] "
                    f"but the {where} capture can only ever yield kinds that "
                    f"do not express it: {sorted(possible) or 'none'} "
                    f"(schema entry: {where})",
                    entry=where)
        pass  # element/array compatibility checked above
    elif target not in (str, int, float, bool):
        return  # opaque types (enums, custom) — runtime coercion decides
    else:
        compatible = compatible_kinds(schema, target, kinds=possible)
        if not compatible:
            _raise(
                model_cls,
                f"field {fname!r} is {_name(target)} but the {where} capture can "
                f"only ever yield kinds that do not coerce to it: "
                f"{sorted(possible) or 'none'} (schema entry: {where})",
                entry=where)
    if any(m.__class__.__name__ == "Unescaped" for m in metadata):
        _check_unescaped_shape(model_cls, schema, fname, target, possible,
                               where)


def _element_ok(schema, elem, kinds: set[str]) -> bool:
    """Do any of `kinds` coerce to the list element type? (field-mode lists:
    the repeated field's nodes are the elements)."""
    from .shapes import _element_shapes
    return bool(_element_shapes(schema, elem, kinds))


def _check_unescaped_shape(model_cls, schema, fname, target, possible, where):
    """Unescaped() decodes a grammar string literal's content, so the
    capture must be able to be a string WRAPPER (string -> string_content,
    not a bare identifier) — the schema-validated part of the marker."""
    from .shapes import text_shapes_for
    base = _unwrap_optional(target)
    from typing import get_args, get_origin as _go
    if _go(base) is list:
        base = _unwrap_optional(get_args(base)[0]) if get_args(base) else str
    if base is not str:
        _raise(
            model_cls,
            f"field {fname!r}: Unescaped() applies to str fields (JSON string "
            f"escape decoding), not {_name(target)}",
            entry=where)
    if not any(wrapper is not None
               for wrapper, _leaf in text_shapes_for(schema, possible)):
        _raise(
            model_cls,
            f"field {fname!r}: Unescaped() requires a string-WRAPPER capture "
            f"(a grammar string literal whose content carries escapes), but "
            f"the {where} capture can only yield {sorted(possible)}",
            entry=where)


def _kind_ok(schema, target, kind: str) -> bool:
    """Does `kind` coerce to `target` (kind-name inference, supertypes
    expanded)?"""
    expanded = schema.expand([kind])
    if target is int:
        return any(is_numeric_kind(k) for k in expanded)
    if target is float:
        return any(is_float_kind(k) or is_numeric_kind(k) for k in expanded)
    if target is bool:
        return any(is_boolean_kind(k) for k in expanded)
    if target is str:
        return any(wrapper is not None or leaf is not None
                   for wrapper, leaf in text_shapes_for(schema, expanded))
    return True


def _name(t) -> str:
    return getattr(t, "__name__", str(t))


# ---------------------------------------------------------------------------
# record-mode structure helpers (Job 3's grammar-knowledge half)
# ---------------------------------------------------------------------------

def find_pair_kind(schema, record_kind: str, model_cls=None) -> str:
    """The record kind's direct-child kind that carries key/value fields (the
    'pair' node). Raises UnsupportedShapeError if none exists."""
    children = schema.expand(r.type for r in schema.children_types(record_kind))
    candidates = [k for k in sorted(children)
                  if schema.has_field(k, "value")
                  and schema.has_field(k, "key")]
    if not candidates:
        raise UnsupportedShapeError(
            f"record mode over {record_kind!r}: no child kind of "
            f"{record_kind!r} has both 'key' and 'value' fields in the "
            f"grammar's node schema (children: {sorted(children) or 'none'})")
    return candidates[0]


def key_shape(schema, pair_kind: str):
    """The text-yielding shapes for the pair's key node. Returns a list of
    (wrapper_or_None, leaf) pairs — the caller builds the capture on the leaf
    (JSON: string -> string_content, config: identifier). Empty when no text
    shape exists."""
    kinds = schema.expand(r.type for r in schema.field_types(pair_kind, "key"))
    return text_shapes_for(schema, kinds)


# ---------------------------------------------------------------------------
# the schema-driven re-derivation (Jobs 3 + record anchoring + constraints)
# ---------------------------------------------------------------------------

def schema_derive(model_cls, schema, language_name: str) -> _Derived:
    """Build (or fetch) the schema-derived query for this model + grammar.

    Cached on the model keyed by grammar name; the base `_derived_cache` (the
    schema-less Phase-1 derivation) is untouched, so `compiled_source()`
    without a schema still shows the portable query.
    """
    cache: dict = getattr(model_cls, "_schema_derived", None)
    if cache is None:
        cache = model_cls._schema_derived = {}
    if language_name in cache:
        return cache[language_name]
    derived = _build_schema_derived(model_cls, schema)
    cache[language_name] = derived
    return derived


def _build_schema_derived(model_cls, schema) -> _Derived:
    m: M = model_cls.__match__
    base: _Derived = model_cls._derived_cache
    bindings: dict = base.bindings
    check_model_schema(model_cls, schema)
    if base.mode == "record":
        return _derive_record_schema(model_cls, schema, bindings)
    return _derive_field_schema(model_cls, schema, bindings)


def _derive_record_schema(model_cls, schema, bindings) -> _Derived:
    from .shapes import shape_for
    m: M = model_cls.__match__
    record_kind = m.path[-1]
    pair_kind = find_pair_kind(schema, record_kind, model_cls)
    key_shapes = key_shape(schema, pair_kind)
    if not key_shapes:
        raise UnsupportedShapeError(
            f"record mode over {record_kind!r}: the pair kind {pair_kind!r} "
            f"has no text-yielding key shape in the node schema")
    wrapper, leaf = key_shapes[0]
    if wrapper is not None:
        key_spec = node(wrapper).child(node(leaf).capture("key"))
    else:
        key_spec = node(leaf).capture("key")

    # outer query: anchored path capturing the record node (the suffix chain;
    # a '...' prefix is enforced by the ancestor walk at materialization)
    from .typed import _split_path
    _prefix, suffix = _split_path(m.path)
    specs = [node(k) for k in suffix]
    cur = specs[-1].capture("record")
    for s in reversed(specs[:-1]):
        cur = s.child(node=cur)
    outer = Query(cur)

    # inner query: per capture field, one anchored pattern per value shape
    patterns = []
    for fname, f in model_cls.model_fields.items():
        b: _Binding = bindings[fname]
        if b.span or b.capture is None:
            continue
        field_key = b.capture
        for vs in shape_for(f.annotation, field_key, f.metadata,
                            schema=schema, record_kind=record_kind,
                            pair_kind=pair_kind):
            spec = (node(record_kind)
                    .child(node(pair_kind)
                           .child(field="key", node=key_spec)
                           .child(field="value", node=vs)
                           .where(cap("key").eq(field_key)))
                    .capture(ANCHOR))
            for p in _predicates_for(field_key, f.metadata):
                spec.where(p)
            patterns.append(spec)

    return _Derived(mode="record",
                    query=None,
                    records=outer,
                    fields=Query(*patterns),
                    bindings=bindings,
                    record_kind=record_kind,
                    pair_kind=pair_kind,
                    match_path=m.path if "..." in m.path else None)


def _derive_field_schema(model_cls, schema, bindings) -> _Derived:
    from .shapes import _kind_set_for, text_shapes_for
    from .typed import _split_path
    m: M = model_cls.__match__
    anchor_kind = m.path[-1]
    _prefix, suffix = _split_path(m.path)
    specs = [node(k) for k in suffix]
    cur = specs[-1]

    for fname, f in model_cls.model_fields.items():
        b: _Binding = bindings[fname]
        if b.span or b.capture is None:
            continue
        field_name = f.default.field if hasattr(f.default, "field") \
            and f.default.field else fname
        possible = schema.expand(r.type for r in
                                 schema.field_types(anchor_kind, field_name))
        k = _field_constraint_kind(schema, possible, f.annotation, f.metadata)
        # query-optional when the model can materialize without the field
        # (an Optional annotation or a REAL default; `= capture(...)` is a
        # marker, not a default) — the `?` matches both shapes (the
        # schema-bound twin of typed._derive_field's Phase-6.5 fix)
        from .typed import _field_is_query_optional
        optional = _field_is_query_optional(f)
        cur.child(field=field_name, node=node(k).capture(fname),
                  quant="?" if optional else "")
        for p in _predicates_for(fname, f.metadata):
            cur.where(p)

    cur.capture(ANCHOR)
    for s in reversed(specs[:-1]):
        cur = s.child(node=cur)
    return _Derived("field", Query(cur), bindings=bindings,
                    match_path=m.path if "..." in m.path else None)


def _field_constraint_kind(schema, possible: set[str], annotation, metadata) -> str:
    """The derived node-kind for a field-mode capture: a NodeKind override if
    given; else the single compatible kind (the §2.2 'int defaults to numeric
    kinds' answer); else the wildcard. The Job-4 check has already verified a
    non-empty intersection."""
    override = None
    for meta in metadata:
        if meta.__class__.__name__ == "NodeKind":
            override = meta.kinds
            break
    if override is not None:
        return override[0]
    target = _unwrap_optional(annotation)
    compatible = _kind_set_for(schema, target, possible)
    if len(compatible) == 1:
        return next(iter(compatible))
    return "_"
