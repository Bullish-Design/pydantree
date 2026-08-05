# KICKOFF — Phase 9: the real-world Nix adoption pass (the "your own
# devenv.nix fleet" example, over a sixth grammar we've never touched)

> Copy the whole contents of this file into a fresh session working in this
> repo. This is the exploration prompt for Phase 9 — the second REAL-user
> adoption pass, per the Phase-8 verdict (GO) and the user's direction:
> no publishing yet; the next consumer exercise is a real-world example
> over Nix, built from the user's OWN fleet of devenv.nix configs. Phase 8
> proved the seam over bash (a fifth, different-shaped grammar); Phase 9
> proves it over the Nix LANGUAGE (a sixth, different-shaped grammar) with a
> corpus that is entirely the user's real configs — the strongest real-user
> evidence yet. The use case is a real tool: the devenv fleet inventory —
> typed rows per repo (packages, env vars, scripts, tasks, enabled
> switches, enterShell), aggregated across 52 repos. Findings go in
> `.scratch/011-nix-example/FINDINGS.md`.

---

## Mission

Validate the seam from a real user's seat over **tree-sitter-nix**
(nix-community/tree-sitter-nix — the Nix language grammar; Nix is consumed,
we do NOT author it), with the corpus being the user's OWN real
`devenv.nix` configs across their fleet. The go/no-go: **does the consumer
story hold over a sixth grammar whose shape is different again (attrsets,
`${...}` interpolation, `''...''` multiline strings, `let ... in`,
function args), and does a pass over real fleet configs surface anything the
bash pass didn't?** Concretely:

1. **Acquire + derive.** Fetch the real Nix grammar SOURCE (the
   `nix-community/tree-sitter-nix` repo — MIT, maintainer @cstrahan — at
   the version that actually matches what the consumer's wheel parses with,
   see the acquisition note below; `src/grammar.json` + `src/scanner.c` +
   `tree_sitter/` headers + the repo's checked-in `src/node-types.json` as
   the oracle) and vendor it under `tests/fixtures/nix/`. Derive the schema
   with `tsgrammar.schema_tool.derive_schema_for_dir` and check it
   byte-for-byte against the CLI's fresh node-types.json AND the vendored
   oracle. **Resolve the wheel-consistency question FIRST** (documented
   below): the PyPI wheel is `tree-sitter-nix` 0.1.0 but the grammar repo's
   latest tag is v0.3.0 — determine which grammar.json the wheel's compiled
   parser actually corresponds to, so the wheel-shape schema is truthful.
2. **Consume through the light install, in BOTH real-user shapes** (the
   Phase-8 pattern): bundle shape (`build_community_bundle` →
   `Language.load_bundle`) and wheel shape (`uv pip install tree-sitter-nix`
   from the real index → `tree_sitter_nix.language()` + the schema bound
   explicitly). Both in a FRESH venv with only the light wheels, both
   B-free (`import tsgrammar` fails), both byte-identical to the in-repo
   results.
3. **The extraction task — the devenv fleet inventory.** Hand-write the
   ground truth BEFORE the models (the phase convention), then extract from
   the user's REAL `devenv.nix` files (a representative subset vendored
   under `tests/fixtures/nix/fleet/`): packages (the `pkgs.*` refs),
   `env.NAME = value`, `scripts.<name>.exec` and `tasks.<name>.exec`
   (multiline bodies — pydantree's own task nests a bash heredoc INSIDE a
   nix multiline string), and the enabled switches (all `attr.path...enable
   = true` dotted paths — the "what's switched on" inventory). Aggregate
   across the fleet with the repo as a field. Also probe **record mode**
   over nix's attrset shape (Phase 8: record mode did NOT fit bash — nix's
   `{ key = value; }` attrsets are the record-mode shape's natural
   candidate; whether it fits is a finding either way).
4. **The deliverable is a USER artifact, not machinery.** Commit a copyable
   example (`examples/devenv-extract/`) a new user runs first — install
   light wheels + `tree-sitter-nix`, run the fleet inventory, see typed
   rows — plus the **friction catalog**: every real-user stumble over nix's
   shape, in one honest list, with the Phase-8 catalog as the baseline.

