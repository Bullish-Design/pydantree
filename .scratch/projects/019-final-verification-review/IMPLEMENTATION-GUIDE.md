# Review 019 — clean-session implementation guide

**Purpose:** close every Review 019 finding (V1–V7), prove the fixes with the
real toolchain, and leave a clean, pushed `main` that supports the repository's
strong saved-output verification claim.

**Current starting point (2026-08-05):** V1 is already resolved on `main` by
commit `ce479f8` (`tests: keep oracle contract JSON-only`). The baseline is 265
passing tests. V4 and V5 remain the release blockers. V2, V3, V6, and V7 are
required hardening work in this guide so the whole review is closed rather than
only the minimum ship condition.

This guide deliberately does **not** preserve backward compatibility with old
generated bundles. Do not restore `tests/oracles/.built/`, do not check in a
native grammar library, and do not add tests that load historical bundle
binaries or metadata. The oracle contract is extraction JSON produced by fresh
builds through the current pipeline.

---

## 1. Start the clean session

### 1.1 Read the authoritative context

Use the `pydantree-dev` skill and read these files before editing:

1. `.agents/skills/pydantree-dev/SKILL.md`
2. `docs/architecture.md`
3. `docs/development.md`
4. `.scratch/projects/019-final-verification-review/PROMPT.md`
5. `.scratch/projects/019-final-verification-review/FINDINGS.md`
6. `.scratch/projects/019-final-verification-review/verdict.md`
7. `.scratch/projects/019-final-verification-review/RESOLUTION.md`
8. this guide

Treat `FINDINGS.md`, `test-run.md`, and `verdict.md` as the historical review
record. Do not rewrite their observations after fixing them. Record closure in
`RESOLUTION.md` and a new implementation log as described in Step 8.

### 1.2 Synchronize and establish the baseline

```bash
cd /home/andrew/Documents/Projects/pydantree
git status --short --branch
git fetch origin
git rev-list --left-right --count main...origin/main
devenv shell -- tree-sitter --version
devenv shell -- sh -c 'gcc --version | head -1'
devenv shell -- python -m pytest tests/ -q
```

Required starting evidence:

- branch is `main`, initially clean and synchronized;
- tree-sitter is 0.25.3 and gcc is 14.2.1;
- 265 tests pass;
- `tests/oracles/.built/` does not exist and `git ls-files
  tests/oracles/.built` prints nothing.

Create `.scratch/projects/019-final-verification-review/implementation-run.md`
and append each command/result as work progresses. Save long raw output under
the existing `evidence/` directory using names beginning with `fix-`.

### 1.3 Working rules

- Run all repository Python, pytest, uv, CLI, and compiler commands through
  `devenv shell -- ...`.
- Use a fresh `cache_dir=` or a temporary `PYDANTREE_SITTER_CACHE` for fixture
  regeneration; do not trust a developer cache as evidence.
- Make the smallest coherent change for each step, run its focused tests, then
  commit and push before proceeding.
- Never regenerate expected output and accept it merely because tests pass.
  Inspect the diff and explain why each changed byte is intentional.

---

## 2. Fix V4: make conflict parsing and golden fixtures genuinely CLI-free

### Goal

Only tests that execute `tree-sitter` or gcc may carry the `toolchain` marker.
The two golden conflict tests—and all other pure parsing, rendering, DSL, and
static-analysis tests in `tests/test_conflicts.py`—must run when the CLI and gcc
are absent.

### 2.1 Refactor the markers

Edit `tests/test_conflicts.py`:

1. Delete the module-level assignment:

   ```python
   pytestmark = pytest.mark.toolchain
   ```

2. Add `@pytest.mark.toolchain` only to tests that actually generate, compile,
   load, or parse a generated grammar. At the current revision those are:

   - `test_ambiguous_resolves_greedy_at_runtime`
   - `test_dangling_else_without_opt_in_conflicts`
   - `test_conflict_cites_per_production_seq_line`
   - `test_build_loop_drives_to_clean`
   - `test_build_loop_fails_after_max_attempts`
   - `test_debug_states_returns_report`
   - `test_whitespace_default_parses_spaces`

