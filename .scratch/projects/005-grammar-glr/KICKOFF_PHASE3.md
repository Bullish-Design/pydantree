# KICKOFF — pydantree Phase 3 (Product B: the GLR-ergonomics layer)

> Copy the whole contents of this file into a fresh session working in this repo.
> This is the **bet-#1 experiment**, building on the real `src/pydantree_sitter_grammar/`
> package from Phase 2. Reference docs live in `.scratch/`; findings go in
> `.scratch/005-grammar-glr/FINDINGS.md`.

---

## Mission

You are working in the **`pydantree`** repo. **Phases 0–2 are done and
passed.** Phase 0 proved the emission pipeline and conflict→source remapping;
Phase 1 proved Product A's model-only surface; Phase 2 (`.scratch/004-pydantree_sitter_grammar/`,
`src/pydantree_sitter_grammar/`) proved Product B's core mechanics at full schema fidelity —
IR, builder DSL, analyzer, native build pipeline, conflict remapping — verdict
**GO**.

This session runs **Phase 3 — the GLR-ergonomics layer**, per the concept (§4.4,
§9, §12): the declarative **precedence ladders**, the **`ExpressionGrammar`
(Pratt-style) helper**, **intentional-ambiguity opt-in**, and the **conflict-UX
polish** (per-production source sites, the fix-one-rerun loop). This is the
experiment that decides **bet #1** — "that we can turn GLR conflict/precedence
pain into typed, declarative, source-located Python" (CONCEPT §12). Phase 2
proved the machinery; Phase 3 proves the *feel*. Deliver a
**go / go-with-changes / no-go verdict with evidence** — an honest "no" on the
feel is a valid, architecture-changing result.

## Context: where we are

- **Phase 0 (done):** `.scratch/002-pydantic-treesitter/spike/` — emission +
  remapping proven. Throwaway code; reference it for patterns only.
- **Phase 1 (done):** `spike-a/`, `spike-a2/` — Product A's model-only surface
  (`OutputModel` IS the query). A waits on the §7 node-schema bridge (Phase 4).
- **Phase 2 (done, THIS is your foundation):** `.scratch/004-pydantree_sitter_grammar/` — the
  real build. **Do not re-derive or rewrite it; extend it.** Package
  `src/pydantree_sitter_grammar/` (submodules `grammar.py`, `builder.py`, `checks.py`,
  `conflicts.py`, `pipeline.py`, `language.py`) with pytest tests in `tests/`.
  Its `FINDINGS.md` §4 lists the exact gaps Phase 3 must close, and §7
  recommends Phase 3 next with the Phase-2A hardening items folded into the
  first sprint.
- **`CONCEPT.md`** — §4.4 is the Product B ergonomics spec (the numbered
  techniques 1–8); §4.6 is the honesty line; §12 names bet #1. Post-Phase-1, so
  §5 is the validated Product A design.
- **`src/pydantree/`** — deprecated first-principles wrapper. **Do not touch.**

## Required reading (in this order — do not skip)

