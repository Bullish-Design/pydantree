# bash-extract — typed extraction from real shell scripts

A copyable end-to-end for **Product A** (tsquery) over the **real
tree-sitter-bash grammar (0.25.1)** — a grammar we don't own and never
authored. Three extraction tasks over real shell scripts, as **typed rows**,
with the schema checks active **before any text is parsed**:

| task | model | what it shows |
|---|---|---|
| function definitions | `FunctionDef` | both `foo() { … }` and `function foo { … }` (same node kind), the `name` field + line |
| top-level assignments | `Assignment` | `VAR=value` at the top level only — the direct-child path excludes `export VAR=…` and function bodies; `value` is the raw node text |
| heredoc usage | `Heredoc` | `<<EOF`, `<<-EOF`, `<<'EOF'`, `3<<EOF` and the unclosed-at-EOF case: delimiter (`capture_kind`), body, closing delimiter, optional descriptor |

## Run it (the "hundreds of grammars" shape — no toolchain anywhere)

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python \
    pydantree-tscore pydantree-tsquery tree-sitter-bash
.venv/bin/python extract.py
```

That's it: the light wheels + the community wheel. `import tsgrammar` is
impossible in this venv (the light install does not ship B) and the
extraction still runs — the full checked A surface over a grammar shipped
as a PyPI wheel, with the schema derived from the grammar source
(`node-schema.json`, v0.25.1 — derived once by the schema tool and checked
in here, byte-for-byte with the CLI's own node-types.json).

The example is self-checking: `extract.py` verifies its rows against the
hand-written ground truth in `ground_truth.json` (written from bash's
semantics, before the models) and exits 0 only on a match.

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