3. Leave the remaining tests unmarked. In particular, both
   `test_golden_conflict_*` tests must be unmarked.

4. Update the module docstring or section comment to state that the file mixes
   pure conflict-report tests with a small set of explicitly marked real-CLI
   integration tests.

Do not replace real CLI tests with mocks. This change is marker precision, not
a reduction in integration coverage.

### 2.2 Prove the toolchain-free contract

First run the file normally:

```bash
devenv shell -- python -m pytest tests/test_conflicts.py -q
```

Then run the two golden nodes with a PATH containing only the managed Python:

```bash
devenv shell -- env \
  PATH=/home/andrew/Documents/Projects/pydantree/.devenv/state/venv/bin \
  /home/andrew/Documents/Projects/pydantree/.devenv/state/venv/bin/python \
  -m pytest \
  tests/test_conflicts.py::test_golden_conflict_corpus_parses_without_the_cli \
  tests/test_conflicts.py::test_golden_conflicts_render_with_matching_grammar \
  -q
```

Acceptance: `2 passed`, not skipped. Also run:

```bash
devenv shell -- python -m pytest tests/test_conflicts.py -q -m 'not toolchain'
devenv shell -- python -m pytest tests/ -q -m 'not toolchain'
```

Record the new toolchain-free count. It should increase because the previous
blanket marker misclassified pure tests.

### 2.3 Commit

```bash
git add tests/test_conflicts.py
git commit -m "tests: run golden conflict guards without the toolchain"
git push origin main
```

---

## 3. Fix V5 and V6 together: make every retained community byproduct a real oracle

### Goal

The retained community `node-types.json` files must have all three properties:

1. exact upstream provenance;
2. one documented regeneration command;
3. a byte-for-byte test against a fresh tree-sitter 0.25.3 generation.

The in-scope community fixtures are:

| fixture | grammar name |
|---|---|
| `tests/fixtures/bash` | `bash` |
| `tests/fixtures/rust` | `rust` |
| `tests/fixtures/nix` | `nix` |
| `tests/fixtures/markdown` | `markdown` |
| `tests/fixtures/markdown-inline` | `markdown_inline` |

The `jsonlike*` node-type files are in-project schema-consumption fixtures,
not upstream community drift fixtures. Say this explicitly in provenance; do
not silently mix the two contracts.

### 3.1 Add one manifest shared by tests and regeneration

Add `tests/community_fixture_manifest.py` containing an immutable entry for
each of the five fixtures. Each entry should include at least:

- directory name;
- grammar/export name;
- upstream repository URL;
- exact tag and/or full 40-character commit;
- expected relative byproduct path (`node-types.json`).

Use a frozen dataclass or named tuple so the regeneration script and the test
cannot drift into separate hand-maintained lists.

Known provenance that can be carried forward:

- Nix: tag `v0.3.0`, commit prefix `ea1d87f` (resolve and record the full
  commit);
- Bash: tag `v0.25.1` (resolve the tag to its full commit);
- Rust and both Markdown grammars: identify the exact upstream commit whose
  `grammar.json`, `scanner.c`, and headers match the vendored source. Do not
  write `master`, `fixture-pinned`, or today's upstream HEAD.

Resolve tags/commits from the upstream Git repositories and compare source
bytes before recording them. If no upstream commit matches all vendored files,
document the fixture as an explicit composite and list the source commit of
each file; do not invent a single revision.

### 3.2 Add a deterministic regeneration command

Add `tests/regenerate_community_node_types.py`. It should:

1. import the shared manifest;
2. accept an optional repeated fixture selector, with all five as the default;
3. call `derive_schema_for_dir` for each committed source directory;
4. write to a temporary directory first;
5. compare generated bytes with the tracked file and print a useful unified
   diff when they differ;
6. require an explicit `--write` flag before replacing tracked fixtures;
7. use atomic replacement when writing;
8. print the CLI version and every file written/unchanged.

