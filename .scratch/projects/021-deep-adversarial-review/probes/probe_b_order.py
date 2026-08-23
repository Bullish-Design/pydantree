"""Probe B — emitted-pattern sibling order is the MODEL's field order."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))

import tree_sitter_python  # noqa: E402
from pydantree_sitter import Language, M, OutputModel, capture  # noqa: E402

py = Language.from_module(tree_sitter_python)


def hr(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


hr("declaration order name -> return_type (grammar order)")


class Ok(OutputModel):
    __match__ = M("module", "function_definition")
    name: str = capture("name")
    ret: str | None = capture("return_type")


e = py.extractor(Ok)
print("source:", e.query_source)
print("rows:", [(r.name, r.ret) for r in
                e.extract("def f() -> int: pass\ndef g(): pass\n")])

hr("declaration order return_type -> name (REVERSED)")


class Bad(OutputModel):
    __match__ = M("module", "function_definition")
    ret: str | None = capture("return_type")
    name: str = capture("name")


try:
    e2 = py.extractor(Bad)
    print("source:", e2.query_source)
    print("rows:", [(r.name, r.ret) for r in
                    e2.extract("def f() -> int: pass\n")])
except Exception as exc:
    print("RAISED:", type(exc).__name__)
    print(str(exc)[:400])

hr("same, but both required (no '?')")


class Bad2(OutputModel):
    __match__ = M("module", "function_definition")
    body: str = capture("body")
    name: str = capture("name")


try:
    e3 = py.extractor(Bad2)
    print("source:", e3.query_source)
    rows = e3.extract("def f(): pass\n")
    print("rows:", [(r.name, r.body) for r in rows])
except Exception as exc:
    print("RAISED:", type(exc).__name__)
    print(str(exc)[:400])

hr("schema-less bind with a VALID kind but a bogus field name")


class BogusField(OutputModel):
    __match__ = M("module", "function_definition")
    x: str = capture("no_such_field")


try:
    e4 = py.extractor(BogusField)
    print("source:", e4.query_source)
    print("rows:", e4.extract("def f(): pass\n"))
except Exception as exc:
    print("RAISED:", type(exc).__name__)
    print(str(exc)[:400])
