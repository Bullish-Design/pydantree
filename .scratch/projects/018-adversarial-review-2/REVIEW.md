# Pydantree — Adversarial Review (018)

**Date:** 2026-08-05 · **Scope:** concept, architecture, and codebase of
`pydantree_sitter` (A) + `pydantree_sitter_grammar` (B), ~7.3k LOC.
**Method:** full read of both packages' source, the CONCEPT/architecture/user
docs, and the 014 decisions; independent runtime verification of the load-bearing
claims; three adversarial sub-reviews (B-pipeline, B-analysis, tests).

Every finding tagged **[verified]** was reproduced at runtime in this review
(commands in `evidence-notes.md`). Findings are ranked by how much they threaten
the project's own stated goal: *the cleanest, most elegant concept, architecture,
and codebase possible.*

---

## 0. Executive verdict

This is a **strong, unusually self-aware design** executed by someone who
understands tree-sitter deeply. The core insight — "the model IS the query,"
checked at bind time against the CLI's own `node-types.json` byproduct — is
genuinely novel and the two-package light/heavy split is principled. The honesty
statements (C1/C2, the non-goals, the scanner scope line) are more mature than
most shipping libraries.

But the review found a consistent pattern that undercuts the "elegant and
correct" bar: **the prose (docstrings, concept doc, user guide) is aspirational
and has drifted from what the code actually does**, and that drift hides real
defects in exactly the two features each product is *sold on*:

- **Product A's** differentiator is *checked* extraction. Yet the bind-time
  checker secretly uses the name-regex heuristic that D6 explicitly bans, so a
  correct committed `ValueMap` can be overruled by a false `SchemaCheckError`
  **[verified]**. And the friendly documented one-liner (`Model.extract(text,
  language=module)`) silently recompiles and re-checks *every call* — the "checks
  run once" guarantee only holds if you hand-manage a `Language` **[verified]**.
- **Product B's** differentiators are (a) the fast Python static analyzer and
  (b) conflict errors pointed at your source. The analyzer's nullability core is
  wrong for wrapped rules, so it misses the exact `EmptyString`/infinite-loop
  hazards it advertises **[verified]**; and the rule-class surface's headline
  "finer-grained conflict sites (`Pair.value`)" is **inert** — the sites point
  into library internals **[verified]**.

None of these are unfixable, and several are one-line fixes. But together they
mean the project's central claims are currently **truer in the docs than in the
code**. The single most valuable cleanup is to make the code and the prose agree
— then delete the drift-generating machinery (the retired wasm story, the dead
`_RULES_FILE` path, the discarded warnings).

**Recommended framing for the work:** treat every "the code does X (F-A?, D?)"
comment as a test obligation. Where you can't cheaply test it, delete the claim.

---

## 1. Concept & architecture critique (the high-order issues)

### 1.1 The surface is bimodal, and the escape hatch drops the entire value proposition
Both products pitch an elegant declarative surface with a "just drop down when you
need more" escape hatch. In both, the escape hatch is reached *early* for real
work, and crossing it discards the differentiator:

- **A:** `M()` expresses only an anchored ancestor path with gaps/alternation and
  direct-child captures. Sibling order, negation, and multi-anchor joins — i.e.
  most non-trivial extraction ("calls whose first arg is a string literal",
  "imports before the first function") — require `__raw_query__`, a literal
  `.scm`. Raw queries are checked only for *capture-name ↔ field* existence
  (`emit.py:218`), **not** the schema-typed checks that are the whole pitch, and
  they bypass the backtracking ancestor matcher. So A is either trivially simple
  (M path) or raw tree-sitter with a thin coercion layer. The "meaningfully nicer
  than py-tree-sitter" bet (CONCEPT §12) holds only in a narrow middle band.
- **B:** the rule-class surface ("the model IS the rule") cannot express
  recursion, unnamed sequences, or bare alternations without `__body__`, which is
  the raw combinator DSL. Mutual recursion forces `tg.ref("name")` strings, losing
  the class-typed references. So B has **two** authoring surfaces kept in lockstep
  by a "byte-identity gate" test — double the teaching surface and maintenance,
  and the "nicer" one delegates to the "lower" one constantly.

This is the deepest architectural tension. It's not wrong to have escape hatches,
but the docs oversell the coverage of the high-level surface. Recommend: measure
what fraction of realistic tasks stay inside `M()` / annotation-only rule classes,
and either (a) grow the surface to cover the common next tier (sibling anchors are
the obvious one for A) or (b) be explicit in the *concept* that the sweet spot is
narrow.

