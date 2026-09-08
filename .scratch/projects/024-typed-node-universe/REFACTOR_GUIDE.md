# The typed-node-universe refactor — step-by-step guide

**Date:** 2026-09-08 · **Baseline:** 466 passed, 1 skipped, 46 deselected @ `b9cad4f`
(`python -m pytest -q -m "not slow"`, ~55 s, in-devenv)
**Scope:** brainstorm ideas 1-4, which are one change.

**Prime directive.** The best version of this library is *smaller*. Every phase
either deletes a subsystem, collapses two implementations into one, or turns a
runtime check into a type. When a step offers "fix or delete", choose the option
that leaves less code. A phase that adds net lines without deleting a named
subsystem is a phase that went wrong.

**Second directive.** No leftovers. Every phase ends with a **Cleanup** list and
a **Gate**. The gate does not pass while any name on the cleanup list still
resolves. Appendix B is the final grep gate; it must be empty before the last
commit.

---

## 0. Scope and non-goals

### In scope

| # | Idea | One line |
|---|------|----------|
| 1 | Node types are the core | The schema is a type system. Use it as one, not as a validator. |
| 2 | One node class | Product A's `OutputModel` and Product B's `Rule` are the same declaration. |
| 3 | No record mode | `dict[str, V]` and `list[Nested]` are annotations, not a pipeline. |
| 4 | Codecs on the class | `__value__` replaces `ValueMap`, `Unescaped`, and the shape inference. |

### Forced into scope

**Schema-less binding is removed** (D5). Idea 1 cannot generate node classes
without a schema, so the schema stops being optional. This is brainstorm idea 9
arriving early. It is a real cost for community wheels — see D5 for the
migration.

### Not in scope

Brainstorm ideas 5-8 and 10-12. `pattern.py`, `agreement.py`, `rules.py`
(ast-grep), and `syntax.py` are touched at exactly one integration point
(`PatternMatch.extract`) and are otherwise left alone. The `.scm` emitter
survives in reduced form. Appendix E records each deferred idea and what it
would delete next.

---

## 1. Decision log (settled — do not re-litigate during implementation)

| # | Decision | Rationale |
|---|----------|-----------|
| **D1** | **The node class is the one noun.** One class per named node kind, generated from `NodeSchema`. It carries the kind, typed field accessors, and the value codec. It lives in the light package (`pydantree_sitter.nodes`). | Idea 1. The schema already describes a type system. Today a hand-written checker re-implements what a type checker does for free. |
| **D2** | **The generator has two renderings, one spec builder.** `generate_module(schema)` emits committed source (static typing, IDE completion, `ty` checks). `build_namespace(schema)` builds the same classes in memory with `type()`. Both call one `_class_specs(schema)`. | A committed module is where idea 1 pays off — errors move to edit time. The in-memory path keeps exploration cheap. Two renderings of one spec cannot drift. |
| **D3** | **An extraction model is a subclass of a node class.** `class Function(py.FunctionDefinition): name: str` — the base supplies the kind and the schema, the subclass narrows. No `Extract[T]`, no `__match__`, no `M`, no `capture`. | Idea 2 pushed to its conclusion. Subclassing *is* projection. It also gives inheritance of the anchor for free, which `__match__` needed MRO-walking code to fake. |
| **D4** | **Ancestor context is `__under__`, and it is rare.** `__under__ = (py.Module,)` — a tuple of node classes, with `...` for a gap. Most models need no path: the anchor kind alone is enough once kinds are types. | `M()`'s path exists mostly to disambiguate kinds that a type universe already disambiguates. Keeping the gap matcher costs ~60 lines and preserves `M(a, ..., b)` power. |
| **D5** | **A schema is required. Schema-less binding is deleted.** Community wheels ship no `node-types.json` (verified: `tree_sitter_python` and `tree_sitter_json` site-packages contain no JSON). The user vendors `src/node-types.json` from the grammar's source repository, exactly as `tests/fixtures/` and `examples/*/node-schema.json` already do. | Forced by D1. Also kills the wildcard emit path, the JSON-family special case, `looks_like_json`, and the "schema-less binding" warning — the largest warning source in the current suite. |
| **D6** | **The generated module records the language fingerprint; loading checks it.** Reuse `binding._language_fingerprint` (name, ABI, semantic version, kind list, field list). A mismatch raises `SchemaDriftError`. | The vendored schema is now load-bearing. Silent drift between a wheel upgrade and a stale schema would produce wrong extractions with no signal. This is the cost of D5, paid explicitly. |
| **D7** | **The value codec is `__value__` on the node class.** Default returns the node's text as `str`. A subclass overrides it. The return annotation is what bind-time checking reads. | Idea 4. `ValueMap.scalars` becomes a return annotation; `ValueMap.wrappers` becomes a method that reads a child; `ValueMap.arrays` becomes `list[T]`; `Unescaped()` becomes `JsonString.__value__`. |
| **D8** | **`propose_value_map` becomes `suggest_codecs(schema)`, a printer.** It writes nothing and is not importable from the package root. It prints `__value__` stubs a human pastes into an overrides module. | Idea 4. The old "draft generator you inspect and commit" ceremony exists only because the codec lived in the wrong place. Keep the heuristic, remove its authority. |
| **D9** | **Record mode is deleted.** `list[Nested]` is the general form; `dict[str, V]` is sugar for the unambiguous pair case. Ambiguity raises at class creation, naming the candidate pair kinds. | Idea 3. Today `record=True` switches the whole pipeline and silently changes what `capture("x")` means. One spelling must not have two semantics. |
| **D10** | **Nested models in the general path are implemented, not rejected.** The current `ShapeError` for "nested model in field mode" (`spec.py`) is deleted. A nested field's value node runs through the nested class's own resolver. | D9 requires it: `list[Nested]` is the replacement for record mode, so it must work everywhere records worked. |
| **D11** | **One metaclass in the light package; Product B adds the forward direction.** `pydantree_sitter.nodes.NodeMeta` owns kind naming, annotation parsing and site capture. `pydantree_sitter_grammar` adds `to_ir()` plus the authoring-only mixins (`Extra`, `Supertype`, `Hidden`, `Inline`, `Word`). | Idea 2. B compiles annotations forward into IR; A binds them backward against a schema. The annotation grammar is identical, so it is written once. |
| **D12** | **The round trip is a test, not a hope.** Author a grammar with node classes in B, build it, generate node classes from the resulting `node-types.json`, and assert structural equivalence with the authored classes (modulo hidden and inline rules the CLI erases). | This is the strongest available evidence that the two directions are one declaration. If it fails, D11 is wrong and must be revisited before Phase 7 deletes anything. |
| **D13** | **The `.scm` emitter survives in reduced form, for `__raw_query__` only.** `emit.Query.raw`, `Cursor`, `MatchView` stay. The spec-to-`NodeSpec` builders, `PatternSet`, `cap`, `node`, `Pred`, and `CaptureRef` go. | Deleting raw queries is idea 6/10 territory and out of scope. Bounding the residue to ~150 lines is not. |
| **D14** | **Field-mode query emission stays, and shrinks.** Kinds come from `schema.field_types(kind, field)` instead of `ValueMap` inference. The wildcard branch goes with D5. | This keeps the refactor scoped to ideas 1-4. Replacing queries with a cursor walk is idea 10; Appendix E records what that would delete next. |
| **D15** | **Instances are validated pydantic models.** A node class is a `BaseModel`. The metaclass builds a resolver that turns a `tree_sitter.Node` into kwargs; pydantic validates. `node` and `span` are private attrs. | Preserves today's contract exactly. A lazy view is faster and is a follow-up, not a prerequisite. Changing both the type model and the evaluation model in one project is how refactors fail. |
| **D16** | **Version bump to `0.3.0`, and the old surface is deleted, not deprecated.** No shim module, no `__getattr__` re-export, no `DeprecationWarning`. | The stated goal is conceptual purity with no regard for migration cost. A compatibility shim is exactly the cruft this project exists to remove. Appendix C is the migration table users get instead. |

---

## 2. Target end-state

### 2.1 Repository layout

