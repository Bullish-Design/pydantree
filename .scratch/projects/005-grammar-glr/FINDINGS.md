# Phase 3 — the GLR-ergonomics layer: Findings & Verdict

**Date:** 2026-08-02
**Status:** COMPLETE
**Verdict: GO on bet #1** — the ergonomics layer changes the feel of GLR
authoring, measurably and honestly. This is a *fresh* go/no-go, not a
Phase-2 rubber-stamp: the go rests on Run 1's decision-count metrics, Run 2's
per-production bite, and Run 3's control — and on a candid account of where
the ladder/ExpressionGrammar abstraction leaks (it does, in two specific
places, both documented below).

Everything here ran against the real toolchain (tree-sitter 0.25.3, gcc
14.2.1, py-tree-sitter 0.26.0, ABI 15). The Phase-3 surface lives in
`src/pydantree_sitter_grammar/` (builder ladder + per-production sites, `expressions.py`,
ambiguity opt-in, `build_loop`/`debug_states`, Phase-2A hardening) with 28 new
pytest tests (69 total). Raw generator output is saved verbatim under
`evidence/`. Re-run:

```bash
devenv shell -- python .scratch/005-grammar-glr/experiment_phase3.py
devenv shell -- python -m pytest tests/
```

---

## 0. What was built (the surface, in one screen)

```python
prec = g.precedence("or", "and", "not", "compare", "add", "mul",
                    "unary", "pow", "postfix")     # ladder: loose -> tight
tg.expression(g, "expr",
    primary=choice(number, string, identifier, seq("(", ref("expr"), ")")),
    infix=[("+", "left", "add"), ("*", "left", "mul"),
           ("^", "right", "pow"), ...],
    prefix=[("-", "unary"), ("not", "not")],
    postfix=[("call", "postfix", lambda e: seq(e, "(", opt(ref("args")), ")")),
             ("member", "postfix", lambda e: seq(e, ".", ref("identifier")))],
    ladder=prec)
g.rule("if_stmt", seq(...), ambiguous=True)        # dangling-else opt-in
g.rule("identifier", pattern(...), word=True)      # visibility sugar
# whitespace extra is a sane default; zero conflict() calls; zero prec* calls
```

Supporting: `Ladder.insert()` renumbers automatically; named-mode ladders emit
a descending `precedence_ordering`; `GrammarConflictError` cites the exact
`seq(...)` alternative line (not just the `rule(...)` call); `build_loop()`
is the fix-one-rerun loop; `debug_states(rule)` wraps
`--report-states-for-rule`.

---

## 1. Run 1 — the helper-built grammar (the pitch): PASS

`qfilter` (`.scratch/005-grammar-glr/qfilter.py`) — a query/filter language
with a genuinely tricky operator surface — authored **entirely** through the
new surface: 9-level declarative ladder, ExpressionGrammar table (left-assoc
`+ - * /`, right-assoc `^`, prefix `-`/`not`, postfix call+member — all
interacting), dangling-else opt-in, `word=True`, sane-default whitespace,
hidden-rule+alias, supertype, fields.

**Pipeline:** analyzer clean → generate exit 0 (ABI 15) → gcc → load →
parse. **Ground truth:** 22 expression + 7 statement cases, hand-computed and
asserted as CST shapes — ALL PASS, including the subtle ones:
`-a ^ b → -(a^b)` (unary looser than `^`, Python semantics), `-f(a) → -(f(a))`
(postfix tighter than unary), `not a == b → not (a==b)`, `a.b.c` chaining,
`f(x)(y)` chaining, `-a or b` (the Phase-2 canonical named-vs-int demo,
unreachable through the helper by construction), greedy dangling else,
keyword rejection via `word`.

**Metrics vs the hand-rolled baseline (see Run 3 for the control):**

| metric | helper (Run 1) | hand-rolled (Run 3) |
|---|---|---|
| precedence integers the author writes | **0** (9 level names, one call) | 9 magic constants |
| `prec*` annotations the author writes | **0** (the table drives them) | 15 explicit calls |
| renumbering when a level is inserted | automatic (`insert()` recomputes) | manual, every time |
| `conflict(...)` entries | 0 (`ambiguous=True` synthesizes) | 1 + manual `prec_dynamic` |
| whitespace/`word` calls | 0 (default / `word=True`) | 1 + 1 |
| conflicts to resolve | 0 | 0 |
| correctness vs ground truth | 22/22 | 22/22 |

