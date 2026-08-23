# Review 021 — deep adversarial review: concept, architecture, codebase

**Date:** 2026-08-19
**Scope:** the whole product — `pydantree_sitter` (A), `pydantree_sitter_grammar` (B),
the docs, the examples, the test suite, the packaging.
**Predecessors:** 014, 018, 019, 020. This review does not re-litigate their
findings; it attacks the parts they did not reach.
**Evidence:** `evidence/*.txt`, reproduced by `probes/*.py`.

---

## 0. Verdict

The idea is good and the discipline is real. The execution has **three
silent-wrong-answer defects on mainline surfaces**, and the headline claim —
"the schema bridge is the differentiator" — is **off in every documented
entry path and actively hostile in one of the two paths where it is on**.

| | |
|---|---|
| Baseline | `342 passed`, exit 0, ~78 s under `devenv shell` (`evidence/full-suite.txt`) |
| Coverage | 79–100 % per module, ~90 % overall |
| New defects found | **3 major** (silent wrong data / broken advertised feature / opaque failure), 5 moderate, ~12 minor |
| Vacuous regression tests found | 1 (the 020 A4 guard passes on the wrong error) |
| Concept-level problems | 3 (see §2) |

The single most important sentence in this review:

> **Two repeated fields on one anchor produce a cartesian product of
> duplicated list entries** — `12` items per field become `1728` per list —
> and nothing in the suite notices (§4, D-1).

The second most important:

> **Binding a node-schema — the product's differentiator — makes the
> documented `M(("a","b"))` alternation feature stop working.** It only works
> when the schema is absent (§4, D-2).

---

## 1. Method

1. Read all 26 source modules end to end, then the docs, examples, packaging
   and `conftest.py`.
2. Ran the full suite in `devenv shell` (342 green), plus `coverage`, `ruff`,
   `mypy`.
3. Wrote seven probe scripts that attack specific claims rather than specific
   lines (`probes/probe_[a-g]_*.py`). Every finding below marked **CONFIRMED**
   has a reproduction in `evidence/`.
4. Where a defect looked structural, I built the *fix* far enough to prove it
   works (§7.1) rather than only asserting it.

---

## 2. The concept — adversarial

### C-1 · "The model IS the query" — correct instinct, one conflation too many

The core bet is right, and it is what makes the library worth using: a
Pydantic class that is simultaneously the pattern and the output type removes
the `.scm` ↔ dataclass drift that every hand-rolled tree-sitter consumer has.

But the class is asked to be **four** things at once: the pattern, the output
type, the coercion policy, and — undocumented — **the sibling order of the
emitted query** (§4, D-3). Three of those are declarative. The fourth is an
accident of the emitter, and it makes a Pydantic model's field order
load-bearing in a way no Python programmer expects. Reordering two fields
turns a working extractor into

```
QueryBuildError: emitted .scm rejected by Query(): Impossible pattern at row 0, column 41
```

about a pattern the user never wrote. The docs say the opposite ("Sibling
order … out of scope").

The conflation also blocks two obvious use cases with no escape hatch short
of `__raw_query__`: one query producing two output shapes, and two queries
producing one output shape. Neither is exotic.

**Judgement:** keep the bet, break the fourth coupling. §7.1 shows a
three-line-of-concept emission change that removes it *and* fixes D-1.

### C-2 · "The bridge is the differentiator" — absent from every documented entry path

The README, the architecture doc, the user guide, and the *only*
toolchain-free example all demonstrate Product A like this:

```python
lang = Language.from_module(tree_sitter_rust)      # README:28
lang = Language.from_module(tree_sitter_python)    # user-guide:54, wheel-extract/extract.py:89
rows = RustFn.extract(rs_source, language=tree_sitter_rust)   # user-guide:522
```

Every one of those has `lang.schema is None` (`evidence/probe_a_core.txt`,
P1). With no schema, `compile_spec` skips `_check_path` **and**
`_check_field_bindings` entirely and emits wildcards. **Zero model↔grammar
checks, zero capture↔type checks.** The comment `# checks run here, once` in
`README.md:29` is, on that line, false.

This is not a doc bug; it is a structural consequence. Community wheels do
not ship `node-types.json` — I checked the installed `tree_sitter_python`
wheel: `__init__.py`, `_binding.abi3.so`, `queries/`, nothing else. To get a
schema you must run the tree-sitter CLI over a *grammar source checkout* —
i.e. install Product B, the heavy package the light package exists to avoid.

So the honest shape of the product today is:

- light install + community wheel → **an ergonomic query DSL with no checks**;
- light install + a bundle someone built with B → the checked product.

That is still a good product. But the marketing and the default path are
inverted, and a user who reads the README will never experience the
differentiator. **The gap to close is a schema-distribution story**, not more
checks: ship `node-schema.json` for the top ~20 community grammars as a data
package (`pydantree-schemas`), or make `Language.from_module` look for a
sibling `node-types.json` and *warn loudly* when it finds none.

Concrete fix with today's code: `examples/wheel-extract/` is the flagship
toolchain-free demo and it runs unchecked. Committing a
`node-schema.json` for python next to it (generated once, byte-verified in
CI) would make the flagship example demonstrate the flagship feature.

### C-3 · "Value shapes are declared data — never silent name-regex inference" is not true

README §"The honesty statements (014 §8.2)" C2 states this twice, and
`valuemap.py`'s docstring repeats it. The code does not honour it:

```python
# compiler.py:550
def _scalar_of(schema, vm, kind):
    if vm is not None and kind in vm.scalars:
        return vm.scalars[kind]
    return _proposed(schema).scalars.get(kind)   # <- the name regex
```

`_scalar_of` feeds `_kind_coerces`, which feeds **both** `_check_type` (every
capture↔type check) **and** `_infer_field_kind` (what kind the emitted query
constrains a capture to). With an empty, deliberately-committed `ValueMap`,
the draft heuristic still assigns a scalar meaning to **137 of the rust
schema's 278 kinds** (134 `str`, 2 `bool`, 1 `float` —
`evidence/probe_a_core.txt`, P8). The name regex is genuinely loose: any kind
whose name ends in `int` is numeric —