```
src/pydantree_sitter/                dist: pydantree-sitter (LIGHT)
  __init__.py       public surface (2.2) — target: 12 names
  nodes.py          NEW. Node, NodeMeta, the annotation grammar, the resolver,
                    __value__, __under__, the schema binding  (~450 lines)
  generate.py       NEW (replaces codegen.py). _class_specs(schema) ->
                    generate_module(schema) | build_namespace(schema);
                    suggest_codecs(schema)                     (~350 lines)
  grammar.py        NEW (replaces binding.py). Grammar: language + schema +
                    namespace + parse(); the fingerprint check  (~220 lines)
  find.py           NEW (replaces compiler.py + materialize.py's loops).
                    Query emission from a node subclass, the match loop,
                    the kwargs build                            (~380 lines)
  raw.py            NEW. __raw_query__ support only (D13)       (~150 lines)
  match.py          UNCHANGED in spirit: the ancestor-path matcher for
                    __under__ gaps + the anchor merge           (~130 lines)
  schema.py         UNCHANGED. NodeSchema and its lookups.
  loader.py         UNCHANGED. load_bundle.
  emit.py           REDUCED to Query.raw + Cursor + MatchView   (~150 lines)
  errors.py         the taxonomy, plus SchemaDriftError
  span.py           NEW. Span moves out of materialize.py       (~55 lines)
  agreement.py      UNCHANGED (ast-grep boundary; out of scope)
  pattern.py        ONE integration point changed: PatternMatch.extract
  rules.py          UNCHANGED (ast-grep rule model; out of scope)
  syntax.py         UNCHANGED (out of scope)
  py.typed

src/pydantree_sitter_grammar/        dist: pydantree-sitter-grammar (HEAVY)
  rules.py          REBASED on pydantree_sitter.nodes: the mixins + to_ir()
                    + assemble()                                (~280 lines,
                    down from 476 — the annotation grammar moves to nodes.py)
  ir.py             UNCHANGED
  builder.py        UNCHANGED (the compile target)
  pipeline.py       ONE addition: write the generated node module into a bundle
  checks.py conflicts.py expressions.py corpus.py patterns.py scanners/
                    UNCHANGED
```

**Deleted outright:**
`src/pydantree_sitter/markers.py`, `src/pydantree_sitter/spec.py`,
`src/pydantree_sitter/valuemap.py`, `src/pydantree_sitter/codegen.py`,
`src/pydantree_sitter/compiler.py`, `src/pydantree_sitter/materialize.py`,
`src/pydantree_sitter/binding.py`. Full symbol-level inventory: **Appendix A**.

### 2.2 Public API (target: 12 names, down from 49)

```python
from pydantree_sitter import (
    Node,               # the base node class
    Grammar,            # language + schema + namespace + parse()
    Span,               # a source span
    generate_module,    # schema -> committed module source
    build_namespace,    # schema -> in-memory namespace
    load_bundle,        # a bundle directory -> Grammar
    NodeSchema,         # the schema model
    PydantreeSitterError, SchemaCheckError, SchemaDriftError,
    ShapeError, ExtractionError,
)
```

`Pattern` and friends stay exported from `pydantree_sitter.pattern`; they are
out of scope and are re-exported unchanged.

### 2.3 The target surface, end to end

**Step 1 — vendor the schema and generate the module (once, committed):**

```console
$ python -m pydantree_sitter.generate \
      --schema vendor/python-node-types.json \
      --language tree_sitter_python \
      --out mylang/python.py
```

**Step 2 — declare and extract:**

```python
import mylang.python as py

class Function(py.FunctionDefinition):
    """Narrow the generated class: `name` becomes text, not an Identifier."""
    name: str
    return_type: str | None

class Config(py.Dictionary):
    entries: dict[str, str]          # record projection, no mode flag

for fn in py.grammar.parse(src).find(Function):
    print(fn.name, fn.return_type, fn.span.line)
```

**What the metaclass checks at class creation, with no grammar loaded:**

- every annotated attribute exists as a field or child kind on the base class;
- the narrowed annotation is reachable from the base's declared types;
- optionality agrees with the schema (a schema-optional field annotated `str`
  is an error naming the schema entry);
- a `dict[...]` projection resolves to exactly one pair kind.

That is the whole of what `compiler.py`'s check jobs did, moved to where a type
checker can see it too.

### 2.4 Error taxonomy delta

```
PydantreeSitterError
  SchemaCheckError      # model <-> schema mismatch, raised at CLASS CREATION now
  SchemaDriftError      # NEW (D6): generated module vs loaded grammar mismatch
  ShapeError            # an unmappable annotation
  QueryBuildError       # tree-sitter rejected the emitted or raw query
  ExtractionError       # per-match failures, carries MatchFailure list
  BundleError
  PatternError + subclasses   # unchanged, out of scope
```

**Removed:** `AmbiguousCaptureError` (there are no capture names left to be
ambiguous — a field resolves to one child by schema), `TreeLanguageError`
(folded into `SchemaDriftError`).

---

## 3. Phase plan

| Phase | Title | Net effect | Risk |
|-------|-------|-----------|------|
| 0 | Ratchet: oracles before surgery | +oracles only | none |
| 1 | `nodes.py` — the node class core | +450, nothing deleted yet | low |
| 2 | `generate.py` — two renderings, one spec | +350, −220 (`codegen.py`) | low |
| 3 | Codecs on the class (idea 4) | −252 (`valuemap.py`) | medium |
| 4 | `Grammar` + `find.py` (idea 1 lands) | −1,400 net | **high** |
| 5 | Record mode deleted (idea 3) | −450 | medium |
| 6 | Product B rebased (idea 2 lands) | −200 | medium |
| 7 | Surface + deletion sweep | −1,100 | low |
| 8 | Docs, examples, skills | docs only | low |
| 9 | Final gates | none | none |

**Ordering rationale.** Phases 1-3 are additive and land behind the existing
surface, so the suite stays green throughout. Phase 4 is the cutover and is the
only phase where the suite goes red on purpose. Phase 5 depends on Phase 4's
nested-model support (D10). Phase 6 depends on Phase 1's annotation grammar.
Phase 7 deletes only what Phases 4-6 proved unreachable.

**Working rule.** Every phase is one lane and one commit. Run
`python -m pytest -q -m "not slow"` before landing. Run the full suite
(`python -m pytest -q`, needs the CLI and gcc) before Phases 4, 6 and 9.

---

## Phase 0 — Ratchet: oracles before surgery

**Goal.** Freeze today's observable behaviour so Phases 4-6 cannot change it by
accident. This phase writes tests only. It deletes nothing.

### Steps

**0.1 — Behaviour oracle.** Add `tests/test_oracle_024.py`. For each of the
seven grammars already vendored under `tests/fixtures/` (`bash`, `nix`, `rust`,
`markdown`, `markdown-inline`, `jsonlike`, `jsonlike_alias`, `jsonlike_hidden`),
declare one field-mode model and one record-mode model, extract over the
committed corpus, and assert the exact `model_dump()` list. Commit the expected
rows as `tests/fixtures/evidence/oracle_024/<grammar>.json`.

This is the contract Phase 4 must reproduce. It is written against the **current**
surface (`M`, `capture`, `record=True`) on purpose; Phase 7 rewrites it against
the new surface, and the row data must not change.

**0.2 — Schema inventory.** Add `tests/test_schema_inventory.py`: for each
vendored `node-types.json`, assert the counts the generator will depend on —
named kinds, supertype kinds, kinds with fields, kinds with a children summary,
and kinds that are text leaves. Print them into
`tests/fixtures/evidence/oracle_024/inventory.md`.

Purpose: Phase 2's generator must produce one class per named non-supertype kind
and one union per supertype kind. This file is what the count assertion checks
against.

**0.3 — Vendoring gap record.** Add `tests/test_wheel_schema_gap.py`, marked
`xfail(strict=True)` with the reason "D5: community wheels ship no
node-types.json". It asserts the absence, so that if a future wheel starts
shipping one, the suite tells us and D5's cost drops.

**0.4 — Baseline capture.** Record in
`.scratch/projects/024-typed-node-universe/BASELINE.md`: the fast-loop and full
suite counts, `wc -l` per source file, and the length of `__all__` for both
packages. Every later phase appends its own row.

