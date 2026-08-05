# Pydantree — adversarial review of concept, architecture, and codebase

**Date:** 2026-08-05 · **Baseline:** 199 passed, 1 skipped (devenv, warm cache)
**Scope:** `src/pydantree_sitter`, `src/pydantree_sitter`, `src/pydantree_sitter_grammar`, tests, docs, packaging,
legacy `src/pydantree`, examples. Every high-severity claim below was verified
with a live repro (`probe_*.py` in this directory) or a file:line read; nothing
is speculation. Companion files: `CONFIRMED_BUGS.md` (repro details),
`probe_findings.py`, `probe_nested_schema.py`, `probe_b_side.py`.

---

## 0. Verdict

The concept is genuinely strong — the A/B split, the grammar.js bypass, the
node-schema bridge, and the phase-gated evidence discipline are better thought
out than most parser tooling ever gets. The implementation currently
**contradicts its own thesis in four places**: the "checks before parse,
never a silent empty result" promise is broken by a cross-language cache bug
that returns silent `[]`; the flagship schema binding *breaks* nested record
extraction that works without it; the "byte-for-byte with the CLI" derivation
has a demonstrated production-order-dependent divergence (plus hash-order
nondeterminism); and the Job-2 "typed node access" stubs type-check code that
crashes at runtime. Separately, the naming/distribution plan is on fire: the
`pydantree` PyPI name is owned by a third party *at the same version number*,
and the `pydantree_sitter`/`pydantree_sitter` import names collide with live third-party PyPI
packages. The codebase's biggest structural debts are a leftover parallel
legacy surface inside `pydantree_sitter`, a dependency inversion at the seam (`pydantree_sitter`
importing `pydantree_sitter_grammar`), and hidden class-level caches where an explicit
binding object should be.

**Top 10 across the whole review, ranked:**

1. F-A1 — cross-language extraction silently returns `[]` (thesis-breaking).
2. F-A2 — schema binding breaks nested record models (thesis-breaking).
3. P-1/P-2 — `pydantree` PyPI name owned by someone else at v0.1.2;
   `pydantree_sitter`/`pydantree_sitter` import-package collisions with live PyPI packages.
4. T-1 — `_ir_derive` field `required` is production-order dependent,
   diverges from the CLI (reproduced), + hash-order nondeterminism (T-2).
5. F-A4 — Job-2 stubs are typing fiction with no runtime.
6. P-4 — root wheel config references nonexistent `data/`; the shipped
   legacy package can't import; console scripts point into it.
7. F-B1/F-B2 — `alias=` emits garbage; multi-value `Literal` crashes/drops.
8. §2.1 — the seam inversion (pydantree_sitter → pydantree_sitter_grammar).
9. §2.3/F-A7/F-A8 — the parallel legacy surface inside pydantree_sitter (two
   `OutputModel`s, two `ExtractionError`s, dsl.py public-but-"not public").
10. TS-1/TS-2 — test suite: ungated toolchain tests + production tests
    standing on `.scratch/` spike code.

---

## 1. Concept review

### 1.1 What is right (and worth protecting)

- **The A/B split with a data-only seam** mirrors tree-sitter's own
  CLI/runtime split and is proven at the install boundary. This is the
  load-bearing architectural decision and it is correct.
- **The grammar.js bypass** (target `grammar.json` directly) is the insight
  that makes B feasible at all.
- **The node-schema bridge** is a real differentiator: nobody else offers
  model↔grammar validation before parse. The byte-for-byte agreement with the
  CLI's `node-types.json` over four real grammars is a serious verification
  achievement.
- **The honesty lines** (§4.6, §10 non-goals) are unusually good. "We don't
  author scanners in Pydantic" and "conflicts can still require judgement"
  keep the promise surface defensible.
- **The evidence discipline** (.scratch phases, FINDINGS.md, planted
  failures) is a working method, not theater.

### 1.2 Conceptual weaknesses