```
'constraint' -> int    'hint' -> int    'joint' -> int    'waypoint' -> int
```

— because `_NUMERIC_NAME` is `(number|numeric|integer|int|real|decimal|count)\b`
and `\b` matches at end-of-word. That is fine for a *draft the user reviews*.
It is not fine as the silent default of the check that the product is sold on.

The claim is true of *record-mode value-shape emission*, which really does
consume only `(schema, ValueMap)`. It is false of the check path and of
field-mode emission. Either the statement must be narrowed to record mode, or
`_scalar_of` must stop falling back — the honest middle ground is to fall back
but **record which kinds were inferred** and surface them as bind warnings
(`Extractor.warnings` already exists and is already the right channel).

### C-4 · The two-package split — right, but cut in the wrong place

Splitting "authoring (needs Rust + gcc)" from "consuming (needs neither)" is
correct and the install boundary is genuinely proven. Two things sit on the
wrong side of the line:

- **`codegen.py` lives in A** (the light runtime) but is only ever called by
  B's `write_bundle(typed_api=True)`. It is 218 lines of code generation
  shipped to every consumer who will never run it.
- **`propose_value_map` lives in A** but is an authoring-time drafting tool by
  its own docstring ("a proposal the user inspects and commits"). It is also
  — see C-3 — silently load-bearing at runtime, which is exactly the coupling
  the split was meant to prevent.

Meanwhile **three names** describe one thing: the repo is `pydantree`, the
root `pyproject.toml` declares a `pydantree` distribution that is never built
(`package = false`), the README title is `pydantree-sitter`, and the products
are `pydantree-sitter` / `pydantree-sitter-grammar`. The `[project]` block at
the root is pure ceremony — it declares a name, a version and a description
for a distribution that cannot exist. Delete it or make the root a real
distribution; a phantom `pydantree 0.2.0` in the workspace is a footgun for
anyone who types `pip install pydantree`.

### C-5 · Record mode is a second product hiding inside a keyword argument

`M(..., record=True)` does not tweak the pipeline; it *replaces* it:

- two queries instead of one (`records` + `fields`);
- an entirely different anchor (`RECORD_CAP`);
- a different materializer (`extract_record` / `_record_kwargs`);
- structural discovery that field mode has no analogue of
  (`_find_pair_kind`, `_key_shapes`);
