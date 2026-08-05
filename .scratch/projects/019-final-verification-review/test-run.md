# Review 019 — test run log

Date: 2026-08-05  
Repository: `/home/andrew/Documents/Projects/pydantree`  
Branch: `main`

This is the command ledger for the testing-and-verification review. Raw command
output is kept under `evidence/`.

## Baseline

### Repository state

Commands:

```bash
git status --short --branch
git remote -v
git fetch origin
git rev-list --left-right --count main...origin/main
```

Result: the initial worktree was clean, `main` tracked `origin/main`, and the
post-fetch ahead/behind count was `0 0`.

### Full suite, verbose

Command:

```bash
devenv shell -- python -m pytest -v
```

Evidence: [`evidence/full-run.txt`](evidence/full-run.txt)

Result: **265 passed in 61.31s**. The verbose log records every collected test.

The first attempt streamed through `tee`; the execution channel capped the
stream at 18%, causing an incomplete log and invalidating that attempt. The
suite was rerun with stdout/stderr redirected directly to the evidence file;
that second run exited 0 and produced the complete 305-line log above.

Per-file counts from the successful verbose run:

| file | passed |
|---|---:|
| `test_builder.py` | 10 |
| `test_bundle.py` | 18 |
| `test_checks.py` | 14 |
| `test_checks_nullable.py` | 7 |
| `test_codegen.py` | 5 |
| `test_conflicts.py` | 22 |
| `test_corpus.py` | 13 |
| `test_expressions.py` | 7 |
| `test_extract.py` | 18 |
| `test_grammar_ir.py` | 8 |
| `test_ladder.py` | 8 |
| `test_loader.py` | 7 |
| `test_match.py` | 4 |
| `test_metadata.py` | 2 |
| `test_oracles.py` | 8 |
| `test_packaging.py` | 6 |
| `test_patterns.py` | 9 |
| `test_phase6_fixes.py` | 11 |
| `test_pipeline.py` | 13 |
| `test_raw_query.py` | 5 |
| `test_rules.py` | 15 |
| `test_rules_sites.py` | 2 |
| `test_scanners.py` | 16 |
| `test_schema.py` | 10 |
| `test_toolchain_version.py` | 1 |
| `test_tsquery_port.py` | 12 |
| `test_tsquery_schema.py` | 11 |
| `test_valuemap_check.py` | 2 |
| `test_wasm.py` | 1 |

### Non-toolchain selection

Command:

```bash
devenv shell -- python -m pytest -q -m "not toolchain"
```

Evidence: [`evidence/non-toolchain-run.txt`](evidence/non-toolchain-run.txt)

Result: **136 passed, 129 deselected in 9.76s**. Thus 129/265 tests are
explicitly toolchain-marked and 136 form the toolchain-free selection. The
toolchain was present for the full run, so there were no conftest-generated
toolchain skips in that run.

### Toolchain versions

Commands (inside the mandatory environment):

```bash
devenv shell -- tree-sitter --version
devenv shell -- sh -c 'gcc --version | head -1'
```

Evidence: [`evidence/toolchain-versions.txt`](evidence/toolchain-versions.txt)

Result:

```text
tree-sitter 0.25.3
gcc (GCC) 14.2.1 20250322
```

The pinned versions match the review prompt.

## Oracle and example verification

Not yet run.

## Fixture verification

Not yet run.

## Review 018 red-against-prefix spot checks

Not yet run.

## Gap probes and determinism

Not yet run.

## Final suite

Pending.
