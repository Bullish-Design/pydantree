# Architecture

The project has two products and one shared declaration seam. Product B authors
a grammar and emits a parser bundle. Product A consumes that bundle or a
vendored schema with generated, schema-backed `Node` classes.

```text
Product B: Rule classes / Grammar DSL -> grammar.json -> tree-sitter -> grammar.so
                                                    \-> node-types.json
                                                    \-> node-schema.json
                                                             |
                                                             v
                         grammar.so + node-schema.json + metadata + loader.py
                                                             |
Product A: Grammar.load_bundle() -> Grammar -> Tree -> typed Node instances
```

The schema is the CLI byproduct. It is not inferred from a consumer model and
it is not optional. This gives generated classes a closed universe of kinds,
fields, children, optionality, and repetition. `NodeMeta` validates narrowed
classes against that universe when the class is created.

## Packages

`pydantree_sitter` is the light runtime: `Node`, `NodeMeta`, `Span`,
`NodeSchema`, generation, bundle loading, typed traversal, codecs, and the
isolated raw-query escape hatch. It never imports Product B.

`pydantree_sitter_grammar` is the heavy authoring/build package: the grammar
DSL, rule classes, static checks, conflict reports, corpus harness, scanners,
and the generate/compile/package pipeline. It depends on the light package so
the direction of the dependency remains one-way.

## Bundle contract

```text
bundle/
  grammar.so
  node-schema.json
  nodes.py
  tree-sitter.json
  loader.py
```

`tree-sitter.json` names the exported grammar symbol, artifact, schema, ABI,
toolchain, and bundle format. The shared loader keeps the native library alive
and accepts format 1 as well as the current format 2. `Grammar.load_bundle()`
loads the schema and builds the same in-memory namespace as `build_namespace()`.

The community path uses the grammar source directory's own `node-types.json`
byproduct. The light wheel does not need the CLI or a compiler; a consumer
vendors the schema when a community wheel omits it. We do not publish a generic
schema data wheel because schemas are coupled to one grammar source and version.
Applications keep the schema beside their generated nodes and may keep a small
provenance file beside it. `load_schema` reports missing and malformed data;
`Grammar.load` verifies the schema vocabulary against the loaded language at
bind time. Alien kinds and fields fail. Missing kinds use a 25 percent ratio
threshold because a grammar can omit valid ABI kinds. Schema supertypes are
exempt from the existence check. The check uses `Language.supertypes`, not
`Language.node_kind_is_supertype()`, because the per-ID predicate is unreliable
on tree-sitter 0.26. `schema_name` remains an optional extra name check.

## Product A runtime

`Grammar` owns a `tree_sitter.Language`, a required `NodeSchema`, and a typed
namespace. `Grammar.parse()` returns a `Tree` carrying that grammar. `Tree.find`
walks one parsed tree, checks the requested anchor's normalized `__under__`
path, and calls the class resolver. A resolver materializes nested nodes,
lists, optional children, literal tokens, scalar text, and unambiguous
`dict[str, V]` projections. The tree bounds recursion; there is no second
binding or extraction compiler.

`Span` is attached to every node. The default `Node.__value__` returns source
text; codec mixins such as `JsonString` override it for decoded scalar values.
Predicates that cannot be represented by the type system remain local
`Annotated` metadata, while `raw.Query` is the escape hatch for sibling order,
negation, and multi-anchor joins.

The public root surface is intentionally small:
`Node`, `Grammar`, `Span`, generation, bundle loading, `NodeSchema`, and the
five public error classes. The module-level surface is tested exactly so the
old extraction vocabulary cannot regrow through a convenience import.

## Product B direction

Product B rule classes use the same `NodeMeta`/`Child` annotation grammar as
generated Product A classes. `Rule.to_ir()` is the forward direction; the
generated module is the reverse direction. `tests/test_direction_roundtrip.py`
compares their child shapes, and the bundle tests exercise the artifact seam.

The authoring/build pipeline is:

```text
Grammar -> IR -> grammar.json -> tree-sitter generate -> parser.c
       -> optional external scanner -> gcc -> grammar.so -> bundle
```

The pipeline cache is content-addressed by grammar, scanner, grammar name, and
toolchain. Static grammar checks run before generation; conflict diagnostics
retain the raw CLI evidence and map it back to DSL sites.

## Structural patterns

`pydantree_sitter.pattern` is an independent ast-grep integration for finding
and rewriting structural text. It is not part of typed traversal. It resolves
ast-grep ranges against the exact node and byte range in pydantree's parse,
then returns edit data without writing files. The deferred decision to remove
that extra is tracked in the refactor guide; the typed core does not depend on
it.

## Development map

```text
src/pydantree_sitter/
  nodes.py       NodeMeta, Child, Node, annotation grammar, resolver
  grammar.py     Grammar and Tree
  find.py        typed anchor traversal
  generate.py    schema -> source / in-memory namespace
  schema.py      node-types schema model
  span.py        immutable source spans
  codecs.py      scalar value codecs
  raw.py         literal query escape hatch
  loader.py      native bundle loading
  match.py       ancestor-path matcher
  errors.py      typed error taxonomy
src/pydantree_sitter_grammar/
  ir.py builder.py rules.py checks.py conflicts.py expressions.py
  corpus.py pipeline.py schema_tool.py scanners/
tests/
  test_nodes.py test_generate.py test_grammar_nodes.py test_bundle.py
  test_codecs.py test_raw.py test_direction_roundtrip.py
```

All commands run inside `devenv shell`. The gates are `pytest -q`,
`ruff check src tests examples`, and `ty check src`.
