# Review 019 — findings and verdict

**Status:** complete
**Date:** 2026-08-05

The live example/oracle behavior is strong: all 265 baseline tests pass,
the three real-world outputs match both saved oracles and hand-written ground
truth, oracle JSON regeneration is byte-stable, and novel A/B probes pass. The
committed saved-artifact story is not yet shippable as claimed.

## Findings

Ranked summary:

| severity | findings |
|---|---|
| major | V1 unverified/stale `.built` bundles; V4 CLI-free golden tests skip; V5 saved community byproducts mostly unasserted |
| minor | V2 example install/run documentation; V3 fresh-worktree dependency sync; V6 incomplete provenance; V7 weak source-location precision assertions |

### V1 — major — committed oracle bundles are outside the verification contract and have drifted

`tests/oracles/.built/{bash,nix,subset}` looks like checked-in, saved build
evidence, but no test references `.built`. `tests/test_oracles.py` always builds
fresh temporary bundles; `--generate` rewrites only the three JSON oracle files.
There is no `.built` provenance/regeneration document.

A real fresh-cache rebuild from the checked-in sources found:

- subset: artifact, schema, metadata, and loader reproduce byte-for-byte;
- bash/nix: schemas and loaders reproduce, but both native artifacts differ;
- bash/nix metadata says `"toolchain": "community"` while the current pipeline
  produces `"toolchain": "tree-sitter 0.25.3"`.

The old bundles still load and drive their example scripts to the correct 34-row
and 102-row ground truths. That is useful manual confirmation, but a future
change can break or stale these files without any suite failure. This directly
violates the saved-output claim for `.built/`.

Evidence: `evidence/artifact-rebuild-hashes.txt`, the two bundle-backed example
logs, and source inspection of `tests/test_oracles.py`.

### V2 — minor — the copyable Product A example path is not runnable in the supported dev environment

The default bash and nix example scripts import community wheels not present in
the managed dev environment, so both fail immediately with
`ModuleNotFoundError`. Their READMEs give a standalone `uv venv` / `uv pip`
flow, but repository instructions say all in-repo work is managed by devenv and
forbid manual installs. Both install snippets also repeat `pydantree-sitter`.
The documented `--bundle` alternative works and was manually verified, but it
is not the primary copy/paste command and is not exercised by the oracle tests
through `.built`.

Evidence: `evidence/example-bash.txt`, `evidence/example-devenv.txt`, and the
successful `*-bundle.txt` logs.

### V3 — minor — a fresh detached worktree's devenv reports dependency sync success but has an empty dependency set

The exact documented oracle regeneration command was tried in a detached
throwaway worktree. `devenv:python:uv` reported success, but the worktree's own
`.devenv/state/venv/bin/python` could not import `pydantic`. This blocks a clean
throwaway-worktree regeneration/review flow and makes the task status misleading.
The oracle generator itself is sound: redirecting its output under the active
known-good environment produced three byte-identical JSON files.

Evidence: `evidence/oracle-regenerate.txt`,
`evidence/fresh-worktree-import.txt`, and
`evidence/oracle-regenerate-hashes.txt`.

### V4 — major — the CLI-free golden conflict guard is skipped when the CLI is absent

The two golden conflict tests are explicitly designed to parse and render
saved real CLI stderr **without invoking the CLI**. Their implementation does
exactly that, but `tests/test_conflicts.py` blanket-marks the whole module as
`toolchain`. With a PATH containing the managed Python but no CLI/gcc, both
golden nodes report `skipped`. Thus the structural drift guard disappears in
the environment it was designed to support, and 22 tests are misleadingly
counted as toolchain-dependent.

Evidence: `evidence/golden-no-toolchain.txt` and the module-level
`pytestmark` in `tests/test_conflicts.py`.

### V5 — major — most checked-in community node-type byproducts are present but not drift-tested

`tests/fixtures/PROVENANCE.md` calls the vendored community
`node-types.json` files drift-detection fixtures. Only Rust has a real
checked-in byte-for-byte regeneration assertion. Nix compares output to the
same fresh generator run (and explicitly documents that the checked-in file
differs); Bash, Markdown, and Markdown-inline build/extraction tests consume
fresh generated schemas and never compare the saved files. Those saved outputs
can drift or become stale without a test failure.

