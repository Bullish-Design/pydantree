# Pydantree Code Review

## Review scope and framing

This review compares the current repository state against:

- Pydantree's stated concept and shell-first workshop contract.
- The Grammatic workshop model in `grammatic_example`, especially its creation/modify/generate/build/test loop and grammar-name-based command surface.
- The stated goal of making pydantree baseclass generation scriptable and composable using Tree-sitter/CUE CLIs plus a small Python library.

---

## 1) Concept fit: how well the current code matches the declared product

## What is already aligned

1. **Query-centric scope is mostly respected.**
   The repo focuses on ingest/normalize/emit/manifest stages, plus diagnostics and validation helpers, which maps to the query-first intent.

2. **Typed boundaries exist at several key stages.**
   Ingest, normalize, emit, manifest, and event logging all use explicit Pydantic models.

3. **Deterministic intent is visible.**
   There is deterministic sorting in ingest/normalize and content fingerprinting in emit/manifest/doctor.

4. **Workshop path abstraction exists.**
   `WorkshopLayout` is a good foundational abstraction for grammar/query-pack-based path resolution.

## Where concept adherence is weak or inconsistent

1. **Public command contract is not implemented coherently.**
   The concept/docs promise `just workshop-init`, `scaffold`, `ingest <language> <query-pack>`, etc., but the `justfile` exposes only low-level `codegen-*` tasks and takes raw paths.

2. **CLI entrypoint is currently merged in an invalid way.**
   `src/pydantree/cli.py` defines one Typer app for `doctor`, then redefines `app` and appends CUE validation commands in the same file. This creates command-surface ambiguity and likely accidental shadowing.

3. **Manifest contract is fragmented.**
   - CUE schema expects `output_file_hashes` and `toolchain_versions`.
   - `doctor` expects `generated_hashes` and `input_hashes`.
   - `build_manifest()` outputs fingerprints and counts but no per-file hash maps expected by doctor/schema.
   These are three incompatible manifest definitions.

4. **Runtime execution layer is conceptually promised but not yet present as a cohesive module.**
   The docs describe a thin Tree-sitter CLI runtime wrapper and typed result envelopes, but implementation is mostly diagnostics/logging plus codegen stages.

5. **Default paths conflict with canonical workshop layout.**
   `doctor` defaults to `queries/` and `generated/manifest.json`, while docs describe `workshop/queries/...` and `workshop/manifests/...`.

---

## 2) General code review

## Strengths

- **Good use of immutable models (`frozen=True`)** in core codegen artifacts.
- **Actionable diagnostics pattern** (`CodegenDiagnosticError`) is practical and user-facing.
- **Registry abstraction (`WorkshopLayout`)** is clean and straightforward.
- **Event model taxonomy** for workshop logging is clear and extensible.
- **Unit tests exist** for doctor, registry layout, logger, cue context mapping, and the pipeline happy path.

## Key issues found

### A) Build/package integrity issues

1. **`pyproject.toml` declares `[project.scripts]` twice**, which makes tooling fail early (pytest cannot even start).
2. This is a release-blocker because it breaks basic developer workflows.

### B) Command/API overlap and accidental redefinition

1. **`src/pydantree/cli.py` is effectively two CLIs jammed together**, with two `app = typer.Typer(...)` assignments.
2. This can silently drop earlier command registrations depending on import/order behavior.
3. The file appears to conflate:
   - user-facing product CLI (`doctor`)
   - generation wrapper CLI (`validate-ir`, `validate-manifest`, `generate`)

### C) Contract drift between docs and implementation

1. Docs claim a grammar/query-pack semantic command contract; actual commands still use file paths.
2. `justfile` does not represent the canonical contract advertised in README/CONCEPT.

### D) Manifest and validation architecture conflicts

1. Doctor, CUE schema, and manifest builder disagree on manifest shape.
2. CUE validation likely cannot validate emitted manifest artifacts from the current Python manifest model without adapters.
3. This blocks trustworthy provenance checks and deterministic validation gates.

### E) Determinism gaps

1. Ingest/emit/manifest include `datetime.now(...)` fields directly in outputs, making artifacts non-reproducible across runs unless those timestamps are intentionally excluded from fingerprints.
2. Generated module strings are deterministic for identical inputs, but surrounding pipeline artifacts include time-variant data.

### F) Model duplication in generated output

1. Every generated module defines local `Capture`, `Pattern`, and `Query` classes.
2. This hinders composability and cross-pack interoperability compared to shared baseclasses + thin per-pack constants.

