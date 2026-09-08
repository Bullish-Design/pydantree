# Cursor-walk vs emitter/query — measurement and decision

Date: 2026-09-09
Session: `20260909-2890613b`
Scope: Phase 024 `REFACTOR_GUIDE.md` Appendix E, deferred idea **10 — "walk the
tree, delete the emitter"**.
Verdict: **RETAIN the emitter/query path. Delete nothing. Deferral documented.**

This report is an independent re-derivation. It uses no result from any other
session, and it reads no artifact outside
`sessions/20260909-2890613b/`.

---

## 0. Scope note

The task named "item 6". Appendix E lists an idea 6 ("drop ast-grep") and an
idea 10 ("walk the tree, delete the emitter"). The task text describes the
query/emitter path, the cursor walk, `emit.py`, capture support, and the
raw-query API. Those are idea 10. This report answers idea 10 and says so.
Idea 6 (`pattern.py`, `agreement.py`, `rules.py`, `syntax.py`) is untouched.

## 1. Baseline

### 1.1 Code baseline — this workspace HAS the final Phase 024 code

Determined from file content, not from version control:

| Phase 024 target | Observed |
|---|---|
| public surface is exactly 12 names | `sorted(pydantree_sitter.__all__)` = the 12 names in `024/FINDINGS.md` |
| `binding.py`, `compiler.py`, `materialize.py`, `spec.py`, `markers.py`, `codegen.py`, `valuemap.py` deleted | absent from `src/` |
| runtime is `nodes/grammar/find/generate/schema/raw/loader` | present |
| `emit.py` reduced | present, 5 lines, re-exports `raw.Cursor/MatchView/Query` |
| suite green | `350 passed, 1 xfailed` |

The suite is 350 tests against the 343 recorded in `024/FINDINGS.md`. The extra
tests come from the later `main` commits (`ffa4d76`..`b9cad4f`). The workspace
therefore holds Phase 024 **plus** the post-024 cleanup.

### 1.2 Version-control baseline — recorded, NOT repaired

```text
Gitman status — OFF-CANONICAL
Reason: lane(s) 024-typed-node-universe have a divergent change-id
        (one change -> multiple commits) - run `gitman reconcile`.
Exit: 1
```

- trunk `main` = `b9cad4fae65ab44119a74b1e85af9dcf085de17b`, in sync with origin.
- current lane = `024-typed-node-universe`, head change `vpzxkznm…`, commit
  `64bf8debf7aaba9484ed401705aece113ab03577`, "phase024: complete typed node
  universe refactor", divergent, 141 files, +25568 / -11868.
- orphaned lane `fix/review-018`.

`gitman reconcile` was **not** run. The working copy belongs to another
session's lane. Full record: `evidence/gitman-status-baseline.{txt,json}`.

### 1.3 Missing skill

`.agents/skills/build-run-investigation-loop/SKILL.md` does not exist in this
workspace, and no copy exists under `~/.claude`. The investigation still
followed a build → run → investigate loop, but the named skill could not be
read.

## 2. What the code actually does

`find.find_in` has three paths, chosen in this order:

1. `__raw_query__` set → `_raw_find` (compiled raw query, name-addressed
   captures).
2. a language is available → `_query_walk`.
3. otherwise → `_walk` (recursive descent over `named_children`).

The structural fact that governs the whole question:

> **The query never extracts anything.** `_query_walk` uses the emitted query
> only to locate anchors, then calls `cls.from_node(anchor)` — the same
> resolver `_walk` calls. Resolution and Pydantic validation are identical in
> both paths.

So a cursor walk can only replace *anchor discovery*, and can only win the
fraction of total time anchor discovery costs.

Second structural fact: `_query_walk` builds `Query.raw(query_source(cls))` and
compiles it **on every call**. Nothing is cached between calls.

## 3. Method

Three anchor strategies, one shared resolver:

| id | strategy | source |
|---|---|---|
| A | compiled emitted query | shipped `find._query_walk` |
| B | recursive `named_children` walk | shipped `find._walk` |
| C | `TreeCursor` pre-order walk, integer `kind_id` compare | prototype, `probes/harness.py::anchors_cursor` |

C is a genuine cursor walk: one persistent `TreeCursor`, no per-node child list,
no recursion, and an integer kind test instead of a string compare. It is the
strongest form of the idea-10 proposal.

### 3.1 Corpus — real files, no synthetic trees

Five languages × three size tiers. Every file is a real artifact; each is
pinned by absolute path and sha256 in `probes/harness.py` and echoed in the
oracle output.

