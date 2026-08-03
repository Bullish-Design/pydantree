# pydantree
Treesitter, but more Pydantic.

Two cooperating libraries (see `.scratch/002-pydantic-treesitter/CONCEPT.md` —
the authoritative concept):

- **`tsgrammar` (B)** — author a tree-sitter grammar as a composable Pydantic
  DSL that compiles to `grammar.json` → parser via the standard toolchain.
- **`tsquery` (A)** — declare an `OutputModel` (**the model IS the query**: field
  names, types, defaults, and a one-line `__match__` path) and get typed
  extraction over any community grammar — no `.scm`, no query DSL, no manual
  coercion.

Status: post-Phase-4. The **bridge** is proven (`.scratch/006-tsquery-bridge/`,
verdict GO): B builds emit a `node-schema.json` (`tscore`); A's
`validate_with(language, schema=...)` runs model↔grammar and capture↔type
checks before any text is parsed, the record value-shape map is derived from
the grammar (not hardcoded), and record-level anchoring kills the
nested-collision class — all with the Phase-1 model-only surface unchanged.
Earlier phases: `spike-a2/` (Product A's model-only surface over Python +
JSON), `.scratch/005-tsgrammar-glr/` (Product B's GLR-ergonomics layer, GO).
The `src/pydantree/` first-principles wrapper is deprecated and slated for the
rewrite.
