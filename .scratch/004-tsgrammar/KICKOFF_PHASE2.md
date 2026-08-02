# KICKOFF — pydantree Phase 2 (Product B core: `tsgrammar`)

> Copy the whole contents of this file into a fresh session working in this repo.
> This is the **real build** of Product B's core (not a spike): the code you
> write here is the foundation of the rewrite, not throwaway. Reference docs
> live in `.scratch/`; your findings go in `.scratch/004-tsgrammar/FINDINGS.md`.

---

## Mission

You are working in the **`pydantree`** repo. **Phases 0 and 1 are done and
passed.** Phase 0 proved the emission pipeline (`grammar.json`-first) and the
conflict→Python-source remapping (verdict: GO). Phase 1 proved Product A's
**model-only** extraction surface (the `OutputModel` class IS the query — the
pre-Phase-1 query-DSL version was rejected) and concluded that **Product B is
the next step**: A's remaining risks (value-shape derivation, compile-time
capture↔type checking) are all bridge-shaped (Phase 4), and the bridge needs B.

This session runs **Phase 2 — Product B core (`tsgrammar`)**, per the concept
(§4, §9): the Pydantic GrammarModel IR mirroring the full real `grammar.json`
schema, the builder DSL, author-time static analysis, and the native build
pipeline (`grammar.json` → `tree-sitter generate` → gcc → `.so` → load).

Deliver a **go / go-with-changes / no-go verdict with evidence**, following the
Phase-0 discipline: one high-risk question, an honest experiment, findings over
code, everything committed.

## Context: where we are

- **Phase 0 (done, committed):** `.scratch/002-pydantic-treesitter/spike/`
  proved `grammar.json`-first emission + conflict remapping. Its code is
  **throwaway** — reference it for patterns (IR, builder, checks, conflicts,
  pipeline), **don't extend it**. Its `FINDINGS.md` contains the **durable
  technical facts and the §7 concept amendments** that are Phase-2 requirements.
- **Phase 1 (done, committed):** `spike-a/` (0.26 API substrate + materializer
  semantics) and `spike-a2/` (the model-only Product A design). Product A is
  defined and waits on B's artifact for the bridge. Both findings recommend
  Phase 2 next; `spike-a2/FINDINGS.md` §5 spells out what A needs from the
  artifact.
