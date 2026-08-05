# pydantree — user guide

You are a developer building your own project on top of pydantree. There are
two products:

- **`pydantree_sitter` (Product A)** — pull **typed data** out of text for which a
  tree-sitter grammar exists (a community grammar like tree-sitter-python,
  or one built by pydantree_sitter_grammar). You declare a model; pydantree derives the
  query, runs schema checks, and materializes typed rows.
- **`pydantree_sitter_grammar` (Product B)** — **author a grammar** as a Pydantic DSL when
  no community grammar exists (or you need a custom one), build it, and ship
  it as a bundle or consume it directly.

Both are Pydantic-native. The node-schema bridge is the differentiator:
model↔grammar and capture↔type checks run **before any text is parsed**.

---

## 1. Installation

```bash
# A (consumption) — light: no toolchain
uv pip install pydantree-sitter
uv pip install tree-sitter-json tree-sitter-python   # community grammars

# B (authoring) — heavy: needs the tree-sitter CLI + a C compiler at build time
uv pip install pydantree-sitter-grammar
```

The distributions are the collision-proof pydantree-sitter names; the import
packages are `pydantree_sitter` / `pydantree_sitter_grammar`. A never imports
B: `import pydantree_sitter_grammar` fails in a light install (the seam is
enforced at install time).

---

## 2. Product A — typed extraction (`pydantree_sitter`)

### 2.1 The model IS the query

```python
from typing import Annotated
from pydantree_sitter import M, Matches, NodeKind, OutputModel, capture, source_meta
import tree_sitter_python

class Assignment(OutputModel):
    __match__ = M("module", "expression_statement", "assignment")
    name: Annotated[str, Matches(r"^[A-Z][A-Z_]*$")] = capture("left")
    value: Annotated[int, NodeKind("integer")] = capture("right")
    line: int = source_meta()

lang = Language.from_module(tree_sitter_python)
rows = lang.extractor(Assignment).extract(source_text)   # checks run here, once
rows = Assignment.extract(source_text, language=lang)    # sugar
# [Assignment(name='x', value=42, line=3), ...]
```

- `__match__ = M("module", "expression_statement", "assignment")` is the
  ancestor path of node kinds: `(module (expression_statement (assignment …)))`.
- `= capture("left")` binds the field to the CST field `left` (the attr name
  is the capture name). `= capture()` (no arg) means the attr name IS the
  field name.
- `source_meta()` injects the anchor's source position: `int` → 1-based line,
  `Span` → full byte span.
- An unmarked field is BOUND BY NAME in both modes (record mode: the record
  key; field mode: the CST field). A COMPUTED field is the marked case:
  `source: str = derived("spike")` (or bare `derived()` for an absent
  field) — a derived() field with no value raises at bind with a warning.

**Descendant matching:** `"..."` in the path matches any depth —
`M("module", ..., "call")` is every call anywhere under a module.

```python
class Call(OutputModel):
    __match__ = M("module", ..., "call")
    name: str = capture("function")
```

### 2.2 Captures and markers

| surface | what it does |
|---|---|
| `= capture("field")` | bind to a CST field (field mode) |
| `= capture_kind("code_span")` | bind to a CHILD BY NODE KIND — for grammars with positional children (real markdown), no CST fields |
| `= source_meta()` | anchor line (`int`) or span (`Span`) |
| `Annotated[T, Matches(re)]` | `(#match? @cap re)` predicate |
| `Annotated[T, Eq(v)]` | `(#eq? @cap v)` |
| `Annotated[T, AnyOf(a, b)]` | `(#any-of? @cap a b)` |
| `Annotated[T, NodeKind("integer")]` | constrain the matched node kind (tuple = alternation); schema-checked |
| `Annotated[str, Unescaped()]` | decode the string literal's escapes (JSON-first) — the schema check requires a string-wrapper shape |
| `= derived(value)` | a COMPUTED field — excluded from the query, materialized from the given value (D4.1: unmarked = bind-by-name) |
| `str \| None = capture(...)` | **optional capture**: matches WITHOUT the field still materialize (None) — a field-mode capture is query-optional iff the model can materialize without it |
| `list[T] = capture("field")` | **field-mode list**: merge the repeated field's matches across the shared anchor (the repeated field must sit ON the anchor node) |
| nested `OutputModel` | a field typed as another `OutputModel` materializes the nested node with the inner model |

### 2.3 Record mode (key/value documents)

For order-independent documents (JSON objects, INI sections, config records):

