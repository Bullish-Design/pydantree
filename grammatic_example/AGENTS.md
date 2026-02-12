# Grammatic Agent Guide

This file defines how agents should operate in this repository.

## Project Positioning

Grammatic is a **tree-sitter grammar workshop**.

Focus on:
- creating grammars
- modifying grammars
- validating grammars
- testing grammars

Parsing exists, but is secondary to grammar iteration and test quality.

## Core Principles

1. **Use existing tools**
   - Prefer `tree-sitter`, `gcc/g++`, `jq`, `git`, and `just`
   - Do not reimplement tree-sitter capabilities in Python

2. **Keep orchestration thin**
   - `just` targets are the main user/agent interface
   - Scripts should be small, explicit, and shell-friendly

3. **Grammar-name-first UX**
   - Commands should be invoked with grammar names (not raw paths)
   - Scripts and recipes must resolve paths internally from repo root

4. **Testing is primary**
   - Corpus tests are first-class
   - Grammar quality is measured by test outcomes and diagnostics

5. **Structured provenance**
   - Keep append-only JSONL logs for workshop events
   - Prefer typed log emission via Pydantic models

## Canonical Workflow

Use this loop as the default process:

1. Add/create grammar (`just add-grammar` or `just new-grammar`)
2. Edit grammar sources and corpus tests
3. `just generate <grammar>`
4. `just build <grammar>`
5. `just test-grammar <grammar>`
6. `just doctor <grammar>`
7. Optional: `just parse <grammar> <source>` for spot validation
8. Inspect logs and iterate

## Path + Artifact Conventions

- Grammar sources: `grammars/<grammar>/...`
- Build outputs: `build/<grammar>/<grammar>.so` (canonical)
- Logs: `logs/builds.jsonl`, `logs/parses.jsonl`

Agents should preserve these conventions when making changes.

## Logging Expectations

- Build events should include success/failure state
- Parse events are supporting telemetry
- Prefer minimal-but-useful fields over large schemas
- Include agent/run metadata when practical

## Implementation Guidance

- Prioritize reliability and clarity over abstraction
- Fail loudly with actionable error messages
- Validate file/dir prerequisites before running tool commands
- Keep Python focused on validation, path normalization, and structured logging

## Scope for MVP

Prioritize:
- workshop loop quality (generate/build/test/doctor)
- grammar-name command consistency
- deterministic build layout
- useful provenance

De-prioritize:
- broad platform support beyond the devenv Unix environment
- complex architectural layers
- over-designed APIs

## Useful Documents

- [CONCEPT.md](./CONCEPT.md): core concept and scope
- [README.md](./README.md): user-facing quick start and workflows
- [skills/grammar-workshop/SKILL.md](./skills/grammar-workshop/SKILL.md): recommended agent workflow skill
