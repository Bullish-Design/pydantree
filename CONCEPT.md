# Pydantree Concept

## Vision

Pydantree should be the **user-facing Python side** of Neovim-style Tree-sitter query workflows.

The library's purpose is to let users describe query objects and match results as Pydantic models, execute queries in a conceptually simple way (wrapping Tree-sitter CLI flows), and consume typed JSON-equivalent data in Python.

## Why This Direction

The previous direction mixed many concerns (views, transformations, graph analysis, etc.).
This concept intentionally narrows scope to improve clarity and long-term maintainability:

- one primary abstraction model,
- one query execution model,
- one output style.

## Product Definition

Pydantree is:

1. **Pydantic schemas for Tree-sitter query interactions**
   - query specification models,
   - capture/match/event models,
   - normalized result envelope models.

2. **A Pythonic Neovim Tree-sitter query API**
   - familiar naming and behavior for query/capture handling,
   - ergonomic helpers for common operations,
   - explicit, inspectable model objects.

3. **A wrapper over Tree-sitter CLI execution**
   - thin process-invocation layer,
   - deterministic mapping from CLI output into models,
   - minimal hidden magic.

Pydantree is **not**:

- a graph library,
- a general AST analytics platform,
- a complex transformation framework.

## Scope Boundaries

### In Scope

- Query authoring and validation via Pydantic.
- Running queries against source files/buffers through CLI-backed workflow.
- Emitting JSON-equivalent match structures (`model_dump`).
- Supporting practical local use inside `devenv.sh` personal environments.

### Out of Scope

- Graph building, traversal, pattern matching, or graph metrics.
- Non-query static analysis features not directly tied to query execution (for example: complexity scoring, security linting rule packs, dependency graphing, architectural smell detection, or broad code-quality auditing).
- Heavy orchestration frameworks.

## Design Tenets

1. **Typed at every boundary**
   - Input, intermediate, and output data structures should be modeled.

2. **Simple over comprehensive**
   - Prefer obvious behavior and small APIs over feature sprawl.

3. **CLI-centric integration**
   - The Tree-sitter CLI integration should remain transparent and debuggable.

4. **Neovim semantics as reference**
   - Terminology and conceptual model should align with Neovim Tree-sitter usage.

5. **Personal-dev-environment pragmatism**
   - Optimize for local workflow reliability over enterprise-level extensibility.

## Proposed High-Level API Surface

> Names are conceptual and can evolve.

- `QuerySpec` — language, query text, capture expectations, options.
- `QueryTarget` — file path or in-memory content target.
- `QueryRunner` — executes a query spec against a target.
- `MatchResult` — normalized top-level result object.
- `MatchItem` / `CaptureItem` — strongly typed result units.

## Execution Model (Conceptual)

1. User creates `QuerySpec` Pydantic model.
2. User points runner at a file/string target.
3. Runner invokes Tree-sitter CLI workflow.
4. Raw output is parsed/normalized into Pydantic result models.
5. User consumes:
   - typed Python attributes,
   - JSON-equivalent payload via `model_dump()`.

## Non-Goals for Initial Iteration

- Cross-language plugin ecosystem.
- Distributed or remote execution.
- Large-scale indexing/storage subsystems.
- Advanced editor-integration frameworks.

## Success Criteria

A successful first release of this concept should make the following easy:

1. Define a query in a typed model in <10 lines.
2. Run it against a file in one call.
3. Get stable, typed capture/match objects.
4. Serialize directly to JSON-equivalent structures for automation scripts.

## Migration Implications

All graph-related documentation and APIs should be considered deprecated for this concept and removed or ignored in future iterations.

## Summary

Pydantree is becoming a **focused Python + Pydantic interface for Neovim Tree-sitter query workflows**, implemented as a **simple wrapper around Tree-sitter CLI behavior**, with **typed JSON-equivalent outputs** as the primary deliverable.
