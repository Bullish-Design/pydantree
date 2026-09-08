#!/usr/bin/env python3
"""Exercise both products: author a grammar, build a bundle, find typed nodes."""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = Path(os.environ.get("DEVENV_BUNDLE_DIR", str(HERE / "dist")))
SOURCE = """\
{ host = example.com; port = 8080; }
"""


def main() -> int:
    sys.path.insert(0, str(HERE))
    from grammar import build

    import pydantree_sitter_grammar as tg
    from pydantree_sitter import Grammar

    result = tg.build_builder(build(), scanner=str(HERE / "scanner.c"))
    bundle = result.package(DIST)
    grammar = Grammar.load_bundle(bundle)
    tree = grammar.parse(SOURCE)
    rows = tree.find(grammar.nodes.Pair)

    print("== Product B: author + build ==")
    print(f"bundle: {bundle}")
    print("== Product A: typed traversal ==")
    for row in rows:
        print(f"{row.key.__value__()} = {row.value.__value__()} "
              f"(line {row.span.line})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
