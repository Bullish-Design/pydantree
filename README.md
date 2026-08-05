# pydantree-sitter

Treesitter, but more Pydantic.

Two cooperating distributions over tree-sitter (the 014 refactor: the
collision-proof `pydantree-sitter` names; the old tscore/tsquery/tsgrammar
split is folded into two packages):

- **`pydantree-sitter`** (import `pydantree_sitter`) — Product A: declare an
  `OutputModel` (**the model IS the query**: field names, types, defaults,
  and a one-line `__match__` path) and get typed, schema-checked extraction
  over any grammar — no `.scm`, no query DSL, no manual coercion. Light: no
  toolchain.
- **`pydantree-sitter-grammar`** (import `pydantree_sitter_grammar`) —
  Product B: author a tree-sitter grammar as a composable Pydantic DSL that
  compiles to `grammar.json` → parser → a shippable bundle. Heavy: needs the
  tree-sitter CLI + gcc at build time.

```python
from pydantree_sitter import M, NodeKind, OutputModel, capture
import tree_sitter_rust

class RustFn(OutputModel):
    __match__ = M("source_file", "function_item")
    name: str = capture("name")
    return_type: str | None = capture("return_type")

lang = pydantree_sitter.Language.from_module(tree_sitter_rust)
rows = lang.extractor(RustFn).extract(rs_source)     # checks run here, once
rows = RustFn.extract(rs_source, language=lang)      # sugar
```

The node-schema bridge is the differentiator: model↔grammar and
capture↔type checks run at **bind time** — before any text is parsed.

## The honesty statements (014 §8.2)

- **A's expressiveness ceiling (C1):** `M()` expresses an *anchored ancestor
  path* (with `...` gaps and per-step alternation), direct-child captures,
  and predicates (`Matches`/`Eq`/`AnyOf`). Sibling order, negation, and
  multi-anchor joins are **out of scope** — `__raw_query__ = RawQuery('...')`
  is the escape hatch: a literal `.scm` whose captures map to fields by name.
- **Value shapes are declared data (C2):** record-mode value shapes come
  from a `ValueMap` — never silent name-regex inference. `propose_value_map`
  is a **draft generator** whose output you inspect and commit (or ship in a
  bundle's `value_map` metadata). Schema-less record mode is the documented
  JSON family + `JSON_VALUE_MAP`, exactly.

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

- Install A (consumption, light): `uv pip install pydantree-sitter`
  (+ community grammar wheels).
- Install B (authoring, heavy): `uv pip install pydantree-sitter-grammar`
  (depends on the light package).
- The schema IS the CLI's `node-types.json` byproduct, tracked by
  construction (the hand-port of node_types.rs is deleted).
- A never imports B: `import pydantree_sitter_grammar` fails in a light
  install by design.
- Dev environment: `devenv shell`; `uv sync` manages the venv (uv workspace,
  no pip); the venv resolves `src/` via a `_pydantree_src.pth`, so edits are
  live immediately (no stale-copy reinstall). Baseline: 233 green (fast loop
  `-m "not slow"` ~24s).