The supported commands should be:

```bash
# Check only; no repository mutation.
devenv shell -- python tests/regenerate_community_node_types.py

# Intentional refresh after inspecting upstream/toolchain changes.
devenv shell -- python tests/regenerate_community_node_types.py --write
```

Do not shell out to a mocked CLI and do not normalize parsed JSON. The claim is
byte-for-byte equality with the installed, supported CLI's byproduct.

### 3.3 Refresh the stale byproducts once

Run the check mode first and save its output. V5 established that at least Nix
is stale relative to the supported CLI. Then run `--write` with a fresh cache,
inspect all five diffs, and run check mode again:

```bash
PYDANTREE_SITTER_CACHE=/tmp/pydantree-review019-fixture-cache \
  devenv shell -- python tests/regenerate_community_node_types.py

PYDANTREE_SITTER_CACHE=/tmp/pydantree-review019-fixture-cache-write \
  devenv shell -- python tests/regenerate_community_node_types.py --write

git diff -- tests/fixtures/bash/node-types.json \
  tests/fixtures/rust/node-types.json \
  tests/fixtures/nix/node-types.json \
  tests/fixtures/markdown/node-types.json \
  tests/fixtures/markdown-inline/node-types.json

PYDANTREE_SITTER_CACHE=/tmp/pydantree-review019-fixture-cache-check \
  devenv shell -- python tests/regenerate_community_node_types.py
```

Expected interpretation: changed `root`/`extra` fields or other serialization
differences are current CLI output replacing stale expected output. They are
not compatibility data to preserve.

### 3.4 Add one parameterized byte-for-byte test

Add `tests/test_community_fixtures.py` (or place the test in
`tests/test_bundle.py` if that keeps imports simpler). Parameterize over the
shared manifest and, for every case:

1. generate in `tmp_path` using `derive_schema_for_dir`;
2. read the generated file as bytes;
3. read the checked-in `node-types.json` as bytes;
4. assert exact equality, with a unified textual diff on failure.

Mark each parameterized case with both:

```python
@pytest.mark.toolchain
@pytest.mark.cli_byte_for_byte
```

This ensures the test needs the real CLI and is skipped only when the CLI is
absent or outside the version range already defended by
`test_toolchain_version.py`.

Remove redundant assertions that no longer compare against the committed
fixture:

- Replace Rust's one-off byte comparison with the shared parameterized test.
- Split the current Nix test: move byte equality into the shared test, but
  retain its useful semantic shape assertions. Those shape assertions may
  load the committed fixture directly and can be toolchain-free if they no
  longer generate.
- Keep bundle/extraction tests for Bash and Markdown; they prove behavior,
  while the new test independently proves saved-file drift.

### 3.5 Complete `PROVENANCE.md`

Update `tests/fixtures/PROVENANCE.md` so every retained saved artifact has:

- repository URL;
- exact tag and full commit (or an honestly documented composite);
- acquisition date;
- source files copied;
- license;
- the exact check and refresh commands from Step 3.2;
- the supported CLI range (`0.25.x`, pinned to 0.25.3 in this repository);
- a statement that `node-types.json` is expected output, while compiled
  libraries and generated parser C files are not checked in.

Keep `tests/fixtures/nix/PROVENANCE.md`, but reconcile it with the global file
and replace the obsolete statement that a newer-CLI byproduct is the oracle.
The committed oracle must now match the supported CLI.

Add the conflict corpus to provenance. Record that the three
`tests/fixtures/conflicts/*_stderr.json` files are verbatim stderr from
tree-sitter 0.25.3, identify the minimal grammar for each, and give a concrete
regeneration command. Prefer adding
`tests/fixtures/conflicts/regenerate.py` so regeneration is executable rather
than prose-only. It must invoke the real CLI with `--json`, require `--write`
before replacing fixtures, and leave the source tree untouched in check mode.

### 3.6 Focused verification and commit

