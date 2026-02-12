# Pydantree Agent Guide

This file guides contributors/agents implementing the roadmap.

## Mission

Build and maintain Pydantree as a focused library that converts generated Tree-sitter query `.scm` files into typed Pydantic models and runs them through a lightweight Tree-sitter CLI wrapper.

## Scope rules

- Keep scope centered on query workflows.
- Do not add graph-analysis, generic static-analysis, or broad export subsystems.
- Prefer small, explicit APIs over framework-style abstractions.

## Working workflow

1. **Start from generated `.scm` files** (treat them as source of truth).
2. Parse + normalize into versioned IR models.
3. Generate deterministic Pydantic model code.
4. Run queries through Tree-sitter CLI adapter.
5. Return typed result envelopes and JSON-equivalent output.

## Engineering constraints

- Determinism first: generation should be reproducible and diff-friendly.
- Validation at boundaries: loader -> IR -> generated model -> runtime output.
- Clear provenance: persist source file, language, query type, and revision/hash info.
- Keep runtime thin and debuggable; avoid hidden side effects.

## Repository conventions

- `src/pydantree/codegen/`: ingestion, IR conversion, emitters.
- `src/pydantree/models/`: hand-written shared schemas.
- `src/pydantree/runtime/`: CLI execution + output normalization.
- `tests/fixtures/`: source inputs and expected query outputs.

## PR expectations

- One logical concern per PR where possible.
- Include before/after behavior summary.
- Document any schema or generation manifest changes.
- Add or update tests for parser, generation, and runtime impacts.

## Definition of done (feature-level)

A change is complete when:

1. Inputs and outputs are modeled/validated.
2. Generation remains deterministic.
3. Tests cover success and failure paths.
4. User-facing docs and examples are updated.
5. No broadened scope beyond query-centric goals.
