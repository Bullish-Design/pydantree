# Phase 5 — polish & reach (the corpus harness + the artifact seam in production): Findings & Verdict

**Date:** 2026-08-02
**Status:** COMPLETE
**Verdict: GO on the reach — with the honest line intact.** Both reach items
landed as first-class surfaces and survived their go/no-go tests. The corpus
harness is NOT ceremony on top of conflict-free generate: it caught every
planted regression that generates clean, it caught a **real latent bug in the
Phase-3 fixture** (qfilter's `if/else` with block bodies never parsed — a
parse ERROR that conflict-freedom, the smoke seed, and Phase-3's own corpus
were all green on), and the associativity flip is *only* catchable by the full
corpus (the 5-case smoke seed is blind to chains). The artifact seam holds
across a real process boundary: a B-free subprocess consumed the packaged
bundle with the Phase-4 ground truth passing and the checks active, the A
surface is byte-identical with and without B, and the community path works
over the wheel. Two honest caveats: pydantree_sitter was NOT actually B-free at import
time (a real bug the B-free subprocess exposed and Phase 5 fixed), and the
`Unescaped()` marker is new annotation vocabulary on a frozen surface (a
go-with-changes finding, used as specced).

Everything here ran against the real toolchain (tree-sitter 0.25.3, gcc
14.2.1, py-tree-sitter 0.26.0, pydantic 2.13.4, ABI 15). Raw outputs saved
verbatim under `evidence/` (r1_*, r2_*, r3_*). Re-run:

```bash
devenv shell -- python .scratch/007-query-distribution/experiment_phase5.py
devenv shell -- python -m pytest tests/    # 139 green
```

---

## 0. What was built (the surface, in one screen)

```python
# B: the corpus harness (CONCEPT §4.8) — the systematic semantic guard
corpus = Corpus([corpus_case("1 + 2 + 3;", "((number) + ((number) + (number)))",
                             name="+ left-assoc", selector="expr")],
                style="compact", snapshots_dir="corpus_snap/")
result = corpus.run(grammar=qfilter.build())     # build, parse, diff, snapshot
print(result.report())                            # per-case failures + diffs

# B: ship a grammar as a bundle (grammar.so + node-schema.json + metadata + loader)
bundle = BuildResult.package("dist/cfg-bundle")   # 4 files, loader = 7 lines

# A: consume it B-free (no pydantree_sitter_grammar in the process — verified)
lang = Language.load_bundle("dist/cfg-bundle")    # one call, checks bound
ServerSection.validate_with(lang)                 # Jobs 1/3/4 before parsing
rows = ServerSection.extract(text, language=lang)

# A polish: reparse + typed Diagnostics, richer errors, descendant '...',
# field-mode lists, Unescaped()
t2 = lang.reparse(t1, new_source)
clean, diags = Query(node("module")).validate(tree)   # Diagnostic{kind,span,expected?,snippet}
rows = Calls.extract(text)        # M("module", ..., "call") — descendant
params: list[str] = capture("param")   # field-mode list (anchor-merge)
title: Annotated[str, Unescaped()]     # JSON-first escape decode
```

---

## 1. Run 1 — the corpus harness bite: DOES it change the feel of B authoring?

**Yes — decisively, and it already paid for itself.** The qfilter corpus (19
expression shapes in the compact smoke style + 13 statement shapes in the sexp
style = 32 `corpus_case()` lines for a 15-rule grammar) passes on the
known-good grammar. All four planted regressions were caught at author time:

| planted regression | generates clean | caught by the smoke seed (5 cases) | caught by the full corpus |
|---|---|---|---|
| **R1 ladder reorder** (unary above pow) | yes | **yes** (`-a ^ b` is in the seed) | yes |
| **R2 associativity flip** (`+` right-assoc) | yes | **NO — blind** (no chain case in the seed) | **yes** (`1 + 2 + 3`) |
| **R3 postfix below unary** | yes | yes (`-f(x)`) | yes — and *adds* `-a.b`, `-f(x) + 1` |
| **R4 statement-level** (block dropped from the statement supertype) | yes (it shipped in Phase 3!) | NO (expression-only) | **yes — 3 cases** |