| language | small | medium | large |
|---|---|---|---|
| python | `src/pydantree_sitter/span.py` 1 609 B | `src/pydantree_sitter/nodes.py` 26 200 B | `mypy/checker.py` 453 424 B |
| bash | `examples/bash-extract/sample.sh` 1 251 B | nix `install-multi-user.sh` 33 212 B | `.devenv/shell-d5f9709ac96d0de3.sh` 102 942 B |
| nix | `devenv.nix` 6 931 B | `tests/fixtures/nix/fleet/flora.nix` 25 915 B | nixpkgs `aliases.nix` 256 322 B |
| rust | rust-lib `core/src/mem/type_info.rs` 4 070 B | rust-lib `coretests/tests/num/mod.rs` 29 081 B | rust-lib `alloc/src/sync.rs` 175 646 B |
| markdown | `docs/typed-node-universe.md` 1 289 B | `docs/development.md` 10 204 B | `024/REFACTOR_GUIDE.md` 61 616 B |

Grammars: python from the `tree_sitter_python` wheel + the maintained vendored
`examples/wheel-extract/vendor/python-node-types.json` (a deliberate 9-entry
subset); bash, nix, rust, markdown built from the vendored community sources in
`tests/fixtures/` through `schema_tool.build_community_bundle`.

### 3.2 Environment

Intel Xeon W-2125 @ 4.00 GHz, 8 cores, 125 GiB RAM, Linux 6.18.38.
Python 3.13.5, tree-sitter bindings 0.26.0, tree-sitter CLI 0.25.3,
gcc 14.2.1, pydantic 2.11.1, pydantree_sitter 0.3.0, devenv 2.2.2.
Full record: `evidence/environment.txt`.

### 3.3 Commands

```console
devenv shell -- python probes/oracle_sweep.py    # exhaustive differential
devenv shell -- python probes/oracle_api.py      # public-API oracle
devenv shell -- python probes/bench.py           # benchmark, run 1 and run 2
devenv shell -- python probes/bench_cache.py     # compiled-query cache probe
```

---

## 4. Behavioural oracle

### 4.1 Exhaustive differential sweep — 984 cases

Every generated class, every language, every tier
(`evidence/oracle-sweep.{json,log}`).

| language | kinds | cases | A == B | kinds whose emitted query will not compile |
|---|---|---|---|---|
| python | 10 | 30 | 27 | 1 |
| bash | 60 | 180 | 174 | 6 |
| nix | 42 | 126 | 125 | 9 |
| rust | 164 | 492 | 486 | 18 |
| markdown | 52 | 156 | 156 | 1 |

- **C == B in 984 of 984 cases.** Zero anchor mismatches, zero row mismatches,
  zero errors. The cursor walk is a faithful reimplementation of `_walk`.
- **A != B in 16 cases.**

### 4.2 Public-API oracle — 120 cases

`Tree.find`-level comparison of rows, order, field values, and raised error
class (`evidence/oracle-api.{json,log}`). Dimensions covered: root and nested
matches, repeated matches, ancestor context (`__under__`), field and named-node
constraints, scalar narrowing, row ordering, missing optional nodes, malformed
queries, unknown captures, and the raw-query escape hatch.

```text
cases=120  query_vs_walk_DIFFER=22  cursor_vs_walk_DIFFER=9  cursor_vs_query_DIFFER=13
```

The 9 `cursor_vs_walk` rows are an artefact of the comparison baseline, not a
prototype defect: `find_in(raw, cls, None)` raises `TypeError` for a
`__raw_query__` class because it has no language. The prototype forwards the
language and matches the shipped query path exactly on all raw-query cases
(3 / 35 / 352 rows; `QueryBuildError` for a malformed raw query;
`SchemaCheckError` for an unknown capture).

**The 13 real divergences, cursor (== walk) vs the shipped query path:**

| class | tier(s) | cursor/walk | shipped query |
|---|---|---|---|
| python `Assignment` (plain and `right` narrowed) | small/medium/large | `ExtractionError` | 3 / 133 / 1176 rows |
| rust `LetDeclaration` | large | `ExtractionError` | 127 rows |
| bash `VariableAssignment`, `BinaryExpression` | large | `ExtractionError` | `ExtractionError`, different payload |
| rust `ScopedIdentifier` | small/medium/large | 5 / 47 / 381 rows | same rows, **different order** |
| rust `BinaryExpression` | large | 53 rows | same rows, **different order** |

### 4.3 Failure classification

