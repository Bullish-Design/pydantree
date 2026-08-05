# KICKOFF — Phase 7, item 3: the wasm runtime + the scanner library (the remaining deferred surface)

> Copy the whole contents of this file into a fresh session working in this repo.
> This is the exploration prompt for Phase 7 item 3 (per Phase-6's findings §5):
> the wasm runtime (the portability story — assessed-not-built in Phase 6) and
> the per-language scanner library growth. Phases 0–6 are done; the consumer
> seam (install boundary + grammar-ownership boundary) is PROVEN (Phase-6
> verdict: GO). What a fresh session lands here: a REAL wasm build + runtime
> assessment (or a decisive no-go with evidence), and 1–2 REAL per-language
> scanner copies following the airtight mechanism. Findings go in
> `.scratch/009-phase7/FINDINGS.md`.

---

## Mission

Phase 6 proved the consumer seam at the install boundary (a light install of
`pydantree-pydantree_sitter` + `pydantree-pydantree_sitter` runs the full checked extraction,
B-free) and at the grammar-ownership boundary (the node-schema derivation is
byte-for-byte with the CLI's node-types.json over FOUR real grammars: rust,
python, markdown-block, markdown-inline). Two items were explicitly deferred
to "when users ask": **the wasm runtime** (assessed-not-built in Phase 6 —
the native `.so` bundle + per-platform wheels carry the current distribution
claim) and **the per-language scanner library** (three seeds shipped: the
indentation, heredoc, and matched-delimiter scanners). THIS session builds
(or decisively assesses) both.

Two questions decide it:

1. **The wasm runtime.** Can a grammar bundle carry a `.wasm` in place of (or
   beside) the `.so`, loaded by A through a wasm runtime, with the same
   one-line `Language.load_bundle` surface? Phase 6 probed: NO emscripten
   toolchain in the devenv, NO wasm runtime importable in A (no
   wasmtime/wasmer/pyodide), and the ~1.5–2× wasm perf note. The go/no-go:
   a REAL `.wasm` grammar artifact, built with a real toolchain (emcc via the
   devenv or a downloaded SDK), loaded and parsed through a real runtime in
   A — OR an evidence-backed no-go (the native bundle is enough; wasm's only
   win is portability, at a perf + toolchain + runtime-dependency cost).
2. **The scanner library.** Can the airtight mechanism (scanner=,
   content-addressed cache keying, `ExternalScannerRequiredError`) scale to
   REAL per-language scanners — the canonical copies a real author needs
   (e.g. tree-sitter-python's indentation scanner, tree-sitter-bash's
   heredoc+$'...' scanner, a CSV/comment scanner)? The go/no-go: 1–2 real
   scanners, each with a mini-grammar + corpus tests, shipped as package data
   in the heavy wheel and reachable via `pydantree_sitter_grammar.scanners` — OR the honest
   assessment that the library's value is marginal vs. pointing authors at
   the upstream scanner.c files.

Deliver a **go / go-with-changes / no-go verdict with evidence** for each.
A wasm no-go is NOT architecture-changing (Phase 6 already ruled the native
bundle sufficient for the distribution claim); a scanner-library no-go is a
scope correction, not a design failure. Say so plainly either way.

---

## Context: where we are (do not re-derive these)

- **The consumer seam is proven and committed.** Phase 6 (`.scratch/008-consumer-seam/FINDINGS.md`, verdict GO): the distribution split
  (`pydantree-pydantree_sitter` / `pydantree-pydantree_sitter` light, `pydantree-pydantree_sitter_grammar`
  heavy with the scanner package data), the fresh-venv install boundary, the
  community-schema byte-for-byte exact path (rust/python/markdown/
  markdown-inline), the schema-registry leak fix, Job-2 `.pyi` stubs,
  optional field-mode captures (`?` quantifiers), `capture_kind()` for
  positional-children grammars, and two scanner seeds beyond the indentation
  one (heredoc + matched-delimiter).
- **The bundle layout is 4 files** (grammar.so + node-schema.json +
  tree-sitter.json metadata + a 7-line loader delegating to
  `pydantree_sitter.loader.load_bundle`). `Language.load_bundle(dir)` is the one-line
  consumer. The metadata's `artifact` field names the artifact file
  (default `grammar.so`); the `.so` is loaded via a PyCapsule
  (`pydantree_sitter.loader.load_grammar_so`). A `.wasm` artifact would need the
  metadata to point at it and a runtime-aware loader — the seam's natural
  extension point.
- **The scanner mechanism is airtight.** `pydantree_sitter_grammar.pipeline.build`:
  externals without a scanner raise `ExternalScannerRequiredError` (before
  gcc's link failure); the cache key content-addresses scanner.c; the
  scanners live in `src/pydantree_sitter_grammar/scanners/` with `scanner_for(name)` +
  per-scanner path helpers. The seeds: `indent_scanner.c` (pymini),
  `heredoc_scanner.c` (hmini), `matched_delimiter_scanner.c` (dmini) — each
  with a mini-grammar in `.scratch/008-consumer-seam/` + tests.
- **Two scanner gotchas are documented facts** (Phase 6): the lexer calls
  the scanner mid-whitespace (skip it first), and multiple externals can be
  valid in ONE parser state (the source disambiguates — a `<` is always a
  heredoc START).
- **The devenv venv has no pip; uv is the manager** (devenv.yaml:
  `uv.enable = true`). Verified facts: tree-sitter CLI 0.25.3, bindings
  0.26.0 (ABI 15, MIN_COMPATIBLE 13), gcc 14.2.1, pydantic 2.13.4.
  Editable installs of the four distributions are in the devenv venv; the
  tests resolve `src/` first via `tests/conftest.py` (the hard-link
  editable caveat: NEW files / replaced files need
  `uv pip install -e . -e src/pydantree_sitter -e src/pydantree_sitter -e src/pydantree_sitter_grammar`).

---

## Required reading (in this order — do not skip)

1. **`.scratch/008-consumer-seam/FINDINGS.md`** — the Phase-6 verdict; §3.3
   (the wasm probe — the exact assessed-not-built status and the probe
   evidence `evidence/r3_wasm_probe.txt`); §3.2 (the scanner seeds + the two
   gotchas); §5 (the recommendation that deferred wasm + the scanner library
   to Phase 7). Appendix facts 2, 4, 5, 9.
2. **`.scratch/007-query-distribution/FINDINGS.md`** — Appendix facts 5
   (the indentation scanner's canonical cadence) and 9 (the bundle = one
   artifact + one loading contract).
3. **`.scratch/002-pydantic-treesitter/CONCEPT.md`** — §8 (the distribution
   strategy; pydantree_sitter "a wasm runtime" was in the original pitch), §4.6/4.7
   (external scanners, the build & distribute pipeline).
4. **Code you will extend (skim, then read the parts you touch):**
   - `src/pydantree_sitter/loader.py` — `load_grammar_so` (the PyCapsule load) and
     `load_bundle` (the artifact-name metadata). The wasm twin belongs here
     or beside it.
   - `src/pydantree_sitter/typed.py` — `Language.load_bundle` (the one-line surface).
   - `src/pydantree_sitter_grammar/pipeline.py` — `build`/`compile_parser` (the C build),
     `BuildResult.package` (the bundle), the scanner cache-keying.
   - `src/pydantree_sitter_grammar/schema_tool.py` — `build_community_bundle` (the
     community bundle path — the same `-o`/scanner handling).
   - `src/pydantree_sitter_grammar/scanners/` — the three seeds + the `scanner_for` table.
   - `tests/test_scanners.py`, `tests/test_packaging.py`,
     `tests/test_bundle.py` — the patterns to extend.
   - `.scratch/008-consumer-seam/{pymini,hmini,dmini}.py` — the mini-grammar
     pattern (in `.scratch/007-query-distribution/pymini.py` for pymini).

---

## Scope

### Run A — the wasm runtime (the portability story)

The question is NOT "can we build a wasm grammar" (the CLI + emcc can) but
"does A deserve a wasm runtime dependency?" Build the honest probe:

1. **The toolchain probe.** Get emcc working (the devenv's nixpkgs has
   emscripten; `nix-shell -p emscripten` or a devenv packages addition, OR
   download the emsdk). Document the size/effort of the toolchain in the
   build environment.
2. **The artifact probe.** `tree-sitter generate` + emcc on a real grammar
   (reuse `tests/fixtures/rust`) → a `.wasm` (the tree-sitter CLI's
   `build --wasm` needs emcc; the runtime needs the export table + the
   tree-sitter wasm runtime). Produce a real `.wasm` grammar artifact if the
   toolchain cooperates.
3. **The runtime probe.** Load the `.wasm` in A through a real runtime
   (wasmtime or wasmer Python bindings — the light distribution would gain
   this dependency). The honest test: `Language.load_bundle`-shaped surface
   over the `.wasm` artifact, a real parse, and a perf comparison vs the
   native `.so` (the ~1.5–2× note — measure it over the rust bundle).
4. **The distribution question.** What does a `.wasm` bundle buy: portability
   (no per-platform native build). What does it cost: a runtime dependency
   in the light install, the emscripten toolchain at build time, the perf
   tax. Compare against per-platform wheels (which Phase 6 proved work).

Deliverable: the probe + evidence, and a one-page assessment answering
"is the wasm runtime worth A's dependency budget, or do per-platform native
wheels carry the portability story?" A genuine go means a working
`.wasm`-bundle load path with a runtime + a test; a no-go means the evidence
(real artifact + real perf numbers) + a clear "not worth it" statement.

### Run B — the scanner library (per-language copies)

1. **Pick 1–2 real scanners** the library genuinely needs — e.g. the
   tree-sitter-python indentation scanner (INDENT/DEDENT on top of
   NEWLINE/comment handling — the real Python semantics, not pymini's
   simplified ones), or a tree-sitter-bash-style heredoc (the multi-heredoc
   case: several pending delimiters, `<<-` indent-stripped), or a simple
   comment/string scanner. The sources are upstream (tree-sitter-python's
   `src/scanner.c`, tree-sitter-bash's `src/scanner.c` — READ them, adapt
   the canonical mechanism, do NOT copy wholesale).
2. **The mechanism contract** (each must satisfy): lives in
   `src/pydantree_sitter_grammar/scanners/`, registered in `scanner_for()`, ships as
   package data (the heavy wheel — verify with a wheel build), with a
   mini-grammar (a `.scratch` module) + corpus tests (the `Corpus` harness)
   + a parse-error test. The two Phase-6 gotchas (mid-whitespace scans,
   multiple-externals-in-one-state) are facts — design for them.
3. **The honest scope line.** If a seed balloons (e.g. the real Python
   scanner's multi-context state), land the assessment (what it would take,
   who it serves) and move on — the library's value is the MECHANISM being
   reusable, not a full replication of every upstream scanner.

### Out of scope — say no to these (politely)

- **New Product A/B surface beyond the named items.** No new annotation
  vocabulary, no grammar-authoring features, no corpus gold-plating, no
  performance work beyond the wasm probe's measurement, no touching
  `src/pydantree` (the deprecated wrapper).
- **The generator rewrite, C-runtime work, or the regex-subset validator.**
- **Re-opening the Phase-6 consumer-seam verdicts** (they're proven; the
  residuals there — CLI-version drift, the name-based kind inference, the
  wrapper-field list case — are documented-and-moved-on).

---

## Environment setup (do this first)

1. `devenv shell` — works (Phase 0 fixed). If it isn't, tell the user
   immediately.
2. **Verified facts (don't re-derive):** tree-sitter CLI 0.25.3, bindings
   0.26.0 (LANGUAGE_VERSION=15, MIN_COMPATIBLE=13 — ABI 13–15 all load),
   gcc 14.2.1, pydantic 2.13.4. The devenv venv has NO pip; uv is the
   manager. Editable installs: `uv pip install -e . -e src/pydantree_sitter -e
   src/pydantree_sitter -e src/pydantree_sitter_grammar` (re-run after adding NEW files — the
   hard-link editable staleness caveat; `tests/conftest.py` makes the suite
   resolve `src/` first regardless).
3. **Fixtures you will reuse:** `tests/fixtures/rust/` (a real grammar with
   the byte-for-byte oracle), `tests/fixtures/markdown*/`,
   `.scratch/008-consumer-seam/{hmini,dmini}.py` (the scanner mini-grammar
   pattern), `.scratch/007-query-distribution/pymini.py` (the indentation
   seed). The community bundle path: `pydantree_sitter_grammar.schema_tool.build_community_bundle`.
4. **Baseline:** `python -m pytest tests/` should be green (162 at the end
   of Phase 6). Capture the count before you start.

---

## Working agreement

- **Commit after each meaningful step**, e.g.:
  `phase7: wasm probe — emcc via <route>, a real .wasm rust artifact, <runtime> load + parse, perf native-vs-wasm <ratio> (assess/land)`,
  `pydantree_sitter_grammar: scanner library — the <language> scanner (adapted from upstream <file>) + mini-grammar + corpus tests; scanner_for() + package-data check`,
  `phase7: findings — the wasm + scanner-library verdict (go / go-with-changes / no-go), evidence captured`.
- **Write findings as you go** into `.scratch/009-phase7/FINDINGS.md`. The
  code is the foundation; the findings are the deliverable.
- **Don't gold-plate.** 80%-done steps get a note and a move-on.
- **Don't fake the primary experiments.** Run A's wasm artifact + runtime
  and Run B's scanners must be real and hand-verified. Save raw outputs
  verbatim under `.scratch/009-phase7/evidence/`.
- **Ask before expanding scope** beyond this brief.

---

## Deliverables (end of session)

1. Run A: the wasm probe (toolchain route + sizes, a real `.wasm` artifact
   OR the decisive blocker with evidence, the runtime load + a real parse,
   the perf measurement native-vs-wasm) — landed (a working wasm-bundle load
   path + test) OR assessed (a one-page no-go with evidence).
2. Run B: 1–2 real per-language scanners (adapted, mechanism-conformant,
   mini-grammar + corpus tests, `scanner_for()` registered, package-data
   verified in the heavy wheel) OR the honest assessment.
3. `.scratch/009-phase7/FINDINGS.md` answering at minimum:
   - Does A deserve a wasm runtime dependency, or do per-platform native
     wheels carry the portability story? What is the real perf ratio, and
     what does the runtime cost the light install?
   - Does the scanner library scale to real per-language copies, and is the
     mechanism (scanner=, cache keying, the escape-hatch error) reusable as
     pitched? Where does it leak over a real upstream scanner?
   - Re-assess §11.2/11.3 (external-scanner frequency, toolchain packaging
     for B) and §11.5 (wasm perf) from THIS side.
   - **Recommendation:** go / go-with-changes / no-go on each run, and the
     single most important next step for the project (real-user adoption?
     more real grammars? the wasm story? stop?).
4. Everything committed and pushed.

## Appendix — durable facts to build on (all verified in prior phases)

1. The bundle is one artifact + one loading contract: `pydantree_sitter.loader` is the
   shared loader; `Language.load_bundle(dir)` is the one-line consumer; the
   metadata's `artifact` field names the artifact file (default
   `grammar.so`).
2. The `.so` is loaded via a PyCapsule named `"tree-sitter.Language"`; the
   export symbol is `tree_sitter_<name>` (recorded in the bundle metadata —
   the bundle renames the file to `grammar.so`). Integer-pointer loading is
   deprecated in 0.26.
3. The exact-path node-schema derivation is byte-for-byte with the CLI's
   node-types.json over rust, python, markdown, and markdown-inline
   (hermetic tests in `tests/test_schema.py`).
4. The indentation scanner's canonical cadence: mark_end before the loop,
   the newline SKIPPED (zero-width NEWLINE), comment-lines count as
   newlines, EOF flushes DEDENTs, blocks are `INDENT statements DEDENT`.
5. The scanner mechanism: externals without a scanner →
   `ExternalScannerRequiredError`; the cache key content-addresses scanner.c;
   the two gotchas (mid-whitespace scans, multiple-externals-in-one-state).
6. The dev flow: no pip, uv only; editable hard-links (reinstall after new
   files); `tests/conftest.py` resolves `src/` first.
7. ABI: bindings 0.26.0 accepts 13–15; the tree-sitter CLI's `generate`
   needs a `tree-sitter.json` with metadata to emit ABI 15 (else ABI 14 —
   still loads).
