# Phase 0 Spike — Findings & Verdict

**Date:** 2026-08-02
**Status:** COMPLETE
**Verdict:** **GO** (with the changes listed in §7)

Everything in this file was verified against a real tree-sitter CLI (0.25.3)
and real generator output — no simulation. Evidence (raw generator output,
byte-for-byte) is in `spike/evidence/`. The code that produced these results is
in `spike/` (IR → `grammar.json` → generate → compile → parse).

---

## 0. Environment that produced these results

| Piece | Version | Notes |
|---|---|---|
| tree-sitter CLI | **0.25.3** | nixpkgs attr `pkgs.tree-sitter` (not `tree-sitter-cli`) |
| Python bindings | **tree-sitter 0.26.0** | `LANGUAGE_VERSION=15`, `MIN_COMPATIBLE=13` |
| pydantic | 2.13.4 | |
| gcc | 14.2.1 | via devenv |
| ABI generated | 14 (no config) / **15** (with `tree-sitter.json`) | both load fine |

Devenv changes: added `pkgs.tree-sitter` + `pkgs.gcc`, fixed the missing
`pre-commit-hooks` input (`devenv update pre-commit-hooks`).

**ABI / config discovery:** without a `tree-sitter.json`, the CLI prints a
warning and falls back to ABI 14. With a `tree-sitter.json` containing just
`{"metadata": {"version": "0.1.0"}}`, it generates ABI 15, which the Python
bindings accept and which also populates `Language.name`. The loader path that
works on py-tree-sitter 0.26 is a **PyCapsule named `"tree_sitter.Language"`**
created via `ctypes.pythonapi.PyCapsule_New` over the `tree_sitter_<name>()`
export — integer pointers are deprecated and warn.

---

## 1. Does the `grammar.json` round-trip work cleanly? — YES, with real findings

The full pipeline works end-to-end (see `spike/main.py`):

```
Pydantic IR  --emit-->  grammar.json  --tree-sitter generate-->  parser.c
  --gcc-->  .so  --PyCapsule-->  tree_sitter.Language  --parse-->  correct CST
```

The DSL-emitted `grammar.json` for the fixed spike grammar is **semantically
identical** to a hand-written reference that was validated against the CLI by
hand first (`spike/main.py` stage 2 asserts this). The DSL-emitted and
hand-written grammars produce **byte-identical conflict JSON** (see §3).
`GrammarModel.model_validate_json()` round-trips the IR structurally.

### What the concept got wrong / what had to be learned (this is the gold)

1. **There is NO `start` field in `grammar.json` (0.25.3).** The start rule is
   the **first entry of `rules`** (it becomes `Symbol{index:0}`, the start
   production — `build_tables/item.rs`). Worse: the CLI **silently prunes rules
   that are unreachable from that first rule** (`parse_grammar.rs`
   `variable_is_used`), and strips them from `conflicts`/`inline`/`supertypes`/
   `precedences` too. Consequence: a DSL that emits rules in insertion order
   with `source_file` last produced a *successful* generate (exit 0) whose
   parser only knew `number` and `identifier`. This is a silent-footgun class
   that Product B MUST defend against (the "unused rule" static check is not
   optional). Fix implemented: the DSL declares an explicit start rule and
   reorders emission to put it first.

2. **`word` auto-extracts keywords; no `keyword` rule is needed.** Declaring
   `word: "identifier"` makes the CLI generate a keyword lexer
   (`ts_lex_keywords`) and turn word-like STRING literals (`"if"`, `"else"`)
   into keywords that are rejected as identifiers. Verified: `iftrue` parses as
   an identifier, `if + 1` produces an ERROR node.

3. **No `OPTIONAL` node** — `opt(x)` must emit `choice(x, BLANK)` (the concept's
   sketch assumed an Optional node; the real schema has `BLANK`).

4. **`REPEAT` is desugared internally** to `choice(repeat(x), BLANK)` — so
   nullable-in-`REPEAT` is a *semantic* hazard (infinite match), not a CLI error.
   Our static check catches it pre-generate.

5. **`precedences` array = declarative precedence ladder, but it can't mix with
   integers.** Entries are `{STRING | SYMBOL}` where STRING means a precedence
   *name*. Named precedences form a partial order resolved at conflict time
   (`build_parse_table.rs` `compare_precedence`); integer-vs-named comparisons
   don't resolve. Phase 3's `ExpressionGrammar` should emit **integers** (or be
   consistently named), and the DSL should validate against mixing.

