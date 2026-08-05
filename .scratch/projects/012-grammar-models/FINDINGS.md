# FINDINGS — 012: a class-based ("model IS the rule") surface for Product B

**Date:** 2026-08-04
**Probe:** `probe_class_surface.py` (re-runnable; output in `evidence/run1.txt`)

## The question

The devenv example (`examples/devenv-subset/grammar.py`) authoring surface is
the builder DSL (`g.rule("pair", tg.seq(tg.field("key", ...), ...))`) — not
very "pydantic". Could B's authoring surface be the grammar rules as Pydantic
models themselves — the B-side mirror of Product A's "the model IS the query"?

## The record (what we actually decided)

- CONCEPT §4.2: the *IR* was always pydantic GrammarModels (the discriminated
  union mirroring grammar.json) — validation, import, round-trip.
- CONCEPT §4.3 is titled **"The builder DSL (never hand-instantiate the IR)"**
  and says **"Raw node construction is unusable"** — so "just the models" in
  the literal sense (hand-building `SeqNode(members=[...])`) was explicitly
  rejected at design time. The models were never meant to be the authoring
  surface; the builder emits them and "advanced authors can drop to raw nodes".
- What was NEVER designed: a **class-per-rule** declaration surface (the
  `OutputModel`-style move for B). This probe tests that.

## Probe result

A ~120-line probe (pure-Python metaclass, **no library changes**) authors the
entire devenv grammar as rule classes and compiles them into the existing
builder DSL:

- **[1] grammar.json is byte-identical** to the current builder-DSL version —
  the class surface is faithful sugar, not a new grammar language.
- **[3] `run_checks` clean, [4] parser builds and parses** the real fixture.
- Since the IR is identical, the schema (node-schema.json), Product A's
  models, the record-mode pair detection, and the ground-truth extraction all
  carry over unchanged by construction.

## The mapping (what "more pydantic" concretely means)

```python
class Interpolation(Rule):
    open: Literal["${"] = "${"        # anonymous token "${" (never fielded)
    expression: Value                  # field("expression", ref("value"))
    close: Literal["}"] = "}"          # anonymous token "}"

class Pair(Rule):
    key: NamePath                      # field("key", ref("name_path"))
    eq: Literal["="] = "="
    value: Value
    semi: Literal[";"] = ";"

class ListRule(Rule):
    __rule_name__ = "list"             # builtin-name escape
    open: Literal["["] = "["
    element: list[Value]               # repeat(field("element", ref(...)))
    close: Literal["]"] = "]"

class String(Rule):
    open: Literal['"'] = '"'
    content: list[StringFragment | Interpolation]   # unnamed repeat(choice)
    close: Literal['"'] = '"'
```

- annotated attr = ordered child; attr name = CST field (unless Literal, or
  the reserved label `content` = unnamed).
- `Literal["x"]` default must equal `x` — a **class-time check** (the pydantic
  move: a mismatched token default fails at definition, not in the build).
- `list[T]` = repeat; `A | B` = choice; `A | None` = opt — field placement
  follows the original IR shapes (`element: list[Value]` = field INSIDE the
  repeat, per the original list rule — the naive `field(name, repeat(...))`
  produced a DIFFERENT IR, caught by the byte-identity check).
- leaves/flags as class attrs: `__pattern__`, `__token__`, `__external__`,
  `__extra__`, `__supertype__`, `__hidden__`, `__inline__`, `__word__`.
- the full hypothetical file is `devenv_grammar_classes.py`; verified to
  produce the identical grammar.json when driven through the probe machinery
  (`verify_standalone.py`).

## The split (honest limits)

Of the 17 rules, the class surface covered:

| mechanism | rules |
|---|---|
| annotations | interpolation, string, indented_string, pair, attrset, list |
| `__pattern__`/`__token__` | name_path, number, path_literal |
| `__external__` | string_fragment, indented_string_fragment |
| `__body__` (escape hatch) | comment, with_expr, value, formal, formals, source_file |

What does NOT map, and why:

1. **Unnamed sequences/choices** (`with_expr`, `formal`, `formals`,
   `source_file`, `value`): annotations are fielded by construction and Python
   can't repeat an `_` name, so bare alternations and unnamed `seq`s stay in
   `__body__` (combinators, with class-refs `R(Class)` instead of strings).
