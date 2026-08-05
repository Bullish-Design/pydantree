# Phase 2 — pydantree_sitter_grammar core: Findings & Verdict

**Date:** 2026-08-02
**Status:** COMPLETE
**Verdict:** **GO** — the core is mechanically sound at full schema fidelity,
end-to-end, and the two go/no-go experiments both pass with honest evidence.
Phase 3 (the GLR-ergonomics layer) is the right next step; a short Phase-2A
hardening list (below) is worth doing inside Phase 3's first sprint rather
than as a separate phase.

Everything here ran against the real toolchain (tree-sitter CLI 0.25.3, gcc
14.2.1, pydantic 2.13.4, py-tree-sitter 0.26.0) — no simulation. Raw
generator output is saved verbatim under `evidence/`. The package is
`src/pydantree_sitter_grammar/` (IR, builder, analyzer, pipeline, language, conflicts) with
pytest tests in `tests/`. Re-run:

```bash
devenv shell -- python .scratch/004-pydantree_sitter_grammar/experiment_a.py
devenv shell -- python .scratch/004-pydantree_sitter_grammar/experiment_b.py
devenv shell -- python -m pytest tests/
```

---

## 0. Environment (unchanged from Phase 0, re-verified)

| Piece | Version |
|---|---|
| tree-sitter CLI | 0.25.3 (nixpkgs `pkgs.tree-sitter`) |
| py-tree-sitter | 0.26.0 (LANGUAGE_VERSION 15, MIN_COMPATIBLE 13) |
| pydantic | 2.13.4 |
| gcc | 14.2.1 |
| ABI generated | 15 (via `tree-sitter.json` `{"metadata":{"version":"0.1.0"}}`) |

Editable install: `uv pip install -e .` works; `src/pydantree_sitter_grammar` added to the
hatch wheel packages in `pyproject.toml`. `import pydantree_sitter_grammar` works in the
venv (no sys.path shim needed).

---

## 1. Experiment A — is the IR faithful to the real 0.25.3 schema? **YES**

`evidence/` holds the raw CLI output. The experiment (`.scratch/004-pydantree_sitter_grammar/
experiment_a.py`) is the Phase-0 "hand-written first" discipline repeated at
full scale:

1. A **hand-written `grammar.json`** (`reference/grammar.json`, "kitsink")
   exercises the *entire* schema surface — all 17 rule-node types and all 10
   grammar-level fields — and was **validated against the CLI first** (exit 0),
   then compiled (with a hand-written `scanner.c`, see §1.4) and parsed a
   corpus with **zero ERROR nodes**.
2. `GrammarModel.model_validate_json` imports it; re-emission is
   **semantically equal** to the hand-written reference (normalized: empty
   lists/None dropped) — the IR is faithful.
3. The re-emitted grammar regenerates (exit 0, ABI 15), compiles, loads via
   PyCapsule, and parses the same corpus cleanly.

**The Phase-0 §3 table needed nothing added** — every node type and field
listed there round-trips, including `PREC*` with name values, `PREC_DYNAMIC`,
`RESERVED`, `PATTERN.flags`, the `precedences` array, and the `reserved` map.
The schema was re-confirmed directly against the CLI source at
`/tmp/tree-sitter/cli/generate/src/parse_grammar.rs` (`GrammarJSON`,
`RuleJSON`, `PrecedenceValueJSON = Integer | Name` untagged).

**A real published grammar also round-trips** (the kickoff's preferred
additional import test, found offline in the nix store): `tree-sitter-bash`
0.25.1 (101 rules, 179 KB, committed under `community/bash/`) imports into
the IR, re-emits **semantically equal** to the published file, and the
re-emitted form regenerates with the stock CLI (exit 0). Two details this
surfaced: published grammars carry a `$schema` key (not part of the schema —
the IR drops it via a before-validator while staying strict about everything
else), and bash's start rule `program` is nullable — confirming the
start-rule-nullable exception in the wild.

### 1.1 What the full-schema reference actually does (all verified at parse time)

