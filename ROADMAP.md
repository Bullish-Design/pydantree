# Pydantree Roadmap

This roadmap describes a practical, step-by-step path to build a focused **Tree-sitter query modeling library** from generated `.scm` query files (highlights/tags/etc.).

## 1) Define the product boundary

1. Confirm scope: Pydantree is a Python + Pydantic wrapper for Tree-sitter query workflows.
2. Lock non-goals: no graph analysis, no generic static-analysis platform, no exporter ecosystem.
3. Freeze initial API targets:
   - `QuerySpec`
   - `QueryTarget`
   - `QueryRunner`
   - `MatchResult`, `MatchItem`, `CaptureItem`

## 2) Establish repository structure

1. Create/confirm package layout:
   - `src/pydantree/models/` for Pydantic input/output schemas.
   - `src/pydantree/codegen/` for `.scm` ingestion + generation.
   - `src/pydantree/runtime/` for Tree-sitter CLI process execution.
   - `src/pydantree/registry/` for language/query-set metadata.
2. Add `tests/` with subfolders:
   - `tests/unit/`
   - `tests/integration/`
   - `tests/fixtures/`

## 3) Build the `.scm` ingestion layer

1. Define source layout for generated query files, for example:
   - `queries/<language>/highlights.scm`
   - `queries/<language>/tags.scm`
2. Implement a loader that discovers files and records provenance (language, query type, source path).
3. Parse captures/patterns into a stable internal representation (IR).

## 4) Implement normalization + IR

1. Create versioned IR models with Pydantic.
2. Normalize parser output into deterministic records:
   - stable ordering
   - explicit pattern ids
   - capture metadata preserved
3. Add strict validation errors for malformed/unsupported query entries.

## 5) Generate typed models from IR

1. Create deterministic codegen templates for query and result models.
2. Emit generated modules by language/query type.
3. Write a generation manifest (hashes, stage fingerprints, counts, tool versions, and timestamp) to support reproducible builds.
4. Ensure generation is idempotent (same inputs => byte-identical outputs).

## 6) Implement runtime query execution

1. Build a small command runner around Tree-sitter CLI.
2. Support running against:
   - filesystem paths
   - in-memory string content (via temp files or stdin where supported)
3. Parse CLI output into normalized structures and hydrate generated models.

## 7) Add user-facing API + CLI

1. Expose minimal Python API surface from `pydantree.__init__`.
2. Add CLI commands:
   - `pydantree generate`
   - `pydantree run`
   - `pydantree validate`
3. Keep CLI output debuggable and machine-readable (JSON option).

## 8) Add validation against Tree-sitter fixtures

1. Start with a small language subset (e.g., Python + JavaScript).
2. Validate at three levels:
   - parse-level (`.scm` -> IR)
   - schema-level (IR -> models)
   - execution-level (queries against fixture code)
3. Store golden outputs for capture spans/names and compare in CI.

## 9) Documentation + examples

1. Document generation workflow end-to-end.
2. Add example scripts for:
   - loading generated models
   - running queries on files
   - dumping JSON-equivalent results
3. Add troubleshooting page for CLI/environment issues.

## 10) Release hardening

1. Add compatibility matrix (Python + Tree-sitter versions).
2. Add changelog policy focused on generated schema/version changes.
3. Cut `0.1.0` with a narrow, stable API.

---

## Suggested implementation phases

- **Phase A (MVP):** Steps 1-7 for one language.
- **Phase B (Validation):** Step 8 with fixture-based confidence.
- **Phase C (Scale):** additional language packs and stronger CI automation.