The verdict at the end: is the seam ready for real users over a sixth
grammar (go), or does the nix pass surface a class of problem that must be
fixed first (go-with-changes)?

---

## Context: where we are (do not re-derive)

- **Phase 8 (`.scratch/010-bash-user/`, verdict GO) is the template.** The
  bash pass proved: the "hundreds of grammars" claim over a fifth
  different-shaped grammar (29 externals, positional heredoc children,
  structural fields), both light-install shapes B-free and byte-identical,
  a hand-truth extraction task matching everywhere, a copyable example
  verified in a fresh venv, and a 16-entry friction catalog. **Two real
  user surprises were FIXED in Phase 8** — these are now pinned surface
  facts, do not regress them:
  1. `capture_kind` was missing from `_field_is_query_optional`'s marker
     tuple → required capture_kind fields wrongly emitted `?`; fixed +
     regression test (`test_capture_kind_optionality_quantifies_only_optional_fields`).
  2. Mixed field + positional captures: the emitted query's child order
     follows model-field order and must match the CST order (bash: the
     `descriptor` field precedes the positional heredoc trio); a wrong
     order is an "Impossible pattern" QueryError — documented, workaround =
     field ordering.
  The Phase-8 consumer (`consumer_bash.py`), experiment scripts
  (`experiment_run1/2/3.py`), and the example (`examples/bash-extract/`)
  are the exact pattern to replicate. **The Phase-8 residual catalog is the
  baseline**: which entries does nix trigger (record mode? the ordering
  trap? name inference? wrapper-field lists? the wheel-version issue?)? —
  that comparison IS a finding.
- **Publishing is DEFERRED by the user.** Phase 8's recommendation (the
  publishing rehearsal — installable-by-name, never rehearsed) stands as
  the NEXT step, but THIS session must NOT publish, must NOT build
  wheelhouses for publishing, and must NOT touch anything publish-related
  beyond the existing test_packaging pattern. Say no to publishing
  rehearsal work here.
