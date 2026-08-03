---
name: pydantree-grammar
description: Author tree-sitter grammars with tsgrammar (Product B) — the Pydantic DSL, static checks, the conflict loop, expressions/precedence ladders, external scanners, the corpus harness, bundles, and the community-grammar schema tool. Use when building or modifying a grammar for use with pydantree.
---

# pydantree — authoring grammars (tsgrammar, Product B)

Write tree-sitter grammars in Pydantic: `Grammar DSL -> grammar.json ->
tree-sitter generate -> gcc -> .so -> bundle`. Full reference:
`../../docs/user-guide.md` §3.

## The shape

```python
import tsgrammar as tg

g = tg.Grammar("cfg")
g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"), word=True)
g.rule("comment", tg.token(tg.seq("#", tg.pattern(r"[^\n]*"))))
g.extra(tg.ref("comment"))
g.rule("entry", tg.seq(tg.field("key", tg.ref("identifier")), "=",
                       tg.field("value", tg.ref("integer"))))
g.rule("source_file", tg.repeat(tg.ref("entry")))
g.start("source_file")

issues = list(tg.run_checks(g))     # author-time static analysis (Python,
assert not tg.errors(g), issues     # before the Rust step)
result = tg.build_builder(g)        # generate + gcc, content-addressed cache
lang, _lib = result.language()
```

## DSL cheat sheet

- `seq / choice / repeat / repeat1 / opt / field / token / immediate_token /
  pattern / ref / blank / alias / prec / prec_left / prec_right /
  prec_dynamic`
- Rule flags: `hidden` (`_name`), `inline`, `supertype`, `alias`, `word`,
  `ambiguous` (opt into an intentional GLR ambiguity, e.g. dangling-else).
- Grammar methods: `start`, `word`, `extra`, `external`, `conflict`,
  `precedence` (a `Ladder`), `replace_rule` (the fix loop).
- External scanners: `g.external(tg.tok("NEWLINE"), ...)` in the scanner's
  expected order + `scanner=` to the build (see the `pydantree-scanners`
  skill / `../../docs/scanner-library.md`).

## Conflicts (the fix-one-rerun loop)

`build_builder` remaps generator conflicts to your per-production DSL source
sites (`GrammarConflictError`). The loop is the intended authoring cadence:

```python
def fix(error, g): ...   # error names the DSL site + the suggested fix
for event in tg.build_loop(g, fix=fix):
    if isinstance(event, tg.GrammarConflictError):
        print(event)
    else:
        result = event   # clean generate
```

## Expressions (precedence ladders)

```python
prec = g.precedence("or", "and", "not", "compare", "+", "*", "unary")
tg.expression(g, "expr",
    primary=tg.choice(tg.ref("number"), tg.ref("identifier")),
    infix=[("+", "left", "+"), ("*", "left", "*")],
    prefix=[("-", "unary")],
    postfix=[("call", "call", lambda e: tg.seq(e, "(", tg.repeat(tg.ref("expr")), ")"))],
    ladder=prec,
    cond_primary=tg.seq("(", tg.ref("expr"), ")"))
tg.semantic_smoke(g)    # precedence smoke corpus
```

## The corpus harness (don't skip it)

`generate` being clean is NOT proof of correctness — the corpus catches
semantic regressions (associativity flips, ladder reorders, dropped
supertypes) that generate-clean code ships anyway:

```python
from tsgrammar.corpus import Corpus, corpus_case
corpus = Corpus([
    corpus_case("1 + 2 + 3;", "((number) + ((number) + (number)))",
                name="+ left-assoc", selector="expr"),
], style="compact", snapshots_dir="corpus_snap/")
result = corpus.run(grammar=g)
assert result.ok(), result.report()
```

## Shipping + community grammars

```python
bundle = result.package("dist/cfg-bundle")     # 4-file bundle for A

from tsgrammar.schema_tool import build_community_bundle, derive_schema_for_dir
build_community_bundle("tree-sitter-rust-checkout", "dist/rust-bundle", name="rust")
schema = derive_schema_for_dir("grammar-src-dir", out="node-schema.json")
```

## Facts that matter

- ABI 15 needs a `tree-sitter.json` with metadata (the pipeline writes it).
- Externals without a scanner -> `ExternalScannerRequiredError` (before gcc).
- Builds are cached by grammar hash + scanner digest + toolchain; use a fresh
  `cache_dir=` when iterating.
- Run everything through `devenv shell`; the venv resolves `src/` directly
  (the `_pydantree_src.pth`), so new files are immediately importable — no
  reinstall. `uv lock` after dependency changes.
- Real example grammars to copy from: `../../../../.scratch/006-tsquery-bridge/cfg_grammar.py`
  (a config language), `../../../../.scratch/009-phase7/{pyindent,bashmini}.py`
  (scanner grammars), `tests/fixtures/rust/` (a real community grammar).