```bash
devenv shell -- python -m pytest \
  tests/test_community_fixtures.py \
  tests/test_bundle.py \
  tests/test_schema.py \
  tests/test_conflicts.py -q
devenv shell -- python tests/regenerate_community_node_types.py
git diff --check
```

Acceptance:

- all five community parameters pass byte-for-byte;
- regeneration check mode exits zero without modifying the worktree;
- Nix no longer documents or relies on a deliberately stale byproduct;
- conflict fixture provenance and regeneration are concrete;
- no `.so`, `parser.c`, or `.built/` path has been added.

Commit and push:

```bash
git add tests/community_fixture_manifest.py \
  tests/regenerate_community_node_types.py \
  tests/test_community_fixtures.py \
  tests/test_bundle.py tests/test_schema.py \
  tests/fixtures/PROVENANCE.md tests/fixtures/nix/PROVENANCE.md \
  tests/fixtures/conflicts \
  tests/fixtures/bash/node-types.json \
  tests/fixtures/rust/node-types.json \
  tests/fixtures/nix/node-types.json \
  tests/fixtures/markdown/node-types.json \
  tests/fixtures/markdown-inline/node-types.json
git commit -m "tests: verify every community node-type fixture"
git push origin main
```

Adjust the `git add` list to actual files created; inspect `git status` before
committing so nothing relevant is omitted.

---

## 4. Fix V7: strengthen source-location regression assertions

### 4.1 Assert attribute line precision, not merely the file

Edit `tests/test_rules_sites.py`.

`AUTHOR_SRC` currently places `Pair.key` and `Pair.value` on distinct known
lines. Strengthen `test_attribute_sites_are_more_precise_than_the_class_line`
to prove all of the following:

- each attribute reference has a non-null site;
- the file equals the temporary author file;
- the two attribute nodes have distinct `lineno` values;
- those lines are the actual `key: Name` and `value: Name` lines;
- neither equals the `class Pair` line;
- the recorded `source` text identifies the corresponding attribute.

Avoid hard-coded fragile line numbers by deriving a mapping from
`AUTHOR_SRC.splitlines()` before the assertion. Collect the relevant body-node
sites by their stripped `source` text or by the order of the two field nodes,
then compare to the derived mapping.

The test must fail if implementation code collapses every child site back to
the class line while retaining the correct file.

### 4.2 Require analyzer warnings to retain their site

Edit `tests/test_pipeline.py::test_build_warnings_surface`.

Replace the permissive assertion:

```python
all(w.site is None or ...)
```

with assertions over the specific precedence-mixing warning:

- find exactly one warning whose message contains `precedence`;
- assert its site is not `None`;
- assert its file is `tests/test_pipeline.py`;
- assert its line is the line that constructs the mixed named/integer
  precedence choice, not merely somewhere in the file;
- optionally assert its recorded source contains `tg.choice` or `tg.prec`.

Derive the expected line at runtime or structure the grammar snippet so its
line is unambiguous. Do not weaken the test to a range broad enough to include
the entire function.

### 4.3 Prove and commit

```bash
devenv shell -- python -m pytest tests/test_rules_sites.py -q
devenv shell -- python -m pytest \
  tests/test_pipeline.py::test_build_warnings_surface -q
```

For extra confidence, temporarily alter each expected line to the class or
function line and confirm the corresponding test fails; restore it before
commit. Record this negative check in `implementation-run.md`.

```bash
git add tests/test_rules_sites.py tests/test_pipeline.py
git commit -m "tests: require precise non-null author source sites"
git push origin main
```

---

## 5. Fix V2: make both Product A examples runnable and continuously self-checked

### Goal

The README must distinguish repository development from a standalone installed
consumer. A repository reader must get a supported `devenv` command first, and
the suite must execute each example script's real CLI entry point against a
fresh bundle.

### 5.1 Correct and reorder the documentation

Edit both:

- `examples/bash-extract/README.md` and its `extract.py` module docstring;
- `examples/devenv-extract/README.md` and its `extract.py` module docstring.

Make these changes:

