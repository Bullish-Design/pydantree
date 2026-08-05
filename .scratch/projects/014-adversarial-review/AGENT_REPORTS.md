# Delegated deep-review reports (verbatim)

Three parallel deep-dives commissioned for this review. Their findings are
integrated (and re-ranked) in REVIEW.md; this file preserves the full
evidence.

---

# Report 1 — Test-suite quality

Suite: 22 test files + conftest, **199 test functions** (docs pin "170 green + 1 skip"). Overall the suite is unusually strong on oracle-style checks (byte-for-byte vs CLI output, planted regressions, B-free subprocess isolation) but has structural problems: coupling to `.scratch/` spike code, two files that break the project's own toolchain-gating contract, global-state leaks, and near-zero coverage of the hand-written Query DSL and error paths.

## (a) Top 10 findings, ranked

1. **Ungated gcc/CLI dependency in two files — contradicts the documented gating contract.**
   `docs/development.md:57` claims "Tests that need the tree-sitter CLI / gcc skip themselves when the toolchain is absent (`TOOLCHAIN_AVAILABLE` guards)". But:
   - `tests/test_phase5_apolish.py:38` computes `TOOLCHAIN_AVAILABLE` and **never uses it** — there is no `pytestmark`. `_cfg_lang()` (line 59-64) and both field-mode-list tests (lines 236-263) call `tg.build_builder` (generate + gcc). ~8 of 13 tests in the file hard-fail without the toolchain.
   - `tests/test_rules.py:376-390` (`test_assembled_grammar_passes_checks_build_and_parse`) calls `tg.build_builder(g, scanner=...)` with no guard.

2. **The suite imports committed spike code from `.scratch/` at module scope.** `test_bundle.py:29-47` (`bfree`, `cfg_grammar`, `json_grammar` from `.scratch/006`/`007`, plus `.scratch/008` and `.scratch/011` consumers), `test_corpus.py:25-41` (`qfilter`, `qfilter_corpus` from `.scratch/005`/`007`), `test_scanners.py:21-30,123-127,207-211` (`pymini`, `dmini`, `hmini`, `bashmini`, `pyindent` from three scratch dirs), `test_phase3a.py:26-27`, `test_phase5_apolish.py:35-43`, `test_schema.py:78`, `test_tsquery_schema.py:30`, `test_packaging.py:164`. The imports run at collection time — before `pytestmark` skips apply — so a pruned `.scratch/` turns skips into collection errors. Six files mutate `sys.path` at module scope for the whole session. Production contract tests should not live on experiment scaffolding.

3. **Global `_SCHEMA_REGISTRY` leak + file-local-only isolation.** `tests/test_tsquery_schema.py:252-274` (`test_language_load_registry_is_opt_in`) registers a schema under name `"cfg"` in the process-global `pydantree_sitter.typed._SCHEMA_REGISTRY` and never cleans up. The isolating autouse fixture exists only in `test_phase5_apolish.py:46-56` — it protects that file, not the rest of the session. Any later schema-less extract over a language named `cfg` silently picks up the leaked schema: latent order dependence across files.

4. **Tests write to the user's real build cache.** `tg.build_builder`/`tg.build` default to `~/.cache/pydantree_sitter_grammar` (`src/pydantree_sitter_grammar/pipeline.py:146-147`). Call sites without `cache_dir=`: `test_phase5_apolish.py:61,70,238,254`, `test_corpus.py:86,94,104,129,...`, `test_bundle.py:71,84`, `test_tsquery_schema.py:53,286`, `test_schema.py:67,85,199`. Tests pollute the developer's home cache and depend on it (the docs themselves call the stale cache a classic gotcha at `docs/development.md:62-65`). Green timing depends on a warm global cache — the "~40s" claim in `docs/development.md:50` is only true on a warmed machine.

5. **`rules.py` multi-value `Literal` is untested and misbehaves — a real gap hiding a bug.** `src/pydantree_sitter_grammar/rules.py:278-279`: nested `Literal["+", "-"]` compiles to `str(get_args(t)[0])` — **silently drops all values but the first**. Top-level: `rules.py:312` `(val,) = get_args(t)` raises a raw "too many values to unpack" instead of an authoring error. `tests/test_rules.py` only ever uses single-value `Literal["="]` (lines 158, 191, 206). No test pins either behavior.

6. **The manual Query DSL (`src/pydantree_sitter/dsl.py`, 475 lines) is essentially untested.** Only three trivial uses exist (`test_phase5_apolish.py:84-85,94,107`: `Query(node(...))`, one `.child`, `.validate`). Untested public surface: `PatternSet` / `|` composition, `cap()`/`where()`/`Matches`/`Eq`/`AnyOf` predicate emission at the DSL level, `Query.check()`, `capture_names`, `quantifier_for`, `Query.extract(into=...)`, the whole `Cursor`/`MatchView`/`NodeView` accessor family (`nodes`, `first`, `all_text`, `has`, `quantifier`, `snippet`, `byte_range`). Same story for `pydantree_sitter/materialize.py`: `binding_warnings`, `build_kwargs`, `AmbiguousCaptureError` have no direct tests.

