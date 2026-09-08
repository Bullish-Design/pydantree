# Review 023 — older-review audit findings and resolution

**Date:** 2026-09-08

## Scope and method

The audit revisited the findings and resolution records in projects 014, 018,
019, 020, and 021, then checked the current implementation and regression
tests. The focused older-review suite was:

```text
tests/test_raw_query.py
tests/test_binding_wheel.py
tests/test_pipeline.py
tests/test_conflicts.py
tests/test_checks_nullable.py
tests/test_scanners.py
tests/test_rules_sites.py
tests/test_community_fixtures.py
tests/test_oracles.py
```

The live probe is `probes/probe_older_reviews.py`; its raw and JSON outputs
are in `evidence/older_review_audit.txt` and
`evidence/older_review_audit.json`.

## Older findings checked against current main

Review 014's confirmed Product A defects A1–A3 are closed by the current
language-aware binding/cache boundary, nested-record binding, and complete
alternation handling. Its Product B B1–B4 defects are covered by the current
rule-class, naming, and extra-ownership implementations and their tests.
The old A4 typed-node stub surface is no longer the runtime extraction path;
the current package uses the generated/bound Product A interfaces. The old
hand-derived schema path was removed in the D3 work, so the T1/T2 derivation
failure mode is not present in the current architecture.

Review 018's verified analyzer, checker, rule-site, conflict, cache, warning,
ABI, packaging, and diagnostic findings are represented by current focused
tests and the recorded resolution. The remaining raw-query concerns are an
intentional escape hatch: raw queries do not receive the full anchored schema
check, while capture names and materialization are still validated. That
boundary is documented rather than silently treated as equivalent to a bound
model.

Review 019's V1–V7 verification concerns are covered by the committed oracle
and provenance checks, runnable example checks, managed dependency-sync task,
CLI skip scoping, and precise source-site assertions. The historical
resolution contains one wording contradiction about whether V1 also closed
independent V4/V5 concerns; this audit leaves that historical text unchanged
and relies on the executable tests and later resolution table.

Review 020's A1–A4 and B1–B2 regressions pass. The C++ scanner follow-up is
implemented and covered by scanner tests. The bundle teardown failure is
covered by the in-place rewrite survival test and the current loader keeps the
native library alive. The focused suite also covers the toolchain-free example
and the current cache/promotion contracts.

Review 021's D4–D18 work is present in current main: recursive records are
lazy-bound, foreign trees are rejected, malformed CST policy is explicit,
record and field alternatives are expanded, Product B exports match the
documented surface, caches are bounded/locked, named whitespace extras have a
single owner, Ty is the active type gate, invalid escapes/dead seams/bundle
format/naming/documentation were cleaned up, and the historical evidence is
preserved with dated notes.

## New gaps found and fixed in this audit

### A10 — cyclic generated supertypes failed too late

The existing progress guard prevented an infinite loop in typed-CST code
generation but still emitted unresolved aliases. Importing that generated
module then failed with `NameError`. Generation now raises `ValueError` with
the cyclic/undefined dependency names, so the declaration fails at the
generation boundary and cannot produce a misleading artifact.

### B11 — caller-owned schema-tool workdirs were deleted

`derive_schema_for_dir(workdir=...)` now removes only workdirs it created
itself. An explicit caller-supplied workdir is preserved regardless of the
`keep` default. The probe and regression leave a sentinel file in place.

### D8 — malformed CST diagnostics were too generic

Strict extraction already rejected malformed anchors, and lenient extraction
already skipped them. The diagnostic now names the concrete malformed node,
such as `ERROR` or `MISSING(')')`, and includes the anchor `Span`. The probe
records both strict failures and the empty lenient output. Valid extraction is
unchanged.

### Point-access contract — remaining runtime reads removed

The audit swept the reviewed code, examples, tests, and documentation for
`Point.row`/`Point.column` reads. Runtime line reporting now uses the sequence
API (`start_point[0]`) and extraction spans continue to use
`Span.from_node()`. The point-access regression docstring retains the names
only because it describes the forbidden API it guards.

## Deliberate boundaries

- Schema-less binding is intentional wildcard behavior. It emits a bind-time
  warning and does not claim model-to-grammar or capture-to-type validation.
- Draft field-mode value-shape inference is surfaced with a warning; committed
  `ValueMap` entries remain authoritative. Record-mode non-JSON value shapes
  require a reviewed map.
- Raw queries are an explicitly weaker escape hatch and do not claim the full
  model/anchor checker.
- Field-mode nested records remain a documented bind-time `ShapeError`; the
  record-mode JSON-shaped path supports nested records, including finite
  self-recursion.
- The larger C5 record-mode module split was not undertaken because the
  minimal correctness fixes closed the tested silent narrowing paths.
- This audit does not make a new claim about publication-service names or
  external consumer compatibility beyond the existing package and bundle
  tests.

These are bounded contracts, not silently accepted wrong-answer behavior.
