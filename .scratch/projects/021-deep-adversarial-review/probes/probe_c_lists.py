"""Probe C — repeated fields, anchor merge, duplicates, ambiguity."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))

import tree_sitter_python  # noqa: E402
from pydantree_sitter import (  # noqa: E402
    Language, M, OutputModel, capture, capture_kind, source_meta,
)

py = Language.from_module(tree_sitter_python)


def hr(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


hr("C1 — one repeated field (python subscript: value + subscript*)")


class Sub(OutputModel):
    __match__ = M("module", "expression_statement", "subscript")
    value: str = capture("value")
    subscript: list[str] = capture("subscript")


e = py.extractor(Sub)
print("q:", e.query_source)
for r in e.extract("a[1, 2, 3]\nb[9]\nc[]\n"):
    print("  value=", r.value, "subs=", r.subscript)

hr("C2 — repeated field + optional field on ONE anchor (duplicate risk)")


class Imp(OutputModel):
    __match__ = M("module", "import_from_statement")
    module_name: str = capture("module_name")
    name: list[str] = capture("name")


e = py.extractor(Imp)
print("q:", e.query_source)
for r in e.extract("from a.b import x, y, z\nfrom q import w\n"):
    print("  module=", r.module_name, "names=", r.name)

hr("C3 — TWO repeated fields on one anchor")
# python: `for_statement` left(multiple)/right(multiple)


class ForStmt(OutputModel):
    __match__ = M("module", "for_statement")
    left: list[str] = capture("left")
    right: list[str] = capture("right")


try:
    e = py.extractor(ForStmt)
    print("q:", e.query_source)
    for r in e.extract("for a, b in x, y, z:\n    pass\n"):
        print("  left=", r.left, "right=", r.right)
except Exception as exc:
    print("RAISED", type(exc).__name__, str(exc)[:300])

hr("C4 — scalar field fed by a repeated grammar field => AmbiguousCaptureError?")


class SubScalar(OutputModel):
    __match__ = M("module", "expression_statement", "subscript")
    value: str = capture("value")
    subscript: str = capture("subscript")


try:
    e = py.extractor(SubScalar)
    print("q:", e.query_source)
    for r in e.extract("a[1, 2, 3]\n"):
        print("  ->", r)
except Exception as exc:
    print("RAISED", type(exc).__name__, str(exc)[:300])

hr("C5 — capture_kind on positional children + list")


class Blk(OutputModel):
    __match__ = M("module", "function_definition", "block")
    stmts: list[str] = capture_kind("expression_statement")
    line: int = source_meta()


try:
    e = py.extractor(Blk)
    print("q:", e.query_source)
    for r in e.extract("def f():\n    a\n    b\n    c\n"):
        print("  line=", r.line, "stmts=", r.stmts)
except Exception as exc:
    print("RAISED", type(exc).__name__, str(exc)[:400])

hr("C6 — '...' gap path + anchor merge")


class Deep(OutputModel):
    __match__ = M("module", "...", "assignment")
    left: str = capture("left")


e = py.extractor(Deep)
print("q:", e.query_source)
print("rows:", [r.left for r in e.extract(
    "x = 1\ndef f():\n    y = 2\n    if q:\n        z = 3\n")])

hr("C7 — how many matches does tree-sitter give for a repeated '?' capture")
import tree_sitter  # noqa: E402
lang = py.language
q = tree_sitter.Query(
    lang, "(module (import_from_statement module_name:(_)? @m name:(_)? @n) @a)")
tree = py.parse("from a.b import x, y, z\n")
ms = tree_sitter.QueryCursor(q).matches(tree.root_node)
print("match count:", len(ms))
for pi, caps in ms:
    print("  pi", pi, {k: [n.text.decode() for n in v] for k, v in caps.items()})
