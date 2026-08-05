# REFACTOR — implementing the rule-class surface in `tsgrammar`

**Project:** `.scratch/013-rule-classes/` (concept: `CONCEPT.md`)
**Goal:** make the rule-class surface (§2 of the concept) a first-class
`tsgrammar` authoring path — sugar over the existing builder — with the
**byte-identity gate** as its regression test and the devenv grammar as its
canonical example.
**Ground rules (from the probes):**
- Every step keeps `devenv shell -- python -m pytest tests/` green.
- The class surface must produce grammar.json **identical** to the
  builder-DSL spelling of the same grammar (the gate).
- The IR, builder, checks, pipeline, conflicts, bundles, and Product A are
  not modified. This is purely additive.
- Probes/evidence go in `012-grammar-models/` (already committed) and this
  dir's `evidence/`; findings accumulate in `FINDINGS.md`.
- Commit style: `tsgrammar: <surface> — <what this step proves>`.

---

## Step 0 — lock the two forks (probe first, cheap)

**0.1 Pure metaclass vs `BaseModel`-based rules.** The 012 probes used a
pure-Python metaclass (~120 lines: registry, `__abstract__` skipping, name
derivation). The alternative — `Rule(BaseModel)` — would give `model_fields`
ordering and native `Literal`-default validation for free, but:

- underscore/dunder class attrs (`__body__`, `__pattern__`, `content` labels)
  interact awkwardly with pydantic's field collection;
- the mutually-recursive annotation resolution (module-globals eval at
  `assemble()` time) is needed either way — pydantic's `model_rebuild` is the
  same deferred pattern;
- pydantic's runtime validation buys nothing (rule classes are never
  instantiated; the IR is already validated pydantic).

Probe: subclass a small `Rule(BaseModel)` with one fielded rule and one
`__body__` rule; record whether `model_fields`/class-creation friction costs
more than the metaclass saves. **Default recommendation: pure metaclass** —
match the probes, minimal friction, "pydantic" is the API *style* (classes,
declarative, class-time checks) while the load-bearing validation stays in
the pydantic IR where it already is.

**0.2 Module + export naming.** Working names: `src/tsgrammar/rules.py`
(metaclass, kinds, compilation, `assemble`) and `src/tsgrammar/patterns.py`
(helpers). Flat re-exports from `tsgrammar/__init__.py` (the kinds, `R`,
`assemble`) + `import tsgrammar.patterns`. Settle the names here so steps 1–5
don't churn.

**Deliverable:** a one-page note in `FINDINGS.md` with the verdicts.

---

## Step 1 — the module skeleton: `src/tsgrammar/rules.py`

**Goal:** `Rule`, the metaclass, the kind subclasses, the registry.

```python
"""tsgrammar.rules — the rule-class authoring surface ("the model IS the
rule"). Each rule is a class; the class body IS the production. assemble()
compiles the classes into the existing builder DSL (builder.py) — the IR,
pipeline, checks, and bundles are untouched."""

_REGISTRY: dict[str, type] = {}   # rule_name -> class, definition order

def _snake(name): ...             # CamelCase -> snake_case

class _RuleMeta(type):
    def __new__(mcs, name, bases, ns):
        cls = super().__new__(mcs, name, bases, ns)
        if not ns.get("__abstract__"):      # OWN ns: kind bases skip
            rn = ns.get("__rule_name__") or _snake(name)
            cls.__rule_name__ = rn
            _REGISTRY[rn] = cls
        return cls

class Rule(metaclass=_RuleMeta):
    __abstract__ = True

# body kinds
class Pattern(Rule):   __abstract__ = True
class Token(Rule):     __abstract__ = True; __token__ = True
class External(Rule):  __abstract__ = True
# behavioral mixins
class Extra(Rule):     __abstract__ = True; __extra__ = True
class Supertype(Rule): __abstract__ = True; __supertype__ = True
class Hidden(Rule):    __abstract__ = True; __hidden__ = True
class Inline(Rule):    __abstract__ = True; __inline__ = True
class Word(Rule):      __abstract__ = True; __word__ = True
```