1. **Semantic filtering (7 cases).** The emitted query requires each declared
   non-optional child to match its schema-derived kind set. Real Python
   assignments whose `left` is an `attribute`, `subscript`, or `pattern_list`
   fail that pattern, so the query skips them. The walk anchors on every
   `assignment`, then `from_node` fails Pydantic validation and `find_in`
   raises `ExtractionError`. On `mypy/checker.py` the query returns 1176 rows
   where the walk returns none and raises.
   **The query is not an accelerator. It is part of the matching semantics.**

2. **Row ordering (4 cases).** For self-nesting kinds the query yields matches
   in a different order from pre-order document order. The walk and the cursor
   both yield strict pre-order.

3. **Silent fallback (35 kinds).** `_query_walk` catches `QueryBuildError` and
   falls back to `_walk`. Affected kinds include rust `FunctionItem`,
   `CallExpression`, `MatchExpression`; bash `FunctionDefinition`; nix
   `IfExpression`, `WithExpression`, `ApplyExpression`. For those kinds the
   shipped default already *is* the walk — plus a failed compile on every call.

4. **Two shipped paths are not equivalent.** `find.py` states the direct
   resolver "still has complete schema behavior … the safe execution
   fallback". The measurement contradicts it: the fallback returns different
   rows, in a different order, and raises where the query path succeeds. A
   user's result depends on whether the emitted query happens to compile.

---

## 5. Benchmark

Two independent full runs (`evidence/bench-run1.*`, `evidence/bench-run2.*`),
30 / 15 / 7 repeats for small / medium / large, `gc.collect()` before each
sample, medians reported.

### 5.1 Parse cost, for the parse-plus-query vs query-only split

| language | small | medium | large |
|---|---|---|---|
| python | 0.264 ms | 3.517 ms | 49.033 ms |
| bash | 0.176 ms | 2.906 ms | 8.966 ms |
| nix | 0.303 ms | 0.671 ms | 11.582 ms |
| rust | 0.515 ms | 4.061 ms | 13.980 ms |
| markdown | 0.344 ms | 2.389 ms | 14.938 ms |

### 5.2 Anchor discovery — cold, warm, walk, cursor (median ms)

Representative rows; the full 63-row table is in `evidence/bench-run1.log`.

| language | tier | class | matches | A cold | A warm | B walk | C cursor |
|---|---|---|---|---|---|---|---|
| bash | small | Command | 10 | 3.306 | 0.111 | 0.082 | 0.096 |
| rust | small | ScopedIdentifier | 5 | 3.349 | 0.274 | 0.234 | 0.280 |
| python | medium | Identifier | 1670 | 4.351 | 2.939 | 1.284 | 1.610 |
| nix | large | Binding | 2225 | 23.555 | 22.640 | 5.288 | 5.295 |
| rust | large | Identifier | 2885 | 11.089 | 8.976 | 6.567 | 7.154 |
| markdown | large | ListItem | 122 | 4.347 | 3.604 | 0.943 | 2.636 |
| python | large | Identifier | 19161 | 54.118 | 55.502 | 16.197 | 20.316 |

Readings:

- **Cold A is dominated by the compile.** bash small: 3.306 ms cold vs 0.111 ms
  warm — about 3.2 ms of compile on a 1 251 B file. The shipped code pays this
  on every `find_in` call.
- **Warm A still loses to the walk** in most rows, sometimes badly (nix large
  `Binding`: 22.640 ms vs 5.288 ms, 4.3× slower).
- **C does not beat B.** The cursor visits every node including anonymous
  tokens; the recursive walk skips whole anonymous subtrees via
  `named_children`. C is slower than B in most rows (markdown large 2.636 vs
  0.943) and faster in a few bash rows.

### 5.3 Full `find_in` — where the time actually goes

Anchor discovery's share of total `find_in` time, from `evidence/bench-run1.json`:

| class | tier | shipped `find_in` | anchor share |
|---|---|---|---|
| nix `ApplyExpression` | large | 740.167 ms | **0.8 %** |
| rust `FunctionItem` | large | 438.307 ms | **1.8 %** |
| rust `CallExpression` | large | 294.858 ms | 3.4 % |
| markdown `Section` | large | 123.919 ms | 3.5 % |
| nix `Binding` | large | 486.504 ms | 4.8 % |
| bash `Command` | large | 158.452 ms | 5.0 % |
| python `Identifier` | large | 194.496 ms | 27.8 % |
| rust `LetDeclaration` | small | 2.578 ms | 99.8 % |

Where there is real extraction work, anchor discovery is **1–10 %** of the
call. Where anchor discovery dominates (60–100 %), there are almost no matches
and the absolute total is 0.5–5 ms — the cost there is the query compile, not
the search.

