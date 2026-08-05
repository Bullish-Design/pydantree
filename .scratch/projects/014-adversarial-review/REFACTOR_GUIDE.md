# The pydantree-sitter refactor — step-by-step guide

**Date:** 2026-08-05 · **Baseline:** 199 passed, 1 skipped @ `fcf505f` (devenv, warm cache)
**Inputs:** `REVIEW.md` (findings referenced as F-A*/F-B*/T-*/P-*/C*/TS-*), the
conceptual assessment that followed it (Theses 1–8), and the three deep-read
reports. This guide implements **all** of it: the review's fixes where they were
already the right answer, and the stronger deletions where they were not.

**Prime directive:** the best version of this library is *smaller*. Every phase
either deletes a subsystem, collapses two implementations into one, or makes an
implicit mechanism explicit. When a step offers "fix or delete," this guide
always chooses the one that leaves less code.

---

## 0. Decision log (settled — do not re-litigate during implementation)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Name: `pydantree-sitter`.** Two distributions: `pydantree-sitter` (consumer, light) and `pydantree-sitter-grammar` (authoring, heavy). Import packages: `pydantree_sitter` and `pydantree_sitter_grammar`. | P-1/P-2/C4. Prefixed import names are collision-proof; two regular top-level packages beat a PEP-420 namespace split (a regular core package and an injected subpackage from a second dist don't compose safely). |
| D2 | **Two packages, not three.** `pydantree_sitter`'s survivors (schema + loader) fold into `pydantree_sitter`; `pydantree_sitter_grammar` depends on `pydantree_sitter`. | Thesis 7. After D3 the seam is ~500 lines; a third name/dist/release defends nothing. "The light package IS the seam." A still never imports B; B depending on A costs nothing. |
| D3 | **Delete `pydantree_sitter/_ir_derive.py` (the node_types.rs port) entirely.** The schema's only source is the CLI's own `node-types.json`. | Thesis 1. Verified: the pipeline already has the CLI's byproduct on disk (`pipeline.py:258,310`) and re-derives it by hand (`:217`); community wheels ship *neither* `grammar.json` nor `node-types.json` (checked `tree_sitter_python`/`tree_sitter_json` site-packages), and grammar source repos ship both side-by-side — no reachable state has the port's input without its output. Kills T-1..T-6 and the seam inversion (§2.1) *by deletion*; the review's "move the IR into pydantree_sitter" step becomes unnecessary. |
| D4 | **Product A: one matching machine.** Model → pure-data `MatchSpec` → one compiler → one query emitter → one ancestor matcher (backtracking, applied uniformly) → one materializer. Schema presence changes what the compiler checks/infers, never which pipeline runs. Legacy `materialize.py`/`dsl.py` public stacks deleted. | Thesis 2. F-A1/A2/A5/A7/A8/A12 + the new list-branch `match_path` skip (`typed.py:884-927`) are all symptoms of two-and-a-half machines. |
| D5 | **Explicit binding.** `lang.extractor(Model)` runs all checks once; compiled state lives on the `Language` instance keyed by model class. No class-level compiled caches, no global `_SCHEMA_REGISTRY`. `Model.extract(text, language=...)` stays as sugar. | Thesis 3 / review §2.2, pushed to the Pydantic-v2 model/validator split. |
| D6 | **Value shapes are declared data (`ValueMap`), not name-regex inference.** Built-in reviewed map for the JSON family; bundles may ship one; users may supply one. The `shapes.py` heuristic survives only as `propose_value_map()` — a generator of a *draft* the user inspects and commits. | Thesis 4 / C2. |
| D7 | **Job-2 becomes real codegen** — generated runtime wrapper classes (plus `.pyi` fidelity) from the schema. `stubs.py`'s pyi-only fiction is deleted. | Thesis 5 / F-A4. |
| D8 | **B: provenance lives on the node** (private, non-serialized `site` attr stamped at construction). All five site stores and the drain/snapshot dance are deleted. | Thesis 6 / §2.6. |
| D9 | **B: grammars are explicit objects.** `assemble(name, start=..., rules=[...])`; the module sweep survives only as an explicit helper `module_rules(module)` that filters to classes *defined in* that module. Rule classes are the canonical authoring surface; the builder is the compile target. | Thesis 6 / C3 / F-B3. |
| D10 | **`run_checks` is part of `build()`** (default on, `check=False` to skip). Generate always runs with `--json` (one run, not a failure-path re-run). One bundle writer; `schema_tool`'s duplicate path merges into the pipeline with caching. | Thesis 6 / §2.6 deep-read items 7, 9, 11. |
| D11 | **Escape hatch = `__raw_query__`** (a literal `.scm` whose captures are named after model fields). The query DSL is not public; `M()` gains only NodeKind-tuple honoring + path-step alternation. Sibling order, negation, multi-anchor joins: documented as out of scope → raw query. | Thesis 8 / C1 / F-A3/A9. |
| D12 | **Bundle metadata carries `bundle_format` (int).** Absent = format 1; the loader rejects unknown formats legibly. | C5. Do this before first publication — the artifact contract is the one thing that can't change cheaply later. |
| D13 | **Deletions:** legacy island (`src/pydantree`, `src/data`, `src/examples`), root distribution, `_wasm_bridge.py` (→ `.scratch/projects/009-phase7/`, keeping only `WasmRuntimeUnavailableError`), `spike-a/`, `spike-a2/`, `KICKOFF_SPIKE.md` (→ `.scratch/projects/`). | T-7/T-8/P-4/C6 + repo-hygiene findings. |
| D14 | **Version reset:** both new dists start at `0.1.0`. Register/claim both PyPI names immediately (before any other public step). | P-1/P-2/P-3. |

---

## 1. Target end-state

### 1.1 Repository layout

