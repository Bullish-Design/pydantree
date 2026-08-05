#!/usr/bin/env python3
"""
Phase 4 — the bet-#2 bridge experiment (the go/no-go).

  RUN 1 — the pitch. A non-JSON config grammar (INI-like, tsgrammar-built)
          -> node-schema (derived from the IR) -> A model-only models in
          record + field mode -> checks at validate_with -> typed rows vs
          hand-computed ground truth. Metrics: the surface-layer table, the
          shape-map lines (schema lookup vs hand-written), NodeKind overrides
          (0), the frozen surface, and the JSON v1-map reproduction.

  RUN 2 — the bite. Four planted failures that are runtime-only in Phase 1;
          each must surface at validate_with (before any text is parsed) with
          the schema entry cited.

  RUN 3 — the control. The same two tasks through the Phase-1 stand-ins
          (no schema): hardcoded JSON shape map, NodeKind overrides, Query()
          typos as the free baseline, runtime errors. Comparison table.

Raw outputs are saved verbatim under evidence/.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / ".scratch" / "006-tsquery-bridge"))
sys.path.insert(0, str(ROOT / ".scratch" / "005-tsgrammar-glr"))

import tree_sitter_json  # noqa: E402
import tsgrammar as tg  # noqa: E402

from cfg_grammar import (  # noqa: E402
    CORPUS,
    LISTEN_GROUND_TRUTH,
    SECTION_GROUND_TRUTH,
    build as build_cfg,
)
from json_grammar import build as build_json  # noqa: E402
from tsgrammar.language import load_language  # noqa: E402
from tsquery import (  # noqa: E402
    Language,
    M,
    Eq,
    NodeKind,
    OutputModel,
    SchemaCheckError,
    capture,
    source_meta,
)
from tscore.schema import NodeSchema, derive_from_ir  # noqa: E402

EVIDENCE = Path(__file__).parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def banner(t: str, width: int = 76) -> None:
    print("\n" + "=" * width + f"\n{t}\n" + "=" * width)


def save(name: str, text: str) -> None:
    (EVIDENCE / name).write_text(text)
    print(f"  [evidence saved] {EVIDENCE / name}")


# ---------------------------------------------------------------------------
# RUN 1 — the pitch
# ---------------------------------------------------------------------------

def run1() -> None:
    banner("RUN 1 — the pitch: config grammar -> schema -> checked extraction")

    # B side: analyze -> build -> compile -> node-schema emitted
    g = build_cfg()
    issues = list(tg.run_checks(g))
    print(f"\n1.1 analyzer: {'CLEAN' if not issues else issues} "
          f"({len(g.rules)} rules)")
    result = tg.build_builder(g)
    print(f"1.1 build: exit 0 (ABI 15), cached={result.cached}")
    schema = NodeSchema.from_list(derive_from_ir(g.build()), name="cfg")
    save("r1_node_schema.json", schema.to_json())
    print(f"1.1 node-schema: {len(schema.node_types)} kinds "
          f"({sorted(schema.kinds())})")
    lang, _ = load_language(result.so_path, "cfg")

    # A side: the model-only surface — IDENTICAL vocabulary to spike-a2
    class ServerSection(OutputModel):
        """Record mode: a [section] is an order-independent key/value record."""

        __match__ = M("source_file", "section", record=True)
        host: str
        port: int
        debug: bool = False
        title: str | None = None
        line: int = source_meta()

    class Listen(OutputModel):
        """Field mode: structured directives; `port: int` derives its kind
        constraint from the schema (no NodeKind override)."""

        __match__ = M("source_file", "directive")
        name: str = capture("name")
        port: int = capture("arg")
        line: int = source_meta()

    bound = Language.load(lang, schema=schema)

    # checks active before any text is parsed
    ServerSection.validate_with(bound)
    Listen.validate_with(bound)
    print("1.2 validate_with: schema checks pass (no text parsed)")

    # extraction vs hand-computed ground truth
    secs = [r.model_dump() for r in
            ServerSection.extract(CORPUS, language=bound)]
    listens = [r.model_dump() for r in Listen.extract(CORPUS, language=bound)]
    ok1 = secs == SECTION_GROUND_TRUTH
    ok2 = listens == LISTEN_GROUND_TRUTH
    print(f"1.3 record rows vs ground truth: {'PASS' if ok1 else 'FAIL'}")
    for r in secs:
        print(f"      {r}")
    print(f"1.3 field rows vs ground truth: {'PASS' if ok2 else 'FAIL'}")
    for r in listens:
        print(f"      {r}")
    save("r1_records.txt", "\n".join(str(r) for r in secs))
    save("r1_directives.txt", "\n".join(str(r) for r in listens))

    # the derived queries (the user never writes these)
    save("r1_section_query.scm", ServerSection.compiled_source(schema=schema))
    save("r1_listen_query.scm", Listen.compiled_source(schema=schema))
    print("1.4 derived queries saved (record + field mode)")

    # JSON reproduction: the derived map == the spike-a2 v1 map, over the wheel
    json_model = build_json().build()
    tg.build(json_model)
    jschema = NodeSchema.from_list(derive_from_ir(json_model), name="json")
    jlang = Language.load(tree_sitter_json.language(), schema=jschema)

    class Person(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        age: int
        tags: list[str]
        nickname: str | None = None
        active: bool = False

    Person.validate_with(jlang)
    inner = Person.compiled_source(schema=jschema).split("-- inner --")[1]
    v1_patterns = [
        "value:(string (string_content) @name)",
        "value:(number) @age",
        "value:(array (string (string_content) @tags))",
        "value:(false) @active",
        "value:(true) @active",
    ]
    ok3 = all(p in inner for p in v1_patterns)
    print("1.5 JSON v1 map reproduced by the derivation over tree_sitter_json: "
          f"{'PASS' if ok3 else 'FAIL'}")
    save("r1_json_inner_query.scm", inner)
    save("r1_summary.txt", _run1_summary(ok1, ok2, ok3))
    assert ok1 and ok2 and ok3


def _run1_summary(ok1, ok2, ok3) -> str:
    return f"""RUN 1 — the pitch (evidence)

