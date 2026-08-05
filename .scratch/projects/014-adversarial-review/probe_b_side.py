"""Product-B probes: rules.py multi-Literal, builder alias=, extras dupes,
assemble() import-pollution, _snake acronyms.

014 refactor Phase 6: every probe now demonstrates the FIXED behavior
(F-B1..F-B5, D9). Run: devenv shell -- python probe_b_side.py
"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from typing import Literal

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar.rules import Rule, Token, _snake, assemble


def probe_multi_literal():
    print("=== multi-value Literal in a rule class (F-B2: fixed) ===")
    try:
        class Op(Rule):
            op: Literal["+", "-"]
            rhs: Literal["x"] = "x"
        class Start(Rule):
            child: Op
        # explicit rules list: function-local classes work (D9)
        g = assemble("t1", start=Start, rules=[Op, Start])
        body = g.rules["op"]
        print("  assembled; op members:", [m.type for m in body.members])
    except Exception as e:
        print(f"  {type(e).__name__}: {e}")


def probe_builder_alias_flag():
    print("=== g.rule(..., alias='y') (F-B1: deleted) ===")
    print("  alias= no longer exists (TypeError if called); the alias()")
    print("  combinator is the one way:")
    g = tg.Grammar("t2")
    g.rule("x", tg.alias("pretty", True, tg.token(tg.pattern("[a-z]+"))))
    g.rule("source_file", tg.repeat(tg.ref("x")))
    g.start("source_file")
    m = g.build()
    print("  alias combinator emitted; rules:", list(m.rules))


def probe_extras_whitespace_dupe():
    print("=== explicit non-canonical whitespace extra (F-B5: fixed) ===")
    g = tg.Grammar("t3")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("tok")))
    g.start("source_file")
    g.extra(tg.pattern(r"[ \t]+"))
    m = g.build()
    print("  extras:", [e.value for e in m.extras])


def probe_assemble_import_pollution():
    print("=== assemble() explicit rules (D9: no silent module sweep) ===")
    class Unrelated(Rule):
        x: Literal["u"] = "u"
    class Start(Rule):
        x: Literal["s"] = "s"
    g = assemble("t4", start=Start, rules=[Start])
    print("  rules:", list(g.rules))


def probe_snake_acronyms():
    print("=== _snake on acronyms (F-B4: fixed) ===")
    for name in ("HTTPServer", "JSONValue", "IOPort", "NamePath"):
        print(f"  {name} -> {_snake(name)}")


if __name__ == "__main__":
    probe_multi_literal()
    probe_builder_alias_flag()
    probe_extras_whitespace_dupe()
    probe_assemble_import_pollution()
    probe_snake_acronyms()