**C1. Product A has no declared expressiveness ceiling and no blessed escape
hatch.** `M()` is a single anchored ancestor path plus per-field captures.
Real extraction quickly needs: sibling constraints, multiple anchors per
model, alternation at the path level ("function_item OR impl_item"),
negation, matching on the anchor's own field values. None of these are
expressible, and the documented position on the query DSL is contradictory:
`docs/architecture.md:162` says `dsl.py` is "NOT public" while
`pydantree_sitter/__init__.py:19-28` exports `Query`, `NodeSpec`, `node`, `cap`,
`Pred`, `NodeView`, `MatchView`. Decide: either the DSL is the supported
tier-2 escape hatch (document it, test it — it currently has near-zero
tests), or it is private (stop exporting it) and the model surface needs an
explicit statement of what it cannot do. "The model IS the query" is a great
slogan until the first user hits the ceiling with no rope.

**C2. The record-mode "derivation" is name-regex folklore dressed as schema
inference.** `shapes.py:49-53` decides int/float/bool/array-ness of node
kinds by regexing their NAMES (`number|integer|int|real|decimal|count`,
`array|list|sequence|vector|slice`…). A grammar with a structural node kind
named `line_count` or `slice` would be classified numeric/array-like. The
CONCEPT (§5.4, §7.3) presents value-shape derivation as "the schema decides";
in truth the schema decides *which kinds can occur* and a naming convention
decides *what they mean*. That's a defensible v1 heuristic — but it should be
named as such in the concept, be overridable per grammar (not only per field
via `NodeKind`), and carry a confidence/diagnostic story, because it is the
weakest link in the bridge chain and the first thing a non-JSON-shaped
grammar will break.

**C3. Two authoring surfaces per product, no stated canonical one.**
B has the combinator DSL *and* the rule-class surface ("the model IS the
rule"); A has `typed.py` *and* the legacy `materialize.py`/`dsl.py` path
(two `OutputModel` classes, two `ExtractionError` classes — see F-A7/F-A8).
The concept documents say "the model IS the rule/query" as if the class
surfaces were the product, but the codebase maintains both stacks fully.
Pick the canonical surface, demote the other to internals (B: builder as
compile target is fine and clean) or delete it (A: the materialize-side
public surface should go).

**C4. Import-name strategy is a known risk being lived with, not managed.**
The README itself concedes `pydantree_sitter` is taken on PyPI, yet the project
installs generic top-level import packages `pydantree_sitter`/`pydantree_sitter`/`pydantree_sitter_grammar`
from differently-named distributions. That's the classic setup for import
collisions (any other distribution installing a `pydantree_sitter` package) and for
user confusion (pip name ≠ import name). A `pydantree.*` namespace
(`pydantree.core`, `pydantree.query`, `pydantree.grammar`) would cost a
one-time rename now and remove the entire risk class; it gets more expensive
every release.

**C5. The artifact contract has no version field for the schema format.**
CONCEPT §11.4 promises "versioned artifacts"; the bundle metadata carries
`abi` and `toolchain` but nothing versions the node-schema format or the
bundle layout itself. When the format changes, old bundles will fail
mysteriously instead of legibly.

**C6. Wasm residue.** Phase 7's verdict was no-go, which is fine — but the
probe-grade ctypes bridge (`_wasm_bridge.py`, 180 lines) ships inside the
"tiny" pydantree_sitter package, and the loader dispatch + env-var protocol
(`TSGRAMMAR_WASM_LIB`) is production surface for a rejected path. Keep the
`WasmRuntimeUnavailableError` seam; move the bridge itself to `.scratch`
where the probe lives.

---

## 2. Architecture review

### 2.1 The seam inversion (highest-leverage structural fix)

`pydantree_sitter.schema.derive_from_ir` lazily imports `pydantree_sitter._ir_derive`, which
imports `pydantree_sitter_grammar.ir` — the tiny shared seam depends on the heavy
authoring package (`pydantree_sitter/schema.py:298-308`). The original CONCEPT §2 had
it right: *"Shared (pydantree_sitter): Pydantic models mirroring the grammar.json
schema."* The IR models (`pydantree_sitter_grammar/grammar.py`, 259 lines, pure Pydantic,
zero toolchain deps) belong in pydantree_sitter. Then:

