# Phase 024 item 6 — cursor-walk benchmark

Date: 2026-09-09

## Decision

Retain the current emitter and tree-sitter query path. Defer a cursor-walk
replacement. Do not delete `emit.py`, `Query`, capture support, or the raw
query API.

The direct walk prototype is faster for simple broad anchors. It is not a
complete replacement. It omits query predicates, raw-query patterns, and the
query engine's capture semantics. The decision gate therefore fails the
"clearly correct and materially faster" requirement for a replacement.

## Baseline and isolation

The repository root is `/home/andrew/Documents/Projects/pydantree`.

gitman reported the final Phase 024 code on trunk commit
`b9cad4fae65ab44119a74b1e85af9dcf085de17b`. The published
`024-typed-node-universe` lane points at the completed refactor, and the
working tree is off-canonical because that lane has a divergent change-id.
The requested unique lane creation command was:

```text
devenv shell -- gitman start task/cursor-walk-benchmark-20260909-0912
```

gitman refused it because the existing Phase 024 lane requires
`gitman reconcile`. This task did not reconcile, repair, switch, land, or
publish that lane. No unique branch or commit exists for this evidence.

## Behavioral oracle

The probe compares `Tree.find()` with a local direct tree walk that visits
named children and calls the same typed resolver. It covers:

- root and nested matches;
- repeated assignment matches and row order;
- `__under__` ancestor context;
- named-node and `Annotated` predicate constraints;
- optional missing return types;
- malformed queries (`QueryBuildError`);
- incompatible raw queries (`SchemaCheckError`); and
- the public `RawQuery` path and captures.

All ordinary query rows matched the direct-walk rows. The raw-query rows
matched the current raw-query oracle. The retained Phase 024 oracle also
covers the committed Python, Bash, Nix, Rust, Markdown, Markdown-inline, and
JSON-like fixtures through `tests/test_oracle_024.py`.

The probe is [probe_cursor_walk_benchmark.py](probe_cursor_walk_benchmark.py).
The behavioral output is [behavior-oracle.json](evidence/2026-09-09/behavior-oracle.json).

## Benchmark method

The probe ran 20 samples per case. Each sample measured:

1. parse plus query;
2. query-only on a parsed tree;
3. direct-walk-only on the same tree; and
4. ten repeated warm queries on one parsed tree.

The direct prototype uses no `Query`, `QueryCursor`, emitted source, or raw
query. Both paths use the same `Node.from_node` resolver. Build time for the
community bundles is outside the samples. The bundle build outputs are kept
under the dated evidence directory.

Environment: Python 3.13.5, tree-sitter 0.26.0, Linux 6.18.38,
GCC 13.3.0. The raw samples are in [timings.jsonl](evidence/2026-09-09/timings.jsonl),
with aggregate median, minimum, maximum, and standard deviation in
[summary.json](evidence/2026-09-09/summary.json).

Median milliseconds:

| fixture | parse + query | warm query | direct walk | ten warm queries |
| --- | ---: | ---: | ---: | ---: |
| Python small | 1.454 | 1.438 | 0.049 | 14.708 |
| Python large | 2.671 | 2.197 | 1.261 | 22.493 |
| Bash | 4.147 | 4.062 | 0.582 | 41.712 |
| Nix | 0.907 | 0.877 | 0.383 | 9.164 |
| Rust | 31.377 | 28.685 | 26.702 | 309.547 |
| Markdown | 4.987 | 4.861 | 4.175 | 48.818 |
| JSON medium | 6.529 | 6.370 | 6.162 | 66.630 |

The direct walk is approximately 1.03x faster than warm query for JSON,
1.16x for Markdown, 1.07x for Rust, 1.74x for Python large, 2.29x for Nix,
7.00x for Bash, and 29.37x for Python small. The large spread tracks the
amount of query work avoided and does not establish semantic replacement.

Memory and allocation behavior was not measured. Python-level allocation
tools cannot account for tree-sitter's native query allocations without
changing the timing path. The raw timing evidence therefore supports a
latency result only.

## Gates

All commands ran through `devenv shell`:

```text
python -m pytest -q
344 passed, 1 xfailed in 44.88s

python -m pytest -q -W error
344 passed, 1 xfailed in 44.04s

ruff check src tests examples
All checks passed.

ty check src
All checks passed.

python -m pytest -q tests/test_docs_snippets.py
1 passed in 0.07s
```

Maintained examples all exited zero: wheel-extract, bash-extract,
devenv-extract, and devenv-subset. The benchmark also built and exercised the
real Bash, Nix, Rust, and Markdown community fixture bundles.

## Failure classification and recommendation

The only probe failures were two local probe defects: an incorrect scratch
root calculation and postponed annotations hiding predicate metadata. Both
were corrected in the probe. No library failure occurred.

The alternative is a useful future optimization for ordinary schema-shaped
queries, but it needs a complete implementation of predicates, named and
unnamed constraints, optional and repeated projections, ancestor context,
capture ordering, query errors, and raw-query dispatch before comparison.
Until that coverage exists, keep the current query/emitter path and its raw
query escape hatch intact.

No public API changed. No generated project artifact changed. The only task
artifacts are this report, the probe, raw timings, summaries, environment
metadata, and dated benchmark bundles under `.scratch/projects/026-cursor-walk-benchmark/`.
