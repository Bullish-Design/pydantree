# Phase 4 — the bridge (node-schema + Product A compile-time typed extraction): Findings & Verdict

**Date:** 2026-08-02
**Status:** COMPLETE
**Verdict: GO on the bridge** — the node-schema changes the feel of Product A,
honestly and measurably. Bet #2's bridge half ("declaring an `OutputModel` and
getting schema-checked typed extraction is meaningfully nicer than
py-tree-sitter / than the Phase-1 runtime safety nets") is **won**: the
hardcoded JSON value-shape map is gone (replaced by a derivation that
reproduces it exactly and generalizes to a non-JSON grammar), the four planted
runtime failure classes surface at `validate_with` with the schema entry
cited and no text parsed, and the model surface is unchanged — the schema is
invisible when it works. The leaks are real and documented (record value kinds
are name-inferred, field-mode multi-kind constraints stay wildcard, duplicate
same-level keys still error at extract), but none of them is a no-go signal.

Everything here ran against the real toolchain (tree-sitter 0.25.3, gcc
14.2.1, py-tree-sitter 0.26.0, pydantic 2.13.4, ABI 15). Raw outputs saved
verbatim under `evidence/` (r1_*, r2_bite.txt, r3_control.txt). Re-run:

```bash
devenv shell -- python .scratch/006-query-bridge/experiment_phase4.py
devenv shell -- python -m pytest tests/    # 106 green
```

---

## 0. What was built (the surface, in one screen)

```python
# B: the config grammar (INI-like), node-schema emitted with the build
g = cfg_grammar.build()
result = tg.build_builder(g)                    # grammar.so + node-schema.json
schema = NodeSchema.from_list(derive_from_ir(g.build()), name="cfg")

# A: the frozen Phase-1 surface — the schema is bound, never written
class ServerSection(OutputModel):
    __match__ = M("source_file", "section", record=True)
    host: str
    port: int
    debug: bool = False
    title: str | None = None
    line: int = source_meta()

lang = Language.load(result.language(), schema=schema)
ServerSection.validate_with(lang)               # Jobs 1/3/4 run — before parsing
rows = ServerSection.extract(text, language=lang)   # typed rows
```

Supporting: `pydantree_sitter.schema` (the shared node-schema + two derivations),
`pydantree_sitter.shapes.shape_for` (Job 3), `pydantree_sitter.schema.check_model_schema` /
`schema_derive` (Jobs 1+4, record anchoring), the Phase-3A hardening
(`semantic_smoke`, `cond_primary=`).

---

## 1. Run 1 — the pitch: PASS, with the feel metric

The config grammar (14 rules, analyzer CLEAN, generate exit 0, ABI 15)
built end-to-end; the node-schema (24 kinds) was derived from the IR and
bound; both tasks extracted the hand-computed ground truth:

- **record mode** (`[section]` = order-independent record): 2 rows, all 6
  fields incl. `title = "My App"` unquoted via `string_content`, `host =
  example.com` via `identifier` (a non-JSON value shape the hardcoded JSON
  map cannot express), defaulted `debug`, optional `title`, span `line`.
- **field mode** (`listen 8080` / `reload 5` directives): 2 rows, with the
  `port: int` capture **derived** to `(integer)` by the schema — the
  `include "base.conf"` row (string arg) is excluded at query level, exactly
  the spike-a2 §2.2 "int defaults to numeric kinds" answer. **No `NodeKind`
  override needed** (Run-1 goal: 0).
- **JSON reproduction**: the derived map over `tree_sitter_json` is exactly
  the spike-a2 v1 pattern set (`str → string_content`, `int → number`,
  `bool → true|false`, `list[str] → array of string_content`) — the
  derivation is sound, not a special case.

**The feel metric — where each check surfaces:**

| mistake | Phase 1 (spike-a2) | Phase 4 (schema bound) |
|---|---|---|
| kind typo in `__match__` | `QueryBuildError` at validate_with/first extract (free from `Query()`) | same — still free |
| CST field typo in `capture()` | `QueryBuildError` (free) | same + **Job 1** cites the kind's actual fields |
| `__match__` chain not a descent | silent empty result at extract | **Job 1** at `validate_with` |
| capture kind can't feed the type | extract-time `ValidationError` (or lenient skip) | **Job 4** at `validate_with` (schema entry cited) |
| record field with no derivable shape | `UnsupportedShapeError` at import of the hardcoded map | schema-cited `SchemaCheckError` at `validate_with` |
| nested-record key collision | `AmbiguousCaptureError` at extract | **fixed at query level** (record anchoring) |
| value coercion (`"x"` → int) | extract | extract (pydantic — correctly still runtime) |