**Gotchas (probe-learned, do not re-derive):**
- `__abstract__` is checked in the class's **OWN** namespace so the kind
  bases are never registered as rules.
- Flags live on the kind bases → **read them inherited** (`getattr(cls,
  "__token__", False)`), never `cls.__dict__.get` (probe 2's `pair` collapse
  came from this class of mistake).
- `__body__` / `__pattern__` are own-namespace only (no kind base defines a
  default body).

**Verify:** a tiny `__main__`-style check that 17 dummy classes register in
definition order and the kind bases don't. (Full verification comes with the
gate in step 3.)

---

## Step 2 — compilation: annotations → builder calls, plus `assemble()`

**Goal:** the mapping table of CONCEPT §2.2, implemented as builder calls.

```python
def _child(cls, t, attr=None) -> tg.B: ...   # ref / Literal / list / union
def _from_annotations(cls) -> tg.B:          # ordered children -> seq
def R(cls) -> tg.B:                          # tg.ref(cls.__rule_name__)
def assemble(name: str, *, start: type) -> tg.Grammar: ...
```

Mapping rules to implement exactly (each is probe-verified):

| annotation | emit |
|---|---|
| `key: NamePath` | `tg.field("key", tg.ref("name_path"))` |
| `eq: Literal["="] = "="` | the string `"="` (anonymous); **error** if the default != the Literal value |
| `element: list[Value]` | `tg.repeat(tg.field("element", tg.ref("value")))` — field INSIDE repeat |
| `content: list[X]` | `tg.repeat(tg.ref(...))` — no field |
| `A \| B` | `tg.field(name, tg.choice(...))` |
| `A \| None` | `tg.field(name, tg.opt(...))` |

`assemble()` walks `_REGISTRY` in order and, per class:

1. `ext = getattr(cls, "__external__", None)`; if `None` and
   `issubclass(cls, External)`, `ext = rn.upper()`; if `ext is not None` →
   `g.external(tg.tok(ext))` — **before** the rule (externals must precede in
   the scanner's expected order; order comes from class definition order).
2. Body: `__body__` (own ns) → `__pattern__` (own ns; token-wrapped iff
   `getattr(cls, "__token__", False)`) → `__external__` → annotations.
3. Token-wrap: `if getattr(cls, "__token__", False) and
   body.node.type != "TOKEN": body = tg.token(body)` — the guard prevents
   double-wrapping.
4. `g.rule(rn, body, supertype=..., hidden=..., inline=..., word=...)` — all
   flags via `getattr`.
5. `if getattr(cls, "__extra__", False): g.extra(tg.ref(rn))`.
6. After the loop: `g.start(start.__rule_name__)`.

**Gotchas (all three cost probe time):**
- `ext = getattr(...) or rn.upper()` is WRONG — truthy for every rule,
  collapses every body to `tok(UPPERCASE)`. Use the `issubclass(cls,
  External)` guard (probe 2 bug).
- The `quoted()` char class: `f'{q}[^{q}]*{q}'` — NOT `[^"{q}]` (probe 2 bug:
  produced `[^""]`).
- `Literal` detection: `get_origin(t) is Literal`; unions are
  `types.UnionType` (from `A | B`) AND `typing.Union` (`Optional[A]`) —
  check both.

**Verify (the gate, finally):** port `verify_standalone2.py` into
`tests/test_rules.py` step 1: the class-authored devenv grammar (bodies
copied from `devenv_grammar_classes2.py`) vs `examples/devenv-subset/
grammar.py`'s `build()` → `grammar.json` deep-equal. This is the test that
makes everything else safe to build on.

---

## Step 3 — `src/tsgrammar/patterns.py` (the helpers)

**Goal:** the seven helpers as composable regex **strings**:

`ident(hyphen=False)`, `integer()`, `quoted(quote='"')`, `slug()`,
`path_literal()`, `dotted_path(segment=None)`, `rest_of_line()`.

**Contract:**
- Strings only — plain composition, no second DSL; grammar.json carries the
  raw string, so the helper output IS the IR.
- Stay inside the tree-sitter lexer regex subset (no backreferences,
  lookaround, `\b`-style anchors beyond what the generator accepts).
- Each helper ships with a test asserting its output equals the exact string
  it replaces (the devenv grammar's hand-written regexes are the first
  test cases; a synthetic grammar exercises the parameter variants).
- `dotted_path()` and `path_literal()` are *shape* helpers (opinionated by
  construction) — document the shape they encode in the docstring.

**Gotcha:** a helper's docstring with a literal `\.` triggers a
SyntaxWarning; escape it (`\\.`) or use raw strings.

**Verify:** `tests/test_patterns.py` — each helper vs its hand-written
spelling; the gate test (step 2) now uses the helpers and must stay green.

---

## Step 4 — public surface: `tsgrammar/__init__.py` + module docs

**Goal:** the surface is importable and documented the moment it lands.

- Add to `__init__.py`'s grouped imports and `__all__`: `Rule`, `Pattern`,
  `Token`, `External`, `Extra`, `Supertype`, `Hidden`, `Inline`, `Word`,
  `R`, `assemble`, and `patterns` (module).
- Add a short "the rule-class surface" section to the module docstring
  (which already enumerates the public surface — keep it in sync).
- The packaging force-include (`"." = "tsgrammar"`) already ships new files
  in the package dir; the venv resolves `src/` directly — **no reinstall
  needed** (devenv skill: new files are immediately importable).
- Keep `build()` returning `tg.Grammar` as the contract — call sites
  (`run_checks`, `build_builder`, bundles) are unchanged.

**Verify:** `python -c "from tsgrammar import Rule, R, assemble, patterns"`.

---

## Step 5 — source sites for conflict remapping (the free win)

**Goal:** `GrammarConflictError` points at the class and the attribute, not
just a combinator call line.

- Record at class creation: `cls.__site__` = the class definition's
  file/lineno/source (the metaclass already has the frame); record each
  annotated attribute's line in a per-class dict (inspect the class body's
  `__annotations__` lines via the module source).