- **The corpus is the user's own fleet.** 52 repos under
  `~/Documents/Projects/*/devenv.nix` (verified; the list is in the
  Appendix). Fleet stats (verified by grep): 30 repos with `packages = [`
  lists, 24 with `env.KEY =`, 28 with `scripts.*`, 3 with `tasks` blocks
  (pydantree's own nests a bash heredoc in a nix multiline string), 42 with
  `languages.*`, 47 with `.enable = true`, 38 with `''...''` multiline
  strings, 18 with `services.*`. Sizes range 8 lines (mypi-agent) to 526
  (flora). This is a real fleet with real variety — the strongest real-user
  corpus the project has ever had.
- **The dev flow is unchanged (uv-sync).** `devenv shell` runs `uv sync
  --frozen --no-install-workspace --all-extras`; `_pydantree_src.pth`
  resolves tscore/tsquery/tsgrammar straight from `src/`; `uv lock` after
  dependency changes. No `uv pip install -e` ritual.
- **Agent skills + docs exist.** `.agents/skills/` (pydantree-dev,
  pydantree-grammar, pydantree-extraction, pydantree-scanners), `docs/`.
  Use them.

---

## Required reading (in this order — do not skip)

1. **`.scratch/010-bash-user/FINDINGS.md`** — the Phase-8 verdict, the
   friction catalog (the baseline for Phase 9's catalog), the two fixes,
   the evidence list. Read it fully.
2. **`.scratch/010-bash-user/experiment_run2.py` + `consumer_bash.py`** —
   the exact consumer/experiment pattern to replicate (both shapes, B-free,
   byte-identical).
3. **`examples/bash-extract/`** — the artifact pattern: extract.py + README
   + node-schema.json + corpus + ground_truth.json, self-checking, verified
   in a fresh venv.
4. **`docs/development.md`** (§1 the uv-sync flow, §3 evidence discipline),
   **`docs/architecture.md`** (§2 packages, §3 seams, §5 schema bridge, §7
   module map), **`docs/user-guide.md`** (§2 the full A surface, §4
   community flows).
5. **`.scratch/008-consumer-seam/FINDINGS.md`** §2 + §3.5 — the rust
   community-seam pattern and the residuals Phase 9 re-assesses.
6. **`.agents/skills/pydantree-extraction/SKILL.md`** — the extraction
   surface (captures, markers, record mode, validate_with, stubs) — the
   surface this phase exercises over nix.

---

## Code you will touch (skim, then read the parts you use)

- `src/tsgrammar/schema_tool.py` — `derive_schema_for_dir`,
  `build_community_bundle` (unchanged; you CALL them).
- `src/tsquery/typed.py` — the A surface (unchanged; you USE it). Pay
  attention to `_derive_field`/`_derive_record` and the Phase-8 fixes.
- `tests/test_bundle.py`, `tests/fixtures/bash/`, `tests/fixtures/rust/` —
  the vendoring + test patterns to copy for nix.
- `examples/devenv-extract/` — the NEW user artifact you author.

---

## Scope

### Run 1 — acquire + derive (the grammar-ownership seam over nix)

1. **Acquisition.** The grammar is **nix-community/tree-sitter-nix**
   (GitHub, MIT, maintainer @cstrahan, actively maintained; latest tag
   **v0.3.0**). Source layout: `src/grammar.json` (~46 KB),
   `src/scanner.c` (~7.6 KB), `src/tree_sitter/` headers, checked-in
   `src/node-types.json` (~40 KB, the oracle). Vendor under
   `tests/fixtures/nix/` keeping the rust/bash fixture layout (grammar.json,
   scanner.c, tree_sitter/, node-types.json at the fixture root — NOT the
   compiled parser.c).
2. **The wheel-consistency question (resolve FIRST, honestly).** The PyPI
   wheel **`tree-sitter-nix` 0.1.0** ships full platform wheels (including
   manylinux x86_64 + aarch64) + an sdist that ships only the COMPILED
   parser.c/scanner.c (the standard pattern). Its metadata homepage points
   at a NONEXISTENT `tree-sitter/tree-sitter-nix` — provenance is murky,
   and 0.1.0 is NOT the repo's v0.3.0. For the wheel shape to be truthful,
   the derived schema must match the wheel's compiled parser. Determine
   which grammar.json the wheel corresponds to (diff the sdist's parser.c
   against repo history, or — pragmatically — parse a probe corpus with
   both the wheel's language and our v0.3.0-built grammar and compare
   trees). Document the decision in FINDINGS; if the wheel lags the source,
   either derive the schema from the matching commit or document the delta
   as an ecosystem fact (a stale wheel is a REAL user friction — candidate
   catalog entry). The bundle shape is unambiguous: v0.3.0 source → schema +
   parser, consistent.
3. **Derive.** `derive_schema_for_dir(tests/fixtures/nix)` → node-schema;
   byte-for-byte vs the CLI's FRESH node-types.json AND vs the vendored
   oracle (any delta = upstream churn, documented — bash was 0 bytes, rust
   was 38). Note nix's shape for the schema: does the grammar declare
   externals (a 7.6 KB scanner suggests something — interpolation,
   indentation?)? Fields? Hidden rules? Supertypes? GLR conflicts at
   generate time (build_community_bundle runs the CLI — a GLR grammar still
   generates; document if so)? The schema shape over nix (kinds count,
   named vs anonymous, externals in/out of node-types) IS a Run-1
   deliverable.

### Run 2 — the light-install consumer, BOTH real-user shapes

Mirror `experiment_run2.py` exactly:
1. Build the light wheels (tscore + tsquery), fresh venv with ONLY those +
   `tree-sitter-nix` from the real index.
2. Bundle shape: `build_community_bundle(tests/fixtures/nix)` → the 4-file
   bundle; in-repo run (B importable) + fresh-venv run (B-free,
   `Language.load_bundle`).
3. Wheel shape: fresh-venv run (`tree_sitter_nix.language()` + the derived
   schema bound explicitly; B-free).
4. All three extraction payloads byte-identical; `import tsgrammar` fails
   in the fresh venv; the wheel's installed version recorded. Evidence
   `r9_r2_*`. If the wheel's parser provably diverges from the v0.3.0
   source (Run-1 resolution), the byte-identical claim is honestly
   qualified (document which runs compared what).

### Run 3 — the fleet inventory extraction task (hand truth BEFORE the models)

1. **Corpus.** Vendor a representative subset of the user's REAL
   `devenv.nix` files under `tests/fixtures/nix/fleet/` — pick ~6–8 with
   variety and coverage of every task: small (mypi-agent 8 lines),
   medium (pydantree 85 — the heredoc task), large (flora 526),
   plus 2–3 more (fsdantic 250, nixvim 240, structured-agents-v2 221, or
   your pick). **Review each vendored file for sensitive content before
   committing** (some configs reference secrets/paths — sanitize or
   choose others; the user owns these files, but the fixture is committed
   to the repo). Record provenance (repo + path + commit) in the fixture.
2. **Hand truth on paper FIRST**, from nix semantics, per file AND
   aggregated across the fleet:
   - **packages** — every `pkgs.<name>` (and bare `<name>`) package ref
     inside `packages = [ ... ]` lists: name + line (+ repo).
   - **env** — `env.NAME = value`: name + value + line (values are strings,
     often with `${...}` interpolation — raw node text).
   - **scripts + tasks** — `scripts.<name>.exec = ''...''` and
     `tasks.<name>.exec = ''...''`: name + the multiline body + line. The
     bodies are real shell (pydantree's task nests a bash heredoc INSIDE
     the nix multiline string — how does the grammar model that?).
   - **enabled switches** — every dotted attr path ending `.enable = true`
     (e.g. `languages.python.enable`, `languages.python.uv.enable`,
     `services.postgres.enable`): the full dotted path + line (+ repo) —
     the "what's switched on" inventory.
   - **enterShell / enterTest** bodies (multiline strings).
   - Aggregation: one row set per task over the whole fleet with `repo` as
     a field.
3. **Models** over the real A surface; `validate_with` active;
   `compiled_source` for the derived .scm; stubs over the nix schema.
   **Document which A-surface features nix's shape needed (or didn't) —
   that IS a finding.** Hypothesis to test, not assume: record mode (nix's
   `{ key = value; }` attrset is the record shape's natural candidate — a
   small `env`/`settings`-style attrset fragment as a record-mode probe;
   the Phase-8 note said record mode fits config-file grammars; does nix's
   attrset qualify?). Also watch: the Phase-8 mixed-ordering trap (does any
   nix anchor mix fields + positional children?), optional captures, the
   name-inference residue, the wrapper-field-list residual.

### Run 4 — the user artifact + the friction catalog

1. **The example** (`examples/devenv-extract/`): the copyable end-to-end —
   `extract.py` (models + the fleet inventory over the vendored fleet
   subset, prints typed rows per task, self-checks vs ground_truth.json) +
   a README a new user follows: install the light wheels (+
   `tree-sitter-nix`), run it, see rows. Must run from the dev venv (bundle
   shape) AND be documented for the fresh-venv shape (wheel shape). Small,
   honest, not a showcase. Ship `node-schema.json` (the derived schema) in
   the example dir for the wheel shape, exactly like bash.
2. **The friction catalog** (the core finding): the Phase-8 16-entry
   catalog as the baseline, re-assessed over nix — which residuals nix
   TRIGGERED (record mode? the ordering trap? name inference? wheel-version
   mismatch? schema surprises like hidden rules/aliases/supertypes over
   nix?), which it didn't, and any NEW stumbles (interpolation nodes?
   multiline string shapes? dotted-attr paths? the grammar's externals?).
   Each entry: what happened, real gap or documented residual, the escape
   hatch.

### Out of scope — say no to these

- **Publishing** (the user deferred it; the recommendation keeps it as the
  next step — note it, don't do it).
- **Authoring nix** (the grammar is consumed, not authored; no new tsgrammar
  features, no scanner work on the real nix grammar).
- **New A/B surface**, corpus gold-plating, perf work, touching
  `src/pydantree` (the deprecated wrapper), re-opening the Phase-6/7/8
  verdicts.
- **Building anything beyond the vendored fleet subset** — the whole-fleet
  scan is a nice future tool, not this phase's deliverable (the example
  covers the vendored subset).

---

## Environment setup (do this first)

1. `devenv shell` — works. If it isn't, tell the user immediately.
2. The venv is uv-sync-managed — NO editable-install ritual. `devenv shell`
   runs `uv sync` automatically; `src/` resolves via `_pydantree_src.pth`
   (edits live). `uv lock` only after dependency changes. Do NOT run
   `uv pip install -e …`.
3. **Verified facts (don't re-derive):** tree-sitter CLI 0.25.3, bindings
   0.26.0 (ABI 13–15 load), gcc 14.2.1, pydantic 2.13.4, Python 3.13.
   Baseline suite: **171 passed + 1 skipped** (Phase-8 count; recapture
   before you start).
4. **Fixtures you will reuse:** `tests/fixtures/bash/` (the vendoring +
   oracle + the Phase-8 fixes' tests), `tests/test_bundle.py` (the
   capture_kind regression test), `.scratch/010-bash-user/{experiment_run2,
   consumer_bash}.py` (the consumer/experiment pattern),
   `.scratch/007-tsquery-distribution/bfree.py` (the B-free machinery).

---

## Working agreement

- **Commit after each meaningful step**, e.g.:
  `phase9: nix acquisition + schema — vendored tests/fixtures/nix (nix-community/tree-sitter-nix, MIT; wheel-consistency resolved: …), schema byte-for-byte vs the CLI (N kinds, externals: …)`,
  `phase9: the light-install nix consumer — bundle shape + wheel shape, B-free, byte-identical (evidence r9_r2_*)`,
  `phase9: the fleet inventory task — packages/env/scripts/tasks/enabled-switches vs hand truth over the vendored fleet, record-mode probe: fits/doesn't (evidence r9_r3_*)`,
  `phase9: examples/devenv-extract + the friction catalog; findings — go/go-with-changes over a sixth grammar, next: publishing rehearsal (still deferred)`,
  `phase9: findings — the nix adoption verdict + friction catalog, evidence captured`.
- **Write findings as you go** into `.scratch/011-nix-example/FINDINGS.md`.
- **Don't gold-plate.** The example is a small honest artifact.
- **Don't fake the primary experiments.** Run 1 (derive), Run 2 (both
  consumer shapes B-free), and Run 3 (ground truth) must be real and
  hand-verified. Save raw outputs verbatim under
  `.scratch/011-nix-example/evidence/` (`r9_*`).
- **Ask before expanding scope** beyond this brief.

---

## Deliverables (end of session)

1. **Run 1:** `tests/fixtures/nix/` vendored (hermetic, oracle included,
   provenance documented); the wheel-consistency question resolved and
   documented; the derived schema byte-for-byte with the CLI's fresh
   node-types.json (or the exact delta + why).
2. **Run 2:** the nix consumer working through the LIGHT install in BOTH
   shapes (bundle + wheel), B-free, outputs byte-identical to the in-repo
   run (or honestly qualified per the wheel-consistency resolution).
   Evidence under `evidence/r9_r2_*`.
3. **Run 3:** the fleet inventory task — vendored fleet subset, hand truth,
   models, `validate_with` active, rows matching ground truth. Which
   A-surface features nix's shape needed (record mode probe result is a
   finding). Evidence `r9_r3_*`.
