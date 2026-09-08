# User guide

## 1. Vendor the schema

Product A requires the grammar's `node-types.json`. Community grammar wheels
usually do not ship it, so vendor the file from the grammar source repository.
The schema is load-bearing: generated modules record the language fingerprint
and `Grammar` verifies the schema against the loaded language.

## 2. Generate the node universe

```console
python -m pydantree_sitter.generate \
  --schema vendor/python-node-types.json \
  --language tree_sitter_python \
  --out mylang/python.py
```

The generated module contains one `Node` subclass per named grammar kind,
supertype aliases, `KIND_MAP`, and `grammar`. The in-memory equivalent is
`build_namespace(schema)`; both renderings use the same class specifications.

## 3. Narrow and extract

```python
import mylang.python as py


class Function(py.FunctionDefinition):
    name: str
    return_type: str | None


rows = py.grammar.parse(source).find(Function)
for row in rows:
    print(row.name, row.return_type, row.span.line)
```

`Grammar.load(language, schema)` is useful when the language and schema are
available at runtime. A path is application data, not a package dependency:

```python
from pydantree_sitter import Grammar
from pydantree_sitter.schema import load_schema

grammar = Grammar.load(language, schema_path, schema_name="python")
rows = grammar.parse(source).find(Function)
```

`load_schema` raises `SchemaMissingError` when the vendored file is absent and
`SchemaDataError` when it is malformed or empty. `Grammar.load` raises
`SchemaDriftError` when the schema contains alien kinds or fields, or omits too
many language kinds. The check allows a bounded set of omitted language kinds,
because a grammar can expose ABI kinds that its schema omits. It exempts
schema supertype entries because the ABI does not expose them as concrete
kinds. It uses `Language.supertypes`; the per-ID supertype predicate is not
reliable on the supported runtime.

The check proves that the schema and language vocabulary are compatible. It
does not prove that they came from the same release or that every field
relation is identical. Keep a provenance file beside each vendored schema.
Record `schema_file`, `grammar`, `source_repository`, `source_package`,
`source_commit`, `acquired`, `license`, `tree_sitter_runtime`, `language_abi`,
`schema_sha256`, and `grammar_semantic_version`.

Remediation:

- `SchemaMissingError`: install or vendor the grammar's `node-types.json`.
- `SchemaDataError`: replace the malformed, invalid, or empty file.
- `SchemaDriftError`: obtain the schema for the loaded grammar, then check its
  provenance and hash.

Set `verify=False` only for tests that intentionally bind a synthetic schema
to an unrelated real language. Do not use it for shipped artifacts.

## 4. Annotation rules

The class annotation is the projection:

| Annotation | Meaning |
| --- | --- |
| `child: py.Expression` | one named CST field |
| `children: list[py.Expression]` | repeated child field |
| `child: py.Expression | None` | optional field |
| `content: list[py.Expression]` | repeated unnamed children |
| `kind: py.Name | py.String` | kind choice |
| `token: Literal["="]` | anonymous literal token |
| `entries: dict[str, str]` | unambiguous key/value projection |

Nested node classes use their own resolver, so nested projections are ordinary
annotations rather than a separate record pipeline. If a dictionary projection
has zero or multiple possible pair kinds, class creation raises `ShapeError`
and suggests `list[Pair]` with an explicit pair class.

Use `__under__ = (py.Module, ..., py.FunctionDefinition)` only when an
anchor kind is not sufficient. `...` is a gap over any number of ancestors.

## 5. Value codecs

The default `Node.__value__` returns source text. A node can override it:

```python
from pydantree_sitter.codecs import JsonString


class String(JsonString, py.String):
    pass
```

The return annotation declares the value type. `--codecs module_name` lets the
generator select override classes, and `--suggest-codecs` only prints stubs.
JSON escape decoding, including lenient raw-newline input, is provided by
`JsonString`.

## 6. Raw queries

`__raw_query__` remains an isolated escape hatch for sibling order, negation,
or multi-anchor joins. Keep ordinary extraction on typed node subclasses.

## 7. Product B

`pydantree_sitter_grammar.Rule` uses the same annotation grammar. Its
`to_ir()` method compiles the shared `NodeMeta`/`Child` declaration forward to
the grammar builder. The D12 round-trip is covered by
`tests/test_direction_roundtrip.py`.

## 8. Errors and gates

The typed core exposes `SchemaCheckError` for class/schema mismatches,
`SchemaDriftError` for generated-language drift, `ShapeError` for unmappable
annotations, and `ExtractionError` for per-match failures.

Run the development gates inside `devenv shell`:

```console
pytest -q -m 'not slow'
ruff check src tests
ty check src
```
