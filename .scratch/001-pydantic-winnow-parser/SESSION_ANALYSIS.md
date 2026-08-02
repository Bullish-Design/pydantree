# Pydantic-authored, Rust-executed parser combinators

## Purpose

This note captures the design conclusions reached while reviewing
`WINNOW_PYO3_PYTHON_COMBINATORS_CONCEPT.md`.  The proposed product is a Python
parser-combinator system in which Python describes the grammar and a Rust
runtime executes it.  The additional direction explored here is to make
Pydantic models the familiar, reusable authoring surface for typed parser
fragments.

The original proposal is preserved alongside this note as
`WINNOW_PYO3_PYTHON_COMBINATORS_CONCEPT.md`.

## Core conclusion

The underlying technical premise is sound:

> Python owns parser descriptions; Rust owns parsing execution.

The Python-to-Rust transition should occur once per top-level parse (or batch),
not once per token, combinator, match, or semantic action.  Python constructs
an immutable grammar graph; Rust validates, optimizes, compiles, and executes
that graph.  Parsing should produce native scalar values, spans, and arena
nodes, with Python objects materialized only when requested.

This makes the useful performance promise precise: parsing happens in Rust
without repeated Python boundary crossings.  It should not promise identical
performance to hand-written, monomorphized Winnow for every grammar.  A
generated-native backend can later narrow that gap for stable, hot grammars.

## Architecture retained from the original concept

The following choices remain the recommended foundation:

- **Grammar as immutable data.**  Python combinators create nodes in a
  backend-neutral IR rather than wrapping arbitrary Winnow trait objects.
  This enables validation, optimization, introspection, serialization,
  deterministic hashing, and more than one backend.
- **Rust-owned dynamic runtime first.**  A compact recursive evaluator or VM
  executes normalized instructions over per-parse state.  It may reuse Winnow
  primitives where useful, but should not be forced into a graph of boxed,
  deeply dynamic parser traits.
- **Compiled-parser immutability.**  One immutable compiled grammar is safely
  reused across parses; each parse owns its cursor, checkpoints, values,
  diagnostics, and limits.  This enables concurrency without a global mutex.
- **Span-first output.**  Captured text is represented by input offsets rather
  than eagerly allocated Python strings.  A lazy result arena can expose
  source-backed text and typed values on demand.
- **Explicit callback policy.**  Arbitrary Python code is an opt-in slow path.
  Pure Rust/native transforms preserve detached execution and concurrency.
- **Generated native backend later.**  Lowering an IR to ordinary Winnow source
  can be valuable, but content-addressed compilation, platform artifacts,
  source maps, cache security, and toolchain requirements make it a later
  optimization rather than the initial delivery path.

## What Pydantic should do

Pydantic can make the system considerably more approachable if it serves as
the typed model and schema language for parser fragments.  A `ParserModel`
or `WinnowModel` can be a reusable component whose fields describe the output
node and whose parser fragment produces that node.

Pydantic is particularly useful for:

- field names, types, nested model relationships, lists, enums, literals, and
  discriminated unions;
- normal Pydantic construction and serialization at the application boundary;
- documentation and type-checking surfaces;
- a supported subset of field constraints that can lower to Rust predicates
  (for example numeric bounds, enum membership, and selected string rules);
- an ergonomic entry point such as `Model.model_validate(text)` or
  `Model.parser().parse(text)`.

The intended flow is:

```text
Pydantic model definitions + parser declarations
        -> canonical parser IR
        -> Rust validation / optimization / compilation
        -> Rust-only parse to native values and spans
        -> optional Pydantic model materialization and normal validation
```

Pydantic instances should normally be materialized at the end, not allocated
throughout parsing.  Source spans should remain in the parse result or a side
table keyed by node/field; ordinary Pydantic values should not need to carry
source-location machinery in every field.

## What Pydantic cannot infer

A data model is not a full grammar.  Normal Pydantic field declarations do not
unambiguously encode:

- token order, delimiters, or comments;
- whitespace and lexing policy;
- discarded syntax that has no result field;
- alternatives with overlapping prefixes;
- lookahead, commits/cuts, recovery, or backtracking policy;
- repetition separators and trailing-separator rules;
- operator precedence and associativity;
- text-vs-bytes behavior and streaming semantics.

For narrow convention-driven formats, some syntax can be inferred.  General
parser combinators cannot be inferred honestly from output shape alone.  The
project must therefore retain an explicit structural grammar language.

## Pydantic validators are not the grammar language

Using Pydantic's existing metadata and class lifecycle is desirable.  Co-opting
`@field_validator` or `@model_validator` as the parser-combinator language is
not recommended.

