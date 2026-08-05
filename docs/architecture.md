# pydantree — architecture & codebase map

This is the working reference for developers new to the codebase. For the
full design argument (why two libraries, the build order, the risks) read
`../.scratch/projects/002-pydantic-treesitter/CONCEPT.md` first. Each phase's findings
(`../.scratch/projects/00X-*/FINDINGS.md`) add the "what changed and why" record.

---

## 1. The idea in one screen

```
 Product B (author)                          Product A (consume)
 tsgrammar (HEAVY)                           tsquery (LIGHT)
   Grammar DSL -> grammar.json                  OutputModel class
   -> tree-sitter generate -> parser.c            |  __match__ = M(...)
   -> gcc -> grammar.so                          \|/
   -> derive schema -> node-schema.json     typed rows, checks before parse
        |                                        /|\
        +------->  the BUNDLE (4 files) <--------+  Language.load_bundle(dir)
                          |
                     tscore (TINY, shared):
                     the node-schema format + the artifact-loading contract
```

- **The model IS the query** (A): the `.scm` is derived from the model and
  never seen. Field names/types/defaults + a one-line `__match__` ancestor
  path declare both the pattern and the output type.
- **B is heavy on purpose**: the Rust CLI + C compiler are B's problem; a
  consumer of A never resolves them (proven at the install boundary, Phase 6).
- **The bridge is the differentiator**: `tscore` derives a node-schema from
  the grammar, and A runs model↔grammar + capture↔type checks against it
  *before any text is parsed*.

## 2. The three packages

All under `src/`, each with its own `pyproject.toml` (the "pyproject per
package" layout — see §4 of development.md). The import packages are
`tscore` / `tsquery` / `tsgrammar`; the PyPI distribution names are
pydantree-branded (`pydantree-tscore`, `pydantree-tsquery`,
`pydantree-tsgrammar`) because the bare `tsquery` name is taken on PyPI.

| package | weight | contents | depends on |
|---|---|---|---|
| `tscore` | tiny, pure Python | the node-schema format (`schema.py`), the exact-path IR derivation (`_ir_derive.py`), the artifact-loading contract (`loader.py` incl. the wasm seam `_wasm_bridge.py`) | pydantic, tree-sitter |
| `tsquery` (A) | light | `typed.py` (OutputModel + Language), `dsl.py` (the query builder), `materialize.py`, `shapes.py`, `schema.py` (schema-rebuilt derivation), `stubs.py` (Job-2 `.pyi`) | tscore, pydantic, tree-sitter |
| `tsgrammar` (B) | heavy | `grammar.py` (IR), `builder.py` (the DSL), `checks.py` (static analysis), `conflicts.py` (GLR conflict remapping), `expressions.py` (precedence ladders), `corpus.py` (the corpus harness), `pipeline.py` (generate → gcc → bundle), `schema_tool.py` (community grammars), `scanners/` (the scanner library) | tscore, pydantic, tree-sitter, **plus the CLI + gcc at build time** |

The root `pyproject.toml` is the LEGACY distribution only (the deprecated
`src/pydantree` wrapper — frozen, untouched) plus the dev flow.

## 3. The three seams (what the project has proven)

1. **The install boundary** (Phase 6, GO): a fresh venv with only the light
   wheels runs the full checked extraction; `import tsgrammar` fails (the
   seam does not leak). The heavy wheel carries the scanner package data;
   the light wheels never resolve B's toolchain.
2. **The artifact boundary** (Phase 5/6, GO): the **bundle** is one artifact
   + one loading contract —

   ```
   bundle/
     grammar.so          the compiled parser (export tree_sitter_<name>)
     node-schema.json    the derived bridge artifact
     tree-sitter.json    metadata: {name, artifact, schema, abi, toolchain}
     loader.py           a 7-line shim -> tscore.loader.load_bundle
   ```

   `tsquery.Language.load_bundle(dir)` is the one-line consumer. The `.so`
   is loaded via a PyCapsule named `"tree-sitter.Language"`; integer-pointer
   loading is deprecated in 0.26.
3. **The grammar-ownership boundary** (Phase 6, GO): the schema derivation
   is **byte-for-byte** with the CLI's `node-types.json` over FOUR real
   grammars (rust, python, markdown, markdown-inline) — the exact path
   (`tscore._ir_derive.derive_from_ir`) mirrors CLI 0.25.3's
   `node_types.rs`; the community path (`tsgrammar.schema_tool`) derives from
   the CLI's own byproduct, so it tracks the installed CLI by construction.

### 3.1 The wasm seam (Phase 7, assessed)

A bundle's metadata may name a `.wasm` artifact. `tscore.loader` dispatches
on the extension: without a wasm-capable runtime it raises
`WasmRuntimeUnavailableError` (the exact state of the path); with the
probe's runtime wired (env-pointed `TSGRAMMAR_WASM_LIB` /
`TSGRAMMAR_WASMTIME_LIB`) it loads through a real wasmtime bridge. The
verdict: **wasm works** (measured 1.6× the native parse cost over rust) but
is **not worth A's dependency budget** — py-tree-sitter 0.26 has no wasm
store, so a wasm load means forking the binding, not pinning a package.
Per-platform native wheels carry the portability story. See
`../.scratch/projects/009-phase7/FINDINGS.md`.

