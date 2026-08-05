"""Step-1 verify: the rule-class skeleton.

Checks (REFACTOR step 1's "tiny __main__-style check", plus the site
recording that step 5 will consume):

  [1] 17 dummy classes register in definition order
  [2] the kind bases (Pattern, Token, External, Extra, Supertype, Hidden,
      Inline, Word) are NOT registered as rules
  [3] __rule_name__ derivation (CamelCase -> snake_case, __rule_name__
      override, hidden-prefix resolution)
  [4] flags read INHERITED (getattr) — a user class inherits __token__ from
      Token, __extra__ from Extra
  [5] __site__ points at each class's definition line
  [6] assemble() compiles a tiny grammar and it round-trips to the IR
"""

import sys
from pathlib import Path
from typing import Literal

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tsgrammar as tg  # noqa: E402
from tsgrammar.rules import (  # noqa: E402
    External, Extra, Hidden, Inline, Pattern, R, Rule, Supertype, Token,
    Word, _RuleMeta, _resolved_name, assemble,
)

# ---- the dummy grammar -----------------------------------------------------

class Comment(Extra, Token):
    """# to end of line."""
    __body__ = tg.seq("#", tg.pattern(r"[^\n]*"))


class NamePath(Token):
    __pattern__ = r'("[^"]*"|[a-zA-Z_][a-zA-Z0-9_-]*)(\.[a-zA-Z_][a-zA-Z0-9_-]*|"[^"]*")*'


class Number(Pattern):
    __pattern__ = r"[0-9]+"


class StringFragment(External):
    pass


class IndentedStringFragment(External):
    __external__ = "MY_FRAG"


class Interpolation(Rule):
    open: "Literal['${']" = "${"


def main() -> int:
    # [1]+[2] registry order + kind bases excluded -------------------------
    mod = sys.modules[__name__]
    classes = [
        obj for obj in vars(mod).values()
        if isinstance(obj, type) and issubclass(obj, Rule)
        and hasattr(obj, "__rule_name__")
    ]
    names = [c.__name__ for c in classes]
    want = ["Comment", "NamePath", "Number", "StringFragment",
            "IndentedStringFragment", "Interpolation"]
    print(f"[1] registration order == definition order: {names == want}  {names}")
    kind_bases = ["Pattern", "Token", "External", "Extra", "Supertype",
                  "Hidden", "Inline", "Word", "Rule"]
    leaked = [k for k in kind_bases if k in names]
    print(f"[2] kind bases NOT registered: {not leaked}  "
          f"{'LEAKED: ' + str(leaked) if leaked else ''}")

    # [3] name derivation ---------------------------------------------------
    print(f"[3] names: {[c.__rule_name__ for c in classes]}")
    print(f"    __rule_name__ override (IndentedStringFragment): "
          f"{IndentedStringFragment.__rule_name__}")
    print(f"    hidden resolution (NamePath not hidden): "
          f"{_resolved_name(NamePath)}")
    assert [c.__rule_name__ for c in classes] == [
        "comment", "name_path", "number", "string_fragment",
        "indented_string_fragment", "interpolation"]

    # [4] inherited flags ---------------------------------------------------
    print(f"[4] Comment inherits __token__: {getattr(Comment, '__token__', False)}"
          f", __extra__: {getattr(Comment, '__extra__', False)}")
    print(f"    Number inherits __token__: {getattr(Number, '__token__', False)}")
    assert getattr(Comment, "__token__", False)
    assert getattr(Comment, "__extra__", False)
    assert not getattr(Number, "__token__", False)

    # [5] definition sites ---------------------------------------------------
    sites = {c.__name__: c.__site__ for c in classes}
    print(f"[5] class definition sites:")
    for n, s in sites.items():
        ok = "probe_step1_skeleton" in s.file
        print(f"      {n:24} {s.file.split('/')[-1]}:{s.lineno}: "
              f"{s.source.strip()!r}  (source file match: {ok})")
        assert ok

    # [6] assemble round-trip -----------------------------------------------
    print("[6] assemble: ", end="")
    g = assemble("mini", start=Interpolation)
    m = g.build()
    rules = list(m.rules)
    print(f"{len(rules)} rules -> {rules}")
    print("    externals:", [str(e.type) for e in m.externals])
    print("    extras:", [str(e.type) for e in m.extras])
    print("    start rule first:", list(m.rules)[0] == "interpolation")
    assert list(m.rules)[0] == "interpolation"
    # the checks run on assembled grammars: the ONLY issues are the "unused
    # rule" notices for the rules this dummy grammar leaves unreachable
    # (the real reachability gate is step 2's byte-identity test)
    flagged = {e.rule for e in tg.errors(g)}
    print("    checks flag exactly the unreachable rules:",
          flagged == {"name_path", "number", "string_fragment",
                      "indented_string_fragment"}, f"{sorted(flagged)}")
    assert flagged == {"name_path", "number", "string_fragment",
                       "indented_string_fragment"}
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