### 1.2 D6 is violated in the trusted path — the checker uses the banned heuristic **[verified]**
D6/§4.4 is emphatic: "value shapes are **declared data** (`ValueMap`), never
silent name-regex inference in the trusted path; `propose_value_map` is a draft
generator only." Emission honors this. **The bind-time checker does not.**
`compiler._check_type → _kind_coerces → _scalar_of → propose_value_map(schema)`
(`compiler.py:408-413`) runs the name-regex heuristic to decide whether to *reject*
a model. Demonstrated: a grammar whose integer leaf is named `qty` with a correct
committed `ValueMap{qty:int}` — emission maps `qty→int`, but the checker's
`_scalar_of("qty")` returns `"str"` (regex misses `qty`) and raises a false
`SchemaCheckError` "field is int but the value capture can only yield kinds that do
not coerce." The emitter trusts the ValueMap; the checker trusts the heuristic;
they disagree. This is a **conceptual contradiction in the differentiator itself.**
Fix: the checker must consume the same `(schema, ValueMap)` the emitter does.

### 1.3 "Checks run once" is silently false on the documented sugar path **[verified]**
D5 and the READMEs promise `lang.extractor(Model)` runs all checks once, cached by
`(model, strict)` on the `Language`. But the friendly sugar — `Model.extract(text,
language=tree_sitter_rust)`, used verbatim in the README headline and user-guide §4
— routes through `_language_for(module)`, which builds a **fresh `Language` every
call** (`binding.py:74-82`). Measured: 5 identical `Rec.extract(...)` calls →
**10 query compilations + 5 full check passes + 5 `warnings.warn`**; the same work
via a persisted `Extractor` → 2 compilations total. The elegant one-liner is the
pathological path. Either memoize per-module Languages, or make the sugar require a
`Language` and document that bare modules are one-shot.

### 1.4 Conflict remapping — B's reason to exist — is the most version-coupled, least-defended code
CONCEPT §11.1 names this the highest risk, and §12 says it is "the whole reason
Product B deserves to exist." The implementation is fragile exactly there:
- `parse_conflict_json` does `json.loads(proc.stderr)` over the **entire** stderr
  stream and indexes `data["BuildTables"]["Conflict"]` — the serde shape of an
  *internal* Rust error enum pinned to CLI 0.25.3, with no version guard. Any
  stderr contamination (the CLI's own PATTERN-flag warnings go to stderr —
  `checks.py:28`) makes `json.loads` throw → `None` → generic `RuntimeError` with a
  truncated dump. A grammar with both a flag warning and a conflict loses the whole
  typed-error feature.
- `_production_symbols` (`builder.py:687`) re-implements the CLI's
  `production_step_symbols` rendering in Python to match alternatives — "best
  effort" for repeats, and it silently omits `ReservedNode`, renders patterns as
  raw regex, so per-production attribution silently degrades to rule-level for those
  productions.
There is no golden-output corpus across CLI versions. The feature that justifies B
is one serde rename away from collapsing to a stderr dump.

**This is already real, not hypothetical [verified].** The delegated full run
showed: on tree-sitter CLI **0.25.3** the suite is green (232 passed), but on
**0.26.8** it is **7 failed** — 6 of them the conflict-detection tests
(`RuntimeError: no conflict report was found` — the report format changed), plus
the "byte-for-byte node-types.json" schema test (0.26.8 emits an `"extra": true`
field). `devenv.nix` pins `pkgs.tree-sitter` with **no version constraint**, and no
test asserts or skips on CLI version, so a nixpkgs bump silently breaks B's flagship
feature with zero early warning.

### 1.5 The wasm story is fully retired but still dominates the concept docs
CONCEPT §4.7/§5.2/§8/§9 and architecture §3.1 feature `.wasm` as a first-class
distribution/loading path; the shipped seam raises `WasmRuntimeUnavailableError`
unconditionally. The concept doc is the "authoritative record [that] must not
silently drift" (014 addendum) — yet a major advertised capability returns an
error. Trim the concept to match, or move wasm to an explicit "assessed, no-go"
appendix. As written it over-promises portability.

