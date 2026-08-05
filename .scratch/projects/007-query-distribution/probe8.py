"""Probe 8: clean single-gap spellings for the `...` path element."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import tree_sitter  # noqa: E402
import tree_sitter_python  # noqa: E402

py = tree_sitter.Language(tree_sitter_python.language())
src = b"x = 1\ndef f():\n    return 1\n"
tree = tree_sitter.Parser(py).parse(src)
root = tree.root_node


def show(label, scm):
    try:
        q = tree_sitter.Query(py, scm)
        m = tree_sitter.QueryCursor(q).matches(root)
        caps = []
        for _pi, c in m:
            caps.append({k: [n.text for n in v] for k, v in c.items()})
        print(f"{label}: {len(m)} matches {caps}")
    except tree_sitter.QueryError as e:
        print(f"{label}: QueryError: {e}")


# A: dup capture name (child + after-paren)
show("A dup-capture  ", "(expression_statement (assignment) @__anchor__ (#has-ancestor? @__anchor__ module)) @__anchor__")
# B: extra child capture @x + anchor after paren
show("B two-names    ", "(expression_statement (assignment) @x (#has-ancestor? @x module)) @__anchor__")
# C: wildcard child + anchor on the expr_statement root
show("C wildcard     ", "(expression_statement (assignment (_) @c (#has-ancestor? @c module))) @__anchor__")
# D: anchor on the assignment via a nested chain where the predicate sits on
#    the assignment captured as a child of expr_statement — with the DEEPEST
#    node also carrying the anchor capture:
show("E direct expr  ", "(expression_statement (assignment) @x (#has-ancestor? @x expression_statement)) @__anchor__")
# F: the simplest: anchor=the expr_statement (not the assignment)? no — anchor
#    is the innermost.
# G: capture the anchor on the root itself (module) — the gap node becomes the
#    record/scan target and the anchor is the DEEP node via nested pattern:
show("G root-anchored", "(module (assignment) @__anchor__) @m")

# H: does a nested child capture with the SAME name as an after-paren capture
#    on a DIFFERENT node break quantifiers? (B form with @__anchor__ twice)
show("H re-anchor    ", "(module (expression_statement (assignment) @__anchor__ (#has-ancestor? @__anchor__ module))) @__anchor__")
