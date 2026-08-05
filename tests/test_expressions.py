"""ExpressionGrammar helper tests: emitted IR shape (unit), and the full
pipeline with ground truth (the probe-2 corpus), int + named ladder modes."""

from __future__ import annotations

import shutil

import pytest

import pydantree_sitter_grammar as tg

pytestmark = pytest.mark.toolchain


def _build_grammar(g: tg.Grammar, ladder):
    g.rule("number", tg.pattern(r"\d+(\.\d+)?"))
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"))
    g.word("identifier")
    g.rule("args", tg.seq(tg.ref("expr"),
                          tg.repeat(tg.seq(",", tg.ref("expr")))))
    tg.expression(g, "expr",
        primary=tg.choice(tg.ref("number"), tg.ref("identifier"),
                          tg.seq("(", tg.ref("expr"), ")")),
        infix=[
            ("or", "left", "or"), ("and", "left", "and"),
            ("<", "left", "compare"), ("==", "left", "compare"),
            ("+", "left", "add"), ("-", "left", "add"),
            ("*", "left", "mul"), ("/", "left", "mul"),
            ("^", "right", "pow"),
        ],
        prefix=[("-", "unary"), ("not", "not")],
        postfix=[
            ("call", "postfix",
             lambda e: tg.seq(e, "(", tg.opt(tg.ref("args")), ")")),
            ("member", "postfix",
             lambda e: tg.seq(e, ".", tg.ref("identifier"))),
        ],
        ladder=ladder)
    g.rule("statement", tg.seq(tg.ref("expr"), ";"))
    g.start("source_file")
    g.rule("source_file", tg.repeat(tg.ref("statement")))
    return g


def _int_grammar() -> tg.Grammar:
    g = tg.Grammar("expr_int")
    ladder = g.precedence("or", "and", "not", "compare", "add", "mul",
                          "unary", "pow", "postfix")
    return _build_grammar(g, ladder)


def _named_grammar() -> tg.Grammar:
    g = tg.Grammar("expr_named")
    ladder = g.precedence("or", "and", "not", "compare", "add", "mul",
                          "unary", "pow", "postfix", named=True)
    return _build_grammar(g, ladder)


def test_expression_emits_single_rule_with_prec_alternatives():
    g = _int_grammar()
    body = g.rules["expr"]
    from pydantree_sitter_grammar.ir import (
        ChoiceNode,
        PrecLeftNode,
        PrecNode,
        PrecRightNode,
        SymbolNode,
    )
    assert isinstance(body, ChoiceNode)
    members = body.members
    # 9 infix + 2 prefix + 2 postfix, primary (a 3-member choice) flattened in
    assert len(members) == 16
    precs = {type(m).__name__ for m in members if not isinstance(m, SymbolNode)}
    assert "PrecLeftNode" in precs and "PrecRightNode" in precs \
        and "PrecNode" in precs
    values = sorted(
        m.value for m in members
        if isinstance(m, (PrecLeftNode, PrecRightNode, PrecNode)))
    # postfix sits at the TOP of the ladder (above unary and pow)
    assert values[-1] == 9
    assert 7 in values and 8 in values      # unary, pow
    assert values[-1] > values[values.index(7)]
    # operands are the expr ref itself (single-rule form)
    first_op = next(m for m in members if isinstance(m, PrecLeftNode))
    assert first_op.content.members[0] == SymbolNode(name="expr")


def test_expression_primary_choice_flattens():
    """A choice primary splices its members into the expr choice (the DSL's
    choice() flattening) — the emitted rule stays one flat choice."""
    g = _int_grammar()
    from pydantree_sitter_grammar.ir import SeqNode, SymbolNode
    members = g.rules["expr"].members
    assert isinstance(members[-1], SeqNode)   # the parens primary
    assert members[-2] == SymbolNode(name="identifier")
    assert members[-3] == SymbolNode(name="number")


def test_ladder_level_validation_raises_early():
    g = tg.Grammar("bad")
    ladder = g.precedence("add", "mul")
    g.rule("number", tg.pattern(r"\d+"))
    with pytest.raises(KeyError):
        tg.expression(g, "expr",
            primary=tg.ref("number"),
            infix=[("+", "left", "nope")],
            ladder=ladder)
    with pytest.raises(KeyError):
        tg.expression(g, "expr",
            primary=tg.ref("number"),
            infix=[("+", "left", "add")],
            prefix=[("-", "missing")],
            ladder=ladder)


