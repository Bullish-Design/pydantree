# Final Review Prompt — Testing & Verification (Review 019)

**To the reviewer:** You are conducting an adversarial, verification-focused
final review of the pydantree codebase (two packages: `pydantree_sitter` =
Product A, consumption; `pydantree_sitter_grammar` = Product B, authoring).
This review's **sole focus is testing and verification**: do the tests prove
the claims? Is there solid *real-world example usage* verification — suites
that run the shipped examples end-to-end against checked-in fixtures and
**saved expected output**, so a future reader can verify everything works
as anticipated with a single command?

The previous review (018) found real defects in the two products'
selling points and the fixes landed on `main` (16 commits, suite 233 → 265).
Your job is the regression guard: confirm those fixes are *positively
verified* by tests, find what is NOT verified, and judge whether the
real-world verification story is solid enough to ship.

---

## 0. Environment (MANDATORY — read first)

This is a **devenv.sh managed dev environment**. The devenv shell is the ONLY
supported way to run in-repo functionality:

```bash
cd /home/andrew/Documents/Projects/pydantree
devenv shell -- python -m pytest tests/            # the whole suite
devenv shell -- python -c "import pydantree_sitter" # anything in-repo
```

- **Never** run `pytest`/`python`/`uv` outside `devenv shell` for in-repo
  work (PATH, the tree-sitter CLI 0.25.3, gcc 14.2.1, and the venv all come
  from the shell).
- The venv resolves `src/` directly via a `_pydantree_src.pth` — edits are
  live immediately; there is no pip/editable-install flow.
- The tree-sitter CLI is pinned via the committed `devenv.lock`
  (0.25.3). `tests/test_toolchain_version.py` is the drift guard: if the
  CLI ever changes minor version, that test fails LOUDLY on purpose.
- `uv` is managed by devenv (`uv sync --all-extras` on shell entry);
  after dependency changes run `devenv shell -- uv lock` and never commit a
  stale lock.
- The pipeline cache defaults to `~/.cache/pydantree_sitter_grammar`
  (`PYDANTREE_SITTER_CACHE` overrides); the suite redirects it to a session
  tmp dir — if a probe disagrees with the suite, suspect the cache first.

## 1. Baseline (do this first, record everything)

1. `git status` — confirm you're on `main` and the tree is clean.
2. `devenv shell -- python -m pytest -q` — **record the pass count** (the
   claimed baseline is 265). Also run with `-v` once and record the
   per-file breakdown.
3. `devenv shell -- python -m pytest -q -m "not toolchain"` — record how
   many tests self-skip when the toolchain is absent (conftest auto-skip).
   Note the toolchain dependency of each major suite.
4. `devenv shell -- tree-sitter --version` and
   `devenv shell -- gcc --version | head -1` — confirm the pinned toolchain.
5. Save a copy of the full run output (e.g.
   `.scratch/projects/019-final-verification-review/evidence/full-run.txt`)
   so your verdict is re-runnable.

## 2. The verification story you are judging

The project's claim: **real-world example usage is verified end-to-end
against saved fixtures and saved expected output.** Specifically:

### 2.1 The three real-world examples (`examples/`)

- `examples/bash-extract/` — real bash corpus (`sample.sh`, `real_script.sh`,
  `unclosed.sh`), a `ground_truth.json`, and a vendored `node-schema.json`.
- `examples/devenv-extract/` — a nix fleet corpus under `fleet/`.
- `examples/devenv-subset/` — a grammar authored with the rule-class
  surface (`grammar.py`) + a hand-written external scanner (`scanner.c`),
  with `fixtures/` and `ground_truth.json`.