### 1.6 Record mode is structurally JSON/INI-shaped, and its scope is under-stated
Record mode assumes a "pair kind" with both `key` and `value` fields;
`_find_pair_kind` picks `candidates[0]` (alphabetically first) when several exist
(`compiler.py:514-523`) — arbitrary and silent. Combined with the ValueMap
draft/commit ceremony for anything non-JSON, record mode is really "JSON and
JSON-shaped grammars, plus a manual map for the rest." The user guide presents it
as general key/value extraction; the honest scope is narrower.

### 1.7 Performance is absent from the design, and the hot paths show it
For a library whose job is "typed data out of source text" (i.e. many files):
- `NodeSchema.by_type()` rebuilds `{t.type: t for t in node_types}` on **every**
  `get()`/`field_types()`/`has_field()` call (`schema.py:155`), and
  `is_possible_descendant` runs a BFS calling `possible_children` (→ `get`) per
  node — O(N²)+ per `...` gap check at bind. No memoization anywhere on the schema.
- `Cursor._source = root.text or b""` decodes the **entire source** on every
  extract and threads it into every `MatchView`, where `_source` is **never read**
  — pure write-only dead weight **[verified]**.
- `Language.parse` builds a fresh `tree_sitter.Parser` per call; queries rebuild
  per sugar call (§1.3).
Acceptable *once* per persisted Language; pathological under the documented sugar.

### 1.8 Tight circular-import cluster in A forces pervasive lazy imports
`spec ↔ compiler ↔ emit ↔ binding ↔ materialize ↔ valuemap` are mutually entangled
enough that nearly every cross-module call is a function-local `import` (e.g.
`compiler.py` imports `emit` inside ~8 functions; `materialize` imports `emit`/
`markers`/`match` inside loops). It works, but the "one compiler / one matcher /
one materializer" cleanliness the module headers advertise is contradicted by an
import graph that can't be expressed at module top level. Worth a dependency-layering
pass (markers → spec → schema/valuemap → emit → compiler → match/materialize →
binding).

---

## 2. Product A (consumer) — findings

| # | sev | finding |
|---|-----|---------|
| A1 | major **[verified]** | D6 violated in the checker (§1.2): committed `ValueMap` overruled by name-regex → false `SchemaCheckError`. `compiler.py:408-413`. |
| A2 | major **[verified]** | Sugar path recompiles/re-checks every call (§1.3). `binding.py:74-82`, `spec.py:443-460`. |
| A3 | major | Raw-query escape hatch skips all schema-typed checks and the ancestor matcher (§1.1); only capture-name existence is validated. `emit.py:218-225`. |
| A4 | minor **[verified]** | `compiled_source(schema=...)`/`emitted_source` run `_check_path`, so the *diagnostic* helper raises the very `SchemaCheckError` you called it to inspect. `compiler.py:122-140`, `spec.py:421-434`. |
| A5 | minor **[verified]** | Dead full-source decode: `Cursor._source`/`MatchView._source` written every extract, never read. `emit.py:259-293`. |
| A6 | minor | `NodeSchema` has no lookup index (§1.7); O(N)-per-call `by_type`. `schema.py:155`. |
| A7 | minor | `AmbiguousCaptureError` raised with identical message text in two places (`match.merge_group` and `materialize.build_kwargs`) — DRY hazard, messages can drift. `match.py:125`, `materialize.py:195`. |
| A8 | minor | Raw-query anchor fallback picks "first truthy capture" by dict order as the `source_meta` anchor (`materialize.py:242-247`) — nondeterministic semantics for span/line on raw queries. |
| A9 | nit | `_try_resolve_forward_ref` hand-parses `"A | None"` by string `.partition(" | ")` (`spec.py:210-224`) — only single-`| None` unions resolve; `Foo | Bar` forward refs won't. |
| A10 | nit **[verified]** | `codegen` union-ordering `while len(order) < len(union_defs)` has no progress guard: a cyclic/undefined-union dep makes `ready` empty → infinite loop. `codegen.py:169-175`. |
| A11 | nit | Five overlapping language-normalizers (`_resolve_language`, `_load_schema`, `_transient_language`, `_language_for`, `_sugar_extractor`) with double-handling of the Language-wrapping-Language case (`binding.py:104-116` re-does what `_resolve_language` already does). Consolidate. |

The core matcher (`match.py`), the marker/spec derivation, and the error taxonomy
are clean and well-factored; `match_ancestor_path`'s backtracking with the
brute-force property test is a highlight.

---

