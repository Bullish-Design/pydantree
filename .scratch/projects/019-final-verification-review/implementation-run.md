# Review 019 — implementation run log

**Start date:** 2026-08-05
**Guide:** `.scratch/projects/019-final-verification-review/IMPLEMENTATION-GUIDE.md`

## Baseline (Step 1.2)

- Branch: `main`, clean, synchronized (`git rev-list --left-right --count main...origin/main` → `0 0`).
- `tests/oracles/.built/` absent; `git ls-files tests/oracles/.built` prints nothing.
- Toolchain: tree-sitter `0.25.3`, gcc `14.2.1 (GCC) 20250322`, Python `3.13.5`.
- Full suite: `265 passed in 60.66s`.
- Starting commit: TBD (record at end).

## Work log

### Step 2 — V4 (commit `b1789bc`)

- Removed the blanket `pytestmark = pytest.mark.toolchain` from
  `tests/test_conflicts.py`; marked only the seven tests that generate /
  compile / load a grammar (`test_ambiguous_resolves_greedy_at_runtime`,
  `test_dangling_else_without_opt_in_conflicts`,
  `test_conflict_cites_per_production_seq_line`, `test_build_loop_*`,
  `test_debug_states_returns_report`, `test_whitespace_default_parses_spaces`).
- Golden conflict tests run with a PATH containing only the managed venv
  (no CLI/gcc): `2 passed`, not skipped.
- `tests/test_conflicts.py -m 'not toolchain'` → `15 passed, 7 deselected`
  (was 0 with the blanket marker).
- Toolchain-free count across the whole suite: 136 → **151**
  (`151 passed, 114 deselected`).

### Step 3 — V5+V6 (commit `8f7607f`)

- Added `tests/community_fixture_manifest.py` (frozen dataclass manifest),
  `tests/regenerate_community_node_types.py` (check/`--write` with atomic
  replacement), `tests/test_community_fixtures.py` (parameterized
  byte-for-byte oracle test, `toolchain` + `cli_byte_for_byte`).
- Resolved exact upstream commits by byte-matching vendored sources
  (grammar.json + scanner.c + tree_sitter headers) against upstream
  history (blob-id comparison): bash `a06c2e44` (tag v0.25.1), nix
  `ea1d87f7` (tag v0.3.0), rust `b3e615de`, markdown + markdown-inline
  `808e105a`. Evidence: `evidence/fix-v5-*.txt`, `evidence/fix-v6-*.txt`.
- Only nix was stale: fresh CLI 0.25.3 adds `"root": true` to `source_code`
  and `"extra": true` to `comment` (the guide-predicted serialization
  fields). `--write` refreshed it; check mode now exits 0 with all five
  unchanged (fresh `PYDANTREE_SITTER_CACHE` each run).
- Replaced rust's one-off byte test in `test_bundle.py` with the shared
  parameterized test; split the nix byte test: byte equality moved to the
  shared test, semantic shape assertions kept toolchain-free in
  `tests/test_schema.py::test_nix_node_types_shape_semantics`.
- Wrote `tests/fixtures/conflicts/regenerate.py` (real CLI `--json`,
  `--write` gate, atomic replace); check mode: all three conflict fixtures
  byte-identical to fresh CLI 0.25.3 stderr.
- Rewrote `tests/fixtures/PROVENANCE.md` (exact commits, regeneration
  commands, supported CLI range, conflicts corpus) and reconciled
  `tests/fixtures/nix/PROVENANCE.md` (committed oracle now matches the
  supported CLI; removed the obsolete stale-byproduct statement).
- Focused suites: `tests/test_community_fixtures.py test_bundle.py
  test_schema.py test_conflicts.py -q` → `54 passed in 35.34s`.

### Step 4 — V7 (commit `<pending>`)

- `tests/test_rules_sites.py::test_attribute_sites_are_more_precise_than_the_class_line`
  now derives key/value/class lines from `AUTHOR_SRC.splitlines()` and
  asserts: non-null sites, author file, distinct `lineno`s, exact
  `key: Name` (6) / `value: Name` (7) lines, neither equal to the class
  line (5), and the recorded `source` text identifies the attribute.
- `tests/test_pipeline.py::test_build_warnings_surface` now finds exactly
  one precedence warning, asserts a non-null site, file
  `test_pipeline.py`, exact mixed-choice construction line (derived at
  runtime from `Path(__file__)`), and `tg.choice` in the recorded source.
- Negative checks (temporarily weakened, then restored):
  - key site asserted against the class line → `AssertionError: assert 6 == 5`;
  - warning site asserted against the function `def` line → AssertionError.
  Both tests fail when the expected line collapses to the broader line.
- `tests/test_rules_sites.py tests/test_pipeline.py -q` → `15 passed in 2.19s`.

### Step 5 — V2 (commit `870730c`)

- Reordered `examples/{bash-extract,devenv-extract}/README.md` + extract.py
  docstrings: repository/developer path first (`pytest tests/test_oracles.py`),
  then the direct in-repo bundle path (`build_community_bundle` →
  `/tmp/pydantree-example-{bash,nix}` → `extract.py --bundle`), then the
  standalone consumer path as a separate section (duplicate
  `pydantree-sitter pydantree-sitter` fixed to the single light dist).
