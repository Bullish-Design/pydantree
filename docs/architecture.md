# pydantree-sitter — architecture & codebase map

This is the working reference for developers new to the codebase. For the
full design argument (why two libraries, the build order, the risks) read
`../.scratch/projects/002-pydantic-treesitter/CONCEPT.md` first (its dated
addendum records the 014 decisions D1–D14). Each phase's findings
(`../.scratch/projects/00X-*/FINDINGS.md`) add the "what changed and why"
record.

---

## 1. The idea in one screen

```
 Product B (author)                          Product A (consume)
 pydantree_sitter_grammar (HEAVY)            pydantree_sitter (LIGHT)
   Rule classes / Grammar DSL -> grammar.json   OutputModel class
   -> tree-sitter generate -> parser.c           |  __match__ = M(...)
   -> gcc -> grammar.so                         \|/
   -> node-schema.json (the CLI byproduct)  typed rows, checks at bind
        |                                        /|\
        +------->  the BUNDLE (4 files) <--------+  Language.load_bundle(dir)
                          |
                     pydantree_sitter (LIGHT, the one package):
                     the node-schema format + the artifact-loading contract
```

- **The model IS the query** (A): the `.scm` is derived from the model and
  never seen. Field names/types/defaults + a one-line `__match__` ancestor
  path declare both the pattern and the output type.
- **B is heavy on purpose**: the Rust CLI + C compiler are B's problem; a
  consumer of A never resolves them (proven at the install boundary).
- **The bridge is the differentiator**: the schema IS the CLI's
  `node-types.json` byproduct (tracked by construction, D3), and A runs
  model↔grammar + capture↔type checks at **bind time** — `lang.extractor(Model)`
  — before any text is parsed.

## 2. The two packages