| Construct | Exercise | Result |
|---|---|---|
| `word` + keyword exclusion | `fn = 1` | keyword rejected as identifier ✓ |
| `extras` comment rule | `//`, `/* */` | lexes (named rule + SYMBOL) ✓ |
| named precedence | `a or b and c` | `a or (b and c)` ✓ |
| `precedences` ladder | `[and, or]` | first = **highest** (descending) ✓ |
| dangling else + `conflicts` | `if a if b c; else d;` | whitelisted, greedy ✓ |
| `PREC_DYNAMIC` | if_stmt body | generates + parses ✓ |
| `IMMEDIATE_TOKEN` | `foo:` labels | `foo : x` (spaced) errors ✓ |
| `FIELD` | name/value/arg/param/cond | fields in CST + node-types ✓ |
| `ALIAS` on hidden rule | `_tuple` → `tuple` | clean tuple node ✓ |
| `inline` | `params`, `member` | no params/member nodes ✓ |
| `supertypes` | `statement` | subtype list in node-types ✓ |
| `reserved` words | `{ if: 1 }` (property ctx) | contextual keywords ✓ |
| `externals` + scanner | `# sigil` (TERM token) | scanner-produced token ✓ |
| `REPEAT1`, `BLANK` via `opt`, `TOKEN` string, `PATTERN.flags` hex | | all ✓ |

### 1.2 Grammar-level schema facts re-verified from source (durable)

- `rules` is an **ordered map; the first rule is the start** (no `start` field).
- `reserved` is `Map<String, Vec<Rule>>` — the **first set is the global
  reserved-word set**; `RESERVED{context_name, content}` nodes override it
  per-position; an **empty array disables reserved words in that context**
  (the contextual-keyword trick, from the tree-sitter test grammar
  `reserved_words` and `dsl.js`).
- `precedences` is `Vec<Vec<Rule>>` with **STRING/SYMBOL entries only**
  (`Unexpected` error otherwise).
- `PATTERN` flags: `i` honored, `u`/`v` silently ignored, anything else
  warns on stderr.
- Non-start rules **must not be nullable** (`EmptyString` error) — see §5.
- Inline rules **must not be tokens** (`Token ... cannot be inlined`).

### 1.3 Corrections to Phase-0's §3/§4 claims (found by building, not reading)

1. **`IMMEDIATE_TOKEN` with a bare SYMBOL is REJECTED by the CLI.** Phase-0
   claimed it was "exempt at top level due to a CLI quirk" (parse_grammar.rs
   propagates the current `is_token` flag, so the parse-grammar check passes).
   Phase 2 planted it: `generate` exits 1 with
   `Unexpected rule` from the token-expansion phase (`extract_tokens`/
   `expand_tokens`). The analyzer now flags SYMBOL inside **both** TOKEN and
   IMMEDIATE_TOKEN (`evidence/b4_immediate_quirk_stderr.txt`).
2. **Every rule in `rules` is a NAMED node type — even a single-string rule**
   (`semicolon: ";"` → named `semicolon`; `compare_op: choice("<",">")` →
   named `compare_op`). Anonymous tokens are only inline string literals.
   Consequence: authors who want anonymous operators should inline the
   literals in the production, not wrap them in a rule (Phase-3 guidance).
3. **`alias()` on a sequence aliases *every* named child** (flatten applies
   the alias metadata to each step) — `alias("tuple", true, seq(...))` made
   four `tuple` nodes. The canonical pattern is `alias` over a **single hidden
   symbol**: `_tuple: alias("tuple", True, ref("_tuple_contents"))`. This is
   a genuine DSL footgun class to document.

### 1.4 externals & scanners (the one place the story gets honest)

Declaring `externals` is free in the IR, but the generated `parser.c` only
*declares* the scanner symbols (`tree_sitter_<name>_external_scanner_*`).
Without a `scanner.c`, **dlopen fails at load time** (undefined symbol), and
with one, the scanner is invoked *before* the main lexer skips extras, so it
must skip whitespace itself. The pipeline compiles `src/scanner.c` when
present. This matches the concept's honesty line (§4.6): externals are a C
escape hatch, and Phase 2 proves the plumbing around them works.

---

## 2. Experiment B — does the DSL-authored pipeline hold end-to-end? **YES**

`filtlang.py` is a nontrivial filter/expression language authored *entirely*
through the builder DSL: tokens, `word`, fields, named-comment extras
(Phase-0 rule), opt/repeat, a hidden rule with an alias, a supertype, an int
precedence ladder (add/mul/unary/compare), and a conflicts whitelist
(dangling else). Pipeline: **analyze clean → generate (exit 0, ABI 15) →
gcc → load via PyCapsule → parse**, with a content-addressed cache.

Ground truth was computed by hand and asserted as CST shapes; all pass,
including the subtle ones: `a < b` parses via a **named** `compare_op` child,
`-a + b` → `(-a)+b`, `f(a, 1+2)` → call with `arguments` alias + fields,
`f()` → empty-args via the BLANK choice, comments, keyword exclusion, and the
whitelisted dangling else resolving greedy.

### 2.1 Where it broke / got ugly (honest list)

