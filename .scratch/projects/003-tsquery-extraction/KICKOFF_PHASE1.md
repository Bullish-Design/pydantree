# KICKOFF — pydantree Phase 1 spike (Product A: typed extraction over community grammars)

> **STATUS: COMPLETE — superseded direction.** This brief scoped Product A as a
> "query DSL → `.scm`" surface. The spike ran it (spike-a) and then rejected
> that surface in favor of **model-only extraction** (spike-a2): the
> `OutputModel` class IS the query; no `.scm`, no builder, no query string.
> The mission text below is preserved as the historical brief. The adopted
> design and evidence: `spike-a2/FINDINGS.md` (repo root), and the updated
> product definition in `.scratch/002-pydantic-treesitter/CONCEPT.md` §5.

## Mission

You are working in the **`pydantree`** repo. **Phase 0 is done and passed** —
the emission pipeline (`grammar.json`-first) and the conflict→Python-source
remapping are proven feasible (verdict: GO). This session runs the **Phase 1
spike** defined in the concept: proving **Product A (`pydantree_sitter`)** — a Pydantic
query DSL that maps captured tree-sitter nodes into typed `OutputModel`
instances, working over **prebuilt community grammars with zero dependency on
Product B**.

Deliver a **go / go-with-changes / no-go verdict with evidence**, following the
Phase-0 discipline: one high-risk question, an honest experiment, findings over
code, everything committed.

## Context: where we are

- **Phase 0 (done, committed):** `.scratch/002-pydantic-treesitter/spike/` proved Product B's core mechanics —
  Pydantic GrammarModel IR → `grammar.json` → `tree-sitter generate` → gcc →
  `.so` → parse, plus conflict remapping via `tree-sitter generate --json`.
  Read `.scratch/002-pydantic-treesitter/spike/FINDINGS.md` for the verdict and the **durable technical facts**
  below. The `.scratch/002-pydantic-treesitter/spike/` code is throwaway — reference it for patterns, don't
  extend it.
- **Concept:** `.scratch/002-pydantic-treesitter/CONCEPT.md`. Product A is §5;
  the two-product design, artifact boundary, sequencing, and risks are §0–§12.
  The concept's **bet #2** (the one Phase 1 must test): *"capture→OutputModel
  with schema-checked queries is meaningfully nicer than py-tree-sitter."*
- **Product B is de-risked and waiting** (Phases 2–3). Phase 1 does not touch
  it — you only *consume* wheels.
- The repo's `src/pydantree/` is the deprecated first-principles wrapper —
  skim only if you want to know what not to do.

## Required reading (in this order — do not skip)

1. **`.scratch/002-pydantic-treesitter/CONCEPT.md`** — full read, but focus on
   §5 (Product A: loading, query DSL, materialization, result modes, error
   surface), §6 (the artifact boundary), §9 (sequencing), §11 (risks), §12
   (bottom line: the two bets).
2. **`.scratch/002-pydantic-treesitter/spike/FINDINGS.md`** — Phase 0's verdict and the durable technical facts
   (toolchain versions, ABI, loading path). Some facts carry into Phase 1.
3. **`.scratch/002-pydantic-treesitter/spike/main.py` + `.scratch/002-pydantic-treesitter/spike/pipeline.py`** — skim. The **PyCapsule loading
   pattern** and the staged-test discipline are the carry-over; the grammar IR
   and builder are not (they're Product B's).
4. **The installed API ground truth** (do not trust docs from memory):
   - `.devenv/state/venv/lib/python3.13/site-packages/tree_sitter/__init__.pyi`
     — the 0.26 `Query`/`QueryCursor`/`Node`/`Tree` surfaces.
   - `.../site-packages/tree_sitter_python/__init__.pyi` + `__init__.py` —
     the wheel's loading surface.
5. (Optional) `.scratch/001-pydantic-winnow-parser/sketch.py` — the
   compile-time grammar↔output bridge-validation *style* (§4.7/§7 of the
   concept); the full bridge is Phase 4, but the type-compatibility thinking
   informs the Phase-1 capture↔model binding checks.

## The concept in 60 seconds (Product A)

Any grammar that already exists (a community wheel, or one built by B later)
can be consumed through a typed lens:

```
text ──► load grammar (wheel .so) ──► parse (C runtime) ──► CST
   ──► Query DSL ──► .scm ──► Query ──► captures ──► OutputModel (Pydantic)
```

- **Query DSL → `.scm`**: `node("assignment").child(field="left", capture="name")`
  compiles to a real tree-sitter S-expression query; predicates (`#eq?`,
  `#match?`, `#any-of?`) become typed calls.
- **Capture → `OutputModel`**: Pydantic models with coercion from node text,
  optional/missing captures, repeated captures → `list`, nested models from
  sub-queries, source-span injection.
