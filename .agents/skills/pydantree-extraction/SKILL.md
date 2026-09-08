---
name: pydantree-extraction
description: Consume schema-backed typed node universes with pydantree_sitter. Use for generated nodes, Pydantic narrowing, codecs, ancestor context, projections, Grammar, bundles, and the remaining raw-query escape hatch.
---

# pydantree extraction

The 0.3 API has one syntax noun: `Node`. Vendor the grammar's
`node-types.json`, generate a module, and narrow its classes:

```console
python -m pydantree_sitter.generate \
  --schema vendor/node-types.json \
  --language tree_sitter_python \
  --out mylang/python.py
```

```python
import mylang.python as py


class Assignment(py.Assignment):
    left: str
    right: py.Expression


rows = py.grammar.parse(source).find(Assignment)
```

Use `Grammar.load(language, schema)` for an in-memory namespace or
`Grammar.load_bundle(directory)` for a generated bundle. A schema is required;
it is the checked type universe. Generated modules carry a language fingerprint
and reject drift with `SchemaDriftError`.

## Declarations

- `x: SomeNode` resolves the CST field `x` to a nested node.
- `x: list[SomeNode]` resolves repeated children.
- `x: SomeNode | None` resolves an optional child.
- `content: ...` addresses unnamed children.
- `dict[str, V]` is sugar for one unambiguous key/value pair child.
- `__under__ = (py.Module, ..., py.FunctionDefinition)` adds rare ancestor
  context; the class's base kind remains the anchor.
- Pydantic validates narrowed scalar annotations after resolution.

Value decoding belongs on the node class. Override `__value__`, use
`pydantree_sitter.codecs.JsonString`, or pass a codec override module to the
generator with `--codecs`. `--suggest-codecs` prints stubs only; it writes no
metadata and is not part of the package root API.

`__raw_query__` remains the isolated escape hatch for sibling order, negation,
and multi-anchor joins. Keep it local and prefer typed fields for ordinary
extraction.

## Product B

`pydantree_sitter_grammar.Rule` subclasses share the same annotation grammar and
`NodeMeta`. `Rule.to_ir()` is the forward direction; generated `Node` classes
are the reverse direction. The round-trip test is
`tests/test_direction_roundtrip.py`.

## Evidence and gates

Run commands inside `devenv shell`. The fast gate is:

```console
pytest -q -m 'not slow'
ruff check src tests
ty check src
```

Keep the schema mandatory, and do not recreate the deleted legacy extraction
surface.