```
src/pydantree_sitter/              dist: pydantree-sitter (LIGHT)
  __init__.py       public surface (see 1.2)
  markers.py        M, capture, capture_kind, source_meta, Matches, Eq, AnyOf,
                    NodeKind, Unescaped  (markers are inert data)
  spec.py           MatchSpec + derivation (model class -> MatchSpec; pure,
                    language-independent, no queries, no compiled state)
  compiler.py       MatchSpec + Language(+schema,+valuemap) -> _Compiled
                    (checks, shape inference, query emission plan)
  emit.py           .scm emission (internal; the surviving core of old dsl.py)
  binding.py        Language, Extractor; per-Language extractor cache
  match.py          the ONE ancestor-path matcher (backtracking) + anchor
                    grouping/merge
  materialize.py    the ONE kwargs builder, Span, JSON unescape, MatchFailure
  valuemap.py       ValueMap model, JSON_VALUE_MAP builtin, propose_value_map()
  schema.py         NodeSchema/NodeTypeInfo/ChildInfo/NodeTypeRef +
                    NodeSchema.from_node_types_json (the ONLY derivation)
  loader.py         load_bundle, load_grammar_so, bundle_format handling,
                    WasmRuntimeUnavailableError (seam only)
  codegen.py        typed-CST codegen: generate_typed_api(schema) -> real classes
  errors.py         the error taxonomy (1.3)
  py.typed
src/pydantree_sitter_grammar/      dist: pydantree-sitter-grammar (HEAVY)
  __init__.py       authoring surface: Rule classes + assemble + build (+ ir ns)
  ir.py             the IR (old grammar.py) with the site private attr
  builder.py        Grammar builder (compile target; still importable, not the
                    headline surface)
  rules.py          Rule/Pattern/Token/External + mixins + assemble/module_rules
  patterns.py       unchanged (regex-string helpers)
  checks.py         unchanged surface; reads a public GrammarView
  conflicts.py      unchanged surface
  expressions.py    unchanged surface (docstrings fixed)
  corpus.py         unchanged surface (hardcodes removed)
  pipeline.py       toolchain, cache, build/build_builder/build_loop,
                    write_bundle (the ONE bundle writer),
                    build_from_source_dir (absorbs schema_tool), scanners glue
  scanners/         unchanged
  py.typed
tests/              per-surface suites, fixtures promoted from .scratch
examples/           bash-extract, devenv-extract, devenv-subset (updated imports)
docs/               rewritten for the new architecture
```

Deleted outright: `src/pydantree_sitter/_ir_derive.py`, `src/pydantree_sitter/_wasm_bridge.py` (moved
to scratch), `src/pydantree_sitter/dsl.py` (public surface; emitter core survives as
`emit.py`), `src/pydantree_sitter/materialize.py`'s legacy public surface,
`src/pydantree_sitter/shapes.py` (folded into `valuemap.py` as the proposal generator),
`src/pydantree_sitter/stubs.py`, `src/pydantree_sitter_grammar/schema_tool.py` (merged into pipeline),
`src/pydantree_sitter_grammar/language.py` (folded into pipeline or loader re-export),
`src/pydantree/`, `src/data/`, `src/examples/`, root `pyproject.toml`'s legacy
distribution, `spike-a/`, `spike-a2/`, `KICKOFF_SPIKE.md`.

### 1.2 Public API (consumer)

```python
from pydantree_sitter import (
    OutputModel, M, capture, capture_kind, source_meta,
    Matches, Eq, AnyOf, NodeKind, Unescaped,
    Language, Extractor, Span,
    NodeSchema, ValueMap, load_bundle,
    ExtractionError, SchemaCheckError, QueryBuildError,
)

lang = Language.load_bundle("bundles/mylang")      # or Language.from_module(tree_sitter_python)
ext  = lang.extractor(Assignment)                   # ALL checks run here, once
rows = ext.extract(text)                            # no hidden state anywhere
rows = Assignment.extract(text, language=lang)      # sugar: lang.extractor(cls).extract(text)
```

### 1.3 Error taxonomy (one deliberate pass — review §2.7)

```
pydantree_sitter.errors:
  PydantreeSitterError(Exception)
    SchemaCheckError        # model↔grammar mismatch at bind time
    ShapeError              # unmappable value shape (class-creation or bind)
    QueryBuildError         # tree-sitter rejected the emitted/raw query
    ExtractionError         # per-match failures (strict mode), carries MatchFailure list
    AmbiguousCaptureError   # scalar field fed by multiple captures
    BundleError             # loader: missing/invalid metadata, unknown bundle_format
pydantree_sitter_grammar.errors:
  GrammarError(Exception)
    GrammarCheckError, GrammarConflictError, GenerateError, CompileError,
    ExternalScannerRequiredError
```

Exactly one `ExtractionError`, one `OutputModel`, one kwargs builder, one
`AmbiguousCaptureError`. `SchemaCheckError` is a sibling of coercion failures,
not a subclass (fixes the `SchemaCheckError < CoercionError < ValueError` smell).

---

## 2. Phase plan — overview and ordering rationale

| Phase | Title | Deletes/creates | Risk |
|-------|-------|-----------------|------|
| 0 | Ratchet: oracles before surgery | creates end-to-end oracles | none |
| 1 | Deletions that touch no product code | −~3,300 lines | low |
| 2 | The rename + two-package fold (mechanical) | new skeletons, old names gone | medium (big diff, no logic change) |
| 3 | Kill the port; version the bundle | −974 lines + T-1..T-6 as a class | low |
| 4 | Product A rewrite (MatchSpec / binding / ValueMap) | the big one | high — gated hardest |
| 5 | Typed CST codegen (real Job-2) | replaces stubs.py | medium |
| 6 | Product B correctness + explicitness pass | site-on-node, assemble, pipeline merge, F-B* | medium |
| 7 | Test-suite hygiene | fixtures promoted, gating fixed | low |
| 8 | Docs truth pass + rewrite | — | low |
| 9 | Packaging floor + publication | claim names, build/inspect wheels | low |