### Validation gate

- `python -m pytest -q -m "not slow"` → 466 + the new tests, 0 failed.
- `python -m pytest -q tests/test_oracle_024.py` → green, and
  `git status` shows the evidence JSON committed.
- `BASELINE.md` exists and records the measured baseline:
  A extraction core = 4,301 lines, A ast-grep layer = 1,658 (out of scope),
  A total = 5,959 / 49 public names, B = 4,175, repo `src/` = 10,134.

### Cleanup

None. Phase 0 adds only.

---

## Phase 1 — `nodes.py`: the node class core

**Goal.** One base class, one metaclass, one annotation grammar. Nothing uses it
yet. It is added beside the existing surface, and the existing surface is
untouched.

### Steps

**1.1 — `Node` and `NodeMeta`.** Create `src/pydantree_sitter/nodes.py`.

```python
class Node(BaseModel, metaclass=NodeMeta):
    __kind__: ClassVar[str]                 # the CST node kind
    __schema__: ClassVar[NodeSchema | None] # bound at generation
    __under__: ClassVar[tuple | None] = None
    _node: tree_sitter.Node = PrivateAttr()
    _span: Span = PrivateAttr()

    @property
    def span(self) -> Span: ...
    def __value__(self) -> str: ...         # default codec: the node text
```

`NodeMeta.__new__` does four things and nothing else:

1. derive `__kind__` from the class name (`_snake`), unless declared;
2. parse the class's own annotations into an ordered `tuple[Child, ...]`
   (the annotation grammar, 1.2);
3. when a base carries `__schema__`, run the class-creation checks (1.3);
4. build and cache the resolver (1.4).

**1.2 — The annotation grammar (one table, written once).** Move the row table
that today lives in `pydantree_sitter_grammar.rules._child` into `nodes.py`, and
make it the single definition both directions read:

| Annotation | Meaning |
|---|---|
| `x: SomeNode` | one child, CST field `x` |
| `x: SomeNode \| None` | optional child |
| `x: list[SomeNode]` | repeated child |
| `x: A \| B` | choice of kinds |
| `x: Literal["="]` | anonymous token (B direction) / literal check (A direction) |
| `x: str \| int \| bool \| float` | the child's `__value__`, coerced by pydantic |
| `x: dict[str, V]` | the record projection (Phase 5) |
| `content: ...` | the reserved label: an unnamed child |

Represent the parse result as a frozen `Child` dataclass:
`name, kinds, optional, repeated, literal, target, is_record`. This is the
replacement for `spec.FieldBinding` and it carries no capture names.

**1.3 — Class-creation checks.** Implement `_check_against_schema(cls)`. It
raises `SchemaCheckError` naming the schema entry when:

- an attribute is neither a field nor a possible child kind of `__kind__`;
- the narrowed kinds are not a subset of `schema.field_types(kind, attr)`
  (supertypes expanded via `schema.expand`);
- a schema-optional field is annotated non-optional, or the reverse;
- a schema-`multiple` field is not annotated `list[...]`, or the reverse.

Port the *messages* from `compiler._check_field_bindings` and `_check_type` —
they are good, and the error text is what users see.

**1.4 — The resolver.** `_build_resolver(cls)` returns a
`Callable[[tree_sitter.Node], dict]` closed over the parsed `Child` tuple. It
uses `child_by_field_name` and `field_name_for_child`, never a query. This is
the function `find.py` calls per anchor in Phase 4, and it is what makes nested
models (D10) a one-liner: a nested `Child` calls the nested class's resolver.

**1.5 — `__under__`.** Accept a tuple of node classes with `...` for a gap.
Normalise to the `PathStep | GAP` tuple `match.match_ancestor_path` already
consumes, so the existing backtracking matcher and its hypothesis property test
are reused unchanged.

**1.6 — Move `Span`.** Create `src/pydantree_sitter/span.py` and move `Span`
there verbatim, **keeping the `node.range` tuple-unpack comment about
py-tree-sitter#472**. Re-export from `materialize.py` for now so nothing breaks.

### Validation gate

- **New unit suite** `tests/test_nodes.py`, built on the vendored `jsonlike` and
  `rust` schemas:
  - every annotation-grammar row above parses to the expected `Child`;
  - each of the four check failures in 1.3 raises `SchemaCheckError`, and the
    message names the offending schema entry (assert on the substring);
  - a resolver over a hand-built tree returns the expected kwargs;
  - `__under__` normalisation feeds `match_ancestor_path` and agrees with the
    existing `M()` normalisation for the same path (assert equality of the
    normalised tuples — this pins the reuse).
- **Property test.** Extend the existing hypothesis test for
  `match_ancestor_path` to run against `__under__`-normalised paths.
- **Full fast loop stays at the Phase-0 count.** `nodes.py` is imported by
  nothing yet, so a regression here means an accidental import.
- `python -c "import pydantree_sitter"` still exposes exactly 49 names.

### Cleanup

None yet — but record the **claim list**, which Phase 7 will collect:
`spec.FieldBinding`, `spec.MatchSpec`, `spec.PathStep`, `spec.derive_spec`,
`spec.DerivingMeta`, `spec.binding_warnings`, `markers.*`,
`rules._child` (B side), `rules._from_annotations` (B side).

---

## Phase 2 — `generate.py`: two renderings, one spec

**Goal.** Replace `codegen.py`'s `TypedNode` emitter with a generator that emits
`Node` subclasses, in both a source rendering and an in-memory rendering, from
one spec builder.

### Steps

**2.1 — `_class_specs(schema)`.** A pure function returning an ordered list of
`ClassSpec(kind, class_name, bases, children, is_supertype, subtypes)`. Reuse
`codegen.class_name`, `codegen._attr_name` and the dependency-first supertype
ordering (including the cyclic-union `ValueError`) verbatim — that logic is
correct and tested.

**2.2 — `generate_module(schema, *, language_import, fingerprint)`.** Emits a
runnable module:

- `from pydantree_sitter import Node, Grammar`;
- one `class Kind(Node)` per named non-supertype kind, with `__kind__` and the
  schema-derived annotations;
- one type alias per supertype kind, emitted dependency-first;
- `KIND_MAP`;
- `__fingerprint__ = (...)` — the D6 tuple;
- `grammar = Grammar._from_generated(__name__, language_import, __fingerprint__)`.

**2.3 — `build_namespace(schema, language)`.** Same `ClassSpec` list, built with
`type()` into a `SimpleNamespace`. Assert in a test that a class built this way
and a class imported from the generated source have equal `__kind__` and equal
parsed `Child` tuples.

**2.4 — CLI.** `python -m pydantree_sitter.generate --schema X --language M --out Y`.

**2.5 — Bundle hook.** In `pipeline.write_bundle`, also write `nodes.py` next to
`node-schema.json`. A bundle then ships its own type universe, and
`Grammar.load_bundle` can import it.

### Validation gate

- **Round-trip per vendored grammar** (`tests/test_generate.py`): for all eight
  fixtures, `generate_module` output must
  1. compile (`compile(src, name, "exec")`),
  2. import cleanly in a temp package,
  3. produce one class per named non-supertype kind — count asserted against
     Phase 0's `inventory.md`,
  4. produce a type alias per supertype kind.
- **Source vs in-memory equality** (2.3): for all eight fixtures, assert equal
  `__kind__` and equal `Child` tuples across the two renderings.
- **Golden module.** Commit `tests/fixtures/evidence/oracle_024/jsonlike_nodes.py`
  as a byte oracle, checked in CI. Regeneration is a deliberate `--update` run,
  matching the `regenerate_community_node_types.py` pattern already in the repo.
- **Static check.** `ty` (the active gate) must pass on the generated golden
  module. This is the proof that idea 1 delivers edit-time errors.
- Cyclic-supertype schema still raises `ValueError` with the same message —
  port the existing test.

### Cleanup

- **Delete `src/pydantree_sitter/codegen.py`** in full: `generate_typed_api`,
  `write_typed_api`, `_union`, `_ref_name`, `_ATTR_SHADOWS`, `TypedNode`.
  Keep `class_name` and `_attr_name` by moving them into `generate.py`.
