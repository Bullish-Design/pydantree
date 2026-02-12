# Pydantree

**Typed Tree-sitter query workflows in Python, driven by generated `.scm` files.**

Pydantree is a focused library for turning Tree-sitter query artifacts (for example `highlights.scm` and `tags.scm`) into typed Pydantic models through a deterministic codegen pipeline.

## Core idea

- Treat generated `.scm` files as source of truth.
- Normalize query/capture data into stable internal models.
- Generate deterministic Pydantic model code with shared baseclasses.
- Validate all artifacts with CUE schemas (CUE is the source of truth, Pydantic wraps CUE objects).

## Shell-first command contract

Pydantree's workshop workflow is shell-first. The `just` interface is the canonical public contract, and command arguments use **grammar names** and **query-pack names** (never raw filesystem paths).

### Contract

```bash
just workshop-init
just scaffold <language> <query-pack>
just generate-models <language> <query-pack>
just validate <language> <query-pack>
just doctor <language> <query-pack>
```

### Argument semantics

- `<language>`: a grammar identifier, such as `python`, `typescript`, or `go`.
- `<query-pack>`: a named query collection for that grammar, such as `highlights`, `tags`, or another pack name exposed by the repository.

### Path-resolution rule

All filesystem paths are resolved **internally from repository root**.

- Users provide only stable names (`<language>`, `<query-pack>`).
- Command implementations map those names to canonical repository locations.
- No command in the public contract accepts raw local paths to grammar/query assets.

## MVP Scope

In scope:
- Query model generation from `.scm` files.
- CUE-based validation (CUE schemas are source of truth).
- Deterministic Pydantic model emission with shared baseclasses.
- Workshop-style workflow (scaffold → generate → validate → doctor).

Out of scope (MVP):
- Runtime query execution (post-MVP).
- Graph analysis features.
- Generic exporter/analyzer frameworks.
- Broad static-analysis platforms.

## Canonical workshop layout

Pydantree uses a canonical on-disk layout so generation, manifests, and lookups stay deterministic:

- `workshop/queries/<language>/<query_pack>/*.scm` (source of truth)
- `workshop/ir/<language>/<query_pack>/ir.v1.json` (normalized IR, validated by CUE)
- `workshop/manifests/<language>/<query_pack>.json` (hashes, tool versions, validated by CUE)
- `src/pydantree/generated/base.py` (shared Capture/Pattern/Query baseclasses)
- `src/pydantree/generated/<language>/<query_pack>/models.py` (generated data)
- `logs/workshop.jsonl` (append-only event log)

All path resolution uses `pydantree.registry.WorkshopLayout` so commands accept only logical names (`language`, `query_pack`) and never raw filesystem paths.

## Workshop quickstart (scaffold → generate → validate → iterate)

The steps below follow the shell-first contract and use one minimal, real fixture pack under `tests/fixtures/`:

- Query fixture: `tests/fixtures/python/minimal_pack/highlights.scm`

### 1) Initialize workshop

Create the canonical workshop directory structure:

```bash
just workshop-init
```

### 2) Scaffold a query-pack

Create a query-pack folder for a grammar:

```bash
just scaffold python highlights
```

This creates:
- `workshop/queries/python/highlights/` (for .scm files)
- `workshop/ir/python/highlights/` (for generated IR)
- `workshop/manifests/python/` (for manifest)

### 3) Add query files

Drop in at least one `.scm` query file:

```bash
cp tests/fixtures/python/minimal_pack/highlights.scm workshop/queries/python/highlights/highlights.scm
```

### 4) Generate models

Run the full codegen pipeline (ingest → normalize → emit → manifest):

```bash
just generate-models python highlights
```

This generates:
- `workshop/ir/python/highlights/ir.v1.json` (normalized IR)
- `workshop/manifests/python/highlights.json` (manifest with hashes)
- `src/pydantree/generated/base.py` (shared baseclasses, if not exists)
- `src/pydantree/generated/python/highlights/models.py` (query data)

### 5) Validate with CUE

Validate IR and manifest against CUE schemas:

```bash
just validate python highlights
```

### 6) Run diagnostics

Check for common issues:

```bash
just doctor python highlights
```

### 7) Inspect and iterate

Inspect generated artifacts, then update `.scm` patterns and rerun:

```bash
cat workshop/manifests/python/highlights.json
cat logs/workshop.jsonl
```

## Architecture: CUE-first validation

CUE schemas in `src/pydantree/cue/` are the source of truth for all data structures:

- `ir_schema.cue` defines the normalized IR structure.
- `manifest_schema.cue` defines the manifest structure.

**Validation flow**:
```
.scm files
  → ingest (Python)
  → normalize (Python)
  → IR JSON
  → validate against ir_schema.cue ✓
  → emit (Python)
  → manifest JSON
  → validate against manifest_schema.cue ✓
```

Pydantic models are thin wrappers that assume CUE-validated input.

## Shared baseclasses pattern

Generated modules import shared baseclasses instead of duplicating class definitions:

```python
# src/pydantree/generated/base.py (shared, generated once)
from pydantic import BaseModel

class Capture(BaseModel):
    capture_id: str
    name: str

class Pattern(BaseModel):
    pattern_id: str
    source: str
    captures: tuple[Capture, ...]

class Query(BaseModel):
    source_file: str
    language: str
    query_type: str
    patterns: tuple[Pattern, ...]
```

```python
# src/pydantree/generated/python/highlights/models.py (generated per pack)
from pydantree.generated.base import Query, Pattern, Capture

QUERY_MODEL = Query(
    source_file="python/highlights.scm",
    language="python",
    query_type="highlights",
    patterns=(
        Pattern(...),
        # ...
    ),
)
```

This eliminates duplication and enables cross-pack composability.

## Doctor command

Run diagnostics for query and generation health:

```bash
just doctor python highlights
pydantree doctor --json  # low-level form
```

Checks include empty query files, capture-name validation, unsupported query features, manifest/hash drift, and generation nondeterminism signals.

## Planning docs

- [ROADMAP.md](ROADMAP.md): MVP implementation plan.
- [AGENT.md](AGENT.md): contributor/agent execution guide.
- [CONCEPT.md](CONCEPT.md): product intent and design principles.
- [CODE_REVIEW.md](CODE_REVIEW.md): historical code review (recommendations implemented in MVP).

## License

MIT License - see [LICENSE](LICENSE).