Ordering: oracles first (0) so every later phase has a ground truth that
survives the rewrite; pure deletions next (1) so the rename (2) moves the
minimum; the port dies (3) before the A rewrite (4) because the new compiler
should only ever see `NodeSchema.from_node_types_json`; codegen (5) needs the
new schema plumbing; B (6) is independent of 4–5 but benefits from the rename;
tests/docs/packaging close it out. **Run the full suite in the devenv at every
phase gate; a phase is not done until its gate passes.**

Suggested branch discipline: one branch per phase off `main`, merged in order.
Phases 4 and 6 are internally sub-gated; commit at each sub-gate.

---

## Phase 0 — Ratchet: oracles before surgery

The suite will be heavily rewritten; what must NOT change silently is
*observable extraction and build behavior* on real inputs. Freeze that first.

**Steps**

0.1 Write `tests/test_oracles.py`: for each of the three `examples/`
    (bash-extract, devenv-extract, devenv-subset), run the example's extraction
    end-to-end and assert against **checked-in expected-output JSON**
    (`tests/oracles/*.json`). devenv-subset already has ground truth — reuse it.
    Generate the other two from the current code and eyeball them once before
    committing. These files are the contract across the whole refactor.

0.2 Add oracle cases that pin the *correct* behavior for the review's
    thesis-breaking bugs (they will fail now — mark `xfail(strict=True)` with
    the finding ID, flip to plain tests in Phase 4):
    - F-A1: one model extracted against python then json → second call raises
      (never silent `[]`).
    - F-A2: nested Person/Address record over JSON, `validate_with(lang,
      schema=...)` bound → same rows as schema-less.
    - F-A3: `NodeKind(("true","false"))` in field mode → both rows.
    - NEW (list-branch): a model with a `list[T]` field and a `...` path over
      input where the anchor's ancestry does NOT match → zero rows.
    - T-1: choice-order `required` — keep the repro grammar from
      `AGENT_REPORTS.md` Report 3; after Phase 3 this becomes a test that the
      *CLI byproduct* is what the schema reports (trivially true), so the case
      converts into a pipeline test that `node-schema.json == the generate
      run's node-types.json` byte-for-byte.

0.3 Record the baseline: `pytest -q` output + commit hash into
    `.scratch/projects/014-adversarial-review/REFACTOR_LOG.md` (append-only log
    you update at every phase gate).

**Gate 0:** suite green except the new strict xfails; oracle JSONs committed.

---

## Phase 1 — Deletions that touch no product code (D13)

1.1 `git rm -r src/pydantree src/data src/examples`. Grep for stragglers:
    `grep -rn "from data\|import data\|from pydantree import\|python_nodes" src tests examples docs` → must be empty.

1.2 Root `pyproject.toml`: delete the legacy distribution config (packages,
    `pydantree`/`demo` console scripts, the `data` reference — P-4). What
    remains at the root is the **uv workspace + dev tooling only**. Update
    `test_packaging.py` accordingly (its grep-the-config tests die here;
    real wheel tests arrive in Phase 9).

1.3 `git mv spike-a .scratch/projects/001-phase1-spike-a` (likewise `spike-a2`,
    `KICKOFF_SPIKE.md` → `.scratch/projects/`). Fix the two references in
    `CONCEPT.md`/docs by path only.