- Delete `tests/test_codegen.py`'s `TypedNode` assertions; the file becomes
  `tests/test_generate.py`.
- Remove `codegen` from `docs/user-guide.md`'s "typed-CST codegen" section
  (rewritten in Phase 8) and from `.agents/skills/pydantree-extraction/SKILL.md`.
- Grep gate: `grep -rn "TypedNode\|generate_typed_api\|write_typed_api" src tests docs examples .agents` → empty.

---

## Phase 3 — Codecs on the class; delete `ValueMap`

**Goal.** Idea 4. Move value decoding onto the node class and remove the
side-car map, the inference, and the `Unescaped` marker.

### Steps

**3.1 — `__value__` on `Node`.** Default implementation returns
`self._node.text.decode("utf-8")`. The **return annotation** is the declared
value type; `nodes._value_type(cls)` reads it. This replaces
`ValueMap.scalars`.

**3.2 — Wrapper codecs are methods.** A wrapper kind overrides `__value__` to
read its text leaf:

```python
class String(Node):
    __kind__ = "string"
    def __value__(self) -> str:
        return "".join(c.text for c in self._node.children
                       if c.type == "string_content")
```

This replaces `ValueMap.wrappers` and `_wrapper_text_leaf`.

**3.3 — `Unescaped()` becomes a codec.** Move `_unescape_json_string` from
`materialize.py` into `pydantree_sitter/codecs.py` as `unescape_json`, and ship
one `JsonString` mixin that calls it. Keep the manual-decode fallback path
verbatim — it handles grammars that permit raw newlines and it is tested.

**3.4 — Arrays.** `ValueMap.arrays` is deleted with no replacement: `list[T]`
already says it, and the element kinds come from
`schema.field_types` / `schema.children_types`.

**3.5 — `suggest_codecs(schema)`.** Port the `propose_value_map` heuristics
(`_is_numeric`, `_is_float`, `_is_boolean`, `_is_null`, `_text_leaf_kind`) into
`generate.suggest_codecs`, which **prints** `__value__` stubs to stdout and
returns `None`. It is reachable only as
`python -m pydantree_sitter.generate --suggest-codecs`. It is not in `__all__`.

**3.6 — Overrides file.** The generator accepts `--codecs mymodule`, and emits
`from mymodule import *  # codec overrides` plus a per-kind base-class lookup, so
a user's `String.__value__` lands on the generated `String`. Document the file as
"the one place value decoding lives".

### Validation gate

- **Equivalence oracle.** `tests/test_codecs.py`: for the JSON family, assert
  that `__value__` over every kind in `JSON_VALUE_MAP` returns a value equal to
  what the current `ValueMap` path produces. Build this table *before* deleting
  `valuemap.py`, from the live `JSON_VALUE_MAP`, and commit it as
  `tests/fixtures/evidence/oracle_024/json_value_table.json`.
- **`Unescaped` parity.** Port `tests/test_extract.py::test_unescaped_decodes_json_string`
  to the codec form and assert the same output string
  (`'a\nb\t"c"\\dA'`), including the manual-fallback branch.
- **`suggest_codecs` is inert.** Assert it writes no file, returns `None`, and
  is absent from `pydantree_sitter.__all__`.
- Fast loop still green (`valuemap.py` still present at this point; the codec
  path runs beside it).

### Cleanup

- **Delete `src/pydantree_sitter/valuemap.py`** in full: `ValueMap`,
  `JSON_VALUE_MAP`, `JSON_KINDS`, `Scalar`, `looks_like_json`,
  `propose_value_map`, `scalar_kinds_for`, `_wanted_scalars`,
  `wrapper_kinds_for`, `array_kinds_for`, `_is_numeric`, `_is_float`,
  `_is_boolean`, `_is_array`, `_is_null`, `_text_leaf_kind`,
  `_wrapper_text_leaf`.
- Delete `markers.Unescaped`.
- Delete `binding.resolve_value_map`, `Language.value_map`,
  `Language._value_map`, and the `value_map=` parameter from
  `Language.__init__` / `load` / `from_module` / `load_bundle` /
  `_transient_language`.
- Delete the `value_map` bundle-metadata key from `loader.py` and
  `pipeline.write_bundle`; delete its mention in `docs/architecture.md`.
- Delete `tests/test_valuemap_check.py`; fold any surviving assertions into
  `tests/test_codecs.py`.
- Delete `compiler._proposed`, `_scalar_of`, `_text_shape`, `_is_text_leaf`,
  `_kind_coerces` — all are `ValueMap` consumers.
- Grep gate: `grep -rn "ValueMap\|value_map\|propose_value_map\|JSON_VALUE_MAP\|Unescaped\|looks_like_json" src tests docs examples .agents` → empty.

---

## Phase 4 — `Grammar` + `find.py`: idea 1 lands

**Goal.** The cutover. Extraction runs from node subclasses. This is the only
phase where the suite goes red on purpose, and the only phase that is high risk.

**Land this phase behind a branch and do not push until 4.8 is green.**

### Steps

**4.1 — `grammar.py`.** One class replaces `Language` + `Extractor`.

```python
class Grammar:
    language: tree_sitter.Language
    schema: NodeSchema
    nodes: SimpleNamespace          # the type universe

    @classmethod
    def load(cls, language, schema) -> Grammar          # schema REQUIRED (D5)
    @classmethod
    def load_bundle(cls, dir) -> Grammar
    def parse(self, source) -> Tree
    def check_fingerprint(self, fp) -> None             # D6
```

Delete on sight, do not port: the `weakref.WeakKeyDictionary` sugar cache, the
`threading.RLock` that guards it, `_transient_language`, `_language_for`,
`_sugar_extractor`, and the four-way `Model.extract` / `extract_tree` /
`validate_with` / `compiled_source` entry set. They all exist to paper over
"which of five language spellings did the caller pass". `Grammar.load` takes a
language and a schema, and that is the whole contract.

**4.2 — `Tree.find(cls)`.** A thin wrapper over `tree_sitter.Tree` carrying the
`Grammar`. `find(cls)` returns `list[cls]`. Also `find_one`, and
`find_in(node)` for scoped extraction (this is what `PatternMatch.extract` and
nested models call).

**4.3 — `find.py`: query emission from a node subclass.** Port
`compiler._compile_field`, `_capture_spec`, `_field_quant`, `_split_suffix`,
`_path_combinations`, `_wrap_anchor` — but:

- the anchor kind is `cls.__kind__` (no path to walk for it);
- capture kinds come from `schema.field_types(kind, attr)`, not from `ValueMap`
  inference — delete `_infer_field_kind` and `_possible_for`;
- there is no wildcard branch (D5), so every `if schema is None` arm is deleted,
  not preserved;
- the `__under__` prefix feeds `match.match_ancestor_path` exactly as
  `MatchSpec.path` did.

**4.4 — The match loop.** Port `materialize.extract_field` and its helpers
(`_malformed`, `_malformed_labels`, `_allowed_missing`, `_first_anchor`,
`_failure`, `_required_captures_present`) into `find.py`. Replace
`build_kwargs` with the Phase-1 resolver: the loop now produces an anchor node,
and the resolver produces kwargs.

**4.5 — Nested models (D10).** Delete the `ShapeError` in `spec._field_binding`
that rejects nested models in field mode. A `Child` whose `target` is a `Node`
subclass calls that class's resolver on the child node. Recursion is bounded by
the tree, so the `_LazyExtractor` self-recursion hack in `compiler.py` is
deleted, not ported.

**4.6 — Predicates.** `Matches`, `Eq`, `AnyOf` survive as `Annotated[...]`
metadata and keep emitting `#match?` / `#eq?` / `#any-of?`. They are the one
part of the marker surface that has no type-system equivalent. Move them from
`markers.py` into `nodes.py`.

**4.7 — `raw.py` (D13).** `__raw_query__` support, isolated: compile the literal
`.scm` via `emit.Query.raw`, run it, map captures to attributes by name, hand
the kwargs to pydantic. It keeps the existing capture-name-exists check.

