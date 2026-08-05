# 014 — adversarial review (concept / architecture / codebase)

**Date:** 2026-08-05. Deep adversarial review of the whole project, requested
to push toward "the best, cleanest, most elegant concept, architecture, and
codebase possible".

## Contents

- **`REFACTOR_GUIDE.md`** — the implementation plan that followed the review
  and the conceptual re-assessment: decision log (D1-D14, incl. the
  `pydantree-sitter` naming, the two-package fold, and deleting the
  `node_types.rs` port), target end-state, phases 0-9 with per-phase gates,
  finding→step traceability, and final grep gates.
- **`REVIEW.md`** — the review. Verdict + top-10, concept critique (C1-C6),
  architecture critique (§2, incl. the `BoundExtractor` proposal and the
  seam-inversion fix), ranked findings for A (F-A1..14), B (F-B1..13),
  tscore/legacy (T-1..10), tests (§6), packaging/docs (P-1..10), and a
  10-step priority program (§8).
- **`CONFIRMED_BUGS.md`** — the live-reproduced bugs with file:line root
  causes.
- **`AGENT_REPORTS.md`** — the three delegated deep-dive reports, verbatim
  (test suite; packaging/docs/PyPI; `_ir_derive`/`_wasm_bridge`/legacy).
- **`probe_findings.py`** — repros: cross-language silent `[]` (F-A1),
  NodeKind tuple drop (F-A3), warning noise, registry state.
- **`probe_nested_schema.py`** — repro: schema binding breaks nested record
  models (F-A2).
- **`probe_b_side.py`** — repros: `alias=` garbage (F-B1), `_snake`
  acronyms, whitespace-extra duplication, assemble() module sweep;
  multi-Literal crash reproduced separately (F-B2).

Run probes inside the devenv:
`devenv shell -- uv run --no-sync python .scratch/projects/014-adversarial-review/probe_findings.py`

Baseline at review time: 199 passed, 1 skipped (in-devenv, warm cache),
commit `fcf505f`.
