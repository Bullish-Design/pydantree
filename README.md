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


## Doctor command

Run diagnostics for query and generation health:

```bash
pydantree doctor
pydantree doctor --json
```

Checks include empty query files, capture-name validation, unsupported query features, manifest/hash drift, generation nondeterminism signals, and required runtime CLIs.
## Canonical workshop layout

Pydantree uses a canonical on-disk layout so generation, manifests, and runtime lookups stay deterministic:

- `workshop/queries/<language>/<query_pack>/*.scm` (source of truth)
- `workshop/ir/<language>/<query_pack>/ir.v1.json`
- `src/pydantree/generated/<language>/<query_pack>/`
- `workshop/manifests/<language>/<query_pack>.json` (hashes, tool versions, source refs)
- `logs/workshop.jsonl` (append-only event log)

Use `pydantree.registry.WorkshopLayout` path helpers so CLI and recipes can accept only logical names (`language`, `query_pack`) and avoid hard-coded paths.

## Workshop quickstart (shell-first)

The workshop flow uses only the `just` contract with semantic names:

```bash
just workshop-init
just scaffold python minimal_pack
just ingest python minimal_pack
just generate-models python minimal_pack
just validate python minimal_pack
just run-query python minimal_pack source
just doctor python minimal_pack
```

### Name → path resolution (internal)

For the example `python minimal_pack`, Pydantree resolves repository-root paths internally:

- Queries: `workshop/queries/python/minimal_pack/*.scm`
- Ingest artifact: `build/python/minimal_pack/ingest.json`
- Normalized IR: `workshop/ir/python/minimal_pack/ir.v1.json`
- Generated models: `src/pydantree/generated/python/minimal_pack/`
- Manifest: `workshop/manifests/python/minimal_pack.json`
- Source alias `source`: `tests/fixtures/python/minimal_pack/source.*`

Users pass names (`language`, `query-pack`, `source`) only; raw paths are not part of the public interface.

## Planning docs

- [ROADMAP.md](ROADMAP.md): step-by-step implementation plan.
- [AGENT.md](AGENT.md): contributor/agent execution guide.
- [CONCEPT.md](CONCEPT.md): product intent and design principles.

## License

MIT License - see [LICENSE](LICENSE).
