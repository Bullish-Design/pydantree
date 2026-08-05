# KICKOFF — pydantree rewrite spike (Phase 0: prove the emission pipeline)

> Copy the whole contents of this file into a fresh session working in this repo.
> This is a **spike**, not a production build: throwaway code, keeper findings.

---

## Mission

You are working in the **`pydantree`** repo. We are **completely rewriting this
library** around a new concept documented under `.scratch/projects/`. Your job for this
session: run the **Phase 0 spike** defined in the concept and deliver a
**go / go-with-changes / no-go verdict with evidence**.

The spike has exactly one high-risk question to answer, and one supporting
pipeline to prove. Everything else is scaffolding.

## Context: what pydantree is today

- Current code under `src/pydantree/` is an early "first-principles" wrapper
  around `py-tree-sitter` (core/parser/generator/views/cli). **Treat it as
  deprecated.** Skim it briefly only to learn what exists and what didn't work;
  the rewrite is greenfield around the concept, not an extension of this code.
- The repo uses **devenv (Nix)** with Python 3.13 + uv + venv. Python deps are
  declared in `pyproject.toml` (pydantic >= 2.11, tree-sitter >= 0.23).
- Git history shows multiple aborted directions (Graphsitter, MVP) — a sign we
  keep missing on architecture. The concept in `.scratch/projects/` is the attempt to get
  the architecture right first.

## Required reading (in this order — do not skip)

1. **`.scratch/projects/002-pydantic-treesitter/CONCEPT.md`** — THE authoritative concept.
   Read it fully. It defines the two-product design (pydantree_sitter_grammar + pydantree_sitter), the
   `grammar.json`-first strategy, and the phased sequencing. Phase 0 is §9.
2. **`.scratch/projects/001-pydantic-winnow-parser/SESSION_ANALYSIS.md`** — the previous
   direction (Pydantic-authored, Rust/Winnow-executed combinators). It is
   **superseded in spirit** (we chose static grammars + tree-sitter GLR), but its
   analysis of what Pydantic can/cannot be trusted to do is durable. Read it.
3. **`.scratch/projects/001-pydantic-winnow-parser/sketch.py`** — a self-contained
   pure-Python ergonomics prototype. Run it (`python sketch.py`). It demonstrates
   the exact ergonomics we want to carry over: a Pydantic **discriminated-union
   IR**, a **builder DSL** that emits that IR, and **compile-time grammar↔output
   bridge validation**. The IR style carries over; the backend does not.
4. (Optional) `.scratch/projects/001-pydantic-winnow-parser/WINNOW_PYO3_PYTHON_COMBINATORS_CONCEPT.md`
   — the fuller earlier analysis; skim for anything we don't want to lose.

## The concept in 60 seconds

Two cooperating libraries put a Pydantic face on tree-sitter:

- **Product B (`pydantree_sitter_grammar`)** — *authoring*, build-time. A Pydantic DSL that
  compiles down to **`grammar.json`** (bypassing `grammar.js` entirely), then runs
  the standard `tree-sitter generate` + compile pipeline. Its whole reason to
  exist: make GLR grammar authoring painless (typed precedence, conflicts remapped
  to your Python source, static analysis before the slow Rust step).
- **Product A (`pydantree_sitter`)** — *consuming*, run-time. A Pydantic query DSL that
  maps captured tree-sitter nodes into typed `OutputModel` instances. Works over
  any community grammar; zero dependency on B.
- **Shared `pydantree_sitter`** — Pydantic models mirroring the `grammar.json` schema + the
  `node-schema` bridge format. The two products meet at exactly one data artifact
  (`.so/.wasm` + `node-schema.json`), never in code.

The load-bearing insight: **`grammar.js` is not load-bearing** — it only
`console.log(JSON.stringify(grammar))`s. So we target `grammar.json` directly.

## Spike scope — Phase 0: prove the emission pipeline

### Primary experiment (the go/no-go): conflict → Python-source remapping

The entire Product-B value proposition rests on turning the tree-sitter
generator's cryptic conflict output into actionable, source-located Python
errors. **You must prove this is mechanically possible from real generator
output.**

1. Author the spike grammar (below) with a **deliberate, genuine ambiguity** —
   e.g. a dangling-else-style construct or a precedence gap — so `tree-sitter
   generate` actually reports conflicts.
2. Capture the **raw** generator output verbatim (save it to a file).
3. Determine exactly what machine-readable information is available (structured
   symbols? rule names? sequences? line numbers? plain text only?).
4. Build a rough prototype that maps the conflict symbols back to the
   `GrammarModel` rules and, from rule definition sites you recorded at build
   time, raises a `GrammarConflictError` that names the offending `g.rule(...)`
   calls.
5. **Verdict, honestly:** is this reliably possible with the current CLI? If the
   output is too coarse to map reliably, say so and show exactly what's missing.
   A negative result is a valid result — it changes the architecture.

### Supporting pipeline (must work end-to-end)