**4.8 — Repoint `PatternMatch.extract`.** One call site in `pattern.py`:
`extract_tree_scoped(node, tree)` becomes `tree.find_in(node, cls)`. Nothing
else in the ast-grep layer changes.

### Validation gate

This is the gate that matters. Do not proceed to Phase 5 until every item is
green.

1. **The Phase-0 behaviour oracle reproduces byte for byte.** Rewrite
   `tests/test_oracle_024.py`'s *models* to the new surface, leave the expected
   `tests/fixtures/evidence/oracle_024/*.json` **untouched**, and require an
   exact match. A changed expectation file in this phase's diff is a failure,
   not a fix — review it as such.
2. **Every `tests/test_extract.py` field-mode case passes** after mechanical
   translation (Appendix C is the translation table). Record-mode cases are
   expected to fail here; mark them `xfail(strict=True)` with reason
   "Phase 5: D9" so Phase 5 flips them.
3. **`tests/test_match.py` and the hypothesis property test pass unchanged.**
   `match.py` was not supposed to change; if it did, revert that part.
4. **`tests/test_pattern_*.py` pass unchanged** except the one `extract` call
   site. Their diff must be one line.
5. **Full suite** (`python -m pytest -q`, with the CLI and gcc) green apart from
   the Phase-5 `xfail`s.
6. **Fingerprint drift is caught.** New test: generate a module from the `nix`
   schema, load it against the `rust` language, assert `SchemaDriftError` and
   assert the message names both grammars.
7. **Schema-less binding is gone.** New test: `Grammar.load(lang)` with no
   schema raises `TypeError`; the string "schema-less" appears nowhere in `src/`.
8. **Warning count drops to zero.** The Phase-0 run emitted 47 warnings, nearly
   all "schema-less binding". Assert `-W error` passes on the fast loop.

### Cleanup

- **Delete `src/pydantree_sitter/binding.py`**: `Language`, `Extractor`,
  `_resolve_language`, `_load_schema` (move the `NodeSchema | path | dict`
  normalisation into `Grammar.load`), `_language_fingerprint` (moves to
  `grammar.py`), `_language_for`, `_transient_language`, `_sugar_extractor`,
  `resolve_value_map`, `_LANGUAGE_CACHE`, `_LANGUAGE_LOCK`, `_point_of`,
  `_apply_edit` (moves to `grammar.py` for `reparse`).
- **Delete `src/pydantree_sitter/compiler.py`**: `_Compiled`, `compile_spec`,
  `_bind_compile`, `emitted_source`, `_LazyExtractor`, `_compile_field`,
  `_check_path`, `_check_field_bindings`, `_check_type`, `_infer_field_kind`,
  `_possible_for`, `_model_site`, `_raise`, `_annotation`, `_name`.
  (`_compile_record` and its ten helpers go in Phase 5.)
- **Delete `src/pydantree_sitter/materialize.py`**: `build_kwargs`,
  `_binding_for`, `_is_marker_default`, `_is_optional`, `_text_of`,
  `extract_field`, `_anchor_of`. `Span` already moved in 1.6; `MatchFailure`
  moves to `errors.py`.
- **Delete from `emit.py` (D13)**: `NodeSpec`, `PatternSet`, `Pred`,
  `CaptureRef`, `cap`, `node`, `_emit`, `_q`, `Query.__init__`'s spec path,
  `Query.capture_names`'s spec branch, `_capture_names_of`. Keep `Query.raw`,
  `Query.compile`, `Query.source`, `Cursor`, `MatchView`.
- **Delete `AmbiguousCaptureError`, `raise_ambiguous_capture`,
  `match.merge_group`, `match._dedup_by_id`, `match.group_matches`** — with one
  child per attribute resolved by schema, there is no anchor merge and no scalar
  ambiguity. `match.py` keeps only `match_ancestor_path` and `_match_steps`.
- **Delete `TreeLanguageError`** (folded into `SchemaDriftError`).
- Delete `tests/test_raw_query.py`'s bind-path assertions that referenced
  `Extractor`; keep the query-behaviour assertions in `tests/test_raw.py`.
- Grep gate:
  `grep -rn "Extractor\|compile_spec\|_Compiled\|build_kwargs\|extract_field\|AmbiguousCaptureError\|emitted_source\|TreeLanguageError" src tests docs examples .agents` → empty.

---

## Phase 5 — Record mode deleted

**Goal.** Idea 3. One spelling, one semantics. `record=True` and everything it
switched on disappears.

### Steps

**5.1 — `list[Nested]` is the general form.** It already works after 4.5. Confirm
with the translation of every record-mode test: a record model becomes a nested
pair model plus a `list[Pair]` attribute on the container.

**5.2 — `dict[str, V]` is the sugar.** In `nodes.py`, a `dict[str, V]`
annotation resolves at class creation:

- find the pair kind: the child kinds of `__kind__` that have **both** a `key`
  and a `value` field. Port `compiler._find_pair_kind`'s candidate search;
- **zero candidates** → `ShapeError` naming `__kind__` and its child kinds;
- **more than one candidate** → `ShapeError` naming all candidates, and telling
  the user to write `list[Pair]` with an explicit pair class instead. This
  replaces `record_pair=`, which existed only to break this tie;
- **one candidate** → emit the projection.

The key's text shape comes from the pair's `key` field types via
`schema.field_types`; the value's from `V`'s `__value__`.

**5.3 — Predicate filtering.** Today a failing predicate on a required record
field filters the whole record, and on an optional field leaves it `None`
(`tests/test_extract.py::test_predicate_on_record_field`). Preserve this exactly
in the `dict` projection. It is a real, tested behaviour and the easiest thing
in this phase to lose.

**5.4 — Flip the Phase-4 `xfail`s.** Each record-mode test in
`tests/test_extract.py` becomes either a `dict[str, V]` test or a
`list[Pair]` test. Rows must be identical.

### Validation gate

- **The Phase-0 record-mode oracle reproduces byte for byte.** Same rule as 4.1:
  the expected JSON must not change.
- All Phase-4 `xfail(strict=True)` markers removed, tests green. A leftover
  `xfail` here means the phase is incomplete.
- **Self-recursive records still work**
  (`tests/test_extract.py::test_self_recursive_record_binds_and_extracts_finite_nesting`)
  through `list[Nested]` with a self-reference, after `model_rebuild()`.
- **Descendant records still work**
  (`test_descendant_record_mode`, the `M("document", ..., "object", record=True)`
  case) through `__under__ = (Document, ...)`.
- **Ambiguity is an error with a good message.** New test on the `nix` fixture,
  which has several key/value child kinds: assert `ShapeError`, assert the
  message lists every candidate, and assert it suggests `list[Pair]`.
- **`Unescaped` in a record** — the `test_unescaped_decodes_json_string` case —
  now runs through the Phase-3 codec inside a `dict` projection. Same output.

### Cleanup

- **Delete from `compiler.py` (finishing the file)**: `_compile_record`,
  `_find_pair_kind`, `_key_shapes`, `_leaf_shape`, `_key_spec_one`,
  `_value_shapes`, `_base_target`, `_scalar_shapes`, `_list_shapes`,
  `_unescape_shapes`, `_check_record_bindings`, `_preds_for`. Then delete
  `compiler.py` itself.
- **Delete from `materialize.py` (finishing the file)**: `extract_record`,
  `_record_kwargs`. Then delete `materialize.py` itself.
- **Delete `markers.RECORD_CAP`**, `M.record`, `M.record_pair`,
  `MatchSpec.record`, `MatchSpec.record_pair`,
  `FieldBinding.source == "record_key"` and every branch that tested it.
- Delete `_Compiled.records`, `.fields`, `.record_kind`, `.pair_kind`,
  `.records_quant_maps`, `.fields_quant_maps` — dead with `_Compiled`.
- Remove the "record mode" section from `docs/user-guide.md` and the record
  paragraphs from `docs/architecture.md` and
  `.agents/skills/pydantree-extraction/SKILL.md`.
- Update `tests/fixtures/consumers/consumer_markdown.py`,
  `consumer_bash.py`, `consumer.py`, `consumer_community.py` — all four use
  `record=True`.
