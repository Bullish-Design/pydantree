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

### Oracle suite

Command:

```bash
devenv shell -- python -m pytest tests/test_oracles.py -q
```

Evidence: [`evidence/oracle-run.txt`](evidence/oracle-run.txt)

Result: **8 passed in 0.55s**. Source inspection confirms that `_oracle()`
reads the checked-in JSON and the three real-example tests compare their
collectors directly to it. The ground-truth agreement test independently
loads each example's hand-written `ground_truth.json` and compares it to the
oracle JSON after removing only note fields.

The suite builds fresh temporary bundles. It does **not** load or compare any
file under `tests/oracles/.built/`.

### Example scripts

Commands:

```bash
devenv shell -- python examples/bash-extract/extract.py
devenv shell -- python examples/devenv-extract/extract.py
DEVENV_BUNDLE_DIR=/tmp/review019-devenv-bundle \
  devenv shell -- python examples/devenv-subset/extract.py
devenv shell -- python examples/bash-extract/extract.py \
  --bundle tests/oracles/.built/bash
devenv shell -- python examples/devenv-extract/extract.py \
  --bundle tests/oracles/.built/nix
```

Evidence:

- [`evidence/example-bash.txt`](evidence/example-bash.txt)
- [`evidence/example-devenv.txt`](evidence/example-devenv.txt)
- [`evidence/example-subset.txt`](evidence/example-subset.txt)
- [`evidence/example-bash-bundle.txt`](evidence/example-bash-bundle.txt)
- [`evidence/example-devenv-bundle.txt`](evidence/example-devenv-bundle.txt)

Results:

- The default bash and nix invocations fail before extraction because the
  managed dev environment lacks `tree_sitter_bash` and `tree_sitter_nix`.
- The documented bundle paths pass against the committed bundles: bash
  extracts **34 rows** and nix **102 rows**, all matching the examples' own
  ground truths.
- The authored subset builds with the real scanner and extracts **56 rows**,
  all matching its ground truth.

All three READMEs describe the corpus, models, build/load shape, and
self-check. The two Product A READMEs' install snippets repeat
`pydantree-sitter` twice and are not commands supported by this repository's
mandatory devenv-managed workflow.

### Oracle regeneration stability

The literal regeneration command was first tried in a detached throwaway
worktree:

```bash
devenv shell -- python tests/test_oracles.py --generate
```

Evidence: [`evidence/oracle-regenerate.txt`](evidence/oracle-regenerate.txt)

It failed before generation because the new worktree's `devenv:python:uv`
task reported success while the managed Python lacked `pydantic`. A second
probe confirmed the worktree selected its own managed venv and still could
not import `pydantic`:
[`evidence/fresh-worktree-import.txt`](evidence/fresh-worktree-import.txt).

To isolate output determinism from that environment failure, the committed
probe redirects the harness's `ORACLES` output path:

```bash
devenv shell -- python \
  .scratch/projects/019-final-verification-review/probe_oracle_regen.py \
  /tmp/pydantree-review019.UkcAVR/generated
```

Evidence:

- [`evidence/oracle-regenerate-probe-success.txt`](evidence/oracle-regenerate-probe-success.txt)
- [`evidence/oracle-regenerate-hashes.txt`](evidence/oracle-regenerate-hashes.txt)

Result: the regenerated bash, nix, and subset JSON files are each
**byte-for-byte identical** to their checked-in oracle.

### Committed bundle reproducibility

Probe:

```bash
PYDANTREE_SITTER_CACHE=/tmp/pydantree-review019.UkcAVR/fresh-cache \
  devenv shell -- python \
  .scratch/projects/019-final-verification-review/probe_artifact_rebuild.py \
  /tmp/pydantree-review019.UkcAVR/bundles-fresh
```

Evidence:

- [`evidence/artifact-rebuild-fresh-cache.txt`](evidence/artifact-rebuild-fresh-cache.txt)
- [`evidence/artifact-rebuild-hashes.txt`](evidence/artifact-rebuild-hashes.txt)

Result:

- `subset`: all four files reproduce byte-for-byte.
- `bash` and `nix`: `loader.py` and `node-schema.json` reproduce exactly,
  but `grammar.so` does not. Bash is 1,335,584 committed bytes versus
  1,352,112 rebuilt bytes; nix is 98,880 versus 99,024 bytes.
- Their metadata also drifts: committed `toolchain` is `"community"`; the
  current pipeline writes `"tree-sitter 0.25.3"`.

No provenance or regeneration document for `.built/` was found. The
documented `--generate` path regenerates only JSON oracles, not these bundles.

## Fixture verification

Not yet run.

## Review 018 red-against-prefix spot checks

Not yet run.

## Gap probes and determinism

Not yet run.

## Final suite

Pending.
