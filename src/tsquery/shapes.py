"""tsquery.shapes — Job 3: the record value-shape derivation (Phase 4).

Replaces spike-a2's hardcoded `_json_value_specs` (a JSON-grammar-shaped
table) with a lookup that derives the shape from the node-schema:

    shape_for(field_type, capture_name, metadata, schema, record_kind,
              pair_kind) -> list[NodeSpec]

For a record-mode field, we find the grammar's node kind(s) that (a) coerce
to the Python type and (b) actually occur as a value under the record's pair
node — derived, not hardcoded. `NodeKind` stays as the typed override.

The (a) half is a small, documented KIND-NAME inference (the grammar's node
kinds carry no type information; "number"→int is a name convention, not a
fact — this is the spike-a2 §2.2 question, decided by the schema):

    int   -> kinds named like number/integer/int/...
    float -> float-ish kinds ∪ int-ish kinds (float coerces "3" too)
    bool  -> kinds named true/false/boolean/bool/...
    str   -> text-yielding kinds that are NOT clearly another primitive
             (numeric/boolean/null kinds are excluded, so JSON's `str` maps
             to string_content exactly like the v1 map, while a config
             grammar's identifier still qualifies)
    list[X] -> array-ish kinds (array/list/sequence/...) whose children
             contain a shape(X) kind (the element shape is the SAME
             top-level shape logic, restricted to the array's children)

The (b) half is the grammar knowledge: the candidate kinds are restricted to
the pair node's `value` field types (supertypes expanded), so the derivation
works over any grammar and reproduces the spike-a2 JSON v1 map over
tree_sitter_json (verified in the Phase-4 experiment).

An empty selection raises UnsupportedShapeError citing the schema entry —
the Run-2 planted failure for a field type with no derivable shape.
"""

from __future__ import annotations

import re
from typing import get_args, get_origin

from .dsl import NodeSpec, node
from .typed import NodeKind, UnsupportedShapeError, _unwrap_optional

# --------------------------------------------------------------------------
# the kind-name inference (documented, not per-grammar)
# --------------------------------------------------------------------------

_NUMERIC_NAME = re.compile(r"(number|numeric|integer|int|real|decimal|count)\b", re.I)
_FLOAT_NAME = re.compile(r"(float|double|real|decimal|number)", re.I)
_BOOL_NAME = re.compile(r"(true|false|boolean|bool)\b", re.I)
_ARRAY_NAME = re.compile(r"(array|list|sequence|vector|slice)", re.I)
_NULL_NAME = re.compile(r"^(null|none|nil|undefined)$", re.I)


def is_numeric_kind(kind: str) -> bool:
    return bool(_NUMERIC_NAME.search(kind))


def is_float_kind(kind: str) -> bool:
    return bool(_FLOAT_NAME.search(kind))


def is_boolean_kind(kind: str) -> bool:
    return bool(_BOOL_NAME.search(kind))


def is_array_kind(kind: str) -> bool:
    return bool(_ARRAY_NAME.search(kind))


def is_null_kind(kind: str) -> bool:
    return bool(_NULL_NAME.match(kind))


def text_leaf_kind(schema, kind: str) -> str | None:
    """If `kind` is a text-yielding leaf, return it; else None. A leaf is a
    kind with no children and no fields (number, identifier, string_content…)
    OR an anonymous literal token (its text IS the token). Supertypes are
    transparent — they never appear in the CST."""
    t = schema.get(kind)
    if t is None:
        return None
    if schema.is_supertype(kind):
        return None
    if not t.named:
        return kind  # anonymous literal: text-yielding by definition
    if t.fields:
        return None
    if t.children is not None and t.children.types:
        return None
    return kind


def wrapper_text_leaf(schema, kind: str) -> str | None:
    """If `kind` is a wrapper whose children include text-yielding leaves
    (string -> string_content), return the leaf to capture. Prefers a
    content-like leaf (string_content) over structural leaves
    (escape_sequence) — the spike-a2 v1 map's `string_content` convention,
    which Python's strings share."""
    t = schema.get(kind)
    if t is None or not t.named:
        return None
    if t.children is None:
        return None
    leaves = [r.type for r in t.children.types
              if r.named and text_leaf_kind(schema, r.type) is not None]
    if not leaves:
        return None
    for preferred in ("string_content", "content", "text"):
        if preferred in leaves:
            return preferred
    return leaves[0]


