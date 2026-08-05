# Spike-a2 — Findings & Verdict (model-only extraction)

**Date:** 2026-08-02
**Status:** COMPLETE
**Verdict:** **The "model IS the query" surface is real and should be the
product.** Both target tasks express as a pure Pydantic model (no `.scm`, no
query builder, no query string), derive and validate at class creation, and
match hand-computed ground truth. The remaining expressibility gaps are
small, mostly grammar-knowledge-shaped, and the node-schema bridge (Phase 4)
is the natural place to close them.

Everything here ran against the installed tree-sitter 0.26.0 / pydantic 2.13.4
(same toolchain as spike-a). Re-run: `devenv shell -- python spike-a2/main.py`.
The emitter + materializer from spike-a are imported and reused as-is; the new
layer is `spike-a2/typed.py` (derivation + metaclass + model-only surface).

---

## 0. What the user writes (the whole API)

**Field mode** (structured nodes):

```python
class Assignment(OutputModel):
    """Module-level integer constant assignments."""
    __match__ = M("module", "expression_statement", "assignment")

    name: Annotated[str, Matches(r"^[A-Z][A-Z_]*$")] = capture("left")
    value: Annotated[int, NodeKind("integer")] = capture("right")
    line: int = source_meta()

rows = Assignment.extract(text, language=tree_sitter_python)
```

**Record mode** (order-independent key/value documents):

```python
class Person(OutputModel):
    """Person records from a JSON array; keys order-independent/optional."""
    __match__ = M("document", "array", "object", record=True)

    name: str
    age: int
    tags: list[str]
    nickname: str | None = None
    active: bool = False
    line: int = source_meta()

people = Person.extract(text, language=tree_sitter_json)
```

That is the entire user surface. The `.scm` the machinery derives (the user
never writes or sees it):

```
(module (expression_statement (assignment left:(_) @name right:(integer) @value
        (#match? @name "^[A-Z][A-Z_]*$")) @__anchor__))

(document (array (object) @record))
(pair key:(string (string_content) @key) value:(string (string_content) @name)  (#eq? @key "name"))
(pair key:(string (string_content) @key) value:(number) @age                  (#eq? @key "age"))
(pair key:(string (string_content) @key) value:(array (string (string_content) @tags)) (#eq? @key "tags"))
(pair key:(string (string_content) @key) value:(string (string_content) @nickname)     (#eq? @key "nickname"))
(pair key:(string (string_content) @key) value:(true) @active                 (#eq? @key "active"))
(pair key:(string (string_content) @key) value:(false) @active                (#eq? @key "active"))
```

Both tasks PASS against hand-computed ground truth (5 and 4 rows, including
`carol`'s empty `tags`, missing `nickname`, default `active=False`, ignored
`score`/`address.city`, and the module-level/nested/Python filtering).

---

## 1. The binding rules (what "used automatically" means)

| Model element | Derived meaning |
|---|---|
| attr name | capture name (field mode) / JSON key (record mode) |
| pydantic type | coercion (`"1920"→int`, `"true"→bool`, `"alice"→str`) |
| `Optional[T]` | capture may be absent |
| `= None` / `= False` / any default | fallback when the capture is absent |
| `list[X]` | repeated capture → list (missing → `[]`) |
| `= source_meta()` | span injection (int → start line, `Span` → full span) from the match anchor |
| `= capture("field")` | the CST field position (field mode); no-arg = attr name is the field |
| `Annotated[..., Matches(re)]` | `#match?` predicate |
| `Annotated[..., Eq(v)]` | `#eq?` predicate |
| `Annotated[..., AnyOf(a,b)]` | `#any-of?` predicate |
| `Annotated[..., NodeKind("integer")]` | constrain the matched node kind (tuple = alternation → one pattern per kind) |
| field typed as another `OutputModel` | nested extraction: value node materialized by the nested model |
| `__match__ = M("a", "b", "c")` | the ONE structural declaration: anchored ancestor path |

Verified mechanically (main.py §3 battery): no-arg capture, Eq, AnyOf,
NodeKind alternation, lenient mode, derived constant fields, clear
`UnsupportedShapeError` at class creation, nested models.

