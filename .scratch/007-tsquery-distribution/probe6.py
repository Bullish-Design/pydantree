"""Probe 6: capture placement vs has-ancestor predicate."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import tree_sitter  # noqa: E402
import tree_sitter_python  # noqa: E402

py = tree_sitter.Language(tree_sitter_python.language())
src = b"x = 1\ndef f():\n    return 1\ndef g():\n    pass\n"
tree = tree_sitter.Parser(py).parse(src)
root = tree.root_node

variants = [
    # capture inside the parens, before the predicate
    "(return_statement @r (#has-ancestor? @r function_definition))",
    "(return_statement @r (#has-ancestor? @r module))",
    "(return_statement @r (#has-ancestor? @r _))",
    # child capture + predicate referencing the child
    "(function_definition (block) @b (#has-ancestor? @b module))",
    # capture on the node, predicate on a child capture: does the child still
    # have the outer node as ancestor? (obviously yes, but check syntax)
    "(identifier @i (#has-ancestor? @i function_definition))",
    "(identifier @i (#has-ancestor? @i module))",
]
for scm in variants:
    try:
        q = tree_sitter.Query(py, scm)
        m = tree_sitter.QueryCursor(q).matches(root)
        kinds = {}
        for _pi, caps in m:
            for name, ns in caps.items():
                kinds.setdefault(name, set()).update(n.text for n in ns)
        print(f"{scm!r} -> {len(m)} matches {kinds}")
    except tree_sitter.QueryError as e:
        print(f"{scm!r} -> QueryError: {e}")
