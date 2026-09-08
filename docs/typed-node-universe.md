# Typed node universe

The schema-backed API uses one noun for syntax nodes: `Node`. Generate a
module once from the grammar's `node-types.json` file, then narrow generated
classes with ordinary Pydantic annotations.

```console
python -m pydantree_sitter.generate \
  --schema vendor/node-types.json \
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

`Grammar.load(language, schema)` is the in-memory equivalent. A schema is
required; it is the grammar's checked node type universe. `list[Child]` means
repeated CST children, nested `Node` subclasses are resolved recursively, and
`dict[str, V]` is the unambiguous key/value projection. Ancestor context is
declared with `__under__ = (py.Module, ..., py.FunctionDefinition)`.

Value decoding belongs on the node class as `__value__`. JSON string decoding
is available as `pydantree_sitter.codecs.JsonString`; custom codec mixins can
be supplied to the generator with `--codecs module_name`. The
`--suggest-codecs` mode only prints reviewable stubs and never writes files.