---

## 2. Findings that matter

### 2.1 The record VALUE shape map is grammar knowledge — the central design fact

Record mode derives each field's inner pattern from its type, but "a JSON
`str` is a `string` node wrapping `string_content`" is JSON-grammar knowledge,
not logic. The spike hardcodes a JSON v1 map (`str → string_content`, `int`/
`float → number`, `bool → true|false`, `list[str] → array of string_content`)
with `NodeKind` as the typed override and a clear error for unmapped shapes
(`list[bool]`). **This is the honest core of the "only way" claim**: the type
tells you the coercion and the repetition; it does not tell you the grammar's
node shapes. The node-schema bridge (Phase 4) is what would turn the hardcoded
map into a derived one. Until then, a shape map per grammar (or per field,
via `NodeKind`) is the escape hatch — and it's typed, not `.scm`.

### 2.2 Types coerce, they don't filter — NodeKind is needed for match precision

`value: int` with a wildcard capture matches *any* RHS; `TITLE = "My Window"`
and `RATIO = 16 / 9` would match and then fail `int` coercion in strict mode
(or be silently skipped in lenient). The `#match?`/`#eq?` predicates filter on
*text*; node-kind filters (`right: (integer)`) are a *match-level* constraint
that a Python type cannot express — pydantic has no opinion about node kinds.
`NodeKind` exists exactly for this and is required for the Python task's
ground truth. **Question this surfaces for the product**: should `int`-typed
captures default to numeric kinds? That is grammar-specific — the schema
bridge's answer.

### 2.3 Record-mode predicates filter records, field-mode predicates filter matches

In field mode the query engine drops non-matching matches (predicate on the
pattern). In record mode the predicate lives on the *inner* query, so a
failing record simply lacks the capture — the first implementation treated
that as a missing-required-field *error*. Fixed: a capture field with a
predicate that is absent filters the whole record (battery 3.2/3.3: `Eq`/
`AnyOf` on `name` return exactly the matching records). Semantics to keep and
document.

### 2.4 Class-creation derivation + validation works (import-time errors)

A `ModelMetaclass` override derives the query and computes binding warnings at
class creation (`model_fields` is available there; it is NOT in
`__init_subclass__`). Structure errors (`UnsupportedShapeError`, unresolved
annotations) fail at import. Grammar errors (typo'd node kind or field name in
`__match__`/`capture()`) need the grammar, so they surface as `QueryBuildError`
at `validate_with(language)` — callable at startup — or at first `extract`,
with the emitted `.scm` in the message. Binding warnings (required field with
no capture and no default) are computed at import, printed at first extract,
before any parsing.

### 2.5 Pydantic-annotation gotchas (real, user-facing)

- `Annotated` metadata must be resolvable in the *defining module's globals*.
  A model class defined inside a function only works when every name in its
  annotations is module-global; a function-local class referenced by another
  model (`address: Address | None`) leaves a `ForwardRef`. The derivation now
  detects this and raises a clear error instead of a confusing one. This is
  standard pydantic behavior — model definitions belong at module level.
- `str | None` (PEP 604) and `Optional[str]` both need unwrapping
  (`types.UnionType` vs `typing.Union`).
- `capture()` no-arg is a *default marker*: fields without any marker and
  with a plain default are derived fields (never populated from the tree).

### 2.6 The spike-a machinery carried over unchanged

The emitter invariants from spike-a (predicates inside pattern parens, capture
suffix after the owning node's paren, multi-pattern alternation, per-pattern
quantifier maps with the `SystemError` guard) and the materializer semantics
(missing → `[]`/default/required-error, scalar-with-N-captures →
`AmbiguousCaptureError`, pydantic-as-coercion) were reused as-is. The
model-only layer is a thin derivation on top; nothing had to change.

---

## 3. Failure modes — where each mistake surfaces

