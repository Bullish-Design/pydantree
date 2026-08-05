# KICKOFF — pydantree Phase 5 (polish & reach: the corpus harness + the artifact seam in production)

> Copy the whole contents of this file into a fresh session working in this repo.
> Phase 4 (`.scratch/006-query-bridge/`) proved the **bridge** and delivered
> verdict **GO**: the node-schema gives Product A checked extraction (Jobs 1/3/4
> at `validate_with`, schema entry cited, no text parsed), the record
> value-shape map is derived (reproduces the spike-a2 JSON v1 map exactly,
> generalizes to a non-JSON grammar), record-level anchoring kills the
> nested-collision class, and the model surface is unchanged. Phase 4's FINDINGS
> §8 named **Phase 5 — polish & reach** as the next step, with two reach items:
> (a) the **corpus-testing harness** (the systematic guard for the Phase-3
> semantic-intent leak — `semantic_smoke` is its seed) and (b) **artifact
> distribution** (a shippable `grammar.so + node-schema.json` bundle consumed
> by A in a B-free process — the artifact seam "in production", not just
> in-process). Reference docs live in `.scratch/`; findings go in
> `.scratch/007-query-distribution/FINDINGS.md`.

---

## Mission

You are working in the **`pydantree`** repo. **Phases 0–4 are done and
passed.** Phase 4 proved the bridge (bet #2's compile-time half) and said:
"the bridge is proven; the two biggest reach items are the corpus harness and
artifact distribution — making the schema/grammar bundle shippable so
community-grammar users get the checks without running B." This session
delivers **Phase 5 — polish & reach**: a fresh go/no-go on *reach*. Two
questions decide it:

1. **Corpus testing (B):** does the `(input, expected-sexp)` corpus harness —
   the Phase-3 §4.8 promise — actually catch the semantic-intent regressions
   that conflict-freedom cannot (a ladder reorder, an associativity flip, a
   postfix-below-unary mistake all generate *clean* but parse *wrongly*)?
   `semantic_smoke` (Phase-3A) is a 5-case seed; the harness generalizes it
   into a first-class authoring surface with reviewable diffs.
2. **Distribution (the artifact seam in production):** can a grammar built by
   B be packaged into a shippable bundle (`grammar.so` + `node-schema.json` +
   metadata + a tiny loader) and consumed by A in a **separate process where B
   is not importable**, with the schema checks still active? A never imports B
   — Phase 4 proved that in-process; Phase 5 proves it across the process
   boundary, the way a real consumer would use it.

Deliver a **go / go-with-changes / no-go verdict with evidence**. If the
corpus harness adds nothing beyond conflict-free generate + the smoke seed, or
if the bundle cannot be consumed B-free without dragging B's toolchain along,
say so plainly — a no-go on either is an architecture-changing result.

## Context: where we are

- **Phase 0 (done):** emission + conflict remapping proven.
- **Phase 1 (done):** `spike-a/`, `spike-a2/` — Product A's **model-only**
  surface (`OutputModel` IS the query), materializer, failure surface. Phase 4
  **ported** this surface into `src/pydantree_sitter/` unchanged.
- **Phase 2 (done):** `src/pydantree_sitter_grammar/` — full-schema IR, builder DSL, analyzer,
  native build pipeline, conflict remapping.
- **Phase 3 (done):** `.scratch/005-grammar-glr/` — the GLR-ergonomics layer
  (ladders, `ExpressionGrammar`), verdict **GO on bet #1**. Its §6 named the
  corpus harness as "the *most* valuable Phase-5 item".
- **Phase 4 (done, THIS phase's foundation):** `.scratch/006-query-bridge/` —
  the bridge, verdict **GO**. This session's raw material:
  - `src/pydantree_sitter/schema.py` — the shared node-schema + `derive_from_ir`
    (exact path, 0 diffs vs the CLI's node-types.json on every grammar tested)
    + `derive_from_node_types` (community path).
  - `src/pydantree_sitter_grammar/pipeline.py` — `BuildResult` now carries
    `node_schema_json` (emitted in the cache entry) + `BuildResult.node_schema()`.
  - `src/pydantree_sitter/` — `OutputModel` surface + `Language.load(lang, schema=)`
    + the schema registry + `check_model_schema` / `schema_derive` +
    `pydantree_sitter.shapes.shape_for`.
  - `src/pydantree_sitter_grammar/expressions.py` — `semantic_smoke` +
    `DEFAULT_PRECEDENCE_CORPUS` + `cond_primary=` (Phase-3A).
  - `json_grammar.py` + `cfg_grammar.py` + `experiment_phase4.py` in
    `.scratch/006-query-bridge/` (reusable fixtures/corpus).
- **`src/pydantree/`** — deprecated first-principles wrapper. **Do not touch.**

## Required reading (in this order — do not skip)

1. **`.scratch/006-query-bridge/FINDINGS.md`** — Phase 4's verdict and the
   honest leaks. Especially §7 (what full A+B still needs: the corpus harness,
   artifact distribution, community-schema availability, A polish items — richer
   `ExtractionError`, field-mode lists, descendant matching, string unescaping),
   §5 (the leak list — name-based kind inference, plural field-mode constraints,
   same-level dup keys), §8 (recommendation: Phase 5, no Phase-4A needed).
2. **`.scratch/002-pydantic-treesitter/CONCEPT.md`** — §4.8 (the corpus-testing
   spec: `(input, expected sexp)` cases, diff the CST, snapshot grammar.json +
   node-schema as reviewable diffs), §4.6/§4.7 (external scanners, the build
   pipeline + wasm note), §5.6 (error surface, incremental reparse "available,
   we do not wrap it" — Phase 5 wraps it), §7 (the bridge + community-grammar
   path), §8 (pydantree_sitter owns the artifact-loading contract — a Phase-5 fact).
3. **`spike-a/FINDINGS.md`** — §4 (the materializer gaps: richer
   `ExtractionError`, `Diagnostic` objects, `Span`-typed `source_meta`,
   `#has-ancestor?` predicates as the descendant-matching mechanism) and §1
   (the 0.26 substrate that still governs everything).
4. **`spike-a2/FINDINGS.md`** — §4 (the expressibility gaps Phase 5 may close
   with the schema: field-mode lists, descendant matching, string unescaping)
   and §2.1 (the value-shape map — now derived, not hardcoded).
5. **`.scratch/005-grammar-glr/FINDINGS.md`** — §6 (the corpus harness is the
   systematic guard for the §4 semantic-intent leak; `semantic_smoke` was the
   Phase-3A seed of it) and §4 (what the leak classes look like).
6. **Phase-4 code you will extend (skim):**
   - `src/pydantree_sitter_grammar/expressions.py` — `semantic_smoke` (the seed; the harness
     should subsume or call it), `DEFAULT_PRECEDENCE_CORPUS`.
   - `src/pydantree_sitter_grammar/pipeline.py` — `BuildResult` (add packaging), the cache,
     `build_loop`.
   - `src/pydantree_sitter/typed.py` — `Language` (add reparse), `_resolve_language`,
     `_ExtractionError` (richen it), `_record_kwargs` (the anchor-merge
     machinery field-mode lists will reuse).
   - `src/pydantree_sitter/dsl.py` — `Query.validate` (currently returns dicts; make
     typed `Diagnostic`s), the emitter (for `...`/descendant + list captures).
   - `src/pydantree_sitter/schema.py` — the derivations (the community tool consumes
     `derive_from_node_types`).

## Phase 5 in 60 seconds

```
   corpus testing (B)                      distribution (B -> pydantree_sitter -> A)
   (input, expected-sexp) cases     BuildResult.package() -> bundle
          |                                   | grammar.so + node-schema.json
          v                                   |   + metadata + tiny loader
   run against fresh build                    v
   diff CST, snapshot grammar    A in a SEPARATE process (no B importable):
   + node-schema as reviewable   Language.load(bundle) -> checks -> typed rows
          |                              + community path: node-types.json
          v                                     -> schema -> checks
   catches ladder reorders /           + reparse + Diagnostics + A polish
   associativity flips / postfix
   mistakes that generate CLEAN
```

The whole point is Phase 4's two reach items landing as first-class surfaces:
a B author can prove their grammar's semantics (not just its conflict-freedom)
with a corpus, and an A consumer who never touches B can load a shipped
grammar with its checks intact. If either half leaks (the harness can't catch
a planted regression, or the bundle needs B at consume time), that is the
go/no-go signal — say so plainly.

## Phase 5 scope

### Primary experiment (the go/no-go): the reach pair

**Run 1 — the corpus harness bite (B).** Take a Phase-3 grammar (qfilter or a
small new one) and author a real corpus: `(source, expected-sexp)` cases in
Python (the `semantic_smoke` corpus is a seed; extend it to statement shapes
and edge cases). Build the harness: run the corpus against the freshly built
grammar, diff the CST (a sexp renderer with a normalization story — decide
anonymous-node handling and document it), and snapshot `grammar.json` +
node-schema so grammar changes produce reviewable diffs. Then **plant three
semantic regressions that generate clean** — a ladder reorder (unary above
pow), an associativity flip (right-`+`), a postfix-below-unary mistake — and
show the harness catches each at author time, citing the case. Metrics: which
of the three the *smoke seed* already catches vs which need the full corpus;
the author effort to write a corpus for a 20-rule grammar; the diff
reviewability. **The go/no-go: does the corpus harness change the feel of B
authoring (catch what generate cannot), or is it ceremony on top of
conflict-free?**

**Run 2 — the artifact seam in production (B → pydantree_sitter → A).** Build a grammar
with B (the Phase-4 cfg grammar is ideal), `BuildResult.package()` it into a
bundle directory (`.so` + `node-schema.json` + metadata + a tiny loader
module), then consume it from a **subprocess that has B removed from
`sys.path`** (and does not import `pydantree_sitter_grammar` at all): `pydantree_sitter` loads the
bundle, binds the schema, runs the Phase-4 record + field tasks against the
hand-computed ground truth with the checks active. Also demo the **community
path**: generate `node-types.json` for the json grammar IR, derive the schema
via `derive_from_node_types`, bind it to the `tree_sitter_json` wheel, and
extract the Phase-4 Person ground truth — checks active, no B in the process.
Metrics: the bundle's file list and size; the loader's line count; that A's
surface is byte-identical with and without B in the process. **The go/no-go:
does the bundle let a consumer who never runs B get the full bridge, or does
the seam leak (loader in the wrong package, schema lost, toolchain needed at
consume time)?**

**Run 3 — the honest control.** The same consumption task through raw
py-tree-sitter: load the `.so` with ctypes yourself, no schema, hand-rolled
`.scm` + dispatch. Compare author effort and where mistakes surface. If Run 2
is not meaningfully better on the control's own terms, that is a reach no-go
signal.

**Verdict framing (be explicit):** Phase 5 proves the reach — corpus authoring
is regression-safe, and the artifact seam holds across a real process boundary
with the checks intact — or it doesn't. A no-go means the harness is ceremony
or the bundle leaks, not that the machinery failed. Phase 4's GO must NOT
rubber-stamp this.

### Supporting surface (the Phase-5 build)

1. **Corpus testing (B, the centerpiece):** `pydantree_sitter_grammar/corpus.py` —
   `Corpus`/`corpus_case(source, expected_sexp)` + a runner that builds (or
   reuses a `BuildResult`), parses each case, renders the CST to a sexp
   string, diffs against the expectation (with a normalization option:
   drop anonymous tokens or keep them — document the choice), and reports
   per-case failures with the case's source line. Snapshotting: write the
   built `grammar.json` + node-schema beside the corpus for reviewable diffs.
   `semantic_smoke` should delegate to (or be reimplemented on top of) the
   corpus runner — no parallel machinery. A default corpus for
   `ExpressionGrammar` grammars (the probe-2 table) stays available.
2. **Artifact packaging (B + pydantree_sitter + A):** `BuildResult.package(dir)` (or a
   small `pydantree_sitter_grammar.package(result, dir)`) emits the bundle:
   `grammar.so`, `node-schema.json`, `tree-sitter.json` (metadata), and a
   `loader.py` (a few lines: ctypes → PyCapsule → `tree_sitter.Language` —
   the loader **belongs in `pydantree_sitter`** as the shared artifact-loading contract,
   CONCEPT §8, so both B's `pydantree_sitter_grammar.language` and A can use it without
   importing each other). A side: `pydantree_sitter` consumes the bundle — `Language.load`
   already accepts a language + schema; make loading a bundle directory a
   one-liner (a `pydantree_sitter.language`-level helper or a `Language.load_bundle(dir)`).
   **A must not gain a pydantree_sitter_grammar dependency** — the loader and schema are the
   only imports.
3. **Community-schema tool (small):** given a grammar source dir containing a
   `grammar.json` (or a pydantree_sitter_grammar IR), run the CLI generate (which produces
   `node-types.json`) and emit `node-schema.json` via `derive_from_node_types` —
   the "community grammar ships no schema" path from CONCEPT §7, now a
   one-command tool. Demo it over the json grammar IR and verify the derived
   schema is equivalent to `derive_from_ir`'s on the shared subset (the Phase-4
   agreement check, reused).
4. **Incremental reparse + typed Diagnostics (A):** wrap the 0.26 API —
   `Language.reparse(old_tree, new_source)` (the binding's `parse(source,
   old_tree)`; edits are internal, source re-given) for editor-ish consumers.
   Turn `Query.validate`'s dict diagnostics into typed `Diagnostic{kind, span,
   expected?, snippet}` objects (CONCEPT §5.6 promised them). Small; the
   reparse demo can be an edit-apply loop over the cfg corpus.
5. **A polish items (each small, schema-checked where possible):**
   - **richer `ExtractionError`** — per-match detail (pattern/anchor, pydantic
     errors, source snippet), not just the first error (spike-a §4).
   - **descendant matching** — a `...` path element in `M()` (or a
     `M(..., anywhere=True)` knob) implemented via the `#has-ancestor?`
     predicate (verified supported in the installed 0.26 bindings), checked by
     Job 1 against the schema. Assess first: what `#has-ancestor?` can and
     cannot express (it cannot bound depth); if it doesn't work cleanly, note
     the alternative and move on (80% rule).
   - **field-mode lists** — reuse the anchor-merge machinery from record mode:
     a `list[X] = capture("f")` field-mode capture collects the repeated
     field's occurrences across matches sharing the `@__anchor__` (spike-a2 §4
     gap 2). Medium; the machinery exists, the field-mode derivation + merge
     does not.
   - **string unescaping** — an `Unescaped()` marker (or a documented
     alternative) on `str` fields that decodes the grammar's escape sequences
     (JSON first: `\n`, `\"`, `\\`, `\uXXXX`), schema-validated (the value
     kind must be a string wrapper). **Note:** this is new annotation
     vocabulary — the Phase-4 surface is frozen, so treat it as a
     go-with-changes finding, not a license to expand.
6. **External-scanner escape hatch (B, small):** the pipeline already accepts
   `scanner=` and the DSL has `g.external(...)`; make the loop airtight (a
   grammar with `externals` builds and parses when a scanner is supplied, with
   a clear error when not) and ship **one** canonical prebuilt scanner if
   feasible (an indentation scanner for a mini-Python-like grammar) as the
   library's seed. If the C scanner work balloons, ship the mechanism + tests
   and note the library as Phase-6.

### Out of scope — say no to these (politely)

- **wasm distribution.** The native `.so` bundle covers the distribution
  reach; wasm adds an emscripten toolchain probe and a runtime. **Assess
  only**: what it would take (CONCEPT §4.7 step 3, §11 risk 5) and whether the
  `.so` bundle is enough for the reach claim. Do not build it.
- **Performance work, incremental-reparse wrappers beyond the one `reparse` +
  `Diagnostic` item, corpus-testing harness gold-plating** (no DSL-driven
  corpus format, no golden-file framework — Python cases + a diff are the
  deliverable).
- **New Product A surface beyond the four named polish items.** Each must be
  schema-checked where possible and justified; anything else is a
  go-with-changes finding.
- **Grammar-authoring features beyond the scanner escape hatch.** No new
  ladder features, no regex-subset validator (still noted, not built), no
  scanner-authoring language.
- **Regex-subset validation, generator rewrite, C-runtime work.** Not ours.

## Environment setup (do this first)

1. `devenv shell` — works (fixed in Phase 0). If it isn't, tell the user
   immediately.
2. **Verified facts (don't re-derive):** tree-sitter CLI 0.25.3, bindings
   0.26.0 (`LANGUAGE_VERSION=15`, `MIN_COMPATIBLE=13`), pydantic 2.13.4, gcc
   14.2.1. ABI 15 via `tree-sitter.json`; conflicts = exit 1, first-only,
   `--json` on stderr; load via PyCapsule `tree_sitter.Language`. Incremental
   reparse = `Parser.parse(new_source, old_tree)` (no edit tuples in this
   binding). `#has-ancestor?` IS supported by `Query()` in this binding.
   All in `src/pydantree_sitter_grammar/pipeline.py` + Phase-2/4 FINDINGS appendices.
3. **Wheels:** `tree-sitter-python` and `tree-sitter-json` are installed in
   the devenv venv (the Run-3 control and the community-path demo need them).
   `import pydantree_sitter_grammar`, `import pydantree_sitter`, `import pydantree_sitter` all work (editable
   install; `src/` is on the path via the devenv).
4. **Phase-4 fixtures you will reuse:** `.scratch/006-query-bridge/` has
   `cfg_grammar.py` (the Run-1 grammar + corpus + hand-computed ground truth),
   `json_grammar.py` (the JSON IR that matches the wheel's kinds), and
   `experiment_phase4.py`. `tests/test_schema.py` has the agreement-check
   helper; `tests/test_phase3a.py` has the smoke tests.
5. **Before writing helpers:** re-run Phase 4's `experiment_phase4.py` (the
   pipeline + fixtures are warm) and `tests/` (106 green at phase end), then
   hand-write Run 1's corpus on paper before coding the harness — the
   "hand-written first" discipline, repeated at the corpus level.

## Working agreement

- **Commit after each meaningful step** (e.g.
  `pydantree_sitter_grammar: corpus harness — (source, expected-sexp) cases, CST render + diff, grammar/node-schema snapshots; semantic_smoke delegates to it`,
  `pydantree_sitter: artifact loader (PyCapsule) as the shared loading contract; BuildResult.package() emits grammar.so + node-schema.json + metadata + loader`,
  `pydantree_sitter: consume a packaged bundle in a B-free subprocess — checks active, ground truth passes`,
  `pydantree_sitter_grammar: community-schema tool (node-types.json -> node-schema.json)`,
  `pydantree_sitter: reparse + typed Diagnostics (kind/span/expected/snippet)`,
  `pydantree_sitter: ExtractionError per-match detail + descendant M(...) via has-ancestor + field-mode lists via anchor-merge + Unescaped()`,
  `pydantree_sitter_grammar: scanner escape hatch airtight + indentation scanner seed`,
  `phase5: experiment — reach verdict (corpus bite + B-free bundle + control), evidence captured`).
- **Write findings as you go** into `.scratch/007-query-distribution/FINDINGS.md`.
  The code is the foundation; the findings are the deliverable.
- **Don't gold-plate.** 80%-done steps get a note and a move-on.
- **Don't fake the primary experiment.** Run 1's planted regressions, Run 2's
  B-free subprocess, and Run 3's control must be real and hand-verified. Save
  raw outputs verbatim under `.scratch/007-query-distribution/evidence/`.
- **Ask before expanding scope** beyond this brief.

## Deliverables (end of session)

1. Working Phase-5 extensions, all committed:
   - `src/pydantree_sitter_grammar/corpus.py` (harness + snapshots; `semantic_smoke` delegates);
   - artifact packaging (`BuildResult.package()` or `pydantree_sitter_grammar.package`) +
     the loader in `src/pydantree_sitter/` (shared loading contract) + A's
     bundle-consumption helper;
   - the community-schema tool;
   - `src/pydantree_sitter/` — `reparse` + typed `Diagnostic`s + the polish items that
     land (richer `ExtractionError`, descendant `M(...)`, field-mode lists,
     `Unescaped()`) — each schema-checked where possible;
   - the scanner escape hatch (airtight) + the indentation-scanner seed if it
     stays small;
   - pytest tests covering: the corpus runner (pass + each planted
     regression caught), the bundle round-trip (B builds → A consumes
     B-free → checks active → ground truth), the community-schema equivalence
     (reuse the agreement check), reparse + `Diagnostic`, and the polish items.
2. Demonstrated, with evidence:
   - (a) Run 1: the corpus bite — planted regressions caught at author time
     (which needed the full corpus vs the smoke seed), effort metrics;
   - (b) Run 2: the bundle consumed in a B-free subprocess with the Phase-4
     ground truth passing, plus the community path over `tree_sitter_json`;
   - (c) Run 3: the raw py-tree-sitter control, with the comparison table.
3. `.scratch/007-query-distribution/FINDINGS.md` answering at minimum:
   - Does the corpus harness change the feel of B authoring (the bet-#1
     residual: does it close the semantic-intent leak)? What does it cost to
     author a corpus, and where does it leak (cases it cannot express)?
   - Does the artifact seam hold in production (the bet-#2 residual)? What
     does a B-free consumer get vs raw py-tree-sitter — and does the bundle
     require anything beyond the artifact (loader placement, schema loss)?
   - Which Phase-5 items landed and which didn't, and what that says about
     the reach plan as specced.
   - Re-assess **§11 risks** from the Phase-5 side (4 upstream churn —
     reparse/`has-ancestor` version-dependence; 2/3 scanner + toolchain
     packaging for B) plus anything Phase 5 surfaced (e.g. whether the
     `has-ancestor` descendant approach bounds depth acceptably, whether the
     native-only bundle is enough without wasm).
   - **Recommendation:** go / go-with-changes / no-go on Phase 5's reach,
     and the single most important next step (Phase 6 — wasm + scanner
     library + Job-2 stubs? a Phase-5A hardening pass? or a rethink).
4. Everything committed and pushed.

## Appendix — durable facts Phase 5 builds on (all from prior phases, verified)

1. **The bridge is proven (Phase 4).** `validate_with(language, schema=)`
   runs Jobs 1/3/4 at class-creation-adjacent time with the schema entry +
   model site cited; the record shape map is derived (`pydantree_sitter.shapes.shape_for`
   — 0 hand-written lines for the common case, 0 `NodeKind` overrides); record
   anchoring kills the nested-collision class; the model surface is frozen and
   unchanged. Evidence: `.scratch/006-query-bridge/evidence/`.
2. **The node-schema derivation is exact.** `derive_from_ir` matches the CLI's
   `node-types.json` (0 diffs on every grammar tested); `derive_from_node_types`
   is equivalent on the shared subset. `pydantree_sitter.schema.NodeSchema` has the query
   helpers (`possible_children`, `expand`, `field_types`, …).
3. **The artifact seam is one artifact.** A never imports B; the only coupling
   is `grammar.so + node-schema.json`. `BuildResult.node_schema_json` is on
   disk and cached; `BuildResult.node_schema()` loads it. Phase 5 adds the
   loader to `pydantree_sitter` (CONCEPT §8: pydantree_sitter owns the artifact-loading contract).
4. **The 0.26 substrate** (all probed in prior phases, plus two new facts):
   predicates inside pattern parens; per-occurrence match repeats (lists =
   anchor-merge); capture-suffix binding; `Query()` validates kinds/fields for
   free; alternation = multi-pattern; anchored patterns re-match per inner
   occurrence; **`Parser.parse(new_source, old_tree)` is the incremental
   reparse** (no edit tuples); **`#has-ancestor?` is supported by `Query()`**
   (descendant matching is expressible via it).
5. **`semantic_smoke` is the corpus seed.** `src/pydantree_sitter_grammar/expressions.py`:
   `DEFAULT_PRECEDENCE_CORPUS` (the probe-2 table: `-a^b → -(a^b)`,
   `-f(x) → -(f(x))`, `a.b.c`, `f(x)(y)`, `-a or b`), a CST renderer that
   walks the first `expr` node, and `cases=` override — the harness should
   generalize this, not parallel it.
6. **The planted-regression classes** (Phase-3 §4, all generate-clean-wrong):
   unary-above-pow flips `-a^b` to `(-a)^b`; associativity flips change
   chains; postfix-below-unary parses `-f(x)` as `(-f)(x)`. The smoke corpus
   already catches the first; the harness must catch all three plus
   statement-level regressions.
7. **The anchor-merge machinery exists** (record mode): `_record_kwargs`
   merges captures across matches anchored at the record node; field-mode
   lists reuse it with the field-mode `@__anchor__`.
8. **Phase-4 fixtures:** `cfg_grammar.py` (15 rules, analyzer CLEAN, ABI 15,
   hand-computed ground truth for record + field tasks), `json_grammar.py`
   (the JSON IR matching the wheel's kinds — the community-path demo target),
   `experiment_phase4.py`. Package layout: wheel packages =
   `["src/pydantree", "src/examples", "data", "src/pydantree_sitter_grammar", "src/pydantree_sitter",
   "src/pydantree_sitter"]`.
