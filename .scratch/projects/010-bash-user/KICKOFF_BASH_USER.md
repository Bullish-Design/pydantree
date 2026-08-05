# KICKOFF — Phase 8: the bash real-user adoption pass (the "hundreds of
# grammars" claim, from a user's seat, over a grammar we've never touched)

> Copy the whole contents of this file into a fresh session working in this
> repo. This is the exploration prompt for Phase 8 — the first REAL-user
> adoption pass, per the unanimous Phase-6/7 recommendation ("the single most
> important next step: real-user adoption, not more machinery"). The
> consumer seam is PROVEN (Phase-6 GO); what it needs now is a user. Since we
> have no literal user, the best surrogate is a real extraction task over a
> real grammar we don't own and have never touched, run end-to-end through
> the LIGHT install exactly as a user would — and a copyable example they can
> run first. Findings go in `.scratch/010-bash-user/FINDINGS.md`.

---

## Mission

Validate the seam from a real user's seat over **tree-sitter-bash 0.25.1**
(the grammar, not our bashmini mini-language — bash is the thing we consume,
we do NOT author it). The go/no-go: **does the consumer story hold over a
fifth, genuinely different-shaped grammar, and does a real user hit anything
we didn't know about?** Concretely:

1. **Acquire + derive.** Fetch the real bash grammar SOURCE (v0.25.1:
   `src/grammar.json` + `src/scanner.c` + `tree_sitter/` headers — the PyPI
   sdist ships only the COMPILED parser.c/scanner.c, so the source comes from
   GitHub, exactly like rust in Phase 6) and vendor it under
   `tests/fixtures/bash/` for hermetic tests (include the repo's own
   checked-in `node-types.json` as the oracle). Derive the schema with
   `tsgrammar.schema_tool.derive_schema_for_dir` and check it against the
   CLI's fresh node-types.json (the grammar-ownership seam over a grammar
   with ~30 external tokens and a big multi-context scanner).
2. **Consume through the light install, in BOTH real-user shapes.** The
   bundle shape (source → `build_community_bundle` → `Language.load_bundle`)
   and — the stronger "hundreds of grammars" shape — the **wheel shape**
   (`uv pip install tree-sitter-bash` from a real index → `tree_sitter_bash.
   language()` + the schema bound explicitly). Both in a FRESH venv with
   only the light wheels (`pydantree-tscore`, `pydantree-tsquery`), both
   B-free (`import tsgrammar` fails), both byte-identical to the in-repo
   results.
3. **The extraction task.** Hand-write the ground truth BEFORE the models
   (the phase convention), then extract from real shell scripts: function
   definitions (both `foo() { … }` and `function foo { … }` forms), top-level
   variable assignments (name + value), and heredoc usage (delimiter + body).
   Use the real A surface only: `M` paths, `capture`/`capture_kind`,
   optional captures, record mode where it fits, `validate_with`, stubs.
4. **The deliverable is a USER artifact, not machinery.** Commit a copyable
   example (`examples/bash-extract/`) a new user runs first — install light
   wheels, run the extraction, see typed rows — plus the **friction
   catalog**: everything a real user would stumble on, in one honest list.

The verdict at the end: is the seam ready for real users (go), or does the
bash pass surface a class of problem that must be fixed first (go-with-changes)?

---

## Context: where we are (do not re-derive)

- **The consumer seam is proven.** Phase 6 (`.scratch/008-consumer-seam/`,
  verdict GO): the light install boundary (tscore/tsquery only, B-free),
  the bundle contract, and the grammar-ownership boundary — the schema
  derivation is byte-for-byte with the CLI's node-types.json over FOUR real
  grammars (rust, python, markdown, markdown-inline) and the community tool
  path is byte-for-byte over REAL rust (182 rules, 11 externals). Phase 7
  added: wasm assessed-not-worth-it (seam landed), and two more scanner
  seeds. The rust Run-2 pattern (`.scratch/008-consumer-seam/experiment_run2.py`
  + `consumer_rust.py`) is the exact template for the bash pass.
- **The wheel-consumer shape is already exercised once.** Phase 5's
  `.scratch/007-tsquery-distribution/consumer_community.py` consumed the
  json grammar from the `tree_sitter_json` WHEEL with a derived schema,
  B-free. Bash's wheel shape follows the same pattern.
