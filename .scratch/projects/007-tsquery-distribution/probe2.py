"""Probe 2: nesting semantics precisely."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / ".scratch" / "006-tsquery-bridge"))

import tree_sitter  # noqa: E402
import tree_sitter_python  # noqa: E402

py = tree_sitter.Language(tree_sitter_python.language())
src = b"x = 1\ndef f():\n    return 1\n"
tree = tree_sitter.Parser(py).parse(src)
root = tree.root_node


def count(scm):
    q = tree_sitter.Query(py, scm)
    return len(tree_sitter.QueryCursor(q).matches(root))


print("root type:", root.type)
print("module children:", [c.type for c in root.children])
fn = next(c for c in root.children if c.type == "function_definition")
print("function_definition children:", [c.type for c in fn.children])
block = next(c for c in fn.children if c.type == "block")
print("block children:", [c.type for c in block.children])

print()
print("(module (expression_statement))           ->", count("(module (expression_statement)) @m"),
      "(expression_statement IS a direct child)")
print("(module (function_definition))            ->", count("(module (function_definition)) @m"))
print("(module (return_statement))               ->", count("(module (return_statement)) @m"),
      "(return is a grandchild)")
print("(function_definition (return_statement))  ->", count("(function_definition (return_statement)) @m"),
      "(return under block = 1 level down)")
print("(module (assignment))                     ->", count("(module (assignment)) @m"))
print("(module (identifier))                     ->", count("(module (identifier)) @m"))
print("(expression_statement (assignment))       ->", count("(expression_statement (assignment)) @m"))

# has-ancestor with a bare type arg
try:
    q = tree_sitter.Query(py, "(return_statement) @r (#has-ancestor? @r function_definition)")
    print("\nhas-ancestor bare type: matches ->",
          len(tree_sitter.QueryCursor(q).matches(root)))
    q = tree_sitter.Query(py, "(return_statement) @r (#has-ancestor? @r module)")
    print("has-ancestor module: matches ->", len(tree_sitter.QueryCursor(q).matches(root)))
    q = tree_sitter.Query(py, "(identifier) @i (#has-ancestor? @i function_definition)")
    print("has-ancestor fn (identifier under fn): matches ->",
          len(tree_sitter.QueryCursor(q).matches(root)))
except tree_sitter.QueryError as e:
    print("QueryError:", e)

# does a deeper nesting with the intermediate node work?
print("\n(module (function_definition (block (return_statement)))) ->",
      count("(module (function_definition (block (return_statement)))) @m"))
