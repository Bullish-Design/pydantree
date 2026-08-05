# Pydantic ⇄ Tree-sitter — Revised Concept

**Status:** concept / post-Phase-1
**Supersedes (in spirit):** `017-pydantic-winnow-parser`
**Phase-1 update (2026-08-02):** Product A's surface was redefined by the
Phase-1 spikes (`spike-a/`, `spike-a2/` (now `.scratch/projects/015-phase1-spike-a/`, `.scratch/projects/016-spike-a2-model-only/`)). The pre-Phase-1
"query DSL → `.scm`" version of §5 was **rejected** in favor of a
**model-only declaration**: the `OutputModel` class itself IS the query — no
`.scm`, no query builder, no query string. §5 below reflects the validated
design; evidence and the rejected-alternative analysis live in
`.scratch/projects/015-phase1-spike-a/FINDINGS.md` and `.scratch/projects/016-spike-a2-model-only/FINDINGS.md`.
**Decision baked in:** static grammars, GLR backend (tree-sitter). We are *not*
building a dynamic-grammar VM or a parser-combinator engine. The whole design
leans into tree-sitter's model instead of fighting it.

---

## 0. One-paragraph pitch

Two cooperating Python libraries put a Pydantic face on tree-sitter. **Product B**
(`pydantree_sitter_grammar`, working name) lets a developer *author* a tree-sitter grammar as a
composable Pydantic DSL that compiles down to tree-sitter's `grammar.json`, then
runs the standard generate + compile pipeline for them — its whole reason to
exist is to make GLR grammar authoring *as painless as tree-sitter allows*.
**Product A** (`pydantree_sitter`, working name) lets a developer *consume* a grammar —
either one built by B or any of the hundreds of prebuilt community grammars —
by declaring a Pydantic `OutputModel` whose field names, types, defaults, and a
one-line `__match__` path are the entire query. A derives the tree-sitter
`.scm`, compiles and runs it, and returns typed `OutputModel` instances; the
user never writes an S-expression or a query DSL. A is useful on its own; B
makes new grammars possible; together they give an end-to-end,
compile-time-checked pipeline from grammar definition to typed output.

The two libraries are deliberately **separate packages with a narrow, data-only
interface** between them. You can adopt A without ever touching B.

---

## 1. Why two libraries, not one

The authoring side and the consumption side have almost nothing in common except
that they both talk about tree-sitter.

