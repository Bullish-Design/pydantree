# Kickoff prompt — pydantree Phases A–D (selector + lazy resolution)

Paste everything below the line into a clean session.

---

You are working in `/home/andrew/Documents/Projects/pydantree`.

Your job is to execute **Phases A, B, C, and D** of an architecture plan that a
prior investigation produced. The investigation is finished and its evidence is
committed to disk. **Do not re-derive it.** Read it, trust it, and build on it.

## 1. Read first

In the repository:

- `AGENTS.md` (= `CLAUDE.md`)
- `.agents/skills/my-ai/SKILL.md` — the cross-repo law
- `.agents/skills/gitman/SKILL.md` — all version control routes through gitman
- `.agents/skills/pydantree-dev/SKILL.md`
- `.agents/skills/pydantree-extraction/SKILL.md`
- `src/pydantree_sitter/find.py` — the module this work is about
- `src/pydantree_sitter/nodes.py` — `_build_resolver`, `Node.from_node`
- `src/pydantree_sitter/pattern.py` — the ast-grep seam

The prior investigation's report and probes:

- In repo (uncommitted):
  `.scratch/projects/026-cursor-walk-benchmark/sessions/20260909-2890613b/`
- Durable copy outside the repo (use this if the repo copy is gone):
  `/home/andrew/pydantree-evidence-026-20260909-2890613b/`

Read `REPORT.md` **in full**, and note in particular:

- **§12 contains a retraction.** An earlier headline example (python
  `Assignment`, "1176 query rows vs a walk `ExtractionError`") no longer
  reproduces; it was an artefact of a 9-entry demo schema that has since been
  replaced with the real 217-entry one. Do not cite it.
- §13 is the finding that drives Phases C and D.

The probes in `probes/` are reusable. `harness.py` builds all five language
grammars and the real-file corpus; `oracle_sweep.py` and `oracle_api.py` are
the differential oracles; `bench.py` and `bench_cache.py` are the benchmarks.
Run them with `PDT_BENCH_CACHE` pointing at a scratch dir.

## 2. Facts you must not re-derive

Measured 2026-09-09 on Intel Xeon W-2125, Python 3.13.5, tree-sitter bindings
0.26.0, CLI 0.25.3, pydantic 2.11.1, ast-grep-py 0.45.3, over real files in
five languages (python, bash, nix, rust, markdown; small/medium/large tiers).

1. **Resolution is 92–99.3 % of every `find_in` call. Anchor discovery is
   0.7–8 %.** One python `class_definition` costs **151 ms** per match because
   the resolver eagerly materialises its whole body subtree.
2. **A cursor/tree-cursor walk is identical to the existing recursive walk** —
   0 mismatches in 1326 cases, and within run-to-run noise on speed (7 sign
   flips in 63 comparisons across two runs). Do not pursue it.
3. **45 kinds across the five grammars emit a query that will not compile.**
   `_query_walk` catches `QueryBuildError` and silently falls back to `_walk`.
   Python alone has 11, including `FunctionDefinition`, `ClassDefinition`,
   `Call`, `Attribute`, `ForStatement`, `WhileStatement`, `WithStatement`.
   A *more accurate* schema made this worse, not better.
4. **The query path and the walk path are not equivalent.** They differ in row
   sets (bash `UnaryExpression` 19 vs 163; `BinaryExpression` 143 vs 155;
   `VariableAssignment` 406 vs 417; rust `LetDeclaration` 127 vs walk-raises),
   and in row order for self-nesting kinds (rust `ScopedIdentifier`,
   `BinaryExpression`; python `BinaryOperator`, `BooleanOperator`). The comment
   in `find.py` calling `_walk` "the safe execution fallback" with "complete
   schema behavior" is not supported by measurement.
5. **The compiled query is never cached.** `find.py:160` and `find.py:202`
   build and compile a fresh `Query` on every call. Cost 0.1–4 ms and
   288–3876 KiB per call.
