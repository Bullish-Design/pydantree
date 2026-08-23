"""Probe A — Product A core claims.

Run: .devenv/state/venv/bin/python .scratch/projects/021-deep-adversarial-review/probes/probe_a_core.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))

from pydantree_sitter import (  # noqa: E402
    JSON_VALUE_MAP,
    Language,
    M,
    NodeKind,
    NodeSchema,
    OutputModel,
    PydantreeSitterError,
    RawQuery,
    capture,
)

FIX = REPO / "tests" / "fixtures"


def hr(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# ---------------------------------------------------------------------------
hr("P1 — README headline: from_module gives NO schema => NO checks")
import tree_sitter_python  # noqa: E402

lang = Language.from_module(tree_sitter_python)
print("schema bound?", lang.schema)


class Bogus(OutputModel):
    __match__ = M("module", "not_a_real_kind_at_all")
    name: str = capture("nope_not_a_field")


try:
    ext = lang.extractor(Bogus)
    print("bind SUCCEEDED with a nonexistent kind + nonexistent field")
    print("emitted:", ext.query_source)
    print("rows:", ext.extract("x = 1\n"))
except PydantreeSitterError as e:
    print("bind raised:", type(e).__name__, e)


# ---------------------------------------------------------------------------
hr("P2 — self-recursive nested record model")
schema = NodeSchema.from_node_types_json(FIX / "jsonlike" / "node-types.json")
print("jsonlike kinds:", sorted(schema.named_kinds()))

import tree_sitter_json  # noqa: E402

jlang = Language.from_module(tree_sitter_json,
                             schema=str(FIX / "jsonlike" / "node-types.json"))


class Node(OutputModel):
    __match__ = M("document", "object", record=True)
    name: str | None = capture("name")
    child: "Node | None" = capture("child")


try:
    jlang.extractor(Node)
    print("bind OK (no recursion problem)")
except RecursionError as e:
    print("RecursionError:", str(e)[:120])
except Exception as e:
    print("other:", type(e).__name__, str(e)[:300])


# ---------------------------------------------------------------------------
hr("P3 — two field-mode list[str] fields on one anchor: duplicates?")
# use the real python grammar: a call has function + arguments
py = Language.from_module(tree_sitter_python)


class Params(OutputModel):
    __match__ = M("module", "function_definition")
    name: str = capture("name")
    body: list[str] = capture("body")
    params: list[str] = capture("parameters")


src = "def f(a, b, c):\n    x = 1\n    y = 2\n    z = 3\n"
rows = py.extractor(Params).extract(src)
for r in rows:
    print("name=", r.name, "n_body=", len(r.body), "n_params=", len(r.params))
    print("   body=", r.body)
    print("   params=", r.params)


# ---------------------------------------------------------------------------
hr("P3b — repeated fielded child, single list field")


class Args(OutputModel):
    __match__ = M("module", "expression_statement", "call", "argument_list")
    args: list[str] = capture("__NOFIELD__")


class Elts(OutputModel):
    __match__ = M("module", "expression_statement", "list")
    # python's `list` uses no field names for elements -> use capture_kind
    pass


# python 'dictionary' pair has key/value fields; use 'parameters' children
class Fn2(OutputModel):
    __match__ = M("module", "function_definition")
    ret: list[str] = capture("return_type")
    name: str = capture("name")


try:
    rows = py.extractor(Fn2).extract("def f() -> int: pass\ndef g(): pass\n")
    print("Fn2 rows:", [(r.name, r.ret) for r in rows])
except Exception as _e:
    print("RAISED", type(_e).__name__, str(_e)[:220])


# ---------------------------------------------------------------------------
hr("P4 — cross-language extract_tree (no guard?)")
tree_py = py.parse("x = 1\n")


class Assign(OutputModel):
    __match__ = M("module", "expression_statement", "assignment")
    left: str = capture("left")


ext = py.extractor(Assign)
print("same-language rows:", [r.left for r in ext.extract_tree(tree_py)])
tree_json = jlang.parse('{"a": 1}')
try:
    out = ext.extract_tree(tree_json)
    print("CROSS-LANGUAGE extract_tree returned:", out)
except Exception as e:
    print("cross-language raised:", type(e).__name__, str(e)[:200])


# ---------------------------------------------------------------------------
hr("P5 — record mode ignores path alternation + non-first anchor kinds")
from pydantree_sitter.compiler import compile_spec  # noqa: E402
from pydantree_sitter.binding import resolve_value_map  # noqa: E402


class RecAlt(OutputModel):
    __match__ = M("document", ("object", "array"), record=True)
    a: str | None = capture("a")


try:
    c = compile_spec(RecAlt, jlang, value_map=resolve_value_map(RecAlt, jlang))
    print("record_kind chosen:", c.record_kind, " (path declared object|array)")
    print("outer query:", c.records.source)
except Exception as e:
    print("raised:", type(e).__name__, str(e)[:300])


# ---------------------------------------------------------------------------
hr("P6 — record key shapes: only the FIRST is emitted")
from pydantree_sitter.compiler import _key_shapes, _find_pair_kind  # noqa: E402

for fixture in ("jsonlike", "nix", "rust"):
    p = FIX / fixture / "node-types.json"
    if not p.exists():
        continue
    s = NodeSchema.from_node_types_json(p)
    for rk in sorted(s.named_kinds()):
        try:
            pk = _find_pair_kind(s, rk)
        except Exception:
            continue
        ks = _key_shapes(s, pk)
        if len(ks) > 1:
            print(f"{fixture}: record {rk!r} pair {pk!r} has {len(ks)} key "
                  f"shapes {ks} — only {ks[0]} is emitted")


# ---------------------------------------------------------------------------
hr("P7 — alternation anchor: field kind inferred from the UNION, emitted for ALL")
from pydantree_sitter.compiler import _infer_field_kind  # noqa: E402

pyschema_path = None
print("(see analysis: _infer_field_kind unions over anchors, "
      "_combinations emits the same kind for every anchor pattern)")


# ---------------------------------------------------------------------------
hr("P8 — C2 claim: 'never silent name-regex inference' vs _scalar_of fallback")
from pydantree_sitter.compiler import _scalar_of, _kind_coerces  # noqa: E402
from pydantree_sitter.valuemap import ValueMap  # noqa: E402

s = NodeSchema.from_node_types_json(FIX / "rust" / "node-types.json")
empty = ValueMap()
hits = []
for k in sorted(s.kinds()):
    got = _scalar_of(s, empty, k)
    if got in ("int", "float", "bool", "null"):
        hits.append((k, got))
print(f"with an EMPTY (committed) ValueMap, the name-regex draft still "
      f"assigns a scalar meaning to {len(hits)} rust kinds; sample:")
for k, v in hits[:12]:
    print("   ", k, "->", v)


# ---------------------------------------------------------------------------
hr("P9 — WasmRuntimeUnavailableError is outside the taxonomy")
from pydantree_sitter.loader import WasmRuntimeUnavailableError  # noqa: E402
print("MRO:", [c.__name__ for c in WasmRuntimeUnavailableError.__mro__])
print("is a PydantreeSitterError?",
      issubclass(WasmRuntimeUnavailableError, PydantreeSitterError))
import pydantree_sitter  # noqa: E402
print("exported from pydantree_sitter?",
      "WasmRuntimeUnavailableError" in pydantree_sitter.__all__)


# ---------------------------------------------------------------------------
hr("P10 — RawQuery is decorative: a plain str works identically")


class RawPlain(OutputModel):
    __raw_query__ = "(assignment left: (_) @left)"
    left: str = capture("left")


print("plain-str raw query rows:",
      [r.left for r in py.extractor(RawPlain).extract("x = 1\ny = 2\n")])


# ---------------------------------------------------------------------------
hr("P11 — Extractor cache keyed on (model, strict) never evicts")
print("Language._extractors is a plain dict, no bound:",
      type(py._extractors), len(py._extractors))


# ---------------------------------------------------------------------------
hr("P12 — bundle_format 0 / negative accepted")
print("loader accepts any int <= 2 including 0 and negatives (see loader.py)")
