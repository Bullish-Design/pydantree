# Pydantree Agent Guide

This file guides contributors/agents implementing the roadmap.

## Mission

Build and maintain Pydantree as a focused library that converts generated Tree-sitter query `.scm` files into typed Pydantic models through a deterministic codegen pipeline.

## MVP Scope

**In scope:**
- Codegen pipeline (ingest → normalize → emit → manifest)
- CUE-first validation (CUE is source of truth)
- Shared baseclasses architecture
- Workshop-style workflow with semantic commands
- Deterministic, reproducible generation

**Out of scope (MVP):**
- Runtime query execution (post-MVP)
- Graph analysis features
- Generic static-analysis platforms
- Framework-style abstractions

## Core Principles

1. **CUE is the source of truth**
   - Define all data structures in CUE schemas first
   - Python Pydantic models are thin wrappers
   - Validate with CUE before Python consumption

2. **Shared baseclasses eliminate duplication**
   - Generate `base.py` once with Capture/Pattern/Query classes
   - Per-pack modules import baseclasses and define data only
   - Enables cross-pack composability

3. **Workshop-style workflow**
   - Commands use semantic names (language, query_pack)
   - Never accept raw filesystem paths in public interface
   - Use `WorkshopLayout` for all path resolution

4. **Deterministic generation**
   - Same inputs → byte-identical outputs
   - Exclude timestamps from fingerprints
   - Stable sorting, stable IDs

5. **Keep scope narrow**
   - Do not add graph analysis or broad static-analysis features
   - Do not add runtime query execution in MVP
   - Prefer small, explicit APIs over framework abstractions

## Working Workflow

1. **Start from generated `.scm` files** (source of truth).
2. Ingest + normalize into versioned IR.
3. Validate IR against `ir_schema.cue`.
4. Emit shared baseclasses + per-pack data modules.
5. Build manifest and validate against `manifest_schema.cue`.
6. Write events to workshop log.

## Engineering Constraints

- **CUE-first:** All schemas defined in CUE, Python follows.
- **Determinism first:** Generation must be reproducible and diff-friendly.
- **Validation at boundaries:** Validate with CUE after ingest/normalize/emit.
- **Clear provenance:** Persist source file, language, query type, hashes.
- **Canonical paths:** Use `WorkshopLayout` exclusively for path resolution.

## Repository Conventions

### Directory structure

```
src/pydantree/
├── codegen/           # Ingest, normalize, emit pipeline
├── registry/          # WorkshopLayout path resolution
├── workshop/          # High-level orchestrator commands
├── cue/               # CUE schemas (source of truth)
└── generated/
    ├── base.py        # Shared baseclasses
    └── <lang>/<pack>/ # Per-pack generated data

workshop/
├── queries/<lang>/<pack>/*.scm      # Source .scm files
├── ir/<lang>/<pack>/ir.v1.json      # Normalized IR
└── manifests/<lang>/<pack>.json     # Manifest

tests/
├── fixtures/          # Test .scm files and source fixtures
├── unit/              # Unit tests for codegen stages
└── integration/       # End-to-end workshop tests
```

### Command structure

**High-level (public contract):**
```bash
just workshop-init
just scaffold <language> <query-pack>
just generate-models <language> <query-pack>
just validate <language> <query-pack>
just doctor <language> <query-pack>
```

**Low-level (internal/dev):**
```bash
just codegen-ingest
just codegen-normalize
just codegen-emit
just codegen-manifest
```

## PR Expectations

- One logical concern per PR where possible.
- Include before/after behavior summary.
- Document any schema changes (especially CUE schemas).
- Add or update tests for codegen, validation, and workshop contract.
- Run CUE validation on all test artifacts.
- Verify determinism (generate twice, assert identical output).

## Definition of Done (Feature-Level)

A change is complete when:

1. **CUE schemas updated** if data structures changed.
2. **Python models aligned** with CUE schemas.
3. **Tests pass** including CUE validation.
4. **Generation remains deterministic** (verified by tests).
5. **Workshop contract preserved** (semantic names, not paths).
6. **Documentation updated** (README, CONCEPT, ROADMAP if needed).
7. **No broadened scope** beyond codegen-centric MVP goals.

## Common Tasks

### Adding a new codegen stage

1. Define output structure in CUE schema.
2. Create Python model matching CUE schema.
3. Implement stage function (pure, no side effects).
4. Add unit tests with fixtures.
5. Add CUE validation step.
6. Update pipeline orchestrator to call new stage.

### Updating manifest format

1. Update `manifest_schema.cue` first.
2. Update `src/pydantree/codegen/manifest.py` to match.
3. Update `doctor` to expect new format.
4. Add migration guide if breaking change.
5. Update tests to validate new format.

### Adding a new workshop command

1. Define expected behavior in CONCEPT.md.
2. Implement function in `src/pydantree/workshop/commands.py`.
3. Use `WorkshopLayout` for all path resolution.
4. Add CLI entry in `src/pydantree/workshop/cli.py`.
5. Add `justfile` recipe.
6. Add integration test in `tests/test_workshop_contract.py`.
7. Update README quickstart if user-facing.

## Testing Strategy

### Unit tests
- Test each codegen stage (ingest, normalize, emit) in isolation.
- Use small, focused fixtures.
- Assert deterministic outputs.

### CUE validation tests
- Generate IR/manifest from fixtures.
- Validate against CUE schemas.
- Assert validation passes for valid inputs.
- Assert validation fails for invalid inputs.

### Integration tests
- Test full workshop flow: scaffold → generate → validate → doctor.
- Use realistic .scm fixtures.
- Assert generated files at canonical paths.
- Assert CUE validation passes.

### Determinism tests
- Generate twice from same input.
- Assert byte-identical output (excluding timestamps).

## CUE Schema Development

### When to update CUE schemas

- Adding new fields to IR or manifest.
- Changing data structure shapes.
- Adding constraints (e.g., required fields, types).

### CUE schema workflow

1. Edit `.cue` file in `src/pydantree/cue/`.
2. Test validation manually: `cue vet <schema>.cue <data>.json`.
3. Update Python models to match.
4. Add tests validating Python → JSON → CUE round-trip.

## Troubleshooting

### CUE validation fails

- Check Python model matches CUE schema exactly.
- Use `cue vet -v` for verbose error messages.
- Ensure field names, types, and nesting match.

### Generated output not deterministic

- Check for `datetime.now()` in artifact payloads.
- Move timestamps to metadata (excluded from fingerprints).
- Ensure stable sorting in all collection outputs.

### WorkshopLayout path errors

- Ensure language/query_pack names are valid (no `/`, `.`, `..`).
- Use `layout.queries_pack_dir()` not manual path construction.
- Never accept raw paths in public commands.

## Architecture Reference

### Shared baseclasses pattern

```python
# Generated once: src/pydantree/generated/base.py
class Capture(BaseModel):
    capture_id: str
    name: str

# Generated per-pack: src/pydantree/generated/python/highlights/models.py
from pydantree.generated.base import Capture, Pattern, Query

QUERY_MODEL = Query(...)  # Just data
```

### CUE-first validation flow

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

## References

- [ROADMAP.md](ROADMAP.md): Implementation phases and tasks.
- [CONCEPT.md](CONCEPT.md): Product vision and design tenets.
- [README.md](README.md): User-facing quickstart and API.
- [CODE_REVIEW.md](CODE_REVIEW.md): Historical review (recommendations addressed in MVP).
