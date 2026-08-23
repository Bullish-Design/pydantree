"""Probe E — _check_path treats a multi-kind PathStep as a DESCENT CHAIN."""
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
    Language, M, OutputModel, SchemaCheckError, capture,
)
import json_grammar  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="probe-e-"))
res = tg.build_builder(json_grammar.build())
lang = Language.load_bundle(write_bundle(res, TMP / "json"))


def hr(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


hr("E1 — the 020 regression test's ACTUAL error message")


class BadPair(OutputModel):
    __match__ = M(("object", "array"))
    x: str = capture("pair")


try:
    lang.extractor(BadPair)
    print("no error")
except SchemaCheckError as e:
    print(e)
print("\n-> the test asserts only \"'array'\" and \"pair\" are in the message; "
      "both appear in the WRONG (chain) error, so the guard is vacuous.")

hr("E2 — a VALID alternation anchor is rejected outright")


class Either(OutputModel):
    """`object` or `array` are siblings under `document`; both are legal
    anchors. This is the documented alternation feature."""
    __match__ = M("document", ("object", "array"))
    x: str | None = capture("nope")


try:
    e = lang.extractor(Either)
    print("bind OK; q =", e.query_source)
except SchemaCheckError as exc:
    print("REJECTED:", str(exc)[:400])

hr("E3 — same, single-step alternation with a field valid on both")


class EitherOk(OutputModel):
    __match__ = M("document", ("object", "array"))


try:
    e = lang.extractor(EitherOk)
    print("bind OK; q =", e.query_source)
except Exception as exc:
    print("REJECTED:", type(exc).__name__, str(exc)[:400])

hr("E4 — alternation where kind[1] IS a child of kind[0] (accidentally passes)")


class Nested(OutputModel):
    __match__ = M(("object", "pair"))
    x: str | None = capture("value")


try:
    e = lang.extractor(Nested)
    print("bind OK; q =", e.query_source)
    print("rows:", [r.x for r in e.extract('{"a": "b"}')])
except Exception as exc:
    print("REJECTED:", type(exc).__name__, str(exc)[:400])
