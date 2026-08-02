"""Builder DSL tests: combinators, operator sugar, definition-site recording,
start-rule ordering, and grammar-level options."""

from __future__ import annotations

import json

import pytest

import tsgrammar as tg
from tsgrammar.grammar import (
    AliasNode, BlankNode, ChoiceNode, FieldNode, PatternNode, RepeatNode,
    SeqNode, StrNode, SymbolNode, TokenNode,
)


def test_operator_sugar_and_flattening():
    a = tg.seq(tg.ref("x"), "+") + tg.ref("y")      # seq flattens
    assert isinstance(a.node, SeqNode)
    assert len(a.node.members) == 3
    c = (tg.ref("x") | tg.pattern(r"\d+")) | tg.ref("y")
    assert isinstance(c.node, ChoiceNode)
    assert len(c.node.members) == 3
    assert isinstance(tg.ref("x").star().node, RepeatNode)
    assert isinstance(tg.opt("a").node, ChoiceNode)
    assert isinstance(tg.opt("a").node.members[1], BlankNode)
    from tsgrammar.grammar import Repeat1Node
    assert isinstance(tg.ref("x").plus().node, Repeat1Node)


def test_str_becomes_string():
    from tsgrammar.builder import as_node
    assert as_node(";") == StrNode(value=";")
    with pytest.raises(TypeError):
        as_node(42)


def test_definition_site_recording():
    g = tg.Grammar("t")
    g.rule("number", tg.pattern(r"\d+"))
    site = g.site("number")
    assert site.file.endswith("test_builder.py")
    assert "g.rule(\"number\"" in site.source
    assert site.lineno > 0


def test_duplicate_rule_raises():
    g = tg.Grammar("t")
    g.rule("a", tg.pattern(r"\d+"))
    with pytest.raises(ValueError):
        g.rule("a", tg.pattern(r"\d+"))


def test_start_rule_emitted_first():
    g = tg.Grammar("t")
    g.rule("a", tg.pattern(r"\d+"))
    g.rule("b", tg.pattern(r"\w+"))
    g.rule("source_file", tg.repeat(tg.ref("a")))
    g.start("source_file")
    model = g.build()
    assert list(model.rules)[0] == "source_file"
    assert model.start_rule == "source_file"
    # default start is source_file even without explicit start()
    g2 = tg.Grammar("t2")
    g2.rule("a", tg.pattern(r"\d+"))
    g2.rule("source_file", tg.repeat(tg.ref("a")))
    assert g2.build().start_rule == "source_file"


def test_hidden_renames_and_inline_supertype():
    g = tg.Grammar("t")
    g.rule("name", tg.pattern(r"\w+"))
    g.rule("stmt", tg.repeat(tg.ref("name")), hidden=True, inline=True)
    g.rule("statement", tg.ref("_stmt"), supertype=True)
    g.rule("source_file", tg.repeat(tg.ref("statement")))
    g.start("source_file")
    m = g.build()
    assert "_stmt" in m.rules
    assert m.inline == ["_stmt"]
    assert m.supertypes == ["statement"]


def test_grammar_level_options():
    g = tg.Grammar("t")
    g.rule("comment", tg.token(tg.seq("//", tg.pattern(r"[^\n]*"))))
    g.rule("identifier", tg.pattern(r"\w+"))
    g.rule("source_file", tg.repeat(tg.ref("identifier")))
    g.start("source_file")
    g.word("identifier")
    g.extra(tg.pattern(r"\s"))
    g.extra(tg.ref("comment"))
    g.conflict("x", "y")
    g.precedence_ordering("and", "or")
    g.external(tg.ref("TERM"))
    g.reserved_word("ctx", tg.ref("identifier"))
    m = g.build()
    assert m.word == "identifier"
    assert len(m.extras) == 2
    assert m.conflicts == [["x", "y"]]
    assert m.precedences == [[StrNode(value="and"), StrNode(value="or")]]
    assert m.externals == [SymbolNode(name="TERM")]
    assert m.reserved == {"ctx": [SymbolNode(name="identifier")]}


def test_emit_json_roundtrip_through_ir():
    g = tg.Grammar("t")
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("number")))
    g.start("source_file")
    model = g.build()
    restored = tg.GrammarModel.model_validate_json(model.model_dump_json())
    assert restored == model
    assert json.loads(model.model_dump_json(exclude_none=True))["rules"]["number"] \
        == {"type": "PATTERN", "value": r"\d+"}


def test_alias_and_token_and_field_helpers():
    assert isinstance(tg.token("a").node, TokenNode)
    assert tg.tok("a").node == tg.token("a").node
    assert isinstance(tg.field("f", "a").node, FieldNode)
    assert isinstance(tg.alias("x", True, tg.ref("y")).node, AliasNode)
    assert isinstance(tg.ref("x").capture("f").node, FieldNode)


def test_opt_is_choice_blank():
    node = tg.opt(tg.ref("x")).node
    assert isinstance(node, ChoiceNode)
    assert node.members[0] == SymbolNode(name="x")
    assert isinstance(node.members[1], BlankNode)
