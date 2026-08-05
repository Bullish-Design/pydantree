# Review 020 — resolution

**Status:** complete
**Date:** 2026-08-05
**Resolution commit:** `9f780cb` (285 passed, exit 0 — was 272 + SIGSEGV 139)

All findings fixed **except B3 (C++ scanners)** — the user explicitly
declined it as unneeded. Every fix is regression-tested; 13 new tests were
verified **red on the pre-fix code** via `git stash push -- src/`.

## Must-fix

| # | Fix | Regression test |
|---|---|---|
| A1 | `emit.py`: raw-query quantifier maps built per REAL pattern index (the old length-1 list IndexError'd `Cursor.matches` for 2+ patterns) | `test_raw_query.py::test_raw_query_multi_pattern_does_not_index_error` |
| A2 | `compiler.py`: field-mode `list[T]` emits `?` (zero-or-more via the anchor merge) — empty-list anchors no longer vanish. `*` was proven unusable empirically (tree-sitter captures only ONE node per `*` capture) | `test_extract.py::test_field_mode_list_anchor_with_zero_occurrences_matches` |
| A3 | `binding.py`: `reparse()` computes the old→new diff and applies `old_tree.edit()` (mid-buffer edits left an ERROR node without it) | `test_extract.py::test_reparse_mid_buffer_edit_applies_the_edit` |
| A4 | `compiler.py` + `spec.py`: alternation anchors checked/inferred over EVERY kind. **Deeper bug found**: `derive_spec` passed M()'s alternation tuples through RAW (not `PathStep`) — every `M(("a","b"),…)` path crashed at bind; the advertised feature was entirely broken and untested | `test_extract.py::test_alternation_anchor_checks_every_kind` |
| B1 | `pipeline.py`: `build_builder` runs the analyzer over the BUILDER grammar first (`check=False` to build) — analyzer ERRORS now cite the author's DSL sites | `test_pipeline.py::test_build_builder_analyzer_errors_cite_author_sites` |
| B2 | `conflicts.py`: conflict-JSON brace counting is STRING-aware (block grammars with `{`/`}` literals no longer fall back to the raw dump) | `test_conflicts.py::test_parse_conflict_json_brace_tokens_inside_strings` |

## The exit-139 segfault — root-caused and fixed

**Root cause:** `load_grammar_so` dlopen'd the bundle's `grammar.so`
directly. dlopen mmaps the file; truncating/rewriting a mapped .so in
place leaves the mapping's pages past the new EOF → SIGBUS (truncate) /
SEGV (copyfile-over) at interpreter shutdown when the language's
finalizer touches one. The trigger was real and reproducible:
`examples/devenv-subset/extract.py` builds its bundle INTO
`DEVENV_BUNDLE_DIR` — the same directory the parent process already
loaded — so the child's `package()` truncated the parent's mapping
(plain-python repro: `segv_test2.py`/`segv_test5.py mode i`, deterministic).

**Fix:** `load_grammar_so` copies the .so to a private snapshot
(`tempfile.mkstemp`), dlopens that, and unlinks it once the mapping is
established. A loaded language is now immune to later rewrites of the
bundle dir. Verified: `tests/test_oracles.py` and the full suite exit 0
(was 139); the repro scripts exit 0.

**Regression test:** `test_bundle.py::test_loaded_bundle_survives_in_place_rewrite`
(subprocess loads a bundle, parses, truncates+rewrites `grammar.so` in
place, exits — asserts rc 0).

## Should-fix / minor

- **B3 C++ scanners** — intentionally NOT fixed (user: "not needed").
- **B4** `checks.py`: nullable-non-start is a WARNING — the CLI 0.25.3
  empirically ACCEPTS nullable non-start rules (repeat-of-symbol,
  opt-in-seq, FIELD-wrapped opt all generate rc 0). The old error-level
  check rejected legitimate `repeat(ref("item"))` idioms.
  Test: `test_checks_nullable.py::test_nullable_non_start_rule_is_advisory_not_an_error`.
- Example `want` NameError (`examples/devenv-extract/extract.py:253` → `len(truth[key])`).
- Doc snippets: README + user-guide import `Language` correctly; README 265→272.
- `materialize.py`: `source_meta()` into `int | None`; record OPTIONAL
  predicate fields keep the record (required ones still filter).
- `spec.py`/`compiler.py`: subclass without `__match__` → friendly
  `ShapeError`.
- `compiler.py`: field-mode `str` over a string wrapper captures the inner
  content (consistent with record mode).
- Cache locks: `_PROPOSED_CACHE` (`compiler.py`) and `_LANGUAGE_CACHE`
  (`binding.py`) are now `threading.Lock`-protected.
- `pipeline.py` `build()` + `schema_tool.py` `derive_schema_for_dir`: work
  dirs are cleaned on generate/compile failure (try/finally).
- `pipeline.py`: `_python_abi` docstring now matches the real
  fallback-only behavior (B16 test unchanged).
- `conflicts.py`: `remap_from_proc` raises `GenerateError` (raw evidence
  preserved) instead of a bare `RuntimeError`.
- `builder.py`: `replace_rule` undoes stale inline/supertype/word/conflicts
  flag entries under both the original and the hidden-renamed name.
  Test: `test_phase6_fixes.py::test_replace_rule_clears_stale_flag_entries`.
- `pipeline.py`: warm-cache schema backfill also writes
  `entry/src/node-types.json` so `node_types_json` never dangles.
- `int` over JSON `number` float-text limitation: documented in the user
  guide (bind cannot know; runtime pydantic error).

## Resolution follow-ups (all three now done)

Follow-up commit `review020-followups` (the user's request): move the
wheel-only tests, add the toolchain-free example, and fix B3.

- **B3 — C++ scanners (was "intentionally not fixed") — DONE.**
  `pipeline.compile_parser` now detects `scanner.cc/.cpp/.cxx` and compiles
  with a TWO-STEP gcc+g++ build (parser.c stays C — g++ rejects its C
  designated initializers, verified empirically — the scanner is compiled by
  g++ and linked with g++ for libstdc++). `build()`, `build_from_source_dir`
  and `schema_tool` all discover `scanner.cc`; the explicit `scanner=` copy
  preserves the suffix (previously renamed to scanner.c, losing it); the
  `ExternalScannerRequiredError` message mentions both. Tests:
  `test_scanners.py::test_cpp_scanner_scanner_cc_builds_with_gpp` and
  `::test_community_layout_discovers_scanner_cc` (both red on pre-fix code).
- **Toolchain-free live example with a committed per-step transcript oracle
  — DONE.** `examples/wheel-extract/` — Product A over the tree_sitter_python
  WHEEL (no CLI, no gcc, no build). `extract.py` prints five steps (bind /
  parse / extract / self-check / transcript) and compares its own stdout
  against the COMMITTED `transcript.txt` (the oracle ends with a fixed
  success line so a green run's stdout equals the file byte-for-byte;
  `--update` regenerates after eyeballing). `tests/test_wheel_example.py`
  (NOT toolchain-marked) asserts the example exits 0, its stdout equals
  `transcript.txt`, the transcript is a real per-step narrative, and the
  ground truth rows are embedded.
- **Wheel-only tests moved off the toolchain gate — DONE.**
  `tests/test_binding_wheel.py` (non-gated) now holds the reparse
  incremental + mid-buffer-edit tests, `source_meta()` into `int | None`,
  and the missing-`__match__` friendly-error test — all wheel-only, removed
  from the toolchain-gated `test_extract.py`. Reviewer gap #4 (Product A's
  core untested off-toolchain) is closed: the plain shell now runs 156
  non-toolchain tests (was 152).

## Evidence

- `evidence/full-suite-final.txt` — 285 passed, exit 0.
- Red-green checks: `git stash push -- src/` ran the new tests against the
  pre-fix code — all 13 red (A1, A2, A3 [ERROR-node variant], A4
  [AttributeError — alternation was fully broken], B1, B2, B4,
  replace_rule, loader truncation [exit ≠ 0]).
- The segfault investigation (plain-python repros, bisection, SIGBUS-vs-SEGV
  pinning) is summarized above.
