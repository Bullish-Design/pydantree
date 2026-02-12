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


## Shell-first command contract

The user-facing workflow is defined by a shell-first `just` contract. Commands accept grammar/query-pack names and resolve all paths internally from repository root.

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

### Interface guarantees

1. `just workshop-init` prepares workshop-local state and indexes known grammars/query packs.
2. `just scaffold <language> <query-pack>` creates deterministic starter assets for a named grammar/query pack pair.
3. `just ingest <language> <query-pack>` loads and normalizes query artifacts into the internal representation.
4. `just generate-models <language> <query-pack>` emits deterministic Pydantic models from normalized query data.
5. `just validate <language> <query-pack>` checks schema integrity and runtime readiness for that pair.
6. `just run-query <language> <query-pack> <source>` executes a named query pack against a named source input and returns typed output.
7. `just doctor <language> <query-pack>` runs diagnostics for environment, assets, and configuration for that pair.

### Resolution policy

- Public inputs are semantic names, not paths.
- Implementations must resolve canonical filesystem locations from repository root.
- Raw path arguments for grammar/query-pack assets are intentionally out of contract.

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
