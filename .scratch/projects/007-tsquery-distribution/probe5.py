"""Probe 5: has-ancestor with the predicate INSIDE the node parens."""
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

for scm in [
    "(return_statement (#has-ancestor? @r function_definition)) @r",
    "(return_statement (#has-ancestor? @r module)) @r",
    "(return_statement (#has-ancestor? @r _)) @r",
    "(identifier (#has-ancestor? @i function_definition)) @i",
    "(identifier (#has-ancestor? @i module)) @i",
    "(identifier (#has-ancestor? @i _)) @i",
]:
    try:
        q = tree_sitter.Query(py, scm)
        m = tree_sitter.QueryCursor(q).matches(root)
        print(f"{scm!r} -> {len(m)} matches")
    except tree_sitter.QueryError as e:
        print(f"{scm!r} -> QueryError: {e}")

# two-gap chain: can we express b-anywhere-under-a + d-anywhere-under-b in ONE pattern?
print("\n-- middle-gap attempts (d under b under a, both any-depth) --")
for scm in [
    # capture the intermediate b inside the same nested pattern? needs d nested in b (child-level) — no
    "(identifier (#has-ancestor? @i function_definition)) @i",
]:
    q = tree_sitter.Query(py, scm)
    print(f"{scm!r} ->", len(tree_sitter.QueryCursor(q).matches(root)))

# count all nodes for reference
def count_nodes(node):
    return 1 + sum(count_nodes(c) for c in node.children)
print("total nodes:", count_nodes(root))