**The honest metric:** the smoke seed catches 2 of the 3 ladder-level
regressions (both are expression shapes in the seed); the associativity flip
needs the full corpus's *chain* case — the seed cannot reach it. That is
exactly the Phase-4 §7 promise: the harness generalizes the seed, it does not
parallel it (`semantic_smoke` now delegates to `pydantree_sitter_grammar.corpus`; no parallel
machinery).

**The corpus caught a REAL bug during authoring.** qfilter's `if_stmt`
`then:`/`else:` used the `statement` supertype, which did NOT include `block`
— so `if (a) { ... }` was a parse ERROR even though the grammar generated
clean, the smoke seed passed, and Phase-3's own 7-statement corpus passed (it
never tested if-with-blocks). The statement-shape corpus caught it; the
fixture was fixed (block added to the supertype); Phase-3's experiment still
passes unchanged. **This is the strongest possible evidence that the harness
is not ceremony:** the class of bug it caught (generates clean + smoke green +
prior corpus green) is precisely the semantic-intent leak §4 of Phase 3 named.

**Author effort:** 32 `corpus_case()` lines for a 15-rule grammar (expression
shapes + statement shapes + edge cases). The expected sexps are
hand-authored from the grammar's *intent* (verified by hand against the
ladder and statement rules); the renderer's normalization story is documented
(sexp style keeps anonymous tokens as `'text'` — they ARE semantic, the
operator distinguishes `1 + 2` from `1 - 2`; `anonymous="drop"` is available
for shape-only checks; the compact style is the smoke format).

**Diff reviewability:** a failure renders as a unified diff per case
(`expected` vs `got` lines) plus the case's definition site (`file:lineno` —
`corpus_case()` records it); snapshots of grammar.json + node-schema.json land
beside the corpus so grammar changes show up as reviewable diffs.

**Where it leaks (honest):** the corpus cannot *decide* intent — it pins the
author-chosen semantics (a wrong choice that's internally consistent still
passes if the author also wrote the wrong expectation). The compact style
renders only the first `expr` node (statement-level regressions need the sexp
style or a selector). The expected strings are brittle to *intentional*
grammar changes (that is the point — they must be updated deliberately, and
the diff shows exactly what changed). No golden-file framework, no DSL-driven
corpus format — Python cases + a diff are the deliverable, per the kickoff.

**The go/no-go:** the harness changes the feel of B authoring — it catches
what generate cannot, and it caught a real bug on its first outing. **Not
ceremony.**

---

## 2. Run 2 — the artifact seam in production: does the bundle hold B-free?

**Yes — and the process boundary found a real leak.** The cfg grammar
packages into a 4-file bundle (`grammar.so` 20 KB, `node-schema.json` 4.6 KB,
`tree-sitter.json` metadata 131 B, `loader.py` **7 lines** — a shim over
`pydantree_sitter.loader.load_bundle`, the shared loading contract, CONCEPT §8). A
separate subprocess with pydantree_sitter_grammar genuinely removed from `sys.path` (a
`sitecustomize` strips the editable `src/` install; the consumer asserts
`import pydantree_sitter_grammar` fails) consumed the bundle via `Language.load_bundle` in
one call, ran Jobs 1/3/4 at `validate_with` with no text parsed, and
extracted the Phase-4 record + field ground truth exactly:

- record rows (2 sections) and field rows (2 directives, `include` excluded
  at query level) match `SECTION_GROUND_TRUTH` / `LISTEN_GROUND_TRUTH`;
