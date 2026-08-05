# pydantree documentation

Two cooperating libraries over tree-sitter, bound by a shared seam (`tscore`):

- **Product A — `tsquery`** (light runtime): declare an `OutputModel` — *the
  model IS the query* — and get schema-checked, typed extraction over any
  tree-sitter grammar. No `.scm`, no query DSL, no manual coercion.
- **Product B — `tsgrammar`** (heavy build tool): author a tree-sitter
  grammar as a composable Pydantic DSL that compiles to `grammar.json` →
  `parser.c` → a shared object → a shippable **bundle**.

The authoritative concept lives in
`../.scratch/projects/002-pydantic-treesitter/CONCEPT.md` (read it first for the full
design argument). This directory is the working reference.

## For developers (working on this codebase)

- [architecture.md](architecture.md) — how the pieces fit: the A/B split,
  the three packages, the seams, the pipeline, the schema bridge, the module
  map, the durable facts.
- [development.md](development.md) — the day-to-day workflow: devenv, uv
  (uv sync, no pip, edits live via a venv .pth), running tests, evidence + commit
  conventions, debugging.
- [scanner-library.md](scanner-library.md) — the external-scanner mechanism:
  the airtight contract, the two gotchas, the five seeds, and the step-by-step
  recipe for adding a per-language scanner copy.

## For users (using the library in your own project)

- [user-guide.md](user-guide.md) — install, Product A extraction
  (`OutputModel`, captures, schemas, bundles, stubs), Product B authoring
  (the DSL, checks, the conflict loop, the corpus harness, packaging,
  community grammars, scanners).

## The phase record

Each phase's verdict + evidence is a `FINDINGS.md` under `../.scratch/projects/00X-*/`:

| phase | topic | verdict (one line) |
|---|---|---|
| 001 | the winnow parser | exploration |
| 002 | the concept | A + B + tscore, model-only extraction |
| 003 | tsquery extraction | A MVP over community grammars |
| 004 | tsgrammar | B core: DSL → generate → gcc |
| 005 | tsgrammar GLR | the ergonomics layer (ladders, conflict remapping) |
| 006 | tsquery bridge | the node-schema bridge (Jobs 1/3/4) |
| 007 | distribution | corpus harness + the artifact seam |
| 008 | consumer seam | install boundary + grammar-ownership boundary, GO |
| 009 | wasm + scanners | wasm assessed (no-go for A's budget, seam landed); 2 real scanners |

## Coding-agent skills

`.agents/skills/` ships Agent-Skills-standard skills that load into pi
(and other agent harnesses) automatically:

- `pydantree-dev` — develop the library (environment, workflow, conventions).
- `pydantree-grammar` — author grammars with Product B.
- `pydantree-extraction` — extract typed data with Product A.
- `pydantree-scanners` — the scanner library's mechanism + how to add a
  scanner.
