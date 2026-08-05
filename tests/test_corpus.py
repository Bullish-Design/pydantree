"""pydantree_sitter_grammar.corpus tests — the Phase-5 corpus-testing harness (CONCEPT §4.8,
the systematic guard for the Phase-3 §4 semantic-intent leak).

Covers: the qfilter corpus (expression shapes in the compact style, statement
shapes in the sexp style) passing on a known-good grammar; each planted
regression that GENERATES CLEAN but parses wrongly (ladder reorder,
associativity flip, postfix-below-unary, a statement-level structural
change) being caught by the harness; the semantic-smoke seed's reach vs the
full corpus; render normalization; snapshotting.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar.corpus import Corpus, corpus_case, render, render_compact
from pydantree_sitter_grammar.expressions import (
    DEFAULT_PRECEDENCE_CORPUS,
    semantic_smoke,
)
from pydantree_sitter_grammar.ir import ChoiceNode, StrNode, SymbolNode

CONSUMERS = Path(__file__).resolve().parent / "fixtures" / "consumers"

pytestmark = pytest.mark.toolchain

from qfilter_corpus import (  # noqa: E402
    EXPR_CASES,
    STMT_CASES,
    expression_corpus,
    statement_corpus,
)

GOOD_LADDER = ("or", "and", "not", "compare", "add", "mul", "unary", "pow",
               "postfix")


def _expr_grammar(name, *, ladder=GOOD_LADDER, plus_assoc="left") -> tg.Grammar:
    """A qfilter-shaped expression grammar (the corpus's subject). `ladder` is
    the declarative ordering; `plus_assoc` flips `+` associativity — the two
    levers the planted regressions pull."""
    g = tg.Grammar(name)
    g.rule("number", tg.pattern(r"\d+(\.\d+)?"))
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"), word=True)
    g.rule("args", tg.seq(tg.ref("expr"), tg.repeat(tg.seq(",", tg.ref("expr")))))
    prec = g.precedence(*ladder)
    tg.expression(g, "expr",
                  primary=tg.choice(tg.ref("number"), tg.ref("identifier"),
                                    tg.seq("(", tg.ref("expr"), ")")),
                  infix=[("or", "left", "or"), ("and", "left", "and"),
                         ("<", "left", "compare"), ("==", "left", "compare"),
                         ("+", plus_assoc, "add"), ("*", "left", "mul"),
                         ("^", "right", "pow")],
                  prefix=[("-", "unary"), ("not", "not")],
                  postfix=[
                      ("call", "postfix",
                       lambda e: tg.seq(e, "(", tg.opt(tg.ref("args")), ")")),
                      ("member", "postfix",
                       lambda e: tg.seq(e, ".", tg.ref("identifier"))),
                  ],
                  ladder=prec)
    g.rule("stmt", tg.seq(tg.ref("expr"), ";"))
    g.rule("source_file", tg.repeat(tg.ref("stmt")))
    g.start("source_file")
    return g


# ---------------------------------------------------------------------------
# the harness on a known-good grammar
# ---------------------------------------------------------------------------

def test_expression_corpus_passes_on_qfilter():
    import qfilter
    g = qfilter.build()
    issues = list(tg.run_checks(g))
    assert not tg.errors(g), issues
    res = tg.build_builder(g)
    r = expression_corpus().run(build_result=res)
    assert r.ok(), r.report()


def test_statement_corpus_passes_on_qfilter():
    import qfilter
    g = qfilter.build()
    res = tg.build_builder(g)
    r = statement_corpus().run(build_result=res)
    assert r.ok(), r.report()


def test_corpus_cases_can_be_plain_tuples_and_render_norm():
    """Cases are corpus_case(...) OR plain (source, expected) tuples; the
    render normalization story is documented and honored (anonymous drop)."""
    import qfilter
    g = qfilter.build()
    res = tg.build_builder(g)
    c = Corpus([("x;", "(source_file (expr_stmt (expr (identifier)) ';'))"),
                ("x;", "(source_file (expr_stmt (expr (identifier))))")],
               anonymous="drop")
    assert len(c.cases) == 2
    # the first case keeps anonymous, the second drops them — the drop case's
    # expectation has no ';' token
    r1 = Corpus([c.cases[0]], anonymous="keep").run(build_result=res)
    r2 = Corpus([c.cases[1]], anonymous="drop").run(build_result=res)
    assert r1.ok(), r1.report()
    assert r2.ok(), r2.report()
    assert render_compact is not None  # exported surface


# ---------------------------------------------------------------------------
# the planted regressions — every one GENERATES CLEAN and parses wrongly
# ---------------------------------------------------------------------------

def test_planted_ladder_reorder_is_caught():
    """Regression 1: the author puts UNARY ABOVE POW in the ladder. Generate
    stays clean (a consistent ladder), but `-a ^ b` silently flips to
    `(-a)^b`. The harness catches it, citing the unary-pow case."""
    g = _expr_grammar("r1_unary_above_pow",
                      ladder=("or", "and", "not", "compare", "add", "mul",
                              "pow", "unary", "postfix"))
    res = tg.build_builder(g)          # generates clean — no conflict raised
    r = expression_corpus().run(build_result=res)
    assert not r.ok()
    msgs = [f.message(r.style) for f in r.failures]
    assert any("'-a ^ b;'" in m for m in msgs), msgs
    # the smoke seed catches this one too (the `-a ^ b` case is in the seed)
    assert any("'-a ^ b;'" in f for f in semantic_smoke(g))


def test_planted_associativity_flip_needs_the_full_corpus():
    """Regression 2: the author flips `+` to RIGHT-associative. Generate stays
    clean; `1 + 2 + 3` becomes `(1+(2+3))`. The 5-case smoke seed CANNOT catch
    this (no chain case in it) — only the full corpus's chain case can."""
    g = _expr_grammar("r2_right_plus", plus_assoc="right")
    res = tg.build_builder(g)          # clean generate
    # the smoke seed (5 cases) is blind to the flip:
    assert semantic_smoke(g) == []
    # the full corpus catches it, citing the + chain case
    r = expression_corpus().run(build_result=res)
    assert not r.ok()
    msgs = [f.message(r.style) for f in r.failures]
    assert any("'1 + 2 + 3;'" in m for m in msgs), msgs


def test_planted_postfix_below_unary_is_caught():
    """Regression 3: the author puts POSTFIX BELOW UNARY in the ladder.
    Generate stays clean; `-f(x)` becomes `(-f)(x)` (and `-a.b` becomes
    `(-a).b`). The harness catches all three affected cases."""
    g = _expr_grammar("r3_postfix_below_unary",
                      ladder=("or", "and", "not", "compare", "add", "mul",
                              "postfix", "unary", "pow"))
    res = tg.build_builder(g)          # clean generate
    r = expression_corpus().run(build_result=res)
    assert not r.ok()
    msgs = [f.message(r.style) for f in r.failures]
    assert any("'-f(x);'" in m for m in msgs), msgs
    assert any("'-a.b;'" in m for m in msgs), msgs
    assert any("'-f(x) + 1;'" in m for m in msgs), msgs


def test_planted_statement_level_regression_is_caught():
    """The statement-level class the expression-only seed cannot reach: drop
    `block` from the statement supertype (the latent qfilter bug the corpus
    authoring found — Phase-3's own corpus and the smoke seed were both green
    on it). Generate stays clean; `if (a) { ... }` becomes a parse error."""
    import qfilter
    g = qfilter.build()
    stmt: ChoiceNode = g.rules["statement"]
    g.rules["statement"] = ChoiceNode(members=[
        m for m in stmt.members
        if not (isinstance(m, SymbolNode) and m.name == "block")])
    res = tg.build_builder(g)          # clean generate (the original shipped)
    r = statement_corpus().run(build_result=res)
    assert not r.ok()
    msgs = [f.message(r.style) for f in r.failures]
    assert any("if (a) { b = 1; } else { b = 2; }" in m for m in msgs), msgs
    assert any("if (a) if (b) { c; } else { d; }" in m for m in msgs), msgs


# ---------------------------------------------------------------------------
# snapshotting + the report surface
# ---------------------------------------------------------------------------

def test_corpus_snapshots_grammar_and_schema(tmp_path):
    """grammar.json + node-schema.json land beside the corpus for reviewable
    diffs when a grammar changes."""
    import qfilter
    g = qfilter.build()
    res = tg.build_builder(g)
    snap = tmp_path / "snap"
    r = Corpus(EXPR_CASES[:2], style="compact", snapshots_dir=snap).run(build_result=res)
    assert r.ok()
    assert (snap / "grammar.json").exists()
    assert (snap / "node-schema.json").exists()
    # a grammar change now shows up as a diff on the snapshot
    assert any("snapshots:" in line for line in r.report().splitlines())


def test_report_shows_expected_vs_got_diff():
    g = _expr_grammar("report_diff")
    res = tg.build_builder(g)
    r = Corpus([corpus_case("-a ^ b;", "(((wrong)))", name="wrong",
                            selector="expr")]).run(build_result=res)
    assert not r.ok()
    report = r.report()
    assert "-" in report and "+" in report  # a unified diff line
    assert "wrong" in report


# ---------------------------------------------------------------------------
# semantic smoke over the qfilter grammar (was test_phase3a.py — dissolved
# into the per-surface suite, 7.5)
# ---------------------------------------------------------------------------


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
    from pydantree_sitter_grammar.language import load_language
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
