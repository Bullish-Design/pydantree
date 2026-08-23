"""Probe G — scaling of the cartesian merge + field order with a BOUND schema."""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests" / "fixtures" / "grammars"))

import pydantree_sitter_grammar as tg  # noqa: E402
from pydantree_sitter_grammar.pipeline import write_bundle  # noqa: E402
from pydantree_sitter import (  # noqa: E402
    Language, M, OutputModel, SchemaCheckError, capture,
)
import json_grammar  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="probe-g-"))


def hr(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


hr("G1 — field ORDER is load-bearing even with a bound schema")
jlang = Language.load_bundle(write_bundle(tg.build_builder(json_grammar.build()),
                                          TMP / "json"))


class PairOk(OutputModel):
    __match__ = M("document", "object", "pair")
    key: str = capture("key")
    value: str = capture("value")


class PairReversed(OutputModel):
    __match__ = M("document", "object", "pair")
    value: str = capture("value")
    key: str = capture("key")


for cls in (PairOk, PairReversed):
    try:
        e = jlang.extractor(cls)
        print(f"  {cls.__name__}: OK  q={e.query_source}")
    except Exception as exc:
        print(f"  {cls.__name__}: {type(exc).__name__}: {str(exc)[:160]}")
print("  -> the bind-time schema checks pass; the failure is a raw "
      "QueryBuildError from tree-sitter about a pattern the user never wrote.")

hr("G2 — cartesian blow-up: 3 repeated fields")
g = tg.Grammar("three")
g.rule("source_file", tg.repeat(tg.ref("item")))
g.rule("item", tg.seq(
    "(",
    tg.repeat(tg.field("a", tg.ref("word"))), ";",
    tg.repeat(tg.field("b", tg.ref("word"))), ";",
    tg.repeat(tg.field("c", tg.ref("word"))),
    ")"))
g.rule("word", tg.pattern(r"[a-z]+"))
g.start("source_file")
lang = Language.load_bundle(write_bundle(tg.build_builder(g), TMP / "three"))


class Item(OutputModel):
    __match__ = M("source_file", "item")
    a: list[str] = capture("a")
    b: list[str] = capture("b")
    c: list[str] = capture("c")


ext = lang.extractor(Item)
for n in (2, 4, 8, 12):
    words = " ".join("w" * 1 for _ in range(n))
    words = " ".join([f"w{i}" for i in range(n)]).replace("0", "a")
    words = " ".join(["ab"] * n)
    src = f"({words} ; {words} ; {words})"
    t0 = time.perf_counter()
    rows = ext.extract(src)
    dt = time.perf_counter() - t0
    r = rows[0]
    print(f"  n={n:3d} per field -> len(a)={len(r.a):6d} len(b)={len(r.b):6d} "
          f"len(c)={len(r.c):6d}   ({dt*1000:.1f} ms)   expected {n} each")

hr("G3 — the same shape with ONE list field is correct")


class ItemA(OutputModel):
    __match__ = M("source_file", "item")
    a: list[str] = capture("a")


exta = lang.extractor(ItemA)
src = "(" + " ".join(["ab"] * 12) + " ; x ; y)"
print("  len(a) =", len(exta.extract(src)[0].a), "(expected 12)")