- Fixed the duplicate package name in `examples/devenv-subset/README.md`.
- `tests/test_oracles.py`: session bundle fixtures (`bash_bundle`,
  `nix_bundle`, `subset_bundle`) + language fixtures loading from them;
  three new subprocess tests run each example's real CLI entry point
  (`sys.executable`) against the same session bundles and assert exit 0
  plus the self-check text: bash 34, nix 102, subset 56 rows. Suite:
  `11 passed` (was 8).
- All direct documented commands verified: `34 rows extracted — all match
  the hand-written ground truth ✓` / `102` / `56`.

### Step 6 — V3 (commit `75fff13`)

- REPRODUCED: a brand-new detached worktree from clean `HEAD` reported
  `devenv:python:uv` success (91ms) while `import pydantic` failed.
- ROOT CAUSE: uv 0.6.17's `uv sync` defaults to the ROOT project only —
  workspace members (`src/pydantree_sitter`, `src/pydantree_sitter_grammar`)
  and their deps (pydantic, tree-sitter) are excluded unless `--all-packages`
  is given. `uv tree` shows the full workspace; `uv sync --dry-run` audits
  only the 5-19 root packages. Proven with a minimal two-member workspace
  and in the real fresh worktree. The primary venv's pydantic predates this
  behavior (installed before the root-only default took effect) and uv never
  removes extra packages, so the checksum-cached root-only sync masked the
  gap — exactly V3. Evidence: `evidence/fix-v3-root-cause.txt`.
- FIX: added the `pydantree:ensure-uv-sync` task (after `devenv:python:uv`,
  before `pydantree:venv-src-pth`, which now depends on it). It runs the
  venv python's import of pydantic/pytest/tree_sitter; on failure runs
  `UV_PROJECT_ENVIRONMENT="${config.env.DEVENV_STATE}/venv" uv sync
  --all-extras --frozen --no-install-workspace --all-packages`; re-checks
  and exits 1 if still broken. `--all-packages` is the minimal deviation
  from the guide's command (without it the prescribed sync provably does
  not install member deps, so the guard would fail every fresh worktree);
  `--no-install-workspace` still keeps member packages OUT of the venv
  (verified: only `_pydantree_src.pth` in site-packages).
- CLEAN-WORKTREE PROOF (from commit `75fff13`): first shell entry imports
  dependencies; `tests/test_oracles.py` → `11 passed` in the fresh worktree;
  second entry fast (guard ~190ms, import check only); `uv.lock` unchanged.
  (The exit-139 interpreter-teardown core after the oracle suite is the
  KNOWN nix-grammar 0.26 teardown crash — reproduced identically in the
  primary worktree; all 11 tests pass in both.)
- `docs/development.md` updated with the guard's purpose + the
  clean-worktree smoke command.

### Step 7 — full verification matrix

- Focused contracts: `test_conflicts.py test_community_fixtures.py
  test_rules_sites.py test_pipeline.py test_oracles.py` → `53 passed`;
  `test_bundle.py test_schema.py` → `27 passed`.
- Toolchain-free: `tests/ -m 'not toolchain'` → `152 passed, 120 deselected`
  (was 136 at review time; +16 pure tests now run without the CLI/gcc).
- Full suite `-p no:randomly`: `272 passed in 66.17s` and
  `272 passed in 65.93s` (identical counts, deterministic).
- `tests/regenerate_community_node_types.py` → exit 0, all five unchanged.
- `tests/fixtures/conflicts/regenerate.py` → exit 0, all three unchanged.
- `tests/test_oracles.py --generate` → wrote the three oracle JSONs;
  `git diff --exit-code -- tests/oracles tests/fixtures` → clean (byte-stable).
- `git diff --check` clean; `main` synchronized `0 0`.

## Summary

- Starting commit: `5cc8400` (review019: add clean-session implementation guide).
- Ending commit: see `git log` (final review019 closure commit below).
- Toolchain: tree-sitter `0.25.3`, gcc `14.2.1`, Python `3.13.5`, uv
  `0.6.17`, pytest `9.1.1`, pydantic `2.13.4`, tree-sitter bindings `0.26.0`.
- Suite: 265 → **272 passed** (deterministic across two full runs);
  toolchain-free 136 → **152**.
- Fresh-worktree (V3): first entry imports pydantic/pytest/tree_sitter;
  oracle suite `11 passed` inside the new worktree; second entry fast;
  `uv.lock` unchanged.
- Regeneration: all five community node-types + three conflict fixtures
  byte-identical to fresh CLI 0.25.3 output; oracle JSON regeneration
  byte-stable (`git diff --exit-code` clean).
- Commits created for the work:
  1. `b1789bc` tests: run golden conflict guards without the toolchain (V4)
  2. `8f7607f` tests: verify every community node-type fixture (V5+V6)
  3. `e272020` tests: require precise non-null author source sites (V7)
  4. `870730c` examples: verify the supported fresh-bundle run path (V2)
  5. `75fff13` dev: guarantee uv sync in fresh worktrees (V3)
  6. (final) review019: close verification findings V2 through V7