- its own predicate semantics ("a required predicate field that does not
  match filters the WHOLE record");
- its own nesting rule (nested models work here and are a `ShapeError` in
  field mode).

And its structural assumptions are narrow and JSON-shaped: a child kind with
literally the field names `key` and `value`; key leaves preferred by the
*names* `string_content` / `content` / `text` (another name heuristic in the
trusted path, `compiler.py:707`); `_unescape_json_string` applied to any
grammar's `Unescaped()` field.

The architecture doc's "the ONE compiler" is therefore aspirational. There are
three pipelines (`_compile_field`, `_compile_record`, `_compile_raw`) and two
materializers, in one 838-line module with 34 module-private helpers. Record
mode is a *fine feature*; it should be a named, first-class thing —
`RecordModel` as a sibling base class, or a `pydantree_sitter.record`
submodule — not a boolean on a marker that silently swaps out half the
runtime. Today's shape means every field-mode reader must page past record
mode's `_key_shapes` / `_value_shapes` / `_find_pair_kind` to follow the code
they care about, and the two modes' bugs (D-6) hide in each other's shadow.

---

## 3. The architecture — adversarial

### A-1 · The emitter has no model of "unordered captures"

`_compile_field` builds **one** pattern containing every capture as a sibling
child, in `model_fields` order. Two independent consequences fall out:

1. tree-sitter validates sibling order against the grammar → **D-3** (field
   order is load-bearing, opaque error).
2. tree-sitter enumerates one match per *combination* of the optional/repeated
   children → **D-1** (cartesian list merge, exponential match count).

Both are the same root cause. The merge layer in `match.py` already exists and
already groups by anchor id — it was built for exactly this. It is simply not
being given one pattern per capture. §7.1 demonstrates the alternative
working.

### A-2 · The bind is advertised as a boundary but is not enforced as one

The README, architecture doc and `binding.py` docstring all make the same
claim: the compiled state lives on the `Language`, so "a silent cross-language
result is impossible by construction". It is not:

```python
ext = lang_a.extractor(Model)
ext.extract_tree(tree_from_lang_b)      # -> [Model(a=[])]     no error
```

(`evidence/probe_d_toolchain.txt`, D6.) `Extractor.extract_tree` never
compares `tree.language` with `self.language._lang`, and `Query.compile`
ignores its `lang` argument once `self._compiled` is set (`emit.py:206`). One
`if` fixes it; the claim should not be made until it is there.

### A-3 · Four cache strategies, three of them unbounded and one address-keyed

| cache | key | bound | leak |
|---|---|---|---|
| `Language._extractors` | `(model_cls, strict)` | none | holds model classes + compiled queries forever |
| `binding._LANGUAGE_CACHE` | weak, per input module | weak | fine |
| `compiler._PROPOSED_CACHE` | **`id(schema)`** + a strong ref to the schema | none | pins every `NodeSchema` ever checked, forever |
| `pipeline` content-addressed dir cache | sha256 | none | on disk, by design |

`_PROPOSED_CACHE` is the notable one: it keys on `id()` and then stores the
object to defend against id reuse — i.e. it deliberately leaks to stay
correct. A `WeakValueDictionary` keyed on `id()`, or simply hanging the draft
map off the `NodeSchema` as a private attr (it is a pydantic model; it already
has `_by_type_cache`), removes the leak and the lock.

### A-4 · The IR is a strict mirror of one CLI version

`GrammarModel` sets `extra="forbid"` and hand-patches `$schema` out in a
`model_validator`. That is a deliberate, defensible choice for *authoring*.
For the **community import path** it is a liability: `build_from_source_dir`
parses an arbitrary upstream `grammar.json` into this model, so any key a
newer CLI adds turns "import a community grammar" into a `ValidationError`.
The same path also *re-emits* the grammar from the IR rather than handing the
CLI the original file, so a faithful round-trip is load-bearing and untested
against real upstream grammars beyond the three checked-in fixtures.

`conftest.CLI_VERIFIED = {"0.25"}` is an honest acknowledgement that the whole
B side is pinned to one CLI minor. That is fine for a personal tool and should
be said louder in the README than it currently is (it is currently only in
`docs/architecture.md` §8).

### A-5 · The external-scanner seam is stringly typed, and the rule-class surface leans on a CLI coincidence

`class Newline(External)` produces (`evidence/probe_f_surface.txt`, F4):

```
externals:        [TOKEN(STRING "NEWLINE")]
rule 'newline':   TOKEN(STRING "NEWLINE")
```

The rule body is a token that lexes the literal characters `NEWLINE`. It works
only because the CLI unifies the external declaration with the identically
valued token. Nothing in the codebase states that dependency, no check
verifies it, and an author reading `rules.py` cannot tell why it works. The
scanner contract (`docs/scanner-library.md`) is otherwise the most carefully
documented part of B — this is the one hole in it.

### A-6 · The error taxonomy has a hole and the version story has a phantom

- `WasmRuntimeUnavailableError` subclasses `RuntimeError`, **not**
  `PydantreeSitterError`, and is not exported from `pydantree_sitter`
  (`evidence/probe_a_core.txt`, P9) — yet `docs/user-guide.md` §5 lists it in
  the failure-surface table. `except PydantreeSitterError` does not catch it.
- `bundle_format` "versions the artifact contract" (D12) but formats 1 and 2
  are handled **identically** — there is not one branch on the value anywhere
  (`evidence/probe_f_surface.txt`, F3). It is a version number that versions
  nothing. Harmless, but it is presented as a guarantee.

### A-7 · The public surface is smaller than the documentation

`from pydantree_sitter_grammar import *` **raises `AttributeError`**: `__all__`
lists `"rule"`, which the module never imports (there is no module-level
`rule` combinator — only `Grammar.rule`). The module docstring advertises it
in its "Public surface" list too.

Documented-as-canonical APIs that are *not* on the package namespace:
`write_bundle` ("THE ONE bundle writer", architecture.md §4),
`build_from_source_dir`, `Toolchain`, `derive_schema_for_dir`,
`build_community_bundle`. Users must import from submodules; `conftest.py` and
`schema_tool.py` already do exactly that.

---

## 4. Defects

Severity: **MAJOR** = silent wrong data, or an advertised feature that does not
work. **MOD** = wrong/opaque behaviour with a workaround. **MIN** = hygiene.

---

### D-1 · MAJOR · CONFIRMED — cartesian duplication of list captures

**Where:** `compiler.py:282` (`_field_quant`) + `match.py:106` (`merge_group`).

Two or more `list[T]` fields on one anchor produce every *combination* of
their occurrences, and `merge_group` extends list captures **without
deduplication** (it dedups scalars only — `match.py:119`).

```
grammar:  item := "(" a* ";" b* ";" c* ")"
model:    a: list[str]; b: list[str]; c: list[str]
```

| items per field | len(a) | len(b) | len(c) | expected | time |
|---|---|---|---|---|---|
| 2 | 8 | 8 | 8 | 2 | 0.3 ms |
| 4 | 64 | 64 | 64 | 4 | 0.8 ms |
| 8 | 512 | 512 | 512 | 8 | 8.5 ms |
| 12 | **1728** | **1728** | **1728** | 12 | 22 ms |

(`evidence/probe_g_scale.txt`, G2; two-field case in
`evidence/probe_d_toolchain.txt`, D1: `a=['x','y','z','x','y','z']`,
`b=['p','p','p','q','q','q']`.)

This is **k^N** matches and **k^N** list entries for N repeated fields with k
occurrences. Any grammar node with two repeated fields — extremely common
(attributes + parameters, modifiers + arguments, decorators + statements) —
silently yields corrupt data. A single list field is correct (G3), which is
exactly why the suite misses it: every list test uses one list.

Note the provenance: 020's fix A2 changed `_field_quant` from `""` to `"?"` to
stop empty lists dropping rows. That fix is right for one list and introduced
this for many.

**Minimum fix:** dedupe list captures by node id, order-preserving, in
`merge_group` — 4 lines. That fixes correctness; the k^N *match count* remains
a scaling hazard. **Structural fix:** §7.1.

**Regression test to add:** the three-field grammar above, asserting
`len(a) == len(b) == len(c) == n`.

---

### D-2 · MAJOR · CONFIRMED — `M()` path alternation is checked as a descent chain

**Where:** `compiler.py:255-275` (`_check_path`).

```python
for step in spec.path:
    if step is GAP: gap = True; continue
    for kind in step.kinds:          # <- alternatives
        if prev is not None:
            ... is_possible_descent(prev, kind) ...
        prev = kind                  # <- kinds[1] is checked as a CHILD of kinds[0]
```

The inner loop walks a `PathStep`'s **alternatives** as if they were a
**chain**. `M("document", ("object", "array"))` — the documented alternation
feature, `markers.py:38` — is rejected with:

```
__match__ chain (PathStep(kinds=('document',)), PathStep(kinds=('object','array'))):
'array' cannot occur as a child of 'object'
```

(`evidence/probe_e_altpath.txt`, E2/E3.) Alternation therefore only works when
the alternatives happen to be legal parents of each other — i.e. essentially
never, since alternatives are by definition siblings.

The kicker: **it works fine without a schema.** `_check_path` is only called
when `language.schema is not None`, so:

```
Language.from_module(tree_sitter_python)                  # no schema
M('module', ('function_definition','class_definition'))   # -> works, 2 patterns, correct rows
```

**Binding the node-schema — the product's differentiator — is what breaks the
feature.**

**Fix:** the alternative check is per-kind against `prev_step.kinds`, not
against the previous *kind*:

```python
prev_kinds: tuple[str, ...] | None = None
for step in spec.path:
    if step is GAP: gap = True; continue
    if prev_kinds is not None:
        for kind in step.kinds:
            if not any(_ok(p, kind, gap) for p in prev_kinds):
                _raise(...)
    prev_kinds, gap = step.kinds, False
```

(Whether a *partial* match should be an error or a warning is a design call:
`M(("a","b"))` under a parent that can only hold `a` is arguably a warning.)

---

### D-2b · MAJOR (process) · CONFIRMED — the 020 regression test for this is vacuous

`tests/test_extract.py:257 test_alternation_anchor_checks_every_kind` is the
guard 020 added for its A4 fix. It asserts:

```python
assert "'array'" in str(exc.value) and "pair" in str(exc.value)
```

The error it actually receives is the D-2 chain error —
`… 'array' cannot occur as a child of 'object' … (possible children of
'object': ['pair'])` — which contains both substrings for entirely unrelated
reasons (`evidence/probe_e_altpath.txt`, E1). The test has never verified the
behaviour it names.

This is the only vacuous assertion I found, but the pattern that produced it
(`assert "<short substring>" in str(exc.value)`) appears **19 times** across
the suite. Substring-on-message assertions should at minimum pin the *error
class plus a discriminating phrase*, e.g. `"has no CST field"`, not a bare
node kind that will appear in half the taxonomy's messages.

---

### D-3 · MAJOR · CONFIRMED — model field order is load-bearing; failure is opaque

**Where:** `compiler.py:337-356`.

```python
class Ok(OutputModel):        class Bad(OutputModel):
    __match__ = M(...)            __match__ = M(...)
    name: str = capture("name")   ret: str | None = capture("return_type")
    ret: str | None = ...         name: str = capture("name")
```

`Ok` works. `Bad` raises `QueryBuildError: Impossible pattern at row 0,
column 51` (`evidence/probe_b_order.txt`). It fails identically **with a bound
schema** (`evidence/probe_g_scale.txt`, G1) — the bind-time checks pass and the
failure comes out of tree-sitter, pointing at a column offset in generated
`.scm` the user has never seen.

Nothing documents this. `README.md:41` and `docs/architecture.md` both state
that sibling order is *out of scope* and lives in `__raw_query__`.

Three ways out, in increasing order of quality:

1. Document it (bad — the constraint is invisible and the error is unusable).
2. Sort emitted children into the grammar's own field order (the schema knows
   it) and raise a real `SchemaCheckError` when no order works.
