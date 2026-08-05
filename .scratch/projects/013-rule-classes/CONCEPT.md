# REVISED CONCEPT — Product B's rule-class surface ("the model IS the rule")

**Status:** concept / post-probe (probes: `.scratch/012-grammar-models/`)
**Supersedes (in part):** CONCEPT §4.3's authoring decision — see §1.
**Revision trigger:** the builder-DSL surface (`g.rule("pair", tg.seq(...))`)
does not feel like the rest of pydantree. Product A's surface is
**model-only** — "the `OutputModel` class IS the query, no query DSL"
(validated in spike-a2). Product B's authoring surface should be the mirror:
**the rule class IS the production, no builder ceremony.**
**Evidence:** `probe_class_surface.py`, `probe_class_surface2.py`,
`devenv_grammar_classes{,2}.py`, `verify_standalone{,2}.py` — all in
`.scratch/012-grammar-models/` — every probe asserts the class surface
produces a grammar.json **byte-identical** to the builder-DSL spelling.

---

## 0. One-paragraph pitch

Keep the IR, the pipeline, the checks, the conflict remapping, and the
bundles exactly as they are. Replace only the **top authoring surface**:
each grammar rule is a **class** — `class Pair(Rule)`, `class NamePath(Token)`
— and the class body IS the production. Annotated attributes are ordered
children (the attribute name is the CST field), `Literal["="] = "="` is an
anonymous token, `list[T]`/`A | B`/`A | None` are repeat/choice/opt, and the
base class carries the rule's kind (`Pattern`, `Token`, `External`) and
behavioral flags (`Extra`, `Supertype`, `Hidden`, `Inline`, `Word`) as
**subclasses**. A small `assemble(name, start=...)` compiles the classes into
the existing builder, so `build()` returns the very same `tg.Grammar` —
`run_checks`, `build_builder`, the scanner wiring, and Product A are
untouched **by construction**. A small `pydantree_sitter_grammar.patterns` helper set
replaces hand-written regexes with composable, verified strings. The proven
claim: the devenv grammar (17 rules, externals, scanner, supertypes) written
in this surface emits grammar.json identical to today's builder-DSL file —
~⅓ less code.

## 1. Why we are revising the concept (the record)

The original concept did not forget about "the pydantic grammar models":

- CONCEPT §4.2: the IR is Pydantic `GrammarModel`s — a discriminated union
  mirroring grammar.json. That is load-bearing and unchanged.
- CONCEPT §4.3, titled **"The builder DSL (never hand-instantiate the IR)"**,
  decided that hand-building `SeqNode(members=[...])` is unusable and layered
  a fluent builder over the models. That decision was correct — **raw node
  construction is still not the surface**.
- What was never designed is the middle option: **class-per-rule
  declarations** — the B-side mirror of Product A's model-only `OutputModel`.
  Phase 1 rejected A's query DSL in favor of "the model IS the query"; the
  equivalent move for B — "the rule class IS the production" — was never
  specced or probed until `.scratch/012-grammar-models/`.

So: "you just needed the pydantic grammar models themselves" is half-true —
the models were always the IR; the missing piece is a *declarative class
surface* that compiles to them. This concept is that missing piece, and it
**amends** §4.3: the builder DSL becomes the low-level surface (the escape
hatch), and the rule-class surface becomes the primary authoring path.

## 2. The surface in one screen

```python
from typing import Literal

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar import (
    External, Extra, Pattern, R, Rule, Supertype, Token, assemble,
)
from pydantree_sitter_grammar.patterns import dotted_path, integer, path_literal, rest_of_line

class Comment(Extra, Token):                 # behavioral kinds are MIXINS
    __body__ = tg.seq("#", tg.pattern(rest_of_line()))

class NamePath(Token):                       # token-wrapped regex leaf
    __pattern__ = dotted_path()

class Number(Pattern):                       # bare regex leaf
    __pattern__ = integer()

class StringFragment(External):              # external-scanner token
    """External-scanner token (scanner.c): a `"..."` string body chunk."""

class Pair(Rule):                            # the annotation form
    key: NamePath                            #   field("key", ref("name_path"))
    eq: Literal["="] = "="                   #   anonymous token "="
    value: Value
    semi: Literal[";"] = ";"

class Value(Supertype):                      # flag as a base class
    __body__ = tg.choice(R(String), R(Number), tg.ref("with_expr"))

def build() -> tg.Grammar:
    return assemble("devenv", start=SourceFile)
```

### 2.1 The rule kinds (the subclass list IS the flag list)

| kind | meaning |
|---|---|
| `Rule` | the base; annotation-bodied rules (the common case) |
| `Pattern` | a regex leaf — bare `pattern(...)`, **not** token-wrapped |
| `Token` | body (or `__pattern__`) wrapped in `token(...)` — lexed as one token |
| `External` | backed by an external-scanner token; the token name defaults to the rule name in SCREAMING_SNAKE (override `__external__`) |
| `Extra` | also an extra (whitespace/comment — never a child) |
| `Supertype` | grammar-level `supertypes` entry |
| `Hidden` / `Inline` / `Word` | the remaining rule flags |