1.4 `git mv src/pydantree_sitter/_wasm_bridge.py .scratch/projects/009-phase7/wasm_bridge.py`.
    In `loader.py`: keep `WasmRuntimeUnavailableError` and the `.wasm`
    dispatch, but the wasm branch now *unconditionally* raises it (the env-var
    protocol moves to the scratch probe's README). Delete
    `tests/test_wasm.py`'s env-gated real-load test and the `/tmp/rust-bundle`
    non-hermetic test; keep the unavailable-error test.

1.5 Fix `pydantree_sitter/__init__.py`'s false docstring while passing through (T-9).

**Gate 1:** suite green (minus deleted tests); `grep -rn "pydantree" src/` hits
only comments/dist-name strings you intend to keep until Phase 2.

---

## Phase 2 — The rename + two-package fold (D1, D2) — mechanical, no logic changes

One large commit where behavior is provably unchanged. Do NOT mix in fixes.

2.1 Create skeletons: `src/pydantree_sitter/`, `src/pydantree_sitter_grammar/`,
    each with `pyproject.toml` (name `pydantree-sitter` / `pydantree-sitter-grammar`,
    version `0.1.0`, full metadata — see Phase 9 floor), `py.typed`, LICENSE.

2.2 Moves (`git mv`, preserve history):
    - `src/pydantree_sitter/schema.py` → `src/pydantree_sitter/schema.py`
    - `src/pydantree_sitter/loader.py` → `src/pydantree_sitter/loader.py`
    - `src/pydantree_sitter/*.py`     → `src/pydantree_sitter/` (typed.py, dsl.py,
      materialize.py, shapes.py, schema.py→`model_schema.py` (temporary name to
      avoid clashing with the seam schema; it dies in Phase 4), stubs.py)
    - `src/pydantree_sitter_grammar/*`      → `src/pydantree_sitter_grammar/` with
      `grammar.py` → `ir.py`
    - Delete the now-empty `src/pydantree_sitter`, `src/pydantree_sitter`, `src/pydantree_sitter_grammar`.

2.3 Mechanical import rewrite across `src tests examples docs .agents`:
    `pydantree_sitter.` → `pydantree_sitter.`, `pydantree_sitter` → `pydantree_sitter`,
    `pydantree_sitter_grammar` → `pydantree_sitter_grammar` (plus the `grammar`→`ir` module
    rename). Keep both old `__init__` surfaces temporarily glued together in
    `pydantree_sitter/__init__.py` — the exports shrink in Phase 4.

2.4 Resolve the `Rule` double-export NOW (F-B7, cheap while every import is
    already being touched): `pydantree_sitter_grammar/__init__.py` exports the
    authoring base as `Rule` only; the IR union is reachable as
    `pydantree_sitter_grammar.ir.Rule` and is NOT in `__all__`. Same for the
    two `Grammar`s: the builder's stays `Grammar`; the IR model is
    `ir.GrammarModel` (rename the class; it was already aliased that way in
    prose).

2.5 Dev flow: update the uv workspace members, `uv lock`; fix `devenv.nix`'s
    `.pth` generation — new package dirs AND un-hardcode `python3.13`
    (P-8: derive `lib/python*/site-packages` by glob). Update
    `tests/conftest.py`'s src-first resolution. Update `.agents/skills/*` for
    the new import names.

2.6 Dependency edges: `pydantree-sitter` depends on pydantic + tree-sitter;
    `pydantree-sitter-grammar` depends on `pydantree-sitter` (this replaces
    both old `pydantree-pydantree_sitter` edges). Assert in a test: importing
    `pydantree_sitter` never imports `pydantree_sitter_grammar`
    (the Phase-6-style B-free guarantee, now trivial to state).

**Gate 2:** full suite green with identical pass count to Gate 1; the
subprocess B-free isolation test passes against the new names;
`grep -rn "pydantree_sitter\|pydantree_sitter\|pydantree_sitter_grammar" src tests examples docs` → empty.

---

## Phase 3 — Kill the port; version the bundle (D3, D12)

3.1 `pipeline.build()`: after `run_generate`, copy the CLI's freshly generated
    `src/node-types.json` into the cache entry as `node-schema.json`
    (byte-for-byte, no transformation). Delete `_ensure_node_schema`'s call to
    `derive_from_ir`. The lazy backfill for warm cache entries re-runs generate
    if `node-schema.json` is missing (rare; acceptable — it's the authoritative
    source).

3.2 Delete `src/pydantree_sitter/_ir_derive.py` (the moved file) and the
    `derive_from_ir` lazy re-export in `schema.py`. `NodeSchema` keeps exactly
    one constructor path: `from_node_types_json` / `derive_from_node_types`
    (pick ONE name: `NodeSchema.load(source)`; keep a `from_node_types_json`
    alias only if churn is annoying — prefer not).

3.3 Tests: delete `test_schema.py`'s byte-for-byte `derive_from_ir` oracle
    tests and the T-1/T-2 repro-of-the-port cases. Replace with:
    - a pipeline test (toolchain-gated): `build()` over a fixture grammar →
      the bundle's `node-schema.json` is byte-identical to the generate run's
      `node-types.json` (correct **by construction** — this test documents the
      contract, it can't drift);
    - schema *consumption* tests keep their fixtures: load
      `tests/fixtures/{rust,markdown,...}/node-types.json` directly and keep
      every content/query-helper assertion (fields, supertypes, descent,
      expand — those tests are about `NodeSchema`, not the derivation).

3.4 Bundle format v2 (D12): `write_bundle` emits
    `{"bundle_format": 2, "name", "artifact", "schema", "abi", "toolchain",
    "value_map"?}`. `loader.load_bundle`: absent `bundle_format` → treat as 1
    (same layout today, accept); `> 2` → `BundleError` naming both versions.
    Add loader tests for: missing tree-sitter.json, missing `name`, missing
    artifact, unknown format (the untested error paths from TS report §7).

3.5 Docs touchpoint: `architecture.md` §3/§5 — the "exact path" is retired; the
    schema *is* the CLI byproduct, tracked by construction. Note the one
    capability consciously dropped (schema from a GrammarModel without running
    generate) and why it was hollow (a schema without a parser has no use; B
    always generates).

**Gate 3:** suite green; `grep -rn "_ir_derive\|derive_from_ir" src tests` →
empty; `pydantree_sitter` line count drops by ~1,000; the T-1 oracle case from
Phase 0 now passes as the by-construction pipeline test.

---

## Phase 4 — Product A rewrite (D4, D5, D6, D11) — the big one

Build the new machine **beside** the old modules, cut over model-by-model in
the tests, then delete the old stack. Sub-gates after each step.

### 4.1 `spec.py` — the pure declaration

```python
GAP = object()          # the '...' path element

@dataclass(frozen=True)
class PathStep:
    kinds: tuple[str, ...]          # len>1 = alternation (NEW, D11)

@dataclass(frozen=True)
class FieldBinding:
    name: str
    source: Literal["cst_field", "child_kind", "record_key", "meta"]
    key: str                        # field name / kind / record key / meta capture
    kinds: tuple[str, ...]          # NodeKind override; () = infer
    predicates: tuple[Pred, ...]    # Matches/Eq/AnyOf, inert data
    optional: bool
    is_list: bool
    nested: type | None             # OutputModel subclass (issubclass check, NOT hasattr)
    unescape: bool
    is_meta: bool                   # source_meta

@dataclass(frozen=True)
class MatchSpec:
    path: tuple[PathStep | GAP, ...]
    record: bool
    raw_query: str | None           # __raw_query__ (D11); mutually exclusive with path
    bindings: tuple[FieldBinding, ...]
```

- `derive_spec(model_cls) -> MatchSpec` is a pure function of
  `model_fields` + `__match__`/`__raw_query__`. No queries, no caches beyond a
  per-class memo of the spec itself (safe: language-independent).
- The metaclass shrinks to: call `derive_spec` **per class** (walk the MRO for
  `__match__` but always re-derive with the subclass's own fields — fixes the
  `ns.get("__match__")` inheritance wart, deep-read item 13).
- Marker identity is `isinstance` everywhere; delete every
  `__class__.__name__ == "..."` check (F-A13).
- Bind-time-checkable class-creation checks stay at class creation
  (unresolvable annotations, marker conflicts, `ShapeError` for unmappable
  record shapes); everything needing a grammar moves to bind.
- Port the quantifier-vs-type binding check from legacy
  `materialize.binding_warnings` (the only thing that lived *only* there —
  deep-read item 11) into spec/compile warnings.

**Sub-gate 4.1:** unit tests: spec derivation for every marker combination,
inheritance re-derivation, `__raw_query__` capture-name↔field validation,
record/field mode symmetry (unmarked field = bind-by-name in BOTH modes;
a computed/derived field is now the *marked* case — `derived()` marker —
resolving the mode asymmetry the deep-read flagged).

### 4.2 `binding.py` + `compiler.py` — the explicit bind (D5)

```python
class Language:
    # wraps tree_sitter.Language; carries schema and value_map (both optional)
    @classmethod
    def load_bundle(cls, path) -> "Language": ...     # keeps bundle.lib alive (F-A10)
    @classmethod
    def from_module(cls, mod, schema=None, value_map=None) -> "Language": ...
    def extractor(self, model_cls, *, strict=True) -> "Extractor":
        # cache on SELF keyed by (model_cls, strict) — correct identity by construction
    def parse(self, text) -> Tree: ...
    def reparse(self, tree, new_source, edits) -> Tree: ...   # old_source param deleted (F-A11)

class Extractor:
    model: type; language: Language
    warnings: tuple[BindingWarning, ...]      # DATA, surfaced once via warnings.warn at bind
    query_source: str                          # diagnostics (old compiled_source())
    def extract(self, text) -> list; def extract_tree(self, tree) -> list
```

- `lang.extractor(Model)` runs, in order: schema Jobs 1/3/4 (if `lang.schema`),
  ValueMap resolution (4.4), query emission, `tree_sitter.Query` compile.
  Everything F-A1/F-A5 cached wrongly now lives here with the right lifetime.
  **Delete** `_SCHEMA_REGISTRY`, `_derived_cache`, `_schema_derived`,
  `Query._compiled` — grep-gate: no module-level mutable dict and no
  class-attribute cache anywhere in `pydantree_sitter`.
- `OutputModel.extract(text, language=..., schema=...)` sugar: normalizes
  `language` (module or Language) and delegates. A bare module + `schema=`
  builds a transient `Language`.
- Warnings: `warnings.warn(..., stacklevel=...)` once at bind; never `print()`
  (F-A6). Grep-gate: `grep -n "print(" src/pydantree_sitter` → empty.

**Sub-gate 4.2:** the F-A1 oracle flips to passing (second-language bind
re-checks and raises `QueryBuildError`/`SchemaCheckError`); a threading smoke
test (two threads, two languages, one model class) passes.

### 4.3 `emit.py` + `match.py` — one query, one matcher

- `emit.py` is old `dsl.py` stripped to the emitter core (`NodeSpec`-equivalent
  internals, predicate rendering, quantifiers). Nothing exported from the
  package. The `Cursor/MatchView/NodeView` result-surface survives only as
  much as `Extractor` needs internally.
- Emission rules (all modes):
  - path suffix after the LAST gap compiles into the nested query pattern;
  - **PathStep alternation** and **NodeKind tuples** emit one pattern per kind
    combination (record mode already proved the per-kind-pattern approach —
    generalize it; F-A3 dies);
  - anchor always captured as `@__anchor__`.
- `match.py`: `match_ancestor_path(node, path) -> bool` — a single
  **backtracking** matcher over the prefix-before-last-gap (fixes F-A12),
  property-tested (hypothesis: random paths with repeated kinds vs a brute
  force reference matcher). It is called from EXACTLY ONE place: the match
  loop, before grouping — scalar and list branches share it (fixes the new
  list-branch bug by construction). Anchor-merge/dedup logic from
  `_extract_field`'s list branch moves here, applied after filtering.
- `__raw_query__` path: compile the user's `.scm` verbatim; captures map to
  fields by name; unknown capture → bind-time error listing the model's
  fields. Everything downstream (grouping, materialization) is shared.

**Sub-gate 4.3:** the list+`...` oracle flips; F-A3 oracle flips; property
test green; `dsl.py` deleted; `pydantree_sitter/__init__.py` no longer exports
`Query/NodeSpec/node/cap/Pred/NodeView/MatchView` (F-A9 resolved by removal).

### 4.4 `valuemap.py` — declared shapes (D6)

```python
class ValueMap(BaseModel):
    format_version: int = 1
    scalars: dict[str, Literal["int", "float", "bool", "str", "null"]]
        # node kind -> scalar meaning, e.g. {"number": "float", "true": "bool"}
    wrappers: dict[str, str]     # wrapper kind -> text-leaf kind, {"string": "string_content"}
    arrays: dict[str, list[str]] # array kind -> element kinds

JSON_VALUE_MAP = ValueMap(...)   # replicates today's hardcoded JSON behavior, reviewed

def propose_value_map(schema: NodeSchema) -> ValueMap:
    # THE old shapes.py heuristics (name regexes + structural leaf/wrapper
    # detection), demoted to a draft generator. Docstring says exactly that.
```

- Resolution order at bind: explicit `value_map=` arg → `lang.value_map`
  (from bundle `value_map` entry) → `JSON_VALUE_MAP` iff the schema looks
  JSON-family (exact kind-set check, not name regex) → else a bind-time
  `ShapeError` telling the user to run `propose_value_map` and pass the
  result. **No silent name-regex inference in the trusted path.**
- Record-mode compilation consumes ONLY (schema, ValueMap): pair-kind
  discovery from the schema, key shape from wrappers, value patterns from
  scalars/wrappers/arrays. The schema-less JSON hardcode becomes "schema-less
  record mode = JSON_VALUE_MAP + the documented JSON kinds", stated in docs.
- `shapes.py` and `model_schema.py` (old pydantree_sitter/schema.py) are deleted; the
  Job-1/3/4 check logic moves into `compiler.py`, reading `NodeSchema` +
  `ValueMap` (keep the good check implementations — `is_possible_descent`,
  supertype `expand`, `_check_capture_type` — they were sound; only their
  caching and dispatch were wrong).

**Sub-gate 4.4:** F-A2 oracle flips (nested records recurse through the SAME
compiler with the sub-model bound against the same Language — there is no
schema-less/schema-bound interleaving left to get wrong); `propose_value_map`
round-trip test over the JSON schema reproduces `JSON_VALUE_MAP`;
`grep -rn "string_content" src/pydantree_sitter --include=*.py` hits only
`valuemap.py`.

### 4.5 `materialize.py` — one builder; cutover and deletion

- Keep: `Span`, `_unescape_json_string` (→ `unescape.py` or private in
  materialize), `build_kwargs` (the typed.py version, which was the newer one),
  `MatchFailure`, `AmbiguousCaptureError`, coercion-through-pydantic.
- Nested materialization in **field mode**: either implement it through the
  shared recursion (a nested binding compiles a sub-extractor at bind time) or
  reject it at class creation with a clear `ShapeError` — never the current
  silent raw-`Node`-into-pydantic (deep-read §4 "de facto record-mode-only").
  Decide by need: the examples don't use it → **reject legibly now**, leave a
  documented TODO.
- `Unescaped` symmetric across modes (deep-read item 14): field mode gets the
  same wrapper-shape handling via ValueMap.
- Delete legacy `materialize.py` surface (`OutputModel` #2, `capture` #2,
  `source_meta` #2, `binding_warnings`, `materialize_matches`,
  `extract_records`, `ExtractionError` #2) and the `__init__` alias imports.

**Sub-gate 4.5 (= Gate 4):** ALL Phase-0 oracles pass un-xfailed; old modules
(`typed.py`, `dsl.py`, legacy `materialize.py` parts, `shapes.py`,
`model_schema.py`) deleted; `pydantree_sitter/__init__.py` exports exactly the
1.2 surface; full suite green; examples run unmodified except imports.

---

## Phase 5 — Typed CST codegen (D7)

5.1 Delete `stubs.py` and its mypy-only test.

5.2 `codegen.py`: `generate_typed_api(schema: NodeSchema, module_name: str) -> str`
    emitting a real module:
    ```python
    class TypedNode:                        # thin wrapper, holds tree_sitter.Node
        def __init__(self, node): self.node = node
        # text, span, kind properties
    class FunctionItem(TypedNode):
        KIND = "function_item"
        @property
        def name(self) -> Identifier | None:        # child_by_field_name + wrap()
    ExpressionT = Identifier | CallExpression | ...  # supertypes as unions
    KIND_MAP: dict[str, type[TypedNode]]
    def wrap(node) -> TypedNode: ...
    ```
    Field accessors: required+single → `T`; optional → `T | None`; multiple →
    `list[T]`. Children accessor from the `children` summary. Named after the
    schema's kinds via the acronym-aware snake helper (shared with Phase 6.4).
5.3 Ship it two ways: a function (A-side, from any `NodeSchema`) and a bundle
    hook (`write_bundle(..., typed_api=True)` drops `typed_api.py` beside the
    schema).
5.4 Tests: generate over the rust fixture schema → module `exec`s; runtime
    round-trip (parse real source, `wrap()` the tree, walk fields, compare
    against raw `child_by_field_name`); a mypy run over a small consumer
    snippet (the old test's spirit, now against code that actually runs).

**Gate 5:** the F-A4 oracle class (typed access that type-checks AND runs) is
pinned by tests; `grep -rn "stubs" src` → empty.

---

## Phase 6 — Product B correctness + explicitness (D8, D9, D10, F-B*)

### 6.1 Site-on-node (D8)

- `ir.RuleNode` gains `_site: RuleSite | None = PrivateAttr(default=None)`
  (private attrs coexist with frozen models). Combinators (`_track`) stamp it
  at construction; `site_of(node)` reads it.
- Delete: `builder._SITES`, the drain in `Grammar.rule()`, `Grammar._node_sites`,
  `rules._snapshot_body_sites`/`__body_sites__`, the re-apply loop in
  `assemble`, and the id-reuse "harmless" argument comment. `Grammar.sites`
  (rule-name → site) survives as a convenience view built from node sites +
  class sites.
- `rules.py` keeps `__site__`/`__attr_sites__` (class/attr line numbers are
  genuinely class-level facts) but the attr-site *textual re-parse* is replaced
  where possible by stamping during `_from_annotations` (each generated node
  gets the class's site; attribute-line precision via the existing
  `__attr_sites__` map applied at node creation, not post-hoc repair).
- Frame-depth magic: centralize in ONE helper `caller_site(skip: int)` with a
  unit test that pins each call path's attribution (file/lineno of a known
  fixture), so a refactor that adds a frame fails a test instead of silently
  mis-attributing.
- `conflicts.py`/`matching_alternative` read sites via `site_of` — behavior
  identical, storage gone.

**Sub-gate 6.1:** conflict-remap tests still name the author's line;
`grep -n "_SITES\|_node_sites\|__body_sites__" src` → empty.

### 6.2 Explicit assembly (D9, F-B3)

```python
def assemble(name: str, *, start: type[Rule], rules: Sequence[type[Rule]]) -> Grammar: ...
def module_rules(module) -> list[type[Rule]]:
    # ONLY classes with cls.__module__ == module.__name__ (imported classes
    # excluded — the silent-join bug dies), in definition order.
```
- `rules` order is load-bearing and now visible: rule order, and externals
  order (**document loudly: must match the C scanner's enum order**).
- Function-local rule classes now just work (no module lookup).
- Migration: every current call site becomes
  `assemble("x", start=S, rules=module_rules(sys.modules[__name__]))` — the
  examples should switch to explicit lists to model best practice.
- Canonical-surface decision (C3) lands in docs: rule classes are the product;
  `builder.Grammar` is documented as the compile target / programmatic API,
  demoted from the headline.

### 6.3 Pipeline consolidation (D10)

- `run_generate` always passes `--json`; `build_builder` parses conflicts from
  the single run (delete the second-generate error path,
  `pipeline.py:337-346`).
- `build(model, *, check=True, ...)`: runs `checks.assert_clean` (errors) +
  surfaces warnings before generate. `checks._GrammarView` stops poking
  builder privates: `builder.Grammar` grows a public read-only view
  (`.as_ir_view()` or just public properties) used by checks.
- ONE bundle writer `write_bundle(result_or_paths, out_dir, *, metadata...)`;
  `BuildResult.package` delegates; the duplicated loader-shim string is a
  single constant.
- `schema_tool.py` merges into pipeline as
  `build_from_source_dir(src_dir, *, cache_dir=..., ...) -> BuildResult`
  (community grammars): same cache, same errors, same bundle writer; its
  `node-schema.json` is (as everywhere post-Phase-3) the generate run's
  byproduct. **rmtree only directories this code created** (F-B11): caller
  workdirs are never deleted; internal work happens in `cache_dir/.work` or
  `tempfile.mkdtemp`. Hand-rolled `main()` argv parsing → `argparse` or
  deletion (keep a console script only if the examples use it).
- Cache promote: `os.replace` after building in a sibling temp dir within the
  cache root; if the target exists after a race, discard yours (rename-if-
  absent). Optional `flock` if CI parallel builds arrive (§2.6).
- `detect_toolchain._cache`: keep per-process caching but store it on a
  module-level `functools.lru_cache` with a documented `detect_toolchain.cache_clear()`.

### 6.4 B bug-fix sweep (each with a pinning test written FIRST)

| Fix | Decision |
|-----|----------|
| F-B1 `rule(alias=)` | **Delete the parameter.** The `alias()` combinator and `AliasNode` are the one way. (Implementing rule-level alias semantics duplicates a working mechanism.) |
| F-B2 multi-`Literal` | Implement the natural semantics: `Literal["+", "-"]` → `choice("+", "-")` of anonymous tokens, both nested and top-level; default-value check adapts (default must be one of the values, or no default). |
| F-B4 `_snake` | Acronym-aware: `HTTPServer → http_server`, `JSONValue → json_value` (the standard two-regex approach). Shared with Phase-5 codegen naming. |
| F-B5 whitespace extras | If the author supplies any extra whose pattern matches only whitespace characters, the injected `\s` default is suppressed (intent-based, not exact-string `\s` match). |
| F-B6 `replace_rule` | Honors `hidden` (same `_` renaming as `rule()`), plus a direct contract test (unknown name, site re-recording). |
| F-B8/B9 | Fix `expressions.py` docstrings (`expression(g, ...)` spelling, corpus renders); fix the `_as_op` comment/emission. |
| F-B10 | Delete dead assignments (`corpus.py:246`, old schema_tool lines die with the file). |
| F-B12 | Document `_first_literal_chars`' pattern-handling limits in the check's docstring + warning text ("heuristic; patterns starting with metachars are not analyzed"). |
| F-B13 | Single `as_node` call in `extra()`. |
| Ladder int-mode | Document the insert-after-use renumbering hazard prominently; recommend named mode as default in docs and examples. |
| corpus `render_compact` | Take the expression kind as a parameter (kill the hardcoded `"expr"`, corpus.py:150). |
| Toolchain ABI env | `Toolchain.python_abi` read from the actual `tree_sitter.LANGUAGE_VERSION` when available; env var stays as override only. |

**Gate 6:** all F-B tests green; suite green; `probe_b_side.py` repros all fail
to reproduce (run them — they should now show correct behavior); B line count
lower than at Gate 2 despite the added features.

---

## Phase 7 — Test-suite hygiene (TS-1/TS-2, review §6)

7.1 **Promote fixtures out of `.scratch`**: copy the mini-grammars the suite
    stands on (`pymini`, `hmini`, `dmini`, `pyindent`, `bashmini`, `qfilter`,
    `cfg`, the json/bfree grammars) into `tests/fixtures/grammars/` as proper
    modules. Zero `sys.path.insert` and zero `.scratch` imports in `tests/`
    (grep-gate). `.scratch` keeps its copies as historical evidence.

7.2 **Gating**: one `tests/conftest.py` mechanism — a `toolchain` pytest marker
    + an auto-skip hook when `tree-sitter`/`gcc` are absent. Delete the nine
    copy-pasted `TOOLCHAIN_AVAILABLE` blocks; the two ungated files
    (`test_phase5_apolish.py`, `test_rules.py:376`) are covered by the marker.
    CI (or a local run) proves it: `PATH` without the toolchain → skips, zero
    errors.

7.3 **Isolation**: autouse fixture pointing `TSGRAMMAR_CACHE`
    (rename: `PYDANTREE_SITTER_CACHE`) at a session `tmp_path_factory` dir —
    tests never touch `~/.cache`. The registry leak dies with the registry
    (Phase 4). Kill module-scope model-class definitions where they can fail
    at collection; kill `sys.modules` leaks in `_exec_grammar` (use
    `importlib` + cleanup).

7.4 **Cost**: session-scoped bundle fixtures for rust/nix/markdown community
    builds (build once per session); `@pytest.mark.slow` on generate+gcc
    tests; document `-m "not slow"` as the fast loop.

7.5 **Structure**: dissolve phase-named files (`test_phase3a.py`,
    `test_phase3_surface.py`, `test_phase5_apolish.py`) into per-surface
    suites (`test_rules.py`, `test_expressions.py`, `test_corpus.py`,
    `test_conflicts.py`, `test_extract.py`...). Rewrite the quirk-pinning and
    vacuous assertions flagged in Report 1 §(c)/(d) (the `cond == "("` pin gets
    either a documented rationale or a fix; the version-string assert dies).

7.6 **Provenance**: `PROVENANCE.md` (upstream repo, commit, license, LICENSE
    file vendored) for rust/bash/markdown/markdown-inline fixtures, matching
    what `nix/` already has.

**Gate 7:** suite green in devenv; suite ALL-SKIP-no-error without the
toolchain; cold-cache run touches nothing outside tmp; no `.scratch` import
from `tests/`; runtime with `-m "not slow"` under a minute warm.

---

## Phase 8 — Docs truth pass + rewrite (P-9, review step 10)

8.1 Rewrite `README.md` / `docs/architecture.md` / `docs/user-guide.md` for:
    the two-package layout, the new names, `Language.extractor` binding, the
    ValueMap story, `__raw_query__`, the retired port ("the schema is the
    CLI's own node-types.json, tracked by construction"), typed CST codegen,
    bundle format v2.
8.2 Add the two honesty statements the concept was missing:
    - **A's expressiveness ceiling (C1)**: `M()` = anchored ancestor path
      (with gaps + per-step alternation) + direct-child captures + predicates;
      sibling order/negation/joins are out of scope → `__raw_query__`.
    - **Value shapes (C2)**: shapes are declared data; `propose_value_map` is
      a reviewed-draft generator, never a silent inference.
8.3 Truth sweep: baseline counts, the §3.9 swapped-file description, phase
    table through 014, `expression()` spelling, unused imports in examples,
    "unpublished" notes replaced by real install instructions post-Phase-9,
    `.agents/skills/` regenerated for the new API.
8.4 Update `CONCEPT.md` with a dated addendum recording D1–D14 (the concept
    doc is the authoritative record; it should not silently drift from the
    shipped design).

**Gate 8:** a doc-vs-code sweep (fresh eyes or an agent pass) finds zero
false statements; every code snippet in docs is executed by a doctest-style
test or copied from a tested example.

---

## Phase 9 — Packaging floor + publication (P-3/P-5/P-6/P-7, D14)

9.1 **Claim the names FIRST**: register `pydantree-sitter` and
    `pydantree-sitter-grammar` on PyPI (initial minimal upload or
    organization/project reservation) before any public reference to them.
9.2 Metadata floor in both pyprojects: `authors`, `classifiers`,
    `project.urls`, PEP 639 `license = "MIT"`, `requires-python`, README as
    long description. `py.typed` in both packages (P-5).
9.3 Wheel truth tests (replacing the old grep-the-config tests): build both
    wheels in a test (gated on `uv`/`build`), inspect contents — `py.typed`
    present, no `__pycache__`/`.pyc` (P-7), scanner `.c` files in the grammar
    wheel, LICENSE present; then a fresh-venv install of the LIGHT wheel only:
    `import pydantree_sitter` works, `import pydantree_sitter_grammar` fails
    (the install boundary, now asserted against real artifacts instead of the
    dev `.pth`).
9.4 Version pins in tests read the package version dynamically (no `==0.1.0`
    literals). CI: suite + wheel-truth + a toolchain-less job proving Gate 7's
    skip behavior.
9.5 Publish `0.1.0` of both; flip docs install lines to real commands.

**Gate 9 (= done):** both dists installable from PyPI; the examples run against
the published wheels in a clean venv; `REFACTOR_LOG.md` closes with the final
suite count and the line-count delta vs `fcf505f`.

---

## Appendix A — Traceability: every finding → its step

| Finding(s) | Resolved by |
|---|---|
| F-A1, F-A5 | 4.2 (binding owns compiled state; caches keyed by construction) |
| F-A2 | 4.4 (one compiler, nested = bound sub-extractor; no pipeline interleaving) |
| F-A3 | 4.3 (per-kind pattern emission everywhere) |
| F-A4 | 5 (real codegen) |
| F-A6 | 4.2 (warnings as data, warn once at bind) |
| F-A7, F-A8 | 4.5 + 1.3 (one ExtractionError, one OutputModel, one builder) |
| F-A9 | 4.3 (dsl not exported; emitter internal) + D11 |
| F-A10 | 4.2 (`Language.load_bundle` keeps `bundle.lib`) |
| F-A11 | 4.2 (`reparse` signature cleaned) |
| F-A12 + NEW list-branch skip | 4.3 (one backtracking matcher, one call site, property-tested) |
| F-A13 | 4.1 (isinstance everywhere) |
| F-A14 | dies with `_extract_field` in 4.3/4.5 |
| F-B1..B13 | 6.4 table (+ 6.1 for the site machinery, 6.2 for B3, 2.4 for B7) |
| T-1..T-6 | 3 (port deleted; correctness by construction) |
| T-7 | 1.4 (wasm bridge to scratch; seam error kept) |
| T-8 | 1.1–1.2 (island + root dist deleted) |
| T-9, T-10 | die with the port/file in 3; docstring fixed in 1.5 |
| §2.1 seam inversion | 3 (evaporates — nothing in the light package needs the IR) |
| §2.2 | 4.2 |
| §2.3 | 4.x target layout (markers/spec/compiler/binding/materialize) |
| §2.4 globals | 4.2 (registry, caches), 6.1 (`_SITES`), 6.3 (toolchain cache) |
| §2.5 | 4.2 |
| §2.6 items | 6.1/6.2/6.3/6.4 |
| §2.7 | 1.3 taxonomy, wired through 4/6 |
| TS-1/TS-2 + §6 items | 7 |
| P-1/P-2/C4 | D1/D14, 2, 9.1 |
| P-3 | 9.5 |
| P-4 | 1.2 |
| P-5/P-6/P-7 | 9.2/9.3 |
| P-8 | 2.5 |
| P-9 | 8.3 |
| C1 | D11, 8.2 |
| C2 | D6, 4.4, 8.2 |
| C3 | D9 docs decision in 6.2/8.1 |
| C5 | D12, 3.4 |
| C6 | 1.4 |

## Appendix B — Grep gates (run at final gate; all must be empty)

```
grep -rn "pydantree_sitter\|pydantree_sitter\|pydantree_sitter_grammar"            src tests examples docs
grep -rn "_ir_derive\|derive_from_ir"            src tests
grep -rn "_SITES\|_node_sites\|__body_sites__"   src
grep -rn "_SCHEMA_REGISTRY\|_derived_cache\|_schema_derived" src
grep -rn "print("                                 src/pydantree_sitter
grep -rn "__class__.__name__ =="                  src
grep -rn "sys.path.insert"                        tests
grep -rn "\.scratch"                              tests
grep -rn "id(node)\|id(n)"                        src/pydantree_sitter_grammar/builder.py
```
