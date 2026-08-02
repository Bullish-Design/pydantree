# pydantree
Treesitter, but more Pydantic.

Two cooperating libraries (see `.scratch/002-pydantic-treesitter/CONCEPT.md` —
the authoritative concept):

- **`tsgrammar` (B)** — author a tree-sitter grammar as a composable Pydantic
  DSL that compiles to `grammar.json` → parser via the standard toolchain.
- **`tsquery` (A)** — declare an `OutputModel` (**the model IS the query**: field
  names, types, defaults, and a one-line `__match__` path) and get typed
  extraction over any community grammar — no `.scm`, no query DSL, no manual
  coercion. Validated in Phase 1 (`spike-a2/FINDINGS.md`).

Status: post-Phase-1. Product A's model-only surface is proven over Python +
JSON (`spike-a2/`, runnable via `devenv shell -- python spike-a2/main.py`);
Product B's emission pipeline is proven (`spike/`, Phase 0). The `src/pydantree/`
first-principles wrapper is deprecated and slated for the rewrite.