6. **Failure is not local.** `find_in(raw, FunctionItem)` over
   rust `alloc/src/sync.rs` raises `ExtractionError` because of a
   `let _ = ...` nested inside one function body. One unresolvable node
   several levels down discards every match in the file.
7. **ast-grep can drive a pydantree-built grammar, verified end to end.**
   `register_bundle_language` + `ast_grep_py.register_dynamic_language` works;
   the two engines then see the same tree (33 named nodes, intersection 33,
   0 only in pydantree) because they load the same `.so`.
   Caveats: registration is process-global and ast-grep-py accepts dynamic
   languages **only in its first registration call**; and `meta_var_char` must
   lex as an identifier in the target grammar or every metavariable pattern
   returns **0 matches silently** (in Nix, `$` fails, `_` works).

## 3. Decisions already made — do not re-litigate

- **Filter semantics, not assert semantics.** A declaration *defines* a match.
  A node of the right kind that does not fit the declaration is a non-match,
  not an error. Errors are reserved for genuine problems (malformed source,
  codec failure).
- **Nested resolution becomes lazy.** Child `Node` fields resolve on attribute
  access and cache. Scalars, `span`, and `__value__` stay eager.
- **Keep ast-grep.** It is the only expressive-search and rewrite layer, and it
  works with pydantree-built grammars. Appendix E idea 6 ("drop ast-grep") is
  rejected on this evidence.
- **Keep the raw-query escape hatch.** `raw.py`, `__raw_query__`, `Query`,
  `Cursor`, `MatchView`, and capture support all stay. They express sibling
  order, negation, and multi-anchor joins that a selector cannot.
- **Do not optimise anchor discovery.** It is 0.7–8 % of the cost.
- **Keep the schema-backed typed-node model and the Product A / Product B
  separation unchanged.**

## 4. How to work here

- Run every project command inside `devenv shell`, batched:
  `devenv shell --no-tui --no-reload -- bash -c '...'`
- **Route all version control through gitman. Never run raw `git` or `jj`.**
  gitman is **not on the devenv PATH**. Use the absolute path:
  `/home/andrew/.local/share/repoman/venv/bin/gitman`
- Exit codes are an API: `0` ok, `1` finding/decision, `2` infra, `3` usage.
- Write in Simplified Technical English: short sentences, active voice, one
  term per idea, no filler.
- Findings go under `.scratch/projects/0NN-*/`, raw output under `evidence/`,
  probes committed as `probe_*.py` so verdicts re-run.

### Version-control hazard — read before you commit

At the time of writing the repo was **OFF-CANONICAL**: lane
`024-typed-node-universe` has a divergent change-id (one change → multiple
commits), and gitman **refuses every mutating verb** (`start`, `save`, `split`,
`publish`) until it is resolved. `gitman reconcile` returns PARTIAL and does not
clear it. A concurrent session owns that lane.

Check `gitman status` first.

- If it is canonical, work on a lane of your own: `gitman start <name>` (a flat
  name roots on trunk; a `/`-path name stacks on its name-parent, which is
  probably not what you want).
- If it is still off-canonical, **stop and ask the user** before touching
  version control. Do not run `gitman reconcile --abandon`; it discards strays
  and could destroy the other session's work. Do the engineering work, keep it
  on disk, and report the blocker.

Never land, tag, release, or push `main` or `024-typed-node-universe`.

## 5. The gates

Every phase ends green on all of these:

```console
devenv shell -- python -m pytest -q
devenv shell -- python -m pytest -q -W error
devenv shell -- ruff check src tests examples
devenv shell -- ty check src
devenv shell -- python -m pytest -q tests/test_docs_snippets.py
devenv shell -- python examples/wheel-extract/extract.py
devenv shell -- python examples/bash-extract/extract.py
devenv shell -- python examples/devenv-extract/extract.py
devenv shell -- python examples/devenv-subset/extract.py
```

