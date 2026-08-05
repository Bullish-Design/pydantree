"""Conflict-remapping tests: parsing the CLI's --json report and rendering the
GrammarConflictError with DSL source sites (using a recorded real report)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import pydantree_sitter_grammar as tg

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = (REPO_ROOT / "tests" / "fixtures" / "evidence"
          / "b5_conflict_gap_stderr.json")

RAW_CONFLICT = json.dumps({
    "BuildTables": {
        "Conflict": {
            "symbol_sequence": ["expr", "'+'", "expr"],
            "conflicting_lookahead": "'+'",
            "possible_interpretations": [
                {
                    "variable_name": "expr",
                    "production_step_symbols": ["expr", "'+'", "expr"],
                    "step_index": 3, "done": True,
                    "preceding_symbols": ["expr", "'+'"],
                    "conflicting_lookahead": "'+'",
                    "precedence": None, "associativity": None,
                },
                {
                    "variable_name": "expr",
                    "production_step_symbols": ["expr", "'+'", "expr"],
                    "step_index": 3, "done": False,
                    "preceding_symbols": ["expr", "'+'", "expr", "'+'"],
                    "conflicting_lookahead": "'+'",
                    "precedence": None, "associativity": None,
                },
            ],
            "possible_resolutions": [
                {"Associativity": {"symbols": ["expr"]}},
                {"AddConflict": {"symbols": ["expr"]}},
            ],
        }
    }
})


def test_parse_conflict_json():
    c = tg.parse_conflict_json(RAW_CONFLICT)
    assert c is not None
    assert c.ambiguous_shape() == "expr '+' expr • '+'"
    assert c.involved_rules == ["expr"]
    assert c.resolutions[0] == {"Associativity": {"symbols": ["expr"]}}


def test_parse_conflict_json_non_conflict_returns_none():
    assert tg.parse_conflict_json(json.dumps({"something": "else"})) is None
    assert tg.parse_conflict_json("not json") is None


def test_conflict_error_names_dsl_sites_and_fixes():
    g = tg.Grammar("t")
    g.rule("expr", tg.choice(
        tg.seq(tg.ref("expr"), "+", tg.ref("expr")),
        tg.ref("number")))
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("expr")))
    g.start("source_file")
    conflict = tg.parse_conflict_json(RAW_CONFLICT)
    assert conflict is not None
    err = tg.GrammarConflictError(g, conflict)
    text = str(err)
    assert "Ambiguous shape: expr '+' expr • '+'" in text
    assert "g.rule('expr', ...) defined at" in text
    assert g.sites["expr"].file.endswith("test_conflicts.py")
    assert "add left/right associativity to expr" in text
    assert "conflicts=[expr]" in text
    assert "expr: expr  '+'  expr" in text


@pytest.mark.skipif(not REPORT.exists(), reason="no recorded real report")
def test_real_generator_report_parses():
    """The verbatim report captured from the real CLI in Experiment B parses
    and renders without error."""
    raw = REPORT.read_text()
    c = tg.parse_conflict_json(raw)
    assert c is not None
    assert c.involved_rules == ["expr"]


# ---------------------------------------------------------------------------
# the intentional-ambiguity opt-in + the fix-one-rerun loop (was
# test_phase3_surface.py — dissolved into the per-surface suite, 7.5)
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.toolchain

# ---------------------------------------------------------------------------
# intentional ambiguity opt-in
# ---------------------------------------------------------------------------

def _dangling_else_grammar(*, ambiguous: bool) -> tg.Grammar:
    g = tg.Grammar("iflang")
    g.rule("identifier", tg.pattern(r"[a-zA-Z_]\w*"))
    g.word("identifier")
    g.rule("expr", tg.choice(tg.ref("identifier"), tg.pattern(r"\d+")))
    if_stmt_body = tg.seq(
        "if", tg.field("cond", tg.ref("expr")),
        tg.field("then", tg.ref("statement")),
        tg.opt(tg.seq("else", tg.field("else", tg.ref("statement")))),
    )
    if ambiguous:
        g.rule("if_stmt", if_stmt_body, ambiguous=True)
    else:
        g.rule("if_stmt", if_stmt_body)
    g.rule("expr_stmt", tg.seq(tg.ref("expr"), ";"))
    g.rule("statement", tg.choice(tg.ref("if_stmt"), tg.ref("expr_stmt")),
           supertype=True)
    g.rule("source_file", tg.repeat(tg.ref("statement")))
    g.start("source_file")
    return g


def test_ambiguous_synthesizes_prec_dynamic_and_conflicts():
    g = _dangling_else_grammar(ambiguous=True)
    from pydantree_sitter_grammar.ir import PrecDynamicNode, SeqNode
    body = g.rules["if_stmt"]
    assert isinstance(body, PrecDynamicNode)
    assert body.value == 1
    assert isinstance(body.content, SeqNode)  # the if-seq with the opt() inside
    m = g.build()
    assert m.conflicts == [["if_stmt"]]


def test_ambiguous_resolves_greedy_at_runtime(tmp_path):
    """The whitelisted dangling else must generate clean (exit 0) and parse
    `if a if b c; else d;` with the inner-if-else binding (greedy)."""
    g = _dangling_else_grammar(ambiguous=True)
    assert not tg.errors(g)
    result = tg.build_builder(g, cache_dir=tmp_path / "cache")
    assert result.generate_proc.returncode == 0
    lang, _ = tg.load_language(result.so_path, "iflang")
    tree = tg.parse(lang, "if a if b c; else d;")
    assert not tree.root_node.has_error
    # greedy: the else binds to the INNER if
    sexp = str(tree.root_node)
    assert "(if_stmt cond: (expr (identifier)) then: (if_stmt" in sexp
    assert "else: (expr_stmt (expr (identifier))))" in sexp


def test_dangling_else_without_opt_in_conflicts(tmp_path):
    """Same grammar WITHOUT the opt-in must hit an unresolved GLR conflict."""
    g = _dangling_else_grammar(ambiguous=False)
    json_path = g.emit_bundle(tmp_path / "dangling")
    proc = tg.run_generate(json_path)   # always --json (D10)
    assert proc.returncode == 1
    conflict, err = tg.remap_from_proc(g, proc)
    assert "if_stmt" in conflict.involved_rules
    assert "Ambiguous shape" in str(err)


# ---------------------------------------------------------------------------
# per-production conflict sites
# ---------------------------------------------------------------------------

def _prec_gap_grammar() -> tg.Grammar:
    """A precedence-gap conflict: `+` and `*` both at the same effective
    level (no precedence annotations at all) -> unresolvable shift/reduce."""
    g = tg.Grammar("gap")
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("expr", tg.choice(
        tg.seq(tg.ref("expr"), "+", tg.ref("expr")),
        tg.seq(tg.ref("expr"), "*", tg.ref("expr")),
        tg.ref("number")))
    g.rule("source_file", tg.repeat(tg.seq(tg.ref("expr"), ";")))
    g.start("source_file")
    return g


def test_conflict_cites_per_production_seq_line(tmp_path):
    g = _prec_gap_grammar()
    json_path = g.emit_bundle(tmp_path / "gap")
    proc = tg.run_generate(json_path)   # always --json (D10)
    assert proc.returncode == 1
    conflict, err = tg.remap_from_proc(g, proc)
    text = str(err)
    # the per-production site must be the seq(...) line, not just the rule()
    # line — they differ in this file (the seq lines are the alternatives)
    sites = [g.matching_alternative("expr", tuple(i.get("production_step_symbols", [])))
             for i in conflict.interpretations]
    assert all(s is not None for s in sites)
    for s in sites:
        assert s.file.endswith("test_conflicts.py")
        assert "tg.seq(tg.ref(\"expr\")" in s.source, s
    assert "Competing parses (per-production source sites)" in text
    assert "at " in text


def test_matching_alternative_distinguishes_operators():
    """The two alternatives (`+` and `*`) must map to DIFFERENT lines."""
    g = _prec_gap_grammar()
    plus_site = g.matching_alternative("expr", ("expr", "'+'", "expr"))
    star_site = g.matching_alternative("expr", ("expr", "'*'", "expr"))
    assert plus_site is not None and star_site is not None
    assert plus_site.source != star_site.source


# ---------------------------------------------------------------------------
# fix-one-rerun loop
# ---------------------------------------------------------------------------

def test_build_loop_drives_to_clean(tmp_path):
    """The loop: yield the conflict, apply the generator's suggested fix
    (Associativity), re-run — must land on a clean generate, and the fixed
    grammar must parse."""
    g = tg.Grammar("loopy")
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("expr", tg.choice(
        tg.seq(tg.ref("expr"), "+", tg.ref("expr")),
        tg.ref("number")))
    g.rule("source_file", tg.repeat(tg.seq(tg.ref("expr"), ";")))
    g.start("source_file")

    fixed = False

    def fix(error, gg):
        nonlocal fixed
        assert isinstance(error, tg.GrammarConflictError)
        fixed = True
        # generator's suggested fix: add left associativity to expr
        gg.replace_rule("expr", tg.choice(
            tg.prec_left(1, tg.seq(tg.ref("expr"), "+", tg.ref("expr"))),
            tg.ref("number")))

    events = list(tg.build_loop(g, fix=fix, cache_dir=tmp_path / "cache"))
    errors = [e for e in events if isinstance(e, tg.GrammarConflictError)]
    result = events[-1]
    assert isinstance(result, tg.BuildResult)
    assert len(errors) == 1 and fixed
    lang, _ = tg.load_language(result.so_path, "loopy")
    tree = tg.parse(lang, "1 + 2 + 3;")
    assert not tree.root_node.has_error


def test_build_loop_fails_after_max_attempts(tmp_path):
    g = tg.Grammar("never")
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("expr", tg.choice(
        tg.seq(tg.ref("expr"), "+", tg.ref("expr")),
        tg.ref("number")))
    g.rule("source_file", tg.repeat(tg.seq(tg.ref("expr"), ";")))
    g.start("source_file")

    def noop(error, gg):
        pass

    with pytest.raises(RuntimeError):
        list(tg.build_loop(g, fix=noop, cache_dir=tmp_path / "cache",
                           max_attempts=2))


# ---------------------------------------------------------------------------
# debug_states
# ---------------------------------------------------------------------------

def test_debug_states_returns_report(tmp_path):
    g = tg.Grammar("states")
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("expr", tg.choice(
        tg.prec_left(1, tg.seq(tg.ref("expr"), "+", tg.ref("expr"))),
        tg.ref("number")))
    g.rule("source_file", tg.repeat(tg.seq(tg.ref("expr"), ";")))
    g.start("source_file")
    rc, body, _proc = tg.debug_states(g, "expr", workdir=tmp_path / "states")
    assert rc == 0
    assert "expr" in body


# ---------------------------------------------------------------------------
# Phase-2A hardening
# ---------------------------------------------------------------------------

def test_alias_on_seq_raises_at_construction():
    with pytest.raises(ValueError, match="aliases every named child"):
        tg.alias("tuple", True, tg.seq(tg.ref("a"), tg.ref("b")))
    # the canonical pattern (single hidden symbol) still works
    assert tg.alias("tuple", True, tg.ref("_contents")).node.type == "ALIAS"
    # wrapping in token is the documented escape hatch
    assert tg.alias("tuple", True, tg.token(tg.seq("a", "b"))).node.type == "ALIAS"


def test_nullable_non_start_rule_detected():
    g = tg.Grammar("t")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("params", tg.opt(tg.ref("tok")))     # nullable non-start
    g.rule("source_file", tg.repeat(tg.seq("(", tg.ref("params"), ")")))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("nullable" in i.message and "non-start" in i.message for i in issues)
    # the fixed form (optional part in the caller) is clean
    g2 = tg.Grammar("t2")
    g2.rule("tok", tg.pattern(r"\d+"))
    g2.rule("params", tg.ref("tok"))
    g2.rule("source_file", tg.repeat(
        tg.seq("(", tg.opt(tg.ref("params")), ")")))
    g2.start("source_file")
    assert not tg.errors(g2)


def test_start_rule_may_be_nullable():
    g = tg.Grammar("t")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.opt(tg.ref("tok")))   # nullable START is legal
    g.start("source_file")
    assert not tg.errors(g)


def test_whitespace_extra_default():
    g = tg.Grammar("t")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("tok")))
    g.start("source_file")
    m = g.build()
    from pydantree_sitter_grammar.ir import PatternNode
    assert any(isinstance(e, PatternNode) and e.value == r"\s" for e in m.extras)
    # explicit \s is not doubled
    g2 = tg.Grammar("t2")
    g2.rule("tok", tg.pattern(r"\d+"))
    g2.rule("source_file", tg.repeat(tg.ref("tok")))
    g2.start("source_file")
    g2.extra(tg.pattern(r"\s"))
    assert len(g2.build().extras) == 1
    # whitespace=False disables
    g3 = tg.Grammar("t3", whitespace=False)
    g3.rule("tok", tg.pattern(r"\d+"))
    g3.rule("source_file", tg.repeat(tg.ref("tok")))
    g3.start("source_file")
    assert g3.build().extras == []


def test_word_sugar():
    g = tg.Grammar("t")
    g.rule("identifier", tg.pattern(r"\w+"), word=True)
    g.rule("source_file", tg.repeat(tg.ref("identifier")))
    g.start("source_file")
    assert g.build().word == "identifier"
    with pytest.raises(ValueError):
        g2 = tg.Grammar("t2")
        g2.rule("a", tg.pattern(r"\w+"), word=True)
        g2.rule("b", tg.pattern(r"\w+"), word=True)


def test_whitespace_default_parses_spaces(tmp_path):
    """The Phase-2 finding §2.1 'no default whitespace extra' — the first test
    inputs failed on spaces. The default must make spaces just work."""
    g = tg.Grammar("ws_default")
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("number")))
    g.start("source_file")
    result = tg.build_builder(g, cache_dir=tmp_path / "cache")
    lang, _ = tg.load_language(result.so_path, "ws_default")
    tree = tg.parse(lang, "1 2 3")
    assert not tree.root_node.has_error
