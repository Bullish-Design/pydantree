# tsgrammar

Product B — author tree-sitter grammars in Pydantic. Heavy build tool:
tscore + the tree-sitter CLI + a C toolchain; produces the artifacts A
consumes (CONCEPT §8).

```python
import tsgrammar as tg

g = tg.Grammar("cfg")
g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"), word=True)
g.rule("entry", tg.seq(tg.field("key", tg.ref("identifier")), "=",
                       tg.field("value", tg.ref("integer"))))
g.rule("source_file", tg.repeat(tg.ref("entry")))
g.start("source_file")
result = tg.build_builder(g)          # generate + gcc (cached)
bundle = result.package("dist/cfg-bundle")   # 4-file bundle for A
```

Also ships: the GLR-ergonomics layer (`precedence` ladders + the conflict
fix-one-rerun loop), the external-scanner library (`scanners/` — five
canonical scanners on the airtight mechanism), the corpus harness
(`tsgrammar.corpus`), and the community-grammar schema tool
(`tsgrammar.schema_tool`).

See [docs/user-guide.md](../../docs/user-guide.md) §3 (users),
[docs/scanner-library.md](../../docs/scanner-library.md) (the scanner
mechanism), [docs/development.md](../../docs/development.md) (the
workflow).
