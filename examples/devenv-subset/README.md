# devenv-subset — BOTH halves of pydantree, end to end

This example does what neither half alone can: **Product B (tsgrammar)
authors a small grammar for the "devenv config surface" — the shapes real
`devenv.nix` files actually use — and builds it into a bundle; Product A
(tsquery) consumes that bundle as typed rows, with record mode working and
position-correct lines.** The corpus is four of the author's own sanitized
`devenv.nix` configs (8–221 lines), the same ones the `../devenv-extract/`
example consumed through the upstream tree-sitter-nix grammar.

## Run it

```bash
devenv shell -- python examples/devenv-subset/extract.py
```

One script, both halves:

1. **B — author + build.** `grammar.py` (the DSL) + `scanner.c` (a ~40-line
   external scanner for the string fragments) → `build_builder` →
   `dist/devenv-bundle` (grammar.so + node-schema.json + metadata + loader).
   The author-time checks run (`tg.run_checks`) before the Rust CLI.
2. **A — consume.** The bundle loads with `Language.load_bundle`, the models
   validate against the schema (`validate_with` — Jobs 1/3/4 before any text
   is parsed), and the extraction prints typed rows per config.

The B-free shape is the same bundle: copy `dist/devenv-bundle` next to a
consumer that only installs the light wheels
(`pydantree-tscore pydantree-tsquery`) — `import tsgrammar` is impossible
there and the extraction still runs (the same separation `../devenv-extract/`
demonstrates over the community wheel).

## What the authored shape fixes (the Phase-9 findings, resolved here)

The upstream `tree-sitter-nix` grammar is *consumed* by `../devenv-extract/`;
this example *authors* a subset grammar, and the authorship is exactly what
makes three Phase-9 findings go away:

| Phase-9 finding | upstream nix | this authored grammar |
|---|---|---|
| **record mode doesn't fit the attrset** | `binding_set` carries a `binding` FIELD with `attrpath`/`expression` — the record machinery's pair-kind detection (a child kind with `key`/`value` fields) raises `UnsupportedShapeError` | the pair is a direct child KIND with `key`/`value` FIELDS — record mode works (`EnvRecord`, `Toolchain`) |
| **the binding key is not str-capturable** | the attrpath is a structural chain of identifiers — `key: str = capture("key")` is rejected by Job 4 | the key is ONE token (`env.GREET`, `tasks."quoted".exec`) — a text-yielding leaf — the capture passes |
| **positions corrupt on large files** | the 7.6 KB scanner triggers a tree-sitter 0.26 start-point corruption (flora 526 lines: garbage lines / SIGSEGV) — the consumer needed a byte-offset line workaround | the ~40-line scanner is position-stable — `source_meta` lines are correct, no workaround |

Two things stay context (honestly documented, same as Phase 9): the FULL
dotted path of a nested binding (`venv.enable` inside `languages.python`
→ `languages.python.venv.enable`) is the attrset nesting, which is an
ancestor walk, not a capture; and the "is this list under a `packages =`"
test for the packages task is the same walk.

## The grammar surface

`{ pkgs, lib, config, ... }:` headers · attrsets with dotted/string keys ·
`"..."` strings with `${...}` interpolation · `''...''` multiline strings
with `''${...}` escapes (the `''${` is literal text to the bash that runs
inside — the raw string text keeps it) · lists · `with pkgs; [...]` ·
`true`/`false` · numbers · `./path` literals · comments. No `let...in`, no
binary operators, no apply — the surface the configs actually use, small
enough to build in seconds and be position-stable. The corpus:

| fixture | lines | the interesting shapes |
|---|---|---|
| `fixtures/mypi-agent.nix` | 8 | the tiny case; `imports = [ ./modules/... ]`, `pkgs.secretspec` |
| `fixtures/pydantree.nix` | 85 | dotted paths (`languages.python.uv.sync.enable`), quoted task keys (`tasks."pydantree:venv-src-pth"`), a bash heredoc nested inside a nix `''…''` string |
| `fixtures/terminal-state.nix` | 192 | `packages = with pkgs; [ … ]`, the nested `env = { … }` attrset (the record-mode demo), a 1252-char `enterShell` |
| `fixtures/structured-agents-v2.nix` | 221 | bash-in-nix: `''${...}` escapes, `${pkgs.bash}` interpolations, backslash continuations, single quotes |

## Shape notes

- env values keep their quotes (`'"devenv"'`); script/task/enterShell bodies
  are the raw `''…''` node text (delimiters kept — the raw-text capture
  contract, same as `../devenv-extract/`).
- `true`/`false` are identifier tokens — the `enable = true` switch filter
  compares the raw value text; record-mode bool fields would need
  authored `true`/`false` kinds (a one-line change — the kind-name boolean
  inference).
- record-mode fields with a REQUIRED key filter the record: only attrsets
  containing that key materialize (`EnvRecord` needs `GREET`; `Toolchain`
  needs `enable` — every `{ enable = … }` container across the fleet, with
  `version` showing which are python toolchains).
- The scanner refuses an unterminated string at EOF (strict — no silent
  swallowing), and refuses to produce a fragment when BOTH fragments are
  valid (the error-recovery state — the upstream scanner's note).

## Files

```
grammar.py        B — the DSL grammar (build())
scanner.c         B — the external scanner (string/indented-string fragments)
extract.py        B + A — build the bundle, extract the inventory + records,
                  self-check vs ground_truth.json
fixtures/         the sanitized real configs (provenance: tests/fixtures/nix/
                  fleet/FLEET_PROVENANCE.md — mypi-agent, pydantree,
                  terminal-state, structured-agents-v2)
ground_truth.json the hand truth (56 rows), written from nix semantics
                  before the models
```
