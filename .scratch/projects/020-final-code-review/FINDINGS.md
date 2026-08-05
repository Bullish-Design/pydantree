# Review 020 — final deep code review: findings

**Status:** complete
**Date:** 2026-08-05
**Scope:** `pydantree_sitter` (Product A, extraction) + `pydantree_sitter_grammar`
(Product B, authoring), tests, examples, docs, oracles. Independent deep
review following 019 (which closed V1–V7).

---

## Bottom line

**Ready for personal use? Almost — not "fully."** The happy paths are correct,
disciplined, and genuinely deliver the bind-time-checks differentiator. But
there are **four real defects in the advanced/escape-hatch surfaces** (multi-
pattern `__raw_query__` crash, empty-list anchor drop, non-applying `reparse`,
under-checked alternation anchors), **two diagnostics regressions in Product B**
(analyzer errors lose source attribution on the default path; conflict JSON
extraction breaks on brace tokens), plus a **SIGSEGV-on-teardown wart** and the
fact that **nothing runs without the full toolchain**. For *careful* personal
use knowing the caveats below: yes. As "ship it and forget the sharp edges":
not yet.

**Live fixture testing with saved outputs? Partially.** Strong on saved
**final** data (regenerable, drift-proof, cross-checked against ground truth),
weak on saved **steps** (the rich per-step transcripts the examples print are
snapshotted nowhere), and entirely gated behind `devenv`. Details in §3.

---

## 1. Verified facts (live)

| Fact | Value |
|---|---|
| Full suite, `devenv shell` | **272 passed** in ~68s — fully green |
| Plain shell (no toolchain) | **127 of ~272 skip** (toolchain-gated) — *every* oracle/live-fixture test is in the skipped set; `pydantree_sitter` cannot even import without `tree_sitter` |
| **New finding — exit status** | Running the full `test_oracles.py` module or the full suite **segfaults on native teardown and exits 139 (SIGSEGV)** *after* reporting all tests passed. A single bundle load exits cleanly; the crash needs several native grammars loaded in one process (a specific combination, not any two bundles). Earlier "exit 0" readings were **masked by pipes to `tail`** — a plain run exits 139. Data is correct; any CI or `pytest && …` gate reads 139 as failure. Likely tree-sitter `Language`/`Parser` finalization order at interpreter shutdown — root-causing is a follow-up. |
| Repository maturity | 152 commits; 19 project phases including two adversarial reviews and a final verification (019) with all V1–V7 findings closed |
| Hygiene | 4 TODOs, 3 `type: ignore`, no bare `except Exception`, no `shell=True`, no unchecked subprocess returncodes |
| Size | ~7.7k LOC in `src/`, 30 `test_*.py` files, 3 examples |

---

## 2. Prioritized findings

### 2.1 Must-fix / know-before-you-rely-on-it

#### A1 — MAJOR — multi-pattern `__raw_query__` crashes with `IndexError`
- **Where:** `src/pydantree_sitter/emit.py:225-226` and `emit.py:269`
- **What:** For a raw query, `spec_caps` is built as a **length-1 list**, but
  `Cursor.matches` indexes `_quant_maps[pi]` with tree-sitter's *real* pattern
  index. Any `RawQuery` with 2+ top-level patterns (i.e. exactly the `a | b`
  sibling/negation cases the hatch exists for) raises `IndexError`.
- **Confirmed:** verified directly in the code. Highest-impact defect found.

#### A2 — MAJOR — non-optional field-mode `list[T]` silently drops empty-list anchors
- **Where:** `src/pydantree_sitter/compiler.py:304`
- **What:** Emits `quant=""` instead of `"*"`, so an anchor whose repeated
  child occurs **zero times** fails to match and the **whole row vanishes** —
  a function with no arguments disappears entirely, silently.
- **Workaround:** `list[T] | None` — undocumented.
- **Confirmed:** verified directly in the code.