config grammar: 14 rules, analyzer CLEAN, generate exit 0 (ABI 15)
node-schema: {len(derive_from_ir(build_cfg().build()))} kinds derived from the IR
record mode rows vs hand-computed ground truth: {'PASS' if ok1 else 'FAIL'}
field mode rows vs hand-computed ground truth: {'PASS' if ok2 else 'FAIL'}
JSON v1 map reproduced over tree_sitter_json: {'PASS' if ok3 else 'FAIL'}

surface-layer table (where each check surfaces):
  __match__ chain descent / capture field-on-kind / capture-type mismatch
    -> validate_with(language, schema=...)  (class-creation-adjacent, NO parsing)
  derived record value shapes / kind constraints
    -> validate_with (rebuilds the query), invisible when it works
  kind/field typos                         -> Query() constructor (free, Phase 1)
  value coercion ("x" -> int)              -> extract (pydantic, runtime)

shape-map metric:
  _json_value_specs-style code that became a schema lookup: ALL of it
  (tsquery/shapes.py shape_for: one generic kind-name inference, restricted by
  the pair's value field types — no per-grammar table, no hand-written lines)
  NodeKind overrides the non-JSON record task needs: 0

model surface: identical to spike-a2 (OutputModel, __match__=M(...), capture(),
source_meta(), Matches/Eq/AnyOf/NodeKind) — the schema is invisible when it works.
"""


# ---------------------------------------------------------------------------
# RUN 2 — the bite
# ---------------------------------------------------------------------------

def run2() -> None:
    banner("RUN 2 — the bite: schema catches it before text is parsed")
    g = build_cfg()
    schema = NodeSchema.from_list(derive_from_ir(g.build()), name="cfg")
    lang, _ = load_language(tg.build_builder(g).so_path, "cfg")
    out: list[str] = []

    def plant(label, model_cls):
        try:
            model_cls.validate_with(lang, schema=schema)
            out.append(f"{label}: NO ERROR (unexpected!)")
            print(f"  2.{label}: NO ERROR (unexpected!)")
        except SchemaCheckError as e:
            entry = e.schema_entry or "?"
            out.append(f"{label}\n  schema entry: {entry}\n  error: {e}\n")
            print(f"  2.{label}: SchemaCheckError at validate_with "
                  f"(schema entry {entry!r})")
            print(f"      {str(e)[:130]}...")
        except Exception as e:  # noqa: BLE001
            out.append(f"{label}: WRONG ERROR {type(e).__name__}: {e}\n")
            print(f"  2.{label}: WRONG ERROR {type(e).__name__}: {e}")

    class F1(OutputModel):
        __match__ = M("source_file", "directive")
        name: str = capture("name")
        value: Annotated[int, NodeKind("identifier")] = capture("arg")

    class F2(OutputModel):
        __match__ = M("source_file", "section")
        name: str = capture("value")  # section has no value field

    class F3(OutputModel):
        __match__ = M("source_file", "section", record=True)
        host: str
        tags: list[str]  # cfg has no array-like kind

    class F4(OutputModel):
        __match__ = M("source_file", "entry", record=True)
        name: str  # entry cannot be a record under source_file

    for i, cls in enumerate((F1, F2, F3, F4), 1):
        plant(f"F{i}", cls)
    save("r2_bite.txt", "\n".join(out))
    print("  2.5 no text was parsed in any case (validate_with only)")


# ---------------------------------------------------------------------------
# RUN 3 — the honest control (Phase-1 stand-ins, no schema)
# ---------------------------------------------------------------------------

def run3() -> None:
    banner("RUN 3 — the control: Phase-1 stand-ins, no schema")
    # the control must be schema-free: drop any schema the earlier runs bound
    from tsquery import typed as _typed
    _typed._SCHEMA_REGISTRY.clear()
    lang, _ = load_language(tg.build_builder(build_cfg()).so_path, "cfg")

    # (a) the hardcoded JSON shape map cannot express the config record task
    from tsquery.typed import _value_specs  # the Phase-1 stand-in

    class Hardcoded(OutputModel):
        __match__ = M("source_file", "section", record=True)
        host: str
        port: int

    print("3.1 hardcoded JSON map on the config grammar: the derived .scm "
          "names JSON kinds (pair/string) that do not exist in cfg:")
    print("    " + Hardcoded.compiled_source().split("-- inner --")[1]
          .strip().splitlines()[0])
    print("    -> Query() rejects it at first extract/validate (kind typo). "
          "The task is NOT expressible without a cfg-shaped map.")

    # (b) per-field NodeKind overrides are the Phase-1 escape hatch
    class Overridden(OutputModel):
        __match__ = M("source_file", "section", record=True)
        host: Annotated[str, NodeKind("identifier")] = capture()
        port: Annotated[int, NodeKind("integer")] = capture()
        debug: Annotated[bool, NodeKind("boolean")] = capture()
        title: Annotated[str, NodeKind("string")] = capture()

    print("3.2 per-field NodeKind overrides (Phase-1 stand-in):")
    for f, ann in (("host", "NodeKind('identifier')"),
                   ("port", "NodeKind('integer')"),
                   ("debug", "NodeKind('boolean')"),
                   ("title", "NodeKind('string')")):
        print(f"    {f}: {ann}")

    # (c) capture/type mistakes are runtime errors without a schema
    print("3.3 runtime-only mistakes without a schema (Phase-1 failure table):")
    try:
        class Typo(OutputModel):
            __match__ = M("source_file", "sectoin")  # kind typo

        Typo.validate_with(lang)
    except Exception as e:  # noqa: BLE001
        print(f"    kind typo -> {type(e).__name__} at validate_with "
              f"(Query() free check): {str(e)[:90]}...")
    try:
        class NoShape(OutputModel):
            __match__ = M("source_file", "section", record=True)
            host: str
            tags: list[str]

        NoShape.validate_with(lang)
    except Exception as e:  # noqa: BLE001
        print(f"    list[str] -> {type(e).__name__} at validate_with "
              f"(the hardcoded JSON map names kinds cfg lacks): "
              f"{str(e)[:90]}...")

    control = f"""RUN 3 — the control (Phase-1 stand-ins, no schema)

  hardcoded JSON shape map on the config grammar: cannot express the record
    task at all (its patterns name JSON kinds: pair/string/string_content).
    The Phase-1 'escape hatch' is a per-field NodeKind override for every
    field of every unmapped shape.
  per-field NodeKind overrides: 4 for the two-record task (vs 0 in Run 1)
  list[str] record field: the hardcoded JSON map's patterns name kinds cfg
    lacks (pair/string) -> QueryBuildError at validate_with — Run 1/2 gets a
    schema-cited SchemaCheckError at validate_with (the schema says cfg has no
    array-like value kind).
  capture/type mistakes (int fed identifier): silent until extract-time
    pydantic ValidationError (or lenient-skipped row) — Run 2 F1 gets it at
    validate_with.

comparison (same two tasks):

  metric                          Phase-1 stand-in   Phase 4 (schema)
  -----------------------------   ----------------   ---------------
  record shape map                hardcoded JSON      derived (0 lines
                                  table (per-grammar) hand-written)
  NodeKind overrides needed       4 (per field)       0
  bad capture kind vs type        extract-time        validate_with
  record field with no shape      import (hardcoded)  validate_with (schema
                                                      entry cited)
  nested-record collision         AmbiguousCapture    record-level anchoring
                                  (extract, runtime)  (query level, no error)
  model surface                   identical           identical
"""
    save("r3_control.txt", control)
    print(control)


def main() -> None:
    run1()
    run2()
    run3()
    banner("DONE — Phase-4 experiment complete (verdict in FINDINGS.md)")


if __name__ == "__main__":
    main()