## 3. Product B (author) — findings

### 3.1 Static analyzer (`checks.py`)
| # | sev | finding |
|---|-----|---------|
| B1 | major **[verified]** | `_nullable` returns `False` for FIELD/ALIAS/PREC*/TOKEN/RESERVED wrappers (no generic `content` fallback), so `check_nullable_non_start_rule` and `check_nullable_in_repeat` miss `field("p", opt(x))`, `repeat(field("a", opt(x)))`, etc. — the exact `EmptyString`/infinite-loop hazards they advertise. `checks.py:191-211`. |
| B2 | major **[verified]** | `_nullable(Repeat1Node)` hard-coded `False`; `repeat1(opt(x))` is nullable. `checks.py:198-199`. |
| B3 | minor | `check_unused_rules` doesn't seed reachability from the `reserved` map → false "unused" error blocks `assert_clean`. `checks.py:288-322`. |
| B4 | minor | Undefined-symbol exemption harvests only SYMBOL-declared externals, not `tok("NAME")`-declared ones — inconsistent with the library's own scanner convention. `checks.py:278`. |
| B5 | minor | `check_precedence_mixing` only fires for two `Prec*` nodes as *direct* CHOICE members; misses nested prec and the cross-rule named/int hazard it documents. `checks.py:377-394`. |
| B6 | minor | `check_alias_on_seq` is `warning=True` while `builder.alias()` raises `ValueError` for the identical defect — same footgun, two severities by provenance. |

### 3.2 Conflict remapping (`conflicts.py`, `builder.py`)
| # | sev | finding |
|---|-----|---------|
| B7 | major | `parse_conflict_json` json-loads the whole stderr and hard-codes the internal serde path, no version guard (§1.4) → CLI drift / stderr contamination collapses the feature. `conflicts.py:64-77`. |
| B8 | minor | `_production_symbols` omits `ReservedNode`, renders PATTERN as raw regex, "best-effort" repeats → silent per-production→rule-level attribution loss. `builder.py:687-719`. |
| B9 | minor | `conflicts._render` assumes resolution `symbols` are strings; non-string entries `TypeError` in the error renderer. `conflicts.py:129`. |

### 3.3 Rule-class surface (`rules.py`)
| # | sev | finding |
|---|-----|---------|
| B10 | major **[verified]** | The advertised "finer-grained conflict sites (names `Pair.value`)" is inert: `_stamp` only writes a site when `site_of(n) is None`, but every combinator node already carries a `rules.py` site from `_track`, so annotation nodes point at library internals, not the author file. `_RULES_FILE` (the intended `file==_RULES_FILE` repoint gate) is **defined and never read**. `rules.py:76,284-295`. |
| B11 | minor | Multi-value `Literal["+","-"]` produces an **anonymous** choice — `attr` never `_wrap`'d — so `op: Literal["+","-"]` loses its `field("op", …)`, breaking the "attribute name is the CST field" promise for that case. `rules.py:259-264`. |
| B12 | minor | `External` with no body compiles to `tok("NAME")` = a token matching the literal text "NAME" (`rules.py:393-397,414-415`) — almost certainly not the intended external-token body; needs checking against a real External grammar. |