```python
class ServerSection(OutputModel):
    __match__ = M("source_file", "section", record=True)
    host: str
    port: int
    debug: bool = False
    title: str | None = None
    line: int = source_meta()

rows = ServerSection.extract(corpus, language=lang)
# [ServerSection(host='example.com', port=8080, debug=True, title='My App', line=2), ...]
```

- The record node is the anchor; the capture name = the record key (attr
  name, or `capture("key")` for an override).
- The value shape comes from a `ValueMap` (D6): the JSON builtin for the JSON
  family / a bundle's `value_map` metadata / your explicit `value_map=`.
  `propose_value_map(schema)` generates a REVIEWED DRAFT (never silent
  inference); record mode over a non-JSON grammar without a map is a
  bind-time `ShapeError`.
- A predicate field that does not match filters the WHOLE record (like the
  field-mode query engine).
- Nested `OutputModel` fields materialize nested records.

### 2.4 Schemas: the checks run before the parse

Binding runs Jobs 1/3/4 (model↔grammar, value-shape derivation,
capture↔type) at bind time — before any text:

```python
from pydantree_sitter import Language

# over a bundle (grammar.so + node-schema.json + metadata + loader)
lang = Language.load_bundle("dist/cfg-bundle")     # one call, checks bound
ext = lang.extractor(ServerSection)                # ALL checks run here, once
rows = ext.extract(corpus)

# over a bare community wheel: attach the schema explicitly
schema = "node-schema.json"                        # path, dict, or NodeSchema
lang = Language.load(tree_sitter_python.language(), schema=schema)
```

The compiled state lives on the Language instance, keyed by (model, strict)
— no class-level caches, no global registry (D5): a model bound against a
SECOND language re-checks (a silent cross-language result is impossible).
The JSON-family check is an exact kind-set check; record mode over a
non-JSON grammar needs a ValueMap (`propose_value_map` draft or a bundle
`value_map` entry). Community grammars ship no schema — see §4.

### 2.5 The rest of the A surface

```python
lang.name                    # the grammar name
lang.language                # the raw tree_sitter.Language
lang.schema                  # the bound NodeSchema or None
lang.parse(src)              # tree_sitter.Tree
lang.reparse(old_tree, new)  # incremental reparse (0.26 wrapped)

OutputModel.extract_tree(tree, ...)      # parse once, extract many models
OutputModel.compiled_source(...)         # the derived .scm (diagnostics)
ext.query_source                         # the bound query (diagnostics)
```

Errors (the taxonomy, §1.3): `ExtractionError` carries one `MatchFailure`
per failed match (pattern, anchor span, snippet, pydantic errors);
`AmbiguousCaptureError` / `ShapeError` / `SchemaCheckError` /
`QueryBuildError` / `BundleError` are the typed failure classes.

### 2.6 Typed CST codegen (typed node access)

Generate a `.pyi` beside the schema — per named kind: field accessors,
`get(field)` overloads, `children(kind)` overloads, supertype aliases:

```python
from pydantree_sitter.codegen import generate_typed_api
# REAL runtime classes (not .pyi fiction — F-A4): the module imports and runs
api_src = generate_typed_api(lang.schema, "mylang_api")
```

---

## 3. Product B — authoring grammars (`pydantree_sitter_grammar`)

### 3.1 A minimal grammar

```python
import pydantree_sitter_grammar as tg

g = tg.Grammar("cfg")

# lexical

g.rule("comment", tg.token(tg.choice(
    tg.seq("#", tg.pattern(r"[^\n]*")),
    tg.seq(";", tg.pattern(r"[^\n]*")))))
g.extra(tg.ref("comment"))
g.rule("integer", tg.pattern(r"[+-]?[0-9]+"))
g.rule("boolean", tg.choice("true", "false"))
g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_.-]*"), word=True)

# structure: values are a supertype (integer | boolean | identifier | …), so
# a record model can extract `host: str`, `port: int` AND `debug: bool` from
# the same pair field

g.rule("value", tg.choice(tg.ref("integer"), tg.ref("boolean"),
                          tg.ref("identifier")),
       supertype=True)
g.rule("entry", tg.seq(tg.field("key", tg.ref("identifier")), "=",
                       tg.field("value", tg.ref("value"))))
g.rule("section", tg.seq("[", tg.field("name", tg.ref("identifier")), "]",
                         tg.repeat(tg.ref("entry"))))
g.rule("source_file", tg.repeat(tg.ref("section")))
g.start("source_file")

# author-time static analysis (fast Python errors BEFORE the Rust step)
issues = list(tg.run_checks(g))
assert not tg.errors(g), issues
```

### 3.2 The DSL in one screen