7. **Loader error paths and the wasm bridge have no effective coverage.** `src/pydantree_sitter/loader.py:158,164,169` (missing `tree-sitter.json`, bad metadata, missing artifact → `FileNotFoundError`/`ValueError`) — untested (grep confirms only happy-path `load_bundle` + the wasm-unavailable error in `test_wasm.py:42-55`). `src/pydantree_sitter/_wasm_bridge.py` (180 lines): the only test exercising it is double-gated on two env vars **and** a probe artifact (`test_wasm.py:75-92`) — effectively never runs. `test_wasm.py:58-68` depends on machine state `/tmp/rust-bundle` — non-hermetic, in practice a permanent skip (this is presumably the "1 skip" in the pinned baseline).

8. **Redundant heavy builds — no session fixtures, no slow marker.** `test_bundle.py` rebuilds the full rust community bundle (generate + gcc over a 182-rule grammar) three times (lines 218, 243, 264), the nix bundle three times (421, 450, 471), markdown twice (337-338, 361); `test_corpus.py` calls `tg.build_builder` in nearly every test. No `@pytest.mark.slow`, no session-scoped bundle fixture; cold-cache runtime is many minutes, silently amortized by finding #4's global cache.

9. **Docs/test contract drift.** `docs/development.md:55` and `README.md:53` pin "170 green + 1 skip (post Phase 7)" — the suite now has 199 test functions (Phases 8/9 + rules-surface tests were added without updating the pinned record). Also `tests/test_rules.py:4-5` docstring references `tests/fixtures/devenv_classes_grammar.py`, which does not exist (the real files are `examples/devenv-subset/grammar.py` and `tests/fixtures/devenv_builder_dsl_grammar.py`). And the gate test at `test_rules.py:90-106` reaches outside `tests/` into `examples/` — the "fixture" is a moving example file.

10. **Vacuous / incoherent / quirk-pinning assertions.**
    - `test_packaging.py:96`: `assert int(major) >= 0.26 or tree_pin >= "tree-sitter>=0.26"` — `int("0") >= 0.26` is always False, so this always falls back to a **lexicographic string comparison of a version string** (would wrongly fail on `>=0.100`). Redundant with the exact-pin test at line 123, but as written it asserts nothing sound.
    - `test_corpus.py:115`: `assert render_compact is not None` — vacuous; `render` is imported (line 22) and never exercised directly.
    - `test_phase3a.py:144`: `assert ifs.child_by_field_name("cond").type == "("` — enshrines the surprising behavior that the `cond` field binds to the anonymous `(` token after hidden-rule flattening. If that's intended API, the docstring should say so; as-is it reads like a pinned quirk.
    - `test_checks.py:31-46` pokes privates (`g2.rules[...] = ....node`, `g2._word`, `g2._start`) and contains dead setup (the first grammar `g` incl. `keyword_only` at line 39 is built and never asserted on).

## (b) Coverage-gap list (each verified by grep over `tests/`)

