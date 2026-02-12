# Pydantree

**Typed Tree-sitter query workflows in Python, driven by generated `.scm` files.**

Pydantree is a focused library for turning Tree-sitter query artifacts (for example `highlights.scm` and `tags.scm`) into typed Pydantic models and executing those queries through a thin Tree-sitter CLI wrapper.

## Core idea

- Treat generated `.scm` files as source of truth.
- Normalize query/capture data into stable internal models.
- Generate deterministic Pydantic model code.
- Execute queries and return typed, JSON-equivalent results.

## Scope

In scope:
- Query model generation and validation.
- CLI-backed query execution.
- Typed capture/match result envelopes.

Out of scope:
- Graph analysis features.
- Generic exporter/analyzer frameworks.
- Broad static-analysis platforms not centered on query execution.

## Canonical workshop layout

Pydantree uses a canonical on-disk layout so generation, manifests, and runtime lookups stay deterministic:

- `workshop/queries/<language>/<query_pack>/*.scm` (source of truth)
- `workshop/ir/<language>/<query_pack>/ir.v1.json`
- `src/pydantree/generated/<language>/<query_pack>/`
- `workshop/manifests/<language>/<query_pack>.json` (hashes, tool versions, source refs)
- `logs/workshop.jsonl` (append-only event log)

Use `pydantree.registry.WorkshopLayout` path helpers so CLI and recipes can accept only logical names (`language`, `query_pack`) and avoid hard-coded paths.

## Planning docs

- [ROADMAP.md](ROADMAP.md): step-by-step implementation plan.
- [AGENT.md](AGENT.md): contributor/agent execution guide.
- [CONCEPT.md](CONCEPT.md): product intent and design principles.

## License

MIT License - see [LICENSE](LICENSE).
