# tests/fixtures/nix — provenance

The Nix language grammar is **consumed, not authored** (Phase 9, the
real-world Nix adoption pass — see `.scratch/011-nix-example/`).

| file | source | version |
|---|---|---|
| `grammar.json` | `nix-community/tree-sitter-nix` `src/grammar.json` | tag **v0.3.0** (commit `ea1d87f` "Release v0.3.0 (#147)") |
| `scanner.c` | `nix-community/tree-sitter-nix` `src/scanner.c` | tag **v0.3.0** (unchanged since `ef6443e`, 2023-07-08) |
| `tree_sitter/parser.h` | `nix-community/tree-sitter-nix` `src/tree_sitter/` | tag **v0.3.0** |
| `node-types.json` | `nix-community/tree-sitter-nix` `src/node-types.json` (the repo's checked-in byproduct) | tag **v0.3.0** — the **oracle** for the schema agreement check |

- Repo: <https://github.com/nix-community/tree-sitter-nix> — MIT, maintainer
  @cstrahan, actively maintained (v0.3.0 released 2025-07-18).
- The compiled `parser.c` is NOT vendored (it is the build byproduct, not
  the source — same policy as `tests/fixtures/bash/` and
  `tests/fixtures/rust/`).
- **Wheel-consistency note (resolved in Run 1 of the Phase-9 kickoff):**
  the PyPI wheel `tree-sitter-nix` 0.1.0 (uploaded 2025-02-20) was built
  from a source state where the grammar.json last changed at commit
  `04e5dca` (2022-09-07) and the scanner.c at `ef6443e` (2023-07-08) — the
  grammar source was **frozen between 2022-09-07 and 2025-07-16**. The only
  grammar.json delta between the wheel era and v0.3.0 is the
  trailing-comma-in-formals fix (`bae4c4f` "#131", 2025-07-16): v0.3.0
  allows a trailing comma WITHOUT ellipses in function formals; the wheel
  requires the comma to pair with ellipses. The wheel's scanner.c is
  byte-identical to v0.3.0's. So the v0.3.0-derived schema is truthful for
  the wheel except for that one grammar rule — see
  `.scratch/011-nix-example/FINDINGS.md` for the parse-probe verdict.