Kinds compose by multiple inheritance (`class Comment(Extra, Token)`); the
kinds set disjoint attributes, so MRO order is irrelevant in practice.

### 2.2 The annotation mapping (ordered children)

| annotation | compiled to |
|---|---|
| `key: NamePath` | `field("key", ref("name_path"))` |
| `eq: Literal["="] = "="` | anonymous token `"="`; the default MUST equal the Literal value (checked at class definition — a pydantic-style class-time error) |
| `element: list[Value]` | `repeat(field("element", ref("value")))` — the field goes INSIDE the repeat (the original list rule's IR shape) |
| `content: list[X]` | `repeat(X)` — the reserved label `content` = an UNNAMED child (the IR's own slot name) |
| `value: String \| Number` | `field("value", choice(ref, ref))` |
| `maybe: Number \| None` | `field("maybe", opt(ref))` |

Attribute order = production order (Python preserves annotation order).

### 2.3 The escape hatch

`__body__` — the combinator DSL as-is for shapes annotations cannot express
(unnamed sequences, bare alternations):

- `R(SomeClass)` — a reference to a rule class (compiles to the same SYMBOL
  as `tg.ref("name")`, class-typed instead of stringly-typed).
- `tg.ref("name")` — used at the **cycle points**: grammar rules are cyclic
  DAGs (`value` ↔ `with_expr`), and a class body is evaluated at class
  creation, so a reference to a class defined later cannot use `R(Class)`.
  The cycle points fall back to the underlying DSL's own string spelling —
  zero new machinery, and it is exactly what the builder DSL writes today.

### 2.4 Pattern helpers (`pydantree_sitter_grammar.patterns`)

Composable **regex strings** in the tree-sitter lexer subset (no
backreferences, no lookaround):

`ident(hyphen=False)` · `integer()` · `quoted(quote='"')` · `slug()` ·
`path_literal()` · `dotted_path()` · `rest_of_line()`

Helpers return strings, not nodes — plain composition, no second language.
The byte-identity gate (§7) asserts each helper's output equals the
hand-written regex it replaces, which is what makes the helpers trustworthy:
during the probes the gate caught a `quoted()` helper emitting `[^""]`
instead of `[^"]` (and an `assemble` truthiness bug that collapsed every rule
to `tok(UPPERCASE_NAME)`). Without the gate, those would have shipped as
silent grammar changes.

## 3. The canonical example

`examples/devenv-subset/grammar.py` re-authored in this surface — the full
hypothetical file, verified byte-identical to the current builder-DSL
version, is `.scratch/012-grammar-models/devenv_grammar_classes2.py`
(verification: `verify_standalone2.py`). It is the both-halves example and
the future fixture: 17 rules, a supertype, an extra, two external scanner
tokens, string interpolation, formals — enough of the surface's feature
matrix to serve as the canonical test grammar.

## 4. Design decisions locked by the probes

1. **The surface is sugar over the existing builder — never a parallel IR.**
   `assemble()` emits builder calls; `build()` returns the same `tg.Grammar`.
   Pipeline, checks, conflict remapping, bundles, and Product A are untouched
   by construction.
2. **Byte-identity is the gate.** Every probe asserts `grammar.json` equality
   with the builder-DSL spelling. Any new mapping rule (field placement,
   helper output, flag reading) is verified, not eyeballed.
3. **Flags are read INHERITED (`getattr`), not from `cls.__dict__`** — the
   kind bases carry them; user classes inherit. (`__body__`/`__pattern__` are
   own-namespace only.)
4. **Rule name = snake_case(class name)**, overridable with `__rule_name__`
   — required for builtin collisions (`list`, `string`, `value`).
5. **External token name = SCREAMING_SNAKE(rule name)** by convention
   (scanner.c must agree), overridable with `__external__`.
6. **Cycle points use `tg.ref("name")`.** Lazy refs cannot fix Python name
   resolution (`R(Value)` raises NameError before `R` runs); the underlying
   string ref is the honest spelling. Only the mutual-recursion pair needs it.
7. **`Literal["x"]` defaults are validated at class definition** — a
   mismatched token default fails immediately, not at build.
8. **`content` is the reserved unnamed-child label** (the IR's own slot
   name); every other attribute name is a CST field.
9. **`name: list[T]` compiles the field INSIDE the repeat** — the naive
   `field(name, repeat(...))` produces a different IR (probe-verified).
10. **The split is intentional:** "models for the data, combinators for the
    plumbing." Fielded rules (what Product A's field/record mode actually
    consumes) get the annotation form; unnamed structure and bare
    alternations get `__body__`.

## 5. The honest split (what maps, what stays)

Probe-verified on the devenv grammar (17 rules):

| mechanism | rules |
|---|---|
| annotations | interpolation, string, indented_string, pair, attrset, list |
| pattern/token | name_path, number, path_literal |
| external | string_fragment, indented_string_fragment |
| `__body__` | comment, with_expr, value, formal, formals, source_file |

What does NOT map, and why it is structural, not a gap:

- **Unnamed sequences/choices** (`with_expr`, `formal`, `formals`,
  `source_file`, the `value` alternation): annotations are fielded by
  construction and Python cannot repeat an `_` name — `__body__`.
- **Cycle points** (`value` ↔ `with_expr`): `tg.ref("name")` — §4.6.
- **Builtin names** (`list`, `string`, `value`): `__rule_name__`.
- **`prec*` ladders, `alias`, `immediate_token`, `reserved`**: no better
  class form — the combinator surface stays their home.

This split is not a compromise; it mirrors Product A, which consumes fielded
kinds in field/record mode and *derives* value shapes rather than declaring
them.

## 6. Implementation shape

- **New module(s) in `src/pydantree_sitter_grammar/`** — the metaclass + kinds +
  compilation + `assemble()` (working name `rules.py`) and the helper set
  (`patterns.py`). The venv resolves `src/` directly (no reinstall); the
  hatch force-include already ships the whole package dir.
- **Exports** via `pydantree_sitter_grammar/__init__.py`: `Rule`, `Pattern`, `Token`,
  `External`, `Extra`, `Supertype`, `Hidden`, `Inline`, `Word`, `R`,
  `assemble`, plus `pydantree_sitter_grammar.patterns`.
- **Source sites** for conflict remapping come for free: the class
  definition line and each annotated attribute's line are finer-grained
  `GrammarConflictError` targets than combinator call sites (design target —
  see REFACTOR.md step 6).
- **`build()` stays the contract**: `assemble("devenv", start=SourceFile)`
  returns the same `tg.Grammar`, so `run_checks`/`build_builder`/bundles are
  unchanged call sites.

## 7. Verification strategy

1. **Byte-identity gate** (the load-bearing check): class-authored grammar →
   `grammar.json` == builder-DSL-authored grammar.json, on the devenv
   grammar and on a synthetic grammar exercising every mapping row of §2.2.
2. **The existing suite stays green** — nothing in the IR/builder/checks/
   pipeline changes, so `tests/` is the regression net.
3. **Checks + build + parse**: the assembled grammar passes `run_checks`
   clean, builds with the scanner, and the smoke parse + Product A
   extraction over the fixtures reproduce the current results
   (the ground-truth file in `examples/devenv-subset/`).
4. **The corpus harness** applies as before — the surface is upstream of the
   same grammar.

## 8. Open questions (to settle in the implementation project, not before)

1. **Pure metaclass vs `BaseModel`-based rules.** The probes used a pure
   metaclass (~120 lines). A `Rule(BaseModel)` variant gets `model_fields`
   ordering + native `Literal`-default validation, but the unnamed/recursive/
   underscore cases push toward a hybrid either way. Probe before building
   the real module.
2. **Auto-check at `assemble()`?** Should `assemble` run the static checks
   (with the cross-rule deferral the checks already do) or keep the explicit
   `run_checks` call the example makes today? Prefer explicit for now.
3. **Source-site granularity** — attribute-level sites for
   `GrammarConflictError` (REFACTOR step 6) need the annotation lines
   recorded; confirm the conflict remapper can consume them.
4. **Helper scope** — ship the seven probe helpers as-is, or grow a curated
   `patterns` set in the first cut? Prefer minimal; the byte-identity test
   for each helper is the cost of adding one.
5. **Naming** — `rules.py` vs `models.py`; whether the kinds live in
   `pydantree_sitter_grammar.rules` and are re-exported flat.

## 9. Non-goals

- **Not** replacing the builder DSL — it remains the escape hatch, the
  low-level surface, and the home of `prec*`/`alias`/`reserved`/scanner work.
- **Not** a new grammar language — annotations and helpers compile to the
  existing combinators; no parallel IR, no second regex dialect.
- **Not** authoring external scanners in Pydantic (unchanged: C escape hatch).
- **Not** dynamic grammars (unchanged: static, generate + compile).
- **Not** changing grammar.json, node-schema, bundles, or Product A.

## 10. Sequencing

This directory (`.scratch/013-rule-classes/`) is the implementation project:

1. **Lock the forks** — probe the BaseModel fork (§8.1) and settle naming
   (§8.5). Findings → `FINDINGS.md`.
2. **Mechanism** — `rules.py` + `patterns.py` per REFACTOR.md steps 1–5.
3. **Tests + docs** — `tests/test_rules.py`, user-guide §3.9, architecture
   module map (REFACTOR steps 6–8).
4. **Example migration + verdict** — `examples/devenv-subset/grammar.py` to
   the class surface; end-to-end run against the ground truth; verdict in
   `FINDINGS.md` (REFACTOR step 9).

Deliverable: the class surface as a first-class `pydantree_sitter_grammar` authoring path,
with the byte-identity gate as its regression test, and the devenv example as
its canonical demonstration.