3. Stop emitting fields as siblings at all — §7.1. This is the same fix as
   D-1.

---

### D-4 · MOD · CONFIRMED — a self-recursive nested record model raises `RecursionError`

**Where:** `compiler.py:113-116` + `binding.py:229-237`.

`compile_spec` binds nested sub-extractors *during* `Extractor.__init__`, but
`Language.extractor` only inserts into `self._extractors` **after** the
constructor returns. A model that nests itself — the natural way to model a
JSON tree — recurses forever:

```python
class Rec(OutputModel):
    __match__ = M("document", "object", record=True)
    inner: "Rec | None" = capture("inner")
# -> RecursionError
```

(`evidence/probe_d_toolchain.txt`, D3.)

**Fix:** insert a placeholder into `_extractors` before compiling, or lazily
resolve `nested_extractors` on first use. Either way the recursion should be
*supported*, not merely diagnosed — recursive documents are the main reason
record mode exists.

---

### D-5 · MOD · CONFIRMED — `extract_tree` accepts a tree from another language

See A-2. Returns a garbage row (`[Item2(a=[])]`) with no error.

---

### D-6 · MOD · CONFIRMED-by-reading — record mode silently discards declarations

Three independent silent narrowings in `_compile_record`:

- `record_kind = suffix[-1].kinds[0]` (`compiler.py:605`) — path **alternation
  is dropped**, only the first kind is used.
