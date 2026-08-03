---
name: pydantree-extraction
description: Extract typed data from text with tsquery (Product A) — OutputModel declarations, captures (field/kind/record/optional/list/descendant), predicates and markers, schema binding and validate_with, bundles, community grammars, stubs, and the error surface. Use when consuming a grammar with pydantree in your own project.
---

# pydantree — typed extraction (tsquery, Product A)

Declare an `OutputModel` — **the model IS the query** — and get
schema-checked, typed rows over any tree-sitter grammar. Full reference:
`../../docs/user-guide.md` §2.

## The model

```python
from typing import Annotated
from tsquery import M, Matches, NodeKind, OutputModel, capture, source_meta
import tree_sitter_python

class Assignment(OutputModel):
    __match__ = M("module", "expression_statement", "assignment")
    name: Annotated[str, Matches(r"^[A-Z][A-Z_]*$")] = capture("left")
    value: Annotated[int, NodeKind("integer")] = capture("right")
    line: int = source_meta()

rows = Assignment.extract(source_text, language=tree_sitter_python)
```

## The capture surface

| pattern | meaning |
|---|---|
| `= capture("f")` | bind to CST field `f` (no-arg: attr name IS the field) |
| `= capture_kind("code_span")` | bind to a CHILD BY NODE KIND (positional-children grammars like markdown) |
| `= source_meta()` | anchor line (`int`) or byte span (`Span`) |
| `list[T] = capture("f")` | field-mode LIST (repeated field on the anchor, merged) |
| `str \| None = capture("f")` | OPTIONAL capture — matches without the field materialize None |
| `Annotated[..., NodeKind(...)]` | constrain the node kind (tuple = alternation) |
| `Annotated[str, Unescaped()]` | decode string-literal escapes |
| nested `OutputModel` field | materialize a nested node with the inner model |
| `M("module", ..., "call")` | descendant `"..."` matches any depth |

## Record mode (key/value documents)

```python
class ServerSection(OutputModel):
    __match__ = M("source_file", "section", record=True)
    host: str
    port: int
    debug: bool = False
    line: int = source_meta()
```

The record node is the anchor; attr names (or `capture("key")`) are the
record keys; the value shapes are DERIVED from the grammar's schema; a
predicate field that doesn't match filters the whole record.

## Schemas: check BEFORE parsing

```python
from tsquery import Language
lang = Language.load_bundle("dist/cfg-bundle")   # one call, checks bound
ServerSection.validate_with(lang)                # Jobs 1/3/4, no text parsed
rows = ServerSection.extract(text, language=lang)

# bare community wheel + explicit schema:
lang = Language.load(tree_sitter_rust.language(), schema="node-schema.json")
```

The schema is bound to the Language INSTANCE (register=True opts into a
name-keyed convenience; nameless languages are refused). Without a schema
the derivation falls back to the schema-less path.

## Other A surface

- `lang.parse(src)` / `lang.reparse(old_tree, new)` — parse + incremental.
- `OutputModel.extract_tree(tree, ...)` — parse once, extract many models.
- `OutputModel.compiled_source(...)` — the derived .scm (diagnostics).
- Job-2 stubs:
  ```python
  from tsquery.stubs import generate_stubs
  generate_stubs(lang.schema, out="node_stubs.pyi")
  ```

## Errors

`ExtractionError` (one `MatchFailure` per failed match: pattern, span,
snippet, pydantic errors), `SchemaCheckError` (at validate_with, before
parsing), `AmbiguousCaptureError`, `UnsupportedShapeError`,
`CoercionError`, and `WasmRuntimeUnavailableError` for a `.wasm` bundle
without the wasm runtime (see ../../docs/architecture.md §3.1).

## Facts that matter

- Community grammars ship no schema — derive one from the grammar source
  with `tsgrammar.schema_tool` (B-side) or bind none (schema-less path).
- `tree-sitter>=0.26` is the floor (0.26-only APIs are used).
- The light install (`pydantree-tscore` + `pydantree-tsquery`) never
  imports tsgrammar — `import tsgrammar` fails there by design.
- Run in your own project with `uv pip install pydantree-tscore
  pydantree-tsquery`.
