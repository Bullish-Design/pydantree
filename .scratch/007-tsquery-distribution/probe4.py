"""Probe 4: settle the has-ancestor match counts."""
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
    "(return_statement) @r",
    "(return_statement) @r (#has-ancestor? @r function_definition)",
    "(module (return_statement)) @r",
    "(module (function_definition (block (return_statement)))) @r",
]:
    q = tree_sitter.Query(py, scm)
    m = tree_sitter.QueryCursor(q).matches(root)
    print(f"{scm!r} -> {len(m)} matches")

# count return_statement nodes manually
def count_nodes(node, t):
    return (1 if node.type == t else 0) + sum(count_nodes(c, t) for c in node.children)
print("manual return_statement count:", count_nodes(root, "return_statement"))
print("manual function_definition count:", count_nodes(root, "function_definition"))
