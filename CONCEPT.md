# Pydantree Concept

## Vision

Pydantree is the user-facing Python layer for Tree-sitter query workflows.

It should let users consume generated query `.scm` files, work with typed Pydantic query/match models, run queries through a small CLI wrapper, and consume stable JSON-equivalent results.

## Product definition

Pydantree provides:

1. **Pydantic schemas for query interactions**
   - query specifications,
   - captures/matches,
   - normalized result envelopes.

2. **A Pythonic API aligned with Tree-sitter query semantics**
   - familiar capture naming,
   - explicit model boundaries,
   - straightforward runtime usage.

3. **A deterministic generation pipeline**
   - `.scm` query inputs,
   - normalized intermediate representation,
   - reproducible generated models.

4. **A transparent Tree-sitter CLI execution layer**
   - minimal process wrapper,
   - debuggable command behavior,
   - deterministic output mapping.

## In scope

- Query authoring/validation through models.
- Generation from `.scm` files.
- Query execution against files/content.
- Typed output suitable for `model_dump()` and automation.

## Out of scope

- Graph construction and graph algorithms.
- Generic metric/security/static-analysis suites.
- Large framework-level orchestration.

## Design tenets

1. Typed at every boundary.
2. Deterministic generation and reproducible outputs.
3. Simple API surface over broad abstraction.
4. CLI-centric integration that is observable and testable.

## Success criteria

1. A generated query set can be loaded without hand-written schema glue.
2. Running a query requires one clear API call.
3. Output is stable and serializable.
4. Validation can run against Tree-sitter fixtures for confidence.