**IR readability (the escape-to-raw-rules metric):** the emitted `expr` rule
(`evidence/r1_expr_rule_ir.json`) is exactly the filtlang-proven shape — one
choice, 15 `PREC*` alternatives like `PREC_LEFT 1 → [expr, or, expr]` — the
helper emits the same IR a competent author would hand-write, minus the
bookkeeping. Readable, escapable.

---

## 2. Run 2 — the bite, and the fix-one-rerun loop: PASS (at per-production granularity)

Three genuine conflicts planted on the same grammar, each driven to a clean
generate through `build_loop` in **2 iterations (1 conflict + 1 fix)**. Raw
`--json` reports saved verbatim (`evidence/r2_C1/C2/C3_conflict.json`). The
`GrammarConflictError` for each cites the **exact `seq(...)` alternative
line**, the ambiguous shape, the competing productions, and the generator's
suggested fix:

- **C1 precedence gap** — raw escape-hatch `expr` rule with no precedence:
  `Ambiguous shape: expr '+' expr • '+'`, both interpretations mapped to the
  `tg.seq(tg.ref("expr"), "+", tg.ref("expr"))` line; fix applied was the
  generator's own `Associativity` suggestion. The ladder + helper make this
  class of bug unreachable by construction (they only emit annotated
  alternatives).
- **C2 dangling else** — `if_stmt` without the opt-in:
  `'if' '(' expr ')' 'if' '(' expr ')' statement • 'else'`; fix = the
  declarative `ambiguous=True` (one line). PREC_DYNAMIC + conflicts entry
  synthesized and CLI-validated; the whitelisted grammar parses greedy.
- **C3 postfix × bare-cond if** — the interaction the probe surfaced (below):
  `'if' expr '(' expr • ')'` mapped to **both** the `args` seq line and the
  parens seq line; fix = the real-language pattern (parens-delimit the cond).

No CLI-source reading was required for any fix; the error message carried
enough. The per-production mapping uses the CLI's
`production_step_symbols`+`step_index` against a per-node combinator-site
registry — the Phase-2 §3 mechanism, refined from per-rule to per-alternative.

---

## 3. Run 3 — the honest baseline (the control): Run 1 ≠ Run 3 on the metrics that matter

