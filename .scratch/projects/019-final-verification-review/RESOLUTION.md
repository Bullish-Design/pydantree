# Review 019 — post-review resolution

**Date:** 2026-08-05

## V1 resolved by removing the compatibility fixture

The project does not guarantee—and does not want—backward compatibility for
previously generated native bundles. Accordingly,
`tests/oracles/.built/{bash,nix,subset}` was removed instead of adding tests
that would turn stale, platform-specific `.so` files into a supported contract.

The retained verification model is simpler:

1. `tests/oracles/*.json` is the durable observable-behavior contract.
2. `tests/test_oracles.py` rebuilds every grammar from committed sources through
   the current pipeline and toolchain.
3. The freshly built bundle must reproduce the saved extraction JSON and the
   examples' independent ground truth.
4. Generated bundles may be release/CI outputs, but they are not repository
   fixtures and carry no cross-version compatibility promise.

The Review 019 findings remain unchanged as the historical record of what was
observed. This resolution closes V1 by removing the unverified artifact claim;
it does not claim to close the independent V4/V5 findings.

## V2–V7 resolved by the clean-session implementation (2026-08-05, guide `IMPLEMENTATION-GUIDE.md`)

All remaining findings are closed with real tests and commands; the detailed
run log is `implementation-run.md`. The suite grew 265 → 272 tests
(toolchain-free 136 → 152). Every commit is on `main`:

| finding | closure evidence (commit) |
|---|---|
| V4 golden guards CLI-free | blanket `toolchain` marker removed; only the seven real-CLI tests stay marked; golden conflict nodes run with a PATH of only the managed venv (`b1789bc`) |
| V5 community byproducts asserted | shared manifest `tests/community_fixture_manifest.py` + `tests/regenerate_community_node_types.py` (check/`--write`, atomic) + parameterized byte-for-byte oracle `tests/test_community_fixtures.py`; nix fixture refreshed to the supported CLI's `root`/`extra` fields (`8f7607f`) |
| V6 provenance concrete | exact upstream commits resolved by byte-matching vendored sources (bash `a06c2e44`/v0.25.1, rust `b3e615de`, nix `ea1d87f7`/v0.3.0, markdown(+inline) `808e105a`); `tests/fixtures/PROVENANCE.md` + `tests/fixtures/nix/PROVENANCE.md` reconciled; conflicts corpus provenance + executable `tests/fixtures/conflicts/regenerate.py` (`8f7607f`) |
| V7 precise sites | `test_rules_sites.py` derives key/value/class lines and requires exact attribute lines; `test_pipeline.py::test_build_warnings_surface` requires the exact mixed-precedence line; both fail when weakened to the broader line (verified) (`e272020`) |
| V2 examples runnable | READMEs/docstrings reordered (dev path first, direct bundle path, standalone section with fixed package name); three subprocess tests run each example's real CLI entry point against the session bundles — bash 34 / nix 102 / subset 56 rows (`870730c`) |
| V3 fresh-worktree sync | root cause: uv 0.6.17 `uv sync` syncs the root project only; workspace-member deps (pydantic, tree-sitter) need `--all-packages`. Added the `pydantree:ensure-uv-sync` guard task (import check → explicit locked sync with `--all-packages` → re-check → fail hard); proven in a brand-new detached worktree: first entry imports deps, oracle suite passes, second entry fast, `uv.lock` unchanged (`75fff13`) |

Verification matrix (Step 7): focused contracts 53 + 27 passed; full suite
`272 passed` twice with `-p no:randomly`; `-m 'not toolchain'` → 152 passed;
`tests/regenerate_community_node_types.py` and
`tests/fixtures/conflicts/regenerate.py` exit 0 with zero worktree changes;
`tests/test_oracles.py --generate` reproduces the three oracle JSONs
byte-for-byte (`git diff --exit-code` clean); `git diff --check` clean;
`main` pushed and synchronized `0 0`.
