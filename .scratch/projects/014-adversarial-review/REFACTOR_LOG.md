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

## Gate 4 — Product A rewrite (D4, D5, D6, D11) — the big one

- **Suite:** 220 passed (49s) — the four thesis-breaking A xfails FLIPPED to
  plain tests in this phase (F-A1 4.2, F-A3+NEW-list 4.3, F-A2 4.4); the
  Phase-0 oracle contract is unchanged (all three example extractions
  byte-identical to the checked-in JSONs).
- **New machine (beside the old, then deleted):**
  - `markers.py` — inert markers (M with kind-tuple alternation, capture/
    capture_kind/source_meta/derived(value), Matches/Eq/AnyOf/NodeKind/
    Unescaped, RawQuery); isinstance everywhere (F-A13).
  - `spec.py` — PathStep/FieldBinding/MatchSpec + pure `derive_spec` +
    DerivingMeta (MRO walk, per-class re-derivation — deep-read item 13);
    class-creation checks (ForwardRefs resolved via the model's module,
    nested-in-field-mode rejected legibly, marker conflicts).
  - `binding.py` — Language (load/from_module/load_bundle with lib kept
    alive, F-A10; reparse without old_source, F-A11) + Extractor; per-Language
    (model, strict) cache (D5); warnings as data, warned once at bind (F-A6).
  - `compiler.py` — the ONE compiler: Jobs 1/3/4 ported (is_possible_descent,
    expand, capture↔type with the ValueMap ladder: int accepts int-only,
    float accepts float+int), per-kind pattern emission (F-A3 dies),
    record-mode compilation consuming ONLY (schema, ValueMap), nested
    sub-extractors bound at bind (F-A2 dies), raw-query compile at bind
    (unknown captures listed).
  - `emit.py` — the dsl emitter core, internal only (dsl.py deleted, F-A9);
    `match.py` — ONE backtracking ancestor matcher + anchor grouping/merge,
    property-tested vs a brute-force reference (2000 random cases) and called
    from exactly one place (the NEW list-branch skip dies by construction);
    `materialize.py` — one kwargs builder + Span + JSON unescape + MatchFailure
    (the legacy second OutputModel/capture/extract_records/Diagnostic stacks
    deleted); `valuemap.py` — ValueMap + JSON_VALUE_MAP + `propose_value_map`
    (shapes.py demoted to the draft generator, D6).
  - The unmarked-field symmetry (D4.1): unmarked = bind-by-name in BOTH
    modes; `derived(value)` is the computed/constant case.
- **Test cutover:** test_tsquery_port / test_tsquery_schema /
  test_phase5_apolish / test_bundle rewritten to the new surface (the
  registry tests became per-instance isolation tests; the DSL tests became
  raw-query tests — `tests/test_raw_query.py`); new `tests/test_match.py`
  property tests. All cfg-grammar record tests attach the reviewed draft
  ValueMap (the cfg grammar is not the JSON family).
- **Examples:** devenv-subset binds record models through the Extractor with
  `propose_value_map(lang.schema)` (the authored grammar needs the map);
  bash/devenv-extract unchanged except imports. devenv-subset self-check:
  56 rows ✓.
- **Gate greps:** no `print(` in pydantree_sitter; no
  `__class__.__name__ ==`; no `_SCHEMA_REGISTRY`/`_derived_cache`/
  `_schema_derived`.

## Gate 5 — typed CST codegen (D7)

- **Suite:** 222 passed (54s).
- **codegen.py:** `generate_typed_api(schema, module_name)` emits a REAL
  runtime module (the stubs.py .pyi fiction is deleted, F-A4): TypedNode
  wraps a tree_sitter.Node (kind/text/line/children), one class per named
  kind with field accessors typed from the schema (required+single -> T,
  optional -> T | None, repeated -> list[T] via field_name_for_child), a
  children(kind) accessor, supertypes as unions (emitted dependency-first —
  unions reference other unions; anonymous refs -> TypedNode), KIND_MAP +
  wrap(). Class names via the acronym-aware camel helper (shared with F-B4).
- **Two shipping forms:** the A-side function, and the bundle hook
  `BuildResult.package(..., typed_api=True)` dropping `typed_api.py` beside
  the schema.
- **Tests (tests/test_codegen.py):** module execs over the real rust schema
  (163 kinds); runtime round-trip (parse real rust, wrap(), field accessors
  == raw child_by_field_name, repeated fields, children accessor); mypy over
  a consumer importing the GENERATED RUNTIME module (the F-A4 spirit —
  type-checks AND runs); acronym-aware naming.
- **Deleted:** stubs.py + test_stubs.py (the mypy-only fiction test).
- **Gate grep:** `grep -rn "stubs" src` -> empty.