| | **Product B — `pydantree_sitter_grammar`** | **Product A — `pydantree_sitter`** |
|---|---|---|
| User | Grammar author (needs a format that doesn't exist yet) | Data extractor (a grammar already exists) |
| Verb | *Define* a grammar | *Query* a parse tree |
| Runs at | **Build time** | **Run time** |
| Heavy deps | Rust `tree-sitter-cli`, C toolchain | None — just the C runtime + our mapping layer |
| Output | A distributable grammar artifact (`.so` + schema) | Typed `OutputModel` instances |
| Failure mode it fights | GLR conflicts, precedence, scanners | Untyped CST, manual coercion/glue, hand-written `.scm` |
| Can ship without the other? | Yes (emits a normal grammar package) | **Yes** (works over community grammars) |

Collapsing them into one package would force every A user to carry B's Rust +
compiler toolchain for no reason. Keeping them split means the *consumer* runtime
stays as light as `py-tree-sitter` itself, while the *author* toolchain can be as
heavy as it needs to be — exactly mirroring how tree-sitter itself separates the
CLI (generate) from the runtime (parse).

---

## 2. What we own vs. what we inherit

We are wrappers. Being honest about the seam is the difference between a good
library and a leaky one.

**We inherit (do not reimplement):**
- The `grammar.json` schema — the stable IR that `grammar.js` merely emits.
- `tree-sitter-cli` (Rust) — the generator: `grammar.json → parser.c` + parse tables.
- `libtree-sitter` (C) — the runtime: parsing, the node/tree CST, the query engine,
  incremental reparse, error recovery.
- The community grammar ecosystem (~hundreds of languages already built).

**We own (the value-add):**
- **B:** a Pydantic DSL that emits valid `grammar.json`, an author-time static
  analyzer, a GLR-ergonomics layer (precedence ladders, expression helper,
  conflict diagnostics remapped to Python source), and a build/distribute pipeline.
- **A:** a model-only typed extraction layer — the `OutputModel` is the query
  declaration, the `.scm` is derived and never seen — plus capture→`OutputModel`
  materialization (coercion/validation/spans/nesting) and a diagnostic surface.
- **Shared (`pydantree_sitter`):** Pydantic models mirroring the `grammar.json` schema, the
  **grammar node-schema** format (see §7), and the artifact-loading contract.

The load-bearing insight from prior analysis stands: **`grammar.js` is not
load-bearing.** It only `console.log(JSON.stringify(grammar))`s. So B targets
`grammar.json` directly and never touches JavaScript or Node.

---

## 3. The tree-sitter pipeline, and where each library plugs in

```
                    ┌──────────────  Product B (pydantree_sitter_grammar, build time)  ──────────────┐
  Pydantic          │                                                                  │
  GrammarModels ──► grammar.json ──► parser.c ──► .so  +  node-schema.json      │
      ▲             │  (we emit)     (ts-cli,      (gcc)        (we derive)          │
      │             │                 Rust)                                          │
   builder DSL      └───────────────────────────────────────────────┬──────────────────┘
                                                                     │  grammar artifact
                                                                     ▼
                    ┌──────────────  Product A (pydantree_sitter, run time)  ──────────────────┐
   text ──────────► load grammar ──► parse (C runtime) ──► CST ──► derived query ──► OutputModel
                    │  (.so)                               │        ▲   (.scm,    ▲          │
                    │                                       │     internal)  mapping layer     │
                    │                                       │   (model = query)                │
                    └───────────────────────────────────────┴─────────────────────────────────┘
                          ▲
                          └── OR: a prebuilt community grammar wheel (no B involved)
```

The artifact boundary (`.so` + `node-schema.json`) is the *only* coupling
between B and A. A never imports B.

---

## 4. Product B — `pydantree_sitter_grammar` (authoring)

### 4.1 Goal & target user

A developer who needs to parse a format that has no tree-sitter grammar yet —
a config language, a DSL, a log format, a query language — and who does not want
to write `grammar.js`, hand-tune magic precedence integers, or decode raw
generator conflict dumps. They want to describe the grammar in typed, composable
Python and get a working parser out.

We promise: **"author in Pydantic, we handle the toolchain, and when GLR bites we
make the bite land on *your Python source* with an actionable message."** We do
**not** promise the bite never happens (see §4.6 — this is the honesty line).

### 4.2 The core: GrammarModels → `grammar.json`

`grammar.json` is already a discriminated union of node types. We mirror it as a
Pydantic discriminated union, one model per rule node:

```python
# pydantree_sitter.grammar — the canonical, validated, serializable IR
class Symbol(RuleNode):    type: Literal["SYMBOL"];     name: str
class Str(RuleNode):       type: Literal["STRING"];     value: str
class Pattern(RuleNode):   type: Literal["PATTERN"];    value: str          # regex
class Seq(RuleNode):       type: Literal["SEQ"];        members: list[Rule]
class Choice(RuleNode):    type: Literal["CHOICE"];     members: list[Rule]
class Repeat(RuleNode):    type: Literal["REPEAT"];     content: Rule       # 0+
class Repeat1(RuleNode):   type: Literal["REPEAT1"];    content: Rule       # 1+
class Optional_(RuleNode): type: Literal["CHOICE"];     ...                 # sugar → CHOICE(x, blank)
class Prec(RuleNode):      type: Literal["PREC"];       value: int; content: Rule
class PrecLeft(RuleNode):  type: Literal["PREC_LEFT"];  value: int; content: Rule
class PrecRight(RuleNode): type: Literal["PREC_RIGHT"]; value: int; content: Rule
class Token(RuleNode):     type: Literal["TOKEN"];      content: Rule
class ImmediateToken(...): type: Literal["IMMEDIATE_TOKEN"]; ...
class Alias(RuleNode):     type: Literal["ALIAS"];      value: str; named: bool; content: Rule
class Field_(RuleNode):    type: Literal["FIELD"];      name: str; content: Rule
Rule = Annotated[Union[...], Field(discriminator="type")]
```

A grammar is a **registry of named rules + a start rule + grammar-level options**
(`extras`, `word`, `conflicts`, `inline`, `supertypes`, `externals`). Recursion is
expressed by `Symbol` (a `RuleRef` by name), never by cyclic instances — so the IR
stays a serializable DAG-of-references. `Grammar.model_dump_json()` *is*
`grammar.json`.

Because both sides are Pydantic:
- `model_validate` gives free structural validation of hand-built grammars.
- `@model_validator` runs well-formedness checks at construction (§4.5).
- Round-tripping to/from `grammar.json` is free, so we can also **import existing
  community grammars into GrammarModels** for inspection or extension.

### 4.3 The builder DSL (never hand-instantiate the IR)

Raw node construction is unusable. The public authoring surface is a thin fluent
builder that *emits* GrammarModels:

```python
from pydantree_sitter_grammar import Grammar, rule, seq, choice, repeat, opt, field, token, tok

g = Grammar("mylang")

# leaf tokens
ident  = g.token("ident", r"[a-zA-Z_]\w*")
number = g.token("number", r"\d+(\.\d+)?")

# a rule; `+` = seq, `|` = choice, .star()/.plus()/.opt() = repetition
g.rule("assignment",
    field("name", ident) + tok("=") + field("value", g.ref("expr")))

g.start("source_file", repeat(g.ref("assignment")))
artifact = g.build()          # emit json → generate → compile → package
```

The builder is sugar; every operator lands on the same validated GrammarModel.
Advanced authors can drop to raw nodes; both paths converge on one IR that we
serialize, hash, cache, and inspect.

### 4.4 **Minimizing GLR authoring misery** (the reason B exists)

This is the heart of Product B. We can't delete GLR's constraints, but we can move
almost all of the pain from *cryptic, post-hoc, integer-encoded* to *typed,
declarative, and pointed at your source*. Concrete techniques:

1. **Declarative precedence ladders, not magic integers.** Tree-sitter's
   `prec(4, …)` forces authors to hand-pick and constantly re-balance integers. We
   let authors declare a *relative ordering* and compute the integers:
   ```python
   prec = g.precedence(["or", "and", "compare", "add", "mul", "unary", "call"])
   # low ────────────────────────────────────────────────► high
   g.rule("add", prec.left("add", g.ref("expr") + tok("+") + g.ref("expr")))
   ```
   Adding a level in the middle renumbers everything automatically. Associativity
   is attached at the operator, not smeared across integers.

2. **A first-class `ExpressionGrammar` (Pratt-style) helper.** Hand-writing binary
   expression rules is the single largest source of tree-sitter conflict pain. We
   generate the correct `prec.left/right` binary/unary rules and the `choice` ladder
   from a table:
   ```python
   expr = g.expression("expr",
       primary = choice(number, ident, tok("(") + g.ref("expr") + tok(")")),
       infix = [
           ("+", "left", "add"), ("-", "left", "add"),
           ("*", "left", "mul"), ("/", "left", "mul"),
           ("^", "right", "pow"),
       ],
       prefix = [("-", "unary"), ("!", "unary")],
   )
   ```
   Emits conflict-free expression rules for the common case; escape to raw rules
   when the language is weird.

3. **Conflicts remapped to *your Python source*.** We capture the definition site
   (`file`, `lineno`, and the builder call) of every rule at construction. When
   `tree-sitter generate` reports a shift/reduce or reduce/reduce conflict, we parse
   its structured output, map the involved symbols back to the GrammarModels, and
   raise a `GrammarConflictError` that says *which of your `g.rule(...)` lines
   collide*, shows the ambiguous input shape, and suggests the canonical fix
   (add precedence / mark intentional ambiguity / use `token`). Raw generator text
   becomes a Python traceback into your grammar.

4. **Intentional ambiguity as a typed opt-in.** GLR can legitimately keep
   ambiguity (resolved by `conflicts` + dynamic precedence). Instead of hand-editing
   the `conflicts` array, authors mark a choice:
   ```python
   choice(a, b, ambiguous=True, dynamic=prec.dynamic("prefer_a", 1))
   ```
   and we synthesize the correct `conflicts` entry + `prec.dynamic` wrapper.

5. **Visibility & structure as typed attributes, not naming conventions.**
   Tree-sitter's `_hidden` rules, `alias`, `inline`, `supertypes`, and `field`
   are all just options: `g.rule(..., hidden=True)`, `.alias("name")`,
   `inline=True`, `supertype=True`. No more leading-underscore folklore.

6. **`extras`, `word`, keywords — sane defaults, declarative overrides.** Whitespace
   and comments in `extras` default on; `word` (keyword extraction, which fixes a
   whole class of keyword/identifier conflicts) is a one-liner:
   `g.word(ident)`. We *default* to the settings that avoid beginner conflicts.

7. **Author-time regex validation for tokens.** Tree-sitter's lexer accepts only a
   regular subset (no backreferences, limited lookaround). We validate `token`
   patterns against that subset *in Python, before* the slow Rust generate, and
   point at the offending construct.

8. **Lean into left recursion.** Unlike PEG/combinators, GLR *allows* left
   recursion — a genuine ergonomic win. The DSL encourages the natural
   left-recursive expression form instead of the awkward right-recursive
   rewrites PEG forces. We advertise this as a feature.

### 4.5 Author-time static analysis (fast Python errors before the slow Rust step)

Before ever invoking the generator, we validate the GrammarModel graph and emit
Pythonic diagnostics with source locations:

- Undefined rule reference (`Symbol` names a rule that doesn't exist).
- Unused / unreachable rules (not reachable from start).
- Nullable rule inside `repeat` (infinite-loop hazard).
- Direct/indirect left-recursion report (allowed, but flagged so authors know
  they'll need precedence).
- `token(...)` whose content references a non-terminal (illegal in tree-sitter —
  we catch it before the generator does, with a clearer message).
- Duplicate rule names; `field` names that don't correspond to any capture.
- First-set overlap warnings that predict likely conflicts *before* generate runs.

This is the cheap, fast feedback loop; `generate` is the slow authoritative one.

### 4.6 The honesty line (what we will NOT hide)

- **Conflicts can still require you to understand precedence.** The helpers cover
  the common cases; a genuinely ambiguous language still needs author judgement.
  We make the judgement *informed and local*, not *cryptic and global*.
- **External scanners.** Some grammars (indentation-sensitive languages, heredocs,
  string interpolation, contextual keywords) require an external scanner that must
  be written in C. We provide a **typed escape hatch**: declare `externals` in the
  DSL, supply a C scanner file (or one of a small library of prebuilt common
  scanners — indentation, matched-delimiter), and we wire it into the build. We do
  **not** claim to author scanners in Pydantic. This is the one place "you only
  write the grammar" is explicitly false, and we say so up front.

### 4.7 Build & distribute pipeline

`g.build()` performs, with content-addressed caching keyed on
`hash(grammar.json) + ABI version + toolchain version`:

1. Emit `grammar.json` (+ `node-schema.json`, see §7).
2. Invoke the bundled `tree-sitter-cli` → `parser.c` (+ compile the scanner if any).
3. Compile to a target:
   - **native `.so`/`.dylib`/`.pyd`** (needs a C compiler) — fastest at runtime.
     (A `.wasm` target was assessed and rejected — see Appendix A; the shipped
     seam raises `WasmRuntimeUnavailableError` for wasm artifacts.)
4. Package as either a Python wheel (à la `tree-sitter-python`) or a standalone
   grammar bundle (`.so` + `node-schema.json` + metadata).

The toolchain (Rust CLI + a C compiler) is B's problem and lives as a
*build/dev dependency*. It is acceptable for B to be heavy; A stays light.

### 4.8 Testing support

Wrap tree-sitter's corpus test format: authors write `(input, expected sexp)`
cases in Python, we run them against the freshly built grammar and diff the CST.
Snapshot the `grammar.json` + node-schema so grammar changes show up as reviewable
diffs.

---

## 5. Product A — `pydantree_sitter` (consumption)

### 5.1 Goal & target user

Anyone who wants structured, typed data out of text for which a grammar exists —
a community grammar (Python, JSON, Bash, Rust, SQL, …) or one built by B. They
should never see a raw `TSNode`, never hand-write an S-expression query, and never
manually coerce a byte-range into an `int`.

A is deliberately shippable **on day one over community grammars, with zero
dependency on B.** That's what de-risks the whole project (§9).

### 5.2 Loading grammars

One uniform `Language.load(...)` accepting:
- a prebuilt community grammar wheel (`tree-sitter-json`, …),
- a native `.so`/`.dylib` built by B,
- (a `.wasm` grammar bundle was assessed and rejected — Appendix A),

each optionally paired with a `node-schema.json` that unlocks compile-time query
checking (§7). Loading is the light runtime — no toolchain required.

### 5.3 The model IS the declaration (validated design)

Phase 1 (spike-a2) rejected a query DSL: for simple queries a builder is
ceremony, and the materialization value lives in the *model*, not the query. A's
surface is therefore just the `OutputModel`. The user writes one class; A
derives the `.scm`, compiles it, runs it, and materializes instances. No `.scm`
is ever written or seen.

**Field mode** — structured nodes, bound by CST field:

```python
class Assignment(OutputModel):
    __match__ = M("module", "expression_statement", "assignment")
    name: Annotated[str, Matches(r"^[A-Z][A-Z_]*$")] = capture("left")
    value: Annotated[int, NodeKind("integer")] = capture("right")
    line: int = source_meta()

rows = Assignment.extract(text, language=tree_sitter_python)
```

**Record mode** — order-independent key/value documents (JSON records, config
files, …); the field name IS the key:

```python
class Person(OutputModel):
    __match__ = M("document", "array", "object", record=True)
    name: str
    age: int
    tags: list[str]
    nickname: str | None = None
    active: bool = False
    line: int = source_meta()

people = Person.extract(text, language=tree_sitter_json)
```

The binding rules are mechanical, not conventional (all verified in spike-a2):

| Model element | Derived meaning |
|---|---|
| attr name | capture name (field mode) / JSON key (record mode) |
| pydantic type | coercion (`"1920"→int`, `"true"→bool`) |
| `Optional[T]` / defaults | missing-capture handling |
| `list[X]` | repeated capture → list (missing → `[]`) |
| `= source_meta()` | span/line injection from the match anchor |
| `= capture("field")` | CST field position (field mode); no-arg = attr name |
| `Annotated[..., Matches/Eq/AnyOf]` | `#match?` / `#eq?` / `#any-of?` predicates |
| `Annotated[..., NodeKind("k")]` | constrain the matched node kind (tuple = alternation) |
| field typed as another `OutputModel` | nested sub-query materialization |
| `__match__ = M("a", "b", "c")` | the one structural declaration: anchored ancestor path |

Structure derivation and validation run at **class creation** (a `ModelMetaclass`
hook — `model_fields` is available there, unlike `__init_subclass__`). Grammar
validation (node kinds, fields) needs the grammar, so it runs at
`Model.validate_with(language)` or the first `extract`; either way the emitted
`.scm` is in the error message.

### 5.4 Capture → `OutputModel` materialization

The value-add over raw tree-sitter — and, per Phase 1, the reason A exists. The
captures derived from the model are mapped onto its fields with **pydantic as
the coercion engine**: the materializer hands raw capture text to
`Model(**kwargs)` and pydantic's lax mode coerces `"1920"→int`, `"98.5"→float`,
`"true"→bool`, `"admin"→enum`, raising a per-field `ValidationError` for
malformed input. Materialization handles: text slicing from byte spans, primitive
coercion, enum lookup, `Optional`/missing captures (defaults, or `[]` for lists),
repeated captures → `list`, span/line injection via `source_meta()`, and nested
`OutputModel`s from sub-queries (a field typed as another model materializes the
value node with that model's machinery).

One honest limit (spike-a2 §2.1): record mode maps each field type to a
grammar's node shape (JSON: `str` → `string_content` inside `string`, `int` →
`number`, `bool` → `true|false`, `list[str]` → array of `string_content`). That
map is grammar knowledge; it is hardcoded per grammar (or overridden per field
with `NodeKind`) until the node-schema bridge (§7) derives it.

### 5.5 Result modes

The public surface is **typed extraction** (`Model.extract(text,
language=...)`) — one call, no opt-in ladder. The 0.26 bindings' `matches()` is
eager anyway (no streaming cursor exists), so "lazy" is at most an internal mode
that defers text reads while skipping model construction; it is not a pitched
feature. Two knobs remain:

- **strict / lenient**: strict raises an `ExtractionError` summarizing every
  failing match (pydantic `ValidationError` with `loc`/`type`); lenient returns
  the good rows and reports the rest.
- **parse-cleanliness**: `validate()` reports `ERROR`/`MISSING` nodes with
  kind/line/span/snippet.

### 5.6 Error & recovery surface

Mistakes surface early, at the cheapest layer that can catch them (spike-a2 §3):

| Mistake | Surfaces at | Kind |
|---|---|---|
| typo node kind / field in `__match__` / `capture()` | class creation + `validate_with()` / first extract | `QueryBuildError` (tree-sitter `Query()` rejects) |
| unmapped record shape (`list[bool]`, unknown type) | **class creation** | `UnsupportedShapeError` |
| annotation not resolvable (e.g. function-local model) | **class creation** | clear `CoercionError` with a fix hint |
| required field with no capture binding | class creation (warning) + extract | pydantic `Field required` |
| non-numeric text into an `int` field | extract | `ValidationError` with `loc`/`type` |
| scalar field fed by multiple captures | extract | `AmbiguousCaptureError` (strict) |
| malformed input (`ERROR`/`MISSING` nodes) | `validate()` | typed diagnostics |

Tree-sitter *always* returns a tree, inserting `ERROR`/`MISSING` nodes rather
than throwing; `validate()` exposes those as typed diagnostics
(`Diagnostic{kind, span, expected}`). The **incremental reparse** API (apply an
edit → reparse) is available for editor-ish consumers; we do not wrap it.

---

## 6. Where the two libraries meet (and where they don't)

They meet at **exactly one data artifact** and never in code:

```
   B.build()  ──►  { grammar.so | grammar.wasm ,  node-schema.json }  ──►  A.Language.load()
```

- A depends only on the artifact + schema, produced equally well by B or by the
  community. So A has no idea B exists, and vice versa.
- If you own *both* halves (your grammar + your extraction models), you
  get an **end-to-end typed, compile-time-checked pipeline** (§7) that neither jc,
  TextFSM, nor raw tree-sitter can offer.

---

## 7. The bridge feature: the grammar node-schema (the real differentiator)

`grammar.json` fully determines what node kinds, fields, and supertypes a grammar
can produce. From it we derive a **`node-schema.json`**: the closed set of node
kinds, each node's possible fields and child types, and supertype relationships.
This small schema is the second half of the artifact B emits — and it's what makes
A *typed*:

1. **Model ↔ grammar validation.** A derived query referencing a node kind or
   field that the grammar cannot produce is rejected at `validate_with()` time,
   not discovered as a silent empty result at runtime. (Phase 1 already gets
   this from tree-sitter's own `Query()` constructor, which validates node kinds
   and field names.)
2. **Autocomplete / typed node access.** A can generate typed node accessors (or
   `.pyi` stubs) from the schema, so consuming a grammar feels like using a typed
   API rather than stringly-typed CST spelunking.
3. **Value-shape derivation.** The record-mode shape map (§5.4) — "a JSON `str`
   is a `string_content` inside `string`" — is grammar knowledge. The schema is
   what lets A *derive* the map (and per-type defaults such as "`int`-typed
   captures match numeric kinds") instead of hardcoding it, for community
   grammars that ship no schema.
4. **Capture ↔ output type cross-validation.** When an `OutputModel` field is fed
   from a capture, we can check the capture's possible node types against the
   field's Python type and flag mismatches (e.g. a capture that can only ever be
   non-numeric feeding an `int` field) at class creation, not at first extract.

This is the same "both sides are Pydantic ⇒ validate the seam at compile time"
capability discussed for the grammar↔output binding, now spanning
grammar → query → output. It is the strongest argument for doing this in our stack
rather than telling people to use `py-tree-sitter` directly.

Community grammars ship without a node-schema, but we can **derive one from their
`grammar.json`** (or, weaker, sample it from `node-types.json` which tree-sitter
already generates). So even community-grammar users get most of the typing benefit.

---

## 8. Distribution strategy

- **`pydantree_sitter`** — tiny, pure-Python: the `grammar.json` Pydantic models, the
  node-schema format, the artifact-loading contract. Shared dependency of A and B.
- **`pydantree_sitter` (A)** — light runtime: `pydantree_sitter` + the C runtime binding + the model→query derivation and mapping layer. **No Rust CLI, no
  compiler.** This is what most users install.
- **`pydantree_sitter_grammar` (B)** — heavy build tool: `pydantree_sitter` + bundled `tree-sitter-cli`
  (Rust) + a C/wasm toolchain hook. A developer/build-time dependency; fine to be
  large. Produces artifacts consumed by A.

This mirrors tree-sitter's own runtime-vs-CLI split and keeps the cost where the
value is: authors pay the toolchain tax once at build time; consumers pay nothing.

---

## 9. Sequencing (build order that de-risks)

The risky, novel part is *ergonomics*, not runtime — the C runtime already works.
So build the piece that delivers value soonest and validates the interface:

- **Phase 0 — spike the emission.** Hand-write GrammarModels for one nontrivial
  grammar (a small expression language with precedence), emit `grammar.json`, run
  `generate` + compile, confirm a working parser. Prove the conflict-diagnostic
  remapping (§4.4.3) is mechanically possible from real generator output. This is
  the single most important go/no-go experiment.
- **Phase 1 — Product A MVP over community grammars (DONE: `.scratch/projects/015-phase1-spike-a/`,
  `.scratch/projects/016-spike-a2-model-only/`).** Proved the **model-only declaration** (the `OutputModel` IS the
  query — §5.3), derived `.scm`, capture→`OutputModel` materialization, nested
  models, and the failure surface over Python + JSON, **independent of B**. The
  spike rejected the query-DSL version of A (ceremony without value for simple
  patterns) and settled on §5. Remaining Phase-1 gaps are bridge-shaped:
  field-mode lists, non-JSON record shapes, JSON string unescaping (§5.4/§7).
- **Phase 2 — Product B core.** GrammarModel hierarchy + `grammar.json` emitter +
  §4.5 static analysis + native build pipeline.
- **Phase 3 — the GLR ergonomics layer.** Precedence ladders, `ExpressionGrammar`,
  conflicts-remapped-to-Python. This is where B earns its name; treat it as the
  make-or-break UX work, not a nicety.
- **Phase 4 — the bridge.** node-schema emission from B + compile-time query
  validation and typed node access in A (§7).
- **Phase 5 — polish & reach.** incremental reparse API,
  external-scanner escape hatch + a small prebuilt-scanner library, corpus testing.

A is valuable after Phase 1. B is valuable after Phase 3. The bridge (Phase 4) is
the capability nobody else has — but it depends on both halves existing, so it
comes last.

---

## 10. Explicit non-goals

- **Dynamic / runtime-constructed grammars.** Generate + compile is a build step;
  doing it per-request means shipping a Rust generator + C compiler to end users
  and eating seconds of latency. Tree-sitter is the most anti-dynamic backend
  possible; we embrace static and say so.
- **Binary / bytes parsing.** Tree-sitter is UTF-8/text-oriented. Out of scope.
- **Unbounded streaming.** Tree-sitter loads whole documents; it does incremental
  *editing*, not incremental *streaming*. Out of scope.
- **Being a parser-combinator / PEG engine.** We are GLR + CST. Ordered-choice /
  lookahead semantics are not our model.
- **Authoring external scanners in Pydantic.** C escape hatch only.
- **Guaranteeing conflict-free grammars.** We minimize and localize conflict pain;
  we don't eliminate the possibility.

---

## 11. Risks & open questions

1. **Conflict diagnostics quality (highest risk / highest value).** The entire B
   value proposition rests on §4.4.3 turning generator conflict output into
   actionable, source-located Python errors. If the generator's machine-readable
   conflict output is too coarse to map back to specific rules reliably, B
   degrades toward "prettier grammar.js" — still useful, but far less compelling.
   *Phase 0 must test this against real conflicts.*
2. **External-scanner frequency.** How many *target* grammars actually need a C
   scanner? If it's most nontrivial ones, the "just write the grammar" story is
   weaker than hoped. Survey representative target formats early.
3. **Toolchain packaging for B** across Linux/macOS/Windows (Rust CLI + a C
   compiler).
4. **Upstream churn.** tree-sitter's language ABI version, `grammar.json` schema,
   `node-types.json`, and query API all evolve. We pin ABI versions and treat
   `grammar.json`/node-schema as versioned artifacts.
5. **wasm** — assessed and rejected (Appendix A): loading `.wasm` would mean
   forking the binding (py-tree-sitter 0.26 has no wasm store) for a runtime A
   promises to keep light; portability is carried by per-platform native wheels.
6. **Regex-subset friction.** Author-time validation (§4.4.7) mitigates, but some
   authors will still be surprised by what the tree-sitter lexer won't accept.
7. **node-schema completeness.** Phase 1 sharpened this: the schema's real jobs
   are (a) deriving the record value-shape map (§5.4) and (b) capture↔type
   cross-validation (§7.4), for community grammars that ship no schema. The
   Phase-1 stand-ins (hardcoded JSON shape map, `NodeKind` overrides, runtime
   `ValidationError`) work but are not derived; how faithfully the schema can be
   derived from `grammar.json` / `node-types.json` determines how much of the
   Phase-4 benefit non-B users get.

---

## Appendix A — Assessed and rejected: wasm distribution (2026-08-05)

Earlier drafts of this concept doc described `.wasm` as a first-class compile
and loading path (§4.7, §5.2, §8, §9). That capability is **assessed — no-go**:

- The shipped seam (`pydantree_sitter.loader`) raises
  `WasmRuntimeUnavailableError` UNCONDITIONALLY for `.wasm` artifacts.
- py-tree-sitter 0.26 has no wasm store, so loading a `.wasm` grammar would
  mean FORKING the binding — a hard dependency add for a runtime A promises to
  keep light. The probe bridge lives in `.scratch/projects/009-phase7/wasm_bridge.py`.
- Portability is carried by per-platform native wheels instead.

Authoritative verdict: `.scratch/projects/009-phase7/FINDINGS.md`. The shipped
design targets native `.so`/`.dylib`/`.pyd` artifacts only.

---

## 12. Bottom line

The `grammar.js`-bypass makes B genuinely feasible; the node-schema bridge makes
the A+B combination something raw tree-sitter cannot match. The project lives or
dies on **two ergonomic bets**: (1) that we can turn GLR conflict/precedence pain
into typed, source-located, declarative Python (Product B), and (2) that
declaring an `OutputModel` and getting schema-checked typed extraction — the
model IS the query — is meaningfully nicer than `py-tree-sitter` (Product A).
Phase 1 (spike-a2) validated bet 2 for typed materialization over Python + JSON.
Ship A first over community grammars to prove bet 2
and earn users cheaply; invest B's effort disproportionately in the GLR-ergonomics
layer, because that — not the emitter, not the build pipeline — is the whole reason
Product B deserves to exist.

---

# Addendum — the 014 refactor decisions (D1–D14)

**Date:** 2026-08-05 · this addendum records the decisions of the adversarial
review + refactor (`.scratch/projects/014-adversarial-review/`); the concept
doc is the authoritative record and must not silently drift from the shipped
design. The implementation lives in `pydantree_sitter` /
`pydantree_sitter_grammar`.

| # | Decision |
|---|----------|
| D1 | Name: **pydantree-sitter** (consumer, light) + **pydantree-sitter-grammar** (authoring, heavy); imports `pydantree_sitter` / `pydantree_sitter_grammar`. Collision-proof (the bare `tsquery`/`tscore` names are taken); two regular top-level packages, not a PEP-420 namespace split. |
| D2 | Two packages, not three: the seam (schema + loader) folds into the light package; B depends on A (A never imports B). "The light package IS the seam." |
| D3 | Delete the `node_types.rs` port (`_ir_derive`): the schema's ONLY source is the CLI's own `node-types.json` byproduct, tracked by construction. |
| D4 | Product A: one matching machine — Model → MatchSpec → one compiler → one emitter → one backtracking ancestor matcher → one materializer. |
| D5 | Explicit binding: `lang.extractor(Model)` runs all checks once; compiled state lives on the Language keyed by (model, strict). No class-level caches, no global registry. |
| D6 | Value shapes are declared data (`ValueMap`), not name-regex inference; `propose_value_map` is the reviewed-draft generator only. |
| D7 | Job-2 becomes real codegen: generated runtime wrapper classes (`.pyi` fiction deleted). |
| D8 | B: provenance lives on the node (private, non-serialized `_site` stamped at construction); the site stores and the drain/snapshot dance are deleted. |
| D9 | B: grammars are explicit objects — `assemble(name, *, start, rules=[...])`; `module_rules(module)` is the explicit sweep (imported classes excluded). Rule classes are the canonical authoring surface. |
| D10 | `run_checks` is part of `build()` (check=True default); generate always runs with `--json` (one run); ONE bundle writer; the community tool merges into the pipeline. |
| D11 | Escape hatch = `__raw_query__` (a literal `.scm`); the query DSL is not public. Sibling order/negation/multi-anchor joins are out of scope → raw query. |
| D12 | Bundle metadata carries `bundle_format` (int): absent = 1, unknown >2 rejected legibly. |
| D13 | Deletions: the legacy island (`src/pydantree`, `src/data`, `src/examples`), the root distribution, `_wasm_bridge.py` (→ scratch), `spike-a/`, `spike-a2/`, `KICKOFF_SPIKE.md`. |
| D14 | Version reset: both dists start at 0.1.0; the PyPI names are registered before any other public step. |
