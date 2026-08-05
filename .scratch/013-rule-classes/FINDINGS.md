# FINDINGS — 013: the rule-class surface (`tsgrammar.rules`)

**Project:** `.scratch/013-rule-classes/` — implement the rule-class authoring
surface for Product B (concept: `CONCEPT.md`; plan: `REFACTOR.md`).
**Date:** 2026-08-04

---

## Step 0 — the two forks locked (evidence: `evidence/step0_basemodel_fork.txt`)

### 0.1 Pure metaclass vs `Rule(BaseModel)` — VERDICT: **pure metaclass**

Probe `probe_basemodel_fork.py` defines the same two rule shapes (a fielded
rule with a Literal token default, a `__body__` rule with mixins) in both
surfaces. Findings:

1. **`Rule(BaseModel)` defines cleanly, but the forward refs defer** — pydantic
   v2 keeps a rule referencing a later-defined rule's schema incomplete until
   `model_rebuild()`. The pure-metaclass surface needs no such ceremony: it
   reads `__annotations__` strings and evaluates them against module globals
   at `assemble()` time (the same deferred pattern, no pydantic machinery).
2. **A bare BaseModel does NOT give the class-time Literal-default check** —
   pydantic v2 validates defaults at *instantiation*, not class definition
   (probe [2]: `BadPair.eq: Literal["="] = ";"` defines with no error). The
   concept's class-time error is a design requirement, so a custom metaclass
   would be needed on top of BaseModel anyway — the "native validation"
   argument evaporates. The metaclass surface raises the mismatch in
   `_from_annotations` at `assemble()` time (before any build), which is the
   same guarantee with no extra layer.
3. **`model_fields` ordering is `__annotations__` ordering** (probe [3]:
   identical) — Python's annotation-order preservation already gives the
   "ordered children" guarantee; pydantic buys nothing.
4. **BaseModel drags in ~3× the namespace machinery** — probe [4]: 107 class
   namespace keys (14 `__pydantic_*`/`model_*` generated names) vs 33 for the
   metaclass — on every rule class, forever, for a surface that never
   instantiates.
5. Both surfaces compile the same annotations to the same body shape
   (probe [5]) — the fork is purely about mechanism, not capability.

The probe confirms the REFACTOR default: **pure metaclass** (matches the 012
probes, minimal friction, class-time checks in `assemble()`, zero runtime
cost). "Pydantic" is the API *style* (declarative classes, class-time
checks); the load-bearing validation stays in the pydantic IR
(`grammar.py`), which is unchanged.

### 0.2 Module + export naming — VERDICT: **locked as proposed**

- `src/tsgrammar/rules.py` — the metaclass, the kinds, annotation
  compilation, `assemble()`. ("rules" over "models": Product A's
  `typed.py` already owns "model" vocabulary for `OutputModel`; B's classes
  are rules, and the IR module is already `grammar.py`.)
- `src/tsgrammar/patterns.py` — the regex-string helpers.
- Flat re-exports from `tsgrammar/__init__.py`: `Rule`, `Pattern`, `Token`,
  `External`, `Extra`, `Supertype`, `Hidden`, `Inline`, `Word`, `R`,
  `assemble`; `tsgrammar.patterns` stays a module import.
- `import tsgrammar as tg` + `from tsgrammar import ...` (as the example
  files spell it) and `from tsgrammar.patterns import ...` are the two
  import shapes — no churn expected.

---

## Steps 1–4 — the mechanism, the gate, the exports (landed together)

### The registry deviation (module-scoped, not global)

The REFACTOR's step-1 sketch has a global `_REGISTRY`. The probes use one —
but a global registry would accumulate every rule class across all modules
imported into a process, so any two grammars (or two of the test matrix's
mini-grammars) in one process would emit each other's rules. `assemble()`
instead walks `vars(sys.modules[start.__module__])` for concrete `Rule`
subclasses (those with `__rule_name__`), in definition order — hermetic per
grammar module, no reset ceremony, imported rule classes count (a `from
other_module import X` binds X in the namespace). Duplicate rule names in one
module surface as the builder's own `duplicate rule` error.

### The `Hidden` name resolution

The builder's `rule(hidden=True)` renames `name` -> `_name`. `R(cls)` and
annotation refs must name the REGISTERED rule, so `_resolved_name()` applies
the underscore to `cls.__rule_name__` for `Hidden` classes; `assemble()` and
the start rule use it too. Without this, `R(HiddenClass)` would emit a dead
symbol.

### Class-definition sites (step-5 groundwork)

The metaclass records `cls.__site__` (file/lineno/source) at class creation.
The frame depth from `_rule_site` to the module frame executing the `class`
statement was MEASURED as 2 (the naive `depth=3` walked off the stack into
`None` — evidence `step1_skeleton.txt` [5]). Attribute-level lines come with
step 5.

### The gate (step 2) is green and in the suite

`tests/test_rules.py::test_gate_devenv_class_grammar_identical_to_builder_dsl`
compares the class-authored devenv grammar
(`tests/fixtures/devenv_classes_grammar.py`, bodies from
`.scratch/012-grammar-models/devenv_grammar_classes2.py`) against
`examples/devenv-subset/grammar.py`: grammar.json deep-equal, 17 rules,
checks clean on both. This is the test everything else builds on — it pinned
the mapping rows (field-inside-repeat, `content` unnamed, externals in
definition order, SCREAMING_SNAKE defaults) and the helper strings in one
shot. Evidence: `evidence/step2_gate.txt`.

### `Rule` rebind (a public-name change the concept mandates)

`tsgrammar.Rule` is now the rule-class BASE (the canonical import
`from tsgrammar import Rule` for `class Pair(Rule)`). The IR node union that
used to share the name remains importable as `tsgrammar.grammar.Rule`; no
in-repo consumer used `tg.Rule` as the union (internal modules import from
`.grammar` directly). Noted in the `__init__` docstring.

### Exports (step 4) + helpers (step 3) landed early

The gate's canonical fixture imports the kinds + `R` + `assemble` from
`tsgrammar` and the helpers from `tsgrammar.patterns` — so the exports and
the helper set shipped with the mechanism. `patterns.py` implements the seven
probe helpers verbatim (including the probe-caught `quoted()` fix — the char
class excludes only the quote char).

---

*Steps 5+ land in follow-up commits; findings appended here as they land.*
