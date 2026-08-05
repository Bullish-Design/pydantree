# pydantree_sitter

Product A — model-only typed extraction over tree-sitter grammars. Light
runtime: pydantree_sitter + the C runtime binding; no Rust CLI, no compiler
(CONCEPT §8).

```python
from pydantree_sitter import M, NodeKind, OutputModel, capture, source_meta
import tree_sitter_python

class Assignment(OutputModel):
    __match__ = M("module", "expression_statement", "assignment")
    name: str = capture("left")
    value: Annotated[int, NodeKind("integer")] = capture("right")
    line: int = source_meta()

rows = Assignment.extract(text, language=tree_sitter_python)
```

The `OutputModel` class IS the query. With a bound node-schema
(`Language.load_bundle(dir)` or `Language.load(lang, schema=...)`),
`validate_with` runs the model↔grammar and capture↔type checks before any
text is parsed.

See [docs/user-guide.md](../../docs/user-guide.md) §2 (users) and
[docs/architecture.md](../../docs/architecture.md) (the bridge).