Full-path ratio `cursor_rows / shipped` spans 0.03 – 1.32. It is below 1 on
small trees (avoided compile) and reaches or exceeds 1 on large trees
(bash large `Command` 1.32, python large `Assignment` 1.17). Note that for the
python `Assignment` and rust `LetDeclaration` rows the two paths do **not**
return the same result (§4.2), so those ratios compare unequal work.

### 5.4 Repeated queries against one parsed tree

4–5 classes re-run 1, 10, and 50 times over a single parsed tree (median ms):

| language | tier | rounds | A cold | C cursor | C/A |
|---|---|---|---|---|---|
| bash | medium | 1 / 10 / 50 | 18.288 / 189.321 / 914.557 | 4.067 / 41.045 / 203.779 | 0.22 |
| rust | medium | 1 / 10 / 50 | 20.962 / 217.753 / 1087.892 | 6.934 / 75.568 / 353.590 | 0.33 |
| python | large | 1 / 10 / 50 | 100.615 / 1027.306 / 5490.107 | 70.557 / 651.217 / 3549.030 | 0.65 |
| nix | large | 1 / 10 / 50 | 40.852 / 420.804 / 2133.300 | 19.822 / 203.574 / 1046.727 | 0.49 |

The ratio is flat in the number of rounds. That is the signature of a cost that
never amortises: the shipped path recompiles the query on every call.

### 5.5 Memory / allocation (tracemalloc peak, medium tier)

| language | class | A cold | B walk | C cursor |
|---|---|---|---|---|
| bash | Command | 3 840.7 KiB | 6.2 KiB | 25.7 KiB |
| rust | Identifier | 1 931.2 KiB | 13.3 KiB | 81.0 KiB |
| python | FunctionDefinition | 1 421.1 KiB | 4.2 KiB | 5.3 KiB |
| markdown | AtxHeading | 479.4 KiB | 2.2 KiB | 3.4 KiB |
| nix | IfExpression | 288.5 KiB | 4.3 KiB | 2.8 KiB |

Anchor discovery through a freshly compiled query peaks at 288–3 876 KiB per
call; the walks peak at 2–121 KiB. Because the query is rebuilt per call, that
allocation repeats on every call. This is a property of the *caching*, not of
queries as such.

### 5.6 Variance across repeated runs

Comparing the 189 medians of run 1 and run 2:

```text
median drift 3.3 %   mean 10.9 %   p90 30.7 %   max 151.3 %
sign flips: 7 of 63 comparisons
```

Six of the seven flips are on the `cursor < recwalk` axis. **C and B are within
machine noise of each other**; the ordering between them is not stable. The
`cursor < query_cold` verdict is stable in 61 of 63.

---

## 6. Decision

Applying the stated gate — *"if the alternative is not clearly correct and
materially faster, retain the current emitter/query path and document the
deferral"*:

**Not clearly correct.** The cursor walk changes results on real corpora: it
raises `ExtractionError` where the shipped path returns 1176 rows, and it
returns a different row order for self-nesting kinds. The emitted query performs
semantic filtering that the walk does not reproduce.

**Not materially faster.** It is indistinguishable from the recursive walk
already in `find.py` (7 sign flips across two runs), and it loses to it on
markdown and python. Its only reliable win over the shipped path is avoiding a
per-call query compile — a cost removable without deleting anything.

**No deletion is justified.** `emit.py`, query support, capture support, and
`__raw_query__` all stay. Replacement coverage does not exist: the cursor walk
covers neither the query's filtering semantics nor its ordering.

### 6.1 What changed in this session

Nothing under `src/`, `tests/`, `docs/`, or `examples/`. No public API changed.
No generated artefact changed. The `examples/wheel-extract` transcript still
matches byte-for-byte. This session added evidence and probes only.

Per the gate, no prototype was landed: a prototype is warranted only when the
alternative *is* materially faster, and it is not.

## 7. Findings to carry forward

Two defects surfaced that are independent of idea 10. Neither is fixed here —
both are outside the scope of "replace the query path with a cursor walk".

**F1 — the compiled query is never cached.** `_query_walk` rebuilds and
recompiles on every call, and re-pays a failing compile for 35 kinds across the
five grammars. Measured cost 0.1–4 ms and 288–3 876 KiB per call.
`probes/bench_cache.py` implements a per-`(class, language)` cache that keeps
the query semantics exactly: **42 of 42 cases return identical rows**, median
speedup 1.07× on medium/large, up to 2.38× where matches are few, and 30× on
the small tier where the compile is the whole cost. This is the change idea 10
was reaching for, and it keeps every behaviour.

