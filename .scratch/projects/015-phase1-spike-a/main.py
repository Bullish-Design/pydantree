#!/usr/bin/env python3
"""
Phase 1 spike runner — the three-way comparison + failure modes.

    devenv shell -- python spike-a/main.py

Sections:
  1. DSL -> .scm acceptance (every query compiles against the real grammar).
  2. Python task: raw vs DSL-lazy vs DSL-typed, checked against hand-computed
     ground truth.
  3. JSON task: raw vs DSL-lazy vs DSL-typed, checked against ground truth.
  4. Failure modes: typo'd node kind / field / capture; int from bad text;
     missing capture; malformed input; validate().
  5. Summary + the diagnostics surface.
"""

from __future__ import annotations

import sys
import traceback

import tree_sitter
import tree_sitter_json
import tree_sitter_python

import tasks_json
import tasks_python
from dsl import Query, QueryBuildError, cap, node
from materialize import (AmbiguousCaptureError, CoercionError, ExtractionError,
                         OutputModel, binding_warnings, capture)
from materialize import extract_records


def banner(t: str) -> None:
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


def load(module) -> tree_sitter.Language:
    return tree_sitter.Language(module.language())


def section1() -> None:
    banner("1. DSL -> .scm acceptance (real Query() constructor is the validator)")
    langs = {"python": load(tree_sitter_python), "json": load(tree_sitter_json)}
    queries = {
        "python-assign (tasks_python.ASSIGN_QUERY)": tasks_python.ASSIGN_QUERY,
        "json-records (tasks_json.RECORDS_QUERY)": tasks_json.RECORDS_QUERY,
        "json-fields (tasks_json.FIELDS_QUERY)": tasks_json.FIELDS_QUERY,
    }
    for name, q in queries.items():
        gname = "python" if "python" in name else "json"
        q.compile(langs[gname])
        warns = q.check()
        print(f"  OK  {name}\n      {q.source.splitlines()[0]} ..."
              f" ({len(q.specs)} pattern(s))")
        for w in warns:
            print(f"      DSL check: {w}")
    print("  All emitted .scm accepted by tree_sitter.Query().")


def _norm(models) -> list[dict]:
    out = []
    for m in models:
        d = dict(m) if hasattr(m, "__iter__") and not hasattr(m, "model_dump") \
            else m.model_dump()
        out.append(d)
    return out


def _compare(tag: str, got, expected) -> bool:
    ok = got == expected
    if ok:
        print(f"  PASS {tag}: {len(got)} result(s) match ground truth")
    else:
        print(f"  FAIL {tag}:\n    got:      {got}\n    expected: {expected}")
    return ok


def section2() -> None:
    banner("2. PYTHON task — three implementations vs ground truth")
    lang = load(tree_sitter_python)
    src = tasks_python.SAMPLE.encode()
    got_raw = tasks_python.raw_extract(lang, src)
    got_lazy = tasks_python.dsl_lazy_extract(lang, src)
    got_typed = _norm(tasks_python.dsl_typed_extract(lang, src))
    _compare("raw      ", got_raw, tasks_python.GROUND_TRUTH)
    _compare("dsl-lazy ", got_lazy, tasks_python.GROUND_TRUTH)
    _compare("dsl-typed", got_typed, tasks_python.GROUND_TRUTH)
    print("  typed models:")
    for a in tasks_python.dsl_typed_extract(lang, src):
        print(f"    {a}")


def section3() -> None:
    banner("3. JSON task — three implementations vs ground truth")
    lang = load(tree_sitter_json)
    src = tasks_json.SAMPLE.encode()
    got_raw = tasks_json.raw_extract(lang, src)
    got_lazy = tasks_json.dsl_lazy_extract(lang, src)
    got_typed = _norm(tasks_json.dsl_typed_extract(lang, src))
    _compare("raw      ", got_raw, tasks_json.GROUND_TRUTH)
    _compare("dsl-lazy ", got_lazy, tasks_json.GROUND_TRUTH)
    _compare("dsl-typed", got_typed, tasks_json.GROUND_TRUTH)
    print("  typed models:")
    for p in tasks_json.dsl_typed_extract(lang, src):
        print(f"    {p}")


