#!/usr/bin/env python3
"""Novel Product B rule-class + scanner + conflict-loop + corpus probe."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar import External, Pattern, R, Rule, Token, assemble
from pydantree_sitter_grammar.corpus import Corpus, corpus_case


class Balanced(External):
    """The matched-delimiter scanner's sole token, in scanner enum order."""


class Name(Token):
    __pattern__ = r"[a-zA-Z_][a-zA-Z0-9_]*"


class Number(Pattern):
    __pattern__ = r"\d+"


class Expr(Rule):
    """Deliberately ambiguous first; build_loop adds associativity."""

    __body__ = tg.choice(
        tg.seq(tg.ref("expr"), "+", tg.ref("expr")),
        R(Number),
    )


class GroupStatement(Rule):
    name: Name
    eq: Literal["="] = "="
    value: Balanced
    semi: Literal[";"] = ";"


class ExprStatement(Rule):
    value: Expr
    semi: Literal[";"] = ";"


class WarningStatement(Rule):
    """Reachable named/numeric precedence mix: warning, not build error."""

    __body__ = tg.choice(tg.prec("low", "@"), tg.prec(1, "$"))


class SourceFile(Rule):
    __body__ = tg.repeat(tg.choice(
        R(GroupStatement), R(ExprStatement), R(WarningStatement)
    ))


def grammar() -> tg.Grammar:
    # Name must match the canonical scanner's exported C symbol.
    g = assemble(
        "dmini",
        start=SourceFile,
        rules=[Balanced, Name, Number, Expr, GroupStatement, ExprStatement,
               WarningStatement, SourceFile],
    )
    g.precedence_ordering("low")
    return g


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: probe_realworld_b.py OUTPUT_DIR")
    out = Path(sys.argv[1]).resolve()
    g = grammar()
    issues = list(tg.run_checks(g))
    assert not tg.errors(g), [str(i) for i in issues]
    assert any(i.site and i.site.file.endswith("probe_realworld_b.py")
               for i in issues), [str(i) for i in issues]

    def fix(error: tg.GrammarConflictError, current: tg.Grammar) -> None:
        text = str(error)
        assert "probe_realworld_b.py" in text, text
        assert "expr" in text, text
        current.replace_rule(
            "expr",
            tg.choice(
                tg.prec_left(
                    1, tg.seq(tg.ref("expr"), "+", tg.ref("expr"))
                ),
                tg.ref("number"),
            ),
        )

    events = list(tg.build_loop(
        g,
        fix=fix,
        scanner=tg.matched_delimiter_scanner_path(),
        cache_dir=out / "cache",
    ))
    conflicts = [e for e in events if isinstance(e, tg.GrammarConflictError)]
    assert len(conflicts) == 1, [str(e) for e in events]
    result = events[-1]
    assert isinstance(result, tg.BuildResult)
    assert any(w.site and w.site.file.endswith("probe_realworld_b.py")
               for w in result.warnings), [str(w) for w in result.warnings]

    source = "x = (1 + (2));\n1 + 2 + 3;\n"
    expected = (
        "(source_file "
        "(group_statement name: (name) '=' value: (balanced 'BALANCED') ';') "
        "(expr_statement value: (expr (expr (expr (number)) '+' "
        "(expr (number))) '+' (expr (number))) ';'))"
    )
    corpus = Corpus([
        corpus_case(source, expected, name="scanner plus fixed associativity")
    ], name="review019-realworld-b")
    run = corpus.run(build_result=result)
    if not run.ok():
        print(run.report())
    assert run.ok(), run.report()

    print(json.dumps({
        "conflicts_fixed": len(conflicts),
        "warnings": [str(i) for i in issues],
        "artifact": str(result.so_path),
        "corpus_ok": run.ok(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