### G) Test coverage blind spots

1. No tests for CLI command registration or `pydantree` script behavior.
2. No tests proving manifest schema compatibility across doctor/CUE/builder.
3. No tests around canonical workshop contract commands (because they are not fully implemented).

---

## 3) Specific toe-stepping / overlap findings

These are the most concrete places where parts of the codebase step on each other:

1. **CLI toe-stepping:** duplicate Typer app definitions in one file with overlapping responsibilities.
2. **Manifest toe-stepping:** three incompatible manifest contracts (schema vs doctor vs builder).
3. **Workflow toe-stepping:** docs assert grammar/query-pack contract while `justfile` and codegen CLI still prioritize path-based execution.
4. **Entrypoint toe-stepping:** conflicting script table declarations in `pyproject.toml`.

---

## 4) Opportunities to improve modularity/composability

## High-value structural changes

1. **Split CLI surfaces explicitly**
   - `pydantree.cli.app`: user-facing workshop commands (name-based)
   - `pydantree.codegen.cli`: stage-level engineering commands (artifact/path-based)
   - `pydantree.validate.cli` (optional): CUE gates as a dedicated CLI

2. **Establish one versioned IR + one versioned manifest contract**
   - Keep schemas in `src/pydantree/cue/` authoritative.
   - Generate Python models from those schemas (or vice versa) to avoid drift.
   - Add explicit `manifest_version` and migration path.

3. **Promote shared generated baseclasses**
   - Emit shared base models once (e.g., `src/pydantree/generated/base.py`).
   - Emit per-pack modules as data payload + lightweight typed wrappers.
   - This improves composability across query packs and reduces duplication.

4. **Make `WorkshopLayout` mandatory in command implementations**
   - All user commands take logical names only.
   - Path-based forms remain internal/developer-only.

5. **Introduce orchestrator library functions for the workshop loop**
   - `scaffold_pack(language, query_pack)`
   - `ingest_pack(...)`
   - `normalize_pack(...)`
   - `emit_pack(...)`
   - `validate_pack(...)`
   - `run_pack_query(...)`
   Then have both CLI and `just` invoke these functions.

## Medium-value cleanup

1. **Normalize deterministic metadata strategy**
   - Separate reproducibility fingerprint payloads from run metadata timestamps.
   - Keep timestamps in logs/events, not in deterministic artifact hashes.

2. **Consolidate diagnostics vocabulary**
   - Shared error codes across doctor/validation/codegen.
   - Include remediation hints consistently.

3. **Unify package exports**
   - Keep `__init__.py` exports minimal and stable.
   - Avoid broad re-export churn before API stabilizes.

---

## 5) Simplification and streamlining plan (practical sequence)

1. **Stabilize packaging + CLI integrity first**
   - Fix duplicate `[project.scripts]`.
   - Split/clean `src/pydantree/cli.py` so command registration is unambiguous.

2. **Pick a single manifest schema and align all producers/consumers**
   - Update builder, doctor, and CUE schema together.
   - Add compatibility test fixtures.

3. **Implement the advertised shell-first contract end-to-end**
   - Add grammar/query-pack-based `just` recipes that route through `WorkshopLayout`.
   - Keep old path-based recipes as internal aliases during transition.

4. **Refactor emitter to shared baseclasses + data-centric generated modules**
   - Reduce repeated class definitions.
   - Improve import ergonomics and composability.

5. **Add contract tests around the workshop loop**
   - Scaffold → ingest → normalize → emit → validate → doctor.
   - Include one successful and one failure-path fixture.

---

## 6) Comparison to Grammatic "workshop" model

Grammatic succeeds by being strict about:

- a small grammar-name command surface,
- explicit loop stages,
- tool-first orchestration,
- diagnostics + logs as iteration aids.

Pydantree is close in spirit but not yet equally coherent in execution. The main gap is **contract consistency**:

- docs and concept are workshop-contract-forward,
- implementation is still mixed between prototype path-based internals and user-facing promises.

If you align CLI + justfile + manifest contracts, pydantree will be much closer to the same workshop reliability profile you want for baseclass generation workflows.

---

## 7) Overall assessment

Current state: **promising architecture with significant contract drift and integration debt**.

- Concept quality: strong.
- Core building blocks: mostly good.
- Integration coherence: currently weak.
- Priority: resolve contract conflicts and CLI/package integrity before adding more features.

Once those are addressed, pydantree should be well-positioned to support scriptable creation/modification/generation workflows analogous to Grammatic, but for typed query/baseclass generation.
