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

## Planning docs

- [ROADMAP.md](ROADMAP.md): step-by-step implementation plan.
- [AGENT.md](AGENT.md): contributor/agent execution guide.
- [CONCEPT.md](CONCEPT.md): product intent and design principles.

## License

MIT License - see [LICENSE](LICENSE).