- Wire into the builder's existing `_node_sites` plumbing: when `assemble()`
  registers a rule, attach the attribute-level sites to the emitted body
  nodes (the same `_iter_body_nodes` / `_SITES` mechanism `Grammar.rule()`
  already uses — reuse it rather than fork it).
- Verify against a deliberately conflicting grammar: the error message names
  `Pair.value` (class + attr), not a raw `tg.seq(...)` line.

**Scope note:** this can land after the mechanism works; it is a UX polish
over the existing remapping, not a dependency of the surface.

---

## Step 6 — tests: `tests/test_rules.py` (the full matrix)

Beyond the gate test (step 2), cover every row of the mapping + the
surface rules, each as a small grammar asserting the compiled IR or the
built grammar's behavior:

1. **The gate** — devenv class-grammar == builder-DSL grammar.json
   (the canonical fixture; bodies from `devenv_grammar_classes2.py`).
2. **Annotation rows** — field at top (`key: NamePath`); Literal + default
   mismatch raises at class definition; `list[T]` field-inside-repeat vs
   `content: list[T]` bare repeat; `A | B` choice; `A | None` opt.
3. **Kinds** — `Pattern` bare vs `Token` wrapped (assert the TOKEN wrapper
   in the IR); `External` default SCREAMING_SNAKE name + `__external__`
   override; mixin composition `class X(Extra, Token)` (assert both flags);
   `Supertype`/`Hidden`/`Inline`/`Word` land in the grammar-level lists.
4. **`__body__` + `R`** — `R(Class)` == `tg.ref("name")`; cycle points with
   `tg.ref("name")` compile and resolve; abstract kind bases are not
   registered.
5. **`assemble`** — start rule first; registry order == rule order;
   `build()` returns the same `tg.Grammar` type the builder returns.
6. **Checks + pipeline** — assembled grammar passes `run_checks` clean;
   `build_builder` (with a scanner) succeeds; smoke parse works.
7. **`patterns`** — each helper vs its hand-written string (from
   `tests/test_patterns.py` if kept separate).