1. Put the repository/developer path first:

   ```bash
   devenv shell -- python -m pytest tests/test_oracles.py -q
   ```

   Explain that this fresh-builds the Bash, Nix, and authored-subset bundles,
   runs the examples' own extraction logic, and compares saved JSON plus
   independent ground truth.

2. Give a direct in-repository script path that builds a temporary bundle from
   `tests/fixtures/bash` or `tests/fixtures/nix` with
   `build_community_bundle`, then runs:

   ```bash
   devenv shell -- python -c \
     'from pydantree_sitter_grammar.schema_tool import build_community_bundle; build_community_bundle("tests/fixtures/bash", "/tmp/pydantree-example-bash", name="bash")'
   devenv shell -- python examples/bash-extract/extract.py \
     --bundle /tmp/pydantree-example-bash

   devenv shell -- python -c \
     'from pydantree_sitter_grammar.schema_tool import build_community_bundle; build_community_bundle("tests/fixtures/nix", "/tmp/pydantree-example-nix", name="nix")'
   devenv shell -- python examples/devenv-extract/extract.py \
     --bundle /tmp/pydantree-example-nix
   ```

   Use a specific narrow `/tmp` directory. Do not mention the deleted
   `tests/oracles/.built/` directory.

3. Keep the standalone, toolchain-free community-wheel path as a separate
   section for users outside the repository. Fix the duplicate package name:

   ```bash
   uv pip install --python .venv/bin/python \
       pydantree-sitter tree-sitter-bash
   ```

   and equivalently for `tree-sitter-nix`.

4. Make clear that standalone `uv venv` / `uv pip` is consumer documentation,
   not the repository development workflow.

Also fix the duplicate `pydantree-sitter pydantree-sitter` wording in
`examples/devenv-subset/README.md`; the B-free consumer needs the single light
distribution, not two copies of its name.

### 5.2 Execute the actual scripts in the oracle suite

Refactor the session-scoped oracle fixtures in `tests/test_oracles.py` so the
fresh Bash, Nix, and subset bundle paths are available as fixtures, and language
fixtures load from those paths. Do not build a second copy merely for the
subprocess tests.

Add one subprocess test per example script. Each test should:

1. call `sys.executable` with the example's `extract.py` and `--bundle`;
2. use the already-built session bundle;
3. capture stdout/stderr;
4. assert return code zero;
5. assert the final self-check text and expected row count:
   Bash 34, Nix 102, subset 56;
6. fail with captured output in the assertion message.

This complements the in-process JSON oracle tests: the existing tests prove
exact data, while the new subprocess nodes prove that argument parsing,
loading, validation, main-loop execution, and exit status remain runnable.

If the subset script takes its bundle from `DEVENV_BUNDLE_DIR` rather than a
`--bundle` argument, pass that environment variable explicitly and preserve the
rest of the managed environment.

### 5.3 Prove and commit

```bash
devenv shell -- python -m pytest tests/test_oracles.py -q
devenv shell -- python -c \
  'from pydantree_sitter_grammar.schema_tool import build_community_bundle; build_community_bundle("tests/fixtures/bash", "/tmp/pydantree-example-bash", name="bash")'
devenv shell -- python examples/bash-extract/extract.py \
  --bundle /tmp/pydantree-example-bash
devenv shell -- python -c \
  'from pydantree_sitter_grammar.schema_tool import build_community_bundle; build_community_bundle("tests/fixtures/nix", "/tmp/pydantree-example-nix", name="nix")'
devenv shell -- python examples/devenv-extract/extract.py \
  --bundle /tmp/pydantree-example-nix
DEVENV_BUNDLE_DIR=/tmp/pydantree-example-subset \
  devenv shell -- python examples/devenv-subset/extract.py
```

The direct commands should use bundles created by the documented preceding
command. Acceptance: all scripts exit zero and state that their rows match the
hand-written ground truth.

```bash
git add examples/bash-extract/README.md examples/bash-extract/extract.py \
  examples/devenv-extract/README.md examples/devenv-extract/extract.py \
  examples/devenv-subset/README.md tests/test_oracles.py
git commit -m "examples: verify the supported fresh-bundle run path"
git push origin main
```

