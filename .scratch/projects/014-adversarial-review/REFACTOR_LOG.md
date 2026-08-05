# pydantree-sitter refactor — phase log (append-only)

Every phase gate records: suite result, commit hash, and anything notable.
Baseline per the guide: **199 passed, 1 skipped @ `fcf505f`** (devenv, warm
cache).

## Gate 0 — oracles before surgery

- **Suite:** 203 passed, 1 skipped, 5 xfailed (strict) (56.5s, devenv) —
  the 4 new oracle tests pass; the 5 thesis-breaking-bug xfails fail as
  designed (they pin the CORRECT behavior).
- **Commit:** `09b40a2` (prerequisite repair: the `.scratch/projects` move
  commit `808c1ce` left `tests/*` sys.path refs pointing at the old flat
  `.scratch/NNN-*` paths and scratch helpers (`bfree.py`, `dev_agreement.py`)
  computing `ROOT` one level too shallow — suite was uncollectable. Fixed
  both mechanically; suite back to the `fcf505f` count.)
- **Oracles committed:** `tests/oracles/{bash-extract,devenv-extract,devenv-subset}.json`
  generated from current code and cross-checked byte-identical against the
  examples' own hand-written ground truths (bash 46 rows across 3 files × 3
  models; nix 102 rows; subset 56 rows + 1 env record + 5 toolchain
  records). The 3 oracle tests run the examples' own models + helpers over
  bundles built from `tests/fixtures/{bash,nix}` and the example's own
  grammar.py + scanner.c (toolchain-gated).
- **New strict xfails (thesis-breaking bugs, to flip in Phase 4):**
  F-A1 (cross-language silent `[]`), F-A2 (schema-bound nested records drop
  matches), F-A3 (NodeKind tuple dropped in field mode), NEW list-branch
  (`...` path skipped for list fields), T-1 (choice-order `required`
  diverges from the CLI — flips to the by-construction pipeline test in
  Phase 3).
- **Also fixed:** `probe_nested_schema.py` still pointed at the flat
  `.scratch/006-*` path (same move breakage).

## Gate 1 — deletions that touch no product code (D13)

- **Suite:** 202 passed, 5 xfailed (55.6s) — the 2 deleted wasm tests were
  the prior skips; everything else identical.
- **Deleted:** `src/pydantree` (8 files, ~800 lines), `src/data`
  (`python_nodes.py` 1147 lines + node-types.json), `src/examples`
  (3 legacy demo scripts); the root distribution (wheel packages config +
  `pydantree`/`demo` console scripts) — root `pyproject.toml` is now the
  uv-workspace + dev-tooling envelope only; `test_packaging.py`'s
  grep-the-config test replaced with a workspace-only assertion.
- **Moved:** `spike-a/` → `.scratch/projects/015-phase1-spike-a/`,
  `spike-a2/` → `.scratch/projects/016-spike-a2-model-only/`,
  `KICKOFF_SPIKE.md` → `.scratch/projects/` (the guide's `001-phase1-spike-a`
  target collided with the existing `001-pydantic-winnow-parser`; used the
  next free numbers). CONCEPT.md path references fixed; .gitignore spike
  paths re-pointed.
