"""pydantree_sitter.schema tests: the node-schema models + consumption.

The 014 refactor killed the node_types.rs hand-port (D3): the schema's ONLY source
is the CLI's own node-types.json byproduct, tracked by construction. These
tests consume that byproduct — the checked-in `tests/fixtures/{jsonlike,
jsonlike_hidden,jsonlike_alias,rust,markdown}/node-types.json` files (real
CLI output) — and pin NodeSchema's query helpers (fields, children,
supertypes, descent, expand) and the canonical serialization round-trip.
"""

from __future__ import annotations

import json
from pathlib import Path

import pydantree_sitter_grammar as tg  # noqa: F401  (the CLI-fixture source)
from pydantree_sitter.schema import (
    NodeSchema,
    derive_from_node_types,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_RUST = _FIXTURES / "rust"


def _norm(types):
    out = {}
    for t in types:
        f = {k: (v["multiple"], v["required"],
                 tuple(sorted((r["type"], r["named"]) for r in v["types"])))
             for k, v in (t.get("fields") or {}).items()}
        ch = (t["children"]["multiple"], t["children"]["required"],
              tuple(sorted((r["type"], r["named"]) for r in t["children"]["types"]))) \
            if t.get("children") else None
        subs = tuple(sorted((r["type"], r["named"]) for r in t["subtypes"])) \
            if t.get("subtypes") else None
        out[t["type"]] = (t["named"], t.get("root", False), t.get("extra", False),
                          f, ch, subs)
    return out


def _schema_for(name: str) -> NodeSchema:
    """Load a checked-in CLI byproduct fixture (the schema IS the byproduct)."""
    return NodeSchema.from_node_types_json(_FIXTURES / name / "node-types.json",
                                           name=name)


# ---------------------------------------------------------------------------
# content spot-checks over the jsonlike CLI byproduct
# ---------------------------------------------------------------------------

def test_fields_and_children_derived():
    s = _schema_for("jsonlike")
    pair = s.get("pair")
    assert pair is not None and pair.named
    assert "key" in pair.fields and "value" in pair.fields
    # field types list the supertype (process_supertypes), not its subtypes
    assert [r.type for r in pair.fields["value"].types] == ["value"]
    assert pair.fields["key"].types[0].type == "string"
    # the record-like node: array has children from the value supertype
    arr = s.get("array")
    assert arr is not None
    assert [r.type for r in arr.children.types] == ["value"]


def test_supertype_subtypes():
    s = _schema_for("jsonlike")
    assert s.is_supertype("value")
    assert sorted(s.supertype_subtypes("value")) == ["false", "number", "string", "true"]
    # expand() replaces supertypes with subtypes
    assert s.expand(["value"]) == {"false", "number", "string", "true"}
    assert s.expand(["string"]) == {"string"}


def test_root_and_extra_and_lexical():
    s = _schema_for("jsonlike")
    assert s.get("source_file").root
    assert not s.get("pair").root
    # lexical rules: {type, named} with no fields/children
    for kind in ("string_content", "number", "true", "false"):
        t = s.get(kind)
        assert t is not None and t.named and not t.fields and t.children is None
    # anonymous tokens present
    assert not s.get('"').named
    assert not s.get(":").named


def test_possible_children_descent():
    s = _schema_for("jsonlike")
    assert s.is_possible_descent("source_file", "pair")
    assert s.is_possible_descent("source_file", "array")
    assert s.is_possible_descent("array", "string")
    assert not s.is_possible_descent("pair", "source_file")
    # supertypes are transparent in the CST — descent goes to the subtypes
    assert s.is_possible_descent("pair", "string")
    assert not s.is_possible_descent("pair", "value")


def test_hidden_inline_transparency():
    """The CLI flattens hidden rules: `_value` does not appear as a kind; its
    visible children do (the schema is the CLI byproduct, not the IR)."""
    s = _schema_for("jsonlike_hidden")
    assert s.get("_value") is None
    assert sorted(r.type for r in s.get("pair").fields["value"].types) == ["ident", "num"]


def test_alias_registers_visible_kind():
    """An alias registers the alias VALUE as the visible kind (`_tuple` is
    gone; `tuple` is a named kind in the byproduct)."""
    s = _schema_for("jsonlike_alias")
    assert s.get("tuple") is not None and s.get("tuple").named
    assert s.get("_tuple") is None


def test_canonical_serialization_roundtrip():
    s = _schema_for("jsonlike")
    data = s.to_list()
    s2 = NodeSchema.from_list([t.model_dump() for t in data])
    assert _norm([t.model_dump() for t in s2.to_list()]) == \
        _norm([t.model_dump() for t in data])


def test_from_node_types_json_handles_our_serialized_dict_form():
    """from_node_types_json accepts BOTH the raw CLI list and our
    {node_types: [...]} serialized form."""
    s = _schema_for("jsonlike")
    as_list = s.to_json()
    s1 = NodeSchema.from_node_types_json(
        _FIXTURES / "jsonlike" / "node-types.json", name="jsonlike")
    s2 = NodeSchema.from_list(json.loads(as_list), name="jsonlike")
    assert _norm([t.model_dump() for t in s1.to_list()]) == \
        _norm([t.model_dump() for t in s2.to_list()])


# ---------------------------------------------------------------------------
# derive_from_node_types (the parsing path)
# ---------------------------------------------------------------------------

def test_derive_from_node_types():
    s = _schema_for("jsonlike")
    cli_shaped = [t.model_dump(exclude_none=True) for t in s.to_list()]
    from_path = derive_from_node_types(cli_shaped)
    assert _norm([t.model_dump() for t in from_path]) == _norm(cli_shaped)


# ---------------------------------------------------------------------------
# the serialization shape over a REAL grammar (byte-for-byte round-trip)
# ---------------------------------------------------------------------------

def test_byte_for_byte_roundtrip_over_real_rust():
    """The schema IS the CLI byproduct: loading the real rust node-types.json
    and re-serializing reproduces it byte-for-byte — no `fields: {}` on
    lexical/bare entries, no `root: false`/`extra: false` leakage."""
    cli = (_RUST / "node-types.json").read_text()
    s = NodeSchema.from_node_types_json(_RUST / "node-types.json", name="rust")
    assert s.to_json() == cli
    assert '"root": false' not in s.to_json()
    assert '"extra": false' not in s.to_json()