6. **`PREC`/`PREC_LEFT`/`PREC_RIGHT` `value` is `int | string-name`**
   (untagged union). `PREC_DYNAMIC` exists and is always int.

7. **`PATTERN` supports only the `i` flag** — `u`/`v` silently ignored, any
   other flag warns on stderr. Phase-3 regex-subset validation should mirror this.

8. **Comments in `extras` must be a named rule referenced via SYMBOL.** Bare
   inline `PATTERN`/`TOKEN` extras whose first char is a token prefix (`/` for
   division) **lose to the token in the lexer and never lex as comments**
   (verified by parsing `1 /* c */ + 2` → ERROR). The fix, matching
   tree-sitter-c: `comment: token(choice(seq("//", …), seq("/*", …)))` with
   `extras: [\s, ref("comment")]`. The load-bearing detail is the SYMBOL
   reference (a bare `TOKEN` inline extra still fails); this belongs in Product
   B's guidance docs.

9. **Fail-fast, first-conflict-only, JSON on stderr.** Unresolved conflict →
   exit code 1, **no `parser.c` written at all**, and with `--json` the machine
   report goes to **stderr**. This makes conflict fixing a deterministic
   iterative loop (fix one, re-run — generate is sub-second).

10. **Unused-rule pruning is silent and aggressive** (see #1). Also: a rule
    that is only referenced by `word` is protected; `externals`/`extras` count
    as references.

11. **`--report-states-for-rule <name>`** prints per-rule LR items with
    lookahead sets and `(Left)`/`(Right)` associativity annotations. Works even
    on grammars with precedence. Excellent Phase-3 debugging surface (e.g. "why
    is my unary/`^` interaction wrong?").

12. `RESERVED` node + grammar-level `reserved` map exist (0.25+ feature) —
    the concept didn't mention them. IR must include them for import/export of
    modern grammars.

---

## 2. Primary experiment: is conflict → Python-source remapping mechanically feasible?

### Verdict: **YES — reliably feasible with the current CLI.**

This was the go/no-go question, and the answer is positive, with the mechanics
demonstrated end-to-end. The evidence is in `spike/evidence/` (raw stderr/stdout
saved verbatim for both experiment cases).

### What machine-readable information exists

`tree-sitter generate grammar.json --json` (exit 1 on conflict) emits a serde
serialization of `GenerateError::BuildTables(ParseTableBuilderError::Conflict)`
to **stderr**:

```json
{
  "BuildTables": {
    "Conflict": {
      "symbol_sequence": ["'if'", "expr", "'if'", "expr", "statement"],
      "conflicting_lookahead": "'else'",
      "possible_interpretations": [
        {
          "preceding_symbols": ["'if'", "expr"],
          "variable_name": "if_statement",
          "production_step_symbols": ["'if'", "expr", "statement"],
          "step_index": 3, "done": true,
          "conflicting_lookahead": "'else'",
          "precedence": null, "associativity": null
        },
        {
          "variable_name": "if_statement",
          "production_step_symbols": ["'if'", "expr", "statement", "'else'", "statement"],
          "step_index": 3, "done": false, ...
        }
      ],
      "possible_resolutions": [
        { "Associativity": { "symbols": ["if_statement"] } },
        { "AddConflict": { "symbols": ["if_statement"] } }
      ]
    }
  }
}
```

Extractable, per conflict:

- **`variable_name`** — the grammar rule (variable) each competing parse belongs
  to. This is the 1:1 key into the DSL's recorded definition sites.
- **`production_step_symbols` + `step_index` + `done`** — the exact production
  shapes competing (e.g. the with-else vs without-else forms of `if_statement`).
- **`symbol_sequence` + `conflicting_lookahead`** — the ambiguous input shape
  (`'if' expr 'if' expr statement • 'else'`).
- **`precedence` / `associativity`** on each interpretation — the current
  precedence context of each competing parse (null here; populated for
  precedence-gap conflicts).
- **`possible_resolutions`** — machine-suggested fixes:
  `Precedence{symbols}`, `Associativity{symbols}`, `AddConflict{symbols}`.
  `AddConflict.symbols` is exactly the `conflicts` array entry to whitelist.
- For conflicts involving **hidden/auxiliary rules**, the report attributes them
  to their visible parent symbols (via `preceding_auxiliary_symbols` in
  `build_parse_table.rs`).

### The remapping (demonstrated)

Two real conflicts were authored, captured verbatim, and remapped:

1. **Precedence gap** — naive `expr` rules (no precedence). The error names
   `g.rule("expr", …)` at `spike_lang.py:85` and `g.rule("expr_statement", …)`
   at `spike_lang.py:57`, shows `expr • '-'`, the competing parses, and the
   generator's suggested fixes.
2. **Dangling else** — correct expression precedence, ambiguous `if`. The error
   names `g.rule("if_statement", …)` at `spike_lang.py:56`, shows
   `'if' expr 'if' expr statement • 'else'`, both production shapes
   (with/without `else`), and `Associativity` / `AddConflict` suggestions.

The `GrammarConflictError` message (see `spike/conflicts.py`) renders:
raw generator text → which of your `g.rule(...)` lines collide → the ambiguous
shape → the competing productions → the canonical fixes. This is precisely the
§4.4.3 promise, and it works on the current CLI with zero patches.

Cross-check: the conflict JSON from the DSL-emitted grammar is **byte-identical**
to the conflict JSON from the hand-written grammar — the emission is faithful,
and the remapping is not an artifact of our own pipeline.

### Honest caveats (what's missing / coarse)

- **Only the FIRST conflict is reported per run.** The CLI is fail-fast
  (`generate_parser_for_grammar_with_opts(...)?` returns the first
  `ConflictError`). Product B should present a "fix one, re-run" loop; generate
  is fast enough (~1s).
- **`grammar.json` carries no source positions.** The CLI reports rule *names*,
  never line numbers. So Product B *must* record definition sites at build time
  (the spike DSL does: file/lineno/source per `rule()` call). This was already
  the plan — confirmed necessary, not optional.
- **Granularity is per-rule (+ production shape), not per-alternative.** The
  DSL records one site per rule; `production_step_symbols` lets us say *which*
  production, but not the DSL line of that specific alternative. Recording
  per-production sites in the DSL would let the error point at the exact
  `seq(expr, '+', expr)` argument line — cheap to add later, not needed for the
  verdict.
- **The text (non-JSON) report is the same data** re-rendered; parsing the JSON
  is strictly better. There is no third, richer machine format in 0.25.3.

---

## 3. What the full GrammarModel IR needs (gaps vs. the real schema)

The spike IR (`spike/grammar_model.py`) mirrors `GrammarJSON` from
`cli/generate/src/parse_grammar.rs` and round-trips. The complete node set the
real schema requires:

| Node `type` | fields | in concept? |
|---|---|---|
| `SYMBOL` | `name` | ✓ |
| `STRING` | `value` | ✓ |
| `PATTERN` | `value`, `flags?` | ~ (flags missing) |
| `BLANK` | — | ✗ (needed for `opt`) |
| `SEQ` / `CHOICE` | `members` | ✓ |
| `REPEAT` / `REPEAT1` | `content` | ✓ |
| `FIELD` | `name`, `content` | ✓ |
| `ALIAS` | `value`, `named`, `content` | ✓ |
| `TOKEN` / `IMMEDIATE_TOKEN` | `content` | ~ (ImmediateToken ok) |
| `PREC` / `PREC_LEFT` / `PREC_RIGHT` | `value: int\|name`, `content` | ~ (value can be a name) |
| `PREC_DYNAMIC` | `value: int`, `content` | ✗ |
| `RESERVED` | `context_name`, `content` | ✗ (0.25+ feature) |

Grammar-level fields: `name` (required), `rules` (required, **ordered — first is
start**), `precedences` (Vec of precedence orderings), `conflicts`,
`externals`, `extras`, `inline`, `supertypes`, `word`, `reserved`. **No
`start` field** — handled by the DSL's start-rule ordering.

Deliberately not built in the spike: `externals` authoring (C scanner wiring),
`reserved` authoring, `alias` in the DSL surface, named-precedence authoring —
the IR validates them, the builder doesn't sugar them yet (Phase 2).

---

## 4. Static checks — what's easy

Implemented in `spike/checks.py` and working: **undefined Symbol refs**,
**nullable-inside-REPEAT/REPEAT1**, **SYMBOL-inside-TOKEN** (mirrors the CLI's
`UnexpectedRule`; `IMMEDIATE_TOKEN` is exempt at top level due to a CLI quirk —
it propagates the current `is_token` flag rather than forcing true).
All three are trivial on the IR.

Two *new* easy checks surfaced by the spike that weren't on the concept's list:
**unused rules** (the CLI drops them silently — a cheap Python check prevents
the "successful generate, missing grammar" trap) and **extras whose first-set
overlaps a token prefix** (the comment-vs-`/` hazard; a first-set overlap check
over `extras × tokens` would predict it).

---

## 5. Verdict

**GO.**

The two things that could have killed the concept both came back positive:

1. `grammar.json`-first emission works cleanly with a stock CLI — the
   `grammar.js`-bypass is real (this was cheap to believe; now it's cheaply
   proven).
2. **The conflict → Python-source remapping is mechanically feasible with the
   current CLI**, via `--json` conflict reports (rule names, production shapes,
   suggested resolutions) + build-time site recording. This was the highest
   risk in §11 and it is retired as a go-blocker, downgraded to a UX polish
   item (per-production sites, fix-one-re-run loop).

The concept needs the small amendments in §7, but none of them change the
architecture.

---

## 6. Re-assessment of §11 risks

| # | Risk | Now |
|---|---|---|
| 1 | **Conflict diagnostics quality** (was: highest risk) | **RETIRED as go-blocker.** Machine-readable, source-mappable conflict output exists and was demonstrated. Remaining work is polish: per-production sites, iterative fix loop UX. |
| 2 | External-scanner frequency | Unchanged — untested in Phase 0; still an honest escape hatch, not a Phase-0 question. |
| 3 | Toolchain packaging (Rust CLI + C compiler) | De-risked: `pkgs.tree-sitter` + `pkgs.gcc` in devenv worked with zero friction. Cross-platform packaging remains a Phase-5 distribution question. |
| 4 | Upstream churn | Real: 0.25.3 schema differs from older assumptions (`RESERVED`, `precedences`, `start`-less, keyword-lexer). Mitigation: pin ABI + CLI version, treat `grammar.json` as a versioned schema (this spike documents 0.25.3 exactly). |
| 5 | wasm runtime perf | Untested (Phase 5). |
| 6 | Regex-subset friction | Partially surfaced: the comment-extras lexing subtlety (§1.8) is the kind of surprise authors will hit; author-time guidance + first-set overlap check should cover it. Full regex-subset validation untested. |
| 7 | node-schema completeness | Untested (Phase 4). The CLI generates `node-types.json` on every successful generate — the derivation source exists. |

---

## 7. Changes the concept needs (go-with-changes items)

1. **Start rule is order-based, not a field.** The DSL needs an explicit
   `start(name)` declaration and must emit the start rule first; add "unused
   rule" to the mandatory static checks (the CLI's silent pruning is a
   footgun).
2. **Comments/extras authoring rule**: named rule + SYMBOL reference in
   `extras`, never a bare inline pattern whose prefix is a token.
3. **Conflict UX is a loop**: report one conflict at a time with source sites
   + suggested fix, re-run. Product B should make this loop first-class (the
   generator's `possible_resolutions` give us the fix suggestions for free).
4. **Phase 3 precedence ladder**: emit integer precedence (or consistently
   named); mixing named and integer precedence does not compare in 0.25.3.
5. IR additions for the real schema: `BLANK`, `PREC_DYNAMIC`, `RESERVED`,
   `PATTERN.flags`, `precedences` array, `reserved` map (all present in the
   spike IR).

---

## 8. Recommendation for the next step

Per the concept's §9 sequencing, the next step is **Phase 1 — Product A
(pydantree_sitter) MVP over community grammars**: query DSL → `.scm`, capture →
`OutputModel`, shipping over prebuilt wheels (e.g. `tree-sitter-python`,
already a dev dep). Phase 0 has proven B's core mechanics, so B is de-risked;
A is the path that delivers standalone value earliest and stress-tests the
consumption ergonomics against real trees. Phase 2 (Product B core: full IR +
analyzer + build pipeline) is now a well-specified, low-risk build — the DSL,
site recording, emission, and conflict remapping already exist in spike form.

---

## Appendix A — how to re-run

```bash
devenv shell -- python .scratch/002-pydantic-treesitter/spike/main.py
```

Stages: (1) IR round-trip, (2) emit-vs-hand-written-reference, (3) static
checks, (4) conflict experiment → remapped `GrammarConflictError`s (raw output
saved to `spike/evidence/`), (5) fixed grammar → generate/compile/load/parse
with precedence/associativity/keyword/comment verification, (6) intentional
ambiguity via `conflicts` whitelist.