- the outer query wraps `s.kinds[0]` (`compiler.py:632`) — same for every
  ancestor step.
- `_key_spec(key_shapes)` uses `key_shapes[0]` (`compiler.py:728`) — when a
  pair's key can be several shapes (e.g. `identifier` **or** `string`, common
  in TOML/INI/nix-shaped grammars), **only the first sorted shape is emitted**
  and records keyed the other way silently vanish. *(By reading only: no
  checked-in fixture has a multi-shape key, which is also why no test covers
  it — `evidence/probe_a_core.txt`, P6 scans jsonlike/nix/rust and finds
  none.)*

None of these raise; all three are "pick the first and say nothing", which is
precisely the behaviour `_find_pair_kind` was rewritten in 018 §4.3 to
*avoid*. Apply the same rule: emit for all shapes, or raise naming them.

---

### D-7 · MOD · by reading — alternation anchors emit one field kind for every alternative

`_infer_field_kind` (`compiler.py:387`) unions the possible kinds **across all
anchor kinds** and, if exactly one coerces, constrains the emitted capture to
it — for *every* anchor pattern. If anchor `A`'s field yields `integer` and
anchor `B`'s yields `string` and the field is `int`, the check passes (union
contains a coercible kind) and `B`'s pattern is emitted as
`field: (integer)`, which can never match. Rows from `B` disappear silently.