- Grep gate:
  `grep -rn "record=True\|record_pair\|record_kind\|pair_kind\|RECORD_CAP\|extract_record\|_record_kwargs" src tests docs examples .agents` → empty.

---

## Phase 6 — Product B rebased: idea 2 lands

**Goal.** One annotation grammar, two directions. `pydantree_sitter_grammar.Rule`
becomes a `pydantree_sitter.Node` subclass, and the duplicated annotation parser
is deleted.

### Steps

**6.1 — Rebase the base.** `pydantree_sitter_grammar.rules.Rule` becomes:

```python
class Rule(Node):
    __abstract__ = True
    __schema__ = None       # forward direction: no schema to check against
```

The `_RuleMeta` metaclass is deleted; `NodeMeta` takes over kind naming
(`_snake`, which moves to `nodes.py`), site capture, and annotation parsing.
`__abstract__` moves into `NodeMeta` as a skip flag.

**6.2 — `to_ir()` is the forward direction.** Replace `rules._child` and
`rules._from_annotations` with `to_ir(cls) -> B | str`, which walks the
**Phase-1 `Child` tuple** instead of re-parsing annotations. The row table
(`field`, `repeat`, `choice`, `opt`, `Literal` token, the `content` label) is
unchanged in behaviour — only its input changes.

**6.3 — Keep the B-only pieces.** `Pattern`, `Token`, `External`, `Extra`,
`Supertype`, `Hidden`, `Inline`, `Word`, `R()`, `assemble()`, `module_rules()`,
`__body__`, `__pattern__`, `__external__`, `__rule_name__` all stay. They express
grammar-authoring facts that have no meaning in the backward direction.

**6.4 — Site capture.** `NodeMeta` captures `__site__` and `__attr_sites__`
through the existing `builder.caller_site`. Keep the frame-depth unit test; the
metaclass moved packages, so the depth changes and the test is what catches it.
(Removing frame walking entirely is brainstorm idea 12 — deferred, see
Appendix E.)

**6.5 — The round-trip invariant (D12).** New test
`tests/test_direction_roundtrip.py`:

1. take `examples/devenv-subset/grammar.py`'s classes;
2. `assemble()` → build → `node-types.json`;
3. `generate.build_namespace(schema)` → generated classes;
4. for every authored class that survives generation (not `Hidden`, not
   `Inline`, not `Extra`), assert the generated class's `Child` tuple matches
   the authored one on: attribute name, kind set, `optional`, `repeated`.

Differences that are legitimate (the CLI erases hidden and inline rules, and
inlines supertype members) must be listed explicitly in the test as a named
allowance set — not silently skipped.

### Validation gate

- `tests/test_rules.py`, `tests/test_rules_sites.py`, `tests/test_builder.py`,
  `tests/test_grammar_ir.py`, `tests/test_ladder.py`, `tests/test_conflicts.py`
  pass unchanged.
- **Full suite** with CLI and gcc: `tests/test_pipeline.py`,
  `tests/test_bundle.py`, `tests/test_corpus.py`,
  `tests/test_community_fixtures.py` green.
- `examples/devenv-subset/extract.py` runs end to end and produces the same rows
  as before this project — compare against the Phase-0 oracle.
- **`tests/test_wheel_example.py` still byte-matches** after `transcript.txt` is
  regenerated with `--update`. The transcript **will** change (the surface
  changed); review the diff line by line and confirm every changed line is a
  surface change, not a row change.
- **D12 round-trip green.** If it fails, stop. D11 is wrong, and Phase 7 must not
  delete anything until it is resolved.

### Cleanup

- Delete `rules._RuleMeta`, `rules._child`, `rules._from_annotations`,
  `rules._wrap`, `rules._resolve`, `rules._snake` (moved to `nodes.py`),
  `rules._rule_site`, `rules._attr_sites` (moved to `nodes.py`).
- Delete the duplicated annotation-grammar docstring table from
  `rules.py` — `nodes.py` owns it now, and `rules.py` links to it.
- Delete `pydantree_sitter_grammar.language` if `Grammar.load_bundle` covers it
  (check `tests/test_loader.py` first).
- Grep gate: `grep -rn "_RuleMeta\|_from_annotations\|def _child" src tests` → empty.

---

## Phase 7 — Surface and deletion sweep

**Goal.** Collect every claim the previous phases made. After this phase the
codebase must contain no path that the new surface does not reach.

### Steps

**7.1 — Delete `spec.py` and `markers.py`.** Both are now unreachable:
`OutputModel`, `DerivingMeta`, `derive_spec`, `MatchSpec`, `FieldBinding`,
`PathStep`, `binding_warnings`, `unwrap_optional`, `is_optional`,
`_field_is_query_optional`, `_kind_override`, `_predicate_markers`,
`_resolve_annotation`, `_try_resolve_forward_ref`, `_field_binding`,
`_sugar_extractor`; and `M`, `GAP`, `ANCHOR`, `capture`, `capture_kind`,
`source_meta`, `derived`, `_Capture`, `_CaptureKind`, `_SourceMeta`, `_Derived`,
`_MARKERS`, `_MISSING`, `RawQuery`.

Two names survive by moving, not by staying:
- `unwrap_optional` / `is_optional` → `nodes.py` (the annotation grammar needs
  them);
- `Matches` / `Eq` / `AnyOf` → `nodes.py` (4.6);
- `RawQuery` → `raw.py` (D13).

`source_meta()` has no replacement and needs none: `span` is a property on every
node instance, so `line: int = source_meta()` becomes `fn.span.line`.

**7.2 — Rewrite `__init__.py`.** Target the 12 names in §2.2. Assert the count in
a test so the surface cannot quietly regrow.

**7.3 — Prune `errors.py`.** Remove `AmbiguousCaptureError`,
`raise_ambiguous_capture`, `TreeLanguageError`, `UnsupportedLanguageError`'s
duplicate docstring reference to the removed bind path. Add `SchemaDriftError`.
Update the module docstring's taxonomy diagram; it is currently the taxonomy
users read.

**7.4 — Dead-code sweep.** Run, and act on every hit:

```console
$ ruff check --select F401,F811,ARG,ERA src tests
$ python -X importtime -c "import pydantree_sitter" 2>&1 | tail -30
$ ty check src
```

The `importtime` run is the cheapest detector of a module that survived only
because something still imports it.

**7.5 — Test-file sweep.** Rename and merge:

| Old | New |
|---|---|
| `test_tsquery_port.py`, `test_tsquery_schema.py` | fold into `test_find.py` |
| `test_codegen.py` | `test_generate.py` (Phase 2) |
| `test_valuemap_check.py` | `test_codecs.py` (Phase 3) |
| `test_schema.py` | unchanged |
| `test_raw_query.py` | `test_raw.py` |
| `test_checks_nullable.py`, `test_phase6_fixes.py` | fold into the suite they pin, or delete if the pinned bug is now impossible by construction |

For each test deleted rather than moved, record **one line** in
`.scratch/projects/024-typed-node-universe/DELETED_TESTS.md` saying which
construction now makes the bug impossible. A deleted test with no such line is
lost coverage, not a simplification.

**7.6 — `pyproject.toml`.** Bump both distributions to `0.3.0` (D16). Remove the
`value_map` extra if one exists. Confirm `pydantree_sitter_grammar` still depends
on `pydantree_sitter`, and that A still never imports B.

### Validation gate

- **Surface count test**: `len(pydantree_sitter.__all__) == 12`, and the names
  match §2.2 exactly.
- **A never imports B**: existing `tests/test_packaging.py` assertion passes.
- `ruff check` and `ty check` clean — these are the repo's active gates.
- **Full suite green**, including slow tests.
- **Line count**: record in `BASELINE.md`. Expected end state for the
  extraction core is ~2,500 lines (from 4,301). If the number is higher, a
  subsystem survived that should not have; find it before Phase 8.
- **Appendix B grep gate empty.**

### Cleanup

This phase *is* the cleanup. The list is Appendix A.

---

## Phase 8 — Docs, examples, skills

**Goal.** No document describes a surface that no longer exists.

