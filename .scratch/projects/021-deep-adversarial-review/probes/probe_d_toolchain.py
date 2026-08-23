"""Probe D — needs the toolchain (devenv shell). Builds throwaway grammars."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests" / "fixtures" / "grammars"))

import pydantree_sitter_grammar as tg  # noqa: E402
from pydantree_sitter_grammar.pipeline import write_bundle  # noqa: E402
from pydantree_sitter import (  # noqa: E402
    JSON_VALUE_MAP, Language, M, OutputModel, capture, propose_value_map,
)


def hr(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


TMP = Path(tempfile.mkdtemp(prefix="probe-d-"))

# ---------------------------------------------------------------------------
hr("D1 — TWO repeated fields on one anchor: cartesian match blow-up?")

g = tg.Grammar("twolist")
g.rule("source_file", tg.repeat(tg.ref("item")))
g.rule("item", tg.seq(
    "(",
    tg.repeat(tg.field("a", tg.ref("word"))),
    ";",
    tg.repeat(tg.field("b", tg.ref("word"))),
    ")"))
g.rule("word", tg.pattern(r"[a-z]+"))
g.start("source_file")
res = tg.build_builder(g)
bundle = write_bundle(res, TMP / "twolist")
lang = Language.load_bundle(bundle)


class Item(OutputModel):
    __match__ = M("source_file", "item")
    a: list[str] = capture("a")
    b: list[str] = capture("b")


e = lang.extractor(Item)
print("q:", e.query_source)
for r in e.extract("(x y z ; p q)\n(m ; n)\n( ; )\n"):
    print("   a=", r.a, " b=", r.b)
print("EXPECT a=['x','y','z'] b=['p','q']  — duplicates mean cartesian merge")

import tree_sitter  # noqa: E402
q = tree_sitter.Query(lang.language,
                      "(source_file (item a:(_)? @a b:(_)? @b) @anc)")
tree = lang.parse("(x y z ; p q)")
ms = tree_sitter.QueryCursor(q).matches(tree.root_node)
print("raw tree-sitter match count for 3x2 occurrences:", len(ms))

# ---------------------------------------------------------------------------
hr("D2 — MISSING / ERROR nodes materialize silently")


class W(OutputModel):
    __match__ = M("source_file", "item")
    a: list[str] = capture("a")
    b: list[str] = capture("b")


rows = lang.extractor(W).extract("(x ;")     # truncated -> ERROR/MISSING
print("malformed source rows:", [(r.a, r.b) for r in rows])
t = lang.parse("(x ;")
print("tree has_error:", t.root_node.has_error)
print("sexp:", t.root_node)

# ---------------------------------------------------------------------------
hr("D3 — self-recursive nested record model")
import json_grammar  # noqa: E402

jres = tg.build_builder(json_grammar.build())
jbundle = write_bundle(jres, TMP / "json")
jlang = Language.load_bundle(jbundle)
print("schema kinds:", sorted(jlang.schema.named_kinds()))


class Rec(OutputModel):
    __match__ = M("document", "object", record=True)
    name: str | None = capture("name")
    inner: "Rec | None" = capture("inner")


try:
    jlang.extractor(Rec)
    print("bind OK")
except RecursionError:
    print("RecursionError (unbounded nested-extractor recursion)")
except Exception as exc:
    print("raised:", type(exc).__name__, str(exc)[:300])

# ---------------------------------------------------------------------------
hr("D4 — record mode: path alternation silently uses only the FIRST kind")


class RecAlt(OutputModel):
    __match__ = M("document", ("object", "array"), record=True)
    name: str | None = capture("name")


try:
    e = jlang.extractor(RecAlt)
    print("outer:", e.compiled.records.source)
    print("record_kind:", e.compiled.record_kind, "(declared object|array)")
except Exception as exc:
    print("raised:", type(exc).__name__, str(exc)[:300])

# ---------------------------------------------------------------------------
hr("D5 — field-mode alternation anchor: kind inferred from the UNION")

g2 = tg.Grammar("alt")
g2.rule("source_file", tg.repeat(tg.choice(tg.ref("na"), tg.ref("nb"))))
g2.rule("na", tg.seq("a", tg.field("v", tg.ref("num"))))
g2.rule("nb", tg.seq("b", tg.field("v", tg.ref("word"))))
g2.rule("num", tg.pattern(r"[0-9]+"))
g2.rule("word", tg.pattern(r"[a-z]+"))
g2.start("source_file")
r2 = tg.build_builder(g2)
b2 = write_bundle(r2, TMP / "alt")
lang2 = Language.load_bundle(b2)


class Alt(OutputModel):
    __match__ = M("source_file", ("na", "nb"))
    v: int = capture("v")


try:
    e = lang2.extractor(Alt)
    print("q:", e.query_source)
    print("rows:", [r.v for r in e.extract("a 1\nb zz\na 2\n")])
    print("EXPECT: bind should flag that `nb.v` can never be an int")
except Exception as exc:
    print("raised:", type(exc).__name__, str(exc)[:400])

# ---------------------------------------------------------------------------
hr("D6 — cross-language extract_tree has no guard")


class Item2(OutputModel):
    __match__ = M("source_file", "item")
    a: list[str] = capture("a")


ext = lang.extractor(Item2)
alien = lang2.parse("a 1\n")
try:
    print("cross-language rows:", ext.extract_tree(alien))
except Exception as exc:
    print("raised:", type(exc).__name__, str(exc)[:200])

# ---------------------------------------------------------------------------
hr("D7 — propose_value_map on a non-JSON grammar + record mode")
vm = propose_value_map(lang2.schema)
print("proposed:", vm.model_dump())

print("\nTMP =", TMP)