**Shape-map metric:** spike-a2's `_json_value_specs` was **~40 lines of
JSON-grammar-shaped code**; the replacement `shape_for` is one generic
derivation (a small kind-name inference — numeric/boolean/array/text names —
restricted to the pair node's `value` field types, supertypes expanded).
**0 hand-written lines for the common case**; `NodeKind` remains the typed
override. Record `str` values over the config grammar derive **two** patterns
(`identifier` + `string_content`) — alternation the hardcoded map could only
fake with JSON-isms.

**The model surface stayed identical** (same markers, same entry points) —
the schema is bound through `Language.load` / `validate_with(schema=)`, never
through new annotation vocabulary.

---

## 2. Run 2 — the bite: all four surface at `validate_with`, no text parsed

| # | planted failure | schema entry cited | error class |
|---|---|---|---|
| F1 | `Annotated[int, NodeKind("identifier")]` — the §2.2 question | `NodeKind(('identifier',)) vs int` (lists the grammar's numeric kinds) | `SchemaCheckError` |
| F2 | `capture("value")` on `section` (no such field) | `section.value` (lists section's actual fields) | `SchemaCheckError` |
| F3 | `tags: list[str]` record field (cfg has no array-like kind) | `value-under-entry` | `SchemaCheckError` |
| F4 | `__match__` chain `source_file -> entry` (not a descent) | `source_file -> entry` (lists possible children) | `SchemaCheckError` |

Each error text (saved verbatim in `r2_bite.txt`) names the model, its
definition site (`file:lineno`), the schema entry, and the actual schema
content (numeric kinds, field lists, possible children). No text was parsed
in any case.

---

## 3. Run 3 — the control: the honest comparison

The same two tasks through the Phase-1 stand-ins: the hardcoded JSON shape
map **cannot express the config record task at all** (its patterns name JSON
kinds — `pair`/`string` — which `Query()` rejects), the per-field `NodeKind`
override escape hatch costs **4 annotations** for the two-record task (vs 0),
and the capture/type mistake (F1) is silent until an extract-time pydantic
error. Kind/field typos stay free via `Query()` in both worlds — as specced,
that is NOT the schema's job.

**The decisive comparison:** Run 1's schema checks are **not** a subset of
what `Query()` + runtime errors already catch — the chain-descent check, the
capture↔type check, the shape-map generalization, and the collision fix all
land at `validate_with` (or don't happen at all in Phase 1). The no-go
condition ("Run 1's checks are a subset of free `Query()` + runtime") is
**not** met; the checks are strictly earlier and strictly more informative.

---

## 4. Which §7 jobs landed, and which didn't

- **Job 1 (model↔grammar validation)** — **LANDED.** Beyond the free
  `Query()` typos: the `__match__` chain is checked as a *possible descent*
  (parent→child through the schema's fields/children, supertypes expanded),
  every capture's CST field is checked against its node kind, and the anchor
  is checked producible. At `validate_with(language, schema=)` / first
  schema-bound extract — never at a silent-empty-result runtime.
- **Job 3 (value-shape derivation)** — **LANDED** and is the phase's core
  result. `shape_for` is grammar-derived (see §1); reproduces the JSON v1
  map exactly; generalizes to the config grammar. The §11 risk-7 crux from
  spike-a2 §2.1 — "the value shape map is grammar knowledge" — is now
  *derived* grammar knowledge with a documented name-inference residue (§6).
- **Job 4 (capture↔type cross-validation)** — **LANDED.** The §2.2 question
  is decided by the schema: `int` defaults to numeric kinds (the field-mode
  capture is constrained to `(integer)` — no `NodeKind`), and a capture that
  can only ever yield non-coercible kinds is a `validate_with` error.
  `NodeKind` overrides are themselves validated against the type.
- **Job 2 (typed node access / `.pyi` stubs)** — **assessed, not built**
  (as specced). What it would take: generate accessor types from the schema's
  per-kind children/fields (a `node.get("statement") -> list[Statement]`
  surface), shipped as `.pyi` alongside the schema. Worth it **after** Phase 5
  distribution: it is a feel win for large community grammars, but the
  extraction model is the product; accessor stubs are polish, not leverage.
- **Record-level anchoring** (the spike-a §3 fix) — **LANDED.** The inner
  record query names the record node and captures `@__anchor__`; matches
  anchored at a nested record are dropped, so `{"meta": {"name": "x"}}`
  cannot collide with a record-level `name`. No `AmbiguousCaptureError`, no
  runtime flagging. The honest residual: a **genuine duplicate key at the
  same level** (`{"name": "a", "name": "b"}`) still errors at extract — two
  identical keys cannot be disambiguated, and that is correct.

**What did NOT land (specced out / residual):** field-mode captures whose
derived compatible kinds are plural keep the wildcard (the check runs, the
constraint doesn't — tree-sitter has no inline alternation and field-mode
multi-pattern cartesian products were not built); JSON string unescaping,
descendant `...` matching, and field-mode lists remain noted-not-built (the
schema makes list-derivation and descendant expansion clearly feasible).

---

## 5. Where the schema still leaks (honest)

1. **The kind→type inference is name-based, not semantic.** "`number` → int"
   is a convention. The schema restricts WHICH kinds are candidates (the
   grammar-knowledge half is exact); WHICH Python type a kind coerce to is
   inferred from the kind's name (numeric/boolean/array/text-name patterns).
   A grammar that names a numeric literal `"amount"` needs a `NodeKind`
   override. This is the irreducible residue of §2.1 — documented, small,
   and `NodeKind` remains the typed escape.
2. **`list[bool]` is now derivable** (array of true|false) where the v1 map
   raised `UnsupportedShapeError`. That is the schema being *better* than
   v1, but it means the reproduction check is exact for the v1-supported
   shapes and a strict superset otherwise — say so plainly.
3. **Field-mode plural-kind constraints stay wildcard** (see §4). Runtime
   coercion is the fallback; the check still fires when the intersection is
   empty.
4. **Merged aliases** (multiple rules aliased under one name) union field
   quantities instead of the CLI's required-AND — `required` can be
   overstated. Untouched by the experiment grammars; documented in pydantree_sitter.
5. **Anonymous extras never appear in node-types.json** (a CLI behavior we
   mirrored) — a schema derived for a grammar whose only extras are
   whitespace/comment patterns cannot validate those; fine, because the
   extraction models never reference them.
6. **Schema provenance for community wheels.** The wheels don't ship
   `node-types.json`, so the community path needs a byproduct the user must
   obtain (generate once, or the grammar's source checkout). The mechanism
   (`Language.load(..., schema=node_types.json)`, `derive_from_node_types`)
   is in place and tested; the artifact distribution is Phase 5.

---

## 6. §11 risk 7 — node-schema completeness, re-assessed from the derivation side

Phase 1 left risk 7 as "how faithfully can the schema be derived from
grammar.json / node-types.json". The evidence:

- `derive_from_ir` (the exact path) reproduces the CLI's `node-types.json`
  **with zero diffs** on three grammars: the JSON-like grammar (15 kinds),
  qfilter (39 kinds), and an alias pattern (4 kinds) — fields (names,
  quantities, types), supertype `subtypes`, children, root/extra markers,
  anonymous kinds, hidden/inline transparency. The node_types.rs algorithm
  (per-production quantities seeded at one, fixed-point recursion, hidden
  inheritance, process_supertypes) ports faithfully to the raw IR.
- The two derivations agree on the shared subset for the same grammar
  (tested) — the community path is equivalent where the CLI byproduct is
  available.
- **Completeness verdict:** the schema is complete enough for Jobs 1/3/4 on
  the grammars exercised. The residual incompleteness is (a) the name-based
  type inference (§5.1 — a *semantic* gap, not a structural one: the schema
  knows every kind a value can be; it cannot know what the author *means*
  by an `amount` kind), and (b) artifact availability for community wheels
  (§5.6). Neither blocks the bridge; both are documented.

---

## 7. What the full Product A + B still needs (gaps vs §5/§7)

- **Phase 5 (corpus harness, distribution):** the corpus-testing harness
  (B's §4.8) is the systematic guard for the Phase-3 semantic-intent leak —
  the `semantic_smoke` helper is its seed. Distribution: `pydantree_sitter`/`pydantree_sitter`
  wheels are now real packages; the node-schema artifact must ride with
  grammar artifacts (B-built bundles already ship it in `BuildResult`).
- **Community-schema availability** (§5.6) — a small converter/tool that
  turns any grammar source into `node-types.json` → schema, so community
  grammars get the checks without B.
- **Product A polish:** richer `ExtractionError` (per-match details),
  `Span`-typed `source_meta()` (already there), field-mode lists,
  descendant matching, string unescaping — all noted-not-built; none blocks.
- **Job 2 stubs** — after distribution (see §4).

**None of these is a Phase-5 blocker.** The bridge's checks and derivation
are complete for the frozen surface; the remaining work is reach and polish.

---

## 8. Recommendation

**GO on the bridge.** The evidence: (1) the value-shape map is derived, not
hardcoded — reproduces v1 exactly and expresses a grammar v1 could not, at
0 hand-written lines and 0 `NodeKind` overrides for the common case;
(2) all four planted runtime-only failure classes surface at `validate_with`
with the schema entry + model site cited, no text parsed; (3) the control
shows the Phase-1 stand-ins are strictly later and strictly less
informative, and one of them (the hardcoded map) cannot express the task at
all — the checks are NOT a subset of what `Query()` + runtime errors catch;
(4) the model surface is unchanged — the schema is invisible when it works;
(5) the Phase-3A hardening items landed (the smoke corpus catches a ladder
reorder that silently flips `-a^b`; `cond_primary=` gives the
parens-cond-if pattern a declarative form).

Phase 3's GO did not rubber-stamp this: the no-go conditions were named up
front (checks ⊆ free `Query()`+runtime, or the map not generalizing) and
were tested, not assumed.

**The single most important next step: Phase 5 — polish & reach.** The
bridge is proven; the two biggest reach items are (a) the corpus-testing
harness (now seeded by `semantic_smoke`) and (b) artifact distribution —
making the schema/grammar bundle shippable so community-grammar users get
the checks without running B. A Phase-4A hardening pass is NOT needed: the
leaks in §5 are documented author responsibilities, not design failures.

---

## Appendix — durable facts Phase 4 established

1. **The node-schema derivation is exact.** `derive_from_ir` matches the
   CLI's `node-types.json` on fields/children/subtypes/root/extra for every
   grammar tested (0 diffs); hidden/inline transparency, alias default-kinds,
   REPEAT desugaring (0+ → optional+multiple; 1+ → required+multiple), and
   process_supertypes (subtypes replaced by their supertype in field/child
   lists) are all replicated.
2. **The CLI-version constraint:** CLI 0.25.3 rejects SYMBOL-inside-TOKEN
   outright, so a JSON-style `string` with named `string_content` children
   must be a plain seq rule (not `token()`). This shapes grammar authoring
   (the config grammar's `string` is non-token) and is why the community
   wheel's older grammar (ABI 14) parses the same texts identically.
3. **Record value kinds are the grammar-knowledge half.** `shape_for` reads
   the pair node's `value` field types (supertypes expanded); the Python-type
   half is a name inference. JSON's `value` supertype is what makes
   `str → string_content` and `list[str] → array of string_content` fall out.
4. **The §2.2 answer:** with a schema bound, an `int`-typed capture defaults
   to the grammar's numeric kinds (field mode constrains the pattern; record
   mode restricts the value shapes) — the `TITLE = "My Window"` class is
   excluded at query level instead of erroring at extraction.
5. **Record anchoring kills the nested-collision class.** The inner query is
   `(record_kind (pair ...)) @__anchor__`; matches anchored at nested record
   nodes are dropped by node identity. Genuine same-level duplicate keys
   still error (correct).
6. **The cond affordance needs a self-referential cond rule.** A near-copy
   of the expression rule shares its productions and reduce/reduce-conflicts;
   `_expr_cond` referencing itself (operands are `_expr_cond`, the call
   postfix dropped) is structurally distinct and generates clean — `if x (y)`
   parses unambiguously, call conds are rejected (parens-delimit them).
7. **The smoke corpus pins semantics, not just conflict-freedom.** A ladder
   with the unary above pow generates clean but parses `-a ^ b` as `(-a)^b`;
   the corpus's CST-render assertions catch it at author time (tested).
8. **Schema provenance:** B-built grammars ship `node-schema.json` in the
   cache entry (content-addressed with the build); community grammars use
   `derive_from_node_types` on a `node-types.json` byproduct — equivalent on
   the shared subset (tested).
