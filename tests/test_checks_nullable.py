import pytest

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar.checks import _nullable, _view


def _g():
    g = tg.Grammar("t")
    g.rule("x", tg.pattern("a"))
    return g


@pytest.mark.parametrize("body_factory, expected", [
    (lambda: tg.field("p", tg.opt(tg.ref("x"))),        True),   # FIELD wrapper
    (lambda: tg.prec(1, tg.opt(tg.ref("x"))),           True),   # PREC wrapper
    (lambda: tg.alias("t", True, tg.opt(tg.ref("x"))),  True),   # ALIAS wrapper
    (lambda: tg.repeat1(tg.opt(tg.ref("x"))),           True),   # REPEAT1 of nullable
    (lambda: tg.repeat1(tg.ref("x")),                   False),  # REPEAT1 of non-nullable
    (lambda: tg.seq(tg.ref("x"), tg.ref("x")),          False),
])
def test_nullable_truth_table(body_factory, expected):
    g = _g()
    view = _view(g)
    body = body_factory()
    node = body.node if hasattr(body, "node") else body
    assert _nullable(node, view, set()) is expected


def test_nullable_non_start_rule_catches_wrapped():
    g = _g()
    g.rule("params", tg.field("p", tg.opt(tg.ref("x"))))
    g.rule("loop", tg.repeat1(tg.opt(tg.ref("x"))))
    g.rule("source_file", tg.seq(tg.ref("params"), tg.ref("loop")))
    g.start("source_file")
    from pydantree_sitter_grammar.checks import check_nullable_non_start_rule

    flagged = {i.rule for i in check_nullable_non_start_rule(g)}
    assert {"params", "loop"} <= flagged


def test_nullable_non_start_rule_is_advisory_not_an_error():
    """B4/REVIEW 020: verified empirically against tree-sitter CLI 0.25.3 —
    the generator ACCEPTS nullable non-start rules (repeat-of-symbol,
    opt-in-seq, FIELD-wrapped opt: generate exits 0 and writes parser.c).
    The check is now a WARNING: `errors()` must be empty so build() does not
    reject a legitimate `repeat(ref("item"))` list idiom."""
    g = _g()
    g.rule("items", tg.repeat(tg.ref("x")))     # nullable non-start — legal
    g.rule("source_file", tg.ref("items"))
    g.start("source_file")
    from pydantree_sitter_grammar.checks import check_nullable_non_start_rule

    issues = check_nullable_non_start_rule(g)
    assert issues and all(i.warning for i in issues)
    assert not tg.errors(g)                       # no error-level issue
    assert all(i.severity == "warning" for i in tg.run_checks(g)
               if "nullable" in i.message)