All under `src/`, each with its own `pyproject.toml` (the "pyproject per
package" layout — see §4 of development.md). Import packages
`pydantree_sitter` / `pydantree_sitter_grammar`; PyPI names
`pydantree-sitter` / `pydantree-sitter-grammar` (collision-proof, D1).

| package | weight | contents | depends on |
|---|---|---|---|
| `pydantree_sitter` | light | `schema.py` (NodeSchema — the byproduct format), `loader.py` (the loading contract + bundle_format), `markers.py` (inert markers), `spec.py` (MatchSpec + OutputModel), `binding.py` (Language/Extractor), `compiler.py` (the ONE compiler), `emit.py` (internal .scm emitter), `match.py` (the ONE ancestor matcher), `materialize.py` (one kwargs builder), `valuemap.py` (ValueMap + propose_value_map), `codegen.py` (real typed CST accessors), `errors.py` (the taxonomy) | pydantic, tree-sitter |
| `pydantree_sitter_grammar` | heavy | `ir.py` (GrammarModel — the grammar.json mirror), `builder.py` (the DSL), `rules.py` (the rule-class surface + assemble/module_rules), `checks.py` (static analysis), `conflicts.py` (GLR conflict remapping), `expressions.py` (precedence ladders), `corpus.py` (the corpus harness), `pipeline.py` (generate → gcc → bundle; write_bundle; build_from_source_dir), `scanners/` (the scanner library) | pydantree-sitter, pydantic, tree-sitter, **plus the CLI + gcc at build time** |

The root `pyproject.toml` is the uv-workspace + dev-tooling envelope only
(the legacy island and the root distribution were deleted in the 014
refactor Phase 1).

## 3. The seams (what the project has proven)

1. **The install boundary** (GO): a fresh venv with only the light wheel
   runs the full checked extraction; `import pydantree_sitter_grammar` fails
   (the seam does not leak). The heavy wheel carries the scanner package
   data and depends on the light package (A never imports B).
2. **The artifact boundary** (GO): the **bundle** is one artifact + one
   loading contract —

   ```
   bundle/
     grammar.so          the compiled parser (export tree_sitter_<name>)
     node-schema.json    the CLI byproduct (D3)
     tree-sitter.json    metadata: {bundle_format, name, artifact, schema,
                          abi, toolchain, value_map?}
     loader.py           a thin shim -> pydantree_sitter.loader.load_bundle
   ```

   `Language.load_bundle(dir)` is the one-line consumer (keeps the .so lib
   alive, F-A10). `bundle_format` versions the contract (D12): absent = 1
   (accepted); unknown >2 = `BundleError` naming both versions.
3. **The grammar-ownership boundary** (GO, D3): the schema IS the CLI's
   `node-types.json` byproduct — a B-built bundle's `node-schema.json` is the
   generate run's `node-types.json` copied byte-for-byte, and the community
   path (`build_from_source_dir`) derives from the same CLI byproduct. The
   `node_types.rs` hand-port is deleted: the schema has exactly one source.

### 3.1 The wasm seam (assessed — no-go)

A bundle's metadata may name a `.wasm` artifact. `pydantree_sitter.loader`
dispatches on the extension and raises `WasmRuntimeUnavailableError`
unconditionally: the probe bridge moved out of the shipped seam
(`.scratch/projects/009-phase7/wasm_bridge.py`), and a wasm load means
forking the binding (py-tree-sitter 0.26 has no wasm store), not pinning a
package. Per-platform native wheels carry the portability story. See
`../.scratch/projects/002-pydantic-treesitter/CONCEPT.md` Appendix A and
`../.scratch/projects/009-phase7/FINDINGS.md`.

## 4. The pipeline (B's build)

```
Grammar -> IR (grammar.json) -> tree-sitter generate --json -> src/parser.c
   (+ scanner.c) -> gcc -O2 -fPIC -shared -> name.so
```

- `pipeline.build(model, scanner=..., check=True)` — content-addressed cache
  keyed on `sha256(grammar.json) + scanner.c digest + toolchain version`;
  on a hit it skips generate+gcc entirely. `check=True` (default, D10) runs
  the static analyzer first. `build_builder` wraps it for the DSL and remaps
  generator conflicts from the SAME run's `--json` stderr to the author's
  per-production DSL sites (`GrammarConflictError`). `build_loop` is the
  fix-one-rerun loop.
- `build_from_source_dir(src_dir)` — a community grammar source dir through
  the same pipeline (check=False — community grammars aren't ours to
  analyze; never touches the author's checkout). `write_bundle(result, dir)`
  is the ONE bundle writer.
- **ABI facts**: the CLI needs a `tree-sitter.json` with
  `{"metadata": {"version": "0.1.0"}}` to emit ABI 15 (else ABI 14 — still
  loads; bindings 0.26 accept ABI 13–15). The bundle's `abi` metadata reads
  `tree_sitter.LANGUAGE_VERSION` when available (env as override only).
- **Errors**: `GenerateError` / `CompileError` carry the raw subprocess
  output; `ExternalScannerRequiredError` fires BEFORE gcc's link failure when
  a grammar declares externals but no scanner was supplied.

## 5. The schema bridge (the differentiator)

- **One source** (D3): the schema IS the CLI's `node-types.json` byproduct.
  A B-built bundle's `node-schema.json` is the generate run's
  `node-types.json` copied byte-for-byte (a by-construction contract, pinned
  in `tests/test_pipeline.py`); the community path runs the CLI over a
  grammar source dir (accepts the standard `src/grammar.json` community
  layout). `NodeSchema.from_node_types_json` / `derive_from_node_types` are
  the only parse path.
- **The bind (D5)**: `lang.extractor(Model)` runs all checks once —
  model↔grammar path/capture checks, capture↔type checks (ValueMap-backed
  kind ladder), and value-shape resolution — and compiles the query against
  THAT language. The compiled state lives on the Language instance, keyed by
  (model, strict): no class-level caches, no global registry (F-A1's silent
  cross-language cache is impossible by construction).
- **Value shapes (D6)**: record-mode shapes consume ONLY (schema, ValueMap).
  `propose_value_map(schema)` is the draft generator (reviewed, committed —
  never silent inference); `JSON_VALUE_MAP` is the schema-less JSON family.

## 6. The external-scanner mechanism (summary — full contract in
[scanner-library.md](scanner-library.md))

- A grammar declares externals and the build takes `scanner=<path to
  scanner.c>`; the cache key content-addresses the scanner.c.
- Library table: `scanner_for(name)` → the canonical scanner path. Five
  seeds: `indent_scanner.c` (pymini), `heredoc_scanner.c` (hmini),
  `matched_delimiter_scanner.c` (dmini), `py_indent_scanner.c` (pyindent),
  `bash_heredoc_scanner.c` (bashmini).
- Two gotchas (proven facts, design for them): the lexer calls the scanner
  **mid-whitespace** (skip it first), and **multiple externals can be valid
  in one parser state** (the source disambiguates).

## 7. Module map (where the code lives)

```
src/pydantree_sitter/
  markers.py         the inert markers (M, capture/capture_kind/source_meta/
                     derived, Matches/Eq/AnyOf/NodeKind/Unescaped, RawQuery)
  spec.py            MatchSpec + derive_spec + OutputModel/DerivingMeta
  schema.py          NodeSchema, NodeTypeInfo, derive_from_node_types
                     (the schema IS the CLI byproduct)
  loader.py          load_grammar_so, load_bundle (bundle_format), the wasm
                     dispatch + error
  valuemap.py        ValueMap + JSON_VALUE_MAP + propose_value_map
  compiler.py        the ONE compiler: MatchSpec + Language -> _Compiled
                     (checks, shape inference, query emission plan)
  emit.py            the internal .scm emitter (not public, D11)
  match.py           the ONE ancestor-path matcher + anchor merge
  materialize.py     the ONE kwargs builder, Span, unescape, MatchFailure
  binding.py         Language + Extractor (the explicit bind, D5)
  codegen.py         generate_typed_api (REAL typed CST accessors, D7)
  errors.py          the error taxonomy (§1.3)
src/pydantree_sitter_grammar/
  ir.py              the IR models (GrammarModel mirror of grammar.json)
                     with the _site private attr (D8)
  builder.py         the author DSL (Grammar, rule/seq/choice/repeat/...,
                     Ladder, prec*, caller_site/site_of)
  rules.py           the RULE-CLASS surface (Rule/Pattern/Token/External +
                     mixins, annotation compilation, assemble/module_rules)
  patterns.py        the regex-string helpers for __pattern__
  checks.py          author-time static analysis (run_checks/errors/warnings)
  conflicts.py       generator conflict output -> per-production DSL sites
  expressions.py     expression() + semantic_smoke + DEFAULT_PRECEDENCE_CORPUS
  corpus.py          Corpus/corpus_case + renderers + snapshots
  pipeline.py        build/build_builder/build_loop, write_bundle,
                     build_from_source_dir, caching, errors
  language.py        load_language / parse (the thin load wrapper)
  scanners/          the scanner library (five .c seeds + the table)
tests/
  conftest.py        src-first resolution + the toolchain marker + hermetic
                     cache isolation
  test_*.py          per-surface suites; tests/fixtures/ holds the promoted
                     mini-grammars + consumers + evidence (PROVENANCE.md)
.scratch/projects/00X-*/      per-phase explorations: FINDINGS.md + evidence/ + probes
```

## 8. Durable facts (verified, do not re-derive)

1. tree-sitter CLI **0.25.3**, bindings **0.26.0** (LANGUAGE_VERSION=15,
   MIN_COMPATIBLE=13), gcc **14.2.1**, pydantic **2.13.4**, Python 3.13.
2. The bundle is one artifact + one loading contract (`pydantree_sitter.loader`
   + `Language.load_bundle`); `bundle_format` 2 is the current, 1 is
   accepted.
3. The `.so` loads via a PyCapsule named `"tree-sitter.Language"`; the
   export symbol is `tree_sitter_<name>` (recorded in the bundle metadata).
4. The indentation scanner's canonical cadence: mark_end before the loop,
   the newline SKIPPED (zero-width NEWLINE), comment-lines count as
   newlines, EOF flushes DEDENTs, blocks are `INDENT statements DEDENT`.
5. Two scanner gotchas: mid-whitespace scans; multiple externals valid in
   one parser state.
6. Dev flow: no pip, uv only; the devenv manages the venv with `uv sync`
   (uv workspace in `pyproject.toml`, `--no-install-workspace`) and a
   `_pydantree_src.pth` resolves both packages straight from `src/` — edits
   are live immediately; `tests/conftest.py` resolves `src/` first as
   belt-and-suspenders. `uv lock` after dependency changes.
7. The schema tracks the INSTALLED CLI's byproduct by construction (the
   community tool uses the installed CLI's own node-types.json) — a newer
   CLI can't silently drift from the schema.
8. Wasm: real artifact + runtime + parse exist (Phase-7 evidence); the
   verdict is no-go for A's dependency budget — the loader seam raises the
   clear error.

## 9. Where to start reading

1. `../.scratch/projects/002-pydantic-treesitter/CONCEPT.md` — the whole idea
   (the dated addendum records the 014 decisions).
2. `src/pydantree_sitter/__init__.py` — Product A's public surface in one view.
3. `src/pydantree_sitter_grammar/__init__.py` — Product B's public surface.
4. `src/pydantree_sitter/loader.py` + `src/pydantree_sitter/schema.py` — the seam.
5. `tests/test_oracles.py` + `tests/oracles/` — the observable-behavior
   contract across the refactor.