1. **No default whitespace extra.** grammar.json has no default extras (the
   grammar.js default `[\s]` does not carry over). First test inputs failed
   with `ERROR` on spaces. The DSL does not auto-add `\s` — honest mirror of
   the schema, but a Phase-3 "sane defaults" item (concept §4.4.6).
2. **`opt` at the top of a rule is illegal.** `params: opt(seq(...))` (a
   nullable non-start rule) is rejected by the CLI (`EmptyString`). The
   nullable part must live in the caller: `seq("(", opt(params), ")")` with
   `params` non-nullable. The analyzer's nullable check covers `repeat`; this
   is a related structural rule to document.
3. **Identifier-vs-call conflict** (`f • (`) required `prec(1, ...)` on `call`
   — the CLI's own suggested fix. Not a problem, but the first authoring
   friction a real user hits.
4. **The cache key initially embedded raw toolchain strings** (`|`, spaces) —
   path-hostile; now `sha256(grammar.json)[:64] + sha256(toolchain)[:12]`.
5. **A 30-line `scanner.c` was needed** to exercise externals (see §1.4).
6. `ctypes.CDLL` with a bare relative filename doesn't search CWD — the
   loader needs an absolute path (fixed in `language.load_language`).

### 2.2 Static analysis: every planted footgun caught pre-generate

Verified on throwaway grammars, each producing the expected diagnostic with
the DSL source site attached (`tests/test_checks.py` + experiment B stage 4):

- **unused rule** (the silent-pruning trap) — plus demonstrated that the CLI
  *does* silently generate a parser that lacks the rule (pipeline test).
- **nullable inside REPEAT/REPEAT1** — infinite-loop hazard.
- **SYMBOL inside TOKEN and IMMEDIATE_TOKEN** — now both flagged (see §1.3).
- **extras first-set × token prefix overlap** — fires only for inline extras;
  the named-rule + SYMBOL fix is exempt (matches the empirical Phase-0 rule).
- **PATTERN flags** — only `i`.
- **undefined refs, duplicate names** (builder raises at registration).
- **named/int precedence mixing** — a warning (and see §3.1: it's *not*
  always harmless).

---

## 3. Conflict remapping at the reimplementation level: **re-verified GO**

A deliberate naive-expression grammar produced the precedence-gap conflict;
`tree-sitter generate --json` (exit 1, stderr) was parsed and remapped to a
`GrammarConflictError` naming the DSL source line:

```
Ambiguous shape: expr '+' expr • '+'
Conflicting rules (from your Python source):
  - g.rule('expr', ...) defined at .../experiment_b.py:301
Competing parses:
  1. expr: expr  '+'  expr
  2. expr: expr  '+'  expr
Suggested fixes from the generator:
  1. add left/right associativity to expr
  2. whitelist as intentional ambiguity: conflicts=[expr]
```

Raw report saved verbatim (`evidence/b5_conflict_gap_stderr.json`). Every
involved rule is cited at its recorded `file:lineno`; the machine report's
`possible_resolutions` render as actionable fixes. First-conflict-only +
sub-second generate makes the fix-one-rerun loop real.

### 3.1 Precedence internals worth knowing (found in the CLI source)

- Shift-vs-reduce compares **the shifted item's prev-step precedence** vs the
  reduction's production precedence.
- **Named vs integer precedence never compare** (`compare_precedence` falls
  through to the named branch, which only matches names). Phase 2 hit a REAL
  conflict from this: `- a or b` (unary int-4 vs named `or`) was unresolvable
  even with the ladder — the fix was to *layer* the grammar (unary's operand
  is the arithmetic layer, not the full expression). The analyzer's mixing
  warning is therefore load-bearing, not cosmetic.
- Named ladders are **descending (first = highest)**; equal named precedence
  without associativity leaves chained operators (`a or b or c`) as a
  conflict — named precedence needs `prec_left`/`prec_right`.

---

## 4. What the full Product B needs (gaps vs concept §4)

**Missing builder operators (small, mechanical):** `alias` exists but should
gain a guard/warning against the alias-on-seq footgun (§1.3.3); `seq1`/
`choice` sugar is done; there is no `token_immediate` sugar beyond
`immediate_token` (present); no `dynamic` sugar beyond `prec_dynamic`
(present); **no `supertype`/`hidden`/`inline` sugar on raw nodes beyond the
`rule(..., hidden=, inline=, supertype=)` flags** — adequate for Phase 2.

**The hard static checks (still hard / not built):**
- first-set *conflict prediction* (predicting real LR conflicts pre-generate
  requires the LR construction itself — out of scope; the extras-prefix
  overlap check is the tractable slice and is done);