#### A3 — MAJOR — `reparse` never applies edits — silently wrong trees
- **Where:** `src/pydantree_sitter/binding.py:212-220`
- **What:** The docstring claims edits are applied internally, but tree-sitter
  does not auto-diff. `reparse` is only correct for EOF appends (the one case
  the single test covers). Any mid-buffer edit reuses subtrees at shifted
  offsets, producing **silently wrong trees**.
- **Fix:** either implement `old_tree.edit(...)` before reparsing, or delete
  the method.

#### A4 — MAJOR — alternation anchors under-check at bind time
- **Where:** `src/pydantree_sitter/compiler.py:280,291,320`
- **What:** For `M("module", ("function_definition", "class_definition"))`,
  bind-time checks/inference use only `anchor_kinds[0]`. An invalid
  second-alternative pattern escapes the actionable `SchemaCheckError` and
  fails later as a raw `QueryBuildError` — the "checks catch it at bind"
  promise is incomplete on this surface.

#### B1 — MAJOR — Product B analyzer *errors* lose source-site attribution on the default build path
- **Where:** `src/pydantree_sitter_grammar/pipeline.py:313-316` and
  `pipeline.py:484-486`
- **What:** Checks run against the site-less IR; only *warnings* are re-run
  over the sited builder. A typo'd `ref("nam")` therefore raises with **no
  `at file:line`** — directly undercutting Product B's headline selling point
  (DSL-site error attribution).
- **Workaround:** call `tg.errors(g)` yourself first.
- **Fix:** re-run analyzer **errors** over the sited builder too.

#### B2 — MAJOR — conflict-report JSON extraction breaks on brace tokens
- **Where:** `src/pydantree_sitter_grammar/conflicts.py:64-83`
- **What:** Brace-counting is not string-aware. Any block-structured grammar
  (C/JS/JSON/Rust — anything with `{…}`) that hits a GLR conflict falls back
  to the raw generator dump, losing the DSL-site remapping.
- **Untested:** the golden conflict fixtures use only `if/then/else`, so this
  path has no coverage.

### 2.2 Should-fix

#### B3 — C++ scanners unsupported though the community path advertises real community grammars
- **Where:** `src/pydantree_sitter_grammar/pipeline.py:139-151,373`
- **What:** Only `scanner.c`/`gcc` are handled — never `scanner.cc`/`g++`.
  `build_community_bundle` on html/cpp/ruby raises a misleading
  "no scanner.c supplied."

#### B4 — `check_nullable_non_start_rule` may reject legitimate grammars by default
- **Where:** `src/pydantree_sitter_grammar/checks.py:492-509`
- **What:** Errors on *every* nullable non-start rule and treats `repeat(...)`
  as always-nullable, so idioms like
  `g.rule("items", repeat(ref("item")))` can be rejected by default. Verify
  against the real CLI; `check=False` is the escape hatch.

#### Example bug — mismatch diagnostic path raises `NameError`
- **Where:** `examples/devenv-extract/extract.py:253`
- **What:** `f"want {len(want)}"` references an undefined `want` (should be
  `len(truth[key])`). The exact path that *reports* a mismatch crashes instead.
- **Confirmed:** verified directly.

#### Doc snippets don't run
- `README.md:27` uses `pydantree_sitter.Language.from_module(...)` but imports
  only names *from* the module, so `pydantree_sitter` is unbound.
- `docs/user-guide.md:52` uses `Language.from_module` without importing
  `Language`.
- **Confirmed:** both verified. These are the first things a reader hits.

### 2.3 Minor (worth a sweep)

**Product A**
- `int` over a JSON `number` passes bind but fails at runtime on float text
  (document the limitation).
- `source_meta()` into `int | None` breaks (`src/pydantree_sitter/materialize.py:165`).
- A missing-`__match__` subclass yields a raw `AttributeError`, not the
  friendly `ShapeError`.
- Record-mode optional-field-with-predicate drops the whole record.
- Field-mode scalar `str` over a string wrapper keeps quotes/escapes —
  inconsistent with record mode.