- the A surface is **byte-identical** with and without B in the process;
- **the leak the boundary exposed:** `pydantree_sitter.schema` imported
  `pydantree_sitter_grammar.ir` at MODULE level (the comment claimed "lazy import" —
  it wasn't), so `import pydantree_sitter` was NOT B-free. Fixed: the exact-path
  derivation moved to `pydantree_sitter._ir_derive`, imported only when
  `derive_from_ir` is actually called (B-side only). `import pydantree_sitter` /
  `import pydantree_sitter` now never touch pydantree_sitter_grammar — verified by the B-free
  subprocess.

**The community path:** the community-schema tool (grammar dir with
grammar.json → CLI generate → node-types.json → `derive_from_node_types` →
node-schema.json, one command, `out=` to persist) derives 20 kinds for the
json grammar, **agreeing byte-for-byte with `derive_from_ir`** (the Phase-4
agreement check reused), and a B-free subprocess binds that schema to the
`tree_sitter_json` wheel and extracts the Phase-1 Person ground truth —
checks active, no B anywhere.

**The go/no-go:** a consumer who never runs B gets the full bridge — the
bundle needs nothing beyond the artifact itself (loader placement: in
`pydantree_sitter`, the shared contract, so B and A and the bundle's `loader.py` all use
ONE loading implementation; schema: shipped in the bundle / derived by the
community tool; no toolchain at consume time — the only imports are
`pydantree_sitter` + `tree_sitter`). **The seam does not leak.**

---

## 3. Run 3 — the honest control: raw py-tree-sitter, no schema

The same two tasks through the raw path: ctypes/PyCapsule load of the bundle's
`.so`, hand-written `.scm`, manual dispatch + coercion. Three raw-path traps
the schema + derivation absorb for free, all hit live in the control:

1. **supertypes match nothing** in a query — `(value)` captures nothing; the
   raw author must know to write `(_)` or enumerate the subtypes by hand (the
   schema derivation does exactly this);
2. **capture-suffix binding** — `@dir` after the wrong `)` binds to the
   source_file, silently wrong lines (the DSL emitter encodes this invariant);
3. **anchored patterns re-match per inner occurrence** — the record query
   matched 4× per section; the raw author must dedup by node id (record-level
   anchoring in A kills this at query level).

With all three hand-applied, the control matches ground truth — at the cost of
~20 lines of hand-rolled query + dispatch + coercion vs ~10 model lines, and
with every mistake class surfacing *later* (silent wrong rows / silent empty
results) than A's `validate_with` (schema entry cited, no text parsed). The
comparison table is saved in `evidence/r3_control.txt`.

**The go/no-go:** Run 2 is meaningfully better than the control on the
control's own terms — the same task, the same ground truth, with the
grammar/binding knowledge that the raw author must know **absorbed** into the
bundle + schema, and the failure surface strictly earlier.

---

## 4. Which Phase-5 items landed, and which didn't

| item | status | note |
|---|---|---|
| corpus harness (`pydantree_sitter_grammar/corpus.py`) | **LANDED** | `Corpus`/`corpus_case` + runner + renderers + snapshots; `semantic_smoke` delegates; qfilter corpus; 9 tests |
| artifact packaging + loader | **LANDED** | `BuildResult.package()`; `pydantree_sitter.loader` (the shared contract); `Language.load_bundle()` one-liner; **the B-free-import fix** (`pydantree_sitter._ir_derive` split) |
| community-schema tool | **LANDED** | `pydantree_sitter_grammar.schema_tool`; agrees with `derive_from_ir`; B-free community consumer over the wheel |
| reparse + typed Diagnostics | **LANDED** | `Language.reparse(old, new)`; `Diagnostic{kind, span, expected?, snippet}` replacing `validate()`'s dicts |
| richer `ExtractionError` | **LANDED** | `MatchFailure` per failed match (pattern/anchor span/snippet/pydantic errors) — every failure reported, not just the first |
| descendant `...` matching | **LANDED (with the assessment documented)** | `M("module", ..., "call")` via an exact ancestor walk at materialization + Job-1 possible-descendant checks. **The `#has-ancestor?` assessment:** it works only when the captured node textually precedes the predicate (a child capture) — the anchor's own ancestor constraint cannot be expressed in one pattern, and it cannot bound depth; the ancestor walk is exact and handles any number of gaps. The query-level predicate remains available for pruning. 80% rule applied; the leaf-anchor + middle-gap cases are covered by the walk. |
| field-mode lists | **LANDED** | `list[X] = capture("f")` merges the repeated field's matches across the shared anchor (record-mode anchor-merge reused, scalars deduped by node id); Job-4 checks lists element-level (field-mode) vs array-level (record-mode). Honest limit: the repeated field must sit ON the anchor node (like qfilter's `params`); a wrapper field (`arguments: (argument_list)`) captures the wrapper once. |
| `Unescaped()` | **LANDED (go-with-changes)** | JSON-first escape decode; the shape derivation captures the string WRAPPER wholesale — and that choice exposed a real latent bug (string_content splits at escape_sequence, so leaf captures split escaped strings). Schema-checked: the capture must be able to be a string wrapper. New annotation vocabulary on the frozen Phase-4 surface — used as specced, not expanded. |
| external-scanner escape hatch | **LANDED** | `ExternalScannerRequiredError` (clear, names the externals, before gcc link failure); scanner.c content-addressed in the cache key; `g.external(*tokens)`; the canonical INDENT/DEDENT/NEWLINE scanner ships (`pydantree_sitter_grammar.scanners.indent_scanner_path()` — the pymini seed) with the pymini grammar. The scanner library beyond the one seed stays Phase-6. |
| wasm distribution | **ASSESSED, NOT BUILT** (as specced) | see §5 |
| corpus gold-plating / new A surface / new grammar features | **NOT BUILT** (out of scope) | — |

