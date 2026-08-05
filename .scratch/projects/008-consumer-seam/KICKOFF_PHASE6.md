# KICKOFF — pydantree Phase 6 (the consumer seam): packaging, real community grammars, and the deferred surface

> Copy the whole contents of this file into a fresh session working in this repo.
> Phase 5 (`.scratch/007-query-distribution/`) proved the reach — corpus
> harness + the artifact seam — and delivered verdict **GO, go-with-changes**,
> naming Phase 6 as wasm + scanner library + Job-2 stubs, with the honest
> residuals documented. THIS session is Phase 6 — **the consumer seam**: make
> the A/B split real at the packaging level (CONCEPT §8 was specced but never
> built — today ONE distribution ships pydantree_sitter_grammar+pydantree_sitter+pydantree_sitter together), prove
> the community-schema path over a grammar we don't own, and land (or honestly
> assess) the deferred surface: Job-2 `.pyi` stubs, the scanner library seeds,
> the wasm probe (assess-only), and the documented residuals (the schema
> registry's name-keyed global leak, the name-based kind-inference residue, the
> field-mode-list wrapper-field case). Findings go in
> `.scratch/008-consumer-seam/FINDINGS.md`.

---

## Mission

Phases 0–5 are done and passed. Phase 5 proved: the corpus harness catches
generate-clean semantic regressions (and a real latent grammar bug), and the
artifact bundle (`grammar.so` + `node-schema.json` + metadata + 7-line loader)
is consumed B-free across a real process boundary with the checks intact — and
it **exposed a real leak** (pydantree_sitter imported pydantree_sitter_grammar at module level; fixed by
`pydantree_sitter._ir_derive`). This session delivers **Phase 6 — the consumer seam**:
the same claims, at the level a real user experiences them. Three questions
decide it:

1. **The packaging seam (CONCEPT §8, never built):** can a user install
   **pydantree_sitter + pydantree_sitter only** (light, no toolchain) and get the full checked
   extraction — while **pydantree_sitter_grammar** (heavy: Rust CLI + C toolchain) ships
   separately? Today `pyproject.toml` publishes ONE wheel containing all three
   packages and pins `tree-sitter>=0.23` while the code uses 0.26-only APIs.
   The go/no-go: a **fresh venv** (no editable `src/` on the path, no
   pydantree_sitter_grammar) installs the light distributions and the Phase-5 bundle
   round-trip + community extraction pass there, byte-identical to the
   in-repo results.
2. **The community seam over a REAL grammar:** the community-schema tool
   (`derive_schema_for_dir`) has only ever been exercised over **our own** json
   IR + the json/python wheels. Take an actual community grammar *source*
   (tree-sitter-rust, or the real tree-sitter-python checkout), derive the
   schema, check byte-for-byte agreement with the CLI's `node-types.json`, and
   extract a real task B-free with the checks active. The go/no-go: the
   "works over the hundreds of prebuilt grammars" claim holds over a grammar we
   don't own.