- **`CONCEPT.md` is post-Phase-1:** §5 is the validated Product A design;
  **§4 is the Product B spec**; §6 (artifact boundary), §7 (the bridge), §9
  (sequencing), §12 (bet #1 is B's) frame the rest.
- **`src/pydantree/`** remains the deprecated first-principles wrapper — **do
  not touch it**. The rewrite targets new packages.

## Required reading (in this order — do not skip)

1. **`.scratch/002-pydantic-treesitter/CONCEPT.md`** — full read, but focus on
   §4 (Product B: §4.2 the IR, §4.3 the builder DSL, §4.4 GLR-ergonomics
   framing, §4.5 static analysis, §4.6 the honesty line, §4.7 the build
   pipeline), §6 (artifact boundary), §7 (the bridge — what B must eventually
   emit), §9 (sequencing), §12 (bottom line: bet #1).
2. **`.scratch/002-pydantic-treesitter/spike/FINDINGS.md`** — Phase 0's verdict
   and durable facts. Read all of it, especially:
   - **§0** — toolchain/ABI/loader facts,
   - **§1** — the learned mechanics: start-rule ordering, `word` keyword
     extraction, `BLANK` for `opt`, named-vs-int precedence, `PREC_DYNAMIC`,
     `RESERVED`, the extras-vs-token-prefix comment footgun, fail-fast
     first-conflict-only `--json` on stderr, silent unused-rule pruning,
   - **§2** — the conflict JSON structure and the remapping mechanics
     (`variable_name` → recorded DSL sites, `possible_resolutions`),
   - **§3** — the full IR node table (the schema the IR must mirror),
   - **§7** — the changes the concept needs (these are Phase-2 requirements).
3. **Phase-0 spike code (skim, for patterns to port):**
   `spike/main.py`, `spike/pipeline.py`, `spike/grammar_model.py`,
   `spike/builder.py`, `spike/checks.py`, `spike/conflicts.py`,
   `spike/spike_lang.py`.
4. **`spike-a2/FINDINGS.md`** — why Phase 2 is next, and what A will consume
   from B's artifact. **`spike-a/FINDINGS.md`** — the 0.26 API facts (for the
   load/parse side; already validated).
5. (Optional) The installed ground truth
   `.devenv/state/venv/lib/python3.13/site-packages/tree_sitter/__init__.pyi`
   — only for the load/parse surface.

## The concept in 60 seconds (Product B)

```
grammar author ──► Pydantic builder DSL ──► GrammarModels (IR)
   ──► grammar.json ──► tree-sitter generate ──► parser.c ──► gcc ──► .so
   ──► loaded via PyCapsule ──► parsed by Product A
```

B's whole reason to exist is §4.4/§4.5/§4.6: move GLR authoring pain from
*cryptic, post-hoc, integer-encoded* to *typed, declarative, pointed at your
Python source*. Phase 2 is the **core mechanics** (IR, builder, analyzer,
pipeline, conflict remapping). The **GLR-ergonomics layer** — precedence
ladders, `ExpressionGrammar`, conflict-UX polish — is **Phase 3**, explicitly
out of scope here. Phase 2 proves the machinery; Phase 3 proves the feel.

## Spike scope — Phase 2

### Primary experiment (the go/no-go): is B's core mechanically sound at full schema fidelity, end-to-end?

Two-part honest experiment (the Phase-0 "hand-written first" discipline,
repeated at full scale):

**Experiment A — IR fidelity to the real schema.** Build a reference
`grammar.json` **by hand** (as Phase 0 did) that exercises the *full* 0.25.3
schema surface — every node type in the Phase-0 §3 table (`SYMBOL`, `STRING`,
`PATTERN` with flags, `BLANK`, `SEQ`, `CHOICE`, `REPEAT`, `REPEAT1`, `FIELD`,
`ALIAS`, `TOKEN`, `IMMEDIATE_TOKEN`, `PREC`/`PREC_LEFT`/`PREC_RIGHT` (int **and**
name values), `PREC_DYNAMIC`, `RESERVED`) and grammar-level `rules`,
`precedences`, `conflicts`, `externals`, `extras`, `inline`, `supertypes`,
`word`, `reserved`. Validate it against the CLI **first** (`tree-sitter
generate` → exit 0). Then: `GrammarModel.model_validate_json` (import) →
re-emit → assert **semantic equality** with the hand-written reference
(normalize like Phase 0's `_norm` — drop empty lists/None) → generate the
re-emitted version → confirm a working parser. If a *real community* grammar's
`grammar.json` is obtainable (published grammar repos), prefer it as an
additional import test — but the hand-written full-schema reference is the
requirement. **Gate:** the IR covers the real schema, or the gaps are enumerated
and the IR amended.

**Experiment B — DSL-authored grammar end-to-end (the go/no-go).** Author ONE
nontrivial grammar **entirely through the builder DSL**: tokens, a `word`
declaration, fields, `extras` with a comment rule per the Phase-0 extras rule
(named rule + SYMBOL reference, never a bare inline pattern whose prefix is a
token), optional/repeat, at least one hidden rule with an `alias`, a
`supertype`. Then: static analysis clean → `generate` (exit 0, ABI 15) →
gcc → load via PyCapsule → parse a small corpus → assert CST shapes against
**ground truth you computed by hand**. Separately, on throwaway grammars,
**plant each known footgun** and show the analyzer catches it *pre-generate*:
unused rule (the silent-pruning trap), nullable inside `repeat`, `SYMBOL`
inside `token` (mind the `IMMEDIATE_TOKEN` quirk), extras first-set overlapping
a token prefix. And author a **deliberate conflict** and show the remapped
`GrammarConflictError` naming the DSL source lines with the ambiguous shape +
competing productions + suggested fixes.

### Supporting pipeline (must work end-to-end)

1. **IR** (`tsgrammar.grammar`): the full node set from Phase-0 §3 as a Pydantic
   discriminated union (discriminator `type`), plus grammar-level fields
   `name` (required), `rules` (**ordered — first is start; there is NO `start`
   field**), `precedences`, `conflicts`, `externals`, `extras`, `inline`,
   `supertypes`, `word`, `reserved`. `model_validate_json` / `model_dump_json`
   round-trip. Include the `OPTIONAL`-is-`CHOICE(x, BLANK)` rule in the docs.
2. **Emitter**: IR → `grammar.json`, **start rule emitted first**, plus the
   ABI-15 `tree-sitter.json` (`{"metadata": {"version": "0.1.0"}}`) alongside.
3. **Builder DSL** (§4.3 surface, ported from the Phase-0 spike): `Grammar`,
   `rule`, `seq`, `choice`, `repeat`, `opt`, `field`, `token`, `tok`, `ref`,
   operator sugar (`+`, `|`, `.star()`, `.plus()`, `.opt()`), `start(...)`,
   and **definition-site recording** (`file`, `lineno`, source) per `rule()`
   call — required for conflict remapping (grammar.json carries no positions).
4. **Static analysis** (§4.5 + the Phase-0 additions): undefined rule refs;
   **unused/unreachable rules (mandatory — the CLI prunes them silently)**;
   nullable-inside-`repeat`/`repeat1`; `SYMBOL`-inside-`TOKEN`; duplicate rule
   names; `PATTERN` flags validation (only `i`); named-vs-integer precedence
   mixing warning; extras first-set × token-prefix overlap warning. Each
   produces a Pythonic diagnostic with the DSL source location.
5. **Build pipeline** (§4.7): invoke the stock CLI (`tree-sitter generate`,
   capture stdout/stderr verbatim for evidence), gcc → `.so`, load via the
   PyCapsule pattern from `spike/pipeline.py`, parse. Content-addressed cache
   keyed on `hash(grammar.json) + ABI version + toolchain version`.
6. **Conflict remapping** (§4.4.3): port `spike/conflicts.py` — parse
   `generate --json` **stderr** (exit 1, first-conflict-only), map
   `variable_name` → the DSL's recorded sites, raise `GrammarConflictError`
   showing which `g.rule(...)` lines collide, the ambiguous input shape, the
   competing productions, and `possible_resolutions`. The fix loop is
   one-conflict-at-a-time; generate is sub-second.

### Cheap checks (trivial only)

- Every emitted `grammar.json` generates with exit 0 on the stock CLI (the
  CLI is the cheapest validator you have).
- IR round-trip: `validate_json` → `dump_json` → `validate_json` is
  structurally equal (Experiment A's gate).
- Analyzer unit cases: each planted footgun (Experiment B) fails with the
  expected diagnostic.
- Definition-site recording: every emitted `GrammarConflictError` cites real
  `file:lineno` of the DSL source.

## Out of scope — say no to these (politely)

- **Phase 3 — the GLR-ergonomics layer.** No `ExpressionGrammar`, no
  precedence-ladder helper, no conflict-UX polish. The IR must *validate*
  `PREC*`/`precedences`/`PREC_DYNAMIC` (they're in the schema) but the DSL
  doesn't sugar them yet.
- **Phase 4 — the bridge.** No `node-schema.json` format design, no A-side
  integration, no compile-time query checking in A. Note: the CLI emits
  `node-types.json` as a free byproduct of every successful generate — leave
  it on disk, don't build on it.
- **Product A code.** A consumes artifacts only; do not import `spike-a2/` or
  extend A in any way.
- **External scanners.** The IR accepts `externals`; no scanner library, no
  scanner authoring.
- **wasm, packaging/wheels, package splitting** (`tscore`/`tsgrammar`/
  `tsquery`), corpus-testing harness (Phase 5), incremental-reparse wrappers,
  performance work of any kind.
- **Ergonomics claims.** Do NOT claim Phase 2 proves bet #1 — it proves the
  machinery, not the feel. That is Phase 3's experiment.

## Environment setup (do this first)

1. `devenv shell` — works (fixed in Phase 0). If it isn't working, tell the
   user immediately rather than fighting it.
2. **Verified facts from Phase 0 (don't re-derive):**
   - tree-sitter CLI **0.25.3** (`pkgs.tree-sitter`), bindings **0.26.0**
     (`LANGUAGE_VERSION=15`, `MIN_COMPATIBLE=13`), pydantic **2.13.4**,
     gcc **14.2.1**.
   - `tree-sitter generate <grammar.json>` works directly (grammar.js is
     bypassed). ABI 15 requires the `tree-sitter.json` config; without it the
     CLI falls back to ABI 14 (works, but use 15).
   - Conflicts: exit code 1, **no `parser.c` written**, first conflict only,
     machine report on **stderr** with `--json`.
   - Load path: PyCapsule named `"tree_sitter.Language"` over the
     `tree_sitter_<name>()` export (int pointers are deprecated). See
     `spike/pipeline.py`.
   - Unused rules are **silently pruned** — the analyzer's unused-rule check is
     not optional.
3. **Where the code goes:** this is the real build — create a proper package
   **`src/tsgrammar/`** (submodules: `grammar.py`, `builder.py`, `checks.py`,
   `conflicts.py`, `pipeline.py`, `language.py`) with pytest tests under
   `tests/`. Add `src/tsgrammar` to `[tool.hatch.build.targets.wheel].packages`
   in `pyproject.toml` and reinstall the editable package so `import tsgrammar`
   works in the venv. Distribution/splitting is a later decision — organize so
   the future `tscore`/`tsquery` split is mechanical, but build one package now.
   **Do not touch `src/pydantree/`.** (If the editable reinstall fights you, a
   session-local sys.path shim is acceptable — note which you did.)
4. **Before writing builder code**: hand-write the Experiment-A reference
   `grammar.json`, run it through the CLI, and confirm a working parser — this
   is the Phase-0 "hand-written grammar.json first" move, repeated.

## Working agreement

- **Commit after each meaningful step**, with clear messages (e.g.
  `tsgrammar: IR mirrors full 0.25.3 schema, round-trips`,
  `tsgrammar: builder DSL + definition-site recording`,
  `tsgrammar: analyzer catches unused-rule pruning footgun`,
  `tsgrammar: pipeline generate→gcc→load→parse with caching`,
  `tsgrammar: conflict remapping ported, evidence captured`).
- **Write findings as you go** into `.scratch/004-tsgrammar/FINDINGS.md`. The
  code is the foundation; the findings are the deliverable.
- **Don't gold-plate.** 80%-done steps get a note and a move-on.
- **Don't fake the primary experiment.** Experiment A's reference and
  Experiment B's corpus must be real, CLI-validated, and ground-truthed by
  hand. Save raw generator output verbatim under
  `.scratch/004-tsgrammar/evidence/`.
- **Ask before expanding scope** beyond this brief.

## Deliverables (end of session)

1. Working `src/tsgrammar/` package (IR + emitter, builder, analyzer, pipeline,
   conflict remapping) with pytest tests, all committed.
2. Demonstrated, with evidence:
   - (a) full-schema reference `grammar.json` → import → re-emit → generate →
     parse, round-trip equal;
   - (b) a DSL-authored nontrivial grammar → clean analyze → generate (ABI 15)
     → compile → load → correct CST against hand-computed ground truth;
   - (c) each planted footgun caught pre-generate by the analyzer;
   - (d) a deliberate conflict remapped to DSL `file:lineno` with suggested
     fixes.
3. `.scratch/004-tsgrammar/FINDINGS.md` answering at minimum:
   - Is the IR **faithful to the real schema**? What had to be added vs the
     Phase-0 §3 table?
   - Does the **DSL-authored pipeline hold end-to-end** (Experiment B)? Where
     did it break or get ugly?
   - What does the **full Product B** need (gaps vs §4) — which builder
     operators are missing, which static checks are hard, what the conflict
     UX surface should be?
   - Re-assess **§11 risks** from the authoring side (1 — conflict diagnostics
     at the reimplementation level; 3 — toolchain; 4 — churn; 6 — regex
     subset), and state where **bet #1** stands after this phase.
   - **Recommendation:** go / go-with-changes / no-go, and the single most
     important next step (is it Phase 3 — the GLR-ergonomics layer — or a
     Phase-2A hardening pass?).
4. Everything committed.

## Appendix — Phase-0 §3 IR node table (the schema checklist)

| Node `type` | fields | notes |
|---|---|---|
| `SYMBOL` | `name` | rule reference |
| `STRING` | `value` | literal |
| `PATTERN` | `value`, `flags?` | regex; only `i` supported |
| `BLANK` | — | needed for `opt` |
| `SEQ` / `CHOICE` | `members` | |
| `REPEAT` / `REPEAT1` | `content` | nullable-in-repeat is a semantic hazard |
| `FIELD` | `name`, `content` | |
| `ALIAS` | `value`, `named`, `content` | |
| `TOKEN` / `IMMEDIATE_TOKEN` | `content` | SYMBOL-in-TOKEN illegal; IMMEDIATE_TOKEN quirk |
| `PREC` / `PREC_LEFT` / `PREC_RIGHT` | `value: int \| name`, `content` | named vs int do not mix |
| `PREC_DYNAMIC` | `value: int`, `content` | |
| `RESERVED` | `context_name`, `content` | 0.25+ feature |

Grammar-level: `name` (required), `rules` (ordered; **first is start**),
`precedences`, `conflicts`, `externals`, `extras`, `inline`, `supertypes`,
`word`, `reserved`.
