# Typed-node filter semantics

This is the decision record for generated-node matching. A generated class is
a filter. It is not an assertion that every node of the anchor kind has the
declared shape.

## One selector

The declaration becomes a `Selector` with four parts:

- the anchor kind, including its schema-defined concrete subtypes;
- the normalized `__under__` ancestor path;
- each declared child's name, allowed kinds, optional and repeated flags; and
- each child's text predicates.

The recursive walk is the execution path. During the decision phase, a
tree-sitter query also used this selector and served only to discover
candidate anchors. The selector remained the definition of what matched, and
the two paths returned candidates in document-preorder. The benchmark showed
that the compiled query added cost without a material win, so Phase C removed
that generated-query path. Raw `__raw_query__` remains available as the
explicit escape hatch.

## Filter rules

An anchor matches when its kind and ancestor path match. A required,
non-repeated, non-projection child must be present with an allowed kind. Its
predicates must also pass. A candidate that fails one of these checks is a
non-match and is skipped before typed materialization.

Optional fields may be absent. Repeated fields may be empty and are resolved
as collections. Mapping projections are resolver-owned. These declarations
still appear in the selector so later execution layers can inspect them, but
they do not reject an anchor during this filter step.

After an anchor passes the filter, pydantree materializes the typed row. A
real scalar, literal, mapping-projection, or codec failure is an error; an
expected schema alternative is not. Direct fields whose declared value is a
`Node` are lazy: the row keeps the CST child and resolves it on first
attribute access, caching either the value or the local exception. The
anchor's `span` and `__value__()` are available immediately. `model_dump()`
and `model_dump_json()` resolve any remaining lazy fields before serializing.

## Public and execution surface after Phase C/D1

The top-level `pydantree_sitter.__all__` remains the following list:

```text
Node, Grammar, Span, generate_module, build_namespace, load_bundle,
NodeSchema, PydantreeSitterError, SchemaCheckError, SchemaDataError,
SchemaDriftError, SchemaDistributionError, SchemaMissingError, ShapeError,
ExtractionError, Pattern, PatternMatch, Edit, ReplaceResult
```

`Grammar.query_source`, `find.query_source`, the generated `_query_walk`, and
the `pydantree_sitter.emit` compatibility module are removed. The inspectable
`Selector` and `SelectorChild` live in `pydantree_sitter.find`. `raw.Query`,
`raw.Cursor`, `raw.MatchView`, `raw.RawQuery`, and capture validation remain.
The structural front end is available from both `pydantree_sitter.pattern`
and the top-level package: `Pattern`, `PatternMatch`, `Edit`, and
`ReplaceResult`. `GrammarAgreement`, `agreement_for`, and `measure_agreement`
remain in `pydantree_sitter.agreement` for the installed wheel-grammar path
and its explicit regeneration evidence.

## Worked example: `let _ = ...`

Rust permits an anonymous pattern in code such as:

```rust
let _ = Vec::from_raw_parts_in(ptr, len, cap, alloc);
```

The anonymous `_` token is not one of the named pattern kinds declared for a
typed `LetDeclaration`. Therefore the `LetDeclaration` selector rejects that
node. It does not return a partial row, and it does not raise merely because
the node has the right anchor kind.

The same rule applies when the node appears inside a function body. The
function selector matches its own declared fields; a nested declaration is a
separate candidate. Direct nested fields are lazy in the current resolver, so a
nested resolution failure is local to the field that is read.
That performance and locality change does not change this matching decision.