1. **GrammarModel IR** — a Pydantic discriminated union mirroring the actual
   `grammar.json` node schema: `SYMBOL`, `STRING`, `PATTERN`, `SEQ`, `CHOICE`,
   `REPEAT`, `REPEAT1`, `PREC`, `PREC_LEFT`, `PREC_RIGHT`, `TOKEN`, `ALIAS`,
   `FIELD`, plus grammar-level options (`extras`, `word`, `conflicts`, `inline`,
   `supertypes`, `externals`, `start`). Use `sketch.py` as the style reference;
   adapt the node types to `grammar.json`'s *real* schema (verify against the
   tree-sitter CLI's expectations — check the installed CLI version's
   grammar.json handling).
2. **Tiny builder DSL** — enough sugar to author the spike grammar:
   `seq`/`choice`/`repeat`/`opt`/`field`/`token`/`ref`/`prec` (+ `prec.left` /
   `prec.right`). Record the definition site (file/lineno) of each rule for the
   conflict experiment.
3. **Spike grammar** — a small expression language that is a *real* GLR test:
   literals, identifiers, binary operators with mixed left/right associativity
   (e.g. `^` right, `+ - * /` left), unary minus, parentheses, a comment/whitespace
   `extras` policy, and a `word`/keyword rule to avoid keyword/identifier
   conflicts. Hand-roll the precedence ladder (do NOT build the
   `ExpressionGrammar` helper — that's Phase 3).
4. **Emit → generate → compile → parse**:
   - Emit `grammar.json` from the IR. Verify round-trip and that it validates.
   - Run `tree-sitter generate`, compile `parser.c` (via `cc`/`gcc`) to a shared
     library, load it with the official `tree-sitter` Python bindings.
   - Parse representative inputs; confirm the CST has the expected structure
     (esp. correct precedence/associativity of expressions).
5. **Cheap static checks** (only the trivial ones): undefined `Symbol` refs,
   nullable-inside-`repeat`, `token` referencing a non-terminal. Note which are
   easy; don't build the full analyzer.

## Out of scope — say no to these (politely)

- Product A: query DSL → `.scm`, capture → `OutputModel` materialization
  (**Phase 1**).
- The `node-schema` bridge / compile-time query validation (**Phase 4**).
- wasm, packaging/wheels, external C scanners (**Phase 5**).
- The `ExpressionGrammar`/Pratt helper and full precedence-ladder machinery
  (**Phase 3**) — hand-roll precedence in the spike; only *note* what the helper
  should do.
- Package renaming/splitting (`pydantree_sitter`/`pydantree_sitter`/`pydantree_sitter_grammar`). Distribution is a
  later decision; the spike proves mechanics, not packaging.
- Performance work of any kind.

## Environment setup (do this first)

1. `devenv shell` (or `nix develop`). If it isn't working, tell the user
   immediately rather than fighting it.
2. Add to `devenv.nix` what the spike needs — likely `pkgs.tree-sitter-cli`
   (the Rust generator) and a C compiler (`pkgs.gcc`, or via `pkgs.stdenv`).
   Check CLI version compatibility with the installed `tree-sitter` Python
   bindings (>= 0.23).
3. Install Python deps (`uv sync` or equivalent; `pydantic>=2.11`,
   `tree-sitter>=0.23`).
4. Confirm you can run `tree-sitter generate` from a directory containing a
   hand-written `grammar.json` before writing any IR code (this validates the
   concept's core assumption cheaply).

## Working agreement

- **Spike code goes in `.scratch/projects/002-pydantic-treesitter/spike/`**, isolated from `src/`.
  Reference docs stay in `.scratch/projects/`.
- **Commit after each meaningful step**, with clear messages (e.g.
  `spike: grammar.json emission round-trips`, `spike: generated parser compiles`).
- **Write findings as you go** into `.scratch/projects/002-pydantic-treesitter/spike/FINDINGS.md`. The code is throwaway;
  the findings are the deliverable.
- **Don't gold-plate.** If a step is 80% done and the remaining 20% is polish,
  note it and move on.
- **Don't fake the primary experiment.** If conflict output can't be remapped,
  record exactly what blocked you and how the concept would need to change.
- **Ask before expanding scope** beyond this brief.

## Deliverables (end of session)

1. Working code in `.scratch/projects/002-pydantic-treesitter/spike/`: IR → `grammar.json` → generated + compiled parser
   that parses the sample expression language with correct precedence.
2. `.scratch/projects/002-pydantic-treesitter/spike/FINDINGS.md` answering at minimum:
   - Does the `grammar.json` round-trip work cleanly? What had to be learned/fixed
     vs. the concept's assumptions (CLI version behavior, schema details)?
   - **Is conflict → Python-source remapping mechanically feasible?** Include the
     raw generator output and what was extracted from it.
   - What does the full GrammarModel IR need (gaps vs. the real `grammar.json`
     schema)?
   - Re-assess the risks in §11 of the concept with what you now know.
   - **Recommendation:** go / go-with-changes / no-go, and the single most
     important next step.
3. Everything committed.
