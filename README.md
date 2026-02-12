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

## Workshop quickstart (scaffold → run → iterate)

The steps below follow the shell-first contract and use one minimal, real fixture pack under `tests/fixtures/`:

- Query fixture: `tests/fixtures/python/minimal_pack/highlights.scm`
- Source fixture: `tests/fixtures/python/minimal_pack/source.py`

### 1) Scaffold a query-pack

Create a query-pack folder for a grammar and drop in at least one generated `.scm` query file.

```bash
mkdir -p workshop/queries/python/minimal_pack
cp tests/fixtures/python/minimal_pack/highlights.scm workshop/queries/python/minimal_pack/highlights.scm
```

### 2) Ingest + normalize

Ingest `.scm` files into a provenance-aware artifact, then normalize pattern/capture IDs into stable IR.

```bash
PYTHONPATH=src python -m pydantree.codegen.cli ingest workshop/queries --out build/ingest.json
PYTHONPATH=src python -m pydantree.codegen.cli normalize --input build/ingest.json --out build/normalize.json
```

### 3) Generate baseclasses/models

Emit deterministic Pydantic query model modules into the canonical generated layout.

```bash
PYTHONPATH=src python -m pydantree.codegen.cli emit \
  --input build/normalize.json \
  --output-dir src/pydantree/generated/python/minimal_pack \
  --out build/emit.json
```

Expected generated module path for this minimal pack:

- `src/pydantree/generated/python/minimal_pack/python_highlights_models.py`

### 4) Validate with CUE + Python checks

Run CUE schema validation gates and Python tests/checks.

```bash
PYTHONPATH=src python -m pydantree.cli validate-ir build/normalize.json --schema-dir src/pydantree/cue
PYTHONPATH=src python -m pydantree.codegen.cli manifest --ingest build/ingest.json --normalize build/normalize.json --emit build/emit.json --out build/manifest.json
PYTHONPATH=src python -m pydantree.cli validate-manifest build/manifest.json --schema-dir src/pydantree/cue
pytest tests/test_codegen_pipeline.py
```

### 5) Run query against fixture source

Use the workshop contract command with logical names (no raw query file paths):

```bash
just run-query python minimal_pack source
```

For this fixture, `source` maps to `tests/fixtures/python/minimal_pack/source.py` and should capture `greet` as `@function.name`.

### 6) Inspect logs/manifests and iterate

Inspect provenance, fingerprints, and workshop logs, then update `.scm` patterns and rerun the loop.

```bash
cat build/manifest.json
cat logs/workshop.jsonl
```

## Planning docs

- [ROADMAP.md](ROADMAP.md): step-by-step implementation plan.
- [AGENT.md](AGENT.md): contributor/agent execution guide.
- [CONCEPT.md](CONCEPT.md): product intent and design principles.

## License

MIT License - see [LICENSE](LICENSE).