- **Wasm:** `src/pydantree_sitter/_wasm_bridge.py` → `.scratch/projects/009-phase7/wasm_bridge.py`;
  `loader.py`'s wasm branch now raises `WasmRuntimeUnavailableError`
  unconditionally (env-var protocol moved to the moved file's docstring);
  deleted the env-gated real-load test and the `/tmp/rust-bundle`
  non-hermetic test; kept the unavailable-error test (asserts the new error
  names the bridge's scratch home).
- **Truth pass:** `pydantree_sitter/__init__.py` false docstring fixed (T-9);
  `docs/architecture.md` module map + wasm seam line; `docs/development.md`;
  `src/pydantree_sitter/README.md`.
- **Grep gate:** `grep -rn "pydantree" src/` hits only dist-name strings
  kept until Phase 2.

## Gate 2 — the rename + two-package fold (D1, D2) — mechanical, no logic changes

- **Suite:** 203 passed, 5 xfailed (55.2s) — Gate-1 count + the one test 2.6
  mandates (`test_importing_light_never_imports_heavy`). The subprocess B-free
  isolation tests pass against the new names.
- **Layout:** `src/pydantree_sitter/` (light: schema.py + loader.py +
  _ir_derive.py from the old seam; typed/dsl/materialize/shapes/stubs +
  schema→`model_schema.py` from the old A package) and
  `src/pydantree_sitter_grammar/` (heavy: builder/checks/conflicts/corpus/
  expressions/language/patterns/pipeline/rules/schema_tool/scanners;
  `grammar.py`→`ir.py`). Old `src/tscore`, `src/tsquery`, `src/tsgrammar`
  deleted. Both packages get pyproject.toml (`pydantree-sitter` /
  `pydantree-sitter-grammar`, 0.1.0), py.typed, LICENSE.
- **Import rewrite:** mechanical across src/tests/examples/docs/.agents +
  the .scratch fixtures/consumers the tests stand on. `ir.GrammarModel`
  (class renamed); `Rule` = the authoring base only, the IR union lives at
  `ir.Rule` and is out of `__all__` (F-B7, 2.4). The `.scratch` evidence dirs
  whose names embedded the old product names were renamed so the Gate-2 grep
  can be empty by construction: `004-tsgrammar`→`004-grammar`,
  `005-tsgrammar-glr`→`005-grammar-glr`, `006-tsquery-bridge`→`006-query-bridge`,
  `007-tsquery-distribution`→`007-query-distribution` (81 refs re-pointed).
- **Dev flow (2.5):** root pyproject members+sources → the two new names;
  `uv lock`; `devenv.nix` `.pth` globs `lib/python*/site-packages` (P-8:
  python3.13 no longer hardcoded) and names the new packages;
  `tests/conftest.py`; `.agents/skills/*` re-pointed (the mechanical sed
  mangled name triples/dist names — hand-repaired).
- **Edges (2.6):** light depends on pydantic + tree-sitter; heavy depends on
  `pydantree-sitter>=0.1`. Wheel-content tests rewritten for the two
  distributions; fresh-venv light install proves B-free against real
  artifacts; new in-process B-free import test.
- **Gate grep:** `grep -rn "tscore\|tsquery\|tsgrammar" src tests examples docs`
  → empty.

## Gate 3 — kill the port; version the bundle (D3, D12)

- **Suite:** 208 passed, 4 xfailed (49s) — the T-1 xfail flipped to the
  by-construction pipeline test; +2 pipeline tests, +7 loader tests.
- **Pipeline (3.1):** `build()` now copies the generate run's
  `src/node-types.json` into the cache entry as `node-schema.json`
  byte-for-byte (`_cache_node_schema`); `_ensure_node_schema` deleted. Warm
  cache entries missing the schema re-run generate (the CLI is the only
  source).
- **Port deleted (3.2):** `src/pydantree_sitter/_ir_derive.py` (974 lines)
  gone; `derive_from_ir` removed from `schema.py` + the package surface;
  `NodeSchema.from_node_types_json` / `derive_from_node_types` are the only
  parse path. Test rewrites: `tests/test_schema.py` now consumes checked-in
  CLI byproducts (`tests/fixtures/jsonlike{,hidden,alias}/node-types.json`,
  generated once from the CLI; the alias grammar's original shape was
  CLI-invalid — repeat-of-empty and a GLR conflict — so the fixture uses
  CLI-valid shapes and the test pins what the byproduct actually reports);
  `test_tsquery_schema.py`/`test_phase5_apolish.py`/`test_bundle.py`/
  `test_oracles.py` re-source schemas from the pipeline byproduct.
- **T-1 (3.3):** the xfail in `test_oracles.py` is replaced by
  `tests/test_pipeline.py::test_choice_order_required_matches_cli_by_construction`
  (both choice orders report the CLI's answer, byte-identical) +
  `test_bundle_schema_is_the_generate_byproduct_byte_for_byte`.
- **Bundle format v2 (3.4, D12):** both bundle writers emit
  `{"bundle_format": 2, ...}`; the loader treats absent as format 1
  (accepted), rejects non-int and >2 with `BundleError` naming both
  versions; new `pydantree_sitter/errors.py` (BundleError) and
  `tests/test_loader.py` covering the TS §7 untested paths (missing
  tree-sitter.json / name / artifact, unknown format) + real format-1 and
  format-2 loads.
- **Docs (3.5):** architecture.md §3/§5 — the schema IS the CLI byproduct,
  tracked by construction; the exact path is retired.
- **Gate greps:** `grep -rn "_ir_derive\|derive_from_ir" src tests` → empty.