### 3.4 Pipeline (`pipeline.py`)
| # | sev | finding |
|---|-----|---------|
| B13 | critical | Cache key omits `grammar_name` (`f"{h}-{tc_digest}"`) but the `.so` filename embeds it. Same model + different `grammar_name` → key hit looks for a `.so` that doesn't exist → rebuild → `os.rename` onto the populated entry (see B14) → `BuildResult.so_path` points at a never-created file. `pipeline.py:291-316,354,373`. |
| B14 | major **[verified]** | Concurrent-build race handler `except FileExistsError` never fires on Linux — `os.rename` onto a non-empty dir raises `OSError(ENOTEMPTY)`, not `FileExistsError` → uncaught crash instead of graceful discard. `pipeline.py:362-365`. |
| B15 | major **[verified]** | Analyzer warnings computed then dropped (`for w in check_warnings(model): pass`); `BuildResult` has no `warnings` field. The "fast Python feedback loop" surfaces errors but silently discards warnings. `pipeline.py:286-288`. |
| B16 | major | `write_bundle` records `"abi": env.get("TSGRAMMAR_ABI","15")` — a different source than `_python_abi()` (which reads `LANGUAGE_VERSION` and feeds the cache key). Bundle metadata can claim ABI 15 for a 14 artifact. `pipeline.py:232`. |
| B17 | minor | `detect_toolchain` uncaught `FileNotFoundError` when `tree-sitter`/`gcc` absent (the `or "unknown"` only covers empty output), firing inside `build()` even on a warm-cache hit. `pipeline.py:71-81,290`. |
| B18 | minor | `_cache_node_schema` may `run_generate` **inside** the promoted (content-addressed, supposed-immutable) cache entry, writing `tree-sitter.json`/`src/` in place. `pipeline.py:241-263`. |
| B19 | minor | `build_builder` docstring says it "re-runs with `--json`"; the code reuses the single run's stderr (and says so). `run_generate` also documents "ONE run." Stale prose. `pipeline.py:426-429`. |
| B20 | minor | `BuildResult.language()` returns `load_grammar_so`'s `(language, lib)` **tuple**, but `language.parse(lang, src)` feeds `lang` straight to `tree_sitter.Parser` — shape mismatch between the keep-alive contract and the parse wrapper. `pipeline.py:174-176`, `language.py:28`. |
| B21 | nit | Duplicated ABI-15 config literal (`pipeline.py:37` vs `ir.py:267`); half-migrated env names (`PYDANTREE_SITTER_CACHE` but still `TSGRAMMAR_ABI`); `debug_states` leaks its `mkdtemp`; `generate()`/`Node = Rule` dead surface. |

### 3.5 schema_tool
| # | sev | finding |
|---|-----|---------|
| B22 | minor | Dead code: `_grammar_name` never called; `grammar_json, _scanner = ...` immediately overwritten; `build_community_bundle(workdir=, keep=)` accepted but never forwarded; `main` writes the schema twice and leaks a temp dir. |

The IR (`ir.py`) is the strongest module in B — a clean Pydantic mirror of
`grammar.json` with a real round-trip property and CLI-sourced schema facts. The
scanner library and its docs are honest and well-scoped. The builder DSL is
tasteful. The `_semantic_smoke` renderer-threading bug (`expr` kind not passed to
`render_compact`, `expressions.py:204`) can produce false smoke results.

---

## 4. Cross-cutting: packaging & documentation drift

