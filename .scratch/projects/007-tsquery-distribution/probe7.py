"""Probe 7: capture-after-predicate inside the parens + middle-gap feasibility."""
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
    # capture AFTER the predicate, still inside the parens
    "(return_statement (#has-ancestor? @r module) @r)",
    "(identifier (#has-ancestor? @i function_definition) @i)",
    # wildcard child + predicate on the wildcard, anchor after paren
    "(return_statement (_) @c (#has-ancestor? @c module)) @r",
    # does the wildcard require a child? try with a leaf-ish node
    "(identifier (_) @c (#has-ancestor? @c module)) @i",
]:
    try:
        q = tree_sitter.Query(py, scm)
        m = tree_sitter.QueryCursor(q).matches(root)
        print(f"{scm!r} -> {len(m)} matches")
    except tree_sitter.QueryError as e:
        print(f"{scm!r} -> QueryError: {e}")

# the '...' via has-ancestor: check that a deep node's capture works with the
# predicate on the SAME node when captured via a nested structure.
# Trick: (module (_) @c) requires a direct child. Instead try:
#   (assignment (#has-ancestor? @a module)) — invalid (capture after).
print()
print("-- the single-gap spelling candidates --")
for scm in [
    "(assignment (_) @c (#has-ancestor? @c module)) @a",
    "(assignment (identifier) @c (#has-ancestor? @c module)) @a",
]:
    try:
        q = tree_sitter.Query(py, scm)
        m = tree_sitter.QueryCursor(q).matches(root)
        caps = []
        for _pi, c in m:
            caps.append({k: [n.text for n in v] for k, v in c.items()})
        print(f"{scm!r} -> {len(m)} matches {caps}")
    except tree_sitter.QueryError as e:
        print(f"{scm!r} -> QueryError: {e}")
