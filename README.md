# Pydantree

**Typed Tree-sitter query workflows in Python, driven by generated `.scm` files.**

Pydantree is a focused library for turning Tree-sitter query artifacts (for example `highlights.scm` and `tags.scm`) into typed Pydantic models and executing those queries through a thin Tree-sitter CLI wrapper.

## Core idea

- Treat generated `.scm` files as source of truth.
- Normalize query/capture data into stable internal models.
- Generate deterministic Pydantic model code.
- Execute queries and return typed, JSON-equivalent results.

## Shell-first command contract

Pydantree's workshop workflow is shell-first. The `just` interface is the canonical public contract, and command arguments use **grammar names** and **query-pack names** (never raw filesystem paths).

### Contract

```bash
just workshop-init
just scaffold <language> <query-pack>
just ingest <language> <query-pack>
just generate-models <language> <query-pack>
just validate <language> <query-pack>
just run-query <language> <query-pack> <source>
just doctor <language> <query-pack>
```

### Argument semantics

- `<language>`: a grammar identifier, such as `python`, `typescript`, or `go`.
- `<query-pack>`: a named query collection for that grammar, such as `highlights`, `tags`, or another pack name exposed by the repository.
- `<source>`: source input selector for query execution (for example, a fixture key, inline content key, or configured source alias).

### Path-resolution rule

All filesystem paths are resolved **internally from repository root**.

- Users provide only stable names (`<language>`, `<query-pack>`, `<source>`).
- Command implementations map those names to canonical repository locations.
- No command in the public contract accepts raw local paths to grammar/query assets.

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