- **Result modes**: lazy CST cursor (default), typed materialization (opt-in),
  validate/recognize (does it parse cleanly?).
- **Zero dependency on Product B.** A is the thing that ships standalone value
  first.

The whole value proposition rests on **bet #2**: doing the above through the
DSL must be *meaningfully nicer* than calling `py-tree-sitter` directly
(raw `Query` + manual byte-range slicing + manual `int()`/coercion + manual
glue). That niceness is what Phase 1 must measure honestly.

## Spike scope — Phase 1

### Primary experiment (the go/no-go): is the DSL → OutputModel path meaningfully nicer than raw py-tree-sitter?

This is an ergonomics bet, so the evidence must be a **head-to-head, same-task
comparison**, not vibes:

1. Build the DSL + materializer (below).
2. Pick **two real extraction tasks** (one per target grammar, see §pipeline)
   with enough shape to hurt: repeated captures, optional fields, nested
   models, primitives needing coercion, at least one `#match?`-style predicate.
3. Implement each task **three ways, side by side in the findings**:
   - **(a) raw py-tree-sitter** — hand-written `.scm`, `QueryCursor`,
     manual `node.text` slicing, manual `int()`/enum/str coercion, manual
     grouping of repeated captures, manual "is this capture present?" checks.
   - **(b) the DSL, lazy mode** — same extraction, cursor-first, no model
     construction.
   - **(c) the DSL, typed mode** — `q.extract(tree, into=Model)`.
4. Compare honestly and measurably:
   - **Code shape**: lines, nesting, how much is glue vs. intent.
   - **Failure modes**: typo a node kind / field name / capture name; declare a
     field `int` fed from a capture that yields text. Where does each approach
     surface the error? (Build-time `Query()` rejection? Silent empty match at
     runtime? `ValidationError` at the end? Crash?)
   - **Robustness**: missing captures, extra captures, malformed input.
5. **Verdict, honestly:** is bet #2 real? A negative result is valid — if raw
   py-tree-sitter turns out to be "fine" and the DSL adds ceremony without
   clarity, that changes Product A's design (maybe the DSL should be thinner,
   or the materializer should be the whole product).

### Supporting pipeline (must work end-to-end)

1. **Query DSL → `.scm` emitter.** Enough surface for the tasks:
   `node(type)`, `.child(field=..., capture=...)`, `.child(node=...)`,
   `.where(cap.matches(re))` / `.eq(str)` / `.any_of(...)`, and at least the
   basics of alternation and anchored (`(module ...) @root`) patterns. The
   emitted `.scm` must be accepted by the real `tree_sitter.Query` constructor
   — that constructor is the cheapest validator you have.
2. **Capture → `OutputModel` materialization** (concept §5.4):
   - text slicing from `node.byte_range`,
   - primitive coercion (`int`/`float`/`bool`/`str`), enum lookup,
   - `Optional`/missing captures,
   - repeated captures → `list`,
   - nested `OutputModel`s from sub-queries,
   - `source_meta()` span/position injection,
   - Pydantic `ValidationError` at the end for malformed captures.
   Use `Query.capture_quantifier()` to know whether a capture is optional or
   repeated — it exists in 0.26 and is the right hook.
3. **Result modes** (concept §5.5): lazy cursor (default), typed
   `extract(..., into=Model)` (opt-in), and a minimal `validate()` that reports
   parse-cleanliness. Do NOT build the full streaming/visitor mode.
4. **Targets — two grammars with real shape contrast:**
   - **Python** — `tree-sitter-python` (installed; `tree_sitter_python.language()`).
     Extraction task: collect module-level assignments as
     `Assignment(name: str, value: int, line: int)` — stresses repeated
     captures, coercion, span injection, and keyword/identifier-shaped text.
   - **JSON** — add `tree-sitter-json` via uv (not installed yet).
     Extraction task: pull a `{name, age, tags[]}` record — stresses nested
     models, `list` from repeated captures, `Optional` fields, and a
     `#match?`-style predicate on keys or values.
   Parse a *real-looking* sample for each (a few dozen lines), not toy one-liners.
5. **CST fidelity check**: for at least one task, assert the extracted values
   match ground truth you computed by hand (not just "it didn't crash").

### Cheap checks (trivial only)

- **DSL→`.scm` acceptance**: every emitted query string must construct a real
  `Query` (build-time rejection is the point).
- **Name sanity within the DSL**: capture names and field names used in the DSL
  must appear in the emitted `.scm` (catches DSL bugs, not grammar typos).
- **Capture↔field type hints at binding time**: if a capture yields text and
  the `OutputModel` field is `int` with no coercion path, warn *before* parsing
  (the sketch.py bridge idea, minimal version — NOT the Phase-4 node-schema
  version; no grammar introspection).

