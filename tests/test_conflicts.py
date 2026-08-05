"""Conflict-remapping tests: parsing the CLI's --json report and rendering the
GrammarConflictError with DSL source sites (using a recorded real report)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tsgrammar as tg

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = (REPO_ROOT / ".scratch" / "projects" / "004-tsgrammar" / "evidence"
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
