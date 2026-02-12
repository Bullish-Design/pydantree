# Pydantree

**A user-facing, Pythonic wrapper for Neovim Tree-sitter queries using Pydantic models.**

Pydantree is being refocused into a small, practical library for personal development environments (`devenv.sh`) where you want to:

- define Tree-sitter query shapes as typed Pydantic models,
- run those queries through the Tree-sitter CLI workflow,
- and receive clean JSON-like, model-backed match data in Python.

This project is intentionally narrowing scope. It is **not** a graph-analysis toolkit.

## Project Direction (New Scope)

Pydantree now targets one core job:

1. Represent query and match structures with Pydantic.
2. Provide a Python-first API that maps closely to Neovim Tree-sitter query concepts.
3. Execute query flows in a simple wrapper around Tree-sitter CLI usage.
4. Emit structured JSON-equivalent match results for downstream automation.

For the detailed concept and architecture goals, see [CONCEPT.md](CONCEPT.md).

## Core Principles

- **User-facing first**: the API should feel natural from Python, not like a thin C binding.
- **Typed interfaces**: Pydantic models should be the primary data boundary.
- **Simple operational model**: prioritize direct CLI-backed workflows over heavy abstraction.
- **Neovim query alignment**: naming and behavior should mirror Tree-sitter query semantics used in Neovim.
- **No graph layer**: graph-specific APIs and concepts are out of scope.

## Intended Usage (Conceptual)

```python
from pydantree import QuerySpec, QueryRunner

spec = QuerySpec(
    language="python",
    query="""
    (function_definition
      name: (identifier) @function.name) @function.def
    """,
    captures=["function.def", "function.name"],
)

runner = QueryRunner()
result = runner.match_file("example.py", spec)

# JSON-equivalent typed output
print(result.model_dump())
```

## What is Explicitly Out of Scope

- AST graph construction
- Graph algorithms or isomorphism matching
- Graph visualization
- Multi-purpose static analysis platform ambitions (e.g., complexity analyzers, security scanners, or architecture-level auditing unrelated to query matches)

## Development Notes

This repository is currently in a concept-first transition. As implementation evolves, the README will track concrete APIs and installation details aligned to the narrowed scope.

## License

MIT License - see [LICENSE](LICENSE).