### Steps

**8.1 — `README.md`.** Rewrite the quick-start to §2.3. **Delete the "honesty
statements" section entirely**: C1's `M()` ceiling is gone with `M()`, and C2's
value-shape statement is gone with `ValueMap`. What remains of C1 — sibling
order, negation, multi-anchor joins — is one sentence in the `__raw_query__`
paragraph.

**8.2 — `docs/user-guide.md` (567 lines).** Rewrite the Product A half. Delete
the `capture` / `capture_kind` / `source_meta` / `derived` reference, the record
mode section, the `ValueMap` section, and the typed-CST-codegen section (codegen
is no longer a side feature — it is step 1 of the quick start). **Add** a
"vendoring a schema" section; D5 makes it the first thing a new user must do,
and it is the one genuinely new burden this project creates.

**8.3 — `docs/architecture.md` (380 lines).** Replace the A/B split diagram: the
seam is now the node-class universe, not the schema-check bridge. Keep the
bundle-layout and pipeline sections unchanged.

**8.4 — `docs/README.md`.** Add row 024 to the phase table.

**8.5 — Examples.**
- `examples/wheel-extract/` — **needs a vendored schema (D5)**. Add
  `vendor/python-node-types.json` from the tree-sitter-python source repository,
  add `mylang/python.py` generated from it, and regenerate `transcript.txt`.
  This example is the flagship toolchain-free path; it must stay toolchain-free,
  and vendoring a JSON file keeps it so.
- `examples/bash-extract/`, `examples/devenv-extract/` — already carry
  `node-schema.json`. Regenerate the node module and update the models.
- `examples/devenv-subset/` — the both-halves example. Its grammar classes now
  *are* node classes; make that visible in the module docstring, and add the D12
  round trip as a printed step.

**8.6 — Agent skills.** Rewrite `.agents/skills/pydantree-extraction/SKILL.md`
completely. Update `pydantree-grammar/SKILL.md` for the rebased `Rule`, and
`pydantree-dev/SKILL.md` for the new module map. Leave
`pydantree-scanners/SKILL.md` alone.

**8.7 — `CLAUDE.md`.** Fill in the "Where things live" section with the new
module map; it is currently a seed placeholder.

### Validation gate

- `grep -rn` for every deleted public name across `README.md`, `docs/`,
  `examples/`, `.agents/`, `CLAUDE.md` → empty (this is Appendix B, run wide).
- Every fenced Python block in `README.md` and `docs/user-guide.md` compiles.
  Add `tests/test_docs_snippets.py` to enforce it; the repo has no such test
  today and doc drift is what makes an elegant surface look complicated.
- `examples/wheel-extract/extract.py` exits 0 with a byte-matching transcript.
- All three other examples run in-devenv.

### Cleanup

- Delete `docs/user-guide.md`'s record-mode, `ValueMap`, and marker-reference
  sections outright. Do not leave a "removed in 0.3" note; Appendix C is the
  migration record and it lives here, in the project directory.

---

## Phase 9 — Final gates

Run all of it, in order, and paste the output into
`.scratch/projects/024-typed-node-universe/FINDINGS.md`.

```console
$ python -m pytest -q                       # full suite, CLI + gcc present
$ python -m pytest -q -W error              # zero warnings (Phase 4 gate 8)
$ ruff check src tests examples
$ ty check src
$ python -m pytest -q tests/test_docs_snippets.py
$ python examples/wheel-extract/extract.py
$ devenv shell -- python examples/devenv-subset/extract.py
```

Then Appendix B, then:

```console
$ wc -l src/pydantree_sitter/*.py src/pydantree_sitter_grammar/*.py
$ python -c "import pydantree_sitter as p; print(len(p.__all__))"
```

**Ship criteria.**

| Metric | Baseline | Target |
|---|---|---|
| Product A public names | 49 | 12 |
| A extraction core (in scope) | 4,301 | ~2,500 (−42%) |
| A total (incl. the ast-grep layer) | 5,959 | ~4,200 (−30%) |
| Product B | 4,175 | ~3,950 (−5%) |
| Repo `src/` total | 10,134 | ~8,100 (−20%) |
| Suite warnings | 47 | 0 |
| Modules in Product A | 17 | 16 |
| Ways to spell "a piece of syntax" | 5 | 3 |
| D12 round trip | absent | green |

Three spellings remain, not one: the node class, `__raw_query__`, and the
ast-grep `Pattern`. Removing the last two is ideas 6 and 10 — Appendix E.

---

## Appendix A — Deletion inventory

Every name below must be unreachable when Phase 7 ends. Grouped by the phase
that removes it.

### Phase 2 — `codegen.py` (whole file, 220 lines)
`generate_typed_api`, `write_typed_api`, `TypedNode`, `_union`, `_ref_name`,
`_ATTR_SHADOWS`. `class_name` and `_attr_name` move to `generate.py`.

### Phase 3 — `valuemap.py` (whole file, 252 lines)
`ValueMap`, `JSON_VALUE_MAP`, `JSON_KINDS`, `Scalar`, `_SCALARS`,
`looks_like_json`, `propose_value_map`, `scalar_kinds_for`, `_wanted_scalars`,
`wrapper_kinds_for`, `array_kinds_for`, `_is_numeric`, `_is_float`,
`_is_boolean`, `_is_array`, `_is_null`, `_text_leaf_kind`, `_wrapper_text_leaf`.

Plus: `markers.Unescaped`, `binding.resolve_value_map`, `Language.value_map`,
`Language._value_map`, the `value_map=` parameter on five constructors, the
`value_map` bundle-metadata key, `compiler._proposed`, `compiler._scalar_of`,
`compiler._text_shape`, `compiler._is_text_leaf`, `compiler._kind_coerces`.

### Phase 4 — `binding.py` (533), most of `compiler.py`, most of `materialize.py`
`Language`, `Extractor`, `_resolve_language`, `_load_schema`, `_language_for`,
`_transient_language`, `_sugar_extractor`, `_LANGUAGE_CACHE`, `_LANGUAGE_LOCK`,
`_default_astgrep_name` (moves to `grammar.py`), `_ASTGREP_NAMES` (moves).

`_Compiled`, `compile_spec`, `_bind_compile`, `emitted_source`,
`_LazyExtractor`, `_compile_field`, `_check_path`, `_check_field_bindings`,
`_check_type`, `_infer_field_kind`, `_possible_for`, `_capture_spec`,
`_field_quant`, `_split_suffix`, `_path_combinations`, `_wrap_anchor`,
`_model_site`, `_raise`, `_annotation`, `_name`.

`build_kwargs`, `_binding_for`, `_is_marker_default`, `_is_optional`,
`_text_of`, `extract_field`, `_anchor_of`, `_allowed_missing`, `_first_anchor`,
`_failure` (the last three move into `find.py`).

`emit.NodeSpec`, `emit.PatternSet`, `emit.Pred`, `emit.CaptureRef`, `emit.cap`,
`emit.node`, `emit._emit`, `emit._q`, `emit._capture_names_of`.

`match.group_matches`, `match.merge_group`, `match._dedup_by_id`.

`errors.AmbiguousCaptureError`, `errors.raise_ambiguous_capture`,
`errors.TreeLanguageError`.

### Phase 5 — the rest of `compiler.py` and `materialize.py`
`_compile_record`, `_find_pair_kind`, `_key_shapes`, `_leaf_shape`,
`_key_spec_one`, `_value_shapes`, `_base_target`, `_scalar_shapes`,
`_list_shapes`, `_unescape_shapes`, `_check_record_bindings`, `_preds_for`,
`extract_record`, `_record_kwargs`, `markers.RECORD_CAP`, `M.record`,
`M.record_pair`, `MatchSpec.record`, `MatchSpec.record_pair`,
`FieldBinding.source == "record_key"`.

### Phase 6 — Product B duplication
`rules._RuleMeta`, `rules._child`, `rules._from_annotations`, `rules._wrap`,
`rules._resolve`, `rules._snake`, `rules._rule_site`, `rules._attr_sites`,
`rules._RULES_FILE`, `rules._stamp` (folded into `NodeMeta`),
`pydantree_sitter_grammar.language` (if `Grammar.load_bundle` covers it).

