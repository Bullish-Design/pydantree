# Pydantree MVP Roadmap

This roadmap describes a practical, step-by-step path to build a focused **Tree-sitter query modeling library** from generated `.scm` query files (highlights/tags/etc.).

## MVP Product Boundary

**Scope:**
- Codegen pipeline only (no runtime query execution)
- CUE schemas as source of truth
- Shared baseclasses architecture
- Workshop-style workflow with semantic commands
- Deterministic, reproducible model generation

**Non-goals (MVP):**
- Runtime query execution (post-MVP)
- Graph analysis features
- Generic static-analysis platform
- Exporter ecosystem

## Implementation Phases

### Phase 1: Align CUE schemas and Python models

**Goal:** Make CUE schemas the single source of truth.

1. **Update `manifest_schema.cue`** to match the decided format:
   ```cue
   #Manifest: {
       input_hashes: [string]: string
       toolchain_versions: [string]: string
       output_file_hashes: [string]: string
       generated_at?: string
   }
   ```

2. **Update `ir_schema.cue`** to match normalized IR structure from Python:
   - Ensure `NormalizedCapture`, `NormalizedPattern`, `NormalizedQuery` align with CUE definitions
   - Add versioning (`version: "v1"`)

3. **Update Python manifest builder** (`src/pydantree/codegen/manifest.py`):
   - Replace `ReproducibilityManifest` with model matching CUE schema
   - Output per-file hash maps instead of aggregate fingerprints
   - Collect toolchain versions (python, cue, tree-sitter if available)

4. **Update doctor** to expect the unified manifest format.

5. **Add tests** validating Python → JSON → CUE round-trip compatibility.

### Phase 2: Implement shared baseclasses generation

**Goal:** Eliminate duplication by generating shared baseclasses once.