3. **The deferred surface:** Job-2 `.pyi` stubs (Phase 4: "worth it after
   distribution" — distribution is now proven), the scanner library seeds
   (heredoc / matched-delimiter / contextual-keyword), the **wasm probe**
   (assess only — what it would take, the same bundle layout with a `.wasm`),
   and the honest residuals (the `_SCHEMA_REGISTRY` name-keyed global leak,
   the name-based kind inference residue — likely re-document-and-move-on, and
   the field-mode-list wrapper-field case — likely document-and-move-on).

Deliver a **go / go-with-changes / no-go verdict with evidence** for each run.
If the light install leaks pydantree_sitter_grammar, or the community tool disagrees over a
real grammar, or every deferred item balloons, say so plainly — a no-go on Run
1 or 2 is an architecture-changing result (the A/B split is the CONCEPT's
load-bearing claim).

## Context: where we are

- **Phases 0–4 (done):** emission + conflict remapping; Product A's model-only
  surface; Product B core; the GLR-ergonomics layer (GO on bet #1); the bridge
  (GO on bet #2). The record value-shape map is derived, the model surface is
  frozen, `src/pydantree` is the deprecated first-principles wrapper — **do not
  touch**.
- **Phase 5 (done, THIS phase's foundation):** `.scratch/007-query-distribution/` —
  the corpus harness (`pydantree_sitter_grammar/corpus.py`, `semantic_smoke` delegates), the
  artifact seam (`pydantree_sitter/loader.py` = the shared loading contract,
  `BuildResult.package()` → 4-file bundle, `pydantree_sitter.Language.load_bundle`), the
  community-schema tool (`pydantree_sitter_grammar/schema_tool.py`), A polish (reparse +
  typed `Diagnostic`, per-match `ExtractionError`, descendant `...`,
  field-mode lists, `Unescaped()`), the airtight scanner escape hatch +
  indentation-scanner seed (`pydantree_sitter_grammar/scanners/`), and the B-free subprocess
  machinery (`bfree.py`, `consumer*.py`, `consumer_env/sitecustomize.py`).
  Verdict: **GO, go-with-changes**; next step named: Phase 6 — wasm + scanner
  library + Job-2 stubs.
- **Packaging (the gap this phase closes):** `pyproject.toml` publishes ONE
  distribution `pydantree` with `packages = ["src/pydantree", "src/examples",
  "data", "src/pydantree_sitter_grammar", "src/pydantree_sitter", "src/pydantree_sitter"]` and
  `tree-sitter>=0.23`. **No wheel has ever been built** (the devenv venv has no
  pip — `uv` is the manager). The CONCEPT §8 layout (pydantree_sitter tiny shared,
  pydantree_sitter light, pydantree_sitter_grammar heavy) is code-only; the distribution has never
  matched it.

## Required reading (in this order — do not skip)

1. **`.scratch/007-query-distribution/FINDINGS.md`** — Phase 5's verdict, §4
   (the landed/not-landed table — the exact surface you will extend), §5 (§11
   re-assessment: the `.so` bundle is enough for the reach claim, scanner
   library = Phase-6, upstream-churn bounds), §6 (the recommendation and next
   step), and the Appendix (9 durable facts, incl. the B-free boundary being
   the honest test and the registry/global-leak fact if noted).
2. **`.scratch/002-pydantic-treesitter/CONCEPT.md`** — §8 (the distribution
   strategy this phase builds: pydantree_sitter tiny pure-Python + the artifact-loading
   contract, pydantree_sitter light runtime with no Rust CLI/compiler, pydantree_sitter_grammar heavy
   build tool), §1 (why two libraries — the A-without-B pitch), §7 (the
   bridge; Job-2 typed node access), §4.6/4.7 (external scanners, the build &
   distribute pipeline).
3. **`.scratch/006-query-bridge/FINDINGS.md`** — §4 (Job 2 assessed-not-built:
   "generate accessor types from the schema's per-kind children/fields (a
   `node.get("statement") -> list[Statement]` surface), shipped as `.pyi`
   alongside the schema. Worth it **after** Phase-5 distribution"), and §5 (the
   leak list).
4. **`spike-a/FINDINGS.md`** — §4 (Job-2 context and the materializer gaps).
5. **Phase-6 code you will extend (skim, then read the parts you touch):**
   - `pyproject.toml` — the one-distribution gap; the split starts here.
   - `src/pydantree_sitter/typed.py` — `_SCHEMA_REGISTRY: dict[str, object]` keyed by
     language name (registered in `Language.__init__` when a schema binds,
     looked up in `_resolve_language`; the leak: a bound schema silently
     applies to later schema-less consumers of the same grammar — tests
     needed `_isolate_schema_registry` fixtures).
   - `src/pydantree_sitter/schema.py` + `src/pydantree_sitter/loader.py` + `src/pydantree_sitter/_ir_derive.py` —
     the B-free seam (verified); the schema's per-kind children/fields are the
     Job-2 stub source.
   - `src/pydantree_sitter_grammar/schema_tool.py` — the community tool (Run 2's subject).
   - `src/pydantree_sitter_grammar/scanners/` — `indent_scanner.c` (the seed), `scanner_for()`
     (the library table to grow).
   - `.scratch/007-query-distribution/bfree.py` + `consumer*.py` + the
     bundle — the fresh-venv harness reuses/replaces the subprocess machinery.
   - `tests/test_bundle.py`, `tests/test_scanners.py`, `tests/test_phase5_apolish.py` —
     the patterns to extend.

## Phase 6 in 60 seconds

```
   Run 1 — the packaging seam (6A)          Run 2 — the community seam (6A)
   one dist -> pydantree_sitter + pydantree_sitter (light)     real grammar SOURCE (rust/python)
   pydantree_sitter_grammar (heavy) separate               -> schema tool -> node-types.json
   pins -> tree-sitter>=0.26                -> byte-for-byte agreement check
   wheel build + FRESH VENV (uv, no src)    -> build + B-free extraction task
   bundle round-trip + community path       -> checks active, hand truth
   go/no-go: A installs light, B separate   go/no-go: the hundreds-of-grammars claim

   Run 3 — the deferred surface (6B)
   Job-2 .pyi stubs (schema -> typed accessors) | scanner seeds (heredoc/
   matched-delimiter) | wasm probe (ASSESS ONLY) | registry leak fix |
   name-inference + wrapper-field residuals (document-and-move-on)
```

The whole point: Phase 5 proved the artifact seam across a process boundary;
Phase 6 proves it across the **install boundary** (a fresh venv with only the
light packages) and across the **grammar-ownership boundary** (a grammar we
don't own), and lands the surface that was explicitly deferred "until after
distribution."

## Phase 6 scope

### Primary experiment (the go/no-go): the consumer seam

**Run 1 — the packaging seam (the centerpiece).** Split the distribution so
`pydantree_sitter` + `pydantree_sitter` install WITHOUT `pydantree_sitter_grammar`, and `pydantree_sitter_grammar` (the heavy
build tool) ships separately. Decide the layout and document it: the natural
hatchling shape is a `pyproject.toml` per package under `src/` (each its own
installable); the hard requirements are (a) a light install that resolves
`pydantic` + `tree-sitter>=0.26` only, (b) a heavy install that additionally
carries pydantree_sitter_grammar + the scanner package data (`scanners/indent_scanner.c` must
ride in the wheel), and (c) **the dev flow keeps working** — the tests import
`pydantree_sitter_grammar`/`pydantree_sitter`/`pydantree_sitter` from `src/` via the editable install, so either
a root dev-only pyproject that installs all three editable, or per-package
editable installs, must cover the suite. Keep the legacy `pydantree` /
`examples` / `data` packages out of the light installables (deprecated wrapper,
untouched). Tighten `tree-sitter>=0.23` → `>=0.26` (the code uses 0.26-only
APIs: `Parser.parse(new, old)` reparse, `#has-ancestor?` probes,
`field_name_for_child`, `node.id`, `is_missing`). Then the **fresh-venv
end-to-end test**: `uv venv` (the devenv venv has NO pip — uv is the manager;
may need network or a local wheelhouse — if offline, `--system-site-packages`
with a documented caveat), install ONLY the light wheels + the community wheel
deps, assert `import pydantree_sitter_grammar` fails, run the Phase-5 bundle round-trip
(`Language.load_bundle` → Jobs 1/3/4 → the cfg record + field ground truth)
and the community extraction (json schema over `tree_sitter_json` → Person
ground truth). Metrics: the wheel contents + sizes (scanner `.c` present in the
heavy wheel, absent in the light), the dependency resolution, the light
install's import graph (`pydantree_sitter` → `pydantree_sitter` → pydantic/tree_sitter, never
pydantree_sitter_grammar), and the byte-identical A surface vs the in-repo results. **The
go/no-go: a consumer who installs only the light packages gets the full
checked extraction, and B's toolchain stays out — or the seam leaks (pydantree_sitter_grammar
pulled in transitively, package data lost, fresh venv broken).**

**Run 2 — the community seam over a real grammar.** Acquire a real community
grammar *source* (pip-download the sdist of `tree-sitter-rust`, or
`tree-sitter-python`'s source — network; the sdists contain the grammar
source). Run `pydantree_sitter_grammar.schema_tool` over it; the tool's contract is
byte-for-byte agreement with the CLI's own `node-types.json`. Then build + load
the grammar and extract a real task B-free with the checks active — hand-author
the ground truth first (e.g. Rust function definitions: name, params, return
type, or Python functions/classes over the real python grammar source). Metrics:
the agreement diff (0 expected), the extraction rows vs hand truth, and an
honest catalog of where the tool leaks over a grammar we don't own (grammar.js
quirks, aliases/inlines, reserved words, externals the IR path never hit). **The
go/no-go: the "hundreds of community grammars" claim holds over a grammar we
didn't author — or the schema tool needs an IR-shaped byproduct and the claim
is weaker than pitched.**

**Run 3 — the deferred surface (assess + land, each small).**
- **Job-2 `.pyi` stubs** (medium): a `NodeSchema`-driven stub generator —
  per-kind typed accessors (`node.get("statement") -> list[Statement]`,
  `field("name") -> Name | None`) emitted as a `.pyi` beside the schema.
  Build the minimal honest version (a generator + a test over the cfg/json
  schema that the stub parses and the accessors type-check against a real
  node) or, if it balloons, ship the assessment (what it would take, who it
  serves) and move on.
- **Scanner library seeds** (small-medium): 1–2 more canonical scanners —
  heredoc or matched-delimiter — following the airtight mechanism (scanner=,
  cache keying, `ExternalScannerRequiredError`), each with a mini-grammar +
  tests. The full library stays Phase-7 if any seed balloons.
- **wasm probe (ASSESS ONLY — do not build):** what it would take (emscripten
  toolchain probe, the same 4-file bundle layout with a `.wasm` in place of
  the `.so`, a wasm runtime in A, the ~1.5–2× perf note), and whether the
  native bundle + per-platform wheels are enough for the distribution claim.
  One page in FINDINGS; no code beyond a probe script if cheap.
- **The honest residuals:** fix the `_SCHEMA_REGISTRY` name-keyed global leak
  (a bound schema silently applies to later schema-less consumers of the same
  language name — scope it properly: per-`Language`-instance binding with the
  name-keyed convenience made opt-in, or the equivalent; the convenience
  `validate_with(lang)`-finds-the-schema must keep working). The name-based
  kind-inference residue (documented, `NodeKind` is the escape) and the
  field-mode-list wrapper-field case (`list[X] = capture("arguments")` where
  the field points at a wrapper) are likely **document-and-move-on** — say so
  plainly with the note.

### Out of scope — say no to these (politely)

- **wasm runtime.** Assess-only (Run 3). The native `.so` bundle + wheels are
  the distribution claim; wasm adds an emscripten toolchain probe and a
  runtime for a portability win Phase 5 already found unnecessary for reach.
- **New Product A surface beyond the named residuals.** Each must be
  justified; anything else is a go-with-changes finding.
- **Grammar-authoring features** (no new ladder/expression work, no
  regex-subset validator — still noted, not built).
- **Corpus-harness gold-plating** (no DSL-driven corpus format, no golden-file
  framework), **performance work**, **the generator rewrite**, **C-runtime
  work**, **touching `src/pydantree`** (deprecated first-principles wrapper).

## Environment setup (do this first)

1. `devenv shell` — works (Phase 0 fixed). If it isn't, tell the user
   immediately.
2. **Verified facts (don't re-derive):** tree-sitter CLI 0.25.3, bindings
   0.26.0 (`LANGUAGE_VERSION=15`, `MIN_COMPATIBLE=13`), pydantic 2.13.4, gcc
   14.2.1. ABI 15 via `tree-sitter.json`; PyCapsule loading via
   `pydantree_sitter.loader.load_grammar_so`. **NEW for this phase:** the devenv venv has
   **no pip** (`python -m pip` → "No module named pip"); **uv** is the package
   manager (`devenv.yaml`: `uv.enable = true`). Fresh-venv testing uses
   `uv venv` / `uv pip install` (index or `--find-links` wheelhouse; if
   offline, `--system-site-packages` with a documented caveat).
3. **Wheels:** `tree-sitter-python` and `tree-sitter-json` installed in the
   devenv venv. `import pydantree_sitter_grammar`, `import pydantree_sitter`, `import pydantree_sitter` all work
   (editable install; a `.pth` in site-packages points at `src/` — that entry
   is what the B-free sitecustomize strips).
4. **Phase-5 fixtures you will reuse:** `.scratch/007-query-distribution/` —
   `bfree.py` (`build_consumer_env`, `run_bfree`), `consumer.py` (the cfg
   bundle consumer), `consumer_community.py`, `consumer_env/sitecustomize.py`,
   the cfg/json grammars in `.scratch/006-query-bridge/`, the bundle
   round-trip in `tests/test_bundle.py`, the scanner mechanism in
   `tests/test_scanners.py`.
5. **Before writing helpers:** re-run `python -m pytest tests/` (139 green at
   phase end) and `.scratch/007-query-distribution/experiment_phase5.py`,
   then hand-author Run 2's extraction ground truth on paper before coding the
   model (the "hand-written first" discipline, repeated at the corpus/ground
   truth level). Also run a wheel build probe (`uv build`, or `uv pip wheel .`)
   EARLY to capture the pre-split wheel's actual contents as baseline evidence.

## Working agreement

- **Commit after each meaningful step**, e.g.:
  `packaging: split distributions — pydantree_sitter/pydantree_sitter light installables, pydantree_sitter_grammar heavy; tree-sitter>=0.26 pin; scanner .c rides as package data; dev flow (editable) still covers the suite`,
  `phase6: fresh-venv harness (uv) — light install, pydantree_sitter_grammar unimportable, bundle round-trip + community extraction byte-identical`,
  `pydantree_sitter_grammar: community seam over tree-sitter-rust (or python) — schema tool agreement + B-free extraction vs hand truth`,
  `pydantree_sitter: Job-2 .pyi stubs from the schema (typed per-kind accessors)`,
  `pydantree_sitter_grammar: scanner library seeds (heredoc/matched-delimiter) + tests`,
  `pydantree_sitter: fix the schema-registry name-keyed global leak (per-Language scoping, convenience preserved)`,
  `phase6: experiment — consumer-seam verdict (packaging + community + deferred surface), evidence captured`).
- **Write findings as you go** into `.scratch/008-consumer-seam/FINDINGS.md`.
  The code is the foundation; the findings are the deliverable.
- **Don't gold-plate.** 80%-done steps get a note and a move-on.
- **Don't fake the primary experiment.** Run 1's fresh venv, Run 2's real
  grammar, and Run 3's assessments must be real and hand-verified. Save raw
  outputs verbatim under `.scratch/008-consumer-seam/evidence/`.
- **Ask before expanding scope** beyond this brief.

## Deliverables (end of session)

1. Working Phase-6 extensions, all committed:
   - the distribution split (light `pydantree_sitter`+`pydantree_sitter` installables; `pydantree_sitter_grammar`
     heavy with the scanner package data; the legacy packages excluded from the
     light installs) + the `tree-sitter>=0.26` pin + the dev-flow solution;
   - the fresh-venv harness + end-to-end test (light install → pydantree_sitter_grammar
     unimportable → bundle round-trip + community extraction pass);
   - the Run-2 community validation (real grammar source → schema tool →
     agreement → B-free extraction vs hand truth);
   - Job-2 `.pyi` stubs (generator + test) OR the honest assessment;
   - 1–2 scanner library seeds (+ mini-grammars + tests) OR the note;
   - the schema-registry leak fix + the documented-and-moved-on residuals;
   - pytest tests covering the packaging split, the fresh venv, the community
     agreement/extraction, the stubs, and the scanner seeds.
2. Demonstrated, with evidence:
   - (a) Run 1: the fresh-venv light install working B-free (wheel contents,
     dep graph, byte-identical surface);
   - (b) Run 2: the real-grammar agreement + extraction (0-diff claim or the
     honest leak catalog);
   - (c) Run 3: Job-2 stubs, scanner seeds, the wasm probe page, the registry
     fix — each landed or assessed.
3. `.scratch/008-consumer-seam/FINDINGS.md` answering at minimum:
   - Does the light install really deliver A without B (the CONCEPT §8 claim,
     now at the install boundary)? What does a consumer get, and what does the
     heavy install still need (toolchain, scanner data)?
   - Does the community-schema path hold over a grammar we don't own? Where
     does it leak (grammar.js quirks, externals, reserved words)?
   - Which Run-3 items landed vs assessed, and what that says about the
     deferred surface as specced.
   - Re-assess the §11 risks from the Phase-6 side (3 toolchain packaging for B
     now that it ships separately; 4 upstream churn — the 0.26 pin is now a
     dependency floor; 5 wasm perf, post-probe) plus anything Phase 6 surfaced.
   - **Recommendation:** go / go-with-changes / no-go on the consumer seam,
     and the single most important next step (Phase 7 — the scanner library +
     wasm runtime + Job-2 completion? a real-user adoption pass? or a
     rethink).
4. Everything committed and pushed.

## Appendix — durable facts Phase 6 builds on (all from prior phases, verified)

1. **The artifact seam is one artifact + one loading contract.** A never
   imports B; the bundle is `grammar.so` (export symbol recorded in the
   metadata — the bundle renames it) + `node-schema.json` + `tree-sitter.json`
   + a 7-line `loader.py` delegating to `pydantree_sitter.loader.load_bundle`.
   `Language.load_bundle(dir)` is the one-line consumer. Verified B-free in a
   subprocess with the editable `src/` install stripped.
2. **pydantree_sitter is B-free at import time** (the Phase-5 fix): the exact-path
   derivation lives in `pydantree_sitter._ir_derive`, imported only when
   `derive_from_ir` is called (B-side only); `import pydantree_sitter` / `import
   pydantree_sitter` never touch pydantree_sitter_grammar — the packaging split can rely on this.
3. **The 0.26 substrate** (probed): nesting is CHILD-level in queries
   (compiler even rejects impossible patterns); `#has-ancestor?` works only
   for captures that textually precede the predicate (the descendant `...`
   therefore uses an ancestor walk, not the predicate); repeated CST fields
   yield one match per occurrence; supertype kinds match nothing in queries;
   incremental reparse = `Parser.parse(new_source, old_tree)`.
4. **The indentation scanner's canonical cadence**: mark_end before the loop +
   the newline SKIPPED (zero-width NEWLINE token, next call re-measures for
   DEDENT/INDENT); comment-lines count as newlines; EOF flushes DEDENTs;
   blocks are `INDENT statements DEDENT` (a NEWLINE-then-INDENT grammar
   sequence cannot work).
5. **The editable-install mechanics**: a `.pth` in site-packages points at
   `src/`; the B-free subprocess uses a `sitecustomize` that strips any path
   containing `pydantree/src`, with `pydantree_sitter`/`pydantree_sitter` copied into the
   consumer env's `lib/`. The consumer asserts `import pydantree_sitter_grammar` fails.
6. **The devenv venv has no pip; uv is the manager.** Fresh-venv work is
   `uv venv` + `uv pip install`; a wheel build probe is `uv build` (or
   `uv pip wheel .`).
7. **The registry leak is real and documented.** `_SCHEMA_REGISTRY` in
   `pydantree_sitter/typed.py` is keyed by language name: a schema bound via
   `Language.load(lang, schema=...)` is found later by ANY schema-less
   consumer of the same language name. Tests needed `_isolate_schema_registry`
   fixtures (save/clear/restore). The convenience it provides
   (`validate_with(lang)` finds the schema) must survive the fix.
8. **The name-based kind inference residue** (Phase-4 §5.1): "number → int" is
   a convention; `NodeKind` is the typed escape. Documented; the schema
   restricts WHICH kinds are candidates exactly, the Python-type half is a
   name pattern.
9. **Package layout:** the six packages are `src/pydantree` (legacy, frozen),
   `src/examples`, `data`, `src/pydantree_sitter_grammar`, `src/pydantree_sitter`, `src/pydantree_sitter`;
   hatchling builds from the `[tool.hatch.build.targets.wheel] packages`
   list. The Phase-5 suite is 139 tests green; the three experiments
   (`.scratch/005/006/007`) re-run clean.