1. **`.scratch/002-pydantic-treesitter/CONCEPT.md`** — focus on §4.4 (the eight
   ergonomics techniques — ladders, ExpressionGrammar, conflict remapping,
   ambiguity opt-in, visibility attributes, sane defaults, regex validation,
   left recursion), §4.6 (honesty line), §4.7 (pipeline), §12 (bet #1).
2. **`.scratch/004-pydantree_sitter_grammar/FINDINGS.md`** — Phase 2's verdict and durable
   facts. Especially:
   - §4 (the Phase-3 gap list) and §7 (recommendation + hardening list),
   - the precedence internals in §3.1 (ladder direction, associativity need,
     int/named never-compare, layering fix),
   - the appendix facts 1–10 (esp. 3: named ladder descending + associativity;
     non-start rules must not be nullable; inline rules must not be tokens;
     alias should wrap a single symbol).
3. **Phase-2 code (skim — this is your base, extend it):**
   - `src/pydantree_sitter_grammar/builder.py` — the DSL surface you will extend. Today it has
     `prec`/`prec_left`/`prec_right`/`prec_dynamic`, a raw `precedence_ordering`
     (named ladder, descending), `conflict()`, `alias()`, `rule(..., hidden=,
     inline=, supertype=)`, `word()`, `extra()`, `external()`, `reserved_word()`,
     operators `+`/`|`/`.star()`/`.plus()`/`.opt()`/`.capture()`.
   - `src/pydantree_sitter_grammar/conflicts.py` — the remapping (per-rule sites; Phase 3 adds
     per-production sites and the fix loop).
   - `src/pydantree_sitter_grammar/checks.py`, `pipeline.py`, `grammar.py` — analyzer, cache,
     IR.
   - `.scratch/004-pydantree_sitter_grammar/filtlang.py` — the Phase-2 hand-rolled precedence
     ladder (`COMPARE, ADD, MUL, UNARY = 1, 2, 3, 4` with `prec_left(ADD, …)`)
     that is EXACTLY the pattern the Phase-3 ladder helper must automate; use it
     as the "without Phase 3" baseline in the experiment.
   - `.scratch/004-pydantree_sitter_grammar/experiment_b.py` — the end-to-end pattern and the
     conflict-remapping harness to reuse.
4. (Optional) The tree-sitter CLI source checkout at `/tmp/tree-sitter/`
   (present from Phase 2) — `cli/generate/src/build_tables/build_parse_table.rs`
   for precedence/shift-reduce internals; `--report-states-for-rule` is a
   Phase-3 debugging surface (Phase-0 finding §1.11).

## The concept in 60 seconds (Product B, Phase 3)

```
grammar author ──► builder DSL (+ ladders, ExpressionGrammar, ambiguity opt-in)
   ──► GrammarModels (IR) ──► grammar.json ──► tree-sitter generate ──► gcc ──► .so
   ──► conflicts remapped to YOUR Python source (per-production sites, fix loop)
```

B's whole reason to exist is §4.4/§4.5/§4.6. Phase 2 built the machinery. Phase 3
builds the part that earns the name: authors declare **relative precedence
orderings** (not magic integers), get expression rules **generated from a
table**, opt into **intentional ambiguity** as a typed flag, and when GLR bites,
the bite lands on the **exact `seq(...)` line** with a suggested fix and a
**fix-one-rerun loop** that's first-class. We still do **not** promise the bite
never happens (honesty line §4.6) — we promise it's informed, local, and fast.

## Phase 3 scope

### Primary experiment (the go/no-go): does the ergonomics layer change the feel?

This is **bet #1's** experiment, honest and evidence-backed. One realistic
grammar, three runs, one verdict.

**Run 1 — the helper-built grammar (the pitch).** Author ONE realistic,
genuinely-tricky grammar **entirely through the new surface**: a declarative
precedence ladder, `ExpressionGrammar` for a mixed-associativity expression
surface (at least: left-assoc `+ - * /`, right-assoc `^`, a unary prefix, a
postfix element (call or member access) — all of which interact), the ambiguity
opt-in for a dangling-else-style construct, sane-defaults extras, `word`,
fields, a hidden rule + alias, a supertype. Then: analyzer clean → generate
(exit 0, ABI 15) → compile → load → parse a corpus → assert CST shapes against
**hand-computed ground truth** (the Phase-2 discipline). Record the metrics:

- how many precedence values/annotations the helper emitted vs. what a
  hand-author writes (filtlang's 4 constants + ~6 annotations is the baseline);
- how many conflicts the helpers *prevented* vs. the same grammar hand-rolled
  (Run 3);
- how many author-added `conflict(...)` entries were needed (0 is the goal for
  the common case);
- whether the generated expression rules are *readable* in the IR (authors must
  be able to escape to raw rules — inspect the emitted `grammar.json`).

**Run 2 — the conflict-fix loop (the bite).** Take the same grammar and plant
2–3 genuine conflicts (a precedence gap, a dangling else, a postfix-vs-binary
interaction). For each: the loop must surface `GrammarConflictError` naming the
**per-production DSL source line** (the exact `seq(expr, '+', expr)` argument,
not just the rule), the ambiguous shape, the competing productions, and the
generator's suggested fix — then one fix, re-run, next. Measure iterations to
clean and whether the error's suggestion was sufficient (no CLI-source reading
required). Raw `--json` reports saved verbatim to evidence.

**Run 3 — the honest baseline (the control).** Re-author the SAME grammar the
Phase-2 way (hand-rolled integer ladder, as filtlang does). Compare: authoring
effort (line count, precedence decisions), conflict count, and fix-loop UX. This
is the "without Phase 3" control. **If Run 1 ≈ Run 3 on the metrics that
matter, that is a no-go signal** — say so plainly.

**Verdict framing (be explicit):** Phase 3 proves the *feel* of bet #1, or it
doesn't. A no-go means the ergonomic idea itself needs rethinking (e.g. the
table-driven ExpressionGrammar is wrong, or the ladder abstraction leaks) — not
that the machinery failed. Also: Phase 2's GO must NOT be used to rubber-stamp
Phase 3; treat this as a fresh go/no-go.