def text_shapes_for(schema, kinds: set[str]) -> list[tuple[str | None, str]]:
    """The text-yielding shapes among `kinds`: (wrapper_or_None, leaf).
    Excludes kinds that are clearly another primitive (numeric/boolean/null),
    so JSON `str` maps to string_content — exactly the v1 map."""
    out = []
    for k in sorted(kinds):
        if is_numeric_kind(k) or is_float_kind(k) or is_boolean_kind(k) or is_null_kind(k):
            continue
        leaf = text_leaf_kind(schema, k)
        if leaf is not None:
            out.append((None, k))
            continue
        inner = wrapper_text_leaf(schema, k)
        if inner is not None:
            out.append((k, inner))
    return out


# --------------------------------------------------------------------------
# the element-shape logic (shared by top-level fields and list elements)
# --------------------------------------------------------------------------

def _element_shapes(schema, base, kinds: set[str]) -> list[tuple]:
    """The shape descriptors for `base` among `kinds`: ("leaf", kind) or
    ("wrap", wrapper, leaf). Empty when `base` has no shape there."""
    if base is str:
        return [("leaf", leaf) if wrapper is None else ("wrap", wrapper, leaf)
                for wrapper, leaf in text_shapes_for(schema, kinds)]
    if base is int:
        return [("leaf", k) for k in sorted(kinds) if is_numeric_kind(k)]
    if base is float:
        return [("leaf", k) for k in sorted(kinds)
                if is_float_kind(k) or is_numeric_kind(k)]
    if base is bool:
        return [("leaf", k) for k in sorted(kinds) if is_boolean_kind(k)]
    return []


def _build_shape(desc: tuple, cap_name: str) -> NodeSpec:
    """A NodeSpec for a shape descriptor, with the capture on the leaf."""
    if desc[0] == "leaf":
        return node(desc[1]).capture(cap_name)
    _, wrapper, leaf = desc
    return node(wrapper).child(node(leaf).capture(cap_name))


# --------------------------------------------------------------------------
# the derivation
# --------------------------------------------------------------------------

def _node_kinds_override(metadata):
    for m in metadata:
        if isinstance(m, NodeKind):
            return m.kinds
    return None


def shape_for(target, cap_name: str, metadata, *, schema,
              record_kind: str, pair_kind: str) -> list[NodeSpec]:
    """Derive the value-node shape(s) for a record-mode field.

    Returns one NodeSpec per emitted pattern (bool/alternation -> multiple).
    Raises UnsupportedShapeError when the grammar's value kinds cannot express
    the Python type (Run-2 failure #3).
    """
    base = _unwrap_optional(target)
    # nested OutputModel fields capture the value node wholesale
    if isinstance(base, type) and base is not type(None) \
            and hasattr(base, "_derived_cache"):
        return [node(None).capture(cap_name)]

    override = _node_kinds_override(metadata)
    if override is not None:
        return [node(k).capture(cap_name) for k in override]

    value_kinds = _value_kinds(schema, pair_kind)

    base = _unwrap_optional(target)
    if _has_unescaped(metadata):
        # Unescaped(): capture the string WRAPPER wholesale — an escaped
        # string's content is split across string_content pieces by the
        # escape_sequence rule, so leaf captures would split the value. The
        # wrapper's text (with quotes) is unescaped at materialization.
        shapes = _unescaped_shapes(schema, base, cap_name, value_kinds)
        if not shapes:
            raise UnsupportedShapeError(
                f"field type {_name(base)} with Unescaped() has no "
                f"string-wrapper shape in grammar {schema.name or '?'}: "
                f"the value kinds under {pair_kind!r} "
                f"({sorted(value_kinds) or 'none'}) contain no string "
                f"wrapper (schema entry: {pair_kind!r} value field)")
        return shapes

    origin = get_origin(base)
    if origin is list:
        elem = get_args(base)[0] if get_args(base) else str
        elem = _unwrap_optional(elem)
        shapes = _list_shapes(schema, elem, cap_name, value_kinds)
        if not shapes:
            raise UnsupportedShapeError(
                f"field type list[{_name(elem)}] has no derivable shape in "
                f"grammar {schema.name or '?'}: the value kinds under "
                f"{pair_kind!r} ({sorted(value_kinds) or 'none'}) contain no "
                f"array-like kind whose children express {_name(elem)} "
                f"(schema entry: {pair_kind!r} value field)")
        return shapes

    if base in (str, int, float, bool):
        shapes = [_build_shape(d, cap_name)
                  for d in _element_shapes(schema, base, value_kinds)]
        if not shapes:
            raise UnsupportedShapeError(
                f"field type {_name(base)} has no derivable shape in grammar "
                f"{schema.name or '?'}: the value kinds under {pair_kind!r} "
                f"({sorted(value_kinds) or 'none'}) contain no {_name(base)}"
                f"-compatible kind (schema entry: {pair_kind!r} value field; "
                f"use Annotated[..., NodeKind(...)] to declare it)")
        return shapes

    raise UnsupportedShapeError(
        f"field type {_name(base)} has no derivable shape (use "
        f"Annotated[..., NodeKind(...)] to declare it)")