Re-authored the SAME grammar the Phase-2 way (`qfilter_handrolled.py`:
filtlang's `OR..POSTFIX = 1..9` + 15 explicit `prec*` calls + `conflict()`
+ manual `prec_dynamic` + explicit extras/word). Same pipeline, same corpus,
all 22/22. A competent hand-roll of the proven filtlang pattern is also
conflict-free — that is expected and is exactly why the comparison is honest:
**conflict-count parity with a competent baseline is not a no-go signal; the
differentiator is the 24 hand-written precedence decisions + the manual
renumbering tax, both gone in Run 1, plus the fix-loop UX.** (Against a
*naive* hand-roll — the Phase-2 `b5` grammar, or the postfix-below-unary
mistake — the helper prevents the whole class; probe 1 demonstrated the
postfix-below-unary variant generates clean but parses `-f(x)` as `(-f)(x)`,
which the ladder's postfix-at-top makes unreachable.)

**Run 1 ≈ Run 3 would have been a no-go signal; it is not.** The feel metric
— decisions, renumbering, bite-localization — favors Run 1 decisively.

---

## 4. Where the abstraction leaks (honest, and what it means)

1. **The ladder encodes semantics, not just conflict-freedom.** The helper
   guarantees a *consistent* precedence ladder (the Phase-2 named/int-mixing
   failure is unreachable through it) and it guarantees *conflict-free for
   the common case* — but it cannot verify *semantic intent*. Whether
   `-a ^ b` is `-(a^b)` or `(-a)^b`, and whether `-f(x)` is `-(f(x))` or
   `(-f)(x)`, is decided by the ladder's relative ordering — the author's
   judgment. A wrong ordering generates clean and parses wrongly. Mitigations
   shipped: the probe-verified finding that **postfix must outrank the unary**
   is in the helper's docstring and the ladder-level error message
   ("postfix belongs at the top"), and Run 1's corpus discipline is the real
   guard. This is the deepest leak and the strongest argument for the §4.8
   corpus harness (Phase 5).
2. **Postfix × bare-cond `if` is a genuine language-design interaction the
   helper does not prevent.** With an expr-callee call (`expr ( args )`), an
   `if <bare expr> <statement>` construct makes `if x (y)` ambiguous
   (cond=`x(y)` call vs then=`(y)` parens). Real languages dodge it by
   parens-delimiting the condition (`if (x)`); the helper's Run-1 grammar does
   exactly that, and Run 2 C3 shows the bite lands locally with the right
   diagnosis when an author hits it. Not prevented-by-construction — a
   documented author responsibility. (filtlang's identifier-callee call dodged
   it structurally but at the cost of call-chaining `f(x)(y)`, `a.b(x)`; the
   helper keeps the full postfix power and documents the trade.)
3. **The raw escape hatch is the Phase-2 world.** Dropping to `prec*`
   reintroduces magic integers and named/int mixing; the analyzer's mixing
   warning is load-bearing, and Run 2 C1 is the canonical reintroduced gap.

The layering lesson from Phase 2 (kitsink's "unary's operand is the
arithmetic layer") turned out, under probing, to be a *named-vs-int mixing*
symptom: with one consistent ladder (int or named), the single-rule form needs
no physical layering — the ladder does the work. Probe 2 verified both modes
generate clean and parse all 21 cases identically. The helper encodes the
lesson as **consistency + postfix-at-top** rather than rule splitting — and
probe 2 also showed the physical-layering alternative (hidden `_arith` rule)
flattens the CST into un-parseable mixed-op nodes, a real consumer cost.

---

## 5. §4.4 techniques — landed / not landed

| §4.4 | technique | status |
|---|---|---|
| 1 | declarative precedence ladders | **LANDED** — int mode (renumber-on-insert) + named mode (descending ordering) both CLI-validated; no magic integers |
| 2 | ExpressionGrammar | **LANDED** — table → single readable rule; layering lesson encoded as ladder consistency + postfix-at-top; leak = semantic intent (see §4) |
| 3 | conflicts → your Python source | **LANDED** — per-production sites (exact `seq(...)` line) on 3 real conflict classes |
| 4 | intentional ambiguity opt-in | **LANDED** — `ambiguous=True` synthesizes PREC_DYNAMIC + conflicts; dangling else CLI-validated greedy |
| 5 | visibility/structure attributes | Phase-2 + `word=True` sugar; alias-on-seq footgun now a construction-time error |
| 6 | sane defaults | **LANDED** — whitespace-extras default kills the Phase-2 §2.1 pain point |
| 7 | regex-subset validation | not built (out of scope; cheap slice exists) — see §6 |
| 8 | lean into left recursion | implicit: every expression alternative is left-recursive; the helper's design assumes it |

---

## 6. Gaps vs §4, and §11 risk re-assessment

**Full Product B still needs** (none is a Phase-4 blocker):
- §4.4.7 regex-subset validation — a real validator against the tree-sitter
  lexer engine (or a port of its regex subset) is its own project. The
  known hazard class (extras-prefix overlap, comment-vs-token) is covered by
  the analyzer.
- §4.6 external-scanner library + §4.8 corpus harness — Phase 5. The corpus
  harness is now the *most* valuable Phase-5 item: it is the systematic guard
  for §4's semantic-intent leak.
- **Phase-3A hardening (recommended, small):** a helper-level "semantic
  smoke" — e.g. the ExpressionGrammar could auto-emit a default
  precedence-corpus (the probe-2 table is exactly that) so semantic regressions
  (`-a^b`, `-f(x)`) are caught at author time, not in the field. Also worth
  adding: a `cond=`/`non_call_primary` affordance so the postfix×if pattern
  (§4.2) has a typed spelling instead of a documentation note.

**§11 risks, authoring side:**
- **§11.1 conflict diagnostics — RETIRED at per-production granularity.** The
  CLI's `production_step_symbols` + `step_index` is detailed enough to map
  every interpretation to the exact `seq(...)` line (Run 2). Residual:
  field-bearing and repeat-bearing conflicts were not exercised, and a
  conflict-free grammar can still be semantically wrong (the §4 leak — that is
  a *testing* gap, not a diagnostics gap).
- **§11.6 regex-subset friction — unchanged**, narrow-but-real; the extras
  check covers the known class.
- **Newly surfaced:** postfix × bare-cond ambiguity (§4.2) — a genuine
  language-design class; the answer (parens-cond) is a documented author
  pattern, and the ergonomics layer localizes it when it bites.

---

## 7. The bet-#1 question, answered

**Does the ergonomics layer change the feel? Yes.** The pitch (Run 1) is a
tricky grammar with **zero** magic integers, **zero** prec annotations, and
**zero** conflict entries — generated clean first try and ground-truthed by
hand. The bite (Run 2) lands on the exact `seq(...)` line with the fix text,
and the fix loop is one iteration. The control (Run 3) is identical in output
but costs 24 precedence decisions and a standing renumbering tax. Bet #1 —
"GLR conflict/precedence pain becomes typed, declarative, source-located
Python" — is **won for the common case**, with the honesty line intact:
authors still choose the ladder's *semantics*, and two interaction classes
(postfix-vs-unary intent, postfix×bare-cond if) remain judgment calls the
helpers localize but do not decide.

## 8. Recommendation

**GO.** Phase 3 proves the feel of bet #1; the leaks in §4 are documented
author responsibilities and Phase-3A hardening items, not design failures.
The single most important next step is **Phase 4 — the bridge**
(node-schema emission + Product A compile-time query checking): nothing Phase 3
surfaced blocks it, and it is the capability neither half can provide alone.
Do a short Phase-3A hardening pass alongside it (the semantic-smoke corpus and
the `cond=` affordance from §6) — neither is a blocker, both close the
honest leaks this experiment found.

---

## Appendix — durable facts Phase 3 established (all CLI-verified)

1. **Single-rule consistent-ladder emission is conflict-free for the full
   tricky operator set** (or/and/not/compare/+/−/×/÷/right-^/unary/call/member
   all interacting) — verified on 21+22 corpus cases, int and named modes.
   Physical layering (hidden `_arith`) is *not* needed when the ladder is
   consistent, and it flattens the CST into mixed-op nodes — worse for
   consumers.
2. **Postfix must OUTRANK the unary in the ladder.** With an expr-callee call,
   postfix-below-unary parses `-f(x)` as `(-f)(x)` (generates clean — a
   silent semantic error, probe 1). postfix-above-unary gives `-(f(x))`
   (probe 2). The Phase-2 `prec(1)`-on-call pattern worked only because
   filtlang's callee was a bare identifier.
3. **`-a ^ b` → `-(a^b)` needs unary BELOW pow** (Python semantics);
   `-a * b` → `(-a)*b` needs unary ABOVE mul. The ladder's relative order is
   the semantic decision; the helper guarantees consistency, not intent.
4. **expr-callee calls + bare-cond `if <expr>` conflict** (args-vs-parens on
   `'if' expr '(' expr • ')'`); parens-delimited `if (expr)` is clean. Real
   grammars (C/JS/Python) all parens-delimit. filtlang's identifier-callee
   dodges it but loses `f(x)(y)`/`a.b(x)`.
5. **The CLI's conflict report carries enough for per-production remapping:**
   `production_step_symbols` renders SYMBOL as the rule name and STRING as
   `'value'`; matching choice alternatives against these lists resolves the
   exact `seq(...)` line (verified on 3 conflict classes).
6. **Equal-precedence postfix chaining is structurally safe**: `a.b.c` and
   `f(x)(y)` need no associativity because the reduce state and the next-shift
   state are separate (verified in build_parse_table.rs + empirically).
7. **Named and int ladders both generate clean and parse identically** for
   this operator set; named mode's value is IR readability, int mode's is
   simplicity. The named ordering must be emitted descending (first = highest)
   and multiple `precedences` entries are separate orderings (first containing
   both names decides).
8. **`ambiguous=True` = PREC_DYNAMIC(1, body) + conflicts [[rule]]** — the
   exact kitsink-proven shape; generates clean and resolves greedy.
9. The Phase-2A hardening items all verified: alias-on-seq is a
   construction-time error; nullable non-start rules are analyzer errors
   (start rules may be nullable); the whitespace-extras default fixes the
   Phase-2 §2.1 "first inputs failed on spaces" class; `word=True` is sugar.
