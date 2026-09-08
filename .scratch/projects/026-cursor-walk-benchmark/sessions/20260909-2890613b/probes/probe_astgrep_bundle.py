"""Can ast-grep drive a pydantree-built grammar? Empirical answer.

Registers a bundle's grammar.so as an ast-grep dynamic language, then checks
three things:
  1. does ast-grep parse with it at all;
  2. do the two engines see the SAME tree (agreement by construction);
  3. does pydantree's own `Pattern` still bind to a post-024 `Grammar`.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness  # noqa: E402

REPORT: dict = {}


def step(name, fn):
    try:
        REPORT[name] = {"ok": True, "result": fn()}
    except Exception as error:  # noqa: BLE001 - the probe records failures
        REPORT[name] = {"ok": False, "error": type(error).__name__,
                        "detail": str(error).splitlines()[0][:300],
                        "tb": traceback.format_exc().splitlines()[-3:]}
    return REPORT[name]


NIX = """
{ pkgs, ... }:
{
  packages = [ pkgs.git pkgs.jq ];
  env.FOO = "bar";
  enterShell = ''
    echo hello
  '';
}
"""


def main() -> None:
    import ast_grep_py

    from pydantree_sitter.pattern import (
        Pattern,
        register_bundle_language,
        registered_languages,
    )

    grammar = harness.grammar("nix")
    bundle_dir = harness.CACHE / "nix-bundle"
    so = bundle_dir / "grammar.so"
    REPORT["setup"] = {"bundle": str(so), "exists": so.exists(),
                       "astgrep_version": ast_grep_py.__doc__ is not None,
                       "schema_kinds": len(grammar.schema.node_types)}

    # 1. register the pydantree-built .so as an ast-grep dynamic language
    step("register", lambda: register_bundle_language(
        "pdtnix", so, "tree_sitter_nix", extensions=["nix"]))
    REPORT["registered_languages"] = registered_languages()

    # 2. does ast-grep parse with it?
    def parse_with_astgrep():
        root = ast_grep_py.SgRoot(NIX, "pdtnix").root()
        return {"root_kind": root.kind(),
                "bindings": len(root.find_all(kind="binding")),
                "first": root.find(kind="binding").text()[:40]}
    step("astgrep_parse", parse_with_astgrep)

    # 3. do both engines see the same tree? (agreement by construction)
    def same_tree():
        from pydantree_sitter.agreement import char_to_byte_table
        table = char_to_byte_table(NIX)
        sg_root = ast_grep_py.SgRoot(NIX, "pdtnix").root()
        sg = set()
        stack = [sg_root]
        while stack:
            node = stack.pop()
            rng = node.range()
            sg.add((node.kind(), table[rng.start.index], table[rng.end.index]))
            stack.extend(node.children())
        ts = set()
        cursor = grammar.parse(NIX).root_node.walk()
        while True:
            n = cursor.node
            if n.is_named:
                ts.add((n.type, n.start_byte, n.end_byte))
            if cursor.goto_first_child():
                continue
            if cursor.goto_next_sibling():
                continue
            while True:
                if not cursor.goto_parent():
                    stack = None
                    break
                if cursor.goto_next_sibling():
                    break
            if stack is None:
                break
        sg_named = {t for t in sg if t[0] not in {"", None}}
        return {"astgrep_nodes": len(sg_named), "pydantree_nodes": len(ts),
                "intersection": len(sg_named & ts),
                "only_astgrep": sorted(sg_named - ts)[:5],
                "only_pydantree": sorted(ts - sg_named)[:5]}
    step("tree_agreement", same_tree)

    # 4. does pydantree's Pattern bind to a post-024 Grammar?
    REPORT["grammar_attrs"] = {
        "has_astgrep_name": hasattr(grammar, "astgrep_name"),
        "has_astgrep_is_bundle": hasattr(grammar, "astgrep_is_bundle"),
        "slots": list(getattr(type(grammar), "__slots__", ())),
    }
    from pydantree_sitter.rules import Rule

    step("pattern_implicit", lambda: repr(
        Pattern(Rule(kind="binding"), language=grammar))[:80])

    def explicit_kind_rule():
        pat = Pattern(Rule(kind="binding"), language=grammar,
                      astgrep_name="pdtnix")
        matches = pat.find_all(NIX)
        return {"n": len(matches),
                "spans": [[m.span.start_byte, m.span.end_byte]
                          for m in matches],
                "texts": [NIX[m.span.start_byte:m.span.end_byte][:34]
                          for m in matches],
                "typed": [type(m.extract(grammar.nodes.Binding)).__name__
                          for m in matches[:1]]}
    step("pattern_kind_rule", explicit_kind_rule)

    def metavariable_pattern():
        pat = Pattern("$K = $V;", language=grammar, astgrep_name="pdtnix")
        matches = pat.find_all(NIX)
        return {"n": len(matches),
                "captures": [sorted(m.captures) for m in matches[:3]]}
    step("pattern_metavariable", metavariable_pattern)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        REPORT["fatal"] = traceback.format_exc().splitlines()[-6:]
    for name, value in REPORT.items():
        print(f"--- {name}: {json.dumps(value, default=str)[:600]}",
              file=sys.stderr)
    json.dump(REPORT, sys.stdout, indent=1, default=str)
