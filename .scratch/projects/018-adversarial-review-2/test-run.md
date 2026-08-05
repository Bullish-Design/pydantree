# Test run (018) — authoritative

The suite **cannot run as documented**: `uv run` fails because the root
`pyproject.toml` declares a hatchling build-backend but ships no package
(`ValueError: Unable to determine which files to ship inside the wheel`) — this is
finding **P2**, reproduced. Ran by reproducing the devenv layout manually
(`uv sync --no-install-workspace --all-extras`, `src/` on path, CLI+gcc from nix).

| Environment | Result |
|---|---|
| No toolchain (a default `pytest`) | **118 passed, 115 skipped** (~4s) |
| tree-sitter CLI **0.25.3** + gcc | **232 passed, 1 skipped** (green) |
| tree-sitter CLI **0.26.8** + gcc | **7 FAILED, 225 passed, 1 skipped** |

- **~49% of the suite (115/233) skips without the Rust+C toolchain** — essentially
  all of Product B. A casual `pytest` proves only Product A. Skips are honest
  (accurate reason strings), auto-applied by `conftest.py:44` on the `toolchain`
  marker. The 1 unconditional skip is the only mypy assertion (`test_codegen.py:110`,
  mypy not on PATH) — so "generated code type-checks" is routinely unverified.

- **CLI-version fragility is real, not hypothetical (confirms §1.4 / B7).** On CLI
  0.26.8 the flagship claims break:
  - `test_bundle.py::test_schema_tool_over_real_rust_source_byte_for_byte` — 0.26.8
    emits an `"extra": true` field the schema tool doesn't, so "byte-for-byte" fails.
  - 6 conflict-detection tests (`test_conflicts` ×4, `test_corpus`, `test_pipeline`)
    — `RuntimeError: no conflict report was found`: the report format the parser
    expects (`conflicts.py:149`) changed. **B's entire raison d'être is already
    broken on a current CLI**, and `devenv.nix` pins `pkgs.tree-sitter` with **no
    version constraint**, so nixpkgs advancing silently breaks the suite with no
    early warning.

## Additional test-quality findings (from the delegated audit)
- **Strong:** no internal mocking anywhere; real artifacts throughout; the ancestor
  matcher property test (2000 randomized cases vs a brute-force reference) is the
  highlight; bundle_format versioning and the wheel/install boundary are genuinely
  exercised (real `uv build` + fresh-venv round-trip); the byte-for-byte schema test
  is what *caught* the 0.26.8 drift.
- **Gaps:** (1) no CLI-version guard anywhere — highest-impact. (2) `AmbiguousCaptureError`
  ("the ONE...") has **no positive test** — the raise path (`match.py:125`) is
  unverified (only a negative assertion elsewhere). (3) the "ONE compiler" claim is
  docstring-only, not guarded. (4) packaging boundary subprocess tests inherit
  `os.environ` (no `env=` scrub) — can pass/fail for the wrong reason if `PYTHONPATH`
  leaks `src`. (5) `test_oracles.py:13-21` docstrings claim F-A1/2/3 are
  `xfail(strict=True)` but there are **no xfail markers** — stale self-description.

**Verdict:** rigorous where it runs, but its confidence is conditional and
under-hedged: half the suite is invisible without the toolchain, and nothing warns
you when the pinned-CLI assumption silently breaks (it already has, on 0.26.8).
