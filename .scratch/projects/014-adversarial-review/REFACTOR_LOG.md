# pydantree-sitter refactor — phase log (append-only)

Every phase gate records: suite result, commit hash, and anything notable.
Baseline per the guide: **199 passed, 1 skipped @ `fcf505f`** (devenv, warm
cache).

## Gate 0 — oracles before surgery

- **Suite:** 203 passed, 1 skipped, 5 xfailed (strict) (56.5s, devenv) —
  the 4 new oracle tests pass; the 5 thesis-breaking-bug xfails fail as
  designed (they pin the CORRECT behavior).
- **Commit:** `09b40a2` (prerequisite repair: the `.scratch/projects` move
  commit `808c1ce` left `tests/*` sys.path refs pointing at the old flat
  `.scratch/NNN-*` paths and scratch helpers (`bfree.py`, `dev_agreement.py`)
  computing `ROOT` one level too shallow — suite was uncollectable. Fixed
  both mechanically; suite back to the `fcf505f` count.)
- **Oracles committed:** `tests/oracles/{bash-extract,devenv-extract,devenv-subset}.json`
  generated from current code and cross-checked byte-identical against the
  examples' own hand-written ground truths (bash 46 rows across 3 files × 3
  models; nix 102 rows; subset 56 rows + 1 env record + 5 toolchain
  records). The 3 oracle tests run the examples' own models + helpers over
  bundles built from `tests/fixtures/{bash,nix}` and the example's own
  grammar.py + scanner.c (toolchain-gated).
- **New strict xfails (thesis-breaking bugs, to flip in Phase 4):**
  F-A1 (cross-language silent `[]`), F-A2 (schema-bound nested records drop
  matches), F-A3 (NodeKind tuple dropped in field mode), NEW list-branch
  (`...` path skipped for list fields), T-1 (choice-order `required`
  diverges from the CLI — flips to the by-construction pipeline test in
  Phase 3).
- **Also fixed:** `probe_nested_schema.py` still pointed at the flat
  `.scratch/006-*` path (same move breakage).
