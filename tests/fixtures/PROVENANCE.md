# tests/fixtures — provenance (014 Phase 7.6)

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

## rust / nix / markdown / markdown-inline — real community grammars (consumed, not authored)

| dir | source | version | license |
|---|---|---|---|
| `rust/` | `tree-sitter/tree-sitter-rust` | master (fixtures pinned to CLI 0.25.3's byproduct) | MIT |
| `nix/` | `nix-community/tree-sitter-nix` | tag v0.3.0 (commit `ea1d87f`) | MIT |
| `markdown/` | `tree-sitter-grammars/tree-sitter-markdown` (block) | fixture-pinned | MIT |
| `markdown-inline/` | `tree-sitter-grammars/tree-sitter-markdown` (inline) | fixture-pinned | MIT |

The `node-types.json` files in these dirs are the CLI's own generate byproduct
(the schema IS the byproduct by construction, D3) — the vendored copies are
the drift-detection fixtures. `nix/` has its own `PROVENANCE.md` (kept); the
bash grammar's source fixtures live under `grammars/community-bash/` and the
`tests/fixtures/bash/` dir (v0.25.1).

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
were captured from are recorded in the project history (the `.scratch`
dirs keep their copies as historical evidence).