4. **Run 4:** `examples/devenv-extract/` (copyable, documented for the
   fresh-venv shape) + the **friction catalog** in FINDINGS (Phase-8
   baseline re-assessed over nix).
5. **`.scratch/011-nix-example/FINDINGS.md`** answering at minimum:
   - Does the "hundreds of grammars" claim hold over a SIXTH grammar (nix:
     attrsets, interpolation, multiline strings, dotted attr paths)? Where
     did the wheel shape and the bundle shape differ for a real user THIS
     time (the wheel-version mismatch)?
   - The friction catalog over nix: which Phase-8 residuals triggered, what
     new stumbles surfaced, each with its escape hatch.
   - **Recommendation:** go / go-with-changes / no-go on "the seam is ready
     for real users over a sixth grammar," and the single most important
     next step — per the user, publishing stays deferred, so say what you
     see (my money stays on the publishing rehearsal as the next step once
     the user lifts the deferral; a whole-fleet scan tool is the natural
     user-facing follow-up).
6. Everything committed and pushed (`origin/main`).

---

## Appendix — durable facts (verified in prior phases; build on these)

1. The bundle contract: `tscore.loader` is the shared loader;
   `Language.load_bundle(dir)` is the one-line consumer; metadata's
   `artifact` names the artifact (default `grammar.so`); the `.so` loads via
   a PyCapsule named `"tree-sitter.Language"` (export `tree_sitter_<name>`).