Currently masked by D-2 (you cannot get an alternation past the path check
with a schema bound). It will surface the moment D-2 is fixed, so fix both
together: infer and emit **per anchor kind**, not over the union.

---

### D-8 · MOD — `ERROR` / `MISSING` nodes materialize silently

`(x ;` (truncated) against a grammar expecting `(a* ; b* )` yields
`Item(a=['x'], b=[])` with no signal (`evidence/probe_d_toolchain.txt`, D2;
`evidence/probe_c_lists.txt`, C1 shows a MISSING node materializing as `''`).
`tree.root_node.has_error` is `True` and nothing in the codebase reads
`has_error` or `is_missing`.

For a library that spends 582 lines on static analysis and stakes its identity
on checked extraction, silently extracting from a broken parse is the wrong
default. Minimum: a bind-time-configurable policy (`strict` already exists as
a knob) and a `MatchFailure` for anchors under an `ERROR`. At the very least,
document it.

---

### D-9 · MOD · CONFIRMED — `from pydantree_sitter_grammar import *` raises

`__all__` names `"rule"`; the module never defines it (`evidence/probe_f_surface.txt`,
F1). The docstring's "Public surface" block lists it too. Either export a
module-level `rule` combinator or delete both mentions.

---

### D-10 · MOD — the canonical B APIs are not exported

`write_bundle`, `build_from_source_dir`, `Toolchain`, `derive_schema_for_dir`,
`build_community_bundle` — all documented as *the* way to do their job, none on
the package namespace (F2). My own probe hit this immediately.

---

### D-11 · MIN — `_PROPOSED_CACHE` never evicts

See A-3. Also: the lock added in 020 protects the dict but the wider
`compile_spec` path is still not thread-safe (a `Language._extractors`
`get`/`set` pair races; two threads can each build an `Extractor` and one wins).
Either document "not thread-safe" or lock the bind.

---

### D-12 · MIN — the `\s` extra is injected next to a named whitespace extra

`Grammar.build()` prepends `PATTERN("\s")` unless `_explicit_whitespace`, and
`_explicit_whitespace` is only set for an **inline** `PatternNode` extra
(`builder.py:497`). An author who does the documented, recommended thing —
declare a named rule and `g.extra(tg.ref("ws_rule"))` — gets **two**
whitespace extras (`evidence/probe_f_surface.txt`, F7). Follow the SYMBOL
into the rule table before deciding.

---

### D-13 · MIN — `py.typed` is shipped with 36 mypy errors

Both wheels force-include `py.typed`, so every downstream user type-checks
against these annotations. `mypy --ignore-missing-imports` reports 36 errors
across 11 files (`evidence/mypy.txt`), including real annotation lies:
`expressions._as_op` is declared `-> B` and returns a `Rule` node;
`OutputModel._match_spec` is not declared on the class at all. mypy is in the
dev extras but **no test or gate runs it** — the gate is `pytest` only.

---

### D-14 · MIN — four `SyntaxWarning: invalid escape sequence` at import

`builder.py:111,132,137` and `patterns.py:57,65,66,69` — non-raw docstrings
containing `\s` / `\.`. They print on every test run
(`evidence/full-suite.txt`) and become errors in a future Python. `r"""`.

---

### D-15 · MIN — dead code and misleading signatures

From `evidence/ruff.txt` (F401/F841/ARG/RUF059), the ones that matter:

- `_compile_field(compiled, language, ...)` and `_compile_record(...)` **never
  use `language`** (`compiler.py:311,596`) — the parameter exists only so
  `emitted_source` can pass `None`. Delete it.
- `_check_raw_bindings` computes `annotations` and never uses it
  (`compiler.py:191`).
- `_check_field_bindings(model_cls, spec, ...)` — `spec` and `annotations`
  unused.
- `rules.assemble` unpacks `attr_nodes` and discards it (`rules.py:424`); the
  map that `_from_annotations` builds and returns is dead.
- `builder.replace_rule` binds `old` and never uses it (`builder.py:454`).
- `corpus.CorpusFailure.message(self, style)` ignores `style`, which
  `CorpusResult.report` carefully passes.
- 18 unused imports.

Individually trivial; collectively they are the tell that the "one owner per
concern" refactor left seams behind.

---

### D-16 · MIN — `bundle_format` versions nothing; `< 1` is accepted

See A-6. `fmt > 2` is the only branch, so `bundle_format: 0` and `-7` load
happily.

---

