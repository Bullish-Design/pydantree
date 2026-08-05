"""Probe 3: has-ancestor details, repeated fields, sexp format, reparse."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / ".scratch" / "006-query-bridge"))

import tree_sitter  # noqa: E402
import tree_sitter_python  # noqa: E402
import pydantree_sitter_grammar as tg  # noqa: E402
from pydantree_sitter_grammar.language import load_language  # noqa: E402

py = tree_sitter.Language(tree_sitter_python.language())
src = b"x = 1\ndef f():\n    return 1\ndef g():\n    pass\n"
tree = tree_sitter.Parser(py).parse(src)
root = tree.root_node


def run(scm):
    q = tree_sitter.Query(py, scm)
    return tree_sitter.QueryCursor(q).matches(root)


print("== has-ancestor variants ==")
for scm in [
    "(return_statement) @r (#has-ancestor? @r function_definition)",
    "(return_statement) @r (#has-ancestor? @r module)",
    "(return_statement) @r (#has-ancestor? @r _)",
    "(identifier) @i (#has-ancestor? @i function_definition)",
    "(return_statement) @r (#has-ancestor? @r function_definition module)",
]:
    try:
        print(f"  {scm!r} ->", len(run(scm)))
    except tree_sitter.QueryError as e:
        print(f"  {scm!r} -> QueryError: {e}")

print("\n== has-ancestor with quoted type ==")
try:
    print("  quoted:", len(run('(return_statement) @r (#has-ancestor? @r "function_definition")')))
except tree_sitter.QueryError as e:
    print("  quoted -> QueryError:", e)

print("\n== sexp format of str(node) ==")
print(repr(str(root)))
fn = next(c for c in root.children if c.type == "function_definition")
print("function_definition str:")
print(str(fn))

print("\n== repeated fields ==")
g = tg.Grammar("repfld2")
g.rule("identifier", tg.pattern(r"[a-z]+"), word=True)
g.rule("params", tg.seq(
    tg.field("param", tg.ref("identifier")),
    tg.repeat(tg.seq(",", tg.field("param", tg.ref("identifier"))))))
g.rule("call", tg.seq(tg.ref("identifier"), "(", tg.ref("params"), ")"))
g.rule("source_file", tg.repeat(tg.ref("call")))
g.start("source_file")
res = tg.build_builder(g)
lang, _ = load_language(res.so_path, "repfld2")
t = tree_sitter.Parser(lang).parse(b"f(a, b, c)\n")
q = tree_sitter.Query(lang, "(params param: (identifier) @p) @par")
mm = tree_sitter.QueryCursor(q).matches(t.root_node)
print("unquantified repeated-field pattern ->", len(mm), "matches")
for pi, caps in mm:
    print("   @p:", [c.text for c in caps.get("p", [])],
          "| @par:", [c.text for c in caps.get("par", [])])
q2 = tree_sitter.Query(lang, "(call (params param: (identifier) @p)) @c")
mm2 = tree_sitter.QueryCursor(q2).matches(t.root_node)
print("anchored at call, repeated field ->", len(mm2), "matches")
for pi, caps in mm2:
    print("   @p:", [c.text for c in caps.get("p", [])])

print("\n== reparse ==")
p = tree_sitter.Parser(py)
t1 = p.parse(b"x = 1\n")
t2 = p.parse(b"x = 1\ny = 2\n", t1)
print("  incremental reparse ok:", str(t2.root_node).strip() == "(module\n  (expression_statement\n    (assignment left: (identifier) right: (integer)))\n  (expression_statement\n    (assignment left: (identifier) right: (integer))))")

print("\n== ERROR/MISSING node attrs for Diagnostics ==")
t3 = p.parse(b"def (\n")
def walk(n):
    if n.type == "ERROR" or n.is_missing:
        print(f"  {n.type} is_missing={n.is_missing} byte_range={n.byte_range} "
              f"start_point={n.start_point} text={n.text!r}")
    for c in n.children:
        walk(c)
walk(t3.root_node)
