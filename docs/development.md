# pydantree — development workflow

How to work on this codebase day to day. Read [architecture.md](architecture.md)
first for the map; this is the "how do I actually run things" doc.

## 1. The environment

- **`devenv shell`** is the entry point for everything (it configures the
  nix shell: Python 3.13 + venv, `uv`, the tree-sitter CLI 0.25.3, gcc
  14.2.1). Always run commands through it:

  ```bash
  devenv shell -- python -m pytest tests/
  devenv shell -- python -c "import tsgrammar as tg; ..."
  ```

- **The venv is managed by `uv sync`** (`languages.python.uv.sync.enable` in
  devenv.nix). On shell entry devenv runs `uv sync --all-extras` against the
  uv workspace (`pyproject.toml` → `uv.lock`), checksum-cached on
  `pyproject.toml` + interpreter + args, so it only actually syncs when
  those change. The root project (the dev-tooling envelope) + dev extras
  (pytest, ruff, mypy, black, coverage, tree-sitter-json/python) land in the
  managed venv (`.devenv/state/venv` — devenv points uv there via
  `UV_PROJECT_ENVIRONMENT`; there is no `.venv` in the repo root).
- **After changing dependencies** (in `pyproject.toml` or a member's), run
  `uv lock` once — the devenv sync uses `--frozen` and will fail loudly if
  the lockfile is stale (that's the signal to lock).

### The staleness non-issue (how it's prevented)

The old flow (`uv pip install -e . -e src/tscore -e src/tsquery -e
src/tsgrammar`) placed a COPY of each package in site-packages, so ANY
change under `src/` was invisible to plain imports until you re-ran the
install — a chronic dev-flow trap. The devenv now prevents it by
construction:

- devenv syncs with **`--no-install-workspace`** (its default): the three
  `src/*` packages are NEVER copied into the venv.
- The `pydantree:venv-src-pth` task writes a `_pydantree_src.pth` into the
  venv whose `import` line runs `sys.path.insert(0, "<repo>/src")` during
  site-packages processing — so every process using the venv resolves
  tscore/tsquery/tsgrammar **straight from `src/`**, and edits are live
  immediately (no reinstall, no stale copy).
- `tests/conftest.py` still resolves `src/` first (belt-and-suspenders, and
  it keeps the suite honest if the devenv is bypassed).

## 2. Tests

```bash
devenv shell -- python -m pytest tests/            # the full suite (fast, ~40s)
devenv shell -- python -m pytest tests/test_scanners.py -q
devenv shell -- python -m pytest tests/test_wasm.py -q
```

- The suite is the pinned record: 170 green + 1 skip (post Phase 7). The
  count is captured in each phase's FINDINGS.
- Tests that need the tree-sitter CLI / gcc skip themselves when the
  toolchain is absent (`TOOLCHAIN_AVAILABLE` guards).
- **test_wasm.py** has env-gated tests: with
  `TSGRAMMAR_WASM_LIB`/`TSGRAMMAR_WASMTIME_LIB` set (the Phase-7 probe's
  runtime) the real wasm load runs; without them it skips.
- **The pipeline caches builds** under `~/.cache/tsgrammar` (override with
  `TSGRAMMAR_CACHE`). A stale cache made from an older scanner/grammar is a
  classic "my fix doesn't work" gotcha — when iterating on a scanner, point
  `cache_dir=` at a fresh temp dir, or delete the cache entry.

## 3. Evidence discipline (the project's convention)

- Findings live in `../.scratch/projects/00X-*/FINDINGS.md`; **raw outputs are saved
  verbatim** under `../.scratch/projects/00X-*/evidence/` (e.g. `rA_wasm_perf.txt`).
- Probes/experiments are committed as `.scratch/projects/00X-*/probe_*.py` so a
  verdict can be re-run. Each FINDINGS "Re-run" section lists the commands.
- Commit messages carry a scope prefix + the finding, e.g.:
  `tsgrammar: scanner library — ...`, `phase7: wasm probe — ...`,
  `tscore: ...`. Commit after each meaningful step.

## 4. Package layout mechanics

- Each product has its own `pyproject.toml` INSIDE its package dir
  (`src/tscore/pyproject.toml`, ...) with
  `[tool.hatch.build.targets.wheel.force-include] "." = "tsgrammar"` — the
  dir's contents (including `scanners/*.c`) become the wheel's package data.
  Known artifact: `pyproject.toml`/`PKG-INFO` ride inside the wheel package
  (harmless, documented).
- **Adding a scanner**: put the `.c` in `src/tsgrammar/scanners/`, add a
  `*_scanner_path()` helper + a `scanner_for()` entry, re-export from
  `tsgrammar/__init__.py` (`__all__` too). The dev venv resolves `src/`
  directly (the `_pydantree_src.pth`), so new files are immediately
  importable — no reinstall. Verify the heavy wheel carries it (see
  `tests/test_packaging.py::test_heavy_wheel_carries_the_scanner_and_0_26_pin`).
- **The mini-grammar pattern**: every scanner seed has a mini-grammar module
  in `../.scratch/projects/` (pymini, hmini, dmini, pyindent, bashmini) with
  `GOOD`/`GOOD_EXPECTED` (+ semantic case constants) used by
  `tests/test_scanners.py`. The expected sexps are hand-computed from the
  grammar's INTENT — the corpus pins semantics, and a wrong expectation is an
  author bug (see the corpus harness section in the user guide).

## 5. Debugging tips

- **Parse-error walker** (the standard helper, reused across tests):

  ```python
  tree = tg.parse(lang, text)
  errs = []
  def walk(n):
      if n.type == "ERROR" or n.is_missing:
          errs.append((n.type, n.start_point.row + 1))
      for c in n.children:
          walk(c)
  walk(tree.root_node)
  ```

- **Rendering**: `tg.render(tree.root_node)` (sexp, anonymous kept) and
  `tg.render_compact(tree.root_node)` — `print(tree.root_node)` shows the
  tree too but the renderers are what the corpus compares.
- **A scanner that never fires**: add a `fprintf(stderr, ...)` at the top of
  `scan()` to see when/where it is called; check `valid_symbols[]` values.
  Two recurring causes: the mid-whitespace dispatch gating on the raw
  lookahead (skip whitespace first), and returning a START decline without
  falling through to BODY when both are valid in one state (see
  [scanner-library.md](scanner-library.md) §3).
- **Inspect a generated parser**: `tests/fixtures/rust/` and the pipeline
  cache contain generated `src/parser.c` — grep
  `ts_external_scanner_states` / `ts_lex_modes` to verify the scanner wiring.

## 6. The phase workflow (when the work is a phase)

1. Copy the kickoff prompt into `../.scratch/projects/00X-*/KICKOFF_*.md`.
2. Baseline: `python -m pytest tests/` (capture the count).
3. Work in steps; commit after each meaningful step; save raw outputs
   verbatim under `evidence/`.
4. Finish with `FINDINGS.md`: the verdict (go / go-with-changes / no-go)
   with evidence, the re-assessed risks, and the single most important next
   step.
5. Push. (The repo is pushed to `origin/main`.)
