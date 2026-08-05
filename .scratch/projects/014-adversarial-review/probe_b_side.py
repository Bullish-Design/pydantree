"""Product-B probes: rules.py multi-Literal, builder alias=, extras dupes,
assemble() import-pollution, _snake acronyms."""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from typing import Literal

import tsgrammar as tg
from tsgrammar.rules import Rule, Token, _snake, assemble


def probe_multi_literal():
    print("=== multi-value Literal in a rule class ===")
    try:
        class Op(Rule):
            op: Literal["+", "-"]
            rhs: Literal["x"] = "x"
        class Start(Rule):
            child: Op
        g = assemble("t1", start=Start)
        print("  assembled; op body:", g.rules["op"])
    except Exception as e:
        print(f"  {type(e).__name__}: {e}")


def probe_builder_alias_flag():
    print("=== g.rule(..., alias='y') semantics ===")
    g = tg.Grammar("t2")
    g.rule("source_file", tg.ref("x"))
    g.rule("x", tg.pattern("[a-z]+"), alias="pretty")
    m = g.build()
    print("  inline list:", m.inline)
    print("  rules:", list(m.rules))
    print("  -> alias= appended a NONEXISTENT rule name to `inline`; no AliasNode emitted")


def probe_snake():
    print("=== _snake on acronyms ===")
    for n in ("HTTPServer", "JSONValue", "IOPort"):
        print(f"  {n} -> {_snake(n)}")


def probe_extra_double_whitespace():
    print("=== explicit non-canonical whitespace extra duplicates \\s ===")
    g = tg.Grammar("t3")
    g.rule("source_file", tg.pattern("[a-z]+"))
    g.extra(tg.pattern(r"[ \t]+"))   # author handles whitespace herself
    m = g.build()
    print("  extras:", [x.model_dump(exclude_none=True) for x in m.extras])


def probe_import_pollution():
    """A Rule subclass imported into the module ONLY for R() reference
    becomes a registered rule of the grammar."""
    print("=== assemble() sweeps every Rule subclass in the module ===")
    import types as _t
    mod = _t.ModuleType("fake_grammar_mod")
    src = (
        "from tsgrammar.rules import Rule, Pattern\n"
        "class Unrelated(Pattern):\n"
        "    __pattern__ = '[0-9]+'\n"
        "class Start(Rule):\n"
        "    child: Unrelated\n"
    )
    sys.modules["fake_grammar_mod"] = mod
    exec(src, mod.__dict__)
    g = assemble("t4", start=mod.Start)
    print("  rules:", list(g.rules))


if __name__ == "__main__":
    probe_multi_literal()
    probe_builder_alias_flag()
    probe_snake()
    probe_extra_double_whitespace()
    probe_import_pollution()