## Out of scope — say no to these (politely)

- The **node-schema bridge** / compile-time query validation against the
  grammar / typed node accessors (**Phase 4**). The capture↔field type hints
  above are the Phase-1 stand-in; do not derive or emit node-schemas.
- **Product B / pydantree_sitter_grammar** anything (**Phases 2–3**): no grammar emission, no
  conflict tooling, no ExpressionGrammar. You consume wheels only.
- wasm, packaging/wheels, external scanners, the streaming/visitor result
  mode, the full incremental-reparse API (**Phase 5**) — note incremental
  reparse exists in 0.26 (`Tree.edit`/`Parser.parse(old_tree=...)`), don't
  build a wrapper.
- Package renaming/splitting (`pydantree_sitter`/`pydantree_sitter`/`pydantree_sitter_grammar`). Distribution is
  a later decision.
- Performance work of any kind.

## Environment setup (do this first)

1. `devenv shell` — already works (fixed in Phase 0). If it isn't working,
   tell the user immediately rather than fighting it.
2. **Verified facts from Phase 0 (don't re-derive):**
   - Python bindings: **tree-sitter 0.26.0** (`LANGUAGE_VERSION=15`,
     `MIN_COMPATIBLE=13`). pydantic **2.13.4**.
   - **0.26 API changes vs. old tutorials:** `Language(ptr)` takes a
     `PyCapsule` named `"tree_sitter.Language"` (int pointers are deprecated).
     Community wheels like `tree-sitter-python` hand you the capsule directly:
     `tree_sitter.Language(tree_sitter_python.language())` — verified working,
     `abi=15`, no manual ctypes needed.
   - **`QueryCursor.captures(node)` returns `dict[str, list[Node]]` grouped by
     capture name** (verified) — NOT the old per-capture iterator. `matches()`
     returns `list[(pattern_index, dict)]`. `Query.capture_quantifier(pi, ci)`
     returns `""|"?"|"*"|"+"`. This API is *friendlier* to materialization than
     the concept assumed — confirm against the installed `.pyi`.
   - `Node.text` is `bytes | None`; spans via `node.byte_range` and `node.range`.
   - The tree-sitter CLI is installed but **not needed** for Phase 1 — ignore it.
3. Add `tree-sitter-json` (or your second target) to dev deps:
   `devenv shell -- uv pip install tree-sitter-json` (+ add to `pyproject.toml`
   dev extras if you want it durable).
4. **Before writing DSL code**, hand-write one `.scm` query, run it through
   the 0.26 `Query` API over a `tree-sitter-python` parse, and print the
   captures — validates your API assumptions cheaply (this is the Phase-0
   "hand-written grammar.json first" move, repeated).

## Working agreement

- **Spike code goes in `spike-a/`** at the repo root — isolated from
  `.scratch/002-pydantic-treesitter/spike/` (Phase 0) and `src/`. Reference docs
  stay in `.scratch/`; the Phase-0 evidence stays untouched where it is.
- **Commit after each meaningful step**, with clear messages (e.g.
  `spike-a: query DSL emits .scm accepted by Query()`,
  `spike-a: captures materialize into OutputModels`).
- **Write findings as you go** into `spike-a/FINDINGS.md`. The code is
  throwaway; the findings are the deliverable.
- **Don't gold-plate.** If a step is 80% done and the remaining 20% is polish,
  note it and move on.
- **Don't fake the primary experiment.** The three-way comparison must be
  written honestly, warts included (show the raw-py version even when it's
  ugly, and say when the DSL version is ALSO ugly).
- **Ask before expanding scope** beyond this brief.

## Deliverables (end of session)

1. Working code in `spike-a/`: DSL → `.scm` → `Query` → captures →
   `OutputModel`, over **Python and JSON**, with the three-way comparison
   implemented and runnable.
2. `spike-a/FINDINGS.md` answering at minimum:
   - Is the **0.26 Query API adequate** for the materialization model
     (repeated captures, nested patterns, predicates, quantifiers)? What had to
     be learned/fixed vs. the concept's assumptions?
   - **Is the DSL meaningfully nicer than raw py-tree-sitter?** Include the
     side-by-side code and the failure-mode comparison. Where does it break
     down or add ceremony without value?
   - What does the **full Product A query DSL + materializer** need (gaps vs.
     §5) — which DSL operators are missing, which materialization features are
     hard, what the diagnostics surface should be?
   - Re-assess **§11 risks** with what you now know (risk 1 is retired by
     Phase 0; how do 2, 4, and 7 look from the consumption side?).
   - **Recommendation:** go / go-with-changes / no-go, and the single most
     important next step (is it Phase 2, or a Phase-1A hardening pass?).
3. Everything committed.
