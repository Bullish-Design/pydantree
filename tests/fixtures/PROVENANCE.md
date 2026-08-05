# tests/fixtures — provenance

Every retained saved artifact below has: an exact upstream source (full
commit), the acquisition date, the files copied, the license, and a concrete
regeneration command. The supported tree-sitter CLI range is **0.25.x,
pinned to 0.25.3 in this repository** (`devenv.lock`); the drift guard is
`tests/test_toolchain_version.py`.

## grammars/ — the mini-grammars the suite stands on (promoted from .scratch)

| file | source | notes |
|---|---|---|
| `json_grammar.py` | authored in-project (006-query-bridge) | the JSON grammar used by A's record-mode tests; the A-side model surface |
| `cfg_grammar.py` | authored in-project (006-query-bridge) | the config grammar (directive/section) used by the schema-check tests |
| `qfilter.py` | authored in-project (005-grammar-glr) | the GLR expression grammar for the corpus harness |
| `qfilter_corpus.py` | authored in-project (007-query-distribution) | the corpus cases for qfilter |
| `pymini.py` | authored in-project (007-query-distribution) | scanner test grammar (indent scanner) |
| `hmini.py` | authored in-project (008-consumer-seam) | scanner test grammar (heredoc scanner) |
| `dmini.py` | authored in-project (008-consumer-seam) | scanner test grammar (matched-delimiter scanner) |
| `pyindent.py` | authored in-project (009-phase7) | scanner test grammar (python indent scanner) |
| `bashmini.py` | authored in-project (009-phase7) | scanner test grammar (bash heredoc scanner) |
| `reference-grammar.json` | captured from the Phase-2 experiment (004-grammar) | a large reference grammar for the IR round-trip tests |
| `community-bash/grammar.json` | `tree-sitter/tree-sitter-bash` v0.25.1 | the community grammar source used by the IR semantic round-trip test |

## bash / rust / nix / markdown / markdown-inline — real community grammars (consumed, not authored)

These five dirs are the retained **community drift oracles**: their
`node-types.json` is EXPECTED OUTPUT — the installed tree-sitter CLI's own
generate byproduct for the vendored grammar source (the schema IS the
byproduct by construction, D3). A byte-for-byte drift guard
(`tests/test_community_fixtures.py`, parameterized over the single shared
manifest `tests/community_fixture_manifest.py`) regenerates each fixture
fresh through the current pipeline and compares it to the checked-in file.
Refresh happens ONLY through the explicit command:

```bash
# Check only; exits non-zero on drift, never mutates the worktree.
devenv shell -- python tests/regenerate_community_node_types.py
# Intentional refresh after inspecting upstream/toolchain changes.
devenv shell -- python tests/regenerate_community_node_types.py --write
```

The manifest records the exact upstream commit whose source files match the
vendored bytes (verified, not assumed): grammar.json, scanner.c, and the
`tree_sitter/` headers. Compiled libraries and generated parser C files are
NOT checked in anywhere in this repository.

| dir | grammar name | upstream repo | exact commit | commit date / subject | acquired |
|---|---|---|---|---|---|
| `bash/` | `bash` | https://github.com/tree-sitter/tree-sitter-bash | `a06c2e4415e9bc0346c6b86d401879ffb44058f7` (tag `v0.25.1`) | 2025-12-02 "Regenerate parser for 0.25.1" | 2026-08-04 |
| `rust/` | `rust` | https://github.com/tree-sitter/tree-sitter-rust | `b3e615de069beb04ff44f65ac52f7f03cff04438` | 2026-03-27 "Fix bad error recovery when parsing repeated string literals (#307)" | 2026-08-02 |
| `nix/` | `nix` | https://github.com/nix-community/tree-sitter-nix | `ea1d87f7996be1329ef6555dcacfa63a69bd55c6` (tag `v0.3.0`) | 2025-07-18 "Release v0.3.0 (#147)" | 2026-08-04 |
| `markdown/` | `markdown` | https://github.com/tree-sitter-grammars/tree-sitter-markdown | `808e105aff82bc7cbc1587384dab71151b62182f` | 2026-02-26 "chore: regenerate parser and bindings with 0.26.6" | 2026-08-03 |
| `markdown-inline/` | `markdown_inline` | https://github.com/tree-sitter-grammars/tree-sitter-markdown | `808e105aff82bc7cbc1587384dab71151b62182f` | 2026-02-26 "chore: regenerate parser and bindings with 0.26.6" | 2026-08-03 |