---

## 6. Fix V3: make first-run dependency sync reliable in a fresh worktree

### Goal

A new worktree's own `.devenv/state/venv/bin/python` must import the locked
dependencies on its first `devenv shell` entry. A cached success record for
`devenv:python:uv` must not allow an empty new venv to masquerade as synced.

### 6.1 Reproduce before changing configuration

From a clean committed tree, create a detached temporary worktree. Use an
explicit temporary path and remove it through Git afterward:

```bash
WORKTREE_PARENT=$(mktemp -d /tmp/pydantree-v3.XXXXXX)
git worktree add --detach "$WORKTREE_PARENT/repo" HEAD
cd "$WORKTREE_PARENT/repo"
devenv shell -- python -c \
  'import pydantic, pytest, tree_sitter; print("fresh-worktree imports ok")'
cd /home/andrew/Documents/Projects/pydantree
git worktree remove "$WORKTREE_PARENT/repo"
rmdir "$WORKTREE_PARENT"
```

Save the pre-fix result. Do not reuse the Review 019 temporary worktree or the
primary repository's venv.

### 6.2 Add a post-sync validity guard

Keep Devenv's managed uv workflow, but add a repository task in `devenv.nix`
after `devenv:python:uv` and before `pydantree:venv-src-pth` that validates the
actual venv at `${config.env.DEVENV_STATE}/venv`.

Recommended behavior:

1. invoke that venv's Python to import at least `pydantic`, `pytest`, and
   `tree_sitter`;
2. if imports succeed, exit immediately;
3. if they fail, run the same locked synchronization explicitly against that
   exact venv:

   ```bash
   UV_PROJECT_ENVIRONMENT="${config.env.DEVENV_STATE}/venv" \
     uv sync --all-extras --frozen --no-install-workspace
   ```

4. rerun the import check and fail the shell entry if it is still broken;
5. make `pydantree:venv-src-pth` depend on this guard rather than directly on
   `devenv:python:uv`.

Use a project-specific task name such as `pydantree:ensure-uv-sync`. Do not
repurpose `HOME`, change the lockfile, install with pip, or silently ignore a
failed sync. Keep the existing src-first `.pth` task.

If investigation shows the cached task can be made path-sensitive directly in
the pinned Devenv configuration, that is preferable to the fallback guard—but
the final behavior must still be verified by the detached-worktree test above.
Do not run `devenv update` merely to make V3 disappear; a lock update is a
separate toolchain change requiring its own review.

### 6.3 Verify the actual clean-first-run path

First verify the edited configuration in the primary worktree, update
`docs/development.md`, and create the V3 commit. A second worktree created from
`HEAD` cannot see uncommitted changes, so the commit must exist before the
clean-worktree proof:

```bash
devenv shell -- python -c \
  'import pydantic, pytest, tree_sitter; print("primary imports ok")'
git diff --check
git add devenv.nix docs/development.md
git commit -m "dev: guarantee uv sync in fresh worktrees"
```

Now repeat Step 6.1 with a brand-new temporary parent created from that commit.
Then run, inside that fresh worktree:

```bash
devenv shell -- python -m pytest tests/test_oracles.py -q
```

Acceptance:

- the first shell entry imports dependencies;
- the oracle suite passes in the new worktree;
- a second shell entry is fast and still imports correctly;
- the task output does not claim success before the venv is usable;
- `uv.lock` is unchanged.

If the proof fails, fix the configuration in the primary worktree, commit the
follow-up, and create another entirely new worktree from the new `HEAD`. Do not
reuse a partially initialized `.devenv` directory as proof.

After the proof passes, return to the primary repository and push:

```bash
git diff --check
git push origin main
```

Update `docs/development.md` with the guard's purpose and the clean-worktree
smoke command so future maintainers do not remove it as redundant.

---

## 7. Re-run the complete verification matrix

Run all focused contracts first:

