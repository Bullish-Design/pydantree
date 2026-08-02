"""Analyzer tests: every planted footgun produces the expected diagnostic."""

from __future__ import annotations

import tsgrammar as tg


def _g(name="t"):
    return tg.Grammar(name)


def test_undefined_symbol():
    g = _g()
    g.rule("source_file", tg.repeat(tg.ref("nope")))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("undefined" in i.message for i in issues)


def test_unused_rule_detected():
    g = _g()
    g.rule("used", tg.pattern(r"\d+"))
    g.rule("orphan", tg.pattern(r"\w+"))
    g.rule("source_file", tg.repeat(tg.ref("used")))
    g.start("source_file")
    issues = tg.run_checks(g)
    unused = [i for i in issues if "unused rule" in i.message]
    assert len(unused) == 1 and unused[0].rule == "orphan"


def test_word_rule_not_flagged_unused():
    g = _g()
    g.rule("identifier", tg.pattern(r"\w+"))
    g.rule("source_file", tg.repeat(tg.ref("identifier")))
    g.word("identifier")
    g.start("source_file")
    # word rule is referenced anyway here; a rule ONLY protected by word must
    # not be flagged
    g.rule("keyword_only", tg.pattern(r"\w+"))
    g2 = tg.Grammar("t2")
    g2.rules["identifier"] = tg.pattern(r"\w+").node
    g2.rules["source_file"] = tg.repeat(tg.ref("identifier")).node
    g2._word = "identifier"
    g2._start = "source_file"
    issues = tg.run_checks(g2)
    assert not any("unused rule" in i.message for i in issues)


def test_nullable_in_repeat():
    g = _g()
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.opt(tg.ref("tok"))))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("nullable" in i.message for i in issues)


def test_nullable_in_repeat1():
    g = _g()
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat1(tg.opt(tg.ref("tok"))))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("nullable" in i.message for i in issues)


def test_symbol_inside_token():
    g = _g()
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.token(tg.seq(tg.ref("tok"), ";")))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("inside TOKEN" in i.message for i in issues)


def test_symbol_inside_immediate_token():
    g = _g()
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.immediate_token(tg.ref("tok")))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("inside IMMEDIATE_TOKEN" in i.message for i in issues)


def test_pattern_flags_only_i():
    g = _g()
    g.rule("tok", tg.pattern(r"[a-z]+", flags="x"))
    g.rule("source_file", tg.repeat(tg.ref("tok")))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("only 'i'" in i.message for i in issues)
    # 'i' is fine
    g2 = _g()
    g2.rule("tok", tg.pattern(r"[a-z]+", flags="i"))
    g2.rule("source_file", tg.repeat(tg.ref("tok")))
    g2.start("source_file")
    assert not any("only 'i'" in i.message for i in tg.run_checks(g2))


def test_precedence_mixing_warning():
    g = _g()
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("expr", tg.choice(
        tg.prec_left(1, tg.seq(tg.ref("expr"), "+", tg.ref("expr"))),
        tg.prec("and", tg.seq(tg.ref("expr"), "and", tg.ref("expr"))),
        tg.ref("tok")))
    g.rule("source_file", tg.repeat(tg.ref("expr")))
    g.start("source_file")
    issues = tg.run_checks(g)
    mixing = [i for i in issues if "mixed" in i.message]
    assert mixing and mixing[0].warning


def test_extras_token_prefix_overlap_warning():
    g = _g()
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("div", tg.pattern(r"/"))
    g.rule("source_file", tg.repeat(
        tg.seq(tg.ref("tok"), tg.opt(tg.ref("div")))))
    g.start("source_file")
    g.extra(tg.pattern(r"/\*"))
    issues = tg.run_checks(g)
    overlap = [i for i in issues if "overlaps" in i.message]
    assert overlap and overlap[0].warning


def test_named_extra_exempt_from_overlap():
    g = _g()
    g.rule("comment", tg.token(tg.seq("/*", tg.pattern(r"[^*]*"), "*/")))
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("div", tg.pattern(r"/"))
    g.rule("source_file", tg.repeat(
        tg.seq(tg.ref("tok"), tg.opt(tg.ref("div")))))
    g.start("source_file")
    g.extra(tg.pattern(r"\s"))
    g.extra(tg.ref("comment"))
    assert not any("overlaps" in i.message for i in tg.run_checks(g))


def test_start_not_defined():
    g = _g()
    g.rule("a", tg.pattern(r"\d+"))
    issues = tg.run_checks(g)  # default start 'source_file' missing
    assert any("start rule" in i.message for i in issues)


def test_assert_clean_raises_on_errors_tolerates_warnings():
    g = _g()
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("div", tg.pattern(r"/"))
    g.rule("source_file", tg.repeat(
        tg.seq(tg.ref("tok"), tg.opt(tg.ref("div")))))
    g.start("source_file")
    g.extra(tg.pattern(r"/\*"))
    tg.assert_clean(g)  # only a warning — tolerated
    g2 = _g()
    g2.rule("source_file", tg.repeat(tg.ref("missing")))
    g2.start("source_file")
    try:
        tg.assert_clean(g2)
        raise AssertionError("should have raised")
    except tg.GrammarCheckError as e:
        assert any("undefined" in i.message for i in e.issues)


def test_issues_carry_dsl_sites():
    import linecache
    g = _g()
    g.rule("used", tg.pattern(r"\d+"))
    g.rule("orphan", tg.pattern(r"\w+"))   # line of this call
    g.rule("source_file", tg.repeat(tg.ref("used")))
    g.start("source_file")
    issues = tg.run_checks(g)
    unused = next(i for i in issues if "unused rule" in i.message)
    assert unused.site is not None
    assert unused.site.file.endswith("test_checks.py")
    assert "orphan" in linecache.getline(unused.site.file, unused.site.lineno)