Per-fixture notes:

- `bash/`: `grammar.json`, `scanner.c`, and all three `tree_sitter/` headers
  are byte-identical to tag `v0.25.1` (verified). MIT.
- `rust/`: the vendored `src/grammar.json`, `src/scanner.c`, and
  `src/tree_sitter/` headers are byte-identical to commit
  `b3e615de` (verified by blob-id comparison across history; there is no
  tag at that commit — it is a plain `main` commit). MIT.
- `nix/`: `grammar.json`, `scanner.c`, `tree_sitter/parser.h` are
  byte-identical to tag `v0.3.0` (verified). See `nix/PROVENANCE.md` for
  the fleet corpus and wheel-consistency notes. MIT.
- `markdown/` and `markdown-inline/`: the vendored sources are
  byte-identical to the single upstream commit `808e105a` (both grammars
  live in the `tree-sitter-markdown` monorepo, in the
  `tree-sitter-markdown/` and `tree-sitter-markdown-inline/` subdirs;
  verified by blob-id comparison across history). MIT.

The `jsonlike*` node-type files are **not** in the community contract: they
are in-project schema-consumption fixtures (the serialized-form round-trip
and shape helpers), authored in-repo, not upstream community byproducts.
Do not mix the two contracts.

## conflicts/ — the golden conflict-report corpus (REVIEW 018 §4.2/B7)

The three `conflicts/*_stderr.json` files are VERBATIM conflict reports the
real tree-sitter CLI (0.25.3) emitted on stderr under `--json` for three
minimal grammars. They are parsed and rendered by `tests/test_conflicts.py`
WITHOUT invoking the CLI — the structural drift guard for the conflict
parser/remapper. Acquisition: 2026-08-05 (Review 018 step 4, commit
`634d1da`). License: n/a (generated output, no upstream code).

| file | minimal grammar | report |
|---|---|---|
| `shift_reduce_stderr.json` | `expr -> expr '+' expr \| number` (no precedence) | shift/reduce on `'+'` |
| `dangling_else_stderr.json` | `if_stmt` / `if_else` over `stmt` | classic dangling-else, lookahead `'else'` |
| `reduce_reduce_stderr.json` | `a -> 'x'; b -> 'x'; s -> a \| b` | reduce/reduce on `'x'` |

Regeneration is executable, not prose:

```bash
# Check only; exits non-zero on drift, never mutates the worktree.
devenv shell -- python tests/fixtures/conflicts/regenerate.py
# Intentional refresh (supported CLI 0.25.x only).
devenv shell -- python tests/fixtures/conflicts/regenerate.py --write
```

The regenerator rebuilds each minimal grammar with the authoring DSL, runs
the real CLI with `--json`, and compares the stderr report byte-for-byte.

## bfree/ — the B-free subprocess machinery (promoted from 007-query-distribution)

`bfree.py` + `consumer_env/` run consumer scripts in a separate interpreter
where the heavy package is genuinely unimportable — the install-boundary
tests. The consumers themselves live in `consumers/`.

## consumers/ — the B-free consumer scripts (promoted from .scratch)

| file | source | task |
|---|---|---|
| `consumer.py` | 007-query-distribution | the cfg-bundle B-free round-trip |
| `consumer_community.py` | 007-query-distribution | the wheel + derived-schema B-free consumer |
| `consumer_rust.py` | 008-consumer-seam | rust bundle B-free extraction |
| `consumer_markdown.py` | 008-consumer-seam | markdown bundle B-free extraction |
| `consumer_bash.py` | 010-bash-user | bash bundle/wheel B-free extraction |
| `consumer_nix.py` | 011-nix-example | nix bundle/wheel B-free fleet extraction |

## evidence/ — recorded real-CLI artifacts (promoted from 004-grammar)

`b5_conflict_gap_stderr.json` — a verbatim conflict report captured from the
real CLI in Experiment B (the conflict-remap test's input).

All files retain their upstream licenses (MIT); the upstream checkouts they
were captured from are recorded above with exact commits. The `.scratch`
dirs keep their copies as historical evidence.