1. **Create baseclass generator**:
   - Add `src/pydantree/codegen/base_emit.py` to generate `base.py`
   - Should output:
     ```python
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

2. **Update emit module** (`src/pydantree/codegen/emit.py`):
   - Generate `base.py` if it doesn't exist (or if schema changed)
   - Update per-pack module template to import from `pydantree.generated.base`
   - Emit only `QUERY_MODEL` data in per-pack modules

3. **Update tests** to verify shared baseclass imports work correctly.

### Phase 3: Implement WorkshopLayout-based orchestrator

**Goal:** Create high-level Python functions that implement the workshop contract.

1. **Create `src/pydantree/workshop/commands.py`**:
   ```python
   def workshop_init(repo_root: Path) -> None:
       """Create canonical workshop directory structure."""

   def scaffold(language: str, query_pack: str, repo_root: Path) -> None:
       """Create starter query pack structure."""

   def generate_models(language: str, query_pack: str, repo_root: Path) -> None:
       """Run full pipeline: ingest → normalize → emit → manifest → validate."""

   def validate(language: str, query_pack: str, repo_root: Path) -> None:
       """Validate IR and manifest against CUE schemas."""

   def doctor(language: str, query_pack: str, repo_root: Path) -> None:
       """Run diagnostics for the query pack."""
   ```

2. **Each function uses `WorkshopLayout`** to resolve paths from semantic names.

3. **Implement pipeline orchestration** in `generate_models()`:
   - Call ingest → normalize → emit → manifest stages
   - Validate IR and manifest with CUE after generation
   - Write events to workshop log

### Phase 4: Implement justfile workshop commands

**Goal:** Expose the workshop contract through `just` recipes.

1. **Update `justfile`** with high-level commands:
   ```just
   workshop-init:
       PYTHONPATH=src python -m pydantree.workshop.cli workshop-init

   scaffold language query_pack:
       PYTHONPATH=src python -m pydantree.workshop.cli scaffold {{language}} {{query_pack}}

   generate-models language query_pack:
       PYTHONPATH=src python -m pydantree.workshop.cli generate-models {{language}} {{query_pack}}

   validate language query_pack:
       PYTHONPATH=src python -m pydantree.workshop.cli validate {{language}} {{query_pack}}

   doctor language query_pack:
       PYTHONPATH=src python -m pydantree.workshop.cli doctor {{language}} {{query_pack}}
   ```

2. **Create `src/pydantree/workshop/cli.py`** as the entry point:
   - Uses `typer` or `argparse`
   - Calls orchestrator functions from `commands.py`

3. **Keep old `codegen-*` recipes** as internal/development commands for debugging.

### Phase 5: Remove determinism gaps

**Goal:** Make generated artifacts byte-for-byte reproducible.

1. **Separate metadata from fingerprints**:
   - Keep `generated_at` timestamp in manifest for debugging
   - Exclude timestamps when computing fingerprints/hashes
   - Or use a separate `metadata` section in manifests

2. **Update ingest/normalize/emit**:
   - Move `datetime.now()` to logging/events, not artifact payloads
   - Or mark timestamp fields explicitly as excluded from deterministic comparisons

3. **Add determinism tests**:
   - Generate twice from same input
   - Assert byte-identical output (excluding timestamps)

### Phase 6: Update canonical paths throughout

**Goal:** Enforce the canonical workshop layout everywhere.

1. **Update default paths** in CLI commands:
   - `doctor` should default to `WorkshopLayout` paths, not `queries/` and `generated/manifest.json`

2. **Remove `build/` directory usage** (or clarify it's for temporary dev artifacts only):
   - Move IR to `workshop/ir/`
   - Move manifests to `workshop/manifests/`

3. **Update tests** to use canonical paths.

### Phase 7: Add end-to-end workshop tests

**Goal:** Validate the complete workshop workflow.

1. **Create `tests/test_workshop_contract.py`**:
   - Test: `workshop-init` → `scaffold` → `generate-models` → `validate` → `doctor`
   - Use a minimal fixture (e.g., `python/highlights`)
   - Assert generated files exist at canonical paths
   - Assert CUE validation passes
   - Assert doctor reports healthy state

2. **Add failure path tests**:
   - Invalid .scm syntax
   - Missing .scm files
   - CUE validation failures

### Phase 8: Documentation and examples

**Goal:** Make the library usable and understandable.

1. **Update all docs** to reflect MVP scope (DONE).

2. **Add usage examples**:
   - `examples/quickstart.md` showing the full workshop flow
   - `examples/custom_query_pack.md` for creating new query packs

3. **Add API reference**:
   - Document `WorkshopLayout` API
   - Document orchestrator functions
   - Document generated baseclass structure

### Phase 9: Cleanup and polish

**Goal:** Remove dead code and finalize package structure.

1. **Remove out-of-scope code**:
   - Remove runtime execution layer if present
   - Remove any graph analysis features

2. **Clean up package exports**:
   - Update `src/pydantree/__init__.py` with minimal stable API
   - Re-export key models: `WorkshopLayout`, base schemas

3. **Update `pyproject.toml`**:
   - Fix duplicate/conflicting entry points
   - Ensure correct script registration

4. **Lint and format**:
   - Run `ruff check` and fix issues
   - Run `mypy` and fix type issues

### Phase 10: Release readiness

**Goal:** Prepare for 0.1.0 MVP release.

1. **Version all artifacts**:
   - Explicit version in manifest
   - Migration path documented for future schema changes

2. **Add CHANGELOG.md**:
   - Document initial MVP release
   - Document breaking changes policy (schema changes only)

3. **CI/CD setup**:
   - Run tests on push
   - Validate CUE schemas
   - Check determinism

4. **Cut 0.1.0 release**:
   - Tag with semantic version
   - Publish to PyPI (if desired)

---

## Success Metrics

MVP is complete when:

1. ✅ All five workshop commands work end-to-end
2. ✅ CUE schemas validate all artifacts
3. ✅ Shared baseclasses eliminate duplication
4. ✅ Generation is deterministic (byte-for-byte reproducible)
5. ✅ Commands accept only semantic names (never raw paths)
6. ✅ Tests cover happy path and failure scenarios
7. ✅ Documentation is complete and accurate

---

## Post-MVP (Future)

After MVP stabilizes:

- Runtime query execution layer
- Additional language support
- Query composition features
- Integration with tree-sitter test fixtures