## Gate 6 — Product B correctness + explicitness (D8, D9, D10, F-B*)

- **Suite:** 233 passed (20s — the fast loop is genuinely fast now).
- **6.1 site-on-node (D8):** `ir.RuleNode` gains `_site` (PrivateAttr,
  non-serialized; `__eq__` overridden to field-only so provenance never
  affects DSL equality); combinators stamp at construction; `site_of(node)`
  reads it; the `_SITES` registry, the rule() drain, `Grammar._node_sites`,
  `__body_sites__` snapshots and the assemble re-apply loop are DELETED
  (annotation nodes stamped at creation via `__attr_sites__`). ONE
  frame-walker `caller_site(skip)` with a pinning test; conflict-remap
  tests still name the author's lines. Greps `_SITES/_node_sites/
  __body_sites__` empty.
- **6.2 explicit assembly (D9):** `assemble(name, *, start, rules=...)`;
  `module_rules(module)` = classes DEFINED in the module (imported classes
  excluded — the silent-join bug dies); function-local rule classes work;
  the example switches to the explicit idiom. Exported `module_rules`.
- **6.3 pipeline consolidation (D10):** `run_generate` always `--json` (the
  conflict report is JSON on the same run's stderr — the second generate is
  deleted); `build(check=True)` runs `checks.assert_clean` (check=False to
  skip; `build_from_source_dir` uses check=False — community grammars aren't
  ours to analyze); `builder.Grammar` grows a public read-only view
  (start_rule/extras_view/externals_view/word_view) that `checks._GrammarView`
  reads; ONE `write_bundle` (BuildResult.package delegates; the duplicated
  loader shim constant deleted); `build_from_source_dir` absorbs schema_tool's
  bundle path (same cache/errors/writer; never touches the author's checkout,
  F-B11); cache promote via rename-if-absent; `detect_toolchain` is an
  lru_cache with documented cache_clear.
- **6.4 F-B sweep (pinning tests in tests/test_phase6_fixes.py):** B1
  `rule(alias=)` deleted; B2 multi-`Literal` -> choice (default must be one
  of the values); B4 `_snake` acronym-aware (`HTTPServer`->`http_server`,
  leading underscore survives); B5 whitespace-only extras suppress the
  injected `\s` (intent-based); B6 `replace_rule` honors `hidden`; B8/B9
  expressions docstrings + `_as_op` returns the StrNode directly; B10 corpus
  dead assignment deleted; B12 `_first_literal_chars` heuristic documented;
  B13 one `as_node` in extra(); ladder int-mode renumbering hazard
  documented; corpus `render_compact(expr_kind=)` parameter; Toolchain ABI
  from `tree_sitter.LANGUAGE_VERSION` (env as override only).
- **probe_b_side.py** updated to the new API: every repro now shows the
  CORRECT behavior (multi-Literal CHOICE, alias= gone, no \s dupe, no
  import pollution, acronym snake).

## Gate 7 — test-suite hygiene (TS-1/TS-2, review §6)

- **Suite:** 233 passed (59s); fast loop `-m "not slow"` = 199 passed in 24s;
  toolchain-less run = 114 passed, 119 skipped, ZERO errors.
- **7.1 fixtures promoted:** `tests/fixtures/grammars/` (json_grammar,
  cfg_grammar, qfilter, qfilter_corpus, pymini, hmini, dmini, pyindent,
  bashmini, reference-grammar.json, community-bash/grammar.json),
  `tests/fixtures/bfree/` (bfree.py + consumer_env), `tests/fixtures/consumers/`
  (consumer.py, consumer_community.py, consumer_rust.py, consumer_markdown.py,
  consumer_bash.py, consumer_nix.py), `tests/fixtures/evidence/` (the
  recorded conflict report). Zero sys.path.insert and zero .scratch imports
  in tests/ (grep-gated); the 004/005/006/007/008/009/010/011 scratch deps
  are all promoted. PROVENANCE.md written (7.6).
- **7.2 gating:** one conftest mechanism — the `toolchain` pytest marker +
  auto-skip hook (toolchain-less runs SKIP, zero errors). The nine
  copy-pasted TOOLCHAIN_AVAILABLE blocks deleted; the ungated tests
  (test_extract, test_conflicts' surface section, test_rules' one build
  test) covered by the marker.
- **7.3 isolation:** autouse fixture points the cache at a session tmp dir
  (env renamed to PYDANTREE_SITTER_CACHE, TSGRAMMAR_CACHE honored as legacy
  fallback); an autouse fixture kills sys.modules leaks from the exec'd
  `g_*` test grammars.
- **7.4 cost:** session-scoped rust/nix/markdown bundle fixtures in
  conftest; `@pytest.mark.slow` on the gcc-heavy files (test_bundle,
  test_scanners); `-m "not slow"` documented as the fast loop (24s).
- **7.5 structure:** test_phase3a.py dissolved into test_corpus.py +
  test_expressions.py; test_phase3_surface.py into test_conflicts.py;
  test_phase5_apolish.py renamed test_extract.py.
- **7.6 provenance:** tests/fixtures/PROVENANCE.md (upstream repo/commit/
  license for rust/bash/nix/markdown + the promoted in-project fixtures).
- **Gate greps:** no .scratch imports, no sys.path.insert in tests/ (the
  only mentions are conftest's own path setup and intentional error-message
  assertions).

## Gate 8 — docs truth pass + rewrite

- **Suite:** 233 passed.
- **README.md** rewritten for the two-package layout, the new names, the
  bind idiom, and the two honesty statements (§8.2: A's expressibility
  ceiling — M() = anchored ancestor path + direct-child captures +
  predicates, everything else -> `__raw_query__`; value shapes are declared
  data — `propose_value_map` is a reviewed-draft generator).
- **docs/architecture.md** rewritten: two packages, the seams, the
  pipeline (--json always, check=True, write_bundle, build_from_source_dir),
  the module map (markers/spec/binding/compiler/emit/match/materialize/
  valuemap/codegen/errors + ir.py), durable facts (bundle_format, the ABI
  from LANGUAGE_VERSION), where to start reading.
- **docs/user-guide.md** truth pass: the extractor bind replaces
  validate_with as the primary idiom, the registry text is gone, the
  taxonomy (ShapeError/QueryBuildError/BundleError), alias= deleted,
  assemble(rules=) + module_rules, the community tool at
  pipeline.build_from_source_dir, typed_api=True bundle hook, the failure
  surface.
- **Truth sweep:** baseline counts (233), the §3.9 swapped-file description
  (devenv_builder_dsl_grammar.py), docs/development.md (toolchain marker,
  PYDANTREE_SITTER_CACHE, wasm error-only test), the extraction skill
  regenerated for the new API. `grep tscore/tsquery/tsgrammar docs README
  .agents` -> empty (the one README mention is the historical note).
- **CONCEPT.md** gains the dated addendum recording D1–D14.

## Gate 9 — packaging floor + publication (P-3/P-5/P-6/P-7, D14)

- **Suite:** 233 passed.
- **9.2 metadata floor:** both pyprojects gain authors/classifiers/
  project.urls, PEP 639 `license = "MIT"`, README as long description;
  py.typed in both packages (already shipped since Phase 2). A TOML gotcha
  was caught by the build: `[project.urls]` swallowed the following
  `dependencies` key — the urls table now ends the [project] section.
- **9.3 wheel truth:** test_packaging now asserts, against REAL wheels:
  py.typed present, LICENSE rides, NO __pycache__/.pyc (P-7), the scanner
  .c files in the grammar wheel and absent from the light, and the
  fresh-venv LIGHT-only install boundary (`import pydantree_sitter` works,
  `import pydantree_sitter_grammar` fails). Verified manually:
  pydantree-sitter wheel = py.typed + LICENSE + no pyc, no scanners;
  pydantree-sitter-grammar = + all five scanner .c files.
- **9.4** version pins in tests read `pydantree_sitter.__version__`
  dynamically (no ==0.1.0 literals).
- **9.1/9.5 — the external step (needs PyPI credentials, a human):**
  register/claim `pydantree-sitter` and `pydantree-sitter-grammar` on PyPI
  and publish 0.1.0 of both. The docs install lines already use the real
  commands (`uv pip install pydantree-sitter`); the packages are buildable
  and wheel-truth-verified as of this gate.
- **Appendix B gates (run):** tscore/tsquery/tsgrammar -> 0;
  _ir_derive/derive_from_ir -> 0; _SITES/_node_sites/__body_sites__ -> 0;
  _SCHEMA_REGISTRY/_derived_cache/_schema_derived -> 0 (the one hit was a
  flipped test's docstring describing the pre-fix bug — reworded);
  `print(` in pydantree_sitter -> 0; `__class__.__name__ ==` -> 0;
  sys.path.insert in tests -> 0 (conftest owns path setup);
  `.scratch` in tests -> only conftest prose + the wasm error-message
  assertion; `id(node)|id(n)` in builder.py -> 0.

**Final suite:** 233 passed (fast loop `-m "not slow"` ~24s; toolchain-less
run all-skip zero-error). Line delta vs `fcf505f`: see `git diff --stat`.
