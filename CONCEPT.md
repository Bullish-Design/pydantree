# Pydantree Concept

## Vision

Pydantree is the user-facing Python layer for Tree-sitter query codegen workflows.

It should let users consume generated query `.scm` files, work with typed Pydantic query models, and produce stable, deterministic Pydantic baseclasses suitable for typed query development.

## Product definition

Pydantree provides:

1. **CUE schemas as source of truth**
   - All data structures defined in CUE
   - Pydantic models are thin wrappers for CUE-validated objects
   - `ir_schema.cue` and `manifest_schema.cue` are authoritative

2. **A deterministic generation pipeline**
   - `.scm` query inputs (source of truth)
   - Normalized intermediate representation (IR)
   - Reproducible generated models with shared baseclasses
   - Manifest with hashes for reproducibility

3. **A Pythonic API aligned with Tree-sitter query semantics**
   - Familiar capture naming
   - Explicit model boundaries
   - Shared baseclasses eliminate duplication

4. **A shell-first workshop workflow**
   - Grammar/query-pack based commands (no raw paths)
   - Simple, observable pipeline stages
   - Deterministic output and validation

## MVP Scope

### In scope

- Query authoring/validation through models.
- Generation from `.scm` files with shared baseclasses.
- CUE-first validation for all artifacts.
- Typed output suitable for `model_dump()` and automation.
- Workshop workflow: scaffold → generate → validate → doctor.

### Out of scope (MVP)

- Runtime query execution (post-MVP).
- Graph construction and graph algorithms.
- Generic metric/security/static-analysis suites.
- Large framework-level orchestration.

## Shell-first command contract

The user-facing workflow is defined by a shell-first `just` contract. Commands accept grammar/query-pack names and resolve all paths internally from repository root.

### Contract

```bash
just workshop-init
just scaffold <language> <query-pack>
just generate-models <language> <query-pack>
just validate <language> <query-pack>
just doctor <language> <query-pack>
```

### Interface guarantees

1. `just workshop-init` prepares workshop-local state (creates canonical directory structure).
2. `just scaffold <language> <query-pack>` creates deterministic starter assets for a named grammar/query pack pair.
3. `just generate-models <language> <query-pack>` runs the full pipeline (ingest → normalize → emit → manifest) and validates with CUE.
4. `just validate <language> <query-pack>` validates IR and manifest against CUE schemas.
5. `just doctor <language> <query-pack>` runs diagnostics for environment, assets, and configuration for that pair.

### Resolution policy

- Public inputs are semantic names, not paths.
- Implementations must resolve canonical filesystem locations from repository root.
- Raw path arguments for grammar/query-pack assets are intentionally out of contract.

## Design tenets

1. **CUE is the source of truth for all data structures.**
2. **Typed at every boundary.**
3. **Deterministic generation and reproducible outputs.**
4. **Simple API surface over broad abstraction.**
5. **Shared baseclasses eliminate duplication.**
6. **Workshop-style workflow like Grammatic.**

## Architecture: Shared baseclasses

Generated modules import shared baseclasses instead of duplicating definitions:

**Shared (generated once):**
```python
# src/pydantree/generated/base.py
class Capture(BaseModel): ...
class Pattern(BaseModel): ...
class Query(BaseModel): ...
```

**Per-pack (generated per query pack):**
```python
# src/pydantree/generated/<language>/<query_pack>/models.py
from pydantree.generated.base import Query, Pattern, Capture

QUERY_MODEL = Query(...)  # Just data
```

**Benefits:**
- No duplication across query packs
- Cross-pack composability
- Smaller generated files
- Cleaner imports

## CUE-first validation flow

```
.scm files
  ↓
  ingest (Python)
  ↓
  normalize (Python)
  ↓
  IR JSON
  ↓
  validate against ir_schema.cue ✓
  ↓
  emit (Python) with shared baseclasses
  ↓
  manifest JSON
  ↓
  validate against manifest_schema.cue ✓
```

Pydantic models assume CUE-valid input. CUE validation happens before Pydantic consumption.

## Canonical workshop layout

```
workshop/
├── queries/<language>/<query_pack>/*.scm     # Source of truth
├── ir/<language>/<query_pack>/ir.v1.json     # Normalized IR
└── manifests/<language>/<query_pack>.json    # Manifest with hashes

src/pydantree/
├── generated/
│   ├── base.py                               # Shared baseclasses
│   └── <language>/<query_pack>/
│       └── models.py                         # Generated data

logs/
└── workshop.jsonl                            # Event log
```

All path resolution uses `WorkshopLayout` to map semantic names to canonical paths.

## Manifest structure (CUE-defined)

The manifest follows `manifest_schema.cue` exactly:

```cue
#Manifest: {
    input_hashes: [string]: string      // .scm file path → SHA256
    toolchain_versions: [string]: string // tool name → version
    output_file_hashes: [string]: string // generated file → SHA256
    generated_at?: string                // ISO timestamp (metadata)
}
```

This provides:
- Input provenance (which .scm files were used)
- Toolchain provenance (which tool versions)
- Output verification (which files were generated and their hashes)
- Timestamp for debugging (excluded from fingerprint calculations)

## Success criteria

1. A generated query set can be loaded without hand-written schema glue.
2. Generation is deterministic and reproducible.
3. Output is stable and serializable.
4. Validation runs against CUE schemas for confidence.
5. Commands use semantic names (language/query-pack), never raw paths.
6. Shared baseclasses eliminate duplication across query packs.