2. The dev flow (CURRENT): devenv manages the venv with `uv sync` (uv
   workspace, `--no-install-workspace`, `uv.lock` committed,
   `_pydantree_src.pth` resolves `src/` — edits live). `uv lock` after dep
   changes. No pip.
3. The schema derivation is byte-for-byte with the CLI's node-types.json
   over FIVE real grammars (rust, python, markdown, markdown-inline, bash —
   bash: 184 kinds, 29 externals, 0-byte oracle delta); the community tool
   path derives from the installed CLI's own byproduct, so it tracks the
   CLI by construction.
4. The Phase-8 fixes (pinned, do not regress): capture_kind marker
   optionality (`_field_is_query_optional` includes `_CaptureKind`);
   mixed field+positional patterns must order fields in CST order
   (documented in examples/bash-extract/README.md + the Heredoc model).
5. Phase-8 residual catalog (the baseline for Phase 9): name-based kind
   inference (NodeKind = escape), field-mode-list wrapper-field case,
   `lang.name` None for capsule-loaded bundles, record mode fits
   config-file grammars not bash's statement list, raw node text is the
   capture contract (quotes kept), unclosed-heredoc-at-EOF → missing node,
   multi-heredoc-on-one-line broken in the real bash grammar.
6. B-free boundary: consumer processes strip the `src/` path and block
   `tsgrammar` at the meta-path-finder level (the `bfree.py` machinery);
   the fresh-venv shape needs no sitecustomize for tsgrammar (the light
   wheels simply don't ship it).
7. Fresh-venv mechanics: `uv venv` + `uv pip install --find-links
   <wheelhouse>` for the light wheels; community wheels from the real index
   (bash 0.25.1 verified; nix 0.1.0 has manylinux x86_64 + aarch64 wheels —
   installable on this machine).
8. The wheels: pydantree-tscore / pydantree-tsquery (light) /
   pydantree-tsgrammar (heavy); import packages stay tscore/tsquery/
   tsgrammar. **Publishing is deferred by the user — do not publish.**
9. **NEW (verified this kickoff): the corpus fleet.** 52 repos under
   `~/Documents/Projects/*/devenv.nix`. Stats: 30 `packages = [`, 24
   `env.KEY =`, 28 `scripts.*`, 3 `tasks` blocks, 42 `languages.*`, 47
   `.enable = true`, 38 `''...''` multiline strings, 18 `services.*`.
   Sizes 8–526 lines. Candidate corpus: mypi-agent (8), copyroom (11),
   docman (17), fleetman (20), poddantic (20), nixvim (240), fsdantic
   (250), structured-agents-v2 (221), interplay (210), terminal-state
   (192), browsee (135), loci-core (128), flora (526), pydantree (85).
10. **NEW (verified this kickoff): the grammar.** `nix-community/
    tree-sitter-nix` (GitHub, MIT, maintainer @cstrahan, active — pushed
    2026-07-30, latest tag v0.3.0). Source: `src/grammar.json` (~46 KB),
    `src/scanner.c` (~7.6 KB), checked-in `src/node-types.json` (~40 KB
    oracle). PyPI wheel `tree-sitter-nix` 0.1.0: full platform wheels +
    sdist (compiled-only); metadata homepage points at a nonexistent repo —
    **the wheel's grammar version is unknown and must be resolved in
    Run 1 before the wheel shape can be truthful.**