### D-17 · MIN — `_snake` and `class_name` are documented as shared; they are duplicated and not inverses

`rules._snake`'s docstring: "Shared with the codegen class-name helper".
They are two implementations in two packages, and the round trip fails for
every acronym: `HTTPServer → http_server → HttpServer`
(`evidence/probe_f_surface.txt`, F5). Harmless today; the docstring claim is
not.

---

### D-18 · MIN — stale numbers and a self-contradicting doc section

- `README.md:86` "272 green"; `docs/development.md:78` "265 green". Actual:
  **342**. Both were current at the time and neither has a gate.
- `docs/user-guide.md` §2.6 opens "Generate a `.pyi` beside the schema — per
  named kind: field accessors, `get(field)` overloads, `children(kind)`
  overloads" and then the code comment two lines down says "REAL runtime
  classes (**not** .pyi fiction)". `codegen.py` emits neither `get(field)` nor
  `children(kind)` overloads. The paragraph predates D7 and was never rewritten.
- `docs/user-guide.md` §2.2 says a nested `OutputModel` field "materializes the
  nested node with the inner model" without saying it is a **`ShapeError` in
  field mode** (`spec.py:270`).
- `docs/README.md` says "the three packages"; there are two.
- The `docs/README.md` phase table stops at phase 009; there are 21 phases.

---

## 5. Tests and evidence discipline

**What is genuinely strong** (and I want to be explicit, because it is
unusual):

- Regenerable JSON oracles cross-checked against independent ground truth,
  with generator and checker sharing collectors so they cannot drift apart.
- Native artifacts deliberately not committed; bundles rebuilt from source.
- The **byte-identity gate** between the rule-class surface and the builder
  DSL (`test_rules.py::test_gate_devenv_class_grammar_identical_to_builder_dsl`)
  is the single best test in the repo: it makes "sugar over the builder" a
  mechanically enforced fact rather than a claim.
- `test_point_access.py` encoding a *known upstream C bug* as a source-level
  gate is exactly right.
- Hermetic cache isolation, toolchain auto-skip, `sys.modules` leak cleanup.

**Where it is weak, and why the defects above survived:**

1. **Every list test uses one list.** D-1 needs two. The suite's shape
   (one feature per test, minimal fixture) systematically misses
   *interaction* bugs. Add a "two of everything" fixture grammar: two repeated
   fields, two optional fields, two alternatives, and bind one model over all
   of it.
2. **Assertion strength.** 19 `assert "<substring>" in str(exc.value)`, one of
   which (D-2b) has never tested its subject. Prefer asserting the error
   *class* plus a phrase that only that check can produce.
3. **Order is never varied.** No test declares fields in a different order
   from the grammar. D-3 is a one-line test away.
4. **No property/fuzz layer for the emitter.** `match.py` has a hypothesis
   property test against a brute-force reference — that is exactly the right
   idea and it is applied to the one component that turned out to be correct.
   The emitter and the merge are where the bugs are, and they have none.
   A natural property: *for any anchor, `len(row.<list field>)` equals the
   number of that field's children on the anchor node* — that single property
   kills D-1.
5. **No lint/type gate.** 171 ruff findings and 36 mypy errors, none of which
   fail anything.

---

## 6. What is right (so a rewrite does not throw it away)

- The core bet (C-1) and the anchored-path model.
- The **node-schema-is-the-CLI-byproduct** decision (D3). Deleting the
  `node_types.rs` hand-port removed a whole class of drift. This is the
  best architectural decision in the project.
- The bind-time-checks *shape* — one place, once, before parsing, with the
  model's source site in the message. `SchemaCheckError` messages are among
  the best I have read in a parsing library.
- Product B's conflict remapping to per-production DSL sites. That is a real,
  hard-won capability and it works.
- The scanner library as *documented mechanism plus proven gotchas* rather than
  a code dump.
- The `_site`-on-the-node provenance model (D8) — no registry, no drain, no
  id reuse.
- `load_grammar_so`'s unlinked-snapshot dlopen. The 020 root-causing of that
  SIGSEGV was excellent work and the fix is the right one.

---

## 7. What I would change

### 7.1 · One anchored pattern per capture (fixes D-1 and D-3 together)

Instead of one pattern with N sibling captures, emit N+1 anchored patterns:

```scheme
(module (function_definition) @__anchor__)                        ; anchor-only
(module (function_definition return_type: (_) @ret) @__anchor__)
(module (function_definition name: (_) @name) @__anchor__)
```

`match.group_matches` + `merge_group` already merge by anchor id — this is the
machinery they were built for. Verified working:

```
{'name': ['f'], 'ret': ['int']}
{'name': ['g']}
--- order independent, optional handled, no 'Impossible pattern' ---
```