Baseline at handoff: **364 passed, 1 xfailed**; `ty` clean; docs snippets pass;
all four examples exit 0. **`ruff` currently FAILS with 8 errors** — Phase A
fixes that. Note `examples/devenv-subset/extract.py` rewrites its own tracked
`dist/` bundle; that is normal.

---

# Phase A — unblock. No behaviour change.

**Goal:** clear the broken gate and remove two pieces of avoidable waste,
without changing a single row any API returns.

### A1 — Fix ruff (8 errors)

- `tests/test_packaging.py:65` — `E741 Ambiguous variable name: l`. This is
  **new code**; rename the variable.
- Six `E402` in `tests/test_scanners.py`, `tests/test_corpus.py`, and
  `tests/fixtures/bfree/consumer_env/sitecustomize.py`, plus one more. These
  files are unchanged since 2026-09-08; a ruff version change surfaced them.
  Deliberate late imports after a `pytestmark` skip guard are a legitimate
  pattern — prefer a narrow `[tool.ruff.lint.per-file-ignores]` entry in the
  root `pyproject.toml` (which currently has no `[tool.ruff]` section at all)
  over rewriting working tests. Say which you chose and why.

### A2 — Cache the compiled query

`find.py:160` (`_query_walk`) and `find.py:202` (`_raw_find`) rebuild and
recompile on every call. Add a cache keyed by `(class, language)` that also
remembers a `QueryBuildError` so a failing compile is attempted once, not
once per call.

A working prototype is `probes/bench_cache.py` in the evidence directory. It
measured **identical rows in 42 of 42 cases**, median 1.07× on medium and large
inputs, up to 2.38× where matches are few, and roughly 30× on small inputs
where the compile is the whole cost.

**Acceptance:** every generated class over every corpus file returns
byte-identical rows before and after. Re-run `probes/oracle_sweep.py` and
`probes/oracle_api.py` and show no new divergence.

### A3 — Repair the ast-grep seam

Phase 024 collapsed `Language` into `Grammar` and orphaned `pattern.py`:

- `Grammar.__slots__` is `("language", "namespace", "schema")`. It has no
  `astgrep_name` and no `astgrep_is_bundle`, which `Pattern.__init__` reads.
  `Pattern(rule, language=grammar)` therefore raises
  `UnsupportedLanguageError`; callers must pass `astgrep_name=` by hand.
- `pattern.py:97` documents `Language.register_astgrep()`. That class no longer
  exists. Provide `Grammar.register_astgrep()` and fix the docstring.
- Record `meta_var_char` in the bundle metadata (`tree-sitter.json`) when a
  grammar is built, and have registration use it. A wrong sigil returns zero
  matches with no error — see fact 7.
- **No test covers `register_bundle_language` or `registered_languages`.**
  Add them. `probes/probe_astgrep_bundle.py` is a working starting point.
- Remember ast-grep-py only accepts dynamic languages in its first
  registration call. Provide one collection point if several bundles must be
  registered in one process.

**Phase A acceptance:** all gates green, including ruff. No row returned by any
public API changes.

---

# Phase B — the decision. This is the important phase.

**Goal:** one definition of "what matches", and a test that proves the finders
agree.

### B1 — Write the semantics down

Add a short decision record under `docs/` stating filter semantics, with the
`let _ = ...` case from fact 6 as the worked example. One page. This is the
document every later argument refers back to.

### B2 — Extract the selector

Introduce a `Selector`: the declaration compiled to inspectable **data**, not
to a query string. It holds:

- the anchor kind, with supertype expansion;
- the ancestor path (`__under__`, normalised);
- per declared child: name, allowed kind set, optional, repeated, predicates.

Most of this already exists in `find.py` as `_schema_kinds()`,
`normalize_under()`, and `nodes.Child`. This step mostly **collects** them into
one object rather than inventing anything. Keep it renderable: a selector must
be able to produce a tree-sitter query and (later) an ast-grep rule, and be
directly evaluable in Python.

### B3 — Make the walk evaluate the selector

