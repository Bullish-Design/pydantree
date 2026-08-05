# bash-extract — typed extraction from real shell scripts

A copyable end-to-end for **Product A** (pydantree_sitter) over the **real
tree-sitter-bash grammar (0.25.1)** — a grammar we don't own and never
authored. Three extraction tasks over real shell scripts, as **typed rows**,
with the schema checks active **before any text is parsed**:

| task | model | what it shows |
|---|---|---|
| function definitions | `FunctionDef` | both `foo() { … }` and `function foo { … }` (same node kind), the `name` field + line |
| top-level assignments | `Assignment` | `VAR=value` at the top level only — the direct-child path excludes `export VAR=…` and function bodies; `value` is the raw node text |
| heredoc usage | `Heredoc` | `<<EOF`, `<<-EOF`, `<<'EOF'`, `3<<EOF` and the unclosed-at-EOF case: delimiter (`capture_kind`), body, closing delimiter, optional descriptor |

## Run it — inside the repository (the supported developer path)

The suite builds the grammar fresh from the vendored source
(`tests/fixtures/bash`, exact upstream commit `a06c2e44`) through the
current pipeline, runs this example's own extraction logic, and compares
both the saved oracle JSON and the example's independent hand-written ground
truth:

```bash
devenv shell -- python -m pytest tests/test_oracles.py -q
```

Or run the script directly against a bundle you build yourself (B available,
grammar source from `tests/fixtures/bash`):

```bash
devenv shell -- python -c \
  'from pydantree_sitter_grammar.schema_tool import build_community_bundle; build_community_bundle("tests/fixtures/bash", "/tmp/pydantree-example-bash", name="bash")'
devenv shell -- python examples/bash-extract/extract.py \
  --bundle /tmp/pydantree-example-bash
```

The example is self-checking: `extract.py` verifies its rows against the
hand-written ground truth in `ground_truth.json` (written from bash's
semantics, before the models) and exits 0 only on a match.

## Run it — standalone (the "hundreds of grammars" shape, no toolchain)

This is **consumer documentation for a user outside the repository**, not
the repository development workflow (in-repo work is managed by devenv and
forbids manual installs). In a fresh venv with only the light wheels plus
the community wheel, `import pydantree_sitter_grammar` is impossible and the
extraction still runs — the full checked A surface over a grammar shipped as
a PyPI wheel, with the schema derived from the grammar source
(`node-schema.json`, v0.25.1 — derived once by the schema tool and checked
in here, byte-for-byte with the CLI's own node-types.json).

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python \
    pydantree-sitter tree-sitter-bash
.venv/bin/python extract.py
```

## The corpus

- `sample.sh` — hand-authored: both function forms, plain/`export`/
  function-local assignments, three heredoc forms (`<<`, `<<-`, `<<'…'`).
- `real_script.sh` — a verbatim excerpt of **llama-infernal's
  `build-xcframework.sh`** (Bullish-Design/llama-infernal, MIT — the ggml
  authors): 19 top-level options, `check_required_tool()`, a
  module.modulemap heredoc.
- `unclosed.sh` — an unclosed heredoc (bash is lenient at EOF): the grammar
  emits a *missing* `heredoc_end`, so `end` is `""` (not `None`).

## What the A surface needed over bash (and what it didn't)

- **`capture_kind` was required** — `heredoc_redirect`'s delimiter/body/end
  are positional children, not CST fields (heredocs were the reason this
  surface exists, in the markdown phase — bash is a second, different
  grammar needing it).
- **`str | None` optional captures** — `descriptor` (absent for `<<EOF`) and
  `heredoc_end` (missing at EOF).
- **Field order matters** when mixing a field with positional children:
  `descriptor` precedes the heredoc trio in the CST, so it comes first in
  the model. A wrong order is an "Impossible pattern" QueryError.
- **Record mode did NOT fit** — bash's top level is a statement list with no
  key/value container node (record mode fits config-file grammars like the
  cfg bundle, not bash's shape).
- **`lang.name` is `None`** for a capsule-loaded bundle (the wheel shape
  reports `"bash"`; the bundle shape does not — a known residual, harmless
  here).

## Shape notes

- `value` keeps the quotes for string assignments (`"/usr/local"`) — bash
  keeps them in the CST; strip them in a model property if you want the
  unquoted form.
- `start` keeps the quotes for `<<'TAG'` (`'TAG'`); `end` is always the
  clean word (`TAG`).
- `body` includes the trailing newline (the delimiter line is not part of
  the body).
- Multi-heredoc-on-one-command-line (`cat <<A <<B`) parses with an ERROR in
  the real grammar (a real upstream limitation — the scanner keeps a queue,
  but the grammar's redirect chain can't chain two heredoc redirects).