**F2 — the two shipped paths are not equivalent.** `_query_walk` and `_walk`
return different row sets, different row order, and different errors. The
comment in `find.py` calling `_walk` "the safe execution fallback" with
"complete schema behavior" is not supported by measurement. Which of the two is
correct is a design decision. Until it is settled, a class's result depends on
whether its emitted query compiles — and 35 kinds across five grammars do not
compile.

## 8. Gates

All run in the pinned `devenv` shell, `--no-tui --no-reload`. Raw output in
`evidence/gates/`.

```text
python -m pytest -q                     350 passed, 1 xfailed in 43.32s   exit 0
python -m pytest -q -W error            350 passed, 1 xfailed in 42.28s   exit 0
ruff check src tests examples           All checks passed!                exit 0
ty check src                            All checks passed!                exit 0
python -m pytest -q tests/test_docs_snippets.py   1 passed                exit 0
python examples/wheel-extract/extract.py   transcript byte-for-byte       exit 0
python examples/bash-extract/extract.py                                   exit 0
python examples/devenv-extract/extract.py                                 exit 0
python examples/devenv-subset/extract.py   host/port round trip           exit 0
```

## 9. Artefacts

```text
sessions/20260909-2890613b/
  REPORT.md                     this report
  probes/harness.py             grammars, corpus, the three strategies
  probes/oracle_sweep.py        exhaustive differential oracle
  probes/oracle_api.py          public-API oracle
  probes/bench.py               the benchmark
  probes/bench_cache.py         the compiled-query cache probe (F1)
  evidence/oracle-sweep.{json,log}
  evidence/oracle-api.{json,log}
  evidence/bench-run1.{json,log}
  evidence/bench-run2.{json,log}
  evidence/bench-querycache.{json,log}
  evidence/environment.txt
  evidence/gitman-status-baseline.{txt,json}
  evidence/gates/               raw gate and example output, with exit codes
```

---

## 10. Version-control outcome — BLOCKED, nothing committed

The evidence is **not committed and not pushed**. gitman refuses every mutating
verb while the repo is off-canonical:

```console
$ gitman split --paths <session dir> \
      --into task-cursor-walk-benchmark-20260909-2890613b -m "<msg>"
refusing: repo is off-canonical (lane(s) 024-typed-node-universe have a
divergent change-id (one change → multiple commits) — run `gitman reconcile`.)
— run `gitman reconcile`.
```

`gitman start` and `gitman save` are refused with the same message.
Record: `evidence/gitman-refusal.txt`.

### `gitman reconcile` does not clear it

With the user's authorisation, `gitman reconcile` was run twice. Both runs
returned **PARTIAL** (`evidence/gitman-reconcile.txt`):

```text
Gitman reconcile — PARTIAL
re-pointed colocated git ref(s) to jj: 024-typed-node-universe b9f39c8d -> b107690f.
note: still off-canonical: lane(s) 024-typed-node-universe have a divergent
change-id (one change → multiple commits) — run `gitman reconcile`.
```

Each run only re-points the colocated git ref to whatever commit jj has
snapshotted at that moment (`b9f39c8d` → `b107690f` → `c6bc74fd`); the commit id
moves again on the next command because jj re-snapshots the working copy. The
**divergent change-id itself is untouched**: change `vpzxkznmrrwxkxry` still maps
to two commits — the published bookmark's twin `64bf8de` and the live head.
`reconcile` has no repair for that, and its only other mode, `--abandon`,
discards strays; using it here could discard the other session's work, so it was
not run. Repeated `reconcile` calls do not converge, so the attempt was stopped.

The divergence pre-dates this session. It is recorded in the opening baseline
(§1.2) and was created by whatever rewrote the `024-typed-node-universe` lane
after publishing it.

### State of the worktree

- All 39 session files are intact under
  `.scratch/projects/026-cursor-walk-benchmark/sessions/20260909-2890613b/`.
- No file outside that directory was created, modified, or deleted by this
  session.
- jj auto-snapshots the working copy, so those files sit inside the
  `024-typed-node-universe` draft change, which grew from 141 to 176 files.
- The two `reconcile` runs moved the `024-typed-node-universe` **git ref** to
  follow jj. No commit was discarded. `gitman undo` reverts them.

### To land this evidence

The divergent change-id must be resolved first, by a session authorised to own
the `024-typed-node-universe` lane. After that:

```console
gitman split \
  --paths .scratch/projects/026-cursor-walk-benchmark/sessions/20260909-2890613b \
  --into task-cursor-walk-benchmark-20260909-2890613b \
  -m "026: cursor-walk vs emitter/query benchmark — retain the query path (idea 10)"
gitman switch task-cursor-walk-benchmark-20260909-2890613b
gitman publish
```