def _has_unescaped(metadata) -> bool:
    return any(m.__class__.__name__ == "Unescaped" for m in metadata)


def _unescaped_shapes(schema, base, cap_name: str,
                      value_kinds: set[str]) -> list[NodeSpec]:
    """String-WRAPPER shapes for Unescaped() fields: the wrapper node is
    captured wholesale (escaped content can't split across string_content
    pieces). list[str] -> the array's string-wrapper children."""
    if base is str:
        return [node(wrapper).capture(cap_name)
                for wrapper, leaf in text_shapes_for(schema, value_kinds)
                if wrapper is not None]
    if get_origin(base) is list:
        elem = get_args(base)[0] if get_args(base) else str
        elem = _unwrap_optional(elem)
        if elem is str:
            out = []
            for arr in sorted(value_kinds):
                if not is_array_kind(arr):
                    continue
                child_kinds = schema.expand(r.type
                                            for r in schema.children_types(arr))
                for wrapper, leaf in text_shapes_for(schema, child_kinds):
                    if wrapper is not None:
                        out.append(node(arr).child(
                            node(wrapper).capture(cap_name)))
            return out
    return []


def _list_shapes(schema, elem, cap_name: str, value_kinds: set[str]) -> list[NodeSpec]:
    """Shapes for list[X]: array-like value kinds whose children express X
    (the element shape is the top-level X shape restricted to the array's
    children — so list[str] over JSON is `(array (string (string_content)
    @cap))`, exactly the v1 map)."""
    shapes = []
    for arr in sorted(value_kinds):
        if not is_array_kind(arr):
            continue
        child_kinds = schema.expand(r.type for r in schema.children_types(arr))
        for desc in _element_shapes(schema, elem, child_kinds):
            shapes.append(node(arr).child(_build_shape(desc, cap_name)))
    return shapes


def _value_kinds(schema, pair_kind: str) -> set[str]:
    """The kinds that can occur as a value under the pair node (supertype
    expanded) — the grammar-knowledge half of the derivation."""
    refs = schema.field_types(pair_kind, "value")
    return schema.expand(r.type for r in refs)


def compatible_kinds(schema, target, *, kinds: set[str]) -> set[str]:
    """The kinds among `kinds` that coerce to the Python type (Job 4's
    intersection). Supertype expansion is the caller's job."""
    base = _unwrap_optional(target)
    origin = get_origin(base)
    if origin is list:
        elem = _unwrap_optional(get_args(base)[0]) if get_args(base) else str
        out = set()
        for arr in {k for k in kinds if is_array_kind(k)}:
            child = schema.expand(r.type for r in schema.children_types(arr))
            if _element_shapes(schema, elem, child):
                out.add(arr)
        return out
    return {k for k in kinds if _kind_ok(schema, base, k)}


def _kind_set_for(schema, base, kinds: set[str]) -> set[str]:
    """The kinds in `kinds` that coerce to `base` (the (a) half)."""
    out = set()
    for desc in _element_shapes(schema, base, kinds):
        if desc[0] == "leaf":
            out.add(desc[1])
        else:
            out.add(desc[1])  # the wrapper kind
    return out


def _kind_ok(schema, base, kind: str) -> bool:
    return bool(_element_shapes(schema, base, schema.expand([kind])))


def _name(t) -> str:
    return getattr(t, "__name__", str(t))
