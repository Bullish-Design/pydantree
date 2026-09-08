# pydantree-sitter

Typed tree-sitter nodes with Pydantic validation.

The schema is the type system. Vendor the grammar's `node-types.json`, generate
the node universe once, then narrow generated classes with ordinary annotations:

```console
python -m pydantree_sitter.generate \
  --schema vendor/python-node-types.json \
  --language tree_sitter_python \
  --out mylang/python.py
```

```python
import mylang.python as py


class Function(py.FunctionDefinition):
    name: str
    return_type: str | None


for function in py.grammar.parse(source).find(Function):
    print(function.name, function.return_type, function.span.line)
```

`Grammar.load(language, schema)` builds the same namespace in memory. A schema
is required: it supplies the checked node universe and lets generated modules
detect language drift. `list[Child]` means repeated children, nested node
subclasses resolve recursively, and `dict[str, V]` is the unambiguous
key/value projection. Ancestor context uses `__under__`.

Value decoding belongs on `Node.__value__`. Use
`pydantree_sitter.codecs.JsonString` for JSON strings or provide codec mixins
with `--codecs`. `--suggest-codecs` prints reviewable stubs and writes nothing.

Product B, `pydantree-sitter-grammar`, authors the same node declarations
forward into a tree-sitter grammar. Its `Rule` classes share Product A's
annotation grammar and metaclass.

## Documentation

- [Typed node universe](docs/typed-node-universe.md)
- [Filter semantics](docs/filter-semantics.md)
- [Architecture](docs/architecture.md)
- [Development](docs/development.md)
- [Scanner library](docs/scanner-library.md)
- [Agent skills](.agents/skills/)

The light package does not require the grammar-authoring toolchain. The
development environment is `devenv shell`; run `pytest -q -m 'not slow'` for the
fast gate, `ruff check src tests`, and `ty check src`.