Run: `devenv shell -- python -m pytest tests/test_rules.py -q` and then the
full suite.

---

## Step 7 — docs

1. **`docs/user-guide.md` §3** — add `### 3.9 The rule-class surface` after
   the existing DSL sections: the one-screen example (devenv grammar), the
   mapping table (§2.2), the kinds table, `__body__`/`R`, cycle points, and
   the "when to use which surface" note (rule classes for data-shaped rules;
   the builder for `prec*`/`alias`/`reserved` and maximal control).
2. **`docs/architecture.md`** — add `rules.py` (the rule-class surface) and
   `patterns.py` to the tsgrammar module map row; note the surface compiles
   into `builder.py` and touches nothing else.
3. **`src/tsgrammar/README.md`** — one-line mention + pointer.
4. Cross-reference the byte-identity gate in the user guide's testing
   section (§3.6-adjacent) as the discipline for the new surface.

---

## Step 8 — example migration: `examples/devenv-subset/grammar.py`

**Goal:** the both-halves example IS the class surface — replace the
builder-DSL file with the class version (from
`012/devenv_grammar_classes2.py`), keeping `build()`'s signature.

1. Copy the class version in; update the module docstring's "Authored with…"
   paragraph to describe the surface (it already documents the why-this-shape
   rationale — keep that).
2. Run the end-to-end:
   `devenv shell -- python examples/devenv-subset/extract.py`
   — it rebuilds the bundle and checks **every row against the hand-written
   ground truth**. This is the strongest possible verdict: Product A's
   extraction is bit-for-bit unchanged by the surface switch.
3. If `extract.py`'s `build_bundle` needs nothing (it calls `build()` +
   `run_checks` + `build_builder` — unchanged), the migration is a file
   swap. Confirm the rule-count/`__main__` block still works.

**Gotcha:** keep `scanner.c` untouched — the external token names
(`STRING_FRAGMENT`, `INDENTED_STRING_FRAGMENT`) come from the SCREAMING_SNAKE
default and must match the scanner's declarations (they do — same names).

---

## Step 9 — evidence, findings, verdict

1. Save raw outputs under `evidence/` (probe outputs, the extract run,
   the gate test run) — verbatim, per the phase discipline.
2. Write `FINDINGS.md`: the fork verdicts (step 0), what the gate caught
   during implementation (expect at least one mapping bug — the probes found
   two), the mapping rows that needed correction, and the final verdict
   (GO / GO-with-changes / NO-GO) with the evidence paths.
3. Commit in scoped, single-finding commits:
   - `tsgrammar: rules — Rule metaclass + kind subclasses`
   - `tsgrammar: rules — annotation compilation + assemble()`
   - `tsgrammar: patterns — the helper set with byte-identity tests`
   - `tsgrammar: rules — exports + module docs`
   - `tsgrammar: rules — attribute source sites for conflict remapping`
   - `tsgrammar: tests — test_rules.py mapping matrix + gate`
   - `tsgrammar: docs — user-guide §3.9 + architecture module map`
   - `examples: devenv-subset on the rule-class surface — ground truth green`
4. The final verdict checks: (a) the devenv example runs end-to-end against
   ground truth, (b) the full suite is green, (c) the byte-identity gate is
   in the suite, (d) no IR/pipeline/Product-A file changed.

---

## Checklist (print this page)

- [ ] Step 0: BaseModel fork probed; names locked; note in FINDINGS
- [ ] Step 1: `rules.py` skeleton — Rule, metaclass, 8 kinds; registry order
- [ ] Step 2: compilation + `assemble()`; the gate test ports green
- [ ] Step 3: `patterns.py`; helper == hand-written string tests
- [ ] Step 4: `__init__.py` exports; module docs; no-reinstall check
- [ ] Step 5: attribute source sites feed the conflict remapper
- [ ] Step 6: `test_rules.py` full matrix; full suite green
- [ ] Step 7: user-guide §3.9, architecture map, README
- [ ] Step 8: `examples/devenv-subset/grammar.py` migrated; extract.py green
- [ ] Step 9: evidence saved; FINDINGS verdict; scoped commits
