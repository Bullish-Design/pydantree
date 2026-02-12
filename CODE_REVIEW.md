# Pydantree Code Review

> **Status:** This review's recommendations have been incorporated into the MVP design (2025-02).
> See [ROADMAP.md](ROADMAP.md), [CONCEPT.md](CONCEPT.md), and [README.md](README.md) for the updated plan.
>
> **Key MVP decisions based on this review:**
> - Single CUE-based manifest format aligned with `manifest_schema.cue`
> - Shared baseclasses architecture to eliminate duplication
> - High-level workshop commands implemented via `WorkshopLayout`
> - Runtime execution deferred to post-MVP
> - Determinism gaps addressed (timestamps excluded from fingerprints)
> - Canonical workshop layout enforced throughout

---

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

2. **Manifest contract is fragmented.**
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


### A) Contract drift between docs and implementation

1. Docs claim a grammar/query-pack semantic command contract; actual commands still use file paths.
2. `justfile` does not represent the canonical contract advertised in README/CONCEPT.

### B) Manifest and validation architecture conflicts

1. Doctor, CUE schema, and manifest builder disagree on manifest shape.
2. CUE validation likely cannot validate emitted manifest artifacts from the current Python manifest model without adapters.
3. This blocks trustworthy provenance checks and deterministic validation gates.

### C) Determinism gaps

1. Ingest/emit/manifest include `datetime.now(...)` fields directly in outputs, making artifacts non-reproducible across runs unless those timestamps are intentionally excluded from fingerprints.
2. Generated module strings are deterministic for identical inputs, but surrounding pipeline artifacts include time-variant data.

### D) Model duplication in generated output

1. Every generated module defines local `Capture`, `Pattern`, and `Query` classes.
2. This hinders composability and cross-pack interoperability compared to shared baseclasses + thin per-pack constants.

### E) Test coverage blind spots

1. No tests for CLI command registration or `pydantree` script behavior.
2. No tests proving manifest schema compatibility across doctor/CUE/builder.
3. No tests around canonical workshop contract commands (because they are not fully implemented).

---

## 3) Specific toe-stepping / overlap findings

These are the most concrete places where parts of the codebase step on each other:

1. **Manifest toe-stepping:** three incompatible manifest contracts (schema vs doctor vs builder).
2. **Workflow toe-stepping:** docs assert grammar/query-pack contract while `justfile` and codegen CLI still prioritize path-based execution.
3. **Entrypoint toe-stepping:** conflicting script table declarations in `pyproject.toml`.

---

## 4) Opportunities to improve modularity/composability

## High-value structural changes



1. **Establish one versioned IR + one versioned manifest contract**
   - Keep schemas in `src/pydantree/cue/` authoritative.
   - Generate Python models from those schemas (or vice versa) to avoid drift.
   - Add explicit `manifest_version` and migration path.

2. **Promote shared generated baseclasses**
   - Emit shared base models once (e.g., `src/pydantree/generated/base.py`).
   - Emit per-pack modules as data payload + lightweight typed wrappers.
   - This improves composability across query packs and reduces duplication.

3. **Make `WorkshopLayout` mandatory in command implementations**
   - All user commands take logical names only.
   - Path-based forms remain internal/developer-only.

4. **Introduce orchestrator library functions for the workshop loop**
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

1. **Pick a single manifest schema and align all producers/consumers**
   - Update builder, doctor, and CUE schema together.
   - Add compatibility test fixtures.

2. **Implement the advertised shell-first contract end-to-end**
   - Add grammar/query-pack-based `just` recipes that route through `WorkshopLayout`.
   - Keep old path-based recipes as internal aliases during transition.

3. **Refactor emitter to shared baseclasses + data-centric generated modules**
   - Reduce repeated class definitions.
   - Improve import ergonomics and composability.

4. **Add contract tests around the workshop loop**
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
