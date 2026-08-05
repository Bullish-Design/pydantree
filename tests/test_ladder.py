"""Precedence ladder tests: int mode, auto-renumbering on insert, named mode
ordering emission, and validation."""

from __future__ import annotations

import pytest

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar.ir import StrNode


def test_int_ladder_ascending_values():
    g = tg.Grammar("t")
    prec = g.precedence("or", "and", "compare", "add", "mul", "unary")
    assert prec.n("or") == 1
    assert prec.n("and") == 2
    assert prec.n("unary") == 6
    assert prec["mul"] == 5
    assert prec("add") == 4  # __call__ shorthand


def test_insert_renumbers_automatically():
    g = tg.Grammar("t")
    prec = g.precedence("or", "and", "add", "mul", "unary")
    assert prec.n("mul") == 4
    prec.insert("compare", after="and")   # or and compare add mul unary
    assert prec.n("or") == 1
    assert prec.n("and") == 2
    assert prec.n("compare") == 3
    assert prec.n("add") == 4             # renumbered automatically
    assert prec.n("mul") == 5
    assert prec.n("unary") == 6
    prec.insert("bitand", before="mul")
    assert prec.n("bitand") == 5
    assert prec.n("mul") == 6


def test_insert_validation():
    g = tg.Grammar("t")
    prec = g.precedence("a", "b")
    with pytest.raises(ValueError):
        prec.insert("a")                  # duplicate
    with pytest.raises(ValueError):
        prec.insert("c", before="a", after="b")  # both anchors
    with pytest.raises(ValueError):
        prec.insert("c", before="nope")   # unknown anchor
    with pytest.raises(KeyError):
        prec.n("nope")                    # unknown level


def test_ladder_registration_validation():
    g = tg.Grammar("t")
    with pytest.raises(ValueError):
        g.precedence()                    # empty
    with pytest.raises(ValueError):
        g.precedence("a", "a")            # duplicate


def test_ladder_prec_helpers_emit_int_nodes():
    g = tg.Grammar("t")
    prec = g.precedence("add", "mul")
    body = tg.seq(tg.ref("e"), "+", tg.ref("e"))
    from pydantree_sitter_grammar.ir import PrecLeftNode, PrecNode
    assert isinstance(prec.left("add", body).node, PrecLeftNode)
    assert prec.left("add", body).node.value == 1
    assert isinstance(prec.prec("mul", body).node, PrecNode)
    assert prec.prec("mul", body).node.value == 2


def test_named_ladder_emits_descending_ordering():
    g = tg.Grammar("t")
    prec = g.precedence("or", "and", "mul", named=True)
    assert prec.n("or") == "or"           # names, not ints
    assert prec.n("mul") == "mul"
    assert prec.ordering() == [
        StrNode(value="mul"), StrNode(value="and"), StrNode(value="or"),
    ]
    g.rule("e", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("e")))
    g.start("source_file")
    m = g.build()
    # descending: first = highest (mul binds tightest)
    assert m.precedences == [[StrNode(value="mul"), StrNode(value="and"),
                              StrNode(value="or")]]


def test_int_and_named_ladders_coexist_as_separate_orderings():
    g = tg.Grammar("t")
    a = g.precedence("x", "y", named=True)
    b = g.precedence("p", "q")
    assert a.n("x") == "x"
    assert b.n("p") == 1
    g.rule("e", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("e")))
    g.start("source_file")
    assert len(g.build().precedences) == 1  # only the named ladder emits


def test_ladder_not_in_ir_for_int_mode():
    g = tg.Grammar("t")
    g.precedence("a", "b")
    g.rule("e", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("e")))
    g.start("source_file")
    assert g.build().precedences == []    # int mode emits nothing
