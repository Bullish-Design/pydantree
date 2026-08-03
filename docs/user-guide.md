# pydantree — user guide

You are a developer building your own project on top of pydantree. There are
two products:

- **`tsquery` (Product A)** — pull **typed data** out of text for which a
  tree-sitter grammar exists (a community grammar like tree-sitter-python,
  or one built by tsgrammar). You declare a model; pydantree derives the
  query, runs schema checks, and materializes typed rows.
- **`tsgrammar` (Product B)** — **author a grammar** as a Pydantic DSL when
  no community grammar exists (or you need a custom one), build it, and ship
  it as a bundle or consume it directly.

Both are Pydantic-native. The node-schema bridge is the differentiator:
model↔grammar and capture↔type checks run **before any text is parsed**.

---

## 1. Installation

```bash
# A (consumption) — light: no toolchain
uv pip install pydantree-tscore pydantree-tsquery
uv pip install tree-sitter-json tree-sitter-python   # community grammars

# B (authoring) — heavy: needs the tree-sitter CLI + a C compiler at build time
uv pip install pydantree-tsgrammar
```

The distributions are pydantree-branded; the import packages stay
`tscore` / `tsquery` / `tsgrammar`. A never imports B: `import tsgrammar`
fails in a light install (the seam is enforced at install time).

---

## 2. Product A — typed extraction (`tsquery`)

### 2.1 The model IS the query

```python
from typing import Annotated
from tsquery import M, Matches, NodeKind, OutputModel, capture, source_meta
import tree_sitter_python

class Assignment(OutputModel):
    __match__ = M("module", "expression_statement", "assignment")
    name: Annotated[str, Matches(r"^[A-Z][A-Z_]*$")] = capture("left")
    value: Annotated[int, NodeKind("integer")] = capture("right")
    line: int = source_meta()

rows = Assignment.extract(source_text, language=tree_sitter_python)
# [Assignment(name='x', value=42, line=3), ...]
```

- `__match__ = M("module", "expression_statement", "assignment")` is the
  ancestor path of node kinds: `(module (expression_statement (assignment …)))`.
- `= capture("left")` binds the field to the CST field `left` (the attr name
  is the capture name). `= capture()` (no arg) means the attr name IS the
  field name.
- `source_meta()` injects the anchor's source position: `int` → 1-based line,
  `Span` → full byte span.
- A field WITHOUT a capture and without a default always raises
  `ValidationError` (a model warning tells you at class creation).

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
- The value shape is DERIVED from the grammar's schema (the JSON-v1 hardcoded
  map is the fallback when no schema is bound).
- A predicate field that does not match filters the WHOLE record (like the
  field-mode query engine).
- Nested `OutputModel` fields materialize nested records.

### 2.4 Schemas: the checks run before the parse

Bind a node-schema and `validate_with` runs Jobs 1/3/4 (model↔grammar,
value-shape derivation, capture↔type) at bind time — before any text:

```python
from tsquery import Language

# over a bundle (grammar.so + node-schema.json + metadata + loader)
lang = Language.load_bundle("dist/cfg-bundle")     # one call, checks bound
ServerSection.validate_with(lang)                  # schema checks, no parse yet
rows = ServerSection.extract(corpus, language=lang)

# over a bare community wheel: attach the schema explicitly
schema = "node-schema.json"                        # path, dict, or NodeSchema
lang = Language.load(tree_sitter_python.language(), schema=schema)
```

The schema is bound to the Language INSTANCE (a nameless language is refused
registration; `register=True` opts into a name-keyed convenience).

Community grammars ship no schema — see §4 (the community tool derives one
from the grammar source) or `tscore.schema` directly.

### 2.5 The rest of the A surface

```python
lang.name                    # the grammar name
lang.language                # the raw tree_sitter.Language
lang.schema                  # the bound NodeSchema or None
lang.parse(src)              # tree_sitter.Tree
lang.reparse(old_tree, new)  # incremental reparse (0.26 wrapped)

OutputModel.extract_tree(tree, ...)      # parse once, extract many models
OutputModel.compiled_source(...)         # the derived .scm (diagnostics)
OutputModel.validate_with(language, schema=...)   # schema checks early
```

Errors: `ExtractionError` carries one `MatchFailure` per failed match
(pattern, anchor span, snippet, pydantic errors); `CoercionError` /
`AmbiguousCaptureError` / `UnsupportedShapeError` / `SchemaCheckError` are
the typed failure classes.

### 2.6 Job-2 stubs (typed node access)

Generate a `.pyi` beside the schema — per named kind: field accessors,
`get(field)` overloads, `children(kind)` overloads, supertype aliases:

```python
from tsquery.stubs import generate_stubs
generate_stubs(lang.schema, out="node_stubs.pyi")
```

---

## 3. Product B — authoring grammars (`tsgrammar`)

### 3.1 A minimal grammar

```python
import tsgrammar as tg

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
`alias=`, `word=True` (also the grammar's word token), `ambiguous=True`
(opt into an intentional GLR ambiguity — the dangling-else shape).
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
from tsgrammar.corpus import Corpus, corpus_case

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

### 3.8 Community grammars (the schema tool)

A community grammar wheel ships no schema. Derive one from the grammar
SOURCE (a repo checkout with `src/grammar.json` — the standard layout):

```python
from tsgrammar.schema_tool import build_community_bundle
build_community_bundle("tree-sitter-rust-checkout", "dist/rust-bundle",
                       name="rust")
# -> the same 4-file bundle, schema derived from the CLI's node-types.json

from tsgrammar.schema_tool import derive_schema_for_dir
schema = derive_schema_for_dir("tree-sitter-json-checkout", out="node-schema.json")
```

CLI form: `python -m tsgrammar.schema_tool <grammar-dir> [-o out.json] [-n name]`.

---

## 4. Common flows, end to end

**Author a grammar, ship it, consume it (one project):**

```python
# authoring.py (B)
import tsgrammar as tg
g = tg.Grammar("cfg")
...  # rules as in §3.1
result = tg.build_builder(g)
bundle = result.package("dist/cfg-bundle")

# extraction.py (A — can live in a DIFFERENT process/venv, B-free)
from tsquery import Language, M, OutputModel, capture, source_meta
lang = Language.load_bundle("dist/cfg-bundle")

class ServerSection(OutputModel):
    __match__ = M("source_file", "section", record=True)
    host: str
    port: int
    debug: bool = False
    line: int = source_meta()

ServerSection.validate_with(lang)          # checks active before parsing
rows = ServerSection.extract(text, language=lang)
```

**Consume a community grammar (A only, no B anywhere):**

```python
from tsquery import M, NodeKind, OutputModel, capture
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
| a type with no value shape | `UnsupportedShapeError` |
| one or more matches fail to materialize | `ExtractionError` (per-match `MatchFailure`s) |
| a bundle's artifact is a `.wasm` with no runtime | `WasmRuntimeUnavailableError` (see the wasm verdict in `docs/architecture.md` §3.1) |

---

## 6. Version pins (verified facts)

tree-sitter CLI 0.25.3 / bindings 0.26.0 (ABI 13–15 all load; a
`tree-sitter.json` with metadata is needed for ABI 15) / pydantic ≥ 2.11 /
Python ≥ 3.11. The distributions pin `tree-sitter>=0.26`.