- **Multi-value `Literal`** in rules.py — no test; behavior is buggy (finding #5).
- **One model extracted across two different languages** — never tested (every model is bound to exactly one language per test).
- **Nested record models under the schema-checked path** — `PersonNested`/`Addr` nesting is tested only on the wheel/no-schema path (`test_tsquery_port.py:234-239`); no `validate_with(lang, schema=...)` over a nested-model record.
- **`load_bundle` non-wasm error paths** (`pydantree_sitter/loader.py:158-169`) and **`_wasm_bridge.py`** (finding #7).
- **`check_alias_on_seq`'s imported-IR warning path** — `grep "wraps a SEQ" tests/` is empty; only the builder-time `ValueError` is tested (`test_phase3_surface.py:206-212`).
- **Corpus renderers** — `render`/`render_compact` never tested directly; snapshot **diffing** on grammar change untested (only snapshot file existence, `test_corpus.py:192-204`).
- **`Language.reparse`** — one smoke test (`test_phase5_apolish.py:78-89`); the comment claims subtree sharing but the test never verifies it, and the `old_source` parameter (`src/pydantree_sitter/typed.py:757-769`) is **accepted and silently ignored** — untested dead parameter.
- **`replace_rule`** — only used incidentally inside the fix-loop test (`test_phase3_surface.py:154`); no direct contract test (unknown rule name, site re-recording).
- **`capture_kind`** — all coverage lives behind the toolchain gate in `test_bundle.py`; no light (schema-only) unit test of its Job-1 check or query emission.
- **`schema_tool` error paths** — bad grammar dir, missing `grammar.json`, CLI failure: untested.
- **`load_language` failure modes** (`pydantree_sitter_grammar/language.py`) — bad `.so` path, wrong name: untested.
- **`binding_warnings` / `build_kwargs` / `AmbiguousCaptureError`** — no direct tests (the ambiguity error is only referenced in a docstring, `test_tsquery_schema.py:192`).
- **`src/pydantree/` legacy wrapper (~700 lines: core, generator, incremental, views, cli)** — zero tests. Documented as frozen, but nothing pins it against regression; it *is* still shipped by the root wheel (`test_packaging.py:111` asserts it's packaged).
- **stubs.py breadth** — only the rust schema; no schema-without-supertypes or degenerate-schema case.
- `M()` path validation edge cases in the unbound (schema-less) mode; `strict=False` covered exactly once (`test_tsquery_port.py:203-211`).

## (c) Test-smell list

- **Phase-named files pin development history, not module contracts**: `test_phase3a.py`, `test_phase3_surface.py`, `test_phase5_apolish.py` overlap `test_expressions.py`/`test_corpus.py`/`test_conflicts.py`; a reader cannot tell where a contract lives.
- `TOOLCHAIN_AVAILABLE` boilerplate copy-pasted in 9 files (and forgotten in 1 — finding #1) instead of a shared conftest marker.
- `_parse_errs`-style tree walkers duplicated 5× across `test_scanners.py`, `test_phase3a.py`.
- Module-level `OutputModel` subclasses (`test_tsquery_port.py:56,113`, `test_bundle.py:53-66`) — class creation runs the derivation machinery at import/collection time; failures become collection errors.
- Module-scope `sys.path.insert` in 6 files, accumulating for the whole session.
- Dead code: `test_schema.py:75` `sys_path_insert = None`; `Eq` imported unused in `test_tsquery_schema.py:20`; `test_wasm.py:59` re-imports `load_bundle` under an alias for no reason.
- Repr-coupled assertions: `test_tsquery_schema.py:140` `ei.value.schema_entry == "NodeKind(('identifier',)) vs int"`; `test_bundle.py:94` `len(loader_lines) <= 8` (brittle "7-line loader" pin).
- Hard-pinned versions: `test_packaging.py:153` installs `pydantree-pydantree_sitter==0.1.0` / `pydantree-pydantree_sitter==0.1.0` — breaks on any version bump.
- Non-hermetic: `test_wasm.py:63` `/tmp/rust-bundle`; `test_conflicts.py:82` and `test_grammar_ir.py:96,167` skip on `.scratch` artifacts (they do exist in git, so these run — but they're evidence files, not fixtures).
- Fixtures: ~1.4MB of vendored community grammar sources committed (`rust`, `bash`, `markdown`, `markdown-inline`, `nix`) — all text, regenerable in principle; **only `nix/` has `PROVENANCE.md`** — rust/bash/markdown lack provenance, upstream version pin, and license attribution (they are MIT grammars whose LICENSE files aren't vendored).
- `_exec_grammar` in `test_rules.py:50-58` leaks synthetic modules into `sys.modules` without cleanup (`g_rows`, `g_bad_lit`, ... persist for the session).

## (d) Heavy pipeline gating, and suite-vs-docs contradictions

- **Does the suite run generate+gcc?** Yes, extensively — `test_pipeline`, `test_expressions`, `test_phase3_surface`, `test_phase3a`, `test_corpus`, `test_scanners`, `test_bundle`, `test_tsquery_schema`, and 3 tests in `test_schema` are gated by `shutil.which("tree-sitter") and shutil.which("gcc")` skips; `test_packaging`'s fresh-venv test additionally gates on `uv`. **Ungated exceptions:** `test_phase5_apolish.py` (guard computed, never applied) and `test_rules.py:376`. On a toolchain-less machine the suite does not degrade to skips as documented — it errors.
- **Contradictions with docs/README:**
  - "170 green + 1 skip" baseline (`README.md:53`, `docs/development.md:55`) vs 199 collected tests today — the pinned record is stale.
  - "Tests that need the CLI/gcc skip themselves" (`docs/development.md:57`) — false for two files.
  - "full suite (fast, ~40s)" (`docs/development.md:50`) — only with a pre-warmed `~/.cache/pydantree_sitter_grammar`; cold runs compile rust/nix/markdown/bash grammars repeatedly (finding #8).
  - `test_rules.py` module docstring names a fixture path that doesn't exist.
- **Tests pinning questionable behavior:** `test_phase3a.py:144` (cond field = `"("` token), `test_packaging.py:96` (vacuous version assert), and `test_phase5_apolish.py:78-89` (comment claims incremental sharing that is never asserted; meanwhile `reparse(old_source=...)` is dead API surface no test would catch).

**Credit where due:** the byte-for-byte oracle tests (`test_schema.py:216-257`, `test_bundle.py:197-209,382-411`), the planted-regression corpus tests (`test_corpus.py:122-185`), and the B-free subprocess isolation tests are genuinely adversarial, high-value tests — the suite's core verification strategy is sound; its hygiene and gating are what need work.

---

# Report 2 — Packaging, distribution, docs, examples

## (a) Top 10 findings by severity

**1. The `pydantree` PyPI name is owned by someone else — the root distribution is unpublishable as configured.**
PyPI `pydantree` 0.1.2 = "Pydantic parser for tree-sitter" by **Louis Maddox <louismmx@gmail.com>** (verified via `https://pypi.org/pypi/pydantree/json`). `pyproject.toml` declares `name = "pydantree"`, `version = "0.1.2"`, author Bullish Design — same name, same version, different owner. Anyone running `pip install pydantree` gets the stranger's package, and this repo can never publish the root project under that name.

**2. Import-package collision: `pydantree_sitter` and `pydantree_sitter` are both live top-level packages on PyPI owned by others.**
PyPI `pydantree_sitter` 0.1.1 (GPL-3.0 CLI) — wheel verified to install **top-level `pydantree_sitter/`**. PyPI `pydantree_sitter` 0.0.1a0 ("TAIScore") also exists. Installing `pydantree-pydantree_sitter` alongside either package clobbers/collides in site-packages with undefined winner. `pydantree_sitter_grammar` is unregistered (404) — free today, squattable tomorrow. The repo's own comments acknowledge the `pydantree_sitter` name is taken but only rebranded the *distribution*, not the *import package* — the collision is unmitigated.

**3. None of the three product distributions are published, yet every install instruction assumes they are.**
`pydantree-pydantree_sitter`, `pydantree-pydantree_sitter`, `pydantree-pydantree_sitter_grammar` all 404 on PyPI. But `README.md:45-47`, `docs/user-guide.md:21-28`, all three `examples/*/README.md` and `examples/bash-extract/extract.py:12` say `uv pip install pydantree-pydantree_sitter pydantree-pydantree_sitter …`. Every user-facing quickstart fails today; nothing says "not yet published".

**4. The root wheel config is broken: `packages = ["src/pydantree", "src/examples", "data"]`.**
There is no root `data/` directory — the package lives at `src/data/`. The installed legacy wheel therefore cannot even be imported: `src/pydantree/__init__.py:20` imports `.views`, and `src/pydantree/views.py:26` does `from data.python_nodes import …` at module import time. Additionally the wheel ships **top-level `examples`** — a maximally generic, collision-prone site-packages name — and the `demo = "examples.demo:main"` script writes to the relative path `"src/data/python_nodes.py"` (`src/examples/demo.py:77`), broken when installed.

**5. No `py.typed` marker in any package.** All three products are typed API surfaces (pydantree_sitter even ships a `.pyi` generator); without PEP 561 markers, mypy/pyright treat installed wheels as untyped.

**6. The "170 green + 1 skip" baseline is stale.** `README.md:53` and `docs/development.md:55` pin it; the suite now collects **200 tests**. (Outside devenv: 96 pass / 94 skip / 10 fail — the failures are toolchain-absence, consistent with devenv requirement; but the documented count is wrong regardless.)

**7. `docs/architecture.md:161` — "`dsl.py` … NOT public" is false.** `src/pydantree_sitter/__init__.py:20-29` imports `MatchView, NodeSpec, NodeView, Pred, Query, QueryBuildError, cap, node` from `.dsl` and lists all in `__all__`.

**8. `docs/user-guide.md:436-442` (§3.9 byte-identity gate) names a nonexistent fixture and swaps the roles.** It claims `tests/fixtures/devenv_classes_grammar.py` (class-authored) is compared to `examples/devenv-subset/grammar.py` ("the builder-DSL spelling"). Reality: the fixture is `tests/fixtures/devenv_builder_dsl_grammar.py` (builder DSL), and `examples/devenv-subset/grammar.py:67-71` is the **class-authored** one. `tests/test_rules.py:4-5` docstring repeats the same inverted description.

**9. Product pyproject metadata is thin:** no `authors`, no `classifiers`, no `project.urls` in `src/pydantree_sitter|pydantree_sitter|pydantree_sitter_grammar/pyproject.toml`. Combined with #2, an unauthored generic-import-name upload is a supply-chain-confusion target. LICENSE files present and identical MIT copies (good).

**10. Stale phase record across docs.** `docs/README.md` phase table stops at 009; `.scratch/` contains `010` … `013` and recent commits reference 012/013. `docs/architecture.md:225` still calls `009-phase7/FINDINGS.md` "the most recent verdicts".

## (b) Full docs-vs-code inconsistency list

1. `architecture.md:161` — `dsl.py` "NOT public" vs `src/pydantree_sitter/__init__.py` exporting 8 dsl symbols.
2. `user-guide.md:436-442` + `tests/test_rules.py:4-5` — swapped/nonexistent gate files.
3. `README.md:53`, `development.md:55` — "170 green + 1 skip" vs 200 collected tests.
4. `docs/README.md` phase table ends at 009; `architecture.md:225` "most recent" = phase 7 — four newer `.scratch` phases exist.
5. `src/pydantree_sitter/__init__.py` docstring: "One module, no more: `pydantree_sitter.schema`" — pydantree_sitter now also contains `loader.py`, `_ir_derive.py`, `_wasm_bridge.py`.
6. `README.md:12` quick example imports `NodeKind` but never uses it; same unused import in `user-guide.md:476`. The example itself is API-valid: `extract(text, language=module)` is supported, `M`, `capture`, `str | None` optional capture all check out.
7. Root/README/docs describe `src/pydantree` as "deprecated … frozen" but the code carries **no** deprecation marker, still registers the `pydantree` console script, and is broken-on-install anyway. Also stray junk inside it: `src/pydantree/cli/cli_module.py` and `src/pydantree/main/main_init.py` (directories without `__init__.py`).
8. `user-guide.md §3.9` inline sample references `R(String)` and `SourceFile` never defined in the sample.
9. All install instructions reference unpublished distributions. Community-wheel references are fine (`tree-sitter-bash`, `tree-sitter-nix` exist).
10. `development.md §2` "fast, ~40s" accurate only in-devenv; 10 tests **fail** (not skip) outside devenv.
11. Verified-accurate claims (no action): `.agents/skills/` exists with all 4 documented skills; scanner library = 5 `.c` seeds matching `scanner-library.md`; `docs/README.md` index links all five docs files; user-guide API table matches `src/pydantree_sitter/typed.py`; `reserved` exists as `Grammar.reserved_word`.

## (c) Packaging risk list

1. **Name squatting / collision (critical):** import packages `pydantree_sitter`/`pydantree_sitter` collide with live third-party PyPI packages; `pydantree_sitter_grammar` and the three `pydantree-*` dist names are unregistered; `pydantree` itself is owned by a third party at the exact same version number. Mitigation: register names now or rename imports (e.g. a `pydantree.` namespace).
2. **Root wheel broken + top-level `examples`; missing `data` package** — fix to `"src/data"` or drop the legacy distribution entirely.
3. **`force-include "." = "<pkg>"`** (all three product pyprojects) maps the entire package dir into the wheel: `pyproject.toml`/`PKG-INFO`/`README.md`/`LICENSE` ride inside site-packages (documented as intentional), but `__pycache__/` dirs exist in every package dir and `tests/test_packaging.py` never asserts `.pyc`/`__pycache__` absence — risk of shipping stale bytecode.
4. **No `py.typed`** in any wheel.
5. **Dependency graph itself is correct** (verified): pydantree_sitter → `pydantree-pydantree_sitter>=0.1`, pydantree_sitter_grammar → `pydantree-pydantree_sitter>=0.1`, no A↔B edge; `pydantree_sitter._ir_derive` imports pydantree_sitter_grammar only lazily. Pins consistent (`pydantic>=2.11`, `tree-sitter>=0.26` in all four); scanner `.c` files land in the heavy wheel and are pinned by test. Minor: root main dep `tree-sitter-python>=0.23.6` vs its own `python` extra `>=0.23`.
6. **Thin product metadata**; `license = { file = "LICENSE" }` produces no license classifier (PEP 639 `license = "MIT"` cleaner).
7. **`_pydantree_src.pth` fragility:** `devenv.nix:60-66` hardcodes `venv/lib/python3.13` (silently no-ops on a Python bump); prepends `src/` for every venv process — top-level generic names `data`, `examples`, `pydantree` in `src/` shadow any same-named installed package during dev; the dev flow never exercises the actual wheels.
8. **`src/data/python_nodes.py` (1147 lines) is dead weight** — imported only by legacy `src/pydantree/` and `src/examples/demo.py`; not referenced by products or tests; not even shipped by the (mis)configured root wheel.
9. **Repo hygiene:** `dist/` gitignored (clean); no `__pycache__`/`.so`/`.pyc` git-tracked (verified). But `spike-a/`, `spike-a2/` (13 tracked files) remain at repo root against the project's own `.scratch/00X-*` convention, as does root-level `KICKOFF_SPIKE.md`.

---

# Report 3 — pydantree_sitter internals (`_ir_derive`, `_wasm_bridge`) + legacy island

## (a) Top findings, ranked by severity

**1. [BUG — demonstrated] `_ir_derive.py` field `required` is production-order dependent and diverges from the CLI.**
`src/pydantree_sitter/_ir_derive.py:287-294`: a field is seeded at `_Quantity.one()` (required=True) when *first seen*, and the "absent from this production flips required off" loop (291-294) only covers productions processed *after* the field enters the map. Productions *before* the field's first appearance never flip it off. The Rust CLI accumulates `variable_info` across fixed-point iterations, so pass 2 re-visits the field-less production and flips required to false; this port rebuilds state from scratch every `_recompute`, so it never does. Reproduced live:

```python
g.rule("x", tg.choice("a", tg.field("f", tg.ref("b"))))   # field in 2nd branch
# -> {"f": {"required": true, ...}}   WRONG (branch "a" has no field)
g.rule("x", tg.choice(tg.field("f", tg.ref("b")), "a"))   # field in 1st branch
# -> {"f": {"required": false, ...}}  correct
```
Same grammar modulo choice order, different output; the CLI emits `false` for both. The byte-for-byte rust/markdown fixtures happen not to hit this shape, which is exactly why fixture-only verification is insufficient (see finding 5).

**2. [BUG-adjacent — hidden mutable state leak] `_relax_hidden_repeat` leaks across calls and is read outside the fixed point.**
Set only in `_recompute` (`:209-211`), read in `_productions` via `getattr(self, "_relax_hidden_repeat", False)` (`:402`). But `_productions`/`_summarize` are also called *after* `compute()` finishes: `derive_from_ir` calls `d._summarize(content)` for structured aliases (`:900`) and `d._productions(body, set())` in `_anonymous_kinds` (`:951`). At those points the flag holds whatever the *last rule recomputed* left behind — and `compute()` iterates `for name in reachable` over a **set of strings** (`:190`), whose order is hash-randomized. So structured-alias summaries (REPEAT1 required-ness of e.g. markdown's `inline`) can differ across runs depending on PYTHONHASHSEED. The `_anonymous_kinds` call is harmless (only reads `tok`/`named`), the `:900` call is not.

**3. [Design — layering inversion] The "tiny shared seam" imports the heavy package's IR.**
`src/pydantree_sitter/_ir_derive.py:20-40` imports `pydantree_sitter_grammar.ir` at module top; `src/pydantree_sitter/schema.py:298-308` hides it behind a lazy import. `src/pydantree_sitter/pyproject.toml` declares **no** pydantree_sitter_grammar dependency (comment admits it), while `pydantree-pydantree_sitter_grammar` depends on `pydantree-pydantree_sitter` — an undeclared reverse edge that makes the import graph cyclic at the package level, makes `pydantree_sitter` untestable/untypecheckable standalone for a third of its code (974 of ~1670 lines), and means a pydantree_sitter release can be silently broken by a pydantree_sitter_grammar IR rename. Functionally contained (lazy import keeps `import pydantree_sitter` B-free; `pydantree_sitter_grammar/pipeline.py:217` is the only real caller), but it inverts the stated architecture. The fix is cheap and was the original spec: CONCEPT.md §2 — "**Shared (`pydantree_sitter`):** Pydantic models mirroring the `grammar.json` schema". `src/pydantree_sitter_grammar/grammar.py` is 259 lines of pure pydantic (imports only `pathlib`/`typing`/`pydantic`) — move it into pydantree_sitter, have pydantree_sitter_grammar re-export, and both the inversion and the undeclared dependency disappear. Alternative (weaker): move `_ir_derive.py` into pydantree_sitter_grammar and have `pydantree_sitter.schema.derive_from_ir` delegate the other way — but then the "exact path" logic lives with B, which is arguably where derivation machinery belongs anyway.

**4. [Broken packaging] Root wheel references nonexistent `data/`; legacy package cannot import when installed.** (Same as Report 2 finding 4; `tests/test_packaging.py:113` only asserts the *string* `"data"` appears in the config line — it never builds the root wheel, so this is invisible to CI.) Additionally ships console scripts `pydantree` and `demo` pointing into the broken package, plus `examples` and `data` as maximally generic top-level import names.

**5. [Maintainability] The 974-line hand-port's correctness is empirical (calibrated heuristics + frozen fixtures), not structural.**
The CLI derives node-types from the *prepared* grammar (extract_tokens → expand_repeats → flatten_grammar). The port works on the raw IR and simulates the pipeline's outcomes with admitted per-grammar calibrations — `:203-211` literally says "Phase-6.5 calibration (probed against the CLI over the markdown block grammar)". Drift detection is byte-for-byte tests against fixtures pinned to **CLI 0.25.3** (`tests/test_schema.py:224-226`, which even notes "the checked-in repo one is generated by a newer CLI and differs slightly"), plus two toolchain-gated agreement tests that skip when the toolchain is absent. So a newer CLI's node_types.rs changes are undetected until someone hand-regenerates fixtures. Verdict: the port is unusually well-verified for what it is, but three grammars' worth of fixtures ≠ the algorithm (finding 1 proves it).

**6. [Dead but shipped] The legacy island (`src/pydantree` + `src/data` + `src/examples`) is frozen, unused by everything current, partially unrunnable, and still owns the project's name.**
Details in (c). Cost of keeping it in `src/`: `import pydantree` gets a broken frozen wrapper while the real products are `pydantree_sitter/pydantree_sitter/pydantree_sitter_grammar` under pydantree-*branded* dists — "pydantree" means two contradictory things; the dev `.pth` puts all of `src/` on the path so the dead island stays importable and lints/greps keep hitting it.

**7. [Probe-grade code in the shipped core] `_wasm_bridge.py` leaks every resource it creates.**
Reachable only via env-gated `loader.py:127`, so exposure is low, but it ships in the "tiny, pure" seam package whose own `__init__.py` still claims "One module, no more: pydantree_sitter.schema".

## (b) `_ir_derive.py` focused assessment

### Correct or verified-correct parts
- `_Quantity.append`/`union` (`:73-92`) are faithful ports of `ChildQuantity` in node_types.rs — checked line-by-line against upstream semantics.
- Fixed-point **termination** is safe: per-rule state lives in a finite lattice (exists/multiple monotone up, required monotone down, type sets monotone up), `_summarize` is monotone in child states, so from-scratch recompute converges. No termination risk found.
- Hidden-child inheritance and `scaled_by` propagation (`:264-284`), supertype exemption (`:329-332`), hidden-external handling (`:347-351`), and `_process_supertypes` (`:959-974`) look right and are covered by the rust byte-for-byte test.
- The emission shape (`fields: {}` vs absent, `root`/`extra` only-when-true) matches the CLI.

### Wrong or fragile spots (line refs)
1. **`:287-294`** — production-order-dependent field `required` (finding 1, reproduced). Fix: after the production loop, do a second pass unioning `zero()` into every field absent from any production, or track per-field "seen in all productions so far".
2. **`:209-211` + `:402` + `:900`/`:951`** — `_relax_hidden_repeat` instance-state leak with hash-order-dependent value at read sites outside `_recompute` (finding 2). Should be a parameter of `_productions`/`_summarize`, not deriver state.
3. **`:209-211` itself** — the relax rule ("hidden rule whose body is not a bare top-level REPEAT1 gets all its repeats treated as 0+") is a heuristic standing in for the CLI's `expand_repeats` auxiliary-rule construction, calibrated against one grammar (markdown). A hidden rule mixing a required REPEAT1 with an unrelated REPEAT elsewhere in the body relaxes *all* of them (`_contains_repeat` at `:512-525` is body-wide). Uncalibrated grammar shapes are at risk.
4. **Three inconsistent notions of "start rule":** `d.start = grammar.start_rule` (`:158`, used at `:696`), `root = next(iter(grammar_rules))` (`:574`), and `is_start = (i == 0)` (`:787`) / `i > 0` (`:500`, `:508`). If `start_rule` is ever not the first rules-dict key, these silently disagree.
5. **`:456-485` vs `:488-509`** — internal inconsistency in token rename: `_string_usage.walk` deliberately skips TOKEN-wrapped strings ("TOKEN-wrapped strings are DIFFERENT terminals", `:468-469`), yet `_rule_is_renamed`'s anon path for a `foo: token("x")` rule requires `usage.get("x") == 1` — a count that by construction only reflects *bare* `"x"` occurrences. A rule whose body is `token("<string>")` (CLI: renamed to a named terminal `foo`) will here fail the rename, emit a `foo` rule-loop entry with `fields: {}` *plus* an anonymous `"x"` kind. None of the three fixture grammars appears to exercise this; verify against the CLI.
6. **`:601`** — `_step_aliases` unwraps with `_unwrap`, which strips `TokenNode`/`ImmediateTokenNode` too, so `token($.sym)` is treated as a plain symbol reference and adds `aliases[sym].add(None)` — upstream fuses the token and produces no child. Could conjure an own-name entry the CLI doesn't emit.
7. **`:667`** — `aliases[ex.value].add(None)` keys an alias *value* into the symbol-name-keyed dict; if a rule shares that name, it silently gains a `None` alias.
8. **Complexity:** `_productions` for SEQ is a Cartesian product (`:388-394`) — exponential in nested choice-in-seq; and it's recomputed for **every rule on every fixed-point pass** with no memoization. `_variable_is_used` (`:567-592`) is un-memoized recursion over all rules, called once per rule from `_reachable` (`:175-182`) — and `_reachable` itself is computed **twice** (`derive_from_ir:759` and again inside `compute():187`). Fine for rust/markdown; likely painful on C++/TypeScript-scale grammars, with Python recursion-depth risk on deep reference chains.
9. **`:764`/`:788`** — iterates a hash-ordered set of aliases; only exotic collisions make it observable, but combined with 2 the module is not guaranteed deterministic across runs.

### Maintainability verdict
A 974-line hand-port is defensible *given the goal* (byte-identical node-types without the Rust toolchain), and the docstrings' upstream cross-references (node_types.rs, extract_tokens.rs, parse_grammar.rs) are genuinely good. What is not defensible: (a) no pinned upstream *source* reference (a commit hash of the ported node_types.rs) anywhere in the file — "drift detection" is three frozen fixture files from CLI 0.25.3 plus skip-gated toolchain tests; (b) the calibration comments admit the port models outcomes, not the algorithm — porting `expand_repeats` for hidden rules would delete the `_relax_hidden_repeat` heuristic entirely and likely finding 2 with it.

### `_wasm_bridge.py` assessment
ctypes usage is competent (correct `TSNode` struct layout `:38-41`, argtypes/restype declared for everything used, byref error structs) but **probe-grade**:
- **Leaks everything:** `ts_tree_delete` bound (`:83`) but never called — every `parse()` leaks a tree; `ts_parser_delete` bound (`:76`) never called; `ts_wasm_store_delete` never even bound; error `message` char* (`:45`, `:62`, `:115`) never freed.
- **`close()` (`:118-119`)** deletes the engine while the store (and any parser/language bound to it) is still alive — use-after-free if anything is used afterward; nothing enforces lifetime ordering, and `loader.load_grammar_wasm` (`loader.py:127-129`) returns `(language, rt)` and never closes.
- **Silent ABI coupling:** the hand-declared `TSNode` layout and symbol list will corrupt memory, not error, if tree-sitter's ABI shifts.
- CI only exercises the *unavailable* path (`tests/test_wasm.py:43-57`); the real load is env-gated.

Belongs in `.scratch/009-phase7/` (where its own docstring says the evidence lives) with `loader.py` raising `WasmRuntimeUnavailableError` unconditionally, or kept but with a `__del__`-free explicit `close()` story and the leaks fixed. Shipping mitigant: it's only imported lazily behind two env vars, so the passive cost is 180 lines of dead weight, not active risk.

## (c) Dead-code / redundancy inventory (with evidence)

### The legacy island — dead, still shipped
- **`src/pydantree/`** (8 files, ~800 lines): frozen since 2025-07-08 (`git log -1`: `0eb4e14 Updates on first-principles version`). Importers, exhaustively (whole-repo grep): `src/examples/demo.py:34`, `src/examples/view_demo.py:12-13`, `src/examples/file_parse_demo.py:23`, `src/data/python_nodes.py:2` — i.e. **only the island itself**. Zero imports from `src/pydantree_sitter`, `src/pydantree_sitter`, `src/pydantree_sitter_grammar`, `tests/`, or `examples/` (test hits for "pydantree" are dist-name strings). Still shipped by `pyproject.toml:66` and owns the `pydantree` console script (`:69`) — and the wheel is broken as configured (finding 4).
- **`src/data/python_nodes.py`** (1147 lines) + `src/data/__init__.py`: generated output of the legacy generator — `src/examples/demo.py:77` writes it (`out_path = pathlib.Path("src/data/python_nodes.py")`). Imported only by `src/pydantree/views.py:26` and its own `__init__.py:1`. Checked-in generated code, dead with the island.
- **`src/examples/`**: all three target the **legacy** API only (imports above); the current-API examples live at top-level `examples/{bash-extract,devenv-extract,devenv-subset}`. `file_parse_demo.py` is unrunnable on any install: `graph_sitter` (`:22`) appears in no pyproject/lockfile in the repo and isn't installed, and `from pydantree import PyFile` (`:23`) names a symbol `pydantree.__init__` doesn't export (it exports `PyView/PyModule/PyFunction/PyClass`). `demo.py`/`view_demo.py` do import cleanly in the dev venv (verified), but only because the dev `.pth` exposes all of `src/`.

**Recommendation:** delete the island (it's in git history), or move it to `.scratch/`, and either retire the root distribution or repoint it.

### Dead code inside `_ir_derive.py`
- `_is_lexical_rule` (`:528-537`) — defined, never called anywhere in the repo (grep); its own docstring admits it's "kept for the legacy check".
- `_VarInfo.multi_step` (`:147`, computed `:242-246`, stored `:224`) — computed and compared in the fixed point but **never consulted by emission**; only inflates the change-detection tuple.
- `_VarInfo.changed` (`:148`, `:225-226`) — stored attribute used only as the immediate return value; a local would do.
- `_Deriver.word` (`:159`) — assigned, never read.
- `_PREC` (`:45`) and `_PREC_NODES` (`:410`) — identical tuples defined twice.
- `_Quantity.repeat_quantity` (`:94-97`) — an instance method that ignores `self`; both call sites (`:380-381`, `:403`) construct `_Quantity.one()` solely to discard it. Should be a classmethod/module function.
- `_reachable()` computed twice per derivation (`:759` and `:187`) — pure redundant work on the most expensive helper in the file.
- Stale docs: `src/pydantree_sitter/__init__.py:4-5` ("One module, no more") vs the actual four modules; `schema.py:54-57` documents merged-alias `required` overstatement as a "known simplification" while the rule loop (`_ir_derive.py:806-820`) now implements merged-alias semantics — the docstrings disagree about what's simplified.

### Misc
- `src/pydantree_sitter_grammar/schema_tool.py:13-15` references `derive_from_ir` in prose only; actual cross-package usage of the exact path is a single call site, `src/pydantree_sitter_grammar/pipeline.py:217-218` — evidence that relocating either the IR models or `_ir_derive` is a one-file change on the consumer side.