The lane name uses a flat form. A `/`-path name such as
`task/cursor-walk-benchmark-…` would stack on a name-parent lane `task`, which
does not exist; a flat name roots on trunk, which is what a sibling lane needs.

Do not land, tag, or release. Leave integration to a later session.

### Side effect of running the maintained examples

`python examples/devenv-subset/extract.py` rebuilds its bundle in place. Five
tracked files were rewritten at 11:03:

```text
examples/devenv-subset/dist/grammar.so
examples/devenv-subset/dist/loader.py
examples/devenv-subset/dist/node-schema.json
examples/devenv-subset/dist/nodes.py
examples/devenv-subset/dist/tree-sitter.json
```

This is the example's normal behaviour, not an edit by this session. The
example exited 0 and reproduced its ground truth (`host = example.com`,
`port = 8080`). Whether the bytes differ from the committed bundle could not be
checked, because every version-control diff verb is blocked (§10). Hashes of
the on-disk result are recorded in `evidence/devenv-subset-dist-sha256.txt`.
No other file under `src/`, `tests/`, `docs/`, `examples/`, or `.agents/` was
touched by this session.

---

## 11. Addendum — ast-grep over a pydantree-built grammar (follow-up question)

Probe: `probes/probe_astgrep_bundle.py`. Raw output:
`evidence/astgrep-bundle.{json,log}`, `evidence/astgrep-metavar-sigil.txt`.
ast-grep-py 0.45.3.

**It works, end to end.** `register_bundle_language` hands a bundle's
`grammar.so` to `ast_grep_py.register_dynamic_language`:

| check | result |
|---|---|
| register bundle `.so` as ast-grep language `pdtnix` | ok |
| ast-grep parses with it | root `source_code`, 3 `binding` nodes |
| tree agreement, pydantree vs ast-grep | 33 named nodes, intersection 33, **0 only in pydantree** |
| `Pattern(Rule(kind="binding"), …, astgrep_name="pdtnix").find_all` | 3 matches, correct byte spans |
| `PatternMatch.extract(nodes.Binding)` | typed rows resolve |
| metavariables, default `$` sigil | **0 matches, silently** |
| metavariables, `meta_var_char="_"` | `{ _K = _V; }` → K=`packages`, V=`[ pkgs.git ]` |

Agreement is by construction, not by measurement: both engines load the same
artifact, so the node sets cannot drift. `CONCEPT §7`'s claim that a
B-built grammar "has no ast-grep support" is wrong, as `pattern.py` already
states.

### Gaps found

