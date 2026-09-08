# AGENTS.md — project instructions

> **Seed.** The `my-ai` personal layer wrote this file because this repo had
> none. It is now **the repo's** file: edit it freely, and no `my-ai` update will
> ever overwrite it (`_skip_if_exists`). Every agent tool reads it through the
> `CLAUDE.md` symlink.

## What this project is

pydantree provides a light, schema-backed typed-node runtime for tree-sitter
and a separate heavy grammar-authoring/build package. Product A consumes
vendored schemas or generated bundles; Product B authors grammars and emits
those bundles. It is not a general-purpose parser generator beyond the
tree-sitter boundary or a compatibility layer for the deleted legacy
extractor API.

## Working here

```bash
devenv shell                     # enter the pinned environment
repoman-sync                     # verify toolchain + install agent skills
```

All commands run inside `devenv shell`:

```bash
devenv shell -- python -m pytest -q
devenv shell -- ruff check src tests examples
devenv shell -- ty check src
```

The full suite, warnings-as-errors suite, Ruff, ty, documentation snippets,
and maintained examples must be green before a PR.

## Where things live

`src/pydantree_sitter/` contains the typed runtime (`nodes.py`, `grammar.py`,
`find.py`, `generate.py`, `schema.py`, `raw.py`, and `loader.py`).
`src/pydantree_sitter_grammar/` contains Product B's rule DSL, checks, pipeline,
and scanners. `tests/` contains schema fixtures, bundle tests, and the full
toolchain gates; deeper architecture and workflow detail lives in `docs/`.

## The standing configuration

The user's cross-repo law — devenv discipline, the exit-code contract, manager
routing, the agent-files convention — lives in
[`.agents/skills/my-ai/SKILL.md`](.agents/skills/my-ai/SKILL.md), delivered by
the `my-ai` personal layer. **Read it first.** Keep this file for what is true of
*this* project only.

```bash
copyroom layer list              # which template layers manage this repo
copyroom update --layer my-ai    # converge the personal layer
copyroom agent-files check       # conformance report
```
