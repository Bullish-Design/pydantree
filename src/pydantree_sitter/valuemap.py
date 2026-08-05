"""pydantree_sitter.valuemap — declared value shapes (014 §4.4, D6).

Value shapes are DECLARED DATA, not name-regex inference. A `ValueMap`
declares, per node kind, its scalar meaning / wrapper leaf / array element
kinds. Record-mode compilation consumes ONLY (schema, ValueMap).

    class ValueMap(BaseModel):
        format_version: int = 1
        scalars:  dict[str, Literal["int", "float", "bool", "str", "null"]]
                  # {"number": "float", "true": "bool"}
        wrappers: dict[str, str]      # wrapper kind -> text-leaf kind
                                      # {"string": "string_content"}
        arrays:   dict[str, list[str]]  # array kind -> element kinds

`JSON_VALUE_MAP` replicates the pre-refactor hardcoded JSON behavior
(reviewed, not re-derived). `propose_value_map(schema)` is THE old name-regex
heuristic, demoted to a DRAFT generator: the user inspects and commits the
result — never silent inference in the trusted path.
"""

from __future__ import annotations

import re
from typing import Literal, get_args, get_origin

from .spec import unwrap_optional

from pydantic import BaseModel, Field

from .schema import NodeSchema

Scalar = Literal["int", "float", "bool", "str", "null"]
_SCALARS = ("int", "float", "bool", "str", "null")


