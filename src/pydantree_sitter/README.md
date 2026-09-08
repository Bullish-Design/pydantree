# pydantree_sitter

The light package consumes a vendored tree-sitter schema as a typed node
universe. Generate a module or build one in memory, then parse and traverse:

```python
from pydantree_sitter import Grammar
from pydantree_sitter.schema import NodeSchema

schema = NodeSchema.from_node_types_json("vendor/node-types.json")
grammar = Grammar.load(language, schema)
rows = grammar.parse(source).find(grammar.nodes.FunctionDefinition)
```

Every schema-backed node has a `Span`; scalar decoding is supplied by the
node's `__value__` codec. `Grammar.load_bundle()` consumes the five-file
artifact emitted by Product B without importing the heavy package.