# ---------------------------------------------------------------------------
# Section 4: failure modes
# ---------------------------------------------------------------------------

def _run(fn) -> tuple[str, str]:
    """Run fn(); return (kind, message)."""
    try:
        fn()
        return "no-error", "(nothing raised — silent outcome)"
    except Exception as e:
        return type(e).__name__, str(e).splitlines()[0][:120]


def _run_full(fn) -> tuple[str, str]:
    """Like _run but returns the full, untruncated message."""
    try:
        fn()
        return "no-error", "(nothing raised — silent outcome)"
    except Exception as e:
        return type(e).__name__, str(e)


def section4(langs: dict[str, tree_sitter.Language]) -> None:
    banner("4. FAILURE MODES — where does each approach surface the error?")
    plang, jlang = langs["python"], langs["json"]
    psrc = b"WIDTH = 1920\nok = 1\n"
    jsrc = tasks_json.SAMPLE.encode()

    print("\n--- 4.1 typo a node kind: 'assignment' -> 'assignmnt' ---")
    def raw_bad_kind():
        tree_sitter.Query(plang, "(module (assignmnt (identifier) @x))")
    def dsl_bad_kind():
        Query(node("module").child(node("assignmnt")
                                   .child(node("identifier").capture("x")))) \
            .compile(plang)
    for tag, fn in [("raw ", raw_bad_kind), ("dsl ", dsl_bad_kind)]:
        kind, msg = _run(fn)
        print(f"  {tag}: {kind} — {msg}")

    print("\n--- 4.2 typo a field name: 'left' -> 'leftt' ---")
    def raw_bad_field():
        tree_sitter.Query(plang, "(assignment leftt: (identifier) @x)")
    def dsl_bad_field():
        Query(node("assignment").child(field="leftt",
                                       node=node("identifier").capture("x"))) \
            .compile(plang)
    for tag, fn in [("raw ", raw_bad_field), ("dsl ", dsl_bad_field)]:
        kind, msg = _run(fn)
        print(f"  {tag}: {kind} — {msg}")

    print("\n--- 4.3 typo a capture name: @namee vs field name 'name' ---")
    tree = tree_sitter.Parser(plang).parse(psrc)
    def raw_bad_capture():
        # query captures @namee; consumer reads caps["name"] -> KeyError at
        # runtime, after a silent no-warning query build
        q = tree_sitter.Query(plang, "(assignment (identifier) @namee)")
        for _pi, caps in tree_sitter.QueryCursor(q).matches(tree.root_node):
            caps["name"][0].text
    def dsl_bad_capture():
        class M(OutputModel):
            name: str
        q = Query(node("assignment")
                  .child(node("identifier").capture("namee")))
        q.extract(tree, into=M)   # binding check warns; field always missing
    for tag, fn in [("raw ", raw_bad_capture), ("dsl ", dsl_bad_capture)]:
        kind, msg = _run(fn)
        print(f"  {tag}: {kind} — {msg}")

    print("\n--- 4.4 int field fed from non-numeric text (wildcard value) ---")
    # JSON: a record with age: "unknown" (a string where an int is wanted).
    # The value node is captured with a wildcard so BOTH paths try to coerce.
    bad_src = b'[{"name": "zoe", "age": "unknown", "tags": []}]'
    WILD_AGE = """\
(pair key: (string (string_content) @key) value: (_) @age (#eq? @key "age"))
"""

    def raw_bad_int():
        tree = tree_sitter.Parser(jlang).parse(bad_src)
        q = tree_sitter.Query(jlang, WILD_AGE)
        for _pi, caps in tree_sitter.QueryCursor(q).matches(tree.root_node):
            return int(caps["age"][0].text.decode())   # ValueError, unwrapped
        return None

    class BadAge(OutputModel):
        name: str = capture("name")
        age: int = capture("age")

    bad_age_query = Query(
        node("pair")
        .child(field="key",
               node=node("string")
               .child(node=node("string_content").capture("key")))
        .child(field="value", node=node(None).capture("age"))
        .where(cap("key").eq("age")),
        node("pair")
        .child(field="key",
               node=node("string")
               .child(node=node("string_content").capture("key")))
        .child(field="value",
               node=node("string")
               .child(node=node("string_content").capture("name")))
        .where(cap("key").eq("name")),
    )

    def dsl_typed_bad_int():
        tree = tree_sitter.Parser(jlang).parse(bad_src)
        return bad_age_query.extract(tree, into=BadAge)

    kind, msg = _run(raw_bad_int)
    print(f"  raw      : {kind} — {msg}")
    kind, msg = _run_full(dsl_typed_bad_int)
    print(f"  dsl-typed: {kind}")
    print("    " + msg.replace("\n", "\n    "))

    print("\n--- 4.5 required field with no capture at all ---")
    class NeedsNickname(OutputModel):
        name: str
        nickname: str     # required, no default, sample has no key in carol
    def typed_missing():
        extract_records(tree_sitter.Parser(jlang).parse(jsrc),
                        tasks_json.RECORDS_QUERY, tasks_json.FIELDS_QUERY,
                        into=NeedsNickname)
    kind, msg = _run_full(typed_missing)
    print(f"  dsl-typed: {kind}")
    print("    " + msg.replace("\n", "\n    "))

    print("\n--- 4.6 malformed input: validate() ---")
    good_tree = tree_sitter.Parser(jlang).parse(
        b'{"name": "ok", "age": 1, "tags": []}')
    bad_tree = tree_sitter.Parser(jlang).parse(
        b'{"name": "ok", "age": 1, "tags": [}')
    clean, diags = tasks_json.RECORDS_QUERY.validate(good_tree)
    clean2, diags2 = tasks_json.RECORDS_QUERY.validate(bad_tree)
    print(f"  clean JSON:    validate()={clean}")
    print(f"  malformed JSON: validate()={clean2}")
    for d in diags2[:3]:
        print(f"    {d['kind']} node at line {d['line']}, "
              f"byte_range={d['byte_range']}, snippet={d['snippet']!r}")

    print("\n--- 4.7 scalar field fed by MULTIPLE captures (nested collision) ---")
    nested_src = b'[{"name": "a", "age": 1, "tags": [], "meta": {"name": "inner"}}]'
    def typed_collision():
        extract_records(tree_sitter.Parser(jlang).parse(nested_src),
                        tasks_json.RECORDS_QUERY, tasks_json.FIELDS_QUERY,
                        into=tasks_json.Person)
    kind, msg = _run_full(typed_collision)
    print(f"  dsl-typed: {kind}")
    print("    " + msg.replace("\n", "\n    "))


def section5() -> None:
    banner("5. DSL cheap checks (no grammar introspection)")
    # a predicate referencing a capture that no pattern declares
    q = Query(node("module")
              .child(node("identifier").capture("name"))
              .where(cap("name").matches(r"^A"))
              .where(cap("nmae").eq("x")))
    for w in q.check():
        print(f"  check: {w}")

    # binding warnings: field fed from a capture the query never makes
    class Bad(OutputModel):
        name: str
        val: int        # no capture @val anywhere in the query

    print("  binding_warnings(Bad):")
    for w in binding_warnings(q, Bad):
        print(f"    - {w}")


def main() -> None:
    langs = {"python": load(tree_sitter_python), "json": load(tree_sitter_json)}
    section1()
    section2()
    section3()
    section4(langs)
    section5()
    banner("DONE — verdict + side-by-side code in FINDINGS.md")


if __name__ == "__main__":
    main()
