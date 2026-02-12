# Grammatic

Grammatic is a **tree-sitter grammar workshop** for humans and agents.

It provides a shell-first workflow for creating, modifying, validating, and testing grammars using existing tools (`tree-sitter`, `gcc/g++`, `jq`, `git`) coordinated through `just`.

## Why Grammatic

Grammatic is intentionally lightweight:

- `just` as the control plane
- tree-sitter CLI for generation, testing, and parse capabilities
- small Python scripts for typed logging and validation
- append-only JSONL logs for reproducible workshop history

Primary goal: **fast grammar iteration with strong testing feedback**.

## Core Workflow

```bash
just init
just add-grammar python https://github.com/tree-sitter/tree-sitter-python

# iterate on grammar + corpus tests
just generate python
just build python
just test-grammar python
just doctor python
```

Use parse as a supporting check when needed:

```bash
just parse python tests/fixtures/sample_python.py
```

## Command Surface (MVP)

All key commands are grammar-name based:

- `just generate <grammar>`
- `just build <grammar>`
- `just test-grammar <grammar>`
- `just doctor <grammar>`
- `just parse <grammar> <source>` (auxiliary)
- `just query-*` and metrics helpers for logs

## Canonical Paths

- Grammar sources: `grammars/<grammar>/`
- Build outputs: `build/<grammar>/<grammar>.so`
- Logs: `logs/builds.jsonl`, `logs/parses.jsonl`

## Testing-First Orientation

Testing is the center of the project:

- corpus tests (`tree-sitter test`) are first-class
- `doctor` identifies common grammar setup/quality issues
- parse output is useful but secondary to test outcomes

## Logging and Provenance

Logs are append-only JSONL for practical reproducibility.

- Build events
- Parse events
- Tooling metadata and structured fields validated by Pydantic models

## Development Environment

Use the devenv-managed environment for consistent tooling:

```bash
devenv shell
```

The canonical runtime is Python 3.13 + `uv`, with `just`, `tree-sitter`, compilers, and `jq` available.

## Additional Documentation

- [CONCEPT.md](./CONCEPT.md) — distilled project concept and scope
- [AGENTS.md](./AGENTS.md) — agent operating guidance
- [skills/grammar-workshop/SKILL.md](./skills/grammar-workshop/SKILL.md) — reusable agent workflow skill