`_walk` currently tests only `node.type == cls.__kind__` and the ancestor path.
Give it the field pre-filter it lacks: for each declared non-optional child,
check the field's kind against the selector's allowed set **before** calling
`from_node`. This is a few `child_by_field_name` lookups against a set that is
already computed — far cheaper than a query compile.

Under filter semantics a node that fails the pre-filter is skipped, not raised.

### B4 — The equivalence property test

Promote the prior investigation's differential harness into a permanent test:
for every generated class in every fixture grammar, over the repository's real
corpus, assert

> **same selector ⇒ same rows, in the same order**

for the walk and the query. `probes/oracle_sweep.py` and `probes/oracle_api.py`
already do exactly this comparison and know the current divergences; port them.

**Phase B acceptance:** the equivalence test is green, or every remaining
difference is documented as intended with a reason.

**STOP CONDITION.** If the walk and the query cannot be made to agree, stop.
Do not proceed to Phase C. Report which semantics each one implements and what
would have to change. Deleting a finder while two finders disagree ships a
silent behaviour change.

---

# Phase C — deletion, now safe

**Goal:** remove the emitted query if, and only if, it has been shown to earn
nothing.

1. Re-measure the query accelerator **with the Phase A2 cache in place**, using
   `probes/bench.py`. Prior measurement says anchor discovery is 0.7–8 % of the
   call, so the ceiling on any win is small.
2. If it earns nothing, delete `query_source`, `_query_walk`, and the
   `src/pydantree_sitter/emit.py` shim.
3. **Keep** `raw.py`, `__raw_query__`, `Query`, `Cursor`, `MatchView`, and
   capture support. This is the honest, smaller version of Appendix E idea 10:
   delete the *emitted* query, not the *raw* one.

**Acceptance:** the equivalence test from B4 still passes with the query path
gone. Follow the 024 convention — one line in a `DELETED_TESTS.md` per deleted
test, naming the construction that makes the bug impossible. Record the public
API delta explicitly. The public surface is currently **14 names**; state the
new list.

---

# Phase D — laziness and the expressive layer

**Goal:** the 100× that Phase C cannot deliver.

### D1 — Lazy nested resolution

Child `Node` fields resolve on attribute access and cache the result. Scalars,
`span`, and `__value__` stay eager. `find_in` should materialise the anchor,
not the world.

This also makes failure local: a bad nested node invalidates *that field*
rather than discarding its grandparent (fact 6).

**Acceptance:** measure with `probes/bench.py` and `evidence/resolution-cost.txt`
as the baseline. The python `class_definition` per-match cost (151 ms at
handoff) must drop materially. No row values may change for code that reads the
same fields.

### D2 — Promote `Pattern`, shrink `agreement.py`

With the seam repaired in A3, make ast-grep the documented expressive front
end: `Pattern` finds, `.extract(TypedClass)` types. Prefer registering the
project's own bundle over ast-grep's vendored grammar — then both engines load
the same artifact and agreement is by construction. `GrammarAgreement` and
`measure_agreement` become dead for the bundle path; `char_to_byte_table` stays
(ast-grep reports character offsets). Reduce `agreement.py` to the
wheel-grammar case, or retire it if no path needs it.

### D3 — Then, and only then, rewrite

Appendix E idea 7 ("rewrite belongs to the tree") becomes tractable once D2
lands. `syntax.py`'s `SyntaxCheck` is its safety net; keep it.

---

# Reporting

Work phase by phase. After **each** phase, report:

- what changed, file by file;
- the gate results, pasted verbatim with exit codes;
- the benchmark or oracle numbers that justify the change;
- any public API or generated artefact delta;
- what you did **not** do, and why.

Keep raw output under `.scratch/projects/0NN-*/evidence/`. Do not summarise a
failing gate as passing. If a phase's acceptance criterion is not met, stop at
that phase and say so.

Ask before: touching version control while the repo is off-canonical; deleting
anything in Phase C if B4 is not green; or widening scope beyond these phases.