1. **The ergonomic entry point does not exist.** `pattern.py:97` documents
   `Language.register_astgrep()`. Phase 024 collapsed `Language` into
   `Grammar`, and `Grammar.__slots__` is `("language", "namespace", "schema")`
   — no `astgrep_name`, no `astgrep_is_bundle`. `Pattern(rule,
   language=grammar)` therefore raises `UnsupportedLanguageError` ("Known
   here: python"). Every caller must pass `astgrep_name=` by hand. The
   ast-grep seam was orphaned by the refactor.
2. **No test covers the capability.** `register_bundle_language` and
   `registered_languages` appear in no test file.
3. **The metavariable sigil is a per-grammar property with a silent failure
   mode.** It belongs in the bundle metadata, not in the caller's head.
4. **ast-grep-py accepts dynamic languages only in its first registration
   call.** `pattern.py` already raises on the second call. A single collection
   point is needed to register several bundles in one process.

---

## 12. Re-measurement after the 2026-09-09 12:41 repo change

A concurrent session changed the repository while this investigation was
written up. Everything below was re-measured against the changed code.
Evidence: `evidence/oracle-sweep-rerun.*`, `evidence/oracle-api-rerun.*`,
`evidence/bench-python-rerun.*`, `evidence/gates-rerun/`.

### What changed

| change | detail |
|---|---|
| vendored Python schema | 9 entries → **217** (real `tree-sitter-python` 0.25.0 `node-types.json`, with a provenance file) |
| new conformance gate | `grammar._conformance` / `_verify_conformance`, `Grammar.load(..., verify=True)`, raises `SchemaDriftError` on alien or missing kinds |
| new test file | `tests/test_schema_conformance.py` |
| public surface | 12 → **14** names (`SchemaDataError`, `SchemaDistributionError`, `SchemaMissingError`) |
| also touched | `generate.py`, `schema.py`, `errors.py`, `wheel-extract` example + transcript, `docs/`, several tests |
| toolchain | `uv.lock` re-locked 12:41; the devenv venv's `ruff` was replaced 12:52 (now 0.15.21) |
| suite | 350 → **364 passed, 1 xfailed** |

**Untouched:** `find.py`, `nodes.py`, `raw.py`, `emit.py`, `pattern.py`,
`agreement.py`. The whole query/walk and ast-grep machinery is unchanged.

### Retracted

The report's strongest Python example **no longer reproduces**. §4.2 and §4.3
cite python `Assignment` returning 1176 query rows against an `ExtractionError`
from the walk. That came from the 9-entry demo schema declaring
`assignment.left` as `identifier` only. The real schema declares
`left: pattern | pattern_list`, which expands to every real kind, so the query
and the walk now agree. Treat that row as an artefact of schema quality, not
as evidence about the query path.

API-level `cursor_vs_query` divergences fell from **13 to 7**.

### Survived, and in two places strengthened

| finding | before | after |
|---|---|---|
| cursor walk == recursive walk | 0 mismatches / 984 cases | **0 mismatches / 1326 cases** |
| kinds whose emitted query will not compile | 35 | **45** (Python alone 1 → 11) |
| under-matching on community schemas | bash, rust | unchanged: bash `UnaryExpression` 19 vs 163, `BinaryExpression` 143 vs 155, `VariableAssignment` 406 vs 417; rust `LetDeclaration` 127 vs walk-raises |
| order-only divergence, self-nesting kinds | rust | rust **plus** python `BinaryOperator`, `BooleanOperator` |
| compiled query never cached (F1) | true | true — `find.py:160`, `find.py:202` unchanged |

Python's 11 non-compiling kinds now include `FunctionDefinition`,
`ClassDefinition`, `Call`, `Attribute`, `ForStatement`, `WhileStatement`,
`WithStatement`. **A more accurate schema made the emitted query worse, not
better.**

### The performance case is stronger

With the real schema the resolver builds full nested models, so anchor
discovery shrinks to a rounding error (median ms, large tier):

| class | matches | shipped `find_in` | anchor share |
|---|---|---|---|
| `FunctionDefinition` | 352 | 3158.391 | **0.8 %** |
| `ClassDefinition` | 14 | 2486.086 | **1.0 %** |
| `Call` | 3034 | 1135.646 | 1.8 % |
| `Assignment` | 1499 | 756.475 | 2.6 % |

Replacing anchor discovery cannot pay for itself.

### New regression: ruff fails

```text
ruff check src tests examples    Found 8 errors.    exit 1
```

At 10:50 the same command printed `All checks passed!` (exit 0,
`evidence/gates/ruff.txt`). Seven of the eight are `E402` / `E741` in files
unchanged since 2026-09-08 (`tests/test_scanners.py`, `tests/test_corpus.py`,
`tests/fixtures/bfree/consumer_env/sitecustomize.py`); the ruff version changed
with the 12:41 re-lock and surfaced them. The eighth is new code:
`E741 Ambiguous variable name: l` at `tests/test_packaging.py:65`, a file
edited at 12:41.

`pytest`, `pytest -W error`, `ty check src`, and the docs snippets all still
pass. This breaks the project's own "ruff must be green before a PR" gate.

### Unaffected

The ast-grep addendum (§11) stands. `Grammar.__slots__` is still
`("language", "namespace", "schema")` with no `astgrep_name`, so the seam
remains orphaned, and the probe was run against the current code.

---

## 13. Where the time really goes — resolution, not search

Measurement: `evidence/resolution-cost.txt`. `bare` is the same kind with no
declared fields (anchors plus a trivial model); `typed` is the generated class
(anchors plus full nested resolution). Large tier.

| language | kind | matches | typed | bare | resolution share | per match |
|---|---|---|---|---|---|---|
| python | `class_definition` | 14 | 2118.9 ms | 13.92 ms | **99.3 %** | **151.35 ms** |
| python | `function_definition` | 352 | 2463.9 ms | 19.37 ms | **99.2 %** | 7.00 ms |
| rust | `impl_item` | 119 | 694.7 ms | 8.97 ms | 98.7 % | 5.84 ms |
| rust | `function_item` | 182 | 498.4 ms | 9.39 ms | 98.1 % | 2.74 ms |
| nix | `apply_expression` | 2014 | 891.6 ms | 24.70 ms | 97.2 % | 0.44 ms |
| nix | `binding` | 2225 | 664.8 ms | 27.59 ms | 95.9 % | 0.30 ms |
| python | `call` | 3034 | 1067.1 ms | 52.91 ms | 95.0 % | 0.35 ms |
| rust | `let_declaration` | 128 | 141.3 ms | 11.33 ms | 92.0 % | 1.10 ms |

**Resolution is 92–99.3 % of every call. Anchor discovery is 0.7–8 %.**

The resolver recurses: `FunctionDefinition.body: Block` calls
`Block.from_node`, which resolves *its* children, and so on to the leaves. One
Python `class_definition` therefore costs 151 ms, because it materialises its
whole body as typed models before the caller reads a single field.

### Failure propagates the same way

`find_in(raw, FunctionItem)` on `alloc/src/sync.rs` raises `ExtractionError`,
and the reported cause is a `let_declaration` **nested inside a function body**:

```text
1 match(es) failed to materialize FunctionItem:
  - pattern 0 @ line 4019 'fn from(v: Vec<T, A>) -> Arc<[T], A> { ... }':
    1 validation error for LetDeclaration
    pattern  Field required [type=missing, ...]
```

The offending node is `let _ = Vec::from_raw_parts_in(...)`. One unresolvable
node, several levels down, discards every `FunctionItem` in the file. This is
assert semantics and eager resolution compounding: the cost model and the
failure model share one root cause.

---

## 14. Phase D1 — lazy nested resolution

### Changes

| file | change |
|---|---|
| `src/pydantree_sitter/nodes.py` | Added deferred direct `Node` child fields. `Node.from_node` now builds shallow placeholders, keeps CST children in a private cache, and resolves each field once on access. Scalar, literal, mapping, `span`, and `__value__` paths remain eager. Cached exceptions are re-raised from the field. `model_dump()` and `model_dump_json()` materialize the value tree before serialization. |
| `src/pydantree_sitter/find.py` | Applied the same lazy field path to raw-query captures. The raw escape hatch keeps its existing query and capture semantics. |
| `tests/test_lazy_nodes.py` | Added eager/lazy equivalence, cache identity, serialization, local nested failure, and raw-query nested-field tests. |
| `docs/filter-semantics.md` | Documented lazy direct `Node` fields, eager anchor metadata, serialization, and local failure behavior. |
| `sessions/.../probes/bench.py` | Rebased the benchmark on the post-Phase-C walk path and added lazy-versus-full-materialization timing. Added `PDT_BENCH_ONLY=language:Class` for focused runs. |
| `evidence/` | Added `bench-phase-d1-class.{json,log}`, the broader benchmark report, and `gates-phase-d1/` raw gate outputs. |

### Acceptance benchmark

Baseline from `evidence/resolution-cost.txt`:

```text
python class_definition n=14 typed=2118.9ms bare=13.92ms
resolution=99.3% per-match=151.35ms
```

Post-D1 output from `evidence/bench-phase-d1-class.log`:

```text
python    large  ClassDefinition        14    20.543    15.978
row materialization
python    large  ClassDefinition        14    24.693  3941.530 full/lazy=159.62
```

The lazy `find_in` cost is 24.693 ms total, or 1.764 ms per match. That is
an 85.8x reduction (98.8%) from the handoff's 151.35 ms per match. Full
materialization remains available when callers read nested fields; its cost
is intentionally visible in the benchmark. The broader run shows the same
shape for Python `FunctionDefinition`: 61.415 ms lazy versus 4960.910 ms
fully materialized on 352 large-file matches.

The new tests compare the lazy row with the existing eager resolver for the
same fields. They also cover a malformed nested child: the parent is returned,
`span` and `__value__` remain usable, and the same nested validation exception
is cached and raised only when that field is read.

### Gates

```text
devenv shell -- pytest -q
369 passed, 1 xfailed in 79.50s (0:01:19)
exit 0

devenv shell -- pytest -q -W error
369 passed, 1 xfailed in 74.42s (0:01:14)
exit 0

devenv shell -- ruff check src tests examples
All checks passed!
exit 0

devenv shell -- ty check src
All checks passed!
exit 0

devenv shell -- pytest -q tests/test_docs_snippets.py
1 passed in 0.09s
exit 0

devenv shell -- python examples/wheel-extract/extract.py
devenv shell -- python examples/bash-extract/extract.py
devenv shell -- python examples/devenv-extract/extract.py
devenv shell -- python examples/devenv-subset/extract.py
all four maintained examples completed successfully
exit 0
```

### API and artefact delta

There is no new public top-level name and no generated bundle change. The
private `Node` extraction implementation now includes `_LazyField` and
`_lazy_fields`; direct field access, serialization, and raw-query extraction
retain their documented behavior. The benchmark and raw outputs are under
`evidence/`.

### Not done

D2 (promoting `Pattern` as the documented expressive front end and reducing
`agreement.py`) and D3 rewrite work were not started. Version-control work was
not performed: gitman reported the lane desynchronized again during the final
read-only check, so no commit, publish, or reconcile was safe.
