# pydantree documentation

Two cooperating libraries over tree-sitter, bound by a shared seam (`pydantree_sitter`):

- **Product A — `pydantree_sitter`** (light runtime): declare an `OutputModel` — *the
  model IS the query* — and get typed extraction over any tree-sitter grammar.
  Bind a node-schema or bundle for schema checks; bare grammars use intentional
  wildcard queries and warn that grammar checks are unavailable. No `.scm`, no
  query DSL, no manual coercion.
- **Product B — `pydantree_sitter_grammar`** (heavy build tool): author a tree-sitter
  grammar as a composable Pydantic DSL that compiles to `grammar.json` →
  `parser.c` → a shared object → a shippable **bundle**.

The authoritative concept lives in
`../.scratch/projects/002-pydantic-treesitter/CONCEPT.md` (read it first for the full
design argument). This directory is the working reference.

## For developers (working on this codebase)

- [architecture.md](architecture.md) — how the pieces fit: the A/B split,
  the two packages, the seams, the pipeline, the schema bridge, the module
  map, the durable facts.
- [development.md](development.md) — the day-to-day workflow: devenv, uv
  (uv sync, no pip, edits live via a venv .pth), running tests, evidence + commit
  conventions, debugging.
- [scanner-library.md](scanner-library.md) — the external-scanner mechanism:
  the airtight contract, the two gotchas, the five seeds, and the step-by-step
  recipe for adding a per-language scanner copy.

## For users (using the library in your own project)

- [user-guide.md](user-guide.md) — install, Product A extraction
  (`OutputModel`, captures, schemas, bundles, typed-CST codegen), Product B authoring
  (the DSL, checks, the conflict loop, the corpus harness, packaging,
  community grammars, scanners).

## The phase record

Each phase's verdict + evidence is a `FINDINGS.md` under `../.scratch/projects/00X-*/`:

| phase | topic | verdict (one line) |
|---|---|---|
| 001 | the winnow parser | exploration |
| 002 | the concept | A + B + pydantree_sitter, model-only extraction |
| 003 | pydantree_sitter extraction | A MVP over community grammars |
| 004 | pydantree_sitter_grammar | B core: DSL → generate → gcc |
| 005 | pydantree_sitter_grammar GLR | the ergonomics layer (ladders, conflict remapping) |
| 006 | pydantree_sitter bridge | the node-schema bridge (Jobs 1/3/4) |
| 007 | distribution | corpus harness + the artifact seam |
| 008 | consumer seam | install boundary + grammar-ownership boundary, GO |
| 009 | wasm + scanners | wasm assessed (no-go for A's budget, seam landed); 2 real scanners |
| 010 | Bash adoption | real-user adoption pass |
| 011 | Nix adoption | real-world adoption pass |
| 012 | grammar models | class-based Product B grammar surface |
| 013 | rule classes | Product B rule-class surface |
| 014 | adversarial review | first deep review and refactor decisions |
| 015 | Product A spike | initial Product A extraction spike |
| 016 | model-only extraction | Product A model-only extraction |
| 017 | legacy island | legacy pydantree isolation |
| 018 | adversarial review 2 | second adversarial review |
| 019 | final verification review | verification and release review |
| 020 | final code review | final code review |
| 021 | deep adversarial review | concept, architecture, and codebase review |
| 022 | ast-grep pattern | grammar-agreement pattern module |

## Coding-agent skills

`.agents/skills/` ships Agent-Skills-standard skills that load into pi
(and other agent harnesses) automatically:

- `pydantree-dev` — develop the library (environment, workflow, conventions).
- `pydantree-grammar` — author grammars with Product B.
- `pydantree-extraction` — extract typed data with Product A.
- `pydantree-scanners` — the scanner library's mechanism + how to add a
  scanner.
