# REVIEW 018 — resolution record

**Date:** 2026-08-05 · **Branch:** `fix/review-018` · **Baseline → final:** 233 → 265 green.

Every finding in `REVIEW.md` was resolved per `IMPLEMENTATION_GUIDE.md`,
test-first where the guide prescribed it. Commits (one per step, scope
prefixed):

| commit | step | findings |
|---|---|---|
| `c0e2ad3` | 1.1 | B1, B2 (`_nullable` wrappers + Repeat1) |
| `266b38a` | 1.2 | A1 (checker consumes (schema, ValueMap)) |
| `7c9cb85` | 1.3 | B13, B14 (cache key + promote race) |
| `7919158` | 1.4 | B10 (rule-class sites point at the author's file) |
| `9ecf9a0` | 1.5 | B7, B9, B19 (conflict remapper robustness, CLI-drift scoping) |
| `5eaafbc` | 2.1 | A2 (sugar-path Language memoized) |
| `a43b566` | 2.2 | B15 (analyzer warnings on BuildResult) |
| `2d53ee5` | 2.3 | B16 (bundle abi = the built ABI) |
| `77750b9` | 3.1 | P1, P2, P3 (root is a virtual workspace envelope) |
| `5cdf62c` | 3.2 | P4, P5, §1.5 (wheel contents, doc truth, wasm no-go appendix) |
| `fb9ae85` | 3.3 | A4–A11 (diagnostics, dead source, schema index, ABI, forward-refs, codegen guard, import layering) |
| `060d0b3` | 3.4 | B3–B6, B8, B11, B12, B21, B23, B24, word guard |
| `9f74a48` | 3.5 | B17, B18, B20, B22 |
| `634d1da` | 4 | A3/§4.1b, §4.2 golden conflict corpus, §4.3 record_pair |

## Notable verdicts

- **B12 (External fallback):** verified empirically against the real CLI
  (0.25.3) — a bodyless `External`'s `tok('NAME')` body IS the external
  reference (the CLI resolves a body STRING matching an external
  declaration to the external; pymini's convention; single node-types
  entry). Pinned end-to-end with a real scanner rather than "fixed".
- **P4:** hatchling force-include does NOT honor the target `exclude`
  patterns (verified in 1.31 source); `only-include` cannot remap to a
  target dir. Used an explicit force-include file list + a
  wheel-vs-source completeness gate in `tests/test_packaging.py`.
- **0.2 toolchain pin:** `devenv.yaml`/`devenv.nix` experiments (pinned
  nixpkgs rev + module-level assert) caused a devenv lock re-resolution
  hang and an infinite-recursion eval respectively — reverted. The
  committed `devenv.lock` already pins the snapshot; the defense is
  `tests/test_toolchain_version.py` (loud, early fail on drift) + the
  `cli_byte_for_byte` skip scope.
- **A1 memo:** id-keyed `_proposed` cache must hold the schema object
  (id-reuse after GC returned a stale draft ValueMap for a different
  grammar — caught by the full suite).

## Re-run

```bash
devenv shell -- python -m pytest -q      # 265 passed (0.25.3)
```