2. **Cycle points take the underlying DSL's string ref.** Grammar rules are
   cyclic DAGs (`pair`→`value`→`with_expr`→`value`): a body expression is
   evaluated at class-creation time, so a body referencing a class defined
   LATER cannot use `R(Class)` (Python NameError — lazy refs can't fix name
   resolution). At the cycle points `__body__` uses `tg.ref("value")` — the
   existing DSL's own spelling, zero new machinery. Annotations avoid the
   issue entirely: they resolve against the module globals at `assemble()`
   time (pydantic's `model_rebuild` pattern), and grammar.json only needs the
   rule NAME, which a class's `__rule_name__` provides.
3. **Builtin-name collisions**: rule kinds `list`, `string`, `value` are
   lowercase builtins — classes need `__rule_name__` (or a suffix rule).
4. **field-inside-repeat placement** (`element: list[Value]`) is a subtle IR
   shape that only the byte-identity check catches; the annotation reads
   "field element repeats" which is the right intuition but the wrong IR
   until you know tree-sitter puts the field on the elements.
5. `prec*` ladders, `alias`, `immediate_token`, `reserved` — untouched; no
   better class form (stays combinator).

## Verdict / recommendation

- **GO (with scope):** the class surface is real, faithful (byte-identical
  IR), and covers the rules that actually matter to Product A — the
  **fielded data-carrying rules** (`pair`, `interpolation`, `list`, strings,
  attrsets) are exactly what field/record mode consumes; the plumbing rules
  (formals, with_expr, the value supertype) are legitimately `__body__`.
- The honest framing: not "model-only" but **"models for the data, combinators
  for the plumbing"** — which mirrors Product A's own reality (record/field
  mode eat fielded kinds; value shapes are *derived*, not declared).
- A real implementation would put this in `tsgrammar` as a sugar layer over
  the existing builder (source sites come for free: class def line + each
  annotated attr's line → finer-grained `GrammarConflictError` targets than
  the current combinator call sites). Cost is small; the metaclass is ~120
  lines and the builder already does the IR work.
- Alternative worth one probe before committing: BaseModel-based rules
  (`Rule(BaseModel)`) for the annotation-form subset — pydantic gives
  `model_fields` ordering + Literal-default validation natively, but the
  recursive/unnamed/builtin collisions make a hybrid surface either way.

## v2 refinement (probe 2 + `devenv_grammar_classes2.py`) — subclasses + helpers

**Kind subclasses instead of flag attrs** — the base-class list IS the flag
list; `assemble` reads flags INHERITED (getattr, not `__dict__`):

```python
class Number(Pattern)          # bare regex rule      (__pattern__)
class NamePath(Token)          # token-wrapped        (__pattern__/body)
class StringFragment(External) # external-scanner token; token name defaults
                               # to the rule name in SCREAMING_SNAKE
class Comment(Extra, Token)    # behavioral kinds are MIXINS (MI composes)
class Value(Supertype)
```

Kinds: body — `Pattern`, `Token`, `External`; behavioral mixins — `Extra`,
`Supertype`, `Hidden`, `Inline`, `Word`. The leaf rules collapse to
one-liners: `class Number(Pattern): __pattern__ = integer()`.

**Pattern/token helpers** (`tsgrammar.patterns`) — composable regex STRINGS
in the tree-sitter lexer subset (no backrefs/lookaround): `ident(hyphen=)`,
`integer()`, `quoted()`, `slug()`, `path_literal()`, `dotted_path()`,
`rest_of_line()`. The probe asserts the helper-produced strings equal the
hand-written regexes EXACTLY (byte-identity depends on it).

The byte-identity check caught two real implementation bugs in the v2
surface: (1) `ext = getattr(...) or rn.upper()` made `ext` truthy for EVERY
rule, collapsing every body to `tok(UPPERCASE_NAME)`; (2) the `quoted()`
helper put the quote inside the char class twice (`[^"]` needed, `[^""]`
produced). Both fixed; the check is what makes the helpers trustworthy.

**Assessment:** the subclasses are a genuine readability win for the leaf
and flag cases (the subclass list is discoverable/self-documenting; MI
composes the common combos). The gotchas: flags must be read inherited
(getattr); the External name default is a naming convention (override with
`__external__`); helpers are plain regex-string composition, so they must
stay inside the lexer's regex subset and any shape helper (e.g.
`dotted_path`) is opinionated by construction. What does NOT change: the
`__body__` plumbing rules, the `tg.ref("name")` cycle points, the
`content` label, `__rule_name__` for builtin collisions.