| combinator | meaning |
|---|---|
| `tg.seq(a, b, c)` | sequence |
| `tg.choice(a, b)` | alternation |
| `tg.repeat(x)` / `tg.repeat1(x)` | 0+ / 1+ |
| `tg.opt(x)` | optional |
| `tg.field("name", x)` | CST field |
| `tg.token(x)` / `tg.immediate_token(x)` | token (no whitespace / immediate) |
| `tg.pattern(r"…")` | regex token |
| `tg.ref("rule")` | reference |
| `tg.blank()` | empty production |
| `tg.alias("name", named, x)` | alias |
| `tg.prec(n, x)` / `tg.prec_left` / `tg.prec_right` / `tg.prec_dynamic` | precedence |

Rule flags: `hidden=True` (`_name`), `inline=True`, `supertype=True`,
`word=True` (also the grammar's word token), `ambiguous=True` (opt into an
intentional GLR ambiguity — the dangling-else shape). Rule-level `alias=`
was DELETED (F-B1): `tg.alias(...)` is the one way.
Grammar methods: `g.start(name)`, `g.word(name)`, `g.extra(rule)`,
`g.external(tg.tok("NEWLINE"), ...)`, `g.conflict("a", "b")`,
`g.precedence("+", "*")` (a `Ladder` for expression grammars),
`g.replace_rule(name, body)` (the fix loop).

### 3.3 Expressions (the GLR-ergonomics layer)

```python
prec = g.precedence("or", "and", "not", "compare", "+", "*", "unary")

tg.expression(g, "expr",
    primary=tg.choice(tg.ref("number"), tg.ref("identifier")),
    infix=[("+", "left", "+"), ("*", "left", "*"),
           ("and", "left", "and"), ("or", "left", "or")],
    prefix=[("-", "unary"), ("not", "not")],
    postfix=[("call", "call", lambda e: tg.seq(e, "(", tg.repeat(tg.ref("expr")), ")"))],
    ladder=prec,
    cond_primary=tg.seq("(", tg.ref("expr"), ")"))
```

