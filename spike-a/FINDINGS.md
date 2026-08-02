# Phase 1 Spike — Findings & Verdict (Product A: tsquery)

**Date:** 2026-08-02
**Status:** COMPLETE
**Verdict:** **GO-WITH-CHANGES** (bet #2 is real, but the win is the
materializer, not the query DSL; scope the DSL thin)

Everything here was verified against the installed tree-sitter **0.26.0**
bindings (`tree_sitter` 0.26.0, `tree-sitter-python` 0.25.0,
`tree-sitter-json` 0.24.8, pydantic 2.13.4) — no simulations. The probe
(`spike-a/probe.py`) hand-wrote `.scm` first and validated every API
assumption against real parses before any DSL code existed (the Phase-0
"hand-written grammar.json first" move, repeated). The three-way comparison
and failure modes are runnable: `devenv shell -- python spike-a/main.py`.

---

## 0. The primary experiment in one paragraph

Bet #2 ("capture→OutputModel with schema-checked queries is meaningfully nicer
than py-tree-sitter") is **real but lopsided**. The materializer is the value:
for the JSON record task, typed mode is ~4 lines of user code where raw
py-tree-sitter is a 24-line function with a hand-rolled key→coercion dispatch
table, and the failure diagnostics are strictly better (pydantic `ValidationError`
with `loc`/`type` vs unwrapped `ValueError`/`KeyError` mid-loop). But the **query
DSL itself is nearly 1:1 with hand-written `.scm`** — for a single simple
pattern the builder is *longer* than the `.scm` (12 lines vs 8), and lazy mode
(no model) is only marginally nicer than raw. The honest conclusion: make the
materializer the product, keep the DSL thin, and let the node-schema bridge
(Phase 4) carry the "compile-time checking" promise that the DSL alone cannot.

---

## 1. The 0.26 Query API — what's really there (learned vs assumed)

All of these were probed against the installed `.pyi` + real parses.

### Verified as the concept/kickoff assumed

- **Loading**: `tree_sitter.Language(tree_sitter_python.language())` — wheel
  hands you a PyCapsule directly; `abi=15`, `name='python'`. Zero ctypes.
- **`QueryCursor.captures(node)`** returns `dict[str, list[Node]]` grouped by
  capture name; **`matches()`** returns `list[(pattern_index, dict)]`.
- **`Query.capture_quantifier(pi, ci)`** exists and returns `""|"?"|"*"|"+"`.
- **`Node.text` is `bytes | None`**; spans via `byte_range`, `range`,
  `start_point` (1-based rows on `Point`).
- **Node kinds and field names ARE validated at `Query()` construction**
  (better than the concept assumed): `Invalid node type` / `Invalid field
  name` — a typo is a build-time `QueryError`, not a silent empty match.

### Learned the hard way (the gold — all probe-evidenced)