- Caches are unsynchronized and `_PROPOSED_CACHE` pins schemas forever
  (fine single-threaded).

**Product B**
- Temp/`.work` dirs leak on generate/compile failure (`pipeline.py`,
  `schema_tool.py`) — need `try/finally`.
- `PYDANTREE_SITTER_ABI` is documented as an override but is only a fallback.
- `remap_from_proc` raises a bare `RuntimeError`, swallowing the underlying
  `GenerateError`.
- `replace_rule` leaves stale flag entries.
- `node_types_json` can point at a nonexistent path after a warm-cache schema
  backfill.

---

## 3. Live fixtures & saved outputs — the direct answer

**Partially met.** What is genuinely strong:

- **Three real end-to-end examples over real grammars and real corpora:**
  - `examples/bash-extract/` — real tree-sitter-bash 0.25.1 over real shell
    scripts.
  - `examples/devenv-extract/` — the author's own `devenv.nix` files.
  - `examples/grammar-authoring/` — a from-scratch DSL-authored grammar.
  Each `extract.py` prints a per-step narrative, self-checks its rows against a
  hand-written `ground_truth.json`, and exits 0/1.
- **A sound saved-output mechanism:** `tests/oracles/*.json` are human-
  readable, regenerable (`--generate`), drift-proof (generator and checker
  share collectors), and cross-checked against independent ground truth.
  Native `.so` artifacts are deliberately *not* committed — the right call.
- **The example CLIs are additionally re-run as subprocesses** to prove they
  stay runnable.

Where it falls short of what was asked:

1. **Saved outputs capture final data only, never the intermediate steps.**
   The rich step-by-step transcripts the examples *print* (schema: N kinds ·
   checks active, per-file/per-row traces, the author+build sections) are
   **snapshotted nowhere** — the subprocess tests only assert a substring such
   as `"34 rows extracted"`. "See what's being done at each step" is met by
   *ephemeral stdout*, not a committed artifact.
2. **Everything requires the full `devenv`/CLI+gcc toolchain.** Off-devenv,
   none of it runs and the library will not import. There is no
   schema-less/community-wheel example that runs toolchain-free.
3. **Several headline A features have no live example with saved output:**
   `__raw_query__`/`RawQuery`, `Matches`/`Eq`/`AnyOf` predicates, `NodeKind`
   alternation, `Unescaped`, `derived()`, nested-model fields. They live only
   in unit tests (some gated).
4. **Product A's extraction core is under-unit-tested:**
   `materialize.py`, `emit.py`, `binding.py`, `compiler.py` are exercised
   mainly through toolchain-gated integration tests, so they are effectively
   untested in any environment lacking the CLI+gcc.

**To fully satisfy the goal:** add one **toolchain-free** live example
(community wheel, no build) with a **committed per-step transcript oracle**,
plus direct unit tests for `materialize`/`emit`/`binding`.

---

## 4. Cheap high-value wins

1. Fix the `want` NameError (`examples/devenv-extract/extract.py:253`) and the
   two doc snippets — trivial, and they are the first things a reader hits.
2. Fix or guard A1 (raw-query `IndexError`) and document/fix A2 (empty-list
   drop) — both are silent surprises.
3. Re-run analyzer **errors** over the sited builder (B1) so Product B's core
   promise holds by default.
4. Track down the exit-139 segfault — or at minimum stop masking it behind
   pipes in CI; the suite currently reads as a hard failure to any
   `pytest && …` gate.
5. Refresh the "265 green" claim in `README.md:78` to 272.

---

## 5. What this review does NOT claim

- Prior reviews 018/019 findings (V1–V7) are treated as closed; this review
  did not re-audit their full resolution, only spot-checked the state.
- The exit-139 root cause is not yet isolated to a specific native
  combination; only the *fact* (reliable 139 on full oracle module / full
  suite teardown, clean exit for a single bundle) is established.
- The severity ranking reflects personal-use risk; if the advanced surfaces
  (raw queries, alternations, `reparse`) are unused, the practical risk drops
  to the minor bucket.