```bash
devenv shell -- python -m pytest tests/test_conflicts.py -q
devenv shell -- python -m pytest tests/test_community_fixtures.py -q
devenv shell -- python -m pytest tests/test_rules_sites.py -q
devenv shell -- python -m pytest tests/test_pipeline.py -q
devenv shell -- python -m pytest tests/test_oracles.py -q
devenv shell -- python -m pytest tests/test_bundle.py tests/test_schema.py -q
```

Run the toolchain-free selection and record its new count:

```bash
devenv shell -- python -m pytest tests/ -q -m 'not toolchain'
```

Run the full suite twice without randomized plugin behavior:

```bash
devenv shell -- python -m pytest tests/ -q -p no:randomly
devenv shell -- python -m pytest tests/ -q -p no:randomly
```

Run the saved-output check independently of pytest:

```bash
devenv shell -- python tests/regenerate_community_node_types.py
devenv shell -- python tests/test_oracles.py --generate
git diff --exit-code -- tests/oracles tests/fixtures
```

The oracle command intentionally writes its tracked JSON; a zero diff proves
stability. If it changes anything, inspect and resolve the drift rather than
resetting it without explanation.

Finally:

```bash
git diff --check
git status --short --branch
git rev-list --left-right --count main...origin/main
```

Acceptance matrix:

| finding | closure evidence |
|---|---|
| V1 | `.built/` absent; JSON-only policy remains; no native fixtures tracked |
| V2 | READMEs give supported dev commands; three script-entry subprocess tests pass |
| V3 | brand-new detached worktree imports dependencies and runs oracle tests on first entry |
| V4 | golden conflict nodes pass with CLI/gcc absent; only seven real integration nodes stay marked |
| V5 | all five community node-type fixtures regenerate byte-for-byte |
| V6 | exact commits, licenses, acquisition details, and executable regeneration documented |
| V7 | tests fail if attribute/warning sites become null or collapse to broader lines |

Do not declare closure if any full-run test skips unexpectedly with the pinned
toolchain present.

---

## 8. Record closure, commit, and push

### 8.1 Documentation

Append a concise V2–V7 resolution section to
`.scratch/projects/019-final-verification-review/RESOLUTION.md`. Link to the
tests and commands, but keep the original V1 resolution intact.

Complete `implementation-run.md` with:

- starting and ending commit;
- exact toolchain versions;
- focused test results;
- toolchain-free count;
- both full-suite counts/timings;
- fresh-worktree result;
- regeneration no-diff result;
- every commit created for the work.

Update `docs/development.md` only where the durable workflow changed: community
fixture regeneration and the fresh-worktree dependency guard.

### 8.2 Final commit

```bash
git status --short
git diff --check
git add .scratch/projects/019-final-verification-review/RESOLUTION.md \
  .scratch/projects/019-final-verification-review/implementation-run.md \
  docs/development.md
git commit -m "review019: close verification findings V2 through V7"
git push origin main
git status --short --branch
git rev-list --left-right --count main...origin/main
```

The terminal state is a clean `main`, `0 0` ahead/behind, all tests green,
all five retained community byproducts asserted, CLI-free golden tests really
CLI-free, and no generated native compatibility fixtures in the repository.

---

## 9. Explicit non-goals and traps

- Do not restore or regenerate `tests/oracles/.built/`.
- Do not promise that bundle format 1 or old native binaries will continue to
  load. Existing loader behavior may remain, but it is not the oracle contract.
- Do not normalize JSON before comparing community byproducts; V5 is about the
  saved file's exact bytes.
- Do not mark an entire mixed test module as `toolchain` for convenience.
- Do not make fixture refresh implicit during pytest. Tests compare; the
  explicit `--write` command refreshes.
- Do not fetch upstream HEAD and call it the fixture's provenance. Match the
  checked-in source to an exact revision first.
- Do not fix V3 with pip, an editable install, or an unpinned sync.
- Do not change `devenv.lock` unless dependency/toolchain changes are explicitly
  intended and separately justified.
- Do not update historical review findings to pretend the gaps never existed;
  preserve the audit trail and add resolution evidence.