class ValueMap(BaseModel):
    """Declared value shapes: node kind -> scalar meaning / wrapper leaf /
    array element kinds (014 D6)."""

    format_version: int = 1
    scalars: dict[str, Scalar] = Field(default_factory=dict)
    wrappers: dict[str, str] = Field(default_factory=dict)
    arrays: dict[str, list[str]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# the JSON builtin (replicates the pre-refactor hardcoded JSON v1 map)
# ---------------------------------------------------------------------------

JSON_VALUE_MAP = ValueMap(
    scalars={
        "number": "int",   # numeric: feeds int AND float (int->int, float->float+int)
        "true": "bool",
        "false": "bool",
    },
    wrappers={
        "string": "string_content",
    },
    arrays={
        "array": ["string", "number", "true", "false", "array", "object"],
    },
)

# the documented JSON kind set (schema-less record mode = JSON_VALUE_MAP +
# these kinds, stated here so the fallback is a fact, not a guess)
JSON_KINDS = {
    "document", "object", "pair", "array", "string", "string_content",
    "number", "true", "false",
}
# the JSON core a schema must contain to count as JSON-family (exact
# set-membership check; extras like escape_sequence don't disqualify)
JSON_CORE = {
    "document", "object", "pair", "array", "string", "string_content",
    "number", "true", "false",
}


def looks_like_json(schema: NodeSchema) -> bool:
    """Exact kind-set check (no name regex): does the schema contain the
    JSON core kinds? A grammar with ALL of document/object/pair/array/
    string/string_content/number/true/false is the JSON family; extra rules
    (escape_sequence etc.) don't disqualify it."""
    kinds = schema.named_kinds()
    return JSON_CORE <= kinds


# ---------------------------------------------------------------------------
# propose_value_map — the demoted heuristic, as a DRAFT generator
# ---------------------------------------------------------------------------

_NUMERIC_NAME = re.compile(r"(number|numeric|integer|int|real|decimal|count)\b", re.I)
_FLOAT_NAME = re.compile(r"(float|double|real|decimal|number)", re.I)
_BOOL_NAME = re.compile(r"(true|false|boolean|bool)\b", re.I)
_ARRAY_NAME = re.compile(r"(array|list|sequence|vector|slice)", re.I)
_NULL_NAME = re.compile(r"^(null|none|nil|undefined)$", re.I)


def _is_numeric(kind: str) -> bool:
    return bool(_NUMERIC_NAME.search(kind))


def _is_float(kind: str) -> bool:
    return bool(_FLOAT_NAME.search(kind))


def _is_boolean(kind: str) -> bool:
    return bool(_BOOL_NAME.search(kind))


def _is_array(kind: str) -> bool:
    return bool(_ARRAY_NAME.search(kind))


def _is_null(kind: str) -> bool:
    return bool(_NULL_NAME.match(kind))


def _text_leaf_kind(schema: NodeSchema, kind: str) -> str | None:
    """If `kind` is a text-yielding leaf (no children/fields, or an
    anonymous literal), return it; else None. Supertypes are transparent."""
    t = schema.get(kind)
    if t is None or schema.is_supertype(kind):
        return None
    if not t.named:
        return kind
    if t.fields:
        return None
    if t.children is not None and t.children.types:
        return None
    return kind


def _wrapper_text_leaf(schema: NodeSchema, kind: str) -> str | None:
    """If `kind` is a wrapper whose children include text-yielding leaves
    (string -> string_content), return the leaf to capture. Prefers a
    content-like leaf (string_content) over structural leaves."""
    t = schema.get(kind)
    if t is None or not t.named or t.children is None:
        return None
    leaves = [r.type for r in t.children.types
              if r.named and _text_leaf_kind(schema, r.type) is not None]
    if not leaves:
        return None
    for preferred in ("string_content", "content", "text"):
        if preferred in leaves:
            return preferred
    return leaves[0]


def propose_value_map(schema: NodeSchema) -> ValueMap:
    """Generate a DRAFT ValueMap for `schema` using the old name-regex +
    structural heuristics. This is a proposal the user inspects and commits
    (D6) — it is never applied silently.

    Heuristic (documented, not per-grammar): a kind's scalar meaning comes
    from its NAME (number→int/float, true/false→bool, null-ish→null); kinds
    with no children/fields and a non-primitive name are text leaves (str);
    kinds whose children include a text leaf are wrappers; array-ish kinds
    map to their named children.
    """
    scalars: dict[str, str] = {}
    wrappers: dict[str, str] = {}
    arrays: dict[str, list[str]] = {}

    for kind in sorted(schema.kinds()):
        t = schema.get(kind)
        if t is None or schema.is_supertype(kind):
            continue
        if _is_array(kind) and t.children is not None:
            arrays[kind] = [r.type for r in t.children.types if r.named]
            continue
        if _is_boolean(kind):
            scalars[kind] = "bool"
            continue
        if _is_numeric(kind):
            # numeric kinds feed int AND float (int accepts int; float
            # accepts float+int) — the old schema-driven shapes semantics
            scalars[kind] = "int"
            continue
        if _is_float(kind):
            scalars[kind] = "float"
            continue
        if _is_null(kind):
            scalars[kind] = "null"
            continue
        leaf = _text_leaf_kind(schema, kind)
        if leaf is not None:
            scalars[kind] = "str"
            continue
        inner = _wrapper_text_leaf(schema, kind)
        if inner is not None:
            wrappers[kind] = inner
            continue
        # unnamed structural kinds (objects, sequences, ...) carry no shape
    return ValueMap(scalars=scalars, wrappers=wrappers, arrays=arrays)


# ---------------------------------------------------------------------------
# the compilation-side lookup (consumed ONLY by compiler.py)
# ---------------------------------------------------------------------------

def scalar_kinds_for(map: ValueMap, target) -> list[str]:
    """The node kinds whose scalar meaning coerces to `target`
    (int accepts int+float; float accepts float+int; str/bool exact)."""
    wanted = _wanted_scalars(target)
    return sorted(k for k, s in map.scalars.items() if s in wanted)


def _wanted_scalars(target) -> set[str]:
    base = target
    origin = get_origin(base)
    if origin is list:
        args = get_args(base)
        base = args[0] if args else str
    if base is int:
        return {"int"}          # int does NOT accept float-only kinds
    if base is float:
        return {"float", "int"}
    if base is bool:
        return {"bool"}
    if base is str:
        return {"str"}
    return set()


def wrapper_kinds_for(map: ValueMap) -> list[str]:
    """The wrapper kinds (in sorted order — deterministic emission)."""
    return sorted(map.wrappers)


def array_kinds_for(schema, map: ValueMap, annotation) -> list[str]:
    """The array kinds whose element kinds contain a shape for `target`'s
    element type (supertypes expanded against the schema when bound)."""
    base = annotation
    origin = get_origin(base)
    if origin is not list:
        return []
    args = get_args(base)
    elem = args[0] if args else str
    out = []
    for arr, elements in sorted(map.arrays.items()):
        expanded = set()
        for e in elements:
            if schema is not None:
                expanded |= schema.expand([e])
            else:
                expanded.add(e)
        if _wanted_scalars(elem) & {map.scalars.get(e, "") for e in expanded}:
            out.append(arr)
            continue
        if unwrap_optional(elem) is str and any(e in map.wrappers for e in expanded):
            out.append(arr)
    return out