- regex-subset validation (Phase-0 §11.6) — the comment-vs-token footgun is
  the only regex-ish hazard hit so far; full validation stays Phase 3+;
- left-recursion *reporting* (allowed, flagged) — not built; low value until
  the precedence layer lands.

**Conflict-UX surface (Phase 3):** per-production source sites (record each
`seq(...)` alternative line, not just the rule), a fix-one-rerun loop wrapper,
and the `--report-states-for-rule` debug surface (`possible_resolutions`
gives the fix text for free). The grammar-level `reserved`/`word`/`externals`
surface in the DSL is raw but complete.

---

## 5. §11 risk re-assessment (authoring side)

| # | Risk | After Phase 2 |
|---|---|---|
| 1 | **Conflict diagnostics quality** | **RE-verified GO** at the reimplementation level (§3): machine report → `variable_name` → DSL site works verbatim; remaining work is polish (per-production sites, loop UX), not feasibility. |
| 3 | **Toolchain** | Solid on this platform (devenv `pkgs.tree-sitter` + `pkgs.gcc`); the externals story adds a C compiler requirement *for grammars with scanners only*. Cross-platform packaging untouched (Phase 5). |
| 4 | **Upstream churn** | Real and bounded: 0.25.3 schema pinned and mirrored exactly; the CLI-source reading let us correct two Phase-0 claims (§1.3). Mitigation stands: pin CLI/ABI, treat grammar.json as versioned. |
| 6 | **Regex subset friction** | Confirmed as a genuine but *narrow* surface (comment-extras lexing, `[^\n]` vs `.*` choices); the extras-prefix check + named-rule guidance covers the known class. Full subset validation remains future work. |

## 6. Where bet #1 stands

**Not yet won — but the machinery it rides on is proven.** Bet #1 is that GLR
authoring pain becomes *typed, declarative, pointed at your Python source*.
Phase 2 proves the "pointed at your source" half mechanically (conflict →
`file:lineno` with the ambiguous shape + fixes), and the full-schema IR +
end-to-end pipeline. What Phase 2 explicitly does **not** prove is the *feel*:
no precedence ladders, no `ExpressionGrammar`, no conflict-UX polish. Do not
read this GO as a bet-#1 win — Phase 3 is the experiment that decides it.

---

## 7. Recommendation

**GO**, with one condition. The core is mechanically sound, faithful, and
tested (38 pytest + two evidence-backed experiments). The condition: Phase 3
must include a short hardening pass for the §4 gap list (the alias footgun
guard, the nullable-rule guidance, and the whitespace-extras default are all
small), but none of it is big enough to block. The single most important next
step is **Phase 3 — the GLR-ergonomics layer** (precedence ladders +
`ExpressionGrammar` + conflict-UX polish), because that is the experiment
that decides bet #1, and Phase 2 has now built every load-bearing part it
needs (IR, analyzer, pipeline, remapping) at full schema fidelity.

---

## Appendix — durable facts for the next phase (all CLI-verified)

1. Start rule = first entry of `rules`; no `start` field. Unused rules are
   silently pruned along with their conflicts/inline/supertypes/precedences
   entries; the word rule and extras/externals references protect a rule.
2. Non-start rules must not be nullable; inline rules must not be tokens;
   `alias` should wrap a single hidden symbol; `opt(x)` = `CHOICE(x, BLANK)`.
3. Named precedence: ladder is descending (first = highest); needs
   associativity for chaining; never compares against integers — layer the
   grammar (unary operand = arithmetic layer) instead of mixing in one rule.
4. SYMBOL inside TOKEN **or** IMMEDIATE_TOKEN is rejected (Phase-0 exemption
   claim corrected).
5. Rules are named node types even when their body is one string; anonymous
   tokens are inline literals only.
6. `reserved`: first set is global; RESERVED nodes override per position;
   empty array = contextual keywords allowed.
7. Extras with a token-prefix overlap must be a named rule + SYMBOL reference
   (bare inline extras lose to the token).
8. Externals need a compiled `scanner.c` (parser.c only declares the symbols;
   dlopen fails without it) and the scanner must skip whitespace itself.
9. Conflicts: exit 1, first only, JSON on stderr; `possible_resolutions`
   gives the fix text; generate is sub-second → fix-one-rerun loop is viable.
10. ABI 15 requires `tree-sitter.json` `{"metadata":{"version":"0.1.0"}}`;
    loading uses a PyCapsule named `tree_sitter.Language`.