## 4. The pipeline (B's build)

```
Grammar DSL -> IR (grammar.json) -> tree-sitter generate -> src/parser.c
   (+ scanner.c) -> gcc -O2 -fPIC -shared -> name.so
```

- `tsgrammar.pipeline.build(model, scanner=...)` — content-addressed cache
  keyed on `sha256(grammar.json) + scanner.c digest + toolchain version`;
  on a hit it skips generate+gcc entirely. `build_builder` wraps it for the
  DSL and remaps generator conflicts to the author's per-production DSL
  sites (`GrammarConflictError`). `build_loop` is the fix-one-rerun loop:
  it yields each conflict error (naming the DSL site + the generator's
  suggested fix), calls your `fix(error, g)`, and re-runs.
- **ABI facts**: the CLI needs a `tree-sitter.json` with
  `{"metadata": {"version": "0.1.0"}}` to emit ABI 15 (else ABI 14 — still
  loads; bindings 0.26 accept ABI 13–15).
- **Errors**: `GenerateError` / `CompileError` carry the raw subprocess
  output; `ExternalScannerRequiredError` fires BEFORE gcc's link failure when
  a grammar declares externals but no scanner was supplied.
- `BuildResult.package(dir)` produces the 4-file bundle.

## 5. The schema bridge (the differentiator)

- **Exact path** (`tscore.schema.derive_from_ir(model)`): a faithful port of
  the CLI's node-types derivation — reachability pruning, aliases-by-symbol,
  hidden-rule inherit steps, supertype handling, STRING-only anonymous kinds.
  Byte-for-byte with CLI 0.25.3's node-types.json over rust/python/markdown/
  markdown-inline (hermetic tests in `tests/test_schema.py`).
- **Community path** (`tsgrammar.schema_tool.derive_schema_for_dir`): run
  the CLI over a grammar source dir (accepts the standard `src/grammar.json`
  community layout), derive from the produced `node-types.json`. One command;
  `build_community_bundle` goes all the way to a shippable bundle.
- **The checks (Jobs 1/3/4)**: A's `validate_with(language, schema=...)`
  runs model↔grammar (path/fields against the schema), value-shape
  derivation, and capture↔type checks before any text is parsed. The schema
  is bound to a `Language` INSTANCE (Phase 6: the old name-keyed registry
  leaked a bound schema into every later schema-less consumer; a nameless
  language is refused registration — `register=True` opts into the
  name-keyed convenience).

## 6. The external-scanner mechanism (summary — full contract in
[scanner-library.md](scanner-library.md))

- A grammar declares externals (`g.external(tg.tok("NEWLINE"), ...)`) and the
  build takes `scanner=<path to scanner.c>`. Externals without a scanner →
  `ExternalScannerRequiredError`; the cache key content-addresses the
  scanner.c.
- Library table: `tsgrammar.scanner_for(name)` → the canonical scanner path.
  Five seeds: `indent_scanner.c` (pymini), `heredoc_scanner.c` (hmini),
  `matched_delimiter_scanner.c` (dmini), `py_indent_scanner.c` (pyindent —
  real Python logical-line semantics), `bash_heredoc_scanner.c` (bashmini —
  the multi-heredoc pending queue).
- Two gotchas (proven facts, design for them): the lexer calls the scanner
  **mid-whitespace** (skip it first), and **multiple externals can be valid
  in one parser state** (the source disambiguates — a `<` is always a
  heredoc START).

## 7. Module map (where the code lives)

