"""tscore.schema tests: the node-schema models, the exact-path derivation
(derive_from_ir) vs the CLI's node-types.json (the agreement check), and the
community-path derivation (derive_from_node_types) converging on the same
format."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import tsgrammar as tg
from tscore.schema import (
    NodeSchema,
    derive_from_ir,
    derive_from_node_types,
)

TOOLCHAIN_AVAILABLE = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None


def _json_like_grammar() -> tg.Grammar:
    g = tg.Grammar("test_json_like")
    g.rule("string_content", tg.token(tg.pattern(r'[^"\\]+')))
    g.rule("escape_sequence", tg.token(tg.seq("\\", tg.pattern(r'("|\\|n)'))))
    g.rule("string", tg.seq('"', tg.repeat(tg.choice(tg.ref("string_content"),
                                                     tg.ref("escape_sequence"))), '"'))
    g.rule("true", "true")
    g.rule("false", "false")
    g.rule("number", tg.token(tg.pattern(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")))
    g.rule("value", tg.choice(tg.ref("string"), tg.ref("true"), tg.ref("false"),
                              tg.ref("number")), supertype=True)
    g.rule("pair", tg.seq(tg.field("key", tg.ref("string")), ":",
                          tg.field("value", tg.ref("value"))))
    g.rule("array", tg.seq("[", tg.repeat(tg.ref("value")), tg.opt(","), "]"))
    g.rule("source_file", tg.repeat(tg.choice(tg.ref("pair"), tg.ref("array"))))
    g.start("source_file")
    return g


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


# ---------------------------------------------------------------------------
# the agreement check (cheap check #2): derive_from_ir == CLI node-types.json
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not TOOLCHAIN_AVAILABLE, reason="CLI / gcc not on PATH")
def test_derive_from_ir_agrees_with_cli_json_like():
    model = _json_like_grammar().build()
    res = tg.build(model)
    cli = json.loads(res.node_types_json.read_text())
    mine = [t.model_dump(exclude_none=True) for t in derive_from_ir(model)]
    assert _norm(cli) == _norm(mine)


@pytest.mark.skipif(not TOOLCHAIN_AVAILABLE, reason="CLI / gcc not on PATH")
def test_derive_from_ir_agrees_with_cli_qfilter():
    sys_path_insert = None
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".scratch" / "005-tsgrammar-glr"))
    try:
        import qfilter
    finally:
        sys.path.pop(0)
    model = qfilter.build().build()
    res = tg.build(model)
    cli = json.loads(res.node_types_json.read_text())
    mine = [t.model_dump(exclude_none=True) for t in derive_from_ir(model)]
    assert _norm(cli) == _norm(mine)


# ---------------------------------------------------------------------------
# derive_from_ir content spot-checks (no toolchain needed)
# ---------------------------------------------------------------------------

def _schema_for(g) -> NodeSchema:
    return NodeSchema.from_list(derive_from_ir(g.build()))


def test_fields_and_children_derived():
    s = _schema_for(_json_like_grammar())
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
    s = _schema_for(_json_like_grammar())
    assert s.is_supertype("value")
    assert sorted(s.supertype_subtypes("value")) == ["false", "number", "string", "true"]
    # expand() replaces supertypes with subtypes
    assert s.expand(["value"]) == {"false", "number", "string", "true"}
    assert s.expand(["string"]) == {"string"}


def test_root_and_extra_and_lexical():
    s = _schema_for(_json_like_grammar())
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
    s = _schema_for(_json_like_grammar())
    assert s.is_possible_descent("source_file", "pair")
    assert s.is_possible_descent("source_file", "array")
    assert s.is_possible_descent("array", "string")
    assert not s.is_possible_descent("pair", "source_file")
    # supertypes are transparent in the CST — descent goes to the subtypes
    assert s.is_possible_descent("pair", "string")
    assert not s.is_possible_descent("pair", "value")


def test_hidden_inline_transparency():
    g = tg.Grammar("test_hidden")
    g.rule("_value", tg.choice(tg.ref("num"), tg.ref("ident")))
    g.rule("num", tg.pattern(r"\d+"))
    g.rule("ident", tg.pattern(r"[a-z]+"))
    g.rule("pair", tg.seq(tg.field("key", tg.ref("ident")), ":",
                          tg.field("value", tg.ref("_value"))))
    g.rule("source_file", tg.repeat(tg.ref("pair")))
    g.start("source_file")
    s = _schema_for(g)
    # the hidden _value does not appear as a kind; its visible children do
    assert s.get("_value") is None
    assert sorted(r.type for r in s.get("pair").fields["value"].types) == ["ident", "num"]


def test_alias_registers_visible_kind():
    g = tg.Grammar("test_alias")
    g.rule("_tuple_contents", tg.repeat(tg.ref("ident")))
    g.rule("ident", tg.pattern(r"[a-z]+"))
    g.rule("_tuple", tg.alias("tuple", True, tg.ref("_tuple_contents")))
    g.rule("source_file", tg.repeat(tg.ref("_tuple")))
    g.start("source_file")
    s = _schema_for(g)
    assert s.get("tuple") is not None
    assert s.get("_tuple") is None
    # the tuple alias kind inherits its content's children
    assert [r.type for r in s.get("tuple").children.types] == ["ident"]


def test_canonical_serialization_roundtrip():
    s = _schema_for(_json_like_grammar())
    data = s.to_list()
    s2 = NodeSchema.from_list([t.model_dump() for t in data])
    assert _norm([t.model_dump() for t in s2.to_list()]) == \
        _norm([t.model_dump() for t in data])


# ---------------------------------------------------------------------------
# the community path converges on the same format
# ---------------------------------------------------------------------------

def test_derive_from_node_types():
    s = _schema_for(_json_like_grammar())
    cli_shaped = [t.model_dump(exclude_none=True) for t in s.to_list()]
    from_path = derive_from_node_types(cli_shaped)
    assert _norm([t.model_dump() for t in from_path]) == _norm(cli_shaped)


@pytest.mark.skipif(not TOOLCHAIN_AVAILABLE, reason="CLI / gcc not on PATH")
def test_both_paths_agree_on_shared_subset():
    """The cheap check: derive_from_ir and derive_from_node_types agree on the
    shared subset (field-bearing kinds + supertype subtypes) for the same
    grammar."""
    model = _json_like_grammar().build()
    res = tg.build(model)
    cli = json.loads(res.node_types_json.read_text())
    ir_path = derive_from_ir(model)
    nt_path = derive_from_node_types(cli)
    assert _norm([t.model_dump() for t in ir_path]) == \
        _norm([t.model_dump() for t in nt_path])


# ---------------------------------------------------------------------------
# Phase 6 — the exact path over a REAL community grammar, byte-for-byte
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rust"
_MD_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "markdown"
_MDI_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "markdown-inline"


def test_derive_from_ir_byte_for_byte_over_real_rust():
    """The Phase-6 Run-2 core: `derive_from_ir` over a REAL community grammar
    we don't own (tree-sitter-rust master: 182 rules, 11 externals, hidden
    supertypes, merged aliases, reserved words) reproduces the CLI's own
    node-types.json BYTE-FOR-BYTE. This is the strongest form of the
    Phase-4 agreement check — no _norm normalization masks shape differences.
    The fixture node-types.json is the CLI 0.25.3's fresh byproduct (the
    checked-in repo one is generated by a newer CLI and differs slightly)."""
    raw = json.loads((_FIXTURES / "grammar.json").read_text())
    model = tg.GrammarModel.model_validate(raw)
    ours = NodeSchema.from_list(derive_from_ir(model), name="rust").to_json()
    cli = (_FIXTURES / "node-types.json").read_text()
    assert ours == cli


def test_byte_for_byte_serialization_shape():
    """The Phase-6 serialization-shape discovery: our node-schema.json must
    match the CLI's node-types.json emission exactly — no `fields: {}` on
    lexical/bare entries, no `root: false`/`extra: false` leakage."""
    raw = json.loads((_FIXTURES / "grammar.json").read_text())
    model = tg.GrammarModel.model_validate(raw)
    ours = NodeSchema.from_list(derive_from_ir(model), name="rust").to_json()
    assert '"root": false' not in ours
    assert '"extra": false' not in ours


def test_derive_from_ir_byte_for_byte_over_real_markdown():
    """The Phase-6.5 follow-up: `derive_from_ir` over the REAL
    tree-sitter-markdown block grammar (47 externals, hidden repeat-aux
    structures, structured-content aliases like `inline` over
    REPEAT1(choice(_line, ...)), positional children) reproduces the CLI's
    node-types.json byte-for-byte — the calibration that landed:
    hidden-rule non-top-level repeats are 0+ (the CLI's auxiliary binary-tree
    rules), and structured-content alias entries inherit their content's
    summary merged with the rule-loop contribution."""
    for fixture in (_MD_FIXTURES, _MDI_FIXTURES):
        raw = json.loads((fixture / "grammar.json").read_text())
        model = tg.GrammarModel.model_validate(raw)
        ours = NodeSchema.from_list(
            derive_from_ir(model), name=model.name).to_json()
        cli = (fixture / "node-types.json").read_text()
        assert ours == cli