Properties:

- **order-independent** — each pattern has one child, so tree-sitter has no
  sibling order to reject (D-3 gone);
- **linear, not cartesian** — N repeated fields give `k₁+k₂+…+k_N` matches
  instead of `k₁·k₂·…·k_N` (D-1 gone at the root, not just deduped);
- optional captures need no `?` gymnastics — an absent field yields no match
  for that pattern;
- predicates still attach per pattern.

Costs to design through, honestly:

- "a required capture that does not match drops the row" must move from the
  query engine into materialization. `build_kwargs` + pydantic validation
  already does most of this; the required/optional distinction becomes
  explicit instead of encoded in a quantifier.
- more patterns per model (N+1 instead of 1) — but each is smaller, and the
  existing `_combinations` cartesian over `NodeKind` alternations shrinks too.
- `Extractor.query_source` becomes multi-pattern; it is diagnostics-only.

This is the single highest-value change in the review.

### 7.2 · Fix `_check_path` (D-2) and `_infer_field_kind` (D-7) together

Alternatives are a set at one level, not a chain. Both functions need
`prev_kinds: tuple[str, ...]` semantics and per-anchor emission. Replace the
vacuous guard (D-2b) with one that asserts the error *class* and a phrase only
that check emits, plus a positive test that a legal alternation **binds and
extracts**.

### 7.3 · Make record mode a named thing

`class X(RecordModel)` (or `pydantree_sitter.record.RecordModel`) rather than
`M(..., record=True)`. Move `_find_pair_kind` / `_key_shapes` / `_value_shapes`
/ `_unescape_json_string` into a `record.py`. `compiler.py` drops to ~450 lines
of field-mode logic that one person can hold in their head. Then fix D-6's three
silent narrowings inside that module, where they are visible.

### 7.4 · Close the schema-distribution gap (C-2)

Pick one and say it in the README:

- **(a)** ship `node-schema.json` for the top community grammars as a data
  package, and make `Language.from_module` find it; or
- **(b)** make `Language.from_module(...)` without a schema emit a bind
  warning ("no node-schema: model↔grammar checks are OFF") and fix every doc
  example to bind one.

(b) is one afternoon and is honest. (a) is the product.

### 7.5 · Truth-up the honesty statements

- C2 ("never silent name-regex inference") → narrow it to record-mode value
  shapes, and add inferred kinds to `Extractor.warnings`.
- The `# checks run here, once` comments in schema-less examples → remove or
  qualify.
- "a silent cross-language result is impossible by construction" → make it
  true with the `extract_tree` guard (D-5), then keep the sentence.
- The sibling-order claim (D-3) → true once 7.1 lands; false today.

### 7.6 · Add the cheap gates

`ruff check src`, `mypy src`, and a test asserting the README's suite count
matches reality (or delete the count). Fix the four `W605` docstrings. Delete
the phantom root distribution's `[project]` block, or make it real.

### 7.7 · Ordered by value

| # | change | fixes | effort |
|---|---|---|---|
| 1 | one anchored pattern per capture (7.1) | D-1, D-3 | 1–2 days |
| 2 | `_check_path` alternatives + per-anchor inference (7.2) | D-2, D-2b, D-7 | half a day |
| 3 | `extract_tree` language guard + nested-extractor placeholder | D-5, D-4 | 1 hour |
| 4 | record-mode `key_shapes` / alternation narrowings | D-6 | half a day |
| 5 | export the documented B API; drop `"rule"` from `__all__` | D-9, D-10 | 15 min |
| 6 | schema-distribution decision + doc truth-up (7.4, 7.5) | C-2, C-3 | 1 day |
| 7 | lint/type gate, `W605`, dead code, stale counts | D-13…D-18 | 2 hours |
| 8 | record mode into its own module (7.3) | C-5 | 2 days |

---

## 8. What this review does not claim

- I did not re-audit findings from 014/018/019/020; I spot-checked their fixes
  and found one (A4/alternation) incompletely fixed with a vacuous guard.
- I did not review the C scanners' internals, the `.agents/skills/` content,
  or `devenv.nix` / `gitman.toml`.
- I did not test on any platform but Linux, any Python but 3.13, any CLI but
  0.25.3, or any pydantic but the pinned one.
- D-7 is reasoned from the source, not reproduced end to end — D-2 blocks the
  path that would exercise it. Everything else marked CONFIRMED has a
  reproduction in `evidence/`.
- Severity is ranked for *silent wrongness*, not for how likely this
  particular author is to hit it. If you never use two list fields, never
  reorder a model's fields, and never bind a schema with an alternation path,
  today's code is correct for you.