| # | sev | finding |
|---|-----|---------|
| P1 | major **[verified]** | Version drift: root `pyproject.toml` is `name="pydantree"`, `version="0.1.2"`; both real dists + both `__init__.__version__` are `0.1.0`; D14 says "both dists start at 0.1.0." |
| P2 | major **[verified]** | Root `pyproject.toml` declares a full `[project]` + `build-system` for a distribution named `pydantree` (with real deps incl. `tree-sitter-python`) while its own comments and the architecture doc say the root "has no distribution of its own." `pip install .` at root would build a `pydantree` wheel. It's simultaneously the "envelope only" and a distribution. |
| P3 | minor **[verified]** | Root `pyproject.toml` comments are stale/self-contradictory: "Phase 2 renames these to pydantree-sitter … until then the workspace members keep the old names" — but the members are *already* renamed; a duplicated line describes `src/pydantree_sitter/pyproject.toml` as both "the shared seam" and "Product A". |
| P4 | minor | `force-include "." = "pydantree_sitter"` ships `pyproject.toml`/`README.md`/`PKG-INFO` *inside* the import package (documented as "harmless" but it's still shipping build metadata into the runtime namespace). |
| P5 | minor | Docs drift: development.md says "there is no `.venv` in the repo root" (there is — used throughout this review); scanner/packaging doc examples show `force-include "." = "pydantree_sitter_grammar"` for the light package too. |
| P6 | good **[verified]** | The seam holds: the light package never *imports* B (only doc/comment mentions). This central claim is real. |

For a project that codifies "the concept doc … must not silently drift from the
shipped design," the *metadata and prose* are the least-maintained surface. A
single "docs-and-metadata truth pass" tied to a test (assert the three
`__version__`/pyproject versions agree; assert the root builds no wheel) would
prevent recurrence.

---

## 5. Test suite (authoritative run — see `test-run.md`)

- **Real results [verified]:** no toolchain → **118 passed / 115 skipped** (~49% of
  the suite skips — essentially all of Product B; a casual `pytest` proves only A);
  CLI **0.25.3** + gcc → **232 passed / 1 skipped** (green); CLI **0.26.8** + gcc →
  **7 FAILED** (§1.4). The one unconditional skip is the sole mypy assertion, so
  "generated code type-checks" is routinely unverified.
- **Rigorous where it runs:** no internal mocking anywhere; real CLI+gcc artifacts
  and real wheel/fresh-venv boundary round-trips; the ancestor-matcher property test
  (2000 randomized cases vs a brute-force reference) is a genuine highlight;
  bundle_format versioning is thorough.
- **But the confidence is conditional and under-hedged:** ~half the suite is
  invisible without the toolchain, and nothing warns you when the pinned-CLI
  assumption breaks (it already has, on 0.26.8).
- The analyzer bugs B1/B2 and the rule-class site bug B10 survived — and they live
  in **toolchain-free** code that *is* exercised every run → missing negative/edge
  tests. `AmbiguousCaptureError` ("the ONE...") has **no positive test**; the "ONE
  compiler" claim is docstring-only; `test_oracles.py:13-21` claims F-A1/2/3 are
  `xfail(strict=True)` but there are **no xfail markers** (stale self-description);
  the packaging boundary subprocess tests inherit `os.environ` (can pass/fail for
  the wrong reason if `PYTHONPATH` leaks `src`).

Recommend adding: (1) a `_nullable` truth table over every wrapper node; (2) a
rule-class "site points at author file, not `rules.py`" assertion; (3) a checker
test that a committed `ValueMap` with an off-name kind binds without a false
`SchemaCheckError`; (4) a sugar-vs-persisted recompilation-count test to pin A2;
(5) a CLI-version guard (assert/skip on the detected `tree-sitter --version`) so B's
conflict/schema claims fail loudly, early, on drift; (6) a positive
`AmbiguousCaptureError` test.

---

## 6. Prioritized remediation

**Tier 1 — wrong behavior / broken selling points (do first):**
1. B1+B2 — fix `_nullable` (generic `content` fallback; `Repeat1` follows content). One-liner each; add the truth-table test.
2. A1 — make the bind checker consume `(schema, ValueMap)`, not `propose_value_map`. Restores D6.
3. B13+B14 — put `grammar_name` (and scanner presence) in the cache key; catch `OSError`/check `entry.exists()` for the promote race.
4. B10 — wire `_stamp`/`_RULES_FILE` so rule-class nodes get author-file sites (or delete the claim from the docs and the dead constant).
5. B7 / CLI drift — **already broken on CLI 0.26.8** (7 red). Add a detected-CLI-version guard that fails loudly + a golden conflict-report corpus; pin `pkgs.tree-sitter` in `devenv.nix`. Update the schema tool for the 0.26.x `"extra"` field or scope the byte-for-byte claim to a CLI range.

**Tier 2 — guarantees that silently don't hold:**
6. A2 — memoize per-module Languages (or require a `Language`); pin with a recompile-count test.
7. B15 — attach warnings to `BuildResult`.
8. B7 — extract the JSON object from stderr rather than json-loading the whole stream (belongs with the Tier-1 CLI-version work).
9. B16 — source bundle `abi` from the same value as the cache key.

**Tier 3 — truth & elegance:**
10. P1–P5 — the docs-and-metadata truth pass (version agreement test; root builds no wheel; retire the wasm story from the concept doc to an appendix).
11. A4/A5/A6/A10/A11, B17–B22 — dead code, diagnostic-raises-the-error, schema indexing, import-layering pass.

**Tier 4 — concept-level, for the "best possible" bar:**
12. Decide the honest scope of the high-level surfaces (§1.1): grow `M()` toward the common next tier (sibling anchors) or state the narrow sweet spot in the concept.
13. Record mode: pick the pair kind deterministically/explicitly rather than `candidates[0]`, and state its JSON/INI-shaped scope honestly (§1.6).

---

## 7. What is genuinely excellent (keep / build on)
- The "model IS the query, checked at bind against the CLI byproduct" thesis (D3/D5).
- The IR round-trip (`GrammarModel.model_dump_json()` *is* `grammar.json`).
- The backtracking ancestor matcher + its brute-force property test.
- The error taxonomy and the per-match `ExtractionError`/`MatchFailure` surface.
- The scanner library's honesty (the "mechanism, not full replication" scope line).
- The install-boundary discipline (A never imports B — verified).
- The non-goals section and the C1/C2 honesty statements — this is the right instinct; the task now is to make the code as honest as the docs already try to be.