---

## 5. Re-assessing the §11 risks from the Phase-5 side

- **§11.4 upstream churn (reparse / has-ancestor version-dependence) — CONFIRMED REAL, BOUNDED.** The reparse wrapper is one line over `Parser.parse(new, old)` (no edit tuples in 0.26 — the binding API differs across versions). `#has-ancestor?` IS supported by `Query()` in 0.26 but has a capture-ordering constraint (the referenced capture must precede the predicate textually) that makes it unsuitable for the anchor's own ancestor check — the descendant implementation therefore does NOT depend on it (ancestor walk + schema closure), which is *more* version-robust. The zero-width-NEWLINE indentation-scanner cadence is the canonical one (mirrors the ecosystem's own scanners).
- **§11.2/11.3 scanner + toolchain packaging for B — CONFIRMED, one seed shipped.** External scanners are genuinely needed for indentation languages (the pymini case) and the mechanism is now airtight; the library is one seed (Phase-6 for the rest). The bundle needs no toolchain at consume time — verified by the B-free subprocess.
- **§11.5 wasm — assessed, not built (as specced).** What it would take: an emscripten toolchain probe (clang/emcc at build time), a wasm runtime in A, and the same bundle layout with a `.wasm` instead of the `.so`. **The `.so` bundle is enough for the reach claim**: the artifact seam is about B-free consumption across the process boundary, and native `.so` + metadata + loader proved it. wasm would buy portability (no per-platform native build) — a real Phase-6 item for distribution, but not needed to prove reach.
- **Newly surfaced:** (a) pydantree_sitter was not actually B-free at import time — the Phase-4 in-process proof masked it (B was always importable); the process-boundary test is the honest one, now in the suite. (b) The record string shape splits escaped strings across string_content pieces (a v1-map behavior the derivation reproduced) — exposed by `Unescaped()`, fixed by capturing the wrapper. (c) qfilter's block bug (§1) — a fixture-level latent defect the corpus caught. (d) The `#has-ancestor?` capture-ordering constraint (§4) — a binding-level fact that shapes the descendant design.

---

## 6. Recommendation

**GO on Phase 5's reach, go-with-changes.** The two reach items are
first-class and proven: corpus authoring is regression-safe (it caught a real
bug on day one, and the associativity class is *only* catchable by the full
corpus), and the artifact seam holds across a genuine process boundary with
the checks intact and the A surface byte-identical — while exposing and
fixing a real B-free-import leak. The changes carried: `Unescaped()` is new
annotation vocabulary (accepted as specced, not a license to expand); the
descendant mechanism uses an ancestor walk rather than `#has-ancestor?`
(documented assessment, 80% rule); the scanner library is one seed (Phase-6).

