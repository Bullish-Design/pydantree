# Review 021 — verdict

**Date:** 2026-08-19 · **Full report:** [FINDINGS.md](FINDINGS.md) ·
**Evidence:** `evidence/` · **Repros:** `probes/`

## One line

The concept is sound and the discipline is unusually good, but three
silent-wrong-answer defects sit on mainline surfaces, and the schema bridge —
the thing that makes this library different — is **off in every documented
entry path** and **breaks an advertised feature in one of the two paths where
it is on**.

## The three that matter

| # | defect | effect |
|---|---|---|
| **D-1** | two `list[T]` fields on one anchor produce a cartesian merge | 12 items per field → **1728** entries per list; `k^N` matches. Silent corrupt data. |
| **D-2** | `_check_path` walks a `PathStep`'s **alternatives** as a **descent chain** | `M("document", ("object","array"))` is rejected with a nonsense error. The feature works only when no schema is bound. Its 020 regression test passes on the wrong error (D-2b). |
| **D-3** | the emitter turns model **field declaration order** into query sibling order | reordering two fields → `QueryBuildError: Impossible pattern at row 0, column 41`, about `.scm` the user never wrote. Undocumented; the docs say the opposite. |

D-1 and D-3 have the same root cause and the same fix: **emit one anchored
pattern per capture** instead of one pattern with N sibling captures. The
anchor-merge machinery in `match.py` already exists for exactly this, and the
alternative is demonstrated working in FINDINGS §7.1.

## The concept-level calls

- **C-2** — community wheels ship no `node-types.json`, so
  `Language.from_module(...)` runs **zero** model↔grammar and capture↔type
  checks. Every README / user-guide / example snippet is on that path,
  including the flagship toolchain-free `examples/wheel-extract/`. Either ship
  schemas or warn loudly; the `# checks run here, once` comment is false where
  it appears.
- **C-3** — "value shapes are declared data, never silent name-regex
  inference" is not true of the check path: `_scalar_of` falls back to the
  draft heuristic, which calls `constraint`, `hint`, `joint` and `waypoint`
  numeric. Narrow the claim or surface the inferences as bind warnings.
- **C-5** — `record=True` swaps out half the runtime (two queries, a different
  anchor, a different materializer, its own predicate and nesting semantics).
  Make it a named base class in its own module; `compiler.py` then halves.

## Recommended order of work

1. One anchored pattern per capture (D-1, D-3) — 1–2 days.
2. `_check_path` alternatives + per-anchor kind inference (D-2, D-2b, D-7) — half a day.
3. `extract_tree` language guard + nested-extractor placeholder (D-5, D-4) — 1 hour.
4. Record-mode silent narrowings (D-6) — half a day.
5. Export the documented B API; drop `"rule"` from `__all__` (D-9, D-10) — 15 min.
6. Schema-distribution decision + doc truth-up (C-2, C-3) — 1 day.
7. Lint/type gate, `W605`, dead code, stale counts (D-13…D-18) — 2 hours.
8. Record mode into its own module (C-5) — 2 days.

## Baseline

`342 passed`, exit 0, ~78 s under `devenv shell`. Coverage 79–100 % per
module. 171 ruff findings and 36 mypy errors, none of which fail anything
(`py.typed` ships regardless).
