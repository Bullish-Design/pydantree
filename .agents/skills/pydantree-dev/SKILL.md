---
name: pydantree-dev
description: Develop the pydantree library itself (tscore/tsquery/tsgrammar). Use when editing library code, running the test suite, debugging builds or scanners, or making changes that touch the package layout, pipeline, loader, or schema. Includes the devenv/uv workflow, the editable-install staleness caveat, module map, and evidence/commit conventions.
---

# pydantree — developing the library

Work on the pydantree codebase: `src/tscore` (shared seam), `src/tsquery`
(Product A, consumption), `src/tsgrammar` (Product B, authoring).

## Read first

- `../../docs/architecture.md` — the module map, the three seams, the durable facts.
- `../../docs/development.md` — the workflow (this file is the cheat sheet).
- `../../.scratch/002-pydantic-treesitter/CONCEPT.md` — the full design argument.
- The latest phase verdict: `../../.scratch/009-phase7/FINDINGS.md`.

## Environment (mandatory)

- **Everything runs through `devenv shell`**:
  ```bash
  devenv shell -- python -m pytest tests/
  ```
- **No pip. uv only.** Packages are installed editable:
  ```bash
  uv pip install -e . -e src/tscore -e src/tsquery -e src/tsgrammar
  ```
- **Editable-install staleness caveat (it WILL bite):** the editable installs
  place a COPY of each package in site-packages that shadows the `src/` .pth
  entry — ANY change under `src/` (in-place, rewrite, or NEW file) is
  invisible to plain `import` until you re-run the `uv pip install` line. The
  test suite resolves `src/` first via `tests/conftest.py`, so the SUITE is
  always current — ad-hoc `python -c` probes outside the suite are what get
  bitten. When a probe disagrees with the suite, suspect this before the
  code.

## Commands

```bash
devenv shell -- python -m pytest tests/            # full suite (fast, ~40s)
devenv shell -- python -m pytest tests/test_scanners.py -q
devenv shell -- python -m pytest tests/test_wasm.py -q
```

## Key facts to not re-derive

- tree-sitter CLI 0.25.3, bindings 0.26.0 (ABI 13–15), gcc 14.2.1,
  pydantic 2.13.4. The CLI needs a `tree-sitter.json` with
  `{"metadata": {"version": "0.1.0"}}` for ABI 15.
- The bundle = grammar.so + node-schema.json + tree-sitter.json + loader.py;
  `Language.load_bundle(dir)` is the one-line consumer.
- The pipeline cache (`~/.cache/tsgrammar`, or `TSGRAMMAR_CACHE`) content-
  addresses grammar.json + scanner.c + toolchain. A stale cache is a classic
  "my fix doesn't work" gotcha — use a fresh `cache_dir=` when iterating.
- Tests that need the CLI/gcc self-skip when the toolchain is absent.
- The wasm seam: `tscore.loader` dispatches on the artifact extension; wasm
  loads only with TSGRAMMAR_WASM_LIB / TSGRAMMAR_WASMTIME_LIB set (the
  Phase-7 probe runtime). Verdict: no-go for A's dependency budget.
- Two scanner gotchas: mid-whitespace calls (skip first) and multiple
  externals valid in one state (fall through when the source disambiguates).
  See `../../docs/scanner-library.md`.

## Conventions

- Findings go in `../../.scratch/00X-*/FINDINGS.md`; raw outputs are saved
  verbatim under `../../.scratch/00X-*/evidence/`; probes are committed as
  `probe_*.py` so verdicts re-run.
- Commit messages carry a scope prefix + the finding:
  `tsgrammar: ...`, `tscore: ...`, `phase7: ...`.
- Adding a NEW package file (e.g. a scanner .c or a module) requires: the
  file, the registration (scanner_for table / __all__ / pyproject
  force-include), the tests, and the editable reinstall.

## Debugging

- Parse-error walker (standard helper):
  ```python
  tree = tg.parse(lang, text)
  errs = []
  def walk(n):
      if n.type == "ERROR" or n.is_missing: errs.append((n.type, n.start_point.row + 1))
      for c in n.children: walk(c)
  walk(tree.root_node)
  ```
- Render trees with `tg.render(root)` / `tg.render_compact(root)` (the
  corpus renderers) — they show anonymous tokens and extras.
- A scanner that never fires: add `fprintf(stderr, ...)` at the top of
  `scan()`; check `valid_symbols[]`; verify the generated parser.c's
  `ts_external_scanner_states` / `ts_lex_modes` wiring.
