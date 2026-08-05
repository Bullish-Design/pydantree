# pydantree

Treesitter, but more Pydantic.

Two cooperating libraries over tree-sitter, bound by a shared seam
(`tscore`):

- **`tsquery` (A)** — declare an `OutputModel` (**the model IS the query**:
  field names, types, defaults, and a one-line `__match__` path) and get
  typed, schema-checked extraction over any community grammar — no `.scm`,
  no query DSL, no manual coercion.
- **`tsgrammar` (B)** — author a tree-sitter grammar as a composable Pydantic
  DSL that compiles to `grammar.json` → parser → a shippable bundle.

```python
from tsquery import M, NodeKind, OutputModel, capture
import tree_sitter_rust

class RustFn(OutputModel):
    __match__ = M("source_file", "function_item")
    name: str = capture("name")
    return_type: str | None = capture("return_type")

rows = RustFn.extract(rs_source, language=tree_sitter_rust)
```

The node-schema bridge is the differentiator: model↔grammar and
capture↔type checks run **before any text is parsed**.

## Documentation

- **Users** (build your own project on top): [docs/user-guide.md](docs/user-guide.md)
- **Developers** (work on this codebase):
  [docs/architecture.md](docs/architecture.md),
  [docs/development.md](docs/development.md)
- **The scanner library** (the C escape hatch): [docs/scanner-library.md](docs/scanner-library.md)
- **Coding agents**: `.agents/skills/` ships Agent-Skills-standard skills
  (`pydantree-dev`, `pydantree-grammar`, `pydantree-extraction`,
  `pydantree-scanners`) that load automatically into pi and other harnesses.
- The authoritative concept: `.scratch/projects/002-pydantic-treesitter/CONCEPT.md`.
  Per-phase verdicts: `.scratch/projects/00X-*/FINDINGS.md` (see docs/README.md).

## Quick facts

- Install A (consumption, light): `uv pip install pydantree-tscore
  pydantree-tsquery` (+ community grammar wheels).
- Install B (authoring, heavy): `uv pip install pydantree-tsgrammar`.
- Imports are `tscore` / `tsquery` / `tsgrammar`; the distributions are
  pydantree-branded (the bare `tsquery` name is taken on PyPI).
- A never imports B: `import tsgrammar` fails in a light install by design.
- Dev environment: `devenv shell`; `uv sync` manages the venv (uv workspace,
  no pip); the venv resolves `src/` via a `_pydantree_src.pth`, so edits are
  live immediately (no stale-copy reinstall). Baseline: 170 green + 1 skip.