### Phase 7 — `spec.py` (498) and `markers.py` (229)
`OutputModel`, `DerivingMeta`, `derive_spec`, `MatchSpec`, `FieldBinding`,
`PathStep`, `binding_warnings`, `_field_is_query_optional`, `_kind_override`,
`_predicate_markers`, `_resolve_annotation`, `_try_resolve_forward_ref`,
`_field_binding`; `M`, `GAP`, `ANCHOR`, `capture`, `capture_kind`,
`source_meta`, `derived`, `_Capture`, `_CaptureKind`, `_SourceMeta`, `_Derived`,
`_MARKERS`, `_MISSING`.

### Files deleted outright
`src/pydantree_sitter/markers.py`, `spec.py`, `valuemap.py`, `codegen.py`,
`compiler.py`, `materialize.py`, `binding.py`.

### Tests deleted or merged
`test_valuemap_check.py`, `test_codegen.py`, `test_tsquery_port.py`,
`test_tsquery_schema.py`, `test_raw_query.py`, `test_checks_nullable.py`,
`test_phase6_fixes.py`. Every deletion needs its line in `DELETED_TESTS.md`
(7.5).

---

## Appendix B — Grep gates

All must return nothing. Run over `src tests docs examples .agents README.md CLAUDE.md`.

```console
$ grep -rn "OutputModel\|__match__\|\bM(\|capture(\|capture_kind\|source_meta\|derived("
$ grep -rn "ValueMap\|value_map\|propose_value_map\|JSON_VALUE_MAP\|Unescaped\|looks_like_json"
$ grep -rn "record=True\|record_pair\|record_kind\|pair_kind\|RECORD_CAP\|extract_record"
$ grep -rn "TypedNode\|generate_typed_api\|write_typed_api"
$ grep -rn "Extractor\|compile_spec\|_Compiled\|build_kwargs\|extract_field\|emitted_source"
$ grep -rn "AmbiguousCaptureError\|TreeLanguageError\|schema-less\|wildcard"
$ grep -rn "_RuleMeta\|_from_annotations\|def _child"
$ grep -rn "Language\.load\|Language\.from_module\|lang\.extractor"
```

Two allowances, and only two:

1. `.scratch/` is the historical record. Exclude it: `--exclude-dir=.scratch`.
2. `pydantree_sitter.pattern` and `agreement.py` legitimately mention
   `Language` in the ast-grep sense. Check those hits by eye; there should be
   fewer than ten and all inside those two modules.

---

## Appendix C — Migration table

The record users get instead of a deprecation shim (D16).

| Before | After |
|---|---|
| `class X(OutputModel)` | `class X(py.SomeKind)` |
| `__match__ = M("a", "b")` | base class is `py.B`; `__under__ = (py.A,)` |
| `__match__ = M("a", ..., "b")` | `__under__ = (py.A, ...)` |
| `M(("if_stmt", "while_stmt"), ...)` | `__under__ = (py.IfStmt \| py.WhileStmt, ...)` |
| `name: str = capture("left")` | `left: str` — the attribute name **is** the field |
| `x: str = capture("left")` (rename) | `left: str` plus a pydantic alias, or read `.left` |
| `code: str = capture_kind("code_span")` | `code: py.CodeSpan` |
| `line: int = source_meta()` | `row.span.line` |
| `x: int = derived(3)` | a plain pydantic field with a default |
| `Annotated[str, NodeKind("integer")]` | `x: py.Integer` |
| `Annotated[str, Matches(r"^A")]` | unchanged |
| `Annotated[str, Unescaped()]` | the node class's `__value__` |
| `M(..., record=True)` | `entries: dict[str, V]` |
| `M(..., record=True, record_pair="p")` | `entries: list[Pair]` with an explicit `class Pair(py.P)` |
| `Language.from_module(m)` | `Grammar.load(m, schema=...)` — schema now required |
| `Language.load_bundle(d)` | `Grammar.load_bundle(d)` |
| `lang.extractor(X).extract(t)` | `g.parse(t).find(X)` |
| `X.extract(t, language=lang)` | `g.parse(t).find(X)` |
| `X.compiled_source(language=lang)` | `g.query_source(X)` |
| `X.validate_with(lang)` | nothing — checks run at class creation |
| `propose_value_map(schema)` | `python -m pydantree_sitter.generate --suggest-codecs` |
| `__raw_query__ = RawQuery(...)` | unchanged |

---

## Appendix D — Traceability

| Idea | Decisions | Phases | Primary deletion |
|---|---|---|---|
| 1 — node types are the core | D1, D2, D5, D6, D14 | 1, 2, 4 | `binding.py`, `compiler.py`'s check jobs, the wildcard path |
| 2 — one node class | D3, D11, D12 | 1, 4, 6 | `spec.py`, `markers.py`, `rules._child` |
| 3 — no record mode | D9, D10 | 4.5, 5 | `_compile_record` + 11 helpers, `extract_record` |
| 4 — codecs on the class | D7, D8 | 3 | `valuemap.py` |
| 9 (forced) — no schema-less mode | D5 | 4 | every `if schema is None` branch, 47 warnings |

---

## Appendix E — Deferred ideas

Recorded so the next project does not re-derive them.

| Idea | Why deferred | What it would delete next |
|---|---|---|
| 5 — `Language` disappears behind a namespace | **Partly done.** D3 and 4.1 collapse `Language` + `Extractor` into `Grammar`. The remaining step is making the generated module itself the entry point (`py.parse(...)` with no `Grammar` in sight). | `grammar.py`'s public surface, one more name from `__all__` |
| 6 — drop ast-grep | Large and independent. It touches no code this project changes. | `pattern.py` (955), `agreement.py` (312), `rules.py` (308), `syntax.py` (83), the `pattern` extra, `UnsupportedLanguageError` |
| 7 — rewrite belongs to the tree | Depends on idea 6 landing first. | `Edit`, `ReplaceResult`, the overlap checker, the `SyntaxCheck` proxy |
| 8 — structural error taxonomy | Cheap, but it churns every test that asserts an exception type. Do it after the taxonomy stops moving. | 5 of the remaining 8 exception classes |
| 10 — walk the tree, delete the emitter | The single largest remaining deletion. Blocked on a measurement: is a cursor walk fast enough against a compiled multi-pattern query on a large corpus? Benchmark before committing. | `emit.py` (all of it), `find.py`'s query half, `QueryBuildError`, `__raw_query__`, and "capture" as a concept |
| 11 — one word per idea | Phase 6 removes the worst collision (`Rule` meaning two things). `Grammar` still means two (builder and IR container); `pattern` still means three. | the disambiguation paragraphs in four module docstrings |
| 12 — provenance without frames | Phase 6.4 keeps `caller_site`. Once `__body__` is the only combinator path left, class `__qualname__` replaces frame walking. | `builder.caller_site`, `linecache` use, the frame-depth tests |

---

## Appendix F — Risk register

| Risk | Phase | Mitigation |
|---|---|---|
| Phase 4 silently changes extracted rows | 4 | The Phase-0 oracle JSON is frozen. A change to those files in the Phase-4 diff is a review stop. |
| Vendored schema drifts from the wheel | ongoing | D6 fingerprint check, raising `SchemaDriftError`. |
| D5 breaks the toolchain-free promise | 8.5 | Vendoring a JSON file needs no toolchain. Verify by running `examples/wheel-extract/` in a venv with no CLI and no gcc. |
| D12 fails — the two directions are not one declaration | 6.5 | **Stop.** Do not run Phase 7. Either the annotation grammar needs a direction flag, or D11 is wrong. Record which in `FINDINGS.md`. |
| Nested models (D10) are slower than record mode was | 5 | Benchmark `test_corpus.py` before and after. Record both numbers in `FINDINGS.md`. A regression above 2x is a design problem, not a tuning problem. |
| The surface regrows during Phases 5-8 | 7.2 | The `len(__all__) == 12` test. |
| A deleted test removes real coverage | 7.5 | `DELETED_TESTS.md`: one line per deletion naming the construction that makes the bug impossible. |
