#!/usr/bin/env python3
"""
Spike-a2 runner — model-only extraction ("the model IS the query").

    devenv shell -- python spike-a2/main.py

Sections:
  1. Both tasks, model-only, vs hand-computed ground truth (CST fidelity).
  2. The derived .scm for both (proof the user never writes it).
  3. Expressibility battery: no-arg capture, Eq/AnyOf predicates, NodeKind
     alternation, lenient mode, derived fields, UnsupportedShape error.
  4. Failure modes: where does each mistake surface (import time vs extract).
  5. The "only way" claim: what the model can and cannot express (gaps).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, ForwardRef

import tree_sitter_json
import tree_sitter_python

sys.path.insert(0, str(Path(__file__).parent))

import typed  # noqa: E402
from tasks import (Assignment, JSON_GROUND_TRUTH, JSON_SAMPLE, PY_GROUND_TRUTH,  # noqa: E402
                   PY_SAMPLE, Person)
from typed import (AnyOf, Eq, M, Matches, NodeKind, OutputModel,  # noqa: E402
                   UnsupportedShapeError, capture, source_meta)


def banner(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


# --- module-level battery models (nested refs need module globals) ---

class Address(OutputModel):
    __match__ = M("document", "object", record=True)
    city: str


class PersonNested(OutputModel):
    __match__ = M("document", "array", "object", record=True)
    name: str
    address: Address | None = None


def norm(models):
    return [m.model_dump() for m in models]


def section1() -> None:
    banner("1. Both tasks model-only — vs hand-computed ground truth")
    got = norm(Assignment.extract(PY_SAMPLE, language=tree_sitter_python))
    ok = got == PY_GROUND_TRUTH
    print(f"  Assignment: {'PASS' if ok else 'FAIL'} ({len(got)} rows)")
    if not ok:
        print("   ", got, PY_GROUND_TRUTH)
    got = norm(Person.extract(JSON_SAMPLE, language=tree_sitter_json))
    ok = got == JSON_GROUND_TRUTH
    print(f"  Person:     {'PASS' if ok else 'FAIL'} ({len(got)} rows)")
    if not ok:
        print("   ", got, JSON_GROUND_TRUTH)


def section2() -> None:
    banner("2. The user never writes this — derived .scm (for the record)")
    print("  Assignment:")
    for line in Assignment.compiled_source().splitlines():
        print(f"    {line}")
    print("  Person (outer):")
    print(f"    {Person._derived_cache.records.source}")
    print("  Person (inner, 6 patterns from 6 fields):")
    for line in Person._derived_cache.fields.source.splitlines():
        if line.strip():
            print(f"    {line}")


# --------------------------------------------------------------------------
# Expressibility battery
# --------------------------------------------------------------------------

def section3() -> None:
    banner("3. Expressibility battery — what the model alone can express")

    # 3.1 no-arg capture: attr name IS the CST field name
    class Func(OutputModel):
        __match__ = M("module", "function_definition")
        name: str = capture()          # CST field "name" on function_definition
        line: int = source_meta()

    funcs = Func.extract("def main():\n    pass\ndef helper():\n    pass\n",
                         language=tree_sitter_python)
    print("  3.1 no-arg capture (name: str = capture()):",
          [(f.name, f.line) for f in funcs])

    # 3.2 Eq predicate filters records at query level
    class Admin(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: Annotated[str, Eq("alice")]
        age: int

    admins = Admin.extract(JSON_SAMPLE, language=tree_sitter_json)
    print("  3.2 Eq predicate (#eq? @name \"alice\"):",
          [(a.name, a.age) for a in admins])

    # 3.3 AnyOf predicate
    class Some(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: Annotated[str, AnyOf("alice", "dave")]
        age: int

    some = Some.extract(JSON_SAMPLE, language=tree_sitter_json)
    print("  3.3 AnyOf predicate:", sorted((s.name, s.age) for s in some))

    # 3.4 NodeKind tuple = alternation (two patterns, one capture)
    class Flags(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        flag: Annotated[bool, NodeKind(("true", "false"))]

    flags = Flags.extract(
        '[{"name": "a", "flag": true}, {"name": "b", "flag": false}]',
        language=tree_sitter_json)
    print("  3.4 NodeKind(('true','false')) -> 2 patterns:",
          [(f.name, f.flag) for f in flags])

    # 3.5 lenient mode: malformed records skipped, good ones returned
    bad = '[{"name": "a", "age": 1, "tags": []}, {"name": "zoe", "age": "x", "tags": []}]'
    strict = None
    try:
        Person.extract(bad, language=tree_sitter_json)
    except typed._ExtractionError as e:
        strict = e
    lenient = Person.extract(bad, language=tree_sitter_json, strict=False)
    print("  3.5 lenient: strict raised"
          + ("" if strict else " (NO — should have raised!)")
          + f"; lenient returned {len(lenient)} row(s):",
          [(p.name, p.age) for p in lenient])

    # 3.6 derived field: attr with a default, no capture, never populated
    class Tagged(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: Annotated[str, NodeKind("identifier")] = capture("left")
        value: Annotated[int, NodeKind("integer")] = capture("right")
        source: str = "spike"

    tagged = Tagged.extract("X = 1", language=tree_sitter_python)
    print("  3.6 derived field (constant default):",
          [(t.name, t.value, t.source) for t in tagged])

    # 3.7 unsupported shape raises a clear error at class creation
    try:
        class BadList(OutputModel):
            __match__ = M("document", "object", record=True)
            vals: list[bool]
    except UnsupportedShapeError as e:
        print(f"  3.7 list[bool] in JSON v1: UnsupportedShapeError at "
              f"class creation — {e}")

    # 3.8 nested OutputModel: a field typed as another model
    # (Address/PersonNested defined at module level — nested model references
    # must resolve in the defining module's globals, pydantic standard)
    nested_src = ('[{"name": "alice", "age": 30, "tags": []},'
                  ' {"name": "carol", "age": 25, "tags": [],'
                  '  "address": {"city": "Paris", "zip": 75001}}]')
    nested_out = PersonNested.extract(nested_src, language=tree_sitter_json)
    print("  3.8 nested OutputModel (address: Address | None):")
    for p in nested_out:
        addr = f"{p.address.city}" if p.address else None
        print(f"      {p.name}: address={addr}")


# --------------------------------------------------------------------------
# Failure modes
# --------------------------------------------------------------------------

def section4() -> None:
    banner("4. Failure modes — where each mistake surfaces")

    # 4.1 typo node kind in the path
    try:
        class Bad(OutputModel):
            __match__ = M("module", "expression_statement", "assignmnt")
            name: str = capture("left")
        Bad.validate_with(tree_sitter_python)
        print("  4.1 typo kind: NOT caught?!")
    except Exception as e:
        print(f"  4.1 typo kind in path: {type(e).__name__} at validate_with:"
              f" {str(e).splitlines()[0][:90]}")

    # 4.2 typo CST field name in capture()
    try:
        class Bad2(OutputModel):
            __match__ = M("module", "expression_statement", "assignment")
            name: str = capture("leftt")
        Bad2.validate_with(tree_sitter_python)
        print("  4.2 typo field: NOT caught?!")
    except Exception as e:
        print(f"  4.2 typo field in capture(): {type(e).__name__} at "
              f"validate_with: {str(e).splitlines()[0][:90]}")

    # 4.3 model-warning (computed at class creation, printed at first
    # extract, before any parsing): required field with no capture binding
    import io
    from contextlib import redirect_stderr
    buf = io.StringIO()

    class Lazy(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str = capture("left")
        value: int = capture("right")
        mystery: int          # no capture, no default

    print("  4.3 required field with no binding:")
    with redirect_stderr(buf):
        try:
            Lazy.extract("X = 1", language=tree_sitter_python)
        except typed._ExtractionError as e:
            print(f"      ...and at extract: {type(e).__name__} — "
                  f"{str(e).splitlines()[-1][:100]}")
    for line in buf.getvalue().strip().splitlines():
        print("     ", line)

    # 4.4 nested key collision -> AmbiguousCaptureError
    nested = '[{"name": "a", "age": 1, "tags": [], "meta": {"name": "inner"}}]'
    try:
        Person.extract(nested, language=tree_sitter_json)
        print("  4.4 nested collision: NOT caught?!")
    except typed._ExtractionError as e:
        print(f"  4.4 nested key collision: {type(e).__name__} — "
              f"{str(e).splitlines()[-1][:120]}")


# --------------------------------------------------------------------------
# The "only way" audit
# --------------------------------------------------------------------------

GAPS = [
    ("node-kind match precision",
     "pydantic types coerce, they don't filter. `value: int` with a wildcard "
     "capture matches non-integer RHS (TITLE, RATIO) and fails in strict mode. "
     "The typed fix exists: Annotated[..., NodeKind('integer')] filters at "
     "query level. Question: should int-typed captures default to numeric "
     "node kinds? That is grammar-specific — the node-schema bridge would "
     "answer it."),
    ("field-mode lists",
     "a list field in FIELD mode (repeated children into one match, e.g. "
     "function params) is not supported — the spike's repeat semantics are "
     "one-match-per-element, which record mode absorbs via merge. A field-mode "
     "list needs the same anchor-merge machinery (params of one def) — "
     "designed but not built."),
    ("nested OutputModels",
     "implemented (3.8): a field typed as another OutputModel materializes "
     "the value node with the nested model's own record machinery. Limits: "
     "nested models must be record-mode; the nested path in M() is ignored "
     "when nested; a predicate-filtered nested record materializes as missing."),
    ("non-JSON record shapes",
     "the record VALUE shape map (string->string_content, int/float->number, "
     "bool->true|false, list[str]->array-of-string) is JSON-grammar knowledge. "
     "Other grammars need their own shape map or per-field NodeKind overrides. "
     "The node-schema bridge (Phase 4) would derive it."),
    ("descendant matching",
     "M() is an exact ancestor chain; there is no 'anywhere under module' "
     "wildcard (module ... assignment). Add a '...' path element if needed."),
    ("JSON string unescaping",
     "string_content is captured raw; embedded quotes/escapes are not "
     "unescaped (concept §5.4 promised unescaping)."),
]


def section5() -> None:
    banner("5. The 'only way' audit — what the model can and cannot express")
    print("  Expressible model-only (verified above):")
    print("   - field captures, record key/value, Optional, defaults, lists,")
    print("     spans, bools, #match?/#eq?/#any-of?, node-kind constraints,")
    print("     kind alternation, anchored ancestor paths, lenient mode.")
    print("  Gaps / escape hatches needed:")
    for i, (name, note) in enumerate(GAPS, 1):
        print(f"   {i}. {name}: {note}")


def main() -> None:
    section1()
    section2()
    section3()
    section4()
    section5()
    banner("DONE — see spike-a2/FINDINGS.md for the verdict")


if __name__ == "__main__":
    main()