**The single most important next step: Phase 6 — distribution + surface
completion**, in this order:
1. **wasm + the scanner library** — the `.so` bundle proved the seam; wasm
   (an emscripten probe, the same bundle layout with a `.wasm`) and the
   per-language scanner copies are the remaining distribution reach;
2. **Job-2 typed node access** (`.pyi` stubs from the schema) — Phase 4 said
   "worth it after distribution"; the bundle now makes it a real consumer
   surface;
3. **the honest residuals from §4/§5** — the field-mode-list wrapper-field
   case, the schema registry's global-name-keyed leak (test isolation was
   needed), and the name-based kind inference residue (documented, small).

A Phase-5A hardening pass is not needed: the go/no-go questions were tested
(harness catches generate-clean regressions; bundle consumed B-free), the
leaks are documented author responsibilities or bounded residuals, and the
frozen Phase-4 surface stayed unchanged.

---

## Appendix — durable facts Phase 5 established

1. **Tree-sitter query nesting is CHILD-level** (probed): `(a (b))` matches b
   only as a direct child of a; the compiler even rejects impossible patterns
   ("Impossible pattern"). This is what makes `...` genuinely needed and why
   the Job-1 chain check (child descents) matches the query engine's own
   semantics.
2. **`#has-ancestor?` works in 0.26 but only for captures that textually
   precede the predicate** (a child capture): `(function_definition (block)
   @b (#has-ancestor? @b module))` matches; `(node ...) @x (#has-ancestor? @x
   m)` and `(node (#has-ancestor? @x m) @x)` are rejected. The anchor's own
   ancestor constraint is therefore not expressible in one pattern — the
   ancestor-walk implementation sidesteps the version-dependence.
3. **A bare top-level predicate is still the spike-a trap**: `(x) @a
   (#has-ancestor? @a m)` (predicate as its own form) compiles to a junk
   pattern matching every node.
4. **Repeated CST fields yield one match per occurrence** (unquantified):
   `(params param: (identifier) @p)` matches once per param — the field-mode
   list anchor-merge is built on this.
5. **The indentation scanner's canonical cadence**: mark_end before the loop
   + the newline SKIPPED (not advanced) — the NEWLINE token is zero-width at
   the newline, so the next call re-crosses it and re-measures for
   DEDENT/INDENT; comment-only lines count as newlines; blank lines are
   skipped in the ordinary path; EOF flushes pending DEDENTs. Blocks are
   `INDENT statements DEDENT` (NEWLINE ends statements) — a NEWLINE-then-INDENT
   grammar sequence cannot work because emitting NEWLINE consumes the
   indentation the INDENT needs.
6. **The B-free boundary is the honest test of the A/B seam**: in-process
   proofs run with B importable; only a subprocess with B removed from
   sys.path (sitecustomize stripping the editable src/ install + the consumer
   asserting `import pydantree_sitter_grammar` fails) reveals import-time coupling.
7. **Supertype kinds match nothing in queries** — `(value)` captures nothing;
   the raw author writes `(_)` or enumerates subtypes (the schema derivation
   does this for free). Confirmed live in the Run-3 control.
8. **`Unescaped()` exposed a real shape bug**: string_content splits at
   escape_sequence, so `value:(string (string_content) @x)` captures each
   piece separately (a v1-map behavior the derivation reproduced); the
   Unescaped shape captures the string wrapper wholesale.
9. **The bundle is one artifact**: grammar.so (export symbol recorded in the
   metadata — the bundle renames it `grammar.so`) + node-schema.json +
   tree-sitter.json + a 7-line loader delegating to pydantree_sitter's shared loading
   contract; `Language.load_bundle(dir)` is the one-line consumer.