The ladder's level names are the helper's `level` strings — the ordering is
unambiguous and the same ladder is usable by raw rules. `semantic_smoke(g)`
runs a precedence smoke corpus. Conflicts are remapped to the author's DSL
source sites (`GrammarConflictError` names the rule, the production, and the
generator's suggested fix).

### 3.4 The conflict loop

`build_loop` is the fix-one-rerun loop: it yields each conflict error (with
the DSL source site + the suggested fix), calls your fix, and re-runs until
clean or `max_attempts`:

```python
def fix(error, g):
    ...  # error names the per-production DSL site; apply one fix

for event in tg.build_loop(g, fix=fix):
    if isinstance(event, tg.GrammarConflictError):
        print(event)
    else:
        result = event   # clean generate -> BuildResult
```

### 3.5 External scanners

Some languages need a C scanner (indentation, heredocs, matched delimiters).
Declare the externals in the scanner's expected order and pass the scanner
path to the build:

```python
g.external(tg.tok("NEWLINE"), tg.tok("INDENT"), tg.tok("DEDENT"))
# ...
result = tg.build_builder(g, scanner=tg.py_indent_scanner_path())
```

The scanner library ships five canonical scanners (see
[scanner-library.md](scanner-library.md)): `indent_scanner_path`,
`heredoc_scanner_path`, `matched_delimiter_scanner_path`,
`py_indent_scanner_path` (real Python logical-line semantics),
`bash_heredoc_scanner_path` (multi-heredoc queue). `tg.scanner_for(name)`
maps grammar names to their canonical scanner. A grammar with externals and
NO scanner raises `ExternalScannerRequiredError` (before gcc's link failure).

### 3.6 The corpus harness (systematic semantic guard)

`generate` being clean does NOT mean the grammar is right — the corpus
catches what generate cannot (it caught a real fixture bug on its first
outing):

```python
from pydantree_sitter_grammar.corpus import Corpus, corpus_case

corpus = Corpus([
    corpus_case("1 + 2 + 3;", "((number) + ((number) + (number)))",
                name="+ left-assoc", selector="expr"),
    corpus_case("if (a) { b(); }", "(if_stmt ...)", name="if with block"),
], name="qfilter")
result = corpus.run(grammar=g)            # or build_result=result
assert result.ok(), result.report()       # unified diffs per failure
```

`style="sexp"` (default, anonymous kept) vs `style="compact"` (smoke format,
first `expr` node); `selector=` renders the first node of a type;
`snapshots_dir=` writes grammar.json + node-schema.json beside the corpus
so grammar changes show up as reviewable diffs.

### 3.7 Shipping a bundle

```python
bundle = result.package("dist/cfg-bundle")   # grammar.so + node-schema.json
                                             # + tree-sitter.json + loader.py
# consumed B-free by A, one line:
lang = Language.load_bundle("dist/cfg-bundle")
```

`package(..., typed_api=True)` also drops `typed_api.py` — REAL typed CST
accessors generated from the schema (D7).

### 3.8 Community grammars (the schema tool)

A community grammar wheel ships no schema. Derive one from the grammar
SOURCE (a repo checkout with `src/grammar.json` — the standard layout):

```python
from pydantree_sitter_grammar.pipeline import build_from_source_dir, write_bundle
result = build_from_source_dir("tree-sitter-rust-checkout", name="rust")
bundle = write_bundle(result, "dist/rust-bundle")
# -> the same 4-file bundle, schema = the CLI's own node-types.json byproduct

from pydantree_sitter_grammar.schema_tool import derive_schema_for_dir
schema = derive_schema_for_dir("tree-sitter-json-checkout", out="node-schema.json")
```

CLI form: `python -m pydantree_sitter_grammar.schema_tool <grammar-dir> [-o out.json] [-n name]`.
The community path never touches the author's checkout (work happens in the
pipeline cache).

---

### 3.9 The rule-class surface ("the model IS the rule")

The builder DSL is the low-level surface. The rule-class surface is the
primary authoring path — the B-side mirror of Product A's "the model IS the
query": each grammar rule is a CLASS, the class body IS the production, and
`assemble()` compiles the classes into the very same builder `Grammar`
(no IR, pipeline, checks, or bundle change). The devenv example
(`examples/devenv-subset/grammar.py`) is authored this way.

```python
from typing import Literal

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar import (
    External, Extra, Pattern, R, Rule, Supertype, Token, assemble,
)
from pydantree_sitter_grammar.patterns import dotted_path, integer, rest_of_line

class Comment(Extra, Token):                 # behavioral kinds are MIXINS
    __body__ = tg.seq("#", tg.pattern(rest_of_line()))

class NamePath(Token):                       # token-wrapped regex leaf
    __pattern__ = dotted_path()

class Number(Pattern):                       # bare regex leaf
    __pattern__ = integer()

class StringFragment(External):              # external-scanner token
    """A `"..."` string body chunk (scanner.c)."""

class Pair(Rule):                            # the annotation form
    key: NamePath                            #   field("key", ref("name_path"))
    eq: Literal["="] = "="                   #   anonymous token "="
    value: Value
    semi: Literal[";"] = ";"

class Value(Supertype):                      # flag as a base class
    __body__ = tg.choice(R(String), R(Number), tg.ref("with_expr"))

def build() -> tg.Grammar:
    import sys
    return assemble("devenv", start=SourceFile,
                    rules=module_rules(sys.modules[__name__]))
```

**The kinds (the base-class list IS the flag list):** body kinds `Rule`
(annotation-bodied rules), `Pattern` (bare regex leaf), `Token` (body or
`__pattern__` wrapped in `token(...)`), `External` (external-scanner token;
the token name defaults to the rule name in SCREAMING_SNAKE, override with
`__external__`); behavioral mixins `Extra`, `Supertype`, `Hidden`,
`Inline`, `Word`. They compose: `class Comment(Extra, Token)`.

**Annotations are ordered children** (attribute order = production order;
the attribute name is the CST field):

| annotation | compiled to |
|---|---|
| `key: NamePath` | `field("key", ref("name_path"))` |
| `eq: Literal["="] = "="` | the anonymous token `"="` (the default MUST equal the Literal value — checked at `assemble()`, before any build) |
| `element: list[Value]` | `repeat(field("element", ref("value")))` — the field goes INSIDE the repeat |
| `content: list[X]` | `repeat(ref(...))` — the reserved label `content` = an UNNAMED child |
| `value: String \| Number` | `field("value", choice(ref, ref))` |
| `maybe: Number \| None` | `field("maybe", opt(ref))` |

**`__body__` is the escape hatch** for shapes annotations cannot express
(unnamed sequences, bare alternations): the combinator DSL as-is, with
`R(SomeClass)` as a class-typed reference (`R(Number)` compiles to the same
SYMBOL as `tg.ref("number")`). At the mutual-recursion CYCLE points a class
body evaluates at class creation, so a reference to a later-defined class
cannot use `R` — use `tg.ref("name")` there (the underlying DSL's own
spelling, zero new machinery):

```python
class WithExpr(Rule):
    __body__ = tg.seq("with", R(NamePath), ";", tg.ref("value"))  # value defined below
```

**Pattern helpers** (`pydantree_sitter_grammar.patterns`) are composable regex STRINGS in
the tree-sitter lexer subset: `ident(hyphen=)`, `integer()`, `quoted()`,
`slug()`, `path_literal()`, `dotted_path()`, `rest_of_line()`.

**Naming and rules of the road:** the rule name is snake_case of the class
name (acronym-aware, F-B4) — override a builtin collision with
`__rule_name__` (`class ListRule(Rule)` with `__rule_name__ = "list"`).
`assemble(name, *, start, rules=...)` takes the EXPLICIT class list (D9):
its order is load-bearing (rule order, and externals order — externals must
precede their rules in the scanner's expected order). `module_rules(module)`
collects the classes DEFINED IN a module (imported classes are excluded —
the silent-join bug died); function-local rule classes work with an
explicit list.

**When to use which surface:** rule classes for data-shaped rules (what
Product A's field/record mode consumes) — the annotation form reads as its
own declaration and gives finer-grained conflict sites (the error names
`Pair.value`, not a `tg.seq(...)` line). The builder DSL stays the home of
`prec*` ladders, `alias`, `immediate_token`, `reserved`, and maximal
control — it is the escape hatch `__body__` opens into.

**The byte-identity gate (the discipline):** the class surface is sugar over
the builder, and the suite enforces it — `tests/test_rules.py`
`test_gate_devenv_class_grammar_identical_to_builder_dsl` asserts the
class-authored devenv grammar (`tests/fixtures/devenv_builder_dsl_grammar.py`)
emits grammar.json DEEP-EQUAL to the builder-DSL spelling
(`examples/devenv-subset/grammar.py`). Any mapping row (field placement,
token wrapping, flag reading, helper output) that drifts from the DSL's IR
fails there first; each pattern helper is additionally pinned
byte-for-byte in `tests/test_patterns.py`.

---

## 4. Common flows, end to end

**Author a grammar, ship it, consume it (one project):**

```python
# authoring.py (B)
import pydantree_sitter_grammar as tg
g = tg.Grammar("cfg")
...  # rules as in §3.1
result = tg.build_builder(g)
bundle = result.package("dist/cfg-bundle")

# extraction.py (A — can live in a DIFFERENT process/venv, B-free)
from pydantree_sitter import Language, M, OutputModel, capture, source_meta
lang = Language.load_bundle("dist/cfg-bundle")

class ServerSection(OutputModel):
    __match__ = M("source_file", "section", record=True)
    host: str
    port: int
    debug: bool = False
    line: int = source_meta()

ext = lang.extractor(ServerSection)        # checks active before parsing
rows = ext.extract(text)
```

**Consume a community grammar (A only, no B anywhere):**

```python
from pydantree_sitter import M, NodeKind, OutputModel, capture
import tree_sitter_rust

class RustFn(OutputModel):
    __match__ = M("source_file", "function_item")
    name: str = capture("name")
    return_type: str | None = capture("return_type")   # optional capture

rows = RustFn.extract(rs_source, language=tree_sitter_rust)
```

---

## 5. The failure surface (what raises when)

| you did | you get |
|---|---|
| grammar with externals, no scanner | `ExternalScannerRequiredError` (names the externals) |
| conflicts in the grammar | `GrammarConflictError` (DSL source sites + suggested fixes) |
| model path/field impossible in the grammar | `SchemaCheckError` at `validate_with`, before parsing |
| capture type not producible by the kind | `SchemaCheckError` |
| a capture matches several nodes for a scalar | `AmbiguousCaptureError` |
| a type with no value shape (record mode, or a non-JSON grammar without a ValueMap) | `ShapeError` |
| a raw query's unknown capture / rejected .scm | `SchemaCheckError` / `QueryBuildError` |
| bundle metadata missing/invalid or an unknown bundle_format | `BundleError` |
| one or more matches fail to materialize | `ExtractionError` (per-match `MatchFailure`s) |
| a bundle's artifact is a `.wasm` with no runtime | `WasmRuntimeUnavailableError` (see the wasm verdict in `docs/architecture.md` §3.1) |

---

## 6. Version pins (verified facts)

tree-sitter CLI 0.25.3 / bindings 0.26.0 (ABI 13–15 all load; a
`tree-sitter.json` with metadata is needed for ABI 15) / pydantic ≥ 2.11 /
Python ≥ 3.11. The distributions pin `tree-sitter>=0.26`.