- **The dev flow changed (Phase-8 pre-work, committed): the venv is managed
  by `uv sync`.** There is NO `uv pip install -e` ritual anymore. The devenv
  runs `uv sync --frozen --no-install-workspace --all-extras` at shell entry
  (checksum-cached), and a `_pydantree_src.pth` makes every process resolve
  tscore/tsquery/tsgrammar straight from `src/` — edits are live
  immediately, staleness is impossible. `uv lock` after dependency changes.
  The three src/* packages are NEVER installed into the dev venv.
- **The scanner synergy is a READ, not a task.** Phase 7 adapted
  tree-sitter-bash's heredoc mechanism into our `bash_heredoc_scanner.c`
  (bashmini). For THIS phase, read the upstream `src/scanner.c` to compare
  with our adaptation and to know what the schema's external tokens mean —
  but bash is consumed, not authored.
- **Agent skills + docs exist.** `.agents/skills/` ships four
  Agent-Skills-standard skills that load into pi automatically
  (pydantree-dev, pydantree-grammar, pydantree-extraction,
  pydantree-scanners). `docs/` has the architecture, development workflow,
  user guide, and scanner-library docs. Use them.

---

## Required reading (in this order — do not skip)

1. **`docs/development.md`** — §1 especially: the uv-sync dev flow, the
   `_pydantree_src.pth`, `uv lock`, tests, evidence/commit conventions.
2. **`docs/architecture.md`** — §2 (packages), §3 (the three seams), §5
   (the schema bridge), §7 (module map), §8 (durable facts).
3. **`docs/user-guide.md`** — §2 (the full A surface) and §4 (the community
   flows, end to end).
4. **`.scratch/008-consumer-seam/FINDINGS.md`** §2 + `experiment_run2.py` +
   `consumer_rust.py` — the rust community-seam pattern to replicate.
5. **`.scratch/007-tsquery-distribution/consumer_community.py`** — the wheel
   shape (json via `tree_sitter_json` + derived schema, B-free).
6. **`.scratch/009-phase7/FINDINGS.md`** — the most recent verdicts (wasm,
   scanner library) and the §4 recommendation this phase executes.
7. **`.scratch/002-pydantic-treesitter/CONCEPT.md`** §8 (distribution) — the
   design the consumer shapes implement.

## Code you will touch (skim, then read the parts you use)

- `src/tsgrammar/schema_tool.py` — `derive_schema_for_dir`,
  `build_community_bundle` (unchanged; you CALL them).
- `src/tsquery/typed.py` — the A surface (unchanged; you USE it).
- `tests/conftest.py`, `tests/test_packaging.py` (the fresh-venv pattern),
  `tests/fixtures/rust/` (the vendoring pattern to copy for bash).
- `examples/bash-extract/` — the NEW user artifact you author.

---

## Scope

### Run 1 — acquire + derive (the grammar-ownership seam over bash)

1. Fetch the tree-sitter-bash **v0.25.1 source** from GitHub
   (`tree-sitter/tree-sitter-bash` tag v0.25.1): `src/grammar.json`,
   `src/scanner.c`, the `tree_sitter/` headers, and the checked-in
   `src/node-types.json` (the oracle). The PyPI sdist does NOT ship the
   grammar source — document this acquisition honestly (same as rust).
2. Vendor under `tests/fixtures/bash/` (hermetic): grammar.json, scanner.c,
   tree_sitter/, node-types.json (oracle). Keep the repo layout identical to
   `tests/fixtures/rust/`.
3. `derive_schema_for_dir(tests/fixtures/bash)` → node-schema; check the
   derived kinds **byte-for-byte** against the CLI's fresh node-types.json
   AND against the vendored oracle. Note the externals (~30 tokens: the
   heredoc trio, STRING_START/CONTENT/END, COMMENT, the expansion tokens…)
   and what the big multi-context scanner means for the schema (named
   externals? hidden rules? supertypes?). A 38-byte-style drift from the
   oracle (a newer CLI) is upstream churn, not our derivation — document it.

### Run 2 — the light-install consumer, BOTH real-user shapes

1. **Bundle shape** (mirror the rust run): `build_community_bundle` → a
   4-file bundle; a FRESH venv (`uv venv`) with ONLY
   `pydantree-tscore` + `pydantree-tsquery` (built wheels); consumer does
   `Language.load_bundle(dir)` and extracts — `import tsgrammar` fails.
2. **Wheel shape** (the true "hundreds of grammars" shape): in the fresh
   venv, `uv pip install tree-sitter-bash` from the real index; consumer
   binds the derived schema to `tree_sitter_bash.language()` and extracts.
3. Both consumers assert the B-free boundary and print results; the outputs
   must be **byte-identical** to the in-repo (B importable) run — the
   A-surface comparison from Phase 5/6.

### Run 3 — the extraction task (hand truth BEFORE the models)

Pick real shell scripts (a couple of small, hand-authored ones + at least
one REAL repo script, e.g. a real Makefile-style or install script from the
repo itself if it exists — otherwise hand-author realistic ones). Ground
truth written on paper first, from bash's semantics:

- **function definitions**: both `name() { … }` and `function name { … }`;
  capture the name and the position (line). Watch how bash nests the body
  (function_definition → command → block) and whether the name is a field or
  positional — `capture_kind` may be needed.
- **top-level variable assignments**: `VAR=value` (no export/prefixes);
  name + value, at the top level only (not inside functions).
- **heredoc usage**: `<<EOF`/`<<-EOF`/`<<'EOF'` — the delimiter and the body
  content.

Exercise the real A surface deliberately: optional captures (a function
without a body? unlikely — use `return_type`-style optional where bash has
one), `validate_with` (the checks active), `compiled_source` for the derived
.scm diff, and `stubs` over the bash schema. Document which surface features
bash's shape needed (or didn't) — that IS a finding.

### Run 4 — the user artifact + the friction catalog

1. **The example** (`examples/bash-extract/`): a copyable end-to-end —
   `extract.py` (the models + extraction over a sample script, prints typed
   rows) + a README that a new user follows: install the light wheels (+
   `tree-sitter-bash`), run it, see rows. It must run from the dev venv AND
   be documented for the fresh-venv shape. This is the "users start here"
   artifact — keep it small and honest, not a showcase.
2. **The friction catalog** (the core finding): everything a real user would
   hit, in one list — name-based kind inference residue (does bash trigger
   it?), the field-mode-list wrapper case, optional captures, record-mode
   fit over bash's shape, externals in the schema, wheel-vs-bundle
   differences, any schema derivation surprises (hidden rules, aliases,
   supertypes), the stubs quality over bash. Each entry: what happened,
   whether it's a real gap or a documented-and-moved-on residual, and the
   escape hatch.

### Out of scope — say no to these

- **Authoring bash** (the grammar is consumed, not authored; no new
  tsgrammar features, no scanner work on the real bash grammar).
- **Publishing** (a separate follow-up: the pydantree-branded distributions
  are resolved-in-name but unrehearsed; note it in the recommendation, don't
  do it here).
- **New A/B surface**, corpus gold-plating, perf work, touching
  `src/pydantree` (the deprecated wrapper), re-opening the Phase-6/7
  verdicts.

---

## Environment setup (do this first)

1. `devenv shell` — works. If it isn't, tell the user immediately.
2. **The venv is uv-sync-managed — there is NO editable-install ritual.**
   `devenv shell` runs `uv sync` automatically (checksum-cached); the venv
   resolves `src/` via `_pydantree_src.pth` (edits live immediately).
   `uv lock` only after changing dependencies in pyproject.toml. Do NOT run
   `uv pip install -e …` (it is gone from the flow; the packages resolve
   from src/ regardless).
3. **Verified facts (don't re-derive):** tree-sitter CLI 0.25.3, bindings
   0.26.0 (ABI 13–15 load), gcc 14.2.1, pydantic 2.13.4, Python 3.13.
   tree-sitter-bash **0.25.1** on PyPI (wheel `cp310-abi3-manylinux*`;
   the sdist ships only the COMPILED parser.c/scanner.c — the grammar source
   comes from GitHub tag `v0.25.1`, like rust).
4. **Baseline:** `python -m pytest tests/` = **170 green + 1 skipped**.
   Capture the count before you start.
5. **Fixtures you will reuse:** `tests/fixtures/rust/` (the vendoring
   pattern + oracle check), `tests/test_packaging.py` (the fresh-venv +
   wheelhouse pattern), `.scratch/008-consumer-seam/{experiment_run2,
   consumer_rust}.py`, `.scratch/007-tsquery-distribution/consumer_community.py`.

---

## Working agreement

- **Commit after each meaningful step**, e.g.:
  `phase8: bash acquisition + schema — vendored tests/fixtures/bash v0.25.1, schema derived byte-for-byte vs the CLI (N kinds, ~30 externals)`,
  `phase8: the light-install bash consumer — bundle shape + wheel shape, B-free, byte-identical (evidence r8_*)`,
  `phase8: the extraction task — functions/assignments/heredocs vs hand truth, validate_with + stubs active`,
  `phase8: examples/bash-extract + the friction catalog; findings — the seam is ready for users (go/go-with-changes), next: publishing rehearsal`,
  `phase8: findings — the adoption verdict + friction catalog, evidence captured`.
- **Write findings as you go** into `.scratch/010-bash-user/FINDINGS.md`.
  The example is the artifact; the friction catalog is the finding.
- **Don't gold-plate.** 80%-done steps get a note and a move-on. The example
  is a small honest artifact, not a showcase.
- **Don't fake the primary experiments.** Run 1 (derive), Run 2 (both
  consumer shapes B-free), and Run 3 (ground truth) must be real and
  hand-verified. Save raw outputs verbatim under
  `.scratch/010-bash-user/evidence/` (`r8_*`).
- **Ask before expanding scope** beyond this brief.

---

## Deliverables (end of session)

1. **Run 1:** `tests/fixtures/bash/` vendored (v0.25.1, hermetic, oracle
   included); the derived schema byte-for-byte with the CLI's fresh
   node-types.json (or the exact delta + why — upstream churn only).
2. **Run 2:** the bash consumer working through the LIGHT install in BOTH
   shapes (bundle + wheel), B-free (`import tsgrammar` fails), outputs
   byte-identical to the in-repo run. Evidence under `evidence/r8_*`.
3. **Run 3:** the extraction task — hand truth, models, `validate_with`
   active, rows matching ground truth. Note which A-surface features bash's
   shape actually needed.
4. **Run 4:** `examples/bash-extract/` (copyable, documented for the
   fresh-venv shape) + the **friction catalog** in FINDINGS.
5. **`.scratch/010-bash-user/FINDINGS.md`** answering at minimum:
   - Does the "hundreds of grammars" claim hold over a fifth, different-
     shaped grammar with ~30 externals and a multi-context scanner? Where
     did the wheel shape and the bundle shape differ for a real user?
   - The friction catalog: every real-user stumble, with its escape hatch,
     and which residuals (name inference, wrapper-field lists, …) bash's
     shape actually triggered.
   - **Recommendation:** go / go-with-changes / no-go on "the seam is ready
     for real users," and the single most important next step — my money is
     on the **publishing rehearsal** (Phase 6's "installable-by-name" blocker,
     resolved-in-name but never rehearsed) — but say what you see.
6. Everything committed and pushed (`origin/main`).

## Appendix — durable facts (verified in prior phases; build on these)

1. The bundle is one artifact + one loading contract: `tscore.loader` is the
   shared loader; `Language.load_bundle(dir)` is the one-line consumer; the
   metadata's `artifact` field names the artifact file (default
   `grammar.so`); the `.so` loads via a PyCapsule named `"tree-sitter.Language"`
   (export symbol `tree_sitter_<name>`).
2. The dev flow (Phase-8 pre-work, CURRENT): devenv manages the venv with
   `uv sync` — uv workspace in root `pyproject.toml`
   (`[tool.uv.workspace] members = ["src/tscore", "src/tsquery",
   "src/tsgrammar"]`), `--no-install-workspace`, `uv.lock` committed;
   `_pydantree_src.pth` resolves tscore/tsquery/tsgrammar from `src/` (edits
   live, no staleness); `uv lock` after dependency changes (sync is
   `--frozen`). No pip, no `uv pip install -e` ritual.
3. The exact-path node-schema derivation is byte-for-byte with the CLI's
   node-types.json over rust, python, markdown, markdown-inline (hermetic
   tests in `tests/test_schema.py`); the community tool path
   (`tsgrammar.schema_tool`) derives from the installed CLI's own byproduct,
   so it tracks the CLI by construction.
4. The rust community-seam pattern (Phase 6): sdist ships only compiled
   parser.c/scanner.c → source vendored from GitHub under
   `tests/fixtures/rust/` (repo's own node-types.json as oracle) →
   `build_community_bundle` → B-free consumer extracts a real task vs hand
   truth, checks active.
5. ABI: bindings 0.26.0 accepts 13–15; the CLI's `generate` needs a
   `tree-sitter.json` with metadata for ABI 15 (the pipeline writes it).
6. External-scanner facts: a grammar with externals needs `scanner=` or
   raises `ExternalScannerRequiredError` before gcc's link failure; the cache
   key content-addresses scanner.c; the two gotchas (mid-whitespace scans,
   multiple externals valid in one state). tree-sitter-bash's scanner is the
   multi-context upstream our `bash_heredoc_scanner.c` was adapted from.
7. B-free boundary: consumer processes strip the `src/` path and block
   `tsgrammar` at the meta-path-finder level (the Phase-6 consumer
   `sitecustomize.py`) — the boundary is enforced by construction.
8. Fresh-venv mechanics: `uv venv` + `uv pip install --find-links <wheelhouse>`
   for the light wheels; `import tsgrammar` fails in the light install (the
   seam does not leak).
9. The wheels: pydantree-tscore / pydantree-tsquery (light) /
   pydantree-tsgrammar (heavy, carries the scanner package data); import
   packages stay tscore/tsquery/tsgrammar.
