# devenv-extract — the devenv fleet inventory with pydantree

A copyable end-to-end for **Product A** (tsquery) over the **real
tree-sitter-nix grammar** (`nix-community/tree-sitter-nix` — a grammar we
don't own and never authored). The corpus is a subset of the author's OWN
real `devenv.nix` configs (7 repos, 8–526 lines), and the extraction task is
the **devenv fleet inventory** — packages, env vars, scripts, tasks, enabled
switches, enterShell/enterTest — as typed rows, aggregated per repo, with the
schema checks active **before any text is parsed**.

| task | what it extracts | example row |
|---|---|---|
| packages | every package ref inside a `packages = [ ... ]` list (raw text: `pkgs.git`, bare `tmux` under `with pkgs;`, `nodePackages.X`) | `pkgs.tailscale` (flora:51) |
| env | every `env.NAME = value` (raw value text — quotes kept) | `env.GREET = '"devenv"'` (pydantree:5) |
| scripts / tasks | every `scripts.<name>.exec` / `tasks.<name>.exec` multiline body (raw `''…''` text kept) | `tasks."pydantree:venv-src-pth".exec` (pydantree:59) |
| switches | every dotted path ending `.enable = true` (full path reconstructed from the attrset nesting) | `languages.python.uv.sync.enable` (pydantree:26) |
| shells | `enterShell` / `enterTest` multiline bodies | pydantree:70 / :76 |

## Run it (the "hundreds of grammars" shape — no toolchain anywhere)

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python \
    pydantree-tscore pydantree-tsquery tree-sitter-nix
.venv/bin/python extract.py
```

That's it: the light wheels + the community wheel. `import tsgrammar` is
impossible in this venv (the light install does not ship B) and the
extraction still runs — the full checked A surface over a grammar shipped as
a PyPI wheel, with the schema derived from the grammar source
(`node-schema.json`, v0.3.0 — derived once by the schema tool and checked in
here). The example is self-checking: it verifies its 102 rows against the
hand-written ground truth (`fleet/ground_truth.json`, written from nix
semantics before the models) and exits 0 only on a match.

Over a pydantree bundle (the dev flow, B available):

```bash
python extract.py --bundle <bundle-dir>     # build_community_bundle output
```

## The corpus

`fleet/` — a representative subset of the user's 52-repo fleet of real
`devenv.nix` files: `mypi-agent` (8 lines), `pydantree` (85 — its task nests
a bash heredoc inside a nix `''…''` string), `terminal-state` (192),
`structured-agents-v2` (221), `nixvim` (240), `fsdantic` (250). Provenance
(repo + commit per file) and the one sanitization (the `/home/andrew` paths
in two files → `/home/nixuser`, same shape) are in
`../../tests/fixtures/nix/fleet/FLEET_PROVENANCE.md`; the corpus here is the
same subset, self-contained for copying.

**flora (526 lines, the fleet's largest config) is deliberately NOT in the
example** — parsing it through the tree-sitter 0.26 runtime triggers the
position corruption below (the extraction content still works; reading node
start points or the interpreter teardown can crash). The full seven-file
extraction (with the byte-offset line workaround) is the Run-3 evidence in
`.scratch/011-nix-example/`, and `fleet/ground_truth.json` here is the
six-repo subset of the same hand truth (102 rows; the full 130-row truth
lives in the tests fixture).

## What the A surface needed over nix (and what it didn't)

- **Two generic models** do the extraction: `Binding` (every
  `attrpath = expression;` binding — the value's raw text + source_meta) and
  `List` (every list literal — the repeated `element` field as a field-mode
  list). Both use descendant matching (`M("source_code", ..., "binding")`) and
  `validate_with` runs the model↔grammar + capture↔type checks before
  parsing.
- **The binding's ATTRPATH is NOT str-capturable** — nix's attrpath node is
  structural (a chain of identifiers + dots), and Job 4 rejects capturing a
  non-text-yielding node as str (the "no raw text of any node" residual from
  the bash phase). The key becomes a small consumer-side walk.
- **Full dotted paths are reconstructed by walking ancestor bindings**
  (`dotted_path`): `venv.enable` inside `languages.python` is
  `languages.python.venv.enable` — attrset nesting is context, not a
  capture. A single top-level `config = { … }` wrapper (the nixvim/flora
  module convention) is stripped.
- **Record mode did NOT fit** — nix's `{ key = value; }` attrset is the
  record shape's natural candidate, but the record machinery's pair-kind
  detection looks for a child kind with `key`/`value` fields (the JSON pair
  shape); nix's `binding_set` carries a `binding` FIELD with
  `attrpath`/`expression` — `UnsupportedShapeError`. The machinery would
  need a "binding-shaped pair" parameterization.
- **`capture_kind` / optional captures / predicates: not needed** — nix's
  bindings are field-shaped, so the field surface sufficed.

## Position caveat (a real ecosystem finding)

The nix grammar under the **tree-sitter 0.26 runtime** has a position bug:
on large multiline-string-heavy files (flora, 526 lines), reading a node's
start POINT (`start_point`, `node.range`) returns garbage rows or segfaults
— reproduced with the upstream wheel AND a from-source build (flora: 30/30
SIGSEGV on a full start_point walk; the tree-sitter CLI 0.25.3 runtime parses
the same file with correct positions). Node start BYTES and texts are always
reliable. This example therefore computes every line from the byte offset
(`src[:start_byte].count(b"\n") + 1`) and keeps `source_meta` in the models
as a cross-check: on the six stable files the two agree; on flora 22/55
bindings disagree (the corruption). The full evidence is in
`../../.scratch/011-nix-example/evidence/r9_r3_*`.

## Shape notes

- env values keep their quotes (`'"devenv"'`); `lib.mkDefault (...)` and
  `++` values are captured whole.
- script/task/enterShell bodies are the raw `''…''` node text (delimiters
  kept, indentation as written — nix strips the common indent at eval; the
  raw text is the capture contract). A `.strip()` in a model property gives
  the cleaner form.
- `tasks."name".exec` string attrs keep their quotes in the dotted path.
- `packages` rows are the refs as written (`pkgs.git`, bare `tmux`,
  `nodePackages.typescript-language-server`); `++`-appended expressions
  (e.g. `lib.optional … llamaCpp`) are not list elements, so they don't
  appear.
- The `tree-sitter-nix` wheel's `language()` returns a bare PyCapsule (it
  was built against an older binding API) — tsquery converts it internally;
  the raw-bindings path needs `tree_sitter.Language(capsule)`.