### Supporting surface (the Phase-3 build)

1. **Precedence ladders** (`builder.py`): a declarative ladder helper —
   `g.precedence("or", "and", "compare", "add", "mul", "unary", "call")` —
   that (a) emits a consistent **integer** ladder (per Phase-2 finding:
   integers work for chained ops; named ladders are descending and need
   associativity; int+named never compare), renumbering automatically when a
   level is inserted, or (b) consistently-named via `precedence_ordering` when
   authors prefer names. Attach associativity at the operator, not the integer.
   Keep the raw `prec*` functions as the escape hatch.
2. **`ExpressionGrammar`** (Pratt-style helper): from a table — primaries,
   infix operators with associativity + precedence levels, prefix operators —
   emit the correct `prec.left/right` rules and the choice ladder. Encode the
   Phase-2 layering lesson (unary's operand is the arithmetic layer, NOT the
   full expression — see kitsink §1 / filtlang); handle postfix (call/member)
   with the `prec(1, …)`-on-call pattern from Experiment A/B. Emit
   conflict-free for the common case; escape hatch to raw rules.
3. **Intentional ambiguity opt-in**: `choice(a, b, ambiguous=True,
   dynamic=prec.dynamic("prefer_a", 1))` (or equivalent) synthesizing the
   `conflicts` entry + `PREC_DYNAMIC` wrapper; validated against the CLI
   (Phase-2 kitsink used the whitelist + PREC_DYNAMIC successfully).
4. **Conflict-UX polish** (`conflicts.py`):
   - **per-production source sites** — record the DSL line of each `seq(...)`
     alternative (not just the `rule()` call), so `GrammarConflictError` points
     at the exact alternative via `production_step_symbols` + `step_index`;
   - **fix-one-rerun loop** as a first-class API (e.g. `g.build_loop()` that
     yields each `GrammarConflictError` and re-runs after the author fixes it —
     generate is sub-second);
   - **`debug_states(rule)`** wrapper over `tree-sitter generate
     --report-states-for-rule <name>` for the "why is my unary/`^` interaction
     wrong?" class of question.