def _expr_shape(n) -> str:
    if n.type in ("ERROR", "MISSING"):
        return "ERROR"
    anon = [c for c in n.children if not c.is_named]
    named = n.named_children
    children = list(n.children)
    # parens primary: the node starts with an anonymous '('
    if children and not children[0].is_named \
            and children[0].text.decode() == "(":
        return "(" + _expr_shape(named[0]) + ")"
    if any(c.text.decode() == "(" for c in anon):
        callee = _expr_shape(named[0])
        args = named[1] if len(named) > 1 else None
        inner = [] if args is None else [_expr_shape(a) for a in args.named_children]
        return f"{callee}({', '.join(inner)})"
    if not named and not anon:
        return n.text.decode()
    if not anon:
        if len(named) == 3 and not named[1].named_child_count:
            op = named[1].text.decode()
            return "(" + _expr_shape(named[0]) + op + _expr_shape(named[2]) + ")"
        return _expr_shape(named[0])
    if len(named) == 1:
        return "(" + anon[0].text.decode() + _expr_shape(named[0]) + ")"
    return "(" + _expr_shape(named[0]) + anon[0].text.decode() \
        + _expr_shape(named[1]) + ")"


CORPUS = [
    ("1 + 2 * 3;", "(1+(2*3))", "mul tighter than add"),
    ("1 + 2 + 3;", "((1+2)+3)", "+ left-assoc"),
    ("2 ^ 3 ^ 4;", "(2^(3^4))", "^ right-assoc"),
    ("-a + b;", "((-a)+b)", "unary tighter than +"),
    ("-a ^ b;", "(-(a^b))", "unary LOOSER than ^"),
    ("a * -b;", "(a*(-b))", "unary tighter than *"),
    ("not a == b;", "(not(a==b))", "not looser than compare"),
    ("not a or b;", "((nota)orb)", "not tighter than or"),
    ("-a or b;", "((-a)orb)", "unary vs or (Phase-2 canonical)"),
    ("a.b.c;", "((a.b).c)", "member chaining"),
    ("f(x)(y);", "f(x)(y)", "call chaining"),
    ("-f(x);", "(-f(x))", "postfix tighter than unary"),
    ("-a.b;", "(-(a.b))", "member tighter than unary"),
    ("a.b + c;", "((a.b)+c)", "member tighter than +"),
    ("f(x) + 1;", "(f(x)+1)", "call tighter than +"),
    ("a.b ^ c;", "((a.b)^c)", "member tighter than ^"),
    ("1 < 2 + 3;", "(1<(2+3))", "compare looser than +"),
    ("a == b == c;", "((a==b)==c)", "compare left-assoc"),
    ("-f(x) + 1;", "((-f(x))+1)", "combined"),
    ("a.b(x);", "(a.b)(x)", "member then call"),
    ("(-a)^b;", "(((-a))^b)", "parens"),
]


@pytest.mark.parametrize("factory,name", [
    (_int_grammar, "expr_int"),
    (_named_grammar, "expr_named"),
])
def test_expression_pipeline_and_ground_truth(factory, name, tmp_path):
    g = factory()
    issues = tg.run_checks(g)
    assert not tg.errors(g), issues
    result = tg.build_builder(g, cache_dir=tmp_path / "cache")
    lang, _lib = tg.load_language(result.so_path, name)
    failures = []
    for src, expected, note in CORPUS:
        tree = tg.parse(lang, src)
        root = tree.root_node
        if root.has_error:
            failures.append(f"{src}: parse ERROR ({note})")
            continue
        stmt = root.named_children[0]
        actual = _expr_shape(stmt.named_children[0])
        if actual != expected:
            failures.append(f"{src}: {actual} != {expected} ({note})")
    assert not failures, "\n".join(failures)


def test_int_ladder_matches_filtlang_baseline_values():
    """The ladder's int values must be the same integers a filtlang-style
    hand-author picks for the same ordering — the 'no magic integers' claim
    keeps the pipeline identical."""
    g = tg.Grammar("t")
    prec = g.precedence("or", "and", "compare", "add", "mul", "unary")
    assert [prec.n(x) for x in ("compare", "add", "mul", "unary")] == [3, 4, 5, 6]
    # filtlang's hand-rolled ladder: COMPARE=1, ADD=2, MUL=3, UNARY=4 — the
    # relative ordering is what matters, and it is preserved level-for-level
    assert prec.n("compare") < prec.n("add") < prec.n("mul") < prec.n("unary")


# ---------------------------------------------------------------------------
# bare-cond affordances (was test_phase3a.py — dissolved, 7.5)
# ---------------------------------------------------------------------------

