"""Phase-5 probes: settle design questions against the installed 0.26 bindings.

  1. Nested pattern semantics: does `(a (b))` match b at ANY depth under a,
     or only as a direct child?
  2. Repeated fields: `(params param: (identifier) @p)` with a repeated field
     name — one match per occurrence, or one match with the first capture?
  3. `#has-ancestor?` — supported by Query()? What's its signature?
  4. str(node) sexp format — what does the bindings' built-in renderer look
     like (field names? anonymous tokens?)?
  5. Parser.parse(new_source, old_tree) — the incremental reparse.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / ".scratch" / "006-tsquery-bridge"))

import tree_sitter  # noqa: E402
import tree_sitter_python  # noqa: E402
import tsgrammar as tg  # noqa: E402
from tsgrammar.language import load_language  # noqa: E402
from tscore.schema import NodeSchema, derive_from_ir  # noqa: E402

EVIDENCE = Path(__file__).parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def banner(t: str, width: int = 76) -> None:
    print("\n" + "=" * width + f"\n{t}\n" + "=" * width)


# ---- 1. nesting: descendant vs child --------------------------------------
banner("1. nested pattern semantics: descendant or direct child?")
py = tree_sitter.Language(tree_sitter_python.language())
src = b"def f():\n    x = 1\n    return x + 1\n"
tree = tree_sitter.Parser(py).parse(src)
# `(module (return_statement))` — return_statement is at depth 3 under module
q = tree_sitter.Query(py, "(module (return_statement)) @m")
m = tree_sitter.QueryCursor(q).matches(tree.root_node)
print("(module (return_statement)) matches:", len(m),
      "-> nesting IS descendant-level" if len(m) else "-> no match (child-only)")
q2 = tree_sitter.Query(py, "(module (function_definition (return_statement))) @f")
m2 = tree_sitter.QueryCursor(q2).matches(tree.root_node)
print("(module (function_definition (return_statement))) matches:", len(m2))

# ---- 2. repeated fields ----------------------------------------------------
banner("2. repeated CST fields: one match per occurrence?")
g = tg.Grammar("repfld")
g.rule("identifier", tg.pattern(r"[a-z]+"), word=True)
g.rule("params", tg.seq(
    tg.field("param", tg.ref("identifier")),
    tg.repeat(tg.seq(",", tg.field("param", tg.ref("identifier"))))))
g.rule("call", tg.seq(tg.ref("identifier"), "(", tg.ref("params"), ")"))
g.rule("source_file", tg.repeat(tg.ref("call")))
g.start("source_file")
res = tg.build_builder(g)
lang, _ = load_language(res.so_path, "repfld")
t = tree_sitter.Parser(lang).parse(b"f(a, b, c)\n")
node = t.root_node
print("str(node):", str(node))
q = tree_sitter.Query(lang, "(params param: (identifier) @p) @par")
mm = tree_sitter.QueryCursor(q).matches(t.root_node)
print("repeated field, unquantified pattern -> matches:", len(mm))
for pi, caps in mm:
    print("   match pi=", pi, "param captures:", [c.text for c in caps.get("p", [])])
q3 = tree_sitter.Query(lang, "(params param: (identifier) @p)* @par")
mm3 = tree_sitter.QueryCursor(q3).matches(t.root_node)
print("with * quantifier -> matches:", len(mm3))
for pi, caps in mm3:
    print("   match pi=", pi, "param captures:", [c.text for c in caps.get("p", [])])

# ---- 3. has-ancestor -------------------------------------------------------
banner("3. #has-ancestor? support + semantics")
try:
    q4 = tree_sitter.Query(py, "(return_statement) @r (#has-ancestor? @r function_definition)")
    m4 = tree_sitter.QueryCursor(q4).matches(tree.root_node)
    print("(#has-ancestor? @r function_definition) matches:", len(m4),
          "(1 = return under the def)")
    q5 = tree_sitter.Query(py, "(return_statement) @r (#has-ancestor? @r module)")
    m5 = tree_sitter.QueryCursor(q5).matches(tree.root_node)
    print("(#has-ancestor? @r module) matches:", len(m5))
except tree_sitter.QueryError as e:
    print("QueryError:", e)

# ---- 4. sexp rendering -----------------------------------------------------
banner("4. the bindings' str(node) sexp format")
print("module node:")
print(str(tree.root_node))
print("named-child render of a function_definition:")
for c in tree.root_node.children:
    if c.type == "function_definition":
        print(str(c))
        break

# ---- 5. incremental reparse -------------------------------------------------
banner("5. Parser.parse(new_source, old_tree) — incremental reparse")
p = tree_sitter.Parser(py)
t1 = p.parse(b"x = 1\n")
t2 = p.parse(b"x = 1\ny = 2\n", t1)
print("old root:", str(t1.root_node).replace("\n", " "))
print("new root:", str(t2.root_node).replace("\n", " "))

print("\nprobes done")