```
src/tscore/
  schema.py          NodeSchema, NodeTypeInfo, derive_from_ir, derive_from_node_types
  _ir_derive.py      the exact-path derivation (the node_types.rs port)
  loader.py          load_grammar_so, load_bundle, the wasm dispatch + error
  _wasm_bridge.py    the wasmtime ctypes bridge (Phase-7 probe runtime)
src/tsquery/
  typed.py           OutputModel, M, capture/capture_kind/source_meta, Language,
                     the markers (Matches/Eq/AnyOf/NodeKind/Unescaped), checks
  dsl.py             the internal query builder (node/cap/Query) — NOT public
  materialize.py     Span, coercion, diagnostics, failures
  shapes.py          the record value-shape derivation
  schema.py          schema_derive (Jobs 1/3/4 over the bound schema)
  stubs.py           generate_stubs (Job-2 .pyi from the schema)
src/tsgrammar/
  grammar.py         the IR models (GrammarModel mirror of grammar.json)
  builder.py         the author DSL (Grammar, rule/seq/choice/repeat/...,
                     Ladder, prec*)
  rules.py           the RULE-CLASS surface ("the model IS the rule"):
                     Rule/Pattern/Token/External + the behavioral mixins,
                     the metaclass registry (module-scoped), annotation
                     compilation, assemble() — sugar that compiles into
                     builder.py and touches nothing else
  patterns.py        the regex-string helpers (ident/integer/quoted/slug/
                     path_literal/dotted_path/rest_of_line) for __pattern__
  checks.py          author-time static analysis (run_checks/errors/warnings)
  conflicts.py       generator conflict output -> per-production DSL sites
                     (rule classes provide class + attribute sites)
  expressions.py     expression() + semantic_smoke + DEFAULT_PRECEDENCE_CORPUS
  corpus.py          Corpus/corpus_case + renderers + snapshots
  pipeline.py        build/build_builder/build_loop, caching, bundles, errors
  schema_tool.py     community schema path + build_community_bundle
  language.py        load_language / parse (the thin load wrapper)
  scanners/          the scanner library (five .c seeds + the table)
tests/
  conftest.py        resolves src/ first (the editable-staleness mitigation)
  test_*.py          per-surface suites (see development.md)
.scratch/projects/00X-*/      per-phase explorations: FINDINGS.md + evidence/ + probes
                     + the mini-grammars (pymini/hmini/dmini/pyindent/bashmini)
```

## 8. Durable facts (verified, do not re-derive)

1. tree-sitter CLI **0.25.3**, bindings **0.26.0** (LANGUAGE_VERSION=15,
   MIN_COMPATIBLE=13), gcc **14.2.1**, pydantic **2.13.4**, Python 3.13.
2. The bundle is one artifact + one loading contract (tscore.loader +
   `Language.load_bundle`).
3. The `.so` loads via a PyCapsule named `"tree-sitter.Language"`; the
   export symbol is `tree_sitter_<name>` (recorded in the bundle metadata).
4. The indentation scanner's canonical cadence: mark_end before the loop,
   the newline SKIPPED (zero-width NEWLINE), comment-lines count as
   newlines, EOF flushes DEDENTs, blocks are `INDENT statements DEDENT`.
5. Two scanner gotchas: mid-whitespace scans; multiple externals valid in
   one parser state.
6. Dev flow: no pip, uv only; the devenv manages the venv with `uv sync`
   (uv workspace in `pyproject.toml`, `--no-install-workspace` so the src/*
   members are never copied) and a `_pydantree_src.pth` resolves
   tscore/tsquery/tsgrammar straight from `src/` — edits are live
   immediately, staleness is impossible; `tests/conftest.py` resolves `src/`
   first as belt-and-suspenders. `uv lock` after dependency changes.
7. The exact-path derivation is byte-for-byte with CLI 0.25.3 over FOUR real
   grammars — a newer CLI's node-types.json can drift (the community tool
   path sidesteps this by using the installed CLI's own byproduct).
8. Wasm: real artifact + runtime + parse exist (Phase-7 evidence); the
   verdict is no-go for A's dependency budget (binding fork + 16MB wasmtime
   + 1.6× perf) — the loader seam is the extension point.

## 9. Where to start reading

1. `../.scratch/projects/002-pydantic-treesitter/CONCEPT.md` — the whole idea.
2. `src/tsquery/typed.py` module docstring — Product A's surface.
3. `src/tsgrammar/__init__.py` — Product B's full public surface in one view.
4. `src/tscore/loader.py` + `src/tscore/schema.py` — the seam.
5. `../.scratch/projects/009-phase7/FINDINGS.md` — the most recent verdicts (wasm +
   the scanner library).
6. `tests/test_scanners.py` + `tests/test_wasm.py` — how the newest surfaces
   are pinned.