This does not weaken the by-construction runtime claim—the pipeline still copies
the current CLI byproduct—but it does weaken the review's stronger claim that
the checked-in expected artifacts are verified.

Evidence: source inspection of `tests/test_bundle.py`, `tests/test_schema.py`,
and reference search across `tests/`.

### V6 — minor — fixture provenance is incomplete for several drift-sensitive artifacts

The global provenance file is useful, and Nix/fleet provenance is excellent.
However, Rust is pinned only to `master`, Markdown/Markdown-inline only to
`fixture-pinned`, Bash has a version but no exact commit in the table, and no
regeneration commands are given. The Review 018 golden `conflicts/` corpus is
not listed at all. This makes intentional refreshes hard to distinguish from
accidental drift.

### V7 — minor — two source-location regression tests do not assert the precision named in their claims

`test_attribute_sites_are_more_precise_than_the_class_line` checks only that
every site has the author's **file**; it never compares the attribute line to
the class line. A regression collapsing all attribute sites back to the class
line would pass. Likewise, `test_build_warnings_surface` uses
`all(w.site is None or ...)`, which passes if every warning loses its site.

Current behavior is good: the novel Product B probe asserts a real analyzer
warning has a non-null site ending in `probe_realworld_b.py`, and the build-loop
conflict also names that file. The gap is regression strength for finer line
precision/nullability, not a reproduced production defect.

## Review 018 red-against-prefix spot checks

Verified red on the parent of each fix and green on current `main`:

1. A1 — `test_committed_valuemap_is_authoritative_in_the_check` against
   `c0e2ad3`: failed because the pre-fix checker does not accept/use the
   committed `ValueMap`.
2. A2 — `test_sugar_reuses_compiled_query` against `9ecf9a0`: failed with 10
   query compiles for five identical calls.
3. B16 — `test_bundle_abi_matches_the_built_language` against `a43b566`:
   failed with stale override ABI `9` instead of runtime ABI `15`.

Current paired run: all three pass.

## Keep

- The baseline is genuinely broad: 265 real tests, all green; 129 are explicitly
  toolchain-marked and 136 run without the toolchain selection.
- Oracle JSON assertions are real file reads, not in-memory regeneration.
- Each oracle also agrees with independently checked-in example ground truth.
- Regenerating the oracle JSON into `/tmp` produced byte-identical output.
- All three example scripts are self-checking, and all pass when given available
  language artifacts; the authored subset exercises both products plus a real
  external scanner end to end.
- Every scanner seed's saved expected sexp is fed to the corpus harness and
  compared to the rendered CST; planted clean-generating semantic regressions
  prove the harness can fail.
- The real wheel boundary is substantive: wheel contents match source modules,
  build metadata is excluded, a fresh venv installs only Product A, Product B
  cannot import, and real bundle extraction succeeds.
- Three sampled Review 018 tests are demonstrably red before their fixes and
  green after them.
- Novel gap probes passed over a real Rust community grammar and a new
  rule-class/external-scanner/conflict-loop grammar; the probes themselves
  failed on incorrect schema assumptions and expected CST/line data before
  their hand expectations were corrected.
- CLI 0.26 drift fails in one dedicated guard in 0.12 seconds, and two
  sequential full-suite runs have identical 265-pass outcomes.

## Verdict

**CONDITIONAL / not yet solid enough to ship under the strong claim that all
saved expected outputs and prebuilt artifacts are verified.**

The executable product behavior is ship-quality: real examples, fresh builds,
B-free consumers, wheels, scanner corpora, novel tasks, robustness guards, and
determinism are all substantive. Release becomes supportable once V1, V4, and
V5 are closed: either remove `.built` and unverified byproducts from the stated
contract, or add provenance/regeneration plus direct assertions; and unmark the
CLI-free golden tests so they actually run without the toolchain. V2, V3, V6,
and V7 are follow-up hardening/documentation work.
