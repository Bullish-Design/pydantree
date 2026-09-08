# wheel-extract — typed nodes over a community wheel

This toolchain-free example vendors the complete schema from the
tree-sitter-python source distribution, loads it with the
`tree_sitter_python` wheel, and finds typed nodes through `Grammar`.
The adjacent provenance file records the source and compatibility policy.

The runtime wheel does not contain community schemas. Install a grammar wheel,
vendor its exact `node-types.json`, then pass the path to `Grammar.load`:

```python
grammar = Grammar.load(language, "vendor/python-node-types.json",
                       schema_name="python")
```

The schema is application data. Product B is needed only when deriving a
schema from grammar source or building a bundle.

```bash
python examples/wheel-extract/extract.py
python examples/wheel-extract/extract.py --update
```

The committed transcript shows schema loading, parsing, typed-node traversal,
and a byte-for-byte ground-truth check. It needs no tree-sitter CLI and no
compiler.