- `pydantree_sitter._ir_derive` is honest (derives from its own package's IR),
- B imports the IR from the seam instead of the seam reaching up into B,
- "import existing community grammars into GrammarModels for inspection"
  becomes possible in a light install — a real feature today locked behind
  the heavy package for no reason.

The current lazy-import trick keeps `import pydantree_sitter` B-free at runtime, but
the *dependency direction* is still inverted and every future contributor
will have to re-learn why the "tiny, pure" package has a 974-line module
that crashes without B installed. (Also: `pydantree_sitter/__init__.py`'s docstring
"One module, no more: pydantree_sitter.schema" is false — loader.py is load-bearing
for A's `load_bundle`.)

### 2.2 pydantree_sitter needs an explicit binding object (kills three bug classes)

The A-side bugs (F-A1, F-A2, F-A5 below) share one root cause: state that is
a function of *(model, language, schema)* is cached on objects keyed by less
than that — `Query._compiled` ignores the language (`dsl.py:244-247`),
`_derived_cache` is class-global, `_schema_derived` is keyed by a language
*name* that may be None (`schema.py:344`, `typed.py:646`). The clean design
is the one the domain is asking for:

```python
extractor = Assignment.bind(language)        # checks run HERE, once
rows = extractor.extract(text)               # no hidden cache, no ambiguity
```

A `BoundExtractor` holding (model, Language, schema, compiled queries) makes
every cache identity explicit, gives `validate_with` a natural home, makes
the thread-safety story trivial, and removes the global `_SCHEMA_REGISTRY`
(the registry exists only because bare languages arrive schema-less — a
binding object carries its schema). The classmethod surface
(`Model.extract(text, language=...)`) can stay as sugar that builds a
transient binding.

### 2.3 Module-level layering (A-side)

`typed.py` is 1089 lines mixing eight concerns: markers, JSON unescaping,
derivation, the metaclass, the Language wrapper + registry, materialization,
failure types, and ancestor-walk matching. Meanwhile `materialize.py` keeps
a *parallel, older* implementation of the same materialization (a second
`OutputModel` at `materialize.py:38`, a second `capture`/`source_meta`, a
second `ExtractionError`, a duplicate `_build_kwargs`≈`build_kwargs`) that
the package `__init__` partially imports under throwaway aliases
(`__init__.py:29-37` imports `OutputModel as _MaterializeOutputModel` and
never uses it). This is the spike's skeleton still inside the product.
Target layout, roughly:

```
pydantree_sitter/
  markers.py     M, capture, capture_kind, source_meta, Matches/Eq/AnyOf/NodeKind/Unescaped
  derive.py      model -> _Derived (schema-less + schema paths, one file)
  binding.py     Language, BoundExtractor (the cache owner)
  materialize.py the ONE kwargs builder + failure types
  dsl.py         internal emitter (or documented tier-2)
  shapes.py      kind-name heuristics, clearly labeled
  stubs.py
```

with `materialize.py`'s legacy public functions (`materialize_matches`,
`extract_records`, `binding_warnings`, its `OutputModel`) deleted.

### 2.4 Global mutable state inventory

- `builder._SITES` (`builder.py:81`): process-global id()-keyed table; nodes
  never registered into a rule leak entries forever; id-reuse after GC is
  "harmless" only by argument, not by construction.
- `typed._SCHEMA_REGISTRY` (`typed.py:688`): global, never pruned, and a
  test leaks a `"cfg"` entry into the whole pytest session.
- `detect_toolchain._cache` (`pipeline.py:86`): cached forever; a toolchain
  upgrade mid-process silently keys the build cache with the stale version.
- Class-attribute caches (`_derived_cache`, `_schema_derived`,
  `Query._compiled`, `_quant_maps`): none are thread-safe, all have
  identity-key problems (§2.2).

### 2.5 Warnings/diagnostics channel

`typed._extract_tree` prints `[model-warning]` to stderr with `print()` on
*every* extract call (probe: 3 calls → 3 prints); `materialize._warn`
likewise. Use `warnings.warn(..., stacklevel=...)` once per class, or a
logger. A library that prints to stderr in a loop is not consumable in
production pipelines.

### 2.6 B-side architecture

Mostly clean: IR (frozen Pydantic union) → builder (registry + sites) →
checks → pipeline → conflicts remapping is a good pipeline with real
separation. Issues:

- **`pydantree_sitter_grammar.Rule` means two things.** `__init__.py` imports the IR union
  `Rule` from `.grammar` then shadows it with the rule-class base from
  `.rules` (`__init__.py:102` vs `:137`; `__all__` lists `"Rule"` twice).
  Deliberate, documented, still a trap — rename one (`RuleIR` alias or
  `RuleClass`), never ship one exported name with two meanings.
- **`assemble()`'s module sweep** (`rules.py:361-365`): every `Rule`
  subclass bound in the start-class's module namespace becomes a grammar
  rule — imported classes included, function-local classes impossible
  (misleading "no rule classes found" error — probe confirmed). An explicit
  registry (`assemble(name, rules=[...])` or a per-grammar base class,
  `class MyLang(RuleSet)`) is the composable design; the module-as-grammar
  convention should at least be an explicit opt-in.
- **The id()-keyed source-site machinery** (`_SITES`, `__body_sites__`,
  `_node_sites`) works but is the most fragile subsystem in B: three
  documented workarounds (drain-on-register, snapshot-at-class-creation,
  re-apply-per-assemble) exist solely because sites are keyed by object
  identity of *frozen, shareable* Pydantic nodes. Attaching the site to the
  node itself (a private attr excluded from serialization, or a wrapper) or
  passing sites through the builder call-graph explicitly would delete all
  three workarounds.
- **`pipeline.build` cache promote** (`pipeline.py:305-308`): `rmtree` +
  `rename` is not concurrent-safe (two processes building the same key can
  race between the `exists()` check and `rename`). Fine for a dev tool;
  worth a `flock` or tempdir-rename-if-absent before anyone CI-parallelizes.
- **`schema_tool` deletes caller-supplied workdirs**
  (`schema_tool.py:129,196`): `workdir=` + default `keep=False` ⇒
  `shutil.rmtree(your_directory)`. Delete-what-you-created only.

### 2.7 Error taxonomy

`SchemaCheckError < CoercionError < ValueError` reads oddly (a schema
mismatch is not a coercion error); two `ExtractionError`s and two
`OutputModel`s exist (F-A7/A8); `UnsupportedShapeError` doubles as both a
class-creation error and a derive-time error. Worth one deliberate pass: a
single `TsqueryError` root, `SchemaCheckError` and `ShapeError` as siblings,
one `ExtractionError`, one `OutputModel`.

---

## 3. Verified code findings — Product A (pydantree_sitter)

Ranked. Full repros in `CONFIRMED_BUGS.md`.

| # | Sev | Finding |
|---|-----|---------|
| **F-A1** | **critical** | **Cross-language extraction silently returns `[]`.** `Query.compile` caches the first language's compiled query (`dsl.py:244`); `_derived_cache` is class-level. Model used on lang X then lang Y reuses X's query against Y's tree. Repro: python-then-json → `[]`, no error; fresh model correctly raises `QueryBuildError`. Violates CONCEPT §7.1's core promise. |
| **F-A2** | **critical** | **Schema binding breaks nested record models.** `_record_kwargs` recurses with the nested model's schema-less derivation (no `@__anchor__` capture) while the outer `record_kind` anchor filter is active → every nested match dropped (`typed.py:996-1006`). Repro: Person/Address over JSON works schema-less, raises `ExtractionError` schema-bound. The differentiator feature regresses working behavior. |
| **F-A3** | high | **`NodeKind` tuple alternation silently dropped in field mode** — only `kinds[0]` emitted (`typed.py:426`, `schema.py:469`); rows with the other kinds silently excluded. Docstring and user-guide promise alternation. |
| **F-A4** | high | **Job-2 stubs are typing fiction**: generated accessors (`name()`, `get()`, `children(kind)`) have no runtime implementation on `tree_sitter.Node`; mypy-verified code crashes when executed (`stubs.py`; `tests/test_stubs.py` is mypy-only). Either ship a runtime wrapper class the stubs describe, or reposition the feature as documentation, not "typed node access". |
| F-A5 | med | `schema_derive` cache keyed by `language_name or "?"` — nameless languages collide; a re-loaded schema for the same name is never re-derived (`typed.py:646`, `schema.py:344`). |
| F-A6 | med | Binding warnings printed to stderr with `print()` on every extract (`typed.py:633-634`). |
| F-A7 | med | Two public `ExtractionError` classes (`typed.py:1055` vs `materialize.py:285`); `Query.extract()` raises the one `pydantree_sitter.ExtractionError` doesn't catch. |
| F-A8 | med | Two `OutputModel` classes; `__init__.py` imports the legacy one under an unused alias (`__init__.py:29-37`). Entire legacy materialize/dsl public path is a parallel product surface (§2.3). |
| F-A9 | med | `dsl.py` exported while documented "NOT public" (`architecture.md:162` vs `__init__.py`); DSL essentially untested (test-suite report §a6). |
| F-A10 | low | `Language.load_bundle` drops `bundle.lib`, contradicting pydantree_sitter's stated keep-alive contract (`typed.py:729` vs `loader.py:53`) — benign in CPython, but one of the two is wrong. |
| F-A11 | low | `Language.reparse(old_source=...)` accepted and ignored (`typed.py:757`). |
| F-A12 | low | `_match_ancestor_path` is a greedy non-backtracking matcher — pathological paths with repeated kind names can false-negative (`typed.py:492`). Document or backtrack. |
| F-A13 | low | Stringly-typed marker checks (`m.__class__.__name__ == "Unescaped"` in `typed.py:117`, `shapes.py:241`, `schema.py:186,465`) beside isinstance checks for the same markers — pick one mechanism (isinstance; no cycle prevents it). |
| F-A14 | low | `_extract_field`'s no-anchor bookkeeping appends duplicate `0` sentinels to `order` (`typed.py:894-897`) — currently unreachable (anchor always captured), i.e. dead defensive code that would be wrong if reached. |

## 4. Verified code findings — Product B (pydantree_sitter_grammar)

| # | Sev | Finding |
|---|-----|---------|
| **F-B1** | high | **`g.rule(..., alias="y")` emits garbage**: appends the alias *name* to the grammar-level `inline` list (no such rule exists) and creates no AliasNode (`builder.py:363-364`). Probed: `build().inline == ['pretty']`. Either implement the documented rename semantics or delete the flag. |
| **F-B2** | high | **Multi-value `Literal["+", "-"]`**: top-level raises raw "too many values to unpack" (`rules.py:312`); nested silently drops all but the first (`rules.py:282`). Natural semantics (choice of anonymous tokens) is neither implemented nor rejected legibly. |
| F-B3 | med | `assemble()` module sweep: imported Rule subclasses join the grammar; function-local classes unsupported with a misleading error (`rules.py:356-370`). |
| F-B4 | med | `_snake` mangles acronyms: `HTTPServer → h_t_t_p_server` (`rules.py:83`). |
| F-B5 | med | Explicit non-`\s` whitespace extras don't suppress the injected `\s` default (`builder.py:428-430`, `506-507`) — the author's deliberate whitespace policy is silently overridden. |
| F-B6 | med | `replace_rule` ignores the `hidden` flag (no `_` renaming), unlike `rule()` (`builder.py:376-409`) — a fix-loop replace of a hidden rule changes its name semantics. |
| F-B7 | low | `pydantree_sitter_grammar.Rule` exported with two meanings (§2.6). |
| F-B8 | low | `expression()` docstrings show `g.expression(...)` (method doesn't exist); `DEFAULT_PRECEDENCE_CORPUS` renders differ between docstring and constant (`expressions.py:39,183-189` vs `220-227`). |
| F-B9 | low | `_as_op` wraps a literal in a 1-member SEQ while claiming "seq over a literal -> StrNode" (`expressions.py:243`); harmless emission noise, wrong comment. |
| F-B10 | low | `corpus.Corpus.run`: dead `cache_dir` recompute (`corpus.py:246`); `schema_tool.py:100` dead assignment; `schema_tool.main` hand-rolled argv parsing + leaks its tempdir (`keep=True`) and writes the schema twice. |
| F-B11 | med | `derive_schema_for_dir`/`build_community_bundle` `rmtree` caller-supplied `workdir` (`schema_tool.py:129,196`). |
| F-B12 | low | `checks._first_literal_chars` treats PATTERN sources as literals — first-set overlap check has both false negatives (any pattern starting with a metachar is ignored) and false positives; acceptable for a heuristic warning but undocumented. |
| F-B13 | low | `builder.extra()` calls `as_node(x)` twice (two nodes for str inputs) (`builder.py:425-430`). |

## 5. pydantree_sitter, legacy, and dead weight (delegated deep review — summary)

Full evidence in `AGENT_REPORTS.md` Report 3.

| # | Sev | Finding |
|---|-----|---------|
| **T-1** | **high** | **`_ir_derive` field `required` is production-order dependent and diverges from the CLI** (reproduced live: same grammar modulo choice order → different `required`; CLI emits `false` for both). Root cause `_ir_derive.py:287-294` — required-flip only sees productions processed *after* the field's first appearance; the CLI's cross-pass accumulation doesn't have this hole. The rust/markdown byte-for-byte fixtures happen not to hit this shape — fixture-identity is not algorithm-identity. |
| **T-2** | high | `_relax_hidden_repeat` is leaked instance state read *outside* the fixed point (`:402`, `:900`) while rule iteration order is a hash-randomized set (`:190`) — structured-alias summaries can differ across runs with PYTHONHASHSEED. The derivation is not guaranteed deterministic. |
| T-3 | med | The heuristic itself (`:209-211`) models the CLI's `expand_repeats` *outcome*, calibrated against one grammar; a hidden rule mixing REPEAT1 + unrelated REPEAT relaxes both. Porting `expand_repeats` properly would delete the heuristic and T-2 with it. |
| T-4 | med | Token-rename inconsistency (`:456-509`): `token("x")`-bodied rules fail the rename the CLI performs — unverified against the CLI, no fixture covers it. `_step_aliases` unwraps TOKEN wrappers it shouldn't (`:601`); alias values keyed into a symbol-name dict (`:667`). |
| T-5 | med | Complexity: `_productions` is an unmemoized Cartesian product per rule per fixed-point pass; `_reachable` computed twice; recursion-depth risk on large grammars. Fine for the fixtures, painful for C++-scale grammars. |
| T-6 | med | No pinned upstream source reference (node_types.rs commit hash) anywhere in the 974-line port; drift detection = frozen 0.25.3 fixtures + skip-gated agreement tests. |
| T-7 | med | `_wasm_bridge.py` leaks every resource (`ts_tree_delete` bound, never called; parser/store never deleted; error strings never freed); `close()` order is use-after-free-prone; hand-declared TSNode layout corrupts (not errors) on ABI drift. Probe-grade code in the shipped "tiny" core — move to `.scratch/009-phase7/`, keep only the unavailable-error seam. |
| T-8 | med | **The legacy island is dead and still shipped**: `src/pydantree` (~800 lines, frozen 2025-07-08) is imported by nothing outside itself; `src/data/python_nodes.py` (1147 lines of checked-in generated code) and `src/examples/` (legacy-API only; `file_parse_demo.py` imports a package that exists in no lockfile and a symbol that doesn't exist) hang off it. It still owns the `pydantree` console script and the project's name. Delete or move to `.scratch/`. |
| T-9 | low | Dead code inside `_ir_derive.py`: `_is_lexical_rule` (never called), `_VarInfo.multi_step` (computed, never emitted), `_Deriver.word` (assigned, never read), duplicate `_PREC`/`_PREC_NODES` tuples, `repeat_quantity` ignoring `self`, `_reachable` ×2. Stale docstrings: `pydantree_sitter/__init__` "One module, no more"; `schema.py:54-57` documents a "simplification" the code no longer makes. |
| T-10 | low | Three inconsistent notions of "start rule" in the same file (`:158`, `:574`, `:787`) — silently disagree if `start_rule` is ever not the first dict key. |

## 6. Test suite (delegated deep review — summary)

The suite's core verification strategy is genuinely strong (byte-for-byte
CLI oracles, planted regressions, B-free subprocess isolation). Structural
problems, verified with file:line evidence:

1. **Gating contract broken**: `test_phase5_apolish.py` computes
   `TOOLCHAIN_AVAILABLE` and never applies it; `test_rules.py:376` builds
   ungated — on a toolchain-less machine the suite errors instead of
   skipping, contradicting `docs/development.md:57`.
2. **Production tests import `.scratch/` spike code at module scope** (8+
   files; collection breaks if `.scratch` is pruned; 6 files mutate
   `sys.path` session-wide). Contract tests must not stand on experiment
   scaffolding — promote the needed mini-grammars to `tests/fixtures/`.
3. **Global-state leaks**: a test registers schema `"cfg"` in the global
   registry with no cleanup; the isolating fixture exists in only one file.
4. **Tests write to the developer's real `~/.cache/pydantree_sitter_grammar`** (a dozen+
   call sites without `cache_dir=`); "fast ~40s" is only true warm.
5. **Coverage gaps that map 1:1 to the bugs above**: multi-language
   extraction (F-A1), nested-record + schema (F-A2), multi-value Literal
   (F-B2), the whole query DSL, loader error paths, `binding_warnings`,
   `AmbiguousCaptureError`, `replace_rule`, corpus renderers.
6. **Stale pins**: "170 green + 1 skip" (README/development.md) vs 199
   collected; `test_packaging.py:96` contains a vacuous always-false-or
   assertion; version-exact pins (`==0.1.0`) break on any bump; fixture
   grammars (~1.4 MB vendored rust/bash/markdown) lack provenance/license
   attribution except `nix/`.
7. Phase-named test files (`test_phase3a.py`, `test_phase5_apolish.py`)
   pin development history rather than module contracts — fold them into
   the per-surface suites.

## 7. Packaging & docs (delegated deep review — summary)

Full evidence in `AGENT_REPORTS.md` Report 2.

| # | Sev | Finding |
|---|-----|---------|
| **P-1** | **critical** | **The `pydantree` PyPI name is owned by a third party** (Louis Maddox, "Pydantic parser for tree-sitter", v0.1.2 — the *same version* this repo declares). `pip install pydantree` installs the stranger's package; the root distribution is unpublishable as configured. |
| **P-2** | **critical** | **Import-package collisions are live**: PyPI `pydantree_sitter` 0.1.1 (GPL CLI) installs a top-level `pydantree_sitter/`; `pydantree_sitter` 0.0.1a0 also exists. Installing `pydantree-pydantree_sitter` next to either collides in site-packages with an undefined winner. `pydantree_sitter_grammar` + all three `pydantree-*` dist names are unregistered — squattable. The repo rebranded the *distribution* names but not the *import* names; the collision is unmitigated. |
| P-3 | high | None of the three product distributions exist on PyPI, yet every quickstart (README, user-guide, all three example READMEs) says `uv pip install pydantree-pydantree_sitter pydantree-pydantree_sitter` with no "unpublished" note. |
| **P-4** | high | Root wheel config broken: `packages = [..., "data"]` references a nonexistent root `data/` (real path `src/data`); installed `import pydantree` fails at import; ships top-level `examples`; `demo` script writes a relative repo path. `test_packaging.py:113` only greps the config string, never builds the wheel. |
| P-5 | high | No `py.typed` in any package — all three typed products are untyped to mypy/pyright when installed. |
| P-6 | med | Product pyprojects have no authors/classifiers/urls; `license={file=...}` yields no license metadata (PEP 639). Supply-chain-confusion surface combined with P-2. |
| P-7 | med | `force-include "." = "<pkg>"` maps the whole package dir into the wheel; `__pycache__/` exists in every package dir and no test asserts its absence from wheels. |
| P-8 | med | `_pydantree_src.pth` generation hardcodes `python3.13` (silent no-op on version bump); dev flow never exercises real wheels; `src/`-on-path means generic names `data`/`examples`/`pydantree` shadow installed packages in dev. |
| P-9 | low | Docs drift: dsl.py "NOT public" vs 8 exported symbols; user-guide §3.9 names a nonexistent fixture *and* swaps which file is class-authored vs builder-DSL (test_rules.py docstring repeats the inversion); "170 green + 1 skip" vs 199-200 collected; docs phase table ends at 009 while `.scratch` is at 013; README/user-guide examples import `NodeKind` unused; `spike-a/`, `spike-a2/`, `KICKOFF_SPIKE.md` at repo root against the project's own `.scratch/00X` convention. |
| P-10 | ok | Verified healthy: dependency graph correct (no A→B edge, consistent pins), scanner `.c` files ship and are pinned by test, `.agents/skills/` matches docs, LICENSE files present, no binary artifacts tracked in git. |

## 8. What "best, cleanest, most elegant" looks like from here

Priority-ordered program:

1. **Decide the name, now** (P-1/P-2, C4). This gates everything public.
   The `pydantree` dist name is gone and the generic import names collide
   with live packages — the third-party evidence has settled the C4 debate:
   rename the import packages (a `pydantree_` prefix or a `pydantree.*`
   namespace package) and pick a publishable root name *before* first
   publication makes it permanent. Every release under the current plan
   deepens the hole.
2. **Fix the thesis-breaking bugs** (F-A1, F-A2, T-1, T-2, F-A4). F-A1/A2
   are mechanical once §2.2's `BoundExtractor` exists; do the refactor and
   the fixes together. T-1/T-2 have pinpointed fixes (post-loop
   required-union; make the relax flag a parameter). Add the missing tests
   first (multi-language, nested+schema, choice-order `required`,
   PYTHONHASHSEED repeats) so the fixes land pinned. F-A4: ship a runtime
   accessor wrapper or reframe stubs as documentation.
3. **Delete the parallel A surface**: one `OutputModel`, one
   `ExtractionError`, one kwargs builder; decide dsl.py's public status
   (export-and-test or hide).
4. **Right the seam**: move the grammar IR (`pydantree_sitter_grammar/grammar.py`, pure
   pydantic) into pydantree_sitter; `_ir_derive` becomes self-contained; pydantree_sitter_grammar
   re-exports. Move `_wasm_bridge` to `.scratch/009-phase7/`, keep only the
   `WasmRuntimeUnavailableError` seam. Fix `pydantree_sitter/__init__` docstring.
5. **Kill the legacy island** (T-8, P-4): delete `src/pydantree`,
   `src/data`, `src/examples` (git history keeps them); retire or repoint
   the root distribution and its console scripts.
6. **B-side correctness pass**: implement-or-delete `alias=` (F-B1);
   multi-Literal → choice-of-tokens or a clear error (F-B2);
   `replace_rule` hidden flag (F-B6); whitespace-extra suppression by
   intent (F-B5); acronym-aware `_snake` or require explicit
   `__rule_name__` (F-B4); stop rmtree-ing caller workdirs (F-B11).
7. **Explicit over implicit in rules.py**: registry-based `assemble`
   (or per-grammar base class), site-on-node instead of id()-tables.
8. **Test hygiene** (§6): promote scratch fixtures into `tests/fixtures/`,
   fix the two ungated files, isolate the registry, `cache_dir=tmp_path`
   everywhere, session-scoped bundle fixtures + a `slow` marker, retire
   phase-named files into per-surface suites, un-pin stale baselines,
   provenance files for vendored grammars.
9. **Packaging floor**: `py.typed` in all three products, real metadata
   (authors/urls/classifiers/PEP 639 license), build-and-inspect the root
   wheel in tests (or delete it per step 5), assert no `__pycache__` in
   wheels, un-hardcode `python3.13` in devenv.nix.
10. **Docs truth pass**: dsl.py publicness, pydantree_sitter docstring, user-guide
    §3.9 file swap, expression() spelling, baseline counts, phase table
    through 013, "unpublished" notes on install instructions, stub feature
    framing, and a written statement of Product A's expressiveness ceiling
    (C1) and the kind-name heuristic's status (C2).

The concept deserves the codebase this list produces.