| Mistake | Where it surfaces | Kind |
|---|---|---|
| typo node kind in `__match__` | `validate_with()` or first `extract` | `QueryBuildError` (Query() rejects) |
| typo CST field in `capture("leftt")` | same | `QueryBuildError` |
| required field, no binding | import (warning) + extract | `ValidationError: Field required` |
| non-integer text into `int` field | extract | `ValidationError` with `loc`/`type` (strict) or row skipped (lenient) |
| nested key collision | extract | `AmbiguousCaptureError` |
| unmapped shape (`list[bool]`) | **class creation** | `UnsupportedShapeError` |
| annotation not resolvable | **class creation** | `CoercionError` with a fix hint |
| record predicate mismatch | extract | record filtered out (no error) |

No mistake is silent, and the two most structural classes (shape map,
annotation resolution) fail at import, before any text is parsed.

---

## 4. The "only way" audit — expressible vs gaps

**Expressible model-only (all verified):** field captures, record key/value
extraction, Optional, defaults, repeated→list, spans, bools, `#match?`/
`#eq?`/`#any-of?`, node-kind constraints, kind alternation, anchored ancestor
paths, nested models, lenient/strict modes.

**Gaps / escape hatches:**

1. **Node-kind match precision** — needs `NodeKind`; pydantic types coerce but
   don't filter. Could default int→numeric-kinds with the schema bridge.
2. **Field-mode lists** (repeated children into one match, e.g. function
   params) — not built; record mode's merge covers the common case; a
   field-mode list needs the same anchor-merge machinery.
3. **Non-JSON record shapes** — the value shape map is JSON-grammar knowledge;
   other grammars need their own map or per-field `NodeKind` overrides. The
   Phase-4 node-schema bridge would derive it.
4. **Descendant matching** — `M()` is an exact ancestor chain; no "anywhere
   under module" wildcard. A `...` path element would add it.
5. **JSON string unescaping** — `string_content` is captured raw; embedded
   escapes are not unescaped (concept §5.4 promised unescaping).
6. **Nested model limits** — nested models must be record-mode; the nested
   `M()` path is ignored when nested; a predicate-filtered nested record
   materializes as missing.

None of the gaps is a `.scm`-shaped hole; all are typed-annotation or
grammar-knowledge shaped, which is exactly where the Phase-4 bridge plugs in.

---

## 5. Verdict and what it changes

**The model-only surface is the product.** It answers the user's requirement —
queries written *only* as the typed model — for the full shape of both target
tasks, with import-time derivation and validation, and it strictly dominates
both alternatives explored earlier:

- vs spike-a's builder DSL: no separate query object, no capture-name
  duplication, nothing to learn beyond Pydantic;
- vs raw `.scm` on the model: no `.scm` authored at all, and the field names,
  types, Optional/list/defaults, and spans all *participate* in the query
  instead of being re-declared alongside it.

The remaining design risk is the **record value-shape map** (§2.1): "the type
tells you the shape" is true only up to the grammar. Everything else holds.

**What this changes for the concept:**

- Product A's pitch becomes "declare a Pydantic model; get typed extraction" —
  no query DSL, no result modes to sell, no lazy-vs-typed distinction in the
  public surface. The materializer and the derivation ARE the product.
- The Phase-4 node-schema bridge changes from "compile-time query checking" to
  "derive the value-shape map and validate capture↔type compatibility" — a
  sharper, more concrete job.
- The spike-a findings stand (0.26 semantics, predicate placement, per-match
  repeats) as the substrate this layer sits on.

**Recommendation:** proceed to Product B (Phase 2) as planned — the bridge is
what generalizes the shape map — and treat this model-only layer as the Product
A shape to build on, not the builder DSL.

---

## Appendix — files & re-run

```
spike-a2/probe_pyd.py      # pydantic mechanics (markers, metadata, hooks)
spike-a2/probe_timing.py   # where model_fields is available (metaclass, not init_subclass)
spike-a2/typed.py          # the model-only layer (derivation, metaclass, extract)
spike-a2/tasks.py          # the two tasks, model-only, + ground truth
spike-a2/main.py           # tasks, derived-scm, expressibility battery, failures, audit
spike-a2/FINDINGS.md       # this file
```

Run: `devenv shell -- python spike-a2/main.py` (imports the spike-a emitter
and materializer via a sys.path shim).