5. **Phase-2A hardening (fold into the first sprint, small):**
   - `alias()` guard: warn/error when `alias` wraps a SEQ (the
     aliases-every-child footgun from kitsink §1.3.3) — require alias over a
     single hidden symbol;
   - nullable non-start-rule guidance: `opt` at the top of a rule is illegal
     (CLI `EmptyString`) — analyzer check + docs;
   - **whitespace-extras default**: grammar.json has NO default whitespace
     (grammar.js's `[\s]` does not carry over) — the builder should default
     extras to `\s` with a declarative override (concept §4.4.6);
   - DSL sugar for `word`/`reserved`/`externals` visibility attributes
     (`rule(..., word=True)`-style or one-liners) if cheap — Phase 2 left these
     raw.
6. **Cheap checks (trivial only):** every emitted grammar generates with exit 0;
   ladder/`ExpressionGrammar` unit cases produce the expected IR; each planted
   conflict in Run 2 cites a real `file:lineno` of the DSL source.

## Out of scope — say no to these (politely)

- **Phase 4 — the bridge.** No `node-schema.json` design, no A-side
  integration, no compile-time query checking. The CLI's `node-types.json`
  byproduct stays on disk, unused.
- **Product A code.** A consumes artifacts only.
- **Full regex-subset validation** (§4.4.7). The cheap slice exists (flags
  only-`i`, the extras-prefix check). A real regex-subset validator against the
  tree-sitter lexer engine is its own project — note what would be needed, don't
  build it.
- **External scanner library / scanner authoring.** externals stay a C escape
  hatch; the pipeline already compiles `scanner.c`.
- **wasm, packaging/wheels, package splitting** (`pydantree_sitter`/`pydantree_sitter`/`pydantree_sitter_grammar`),
  corpus-testing harness (Phase 5), incremental-reparse wrappers, performance
  work.
- **Ergonomics claims beyond the experiment.** Run 1's metrics are evidence, not
  marketing; if the feel isn't there, say so.

## Environment setup (do this first)

1. `devenv shell` — works (fixed in Phase 0). If it isn't, tell the user
   immediately.
2. **Verified facts (don't re-derive):** tree-sitter CLI 0.25.3, bindings 0.26.0
   (`LANGUAGE_VERSION=15`, `MIN_COMPATIBLE=13`), pydantic 2.13.4, gcc 14.2.1.
   ABI 15 via `tree-sitter.json`; conflicts = exit 1, first-only, `--json` on
   stderr; load via PyCapsule `tree_sitter.Language`; unused rules silently
   pruned. All in `src/pydantree_sitter_grammar/pipeline.py` + Phase-2 FINDINGS appendix.
3. **Where the code goes:** extend **`src/pydantree_sitter_grammar/`** (builder.py, checks.py,
   conflicts.py; new `expressions.py` for the ExpressionGrammar helper if it
   grows), pytest tests under `tests/`. The package is editable-installed
   (`uv pip install -e .`) — `import pydantree_sitter_grammar` works. **Do not touch
   `src/pydantree/`.** The new work lives under
   `.scratch/005-grammar-glr/` (experiments, the Run-1 grammar, evidence/).
4. **Before writing helpers**: re-run Phase 2's `experiment_b.py` (or at least
   its conflict stage) so you have a warm pipeline and the filtlang baseline
   fresh. Then hand-write Run 1's precedence table on paper and predict the
   emitted IR before coding the helper (the Phase-0 "hand-written first"
   discipline, repeated at the helper level).

## Working agreement

- **Commit after each meaningful step** (e.g.
  `pydantree_sitter_grammar: precedence ladder helper emits int ladders, renumbers on insert`,
  `pydantree_sitter_grammar: ExpressionGrammar from a table (layering + postfix handled)`,
  `pydantree_sitter_grammar: ambiguity opt-in synthesizes conflicts + PREC_DYNAMIC`,
  `pydantree_sitter_grammar: per-production conflict sites + fix-one-rerun loop`,
  `pydantree_sitter_grammar: Phase-3 experiment — bet #1 feel verdict, evidence captured`).
- **Write findings as you go** into `.scratch/005-grammar-glr/FINDINGS.md`.
  The code is the foundation; the findings are the deliverable.
- **Don't gold-plate.** 80%-done steps get a note and a move-on.
- **Don't fake the primary experiment.** Run 1's corpus, Run 2's conflicts, and
  Run 3's baseline must be real, CLI-validated, and ground-truthed by hand. Save
  raw generator output verbatim under `.scratch/005-grammar-glr/evidence/`.
- **Ask before expanding scope** beyond this brief.

## Deliverables (end of session)

1. Working Phase-3 extensions in `src/pydantree_sitter_grammar/` (ladder helper,
   `ExpressionGrammar`, ambiguity opt-in, per-production conflict sites + fix
   loop, the Phase-2A hardening items) with pytest tests, all committed.
2. Demonstrated, with evidence:
   - (a) Run 1: helper-built grammar → clean analyze → generate (ABI 15) →
     compile → load → correct CST against hand-computed ground truth, with the
     effort/conflict metrics recorded;
   - (b) Run 2: each planted conflict remapped to the **per-production** DSL
     `file:lineno` with ambiguous shape + competing productions + suggested fix,
     and the fix loop driven to a clean generate;
   - (c) Run 3: the same grammar hand-rolled the Phase-2 way, with the
     comparison table.
3. `.scratch/005-grammar-glr/FINDINGS.md` answering at minimum:
   - Does the ergonomics layer **change the feel** (the bet-#1 question)? Where
     does the ladder/ExpressionGrammar abstraction leak, and what must authors
     still hand-tune?
   - Which §4.4 techniques landed cleanly and which didn't (and what that says
     about the concept)?
   - What does the **full Product B** still need (gaps vs §4) — and is any of it
     a blocker for Phase 4 (the bridge)?
   - Re-assess **§11 risks** from the authoring side (1 — conflict diagnostics
     now at per-production granularity; 6 — regex subset; and anything Phase 3
     surfaced).
   - **Recommendation:** go / go-with-changes / no-go on bet #1, and the single
     most important next step (is it Phase 4 — the bridge — or a Phase-3A
     hardening pass, or a rethink?).
4. Everything committed and pushed.

## Appendix — durable facts Phase 3 builds on (from Phase 2, all CLI-verified)

1. Start rule = first `rules` entry; no `start` field; unused rules silently
   pruned (word/extras/externals references protect).
2. Non-start rules must not be nullable (`EmptyString`); inline rules must not
   be tokens; `alias` should wrap a single hidden symbol (alias-on-SEQ aliases
   every child).
3. **Precedence:** shift-vs-reduce compares the shifted item's prev-step
   precedence vs the reduction's precedence. Integer ladders work for chained
   ops; **named ladders are descending (first = highest) and need
   associativity** (`prec_left`/`prec_right`) for chaining; **named vs integer
   precedence never compare** — layer the grammar (unary's operand = arithmetic
   layer, not the full expression) instead of mixing in one rule. The
   `- a or b` (int 4 vs named "or") conflict is the canonical demonstration.
4. Every rule in `rules` is a NAMED node type (even single-string bodies);
   anonymous tokens are inline literals only — a `compare_op: choice("<", ">")`
   rule is a named node, so inline the literals for anonymous operators.
5. `reserved`: first set is global; `RESERVED` nodes override per position;
   empty array = contextual keywords allowed.
6. Extras with a token-prefix overlap must be a named rule + SYMBOL reference.
7. Externals need a compiled `scanner.c` (parser.c only declares the symbols);
   the scanner must skip whitespace itself.
8. Conflicts: exit 1, first only, `--json` on stderr; `possible_resolutions`
   gives the fix text (`Associativity`/`AddConflict`/`Precedence`); generate is
   sub-second → fix-one-rerun is viable. `--report-states-for-rule <name>` is
   the debugging surface.
9. ABI 15 via `tree-sitter.json` `{"metadata":{"version":"0.1.0"}}`; load via a
   PyCapsule named `tree_sitter.Language`.
10. The Phase-2 builder surface to extend: `prec*`, `precedence_ordering`,
    `conflict()`, `alias()`, `rule(..., hidden=/inline=/supertype=)`, `word()`,
    `extra()`, `external()`, `reserved_word()`, operators `+`/`|`/`.star()`/
    `.plus()`/`.opt()`/`.capture()`. Baseline hand-rolled ladder: filtlang's
    `COMPARE, ADD, MUL, UNARY = 1, 2, 3, 4` + `prec_left(ADD, seq(...))`.
