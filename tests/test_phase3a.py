"""Phase-3A hardening tests: the ExpressionGrammar semantic-smoke corpus (the
systematic guard for the Phase-3 §4 semantic-intent leak) and the
cond_primary=/cond_drops= affordance (the typed spelling for the postfix ×
bare-cond-`if` interaction)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

import tsgrammar as tg
from tsgrammar.expressions import (
    DEFAULT_PRECEDENCE_CORPUS,
    semantic_smoke,
)

TOOLCHAIN_AVAILABLE = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None

pytestmark = pytest.mark.skipif(
    not TOOLCHAIN_AVAILABLE, reason="tree-sitter CLI / gcc not on PATH")

QFILTER_DIR = Path(__file__).resolve().parents[1] / ".scratch" / "005-tsgrammar-glr"
sys.path.insert(0, str(QFILTER_DIR))


# ---------------------------------------------------------------------------
# semantic smoke
# ---------------------------------------------------------------------------

def _qfilter_grammar():
    import qfilter
    return qfilter.build()


def test_semantic_smoke_passes_on_qfilter():
    import qfilter
    g = qfilter.build()
    failures = semantic_smoke(g)
    assert failures == [], failures


def test_semantic_smoke_catches_a_ladder_reorder():
    """A ladder with the unary ABOVE pow makes `-a ^ b` silently parse as
    `(-a)^b` (generates clean, semantically wrong — the Phase-3 §4 leak).
    The smoke corpus pins the author-chosen `-(a^b)` and catches it."""
    g = tg.Grammar("wrongladder")
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("identifier", tg.pattern(r"[a-z]+"), word=True)
    prec = g.precedence("or", "add", "pow", "unary")  # unary TIGHTER than pow
    tg.expression(g, "expr",
                  primary=tg.choice(tg.ref("number"), tg.ref("identifier")),
                  infix=[("^", "right", "pow"), ("+", "left", "add"),
                         ("or", "left", "or")],
                  prefix=[("-", "unary")],
                  ladder=prec)
    g.rule("stmt", tg.seq(tg.ref("expr"), ";"))
    g.rule("source_file", tg.repeat(tg.ref("stmt")))
    g.start("source_file")
    failures = semantic_smoke(g)
    assert any("'-a ^ b;'" in f for f in failures), failures


# ---------------------------------------------------------------------------
# cond_primary: the postfix × bare-cond-`if` affordance
# ---------------------------------------------------------------------------

def _cond_grammar(*, cond_primary) -> tg.Grammar:
    g = tg.Grammar("condlang")
    g.rule("identifier", tg.pattern(r"[a-z]+"), word=True)
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("string", tg.token(tg.seq('"', tg.pattern(r'[^"\\]*'), '"')))
    primary = tg.choice(tg.ref("number"), tg.ref("string"),
                        tg.ref("identifier"), tg.seq("(", tg.ref("expr"), ")"))
    prec = g.precedence("or", "and", "not", "compare", "add", "mul",
                        "unary", "pow", "postfix")
    g.rule("args", tg.seq(tg.ref("expr"), tg.repeat(tg.seq(",", tg.ref("expr")))))
    tg.expression(g, "expr",
                  primary=primary,
                  infix=[("or", "left", "or"), ("and", "left", "and"),
                         ("<", "left", "compare"), ("+", "left", "add"),
                         ("*", "left", "mul"), ("^", "right", "pow")],
                  prefix=[("-", "unary"), ("not", "not")],
                  postfix=[("call", "postfix",
                            lambda e: tg.seq(e, "(", tg.opt(tg.ref("args")), ")")),
                            ("member", "postfix",
                             lambda e: tg.seq(e, ".", tg.ref("identifier")))],
                  ladder=prec,
                  cond_primary=cond_primary)
    cond = "_expr_cond" if cond_primary is not None else "expr"
    g.rule("if_stmt", tg.seq("if",
                             tg.field("cond", tg.ref(cond)),
                             tg.field("then", tg.ref("expr")), ";"))
    g.rule("expr_stmt", tg.seq(tg.ref("expr"), ";"))
    g.rule("source_file", tg.repeat(tg.choice(tg.ref("if_stmt"),
                                               tg.ref("expr_stmt"))))
    g.start("source_file")
    return g


def test_bare_cond_without_affordance_conflicts():
    """The Phase-3 C3 class: `if <bare expr> <expr>;` with an expr-callee call
    is genuinely ambiguous (`if x (y)` = call vs parens-then)."""
    g = _cond_grammar(cond_primary=None)
    with pytest.raises(tg.GrammarConflictError):
        tg.build_builder(g)


def test_cond_primary_resolves_bare_cond():
    """The declarative form: `cond_primary=seq('(', ref('expr'), ')')` emits
    `_expr_cond` (the ladder minus the call postfix, at a distinct
    precedence so the near-copy doesn't reduce/reduce); the author's if_stmt
    uses it for the condition. The parens-cond pattern (`if (x) y;`, calls
    inside parens `if (f(x)) y;`) parses clean — no call misread. The
    bare-cond + parens-then combination (`if x (y);`) is the residual C3
    hazard the affordance declares away (parens-delimit the cond)."""
    g = _cond_grammar(cond_primary=tg.choice(tg.ref("number"), tg.ref("string"),
                                             tg.ref("identifier"),
                                             tg.seq("(", tg.ref("expr"), ")")))
    res = tg.build_builder(g)
    from tsgrammar.language import load_language
    import tree_sitter
    lang, _ = load_language(res.so_path, "condlang")
    ok, residual = 0, 0
    for src in (b"if (x) y;", b"if (f(x)) y;", b"if x + 1 + 2 y;",
                b"if x (y);"):
        tree = tree_sitter.Parser(lang).parse(src)
        errors = []

        def walk(n):
            if n.type == "ERROR" or n.is_missing:
                errors.append(n.type)
            for c in n.children:
                walk(c)
        walk(tree.root_node)
        assert errors == [], src
        ok += 1
    # the cond field is bound (hidden rule flattens into the if_stmt)
    tree = tree_sitter.Parser(lang).parse(b"if (f(x)) y;")
    ifs = tree.root_node.children[0]
    assert ifs.child_by_field_name("cond").type == "("
    assert ifs.child_by_field_name("then").type == "expr"
    # the residual: a CALL cond is rejected (parse error), not misread —
    # parens-delimit it: `if (f(x)) y;`
    tree = tree_sitter.Parser(lang).parse(b"if f(x) y;")
    nested = []

    def walk2(n):
        if n.type == "ERROR" or n.is_missing:
            nested.append(n.type)
        for c in n.children:
            walk2(c)
    walk2(tree.root_node)
    assert nested, "call conds should be rejected (parens-delimit them)"
    # and the corpus still passes on the cond-enabled grammar
    failures = semantic_smoke(g, cases=DEFAULT_PRECEDENCE_CORPUS)
    assert failures == [], failures
