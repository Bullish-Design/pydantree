# Review 019 — findings and verdict

**Status:** in progress  
**Date:** 2026-08-05

The live example/oracle behavior is strong so far: all 265 baseline tests pass,
the three real-world outputs match both saved oracles and hand-written ground
truth, and oracle JSON regeneration is byte-stable. The committed prebuilt
artifact story is not yet shippable as claimed.

## Findings

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

## Review 018 red-against-prefix spot checks

Pending.

## Keep

- The baseline is genuinely broad: 265 real tests, all green; 129 are explicitly
  toolchain-marked and 136 run without the toolchain selection.
- Oracle JSON assertions are real file reads, not in-memory regeneration.
- Each oracle also agrees with independently checked-in example ground truth.
- Regenerating the oracle JSON into `/tmp` produced byte-identical output.
- All three example scripts are self-checking, and all pass when given available
  language artifacts; the authored subset exercises both products plus a real
  external scanner end to end.

## Verdict

Pending fixture, regression, gap, packaging, and determinism review.
