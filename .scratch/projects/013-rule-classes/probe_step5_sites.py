"""Step-5 verify: class/attribute source sites for conflict remapping.

REFACTOR step 5's promise: `GrammarConflictError` points at the CLASS
definition and the exact ATTRIBUTE line — not at rules.py internals.

Checks:

  [1] the rule-level site of an assembled grammar is the class definition
      line (not `g.rule(rn, body,` inside rules.py)
  [2] annotation-emitted nodes carry their ATTRIBUTE lines: on the devenv
      fixture, `pair`'s `key: NamePath` field node site is the `key:` line
  [3] a REAL conflicting class grammar (expr-without-precedence) produces a
      GrammarConflictError whose message names the class definition lines
      and the author-module `__body__` seq line — no rules.py internals
  [4] `matching_alternative` resolves the conflict's production to the
      attribute/class site (the per-production line the remapper prefers)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tsgrammar as tg  # noqa: E402
from tsgrammar import (  # noqa: E402
    Rule, R, assemble,
)

HERE = Path(__file__).resolve().parent


# ---- [1]+[2]: sites on the devenv fixture ----------------------------------

def check_fixture_sites() -> bool:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "devenv_classes_grammar_sites",
        REPO / "examples" / "devenv-subset" / "grammar.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["devenv_classes_grammar_sites"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    g = mod.build()
    ok = True

    # [1] rule-level site = class line
    pair_site = g.sites["pair"]
    print(f"[1] pair rule site: {pair_site}")
    ok &= "devenv-subset/grammar.py" in pair_site.file \
        and "class Pair(Rule):" in pair_site.source
    assert not pair_site.file.endswith("rules.py")

    # [2] annotation attribute lines
    for attr, want_line in [("key", "key: NamePath"), ("value", "value: Value")]:
        site = g.matching_alternative("pair", ("name_path",)) \
            if attr == "key" else None
        # direct: walk the body nodes, find the field node for the attr
        from tsgrammar.builder import _iter_body_nodes
        from tsgrammar.grammar import FieldNode
        found = None
        for node in _iter_body_nodes(g.rules["pair"]):
            if isinstance(node, FieldNode) and node.name == attr:
                found = g.node_site(node)
                break
        print(f"[2] pair.{attr} field node site: {found}")
        assert found is not None and want_line in found.source, \
            f"{attr}: {found}"
        ok &= want_line in found.source
    return ok


# ---- [3]: a real conflicting class grammar ---------------------------------

class Number(Rule):
    __body__ = tg.pattern(r"\d+")


class Expr(Rule):
    # self-recursive: the cycle point uses the DSL's own string ref
    # (concept §4.6 — `R(Expr)` would NameError at class creation)
    __body__ = tg.choice(tg.seq(tg.ref("expr"), "+", tg.ref("expr")),
                         R(Number))


class SourceFile(Rule):
    __body__ = tg.repeat(R(Expr))


def check_real_conflict() -> bool:
    g = assemble("conflict-demo", start=SourceFile)
    try:
        event = next(tg.build_loop(g))
    except StopIteration:
        print("[3] build_loop yielded nothing")
        return False
    if isinstance(event, tg.BuildResult):
        print("[3] UNEXPECTED: generate succeeded cleanly — no conflict")
        return False
    text = str(event)
    print("[3] GrammarConflictError raised; message:")
    for line in text.splitlines()[:14]:
        print("    " + line)
    # the conflicting rules' sites are the class lines in THIS probe
    ok = "probe_step5_sites.py" in text
    ok &= "class Expr(Rule):" in text
    # the per-production site is the author-module __body__ seq line
    ok &= "tg.seq(tg.ref(\"expr\"), \"+\", tg.ref(\"expr\"))" in text
    assert not any("rules.py" in l for l in text.splitlines()), text
    return ok


# ---- [4]: matching_alternative prefers the attribute/class site ------------

def check_matching_alternative() -> bool:
    g = assemble("conflict-demo", start=SourceFile)
    site = g.matching_alternative("expr", ("expr", "'+'", "expr"))
    print(f"[4] matching_alternative('expr', [expr '+' expr]) -> {site}")
    ok = site is not None and "probe_step5_sites.py" in site.file
    ok &= "tg.seq(tg.ref(\"expr\"), \"+\", tg.ref(\"expr\"))" in site.source
    return ok


def main() -> int:
    ok = True
    ok &= check_fixture_sites()
    print()
    ok &= check_real_conflict()
    print()
    ok &= check_matching_alternative()
    print()
    print("ALL SITE CHECKS:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
