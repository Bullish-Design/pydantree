"""Can ast-grep load a grammar that pydantree BUILT? (022 §7 says no.)

CONCEPT §7: "ast-grep supports a fixed set of languages, compiled into its
wheel... A custom grammar built by pydantree-sitter-grammar has no ast-grep
support." That is false. `ast_grep_py.register_dynamic_language` takes any
tree-sitter shared library, and `pydantree_sitter_grammar.write_bundle`
produces exactly one.

The consequence is bigger than a feature: when BOTH engines load the SAME
`.so`, the two-parser divergence risk of §4 does not exist. There is one
grammar, one revision, one artifact.

Run inside the devenv shell (needs the tree-sitter CLI + gcc to build).
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

sys.path.insert(0, "tests/fixtures/grammars")

import pydantree_sitter_grammar as tg
from ast_grep_py import SgRoot, register_dynamic_language
from json_grammar import build
from pydantree_sitter_grammar.pipeline import write_bundle

from pydantree_sitter import Language

OUT = pathlib.Path(__file__).parent / "evidence" / "dynamic_language.json"


def nodes_pydantree(tree):
    out = []
    stack = [tree.root_node]
    while stack:
        n = stack.pop()
        out.append((n.type, n.start_byte, n.end_byte))
        stack.extend(n.children)
    return sorted(out)


def nodes_astgrep(root):
    out = []
    stack = [root]
    while stack:
        n = stack.pop()
        r = n.range()
        out.append((n.kind(), r.start.index, r.end.index))
        stack.extend(n.children())
    return sorted(out)


def main() -> int:
    bundle = pathlib.Path(str(write_bundle(tg.build(build().build()), "/tmp/jbundle")))
    so = bundle / "grammar.so"
    symbols = [line.split()[-1]
               for line in subprocess.run(["nm", "-D", "--defined-only", str(so)],
                                          capture_output=True, text=True,
                                          check=False).stdout.splitlines()
               if "tree_sitter" in line]

    # `extensions` is REQUIRED — the .pyi's CustomLang omits it, and leaving
    # it out fails with `missing field \`extensions\``.
    register_dynamic_language({
        "pydantree_json": {
            "library_path": str(so),
            "language_symbol": "tree_sitter_json",
            "extensions": ["pjson"],
        }
    })

    src = '{"host": "x", "port": 1}'
    ours = nodes_pydantree(Language.load_bundle(bundle).parse(src.encode()))
    theirs = nodes_astgrep(SgRoot(src, "pydantree_json").root())

    report = {
        "bundle": str(bundle),
        "exported_symbols": symbols,
        "source": src,
        "pydantree_nodes": len(ours),
        "astgrep_nodes": len(theirs),
        "identical_node_sets": ours == theirs,
        "kind_rule_matches": [n.text() for n
                              in SgRoot(src, "pydantree_json").root().find_all(kind="pair")],
        # A pattern string must PARSE in the target language. `$H` is not a
        # JSON value, so a bare `$` metavariable finds nothing. `meta_var_char`
        # / `expando_char` in CustomLang exist for exactly this.
        "pattern_matches_with_default_sigil": [
            n.text() for n in SgRoot(src, "pydantree_json").root()
            .find_all(pattern='{"host": $H, $$$R}')],
    }
    OUT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if report["identical_node_sets"] else 1


if __name__ == "__main__":
    sys.exit(main())