**Verify:** each example has a README that a fresh reader can follow; the
example's own `extract.py` actually runs against its own corpus; the
checked-in `ground_truth.json` matches what the current code produces (a
drift here is a finding — examples are the docs' living proof).

### 2.2 The oracle contract (`tests/test_oracles.py` + `tests/oracles/`)

The three examples' extraction behavior is frozen against **saved expected
output**: `tests/oracles/{bash-extract,devenv-extract,devenv-subset}.json`,
with pre-built grammar artifacts under `tests/oracles/.built/`
(`grammar.so` + `node-schema.json` + `loader.py` + `tree-sitter.json`).

**Verify:**
- `devenv shell -- python -m pytest tests/test_oracles.py -q` passes, and
  the oracles genuinely assert against the checked-in JSON (not regenerated
  in-memory).
- Read `tests/oracles/.built/` provenance: are the committed `.so`/schema
  artifacts reproducible from the committed fixture sources? Is there a
  documented regeneration path (`tests/test_oracles.py --generate` +
  eyeball)? Does the code that builds/loads them match the current pipeline?
- Try the regeneration flow once in a throwaway dir and eyeball the diff —
  is the saved output stable, or does it churn with every run?

### 2.3 Fixture corpora with saved expected output

- `tests/fixtures/grammars/` — the mini-grammars (pymini, hmini, dmini,
  pyindent, bashmini, json_grammar, cfg_grammar, qfilter, …). Each scanner
  seed has `GOOD`/`GOOD_EXPECTED` (hand-computed sexp ground truth) used by
  `tests/test_scanners.py` and the corpus harness. Verify the expected
  sexps are asserted, not just "no error".
- `tests/fixtures/{bash,nix,rust,markdown}/` — real community grammar
  sources with checked-in `node-types.json` byproducts. Verify the
  byte-for-byte round-trip tests and the community-bundle consumers
  (`tests/fixtures/consumers/consumer_{rust,nix,bash,markdown,community}.py`
  — B-free subprocess consumers proving the light-package boundary).
- `tests/fixtures/conflicts/` — the golden conflict-report corpus added in
  review 018 (shift/reduce, dangling-else, reduce/reduce real CLI stderr).
  Verify it parses/renders WITHOUT invoking the CLI (that is the point).
- `tests/fixtures/evidence/` — recorded real generator output.
- Is there a `PROVENANCE.md` documenting where each fixture came from and
  how to regenerate it? A fixture without provenance is a drift risk.

### 2.4 The 018 regression tests (each should be RED against the pre-fix code)

The 018 fixes added these regression tests — spot-check that each is
meaningful (a real assertion of the fixed behavior, not a tautology):

| regression test | fixes (018 finding) |
|---|---|
| `tests/test_checks_nullable.py` | B1/B2 `_nullable` wrappers + Repeat1 |
| `tests/test_valuemap_check.py` | A1 committed ValueMap beats the heuristic |
| `tests/test_pipeline.py::test_cache_key_distinguishes_grammar_name`, `test_promote_race_is_graceful` | B13/B14 |
| `tests/test_rules_sites.py` | B10 rule-class sites point at the author's file |
| `tests/test_conflicts.py::test_parse_conflict_json_survives_stderr_contamination` + golden corpus | B7/B9 |
| `tests/test_extract.py::test_sugar_reuses_compiled_query` | A2 |
| `tests/test_pipeline.py::test_build_warnings_surface` | B15 |
| `tests/test_pipeline.py::test_bundle_abi_matches_the_built_language` | B16 |
| `tests/test_extract.py::test_one_compiler_all_paths_route_through_compile_spec` | §5.1 discipline |
| `tests/test_extract.py::test_raw_query_explicit_capture_is_schema_checked` | A3 |
| `tests/test_extract.py::test_record_pair_kind_must_be_pinned_when_ambiguous` | §4.3 |
| `tests/test_pipeline.py::test_bodyless_external_emits_scanner_token_not_literal_text` | B12 |
| `tests/test_metadata.py` | P1/P2 |
| `tests/test_packaging.py::_assert_no_build_metadata_leak` / `_assert_wheel_matches_source_py` | P4 |

**Spot-check method (at least 3 of these):** `git stash` the corresponding
source change (or check out the parent commit of the fix), run the test,
confirm it FAILS, restore. Record which ones you actually verified this way
— an untested regression test is itself a finding.

### 2.5 Packaging / install boundary

`tests/test_packaging.py` builds real wheels (`uv build`) and installs the
light wheel into a **fresh venv** in a subprocess, proving:
- the light package never imports the heavy one (B-free boundary),
- wheel contents match the source dir (no forgotten module registration),
- no build metadata inside the import namespace.

Verify these actually run (they need `uv` on PATH inside the shell) and
that the fresh-venv subprocesses do not inherit a `PYTHONPATH` that
silently makes them pass (the 018 review flagged exactly this risk).

### 2.6 What is NOT covered — your most important job

Spend at least as much effort finding verification gaps as confirming what
exists. Concretely probe:
- **Real-world A usage not in the suite:** take a real grammar
  (tree-sitter-rust/python/json) and a realistic extraction task not
  already in the tests — does the typed surface work, and would a broken
  change be caught? E.g. extract from the example corpora with a
  committed `ValueMap`, nested records, `...` gaps, `source_meta`, raw
  queries with predicates.
- **Real-world B usage:** a grammar authored from scratch with the rule-class
  surface + an external scanner + a conflict, through
  `build_loop`/`build_builder`, with a corpus; verify the analyzer's
  warnings/errors cite the author's file.
- **Robustness:** error paths — conflicting grammar, missing scanner,
  undefined symbols, a CLI-version drift (what happens if you point
  `tree-sitter` at a different version? the guard should fail loudly and
  EARLY, not 7 scattered failures).
- **Determinism:** run the suite twice — same result? Run the corpus/
  scanner tests with `-p no:randomly` if randomness is involved — is there
  any order dependence (the 018 work hit an id-reuse/GC-order bug in a
  cache — are there others)?
- **The saved-output claim:** for every "saved expected output" (oracles,
  ground_truth.json, GOOD_EXPECTED, `.built/` artifacts, golden conflicts),
  is the file actually ASSERTED by a test, or just present in the repo?

## 3. Method

- Work top-down: baseline → oracle/example verification → fixtures →
  regression spot-checks → gap hunting. Record everything you run and the
  exact command + result in a `test-run.md`.
- **No mocking of the toolchain anywhere**: real CLI + gcc + real wheels.
  If you find a test that mocks the CLI/gcc to "pass", that's a finding.
- Each finding gets an ID (V1, V2, …) with severity
  (major = a claim that isn't verified / a test that can't fail /
  example-oracle drift; minor = provenance gaps, documentation drift;
  nit = style).
- Prefer a probe over speculation: commit small probes under
  `.scratch/projects/019-final-verification-review/evidence/` so verdicts
  re-run.

## 4. Deliverables (write into `.scratch/projects/019-final-verification-review/`)

1. **`FINDINGS.md`** — the verdict, ranked: (a) is the real-world
   verification suite solid and shippable, or does it only *look* covered?
   (b) every V# finding with evidence; (c) the list of 018 regression
   tests you actually spot-checked red-against-prefix; (d) a "keep"
   section — what is genuinely excellent.
2. **`test-run.md`** — every command you ran, its output (saved verbatim
   under `evidence/`), and the final suite count.
3. **`verdict.md`** (one page) — pass/fail/conditional for "the verification
   story is solid enough to ship", with the 3 strongest reasons and the 3
   biggest gaps.

## 5. Environment reminder (repeat as needed)

Everything in-repo runs through **`devenv shell`**. If a command needs the
toolchain and the toolchain is missing from your PATH, you are not in the
shell. The pinned CLI is 0.25.3; `tests/test_toolchain_version.py` is the
guard, not a bug. Never edit `devenv.yaml`/`devenv.lock` to "fix" an
environment issue without flagging it as a finding.