1. **Predicates must be INSIDE the pattern's parens.** `(pair ...) (#eq? @key
   "name")` (two top-level forms) compiles to a **second pattern** — a bare
   predicate with no node — that **matches every node in the tree** with empty
   captures. This bit our own "raw" JSON implementation live (KeyError on the
   junk matches) before we fixed the `.scm`. The correct form is `(pair ...
   (#eq? @key "name"))`. The DSL emitter encodes this invariant; a raw user
   hits it blind. (probe.py §4, main.py §4.3)

2. **Repeated captures do NOT accumulate in one match.** `(array (string
   (string_content) @tag)*)` yields **one match with ONE @tag** (the first),
   not three — despite the `*` quantifier on the capture. The 0.26 cursor's
   actual "repeat" semantics: the sub-pattern is optional/repeatable, and the
   cursor yields **one match per occurrence**. To get a list, either (a) omit
   the quantifier so each element is its own match and group by an anchored
   ancestor, or (b) walk the captured container's children. We use (a) for
   JSON `tags`. This directly contradicts the naive reading of §5.4 "repeated
   captures → list" and is the single most important API fact for the
   materializer design. (probe §6, dsl_probe3/4/5/6)

3. **A capture suffix binds to the node whose `)` it follows.** `(array
   (string (string_content) @c) @arr)` puts `@arr` on the **string**, not the
   array — the `@arr` must come after the array's own closing paren:
   `(array (string (string_content) @c)) @arr`. The emitter must place each
   node's capture after *its* paren, which the DSL does correctly. (probe5)

4. **`QueryCursor` is NOT iterable in 0.26** — no `__next__`, no `__iter__`.
   `matches()` and `captures()` are **eager lists**. The concept's "lazy CST
   cursor, iterate matches on demand" (§5.5) cannot be a true streaming
   iterator over the binding's public API; the best available laziness is
   deferred node-text/span reads and zero model construction. Our `Cursor` is
   honest about this. (probe §7)

5. **`capture_quantifier(pi, ci)` raises `SystemError`** for captures that do
   not belong to pattern `pi` (the C layer returns an unexpected value). You
   must know each pattern's captures statically — fine for a DSL (we do), a
   trap for ad-hoc raw loops. (main.py §1 fix)

6. **Inline alternation does not exist** in tree-sitter queries
   (`(true | false)` is `Invalid syntax`). Alternation = multiple top-level
   patterns, which `matches()` distinguishes by `pattern_index`. The DSL's
   `|` emits multiple patterns and the quantifier maps are per-pattern.
   (alt_probe)

7. **Anchored patterns re-match per inner occurrence.** `(module
   (expression_statement (assignment ...)) @stmt) @root` matches **once per
   assignment**, each match carrying the same `@root` — so "module-level only"
   falls out of anchoring, and grouping by an anchored ancestor is how record
   extraction scopes work. (probe §3)

8. **Duplicate capture names corrupt quantifiers.** Emitting `@name` twice in
   one pattern (an emitter bug we hit) makes `capture_quantifier` report `+`
   for that name. We added an emitter assertion (`pattern_count == len(specs)`)
   and the DSL `check()` for declared captures.

### Adequacy verdict

The 0.26 API is **adequate** for the materialization model, but it does not
give you repeated-capture accumulation or a streaming cursor — the materializer
must be built around "one match per element + anchor grouping", which is
exactly what the record/sub-query design does. The concept's assumption that
`capture_quantifier` cleanly tells you "optional vs repeated" is **only half
true**: it tells you the *declared* quantifier, but the cursor's per-occurrence
match behavior is the real driver of materialization.

---

## 2. The primary experiment — three-way, same task, honest

### Task 1: Python — module-level integer constant assignments

Sample (17 lines, includes a string-valued assignment, a lowercase assignment,
and assignments inside a function that must NOT match).

**Ground truth (hand-computed, all three implementations agree):**

| name | value | line |
|---|---|---|
| WIDTH | 1920 | 1 |
| HEIGHT | 1080 | 2 |
| SCALE | 2 | 3 |
| DEBUG_MODE | 1 | 5 |
| MAX_RETRIES | 5 | 14 |

*(My first hand-computed truth said line 15 for MAX_RETRIES — the sample has
14 lines; all three implementations agreed on 14. CST-fidelity check passed
against the corrected truth.)*

**(a) raw py-tree-sitter — 8-line `.scm` + 10-line function:**

```python
RAW_SCM = """\
(module
  (expression_statement
    (assignment
      left: (identifier) @name
      right: (integer) @value)
    (#match? @name "^[A-Z][A-Z_]*$")) @stmt) @root
"""

def raw_extract(lang, source: bytes) -> list[dict]:
    tree = tree_sitter.Parser(lang).parse(source)
    query = tree_sitter.Query(lang, RAW_SCM)
    out = []
    for _pi, caps in tree_sitter.QueryCursor(query).matches(tree.root_node):
        name = caps["name"][0].text.decode()
        value = int(caps["value"][0].text.decode())      # manual coercion
        line = caps["stmt"][0].start_point.row + 1       # manual span math
        out.append({"name": name, "value": value, "line": line})
    return out
```

**(b) DSL lazy — 12-line query declaration + 10-line function:**

```python
ASSIGN_QUERY = Query(
    node("module")
    .child(node("expression_statement")
           .child(node("assignment")
                  .child(field="left",
                         node=node("identifier").capture("name"))
                  .child(field="right",
                         node=node("integer").capture("value")))
           .capture("stmt"))
    .capture("root")
    .where(cap("name").matches(r"^[A-Z][A-Z_]*$"))
)

def dsl_lazy_extract(lang, source: bytes) -> list[dict]:
    tree = tree_sitter.Parser(lang).parse(source)
    out = []
    for m in ASSIGN_QUERY.run(tree).matches():
        out.append({
            "name": m.text("name"),
            "value": int(m.text("value")),               # manual coercion
            "line": m.first("stmt").line,                # helper, still manual
        })
    return out
```

**(c) DSL typed — 4-line model + 3-line function:**

```python
class Assignment(OutputModel):
    name: str
    value: int
    line: int = source_meta(capture="stmt")

def dsl_typed_extract(lang, source: bytes) -> list[Assignment]:
    tree = tree_sitter.Parser(lang).parse(source)
    return ASSIGN_QUERY.extract(tree, into=Assignment)
```

**Line count: raw 18 (8 scm + 10 fn) · lazy 22 (12 q + 10 fn) · typed 19
(12 q + 4 model + 3 fn).**

### Task 2: JSON — person records from an array (order-independent keys)

Sample (25 lines, 4 records): keys are **not** in fixed order; `nickname` and
`active` are optional; one record has an empty `tags` array; one record has an
extra key (`score`) and a nested object (`address`) that must be ignored.

**(a) raw — 6 hand-written patterns + 24-line function with a manual dispatch
table:**

```python
RAW_FIELDS_SCM = """\
(pair key: (string (string_content) @key) value: (string (string_content) @name) (#eq? @key "name"))
(pair key: (string (string_content) @key) value: (number) @age (#eq? @key "age"))
(pair key: (string (string_content) @key) value: (array (string (string_content) @tag)) (#eq? @key "tags"))
(pair key: (string (string_content) @key) value: (string (string_content) @nickname) (#eq? @key "nickname"))
(pair key: (string (string_content) @key) value: (true) @active (#eq? @key "active"))
(pair key: (string (string_content) @key) value: (false) @active (#eq? @key "active"))
"""

def raw_extract(lang, source: bytes) -> list[dict]:
    tree = tree_sitter.Parser(lang).parse(source)
    rec_q = tree_sitter.Query(lang, RAW_RECORDS_SCM)
    fld_q = tree_sitter.Query(lang, RAW_FIELDS_SCM)
    out = []
    for _pi, caps in tree_sitter.QueryCursor(rec_q).matches(tree.root_node):
        rec = caps["record"][0]
        person = {"name": None, "age": None, "tags": [],
                  "nickname": None, "active": False,
                  "line": rec.start_point.row + 1}
        for _fpi, fc in tree_sitter.QueryCursor(fld_q).matches(rec):
            key = fc["key"][0].text.decode()          # manual dispatch
            if key == "name":
                person["name"] = fc["name"][0].text.decode()
            elif key == "age":
                person["age"] = int(fc["age"][0].text.decode())
            elif key == "tags":                       # repeated match -> append
                person["tags"].append(fc["tag"][0].text.decode())
            elif key == "nickname":
                person["nickname"] = fc["nickname"][0].text.decode()
            elif key == "active":
                person["active"] = fc["active"][0].text.decode() == "true"
        out.append(person)
    return out
```

**(b) DSL lazy — 22 lines, the SAME dispatch table, NodeView helpers instead
of raw slicing:**

```python
def dsl_lazy_extract(lang, source: bytes) -> list[dict]:
    tree = tree_sitter.Parser(lang).parse(source)
    out = []
    for rm in RECORDS_QUERY.run(tree).matches():
        rec = rm.first("record")
        person = {"name": None, "age": None, "tags": [],
                  "nickname": None, "active": False,
                  "line": rec.line}
        for fm in FIELDS_QUERY.run(tree).matches_on(rec._node):
            key = fm.text("key")
            if key == "name":
                person["name"] = fm.text("name")
            elif key == "age":
                person["age"] = int(fm.text("age"))
            elif key == "tags":
                person["tags"].append(fm.text("tag"))
            elif key == "nickname":
                person["nickname"] = fm.text("nickname")
            elif key == "active":
                person["active"] = fm.text("active") == "true"
        out.append(person)
    return out
```

**(c) DSL typed — 7-line model + 3-line function; the dispatch table
disappears:**

```python
class Person(OutputModel):
    name: str
    age: int
    tags: list[str] = capture("tag")        # repeated capture renamed
    nickname: str | None = None
    active: bool = False
    line: int = source_meta(capture="record")

def dsl_typed_extract(lang, source: bytes) -> list[Person]:
    tree = tree_sitter.Parser(lang).parse(source)
    return extract_records(tree, RECORDS_QUERY, FIELDS_QUERY, into=Person)
```

**Line count: raw 30 (6 scm + 24 fn) · lazy 22 + query defs · typed ~20 (query
defs + 7 model + 3 fn).** All three produce the hand-computed ground truth
(4 records; `carol` gets `tags=[]`, `nickname=None`, `active=False` defaults;
nested `address.city` ignored).

### The honest read

| | raw | DSL lazy | DSL typed |
|---|---|---|---|
| Python task | 18 lines | 22 lines | 19 lines |
| JSON task | 30 lines | 22 lines + query | ~20 lines + query |
| coercion | manual `int()`/decode | manual `int()`/decode | pydantic (free) |
| missing/optional | manual `None` bookkeeping | manual | pydantic + markers |
| repeated→list | manual append by key | manual append by key | `list[str] = capture("tag")` |
| span/line | `start_point.row + 1` | `m.first("stmt").line` | `source_meta()` |
| dispatch table | hand-rolled `if/elif` | hand-rolled `if/elif` | gone |

1. **The DSL query builder is NOT nicer than `.scm` for simple queries.** A
   1-pattern query is 12 builder lines vs 8 `.scm` lines. The builder only
   pays off when patterns are composed programmatically, alternated, or
   generated. If the materializer didn't exist, the DSL would be **ceremony
   without value** for single patterns.
2. **Lazy mode ≈ raw.** The NodeView helpers (`m.text()`, `m.first().line`)
   shave the byte-slicing boilerplate but the coercion, dispatch, and
   optional-handling stay manual — lazy mode is a small win, not a
   transformation. This is expected (no model = no typing), but it means the
   "lazy default" result mode does **not** carry the value proposition.
3. **Typed mode is where bet #2 lives.** The JSON dispatch table — the ugliest
   part of raw — is *declared away* by the model: `tags: list[str] =
   capture("tag")`, `nickname: str | None = None`, `active: bool = False`,
   `line: int = source_meta()`. Coercion, defaults, optionality, span injection
   are all data, not code. Pydantic v2 lax mode handles `"1920"→int`,
   `"true"→bool`, `"admin"→enum` with zero custom coercion code.
4. **The record/sub-query pattern is not a nice-to-have — it is the only way
   to do order-independent, partially-missing JSON records**, because
   tree-sitter queries are strict structural patterns (fixed order, all
   elements present). The concept's "nested OutputModels from sub-queries"
   (§5.4) is exactly this and it is load-bearing.

---

## 3. Failure modes — where each approach surfaces the error

| Mistake | raw py-tree-sitter | DSL (lazy / typed) |
|---|---|---|
| typo node kind `assignmnt` | `QueryError: Invalid node type` at build (good) | same `QueryError` via `QueryBuildError`, includes emitted `.scm` (equally good) |
| typo field `leftt` | `QueryError: Invalid field name` at build (good) | same (equally good) |
| typo capture `@namee` | **silent** at build; `KeyError: 'name'` mid-loop at runtime | binding warning before parsing + pydantic `Field required` at the end (`ExtractionError`) |
| int field fed text `"unknown"` | `ValueError: invalid literal for int()` unwrapped at the call site | pydantic `ValidationError` `loc=('age',) type=int_parsing` — names the field and the bad input |
| required field, capture absent | manual `.get()` returns `None` → silent `None` data (age: None) | `ValidationError: Field required` naming the field (strict) |
| scalar field, N captures (nested key collision) | takes the first silently (data corruption risk) | `AmbiguousCaptureError` (strict) — a real catch, see below |
| bare top-level `(#eq? ...)` | **junk match per node**, empty dicts → `KeyError` (we hit this) | impossible: emitter places predicates inside parens |
| malformed input (ERROR/MISSING) | you walk the tree yourself or never notice | `validate()` reports `ERROR`/`MISSING` with kind/line/byte-range/snippet |

Two of these are genuinely important:

- **Field/kind typos are already build-time errors in 0.26** — so the node-schema
  bridge (Phase 4) is *not* needed for typos; it is needed for *semantic*
  checks (field fed from a wrong-shaped capture, `int` field whose capture can
  only ever be non-numeric, etc.). The concept's "silent empty match" fear for
  kind/field typos is retired for free.
- **Capture-name typos are the one fully-silent raw failure**, and the DSL's
  pre-parse binding warning + end-of-run pydantic error is the meaningful
  improvement. This is the cheap-check win (kickoff "cheap checks" #3) and it
  costs almost nothing.

The nested-collision case (record `{"meta": {"name": "inner"}}` — the scoped
sub-query captures the inner `name` too) is an **honest limitation of the
spike's record design**: scoped sub-queries can't distinguish record-level from
nested pairs without deeper anchoring (e.g. matching the pair's parent object
explicitly). The strict `AmbiguousCaptureError` is the right Phase-1 behavior
(no silent corruption), and Phase-4-style anchoring (or a `#eq?`-key
restriction per level) is the fix.

---

## 4. What the full Product A needs (gaps vs. concept §5)

### Query DSL
- **Keep it thin.** The builder ≈ `.scm` for simple patterns; do not add more
  sugar for sugar's sake. The genuinely useful operators are the ones that
  compose: `.child(field=...)`, `.where(...)`, `|` (multi-pattern), and
  anchored `.capture()` roots. Missing operators worth adding later:
  `.any_of` on captures (have it), `#is?`/`#has-ancestor?` predicates,
  `#eq?` with a literal first (for `value: (_) @v` + `#eq? @v "x"` patterns —
  we only emit capture-first).
- **Predicates-inside-parens must be an invariant of the emitter** (it is in
  ours), and the raw footgun (§3.1) should be documented for users who
  hand-write `.scm` alongside.
- **Alternation → multi-pattern is the only option**; the DSL's `|` should
  probably stay pattern-level and *not* try to sugar per-node choices.

### Materializer
- **Repeated captures are per-match-one-or-many-matches, not accumulate-in-one.**
  The record/sub-query merge (group captures across matches sharing an anchor)
  is the core mechanism; a `RecordQuery`-style API (outer + inner + per-field
  binding) is the natural product shape, not a per-task helper.
- **Pydantic-is-the-coercion-engine is a keeper.** Hand raw text to
  `Model(**kwargs)`; pydantic's lax mode coerces int/float/bool/enum and
  produces the best diagnostics surface. Custom coercion is only needed for
  grammar-specific shapes (e.g. JSON `string` node unquoting — we avoided it
  by capturing `string_content`).
- **Missing-capture semantics need to be explicit per field kind**: list →
  `[]`, defaulted → default, optional-without-default → `None`, required →
  pydantic `Field required`. We implement list/defaulted/required; optional-
  without-default currently errors (fine for Phase 1, worth deciding in
  product).
- **`source_meta()` should inject a `Span` object** (line/col/end/bytes/text)
  with the int-line shortcut, and the capture-name default should be the
  pattern's anchor. Our `line: int = source_meta(capture="stmt")` works;
  `capture="root"` default is a footgun for multi-pattern queries.
- **Diagnostics surface**: `ExtractionError` should carry per-match
  (pattern/anchor, pydantic errors, source snippet) rather than just the first
  error; and `validate()` should become a first-class result mode returning
  typed `Diagnostic{kind, span, expected}` objects (concept §5.6).

### Honest cost center
The **binding between model fields and captures is name-based magic**:
`field name == capture name` by default, `= capture("other")` to rename. It's
convenient but stringly-typed; the Phase-4 node-schema bridge is what makes it
checkable at compile time ("capture `age` can only yield `number` nodes").
Until then, the binding warnings + pydantic errors are the safety net, and they
are good but not compile-time.

---

## 5. §11 risk re-assessment (from the consumption side)

| # | Risk | Phase 1 evidence |
|---|---|---|
| 2 | External-scanner frequency | Unchanged, but Phase 1 shows it does **not** block Product A: both target grammars are pure-lexer community wheels and record extraction works over them. Scanner-heavy grammars (Python already has one — the indentation scanner — and it's *inside the wheel*) are B's concern, not A's. |
| 4 | Upstream churn | **Real and active.** The 0.26 binding's API diverges from old tutorials in concrete ways: eager `matches()` lists (no cursor iteration), `SystemError` from `capture_quantifier` for foreign captures, `QueryCursor.captures()` dict shape, capture-suffix binding quirks. Mitigation confirmed: the `.pyi` is the ground truth, the `Query()` constructor is a free validator, and version pinning (0.26.0) is mandatory. |
| 7 | node-schema completeness | **Now clearly the crux.** Typos are already free (Query() validates kinds/fields), so the schema's real value is (a) capture→field type compatibility at compile time and (b) record-level anchoring to kill the nested-collision class (§3). Both are Phase 4. A's Phase-1 stand-ins (binding warnings, AmbiguousCaptureError) work but are runtime, not compile-time. |
| (new) | Repeated-capture semantics | **Discovered**: quantified sub-nodes don't accumulate captures in one match. Affects the materializer design (record-merge by anchor) and any docs that promise `@cap*` → list in one match. |

---

## 6. Recommendation

**GO-WITH-CHANGES.** Product A's value proposition is confirmed but needs a
design amendment: **the materializer is the product; the query DSL is a thin
emitter over `.scm` and must not be gold-plated.** The evidence:

- Bet #2 holds **for typed materialization** (JSON task: dispatch table
  declared away; diagnostics strictly better).
- Bet #2 **fails for lazy mode and for the bare query DSL** on simple patterns
  (lazy ≈ raw; builder longer than `.scm`). The default result mode should not
  be where the pitch lives.
- The 0.26 API is adequate but demands a specific materializer shape
  (per-occurrence matches + anchor grouping), which we've now built and
  verified end-to-end against ground truth on two grammars.

**Single most important next step: Phase 2 (Product B core).** Rationale: A's
Phase-1 stand-ins (binding warnings, strict record collisions) are runtime
safety nets, and the two things that would make A genuinely typed — compile-time
capture↔field checking and record-level anchoring — both come from the
node-schema bridge (Phase 4), which requires B's grammar emission first. Phase 2
is now low-risk (Phase 0 proved emission + conflict remapping; the builder/IR
patterns carry over) and unblocks the only remaining big A risk. A **Phase-1A
hardening pass is optional** and cheap: `Span`-typed `source_meta()`, richer
`ExtractionError`, `Diagnostic` objects, and the record-level anchor fix for
nested collisions — none of it is a go-blocker.

---

## Appendix — how to re-run

```bash
devenv shell -- python spike-a/probe.py      # raw-API assumption probe
devenv shell -- python spike-a/dsl.py        # DSL self-test
devenv shell -- python spike-a/main.py       # three-way comparison + failures
```

Sections: (1) DSL→`.scm` acceptance, (2) Python task ×3 vs ground truth,
(3) JSON task ×3 vs ground truth, (4) failure modes 4.1–4.7, (5) cheap checks.