Those decorators conventionally mean “run Python over a value that already
exists.”  Parser operations such as `skip("=")`, `peek`, `cut`, whitespace,
or Pratt parsing are syntactic control operations that often produce no value
and must run before a model can exist.  Reusing validator names for a hidden
Rust grammar would make normal Pydantic behavior surprising; allowing the
validators to run during parse would also put Python back on the hot path.

The recommended policy is:

| Pydantic capability | Recommended parser treatment |
| --- | --- |
| fields / nested models / types | output schema and reusable model fragments |
| supported `Field` constraints | compile to native Rust predicates |
| `Literal`, enum, tagged union | lower to literals/choices when syntactically defined |
| ordinary field/model validators | run after Rust parsing by default |
| arbitrary Python hooks | explicit post-parse or immediate-callback slow path |

An optional strict profile should reject ordinary Python validators and
unsupported defaults so callers can guarantee an entirely Rust-native parse
and validation path.

## Preferred public API direction

Keep model attributes clean and use an explicit, first-class grammar expression
that binds parser results to model fields.  It can be declared outside a model,
or through a dedicated parser-specific registration mechanism, but should not
pretend to be a Pydantic validator.

For example:

```python
class Assignment(WinnowModel):
    name: str
    value: int


assignment = parser_model(Assignment).seq(
    field("name", identifier),
    skip("="),
    field("value", integer),
)
```

This is a named, typed, reusable Pydantic chunk with clear syntax.  It
composes naturally:

```python
document = assignment.repeat(separator=skip("\n")).as_model(Document)
```

For class-local organization, a purpose-built decorator can be acceptable:

```python
@parser_model
class Assignment(BaseModel):
    name: str
    value: int

    @grammar.entrypoint
    @classmethod
    def parser(cls, p):
        return p.seq(
            p.field("name", identifier),
            p.skip("="),
            p.field("value", integer),
        )
```

The class-method form keeps output fields clean, but it is not inherently
better than the external expression.  The external form is less magical and
may be easier to compose, cache, inspect, and test.  Supporting both is
reasonable if both lower to exactly the same IR.

`Annotated` metadata is another possible Pydantic-compatible notation for
simple field-local parsing, but it becomes dense for discarded syntax,
lookahead, expression grammars, and complex alternatives.  It should be a
convenience layer, not the only grammar form.

## Callback semantics

The distinction between native and Python actions must be made visible.

- Native transformations such as integer conversion, range checks, escape
  decoding, enum lookup, and AST construction belong in the IR and run in
  Rust.
- A deferred Python action may run only after the parse has selected a
  successful path.  Since its result cannot influence subsequent recognition,
  it should not masquerade as an ordinary `map` combinator.
- An immediate Python callback may influence subsequent parsing, but requires
  reacquiring Python and prevents a fully native backend.  It must be an
  explicitly named, restricted, measurable escape hatch.

Ordinary Pydantic validators fit most naturally in the first post-parse Python
materialization phase, not inside parser execution.

## Product and scope advice

The complete original roadmap is ambitious: it is a parser platform, not a
thin binding package.  The initial implementation should prove the central
value before adding broad capabilities.

Recommended MVP:

1. Text input only; no streaming, plugins, code generation, or arbitrary
   Python callbacks.
2. A small IR with literals, character classes, sequence, choice, optional,
   repetition, discarded tokens, captures, nodes, cuts, complete/prefix parse,
   and structured errors.
3. Pydantic models as output schemas and reusable parser chunks, with a clear
   explicit structural grammar expression.
4. Rust arena results and span-backed captures, plus opt-in Pydantic
   materialization.
5. Benchmarks against hand-written Winnow, a representative pure-Python
   approach, and the same grammar with eager vs lazy conversion.

Defer recursion/Pratt parsing until the core semantics are stable; defer bytes
and streaming until the runtime representation can support suspension; defer
native source generation until measured dynamic-runtime overhead warrants its
complexity.

## Validation experiment

The first technical spike should implement a representative configuration or
JSON-subset grammar three ways:

1. hand-written Winnow;
2. Pydantic-shaped parser IR executed by the dynamic Rust runtime;
3. optionally, IR-generated Winnow source.

Measure valid and malformed small/large documents, nested input, validation
only, span/arena results, and eager Pydantic materialization separately.  The
decision to build source generation should follow these measurements rather
than an assumed target such as “within 10% of native.”

## Naming and positioning

If the dynamic runtime directly implements substantial normalized-combinator
semantics, the public project should not be constrained to being merely a
“Winnow binding.”  A more accurate positioning is:

> Pydantic-authored parser combinators, compiled to a Rust-executed parser;
> Winnow supplies compatible semantics, primitives, and an optional native
> code-generation backend.

That preserves the value of Winnow without overstating that every runtime path
is a direct wrapper around its Rust trait API.
