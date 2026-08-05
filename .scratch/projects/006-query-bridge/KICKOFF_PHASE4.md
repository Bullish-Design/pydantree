# KICKOFF — pydantree Phase 4 (the bridge: node-schema + Product A compile-time typed extraction)

> Copy the whole contents of this file into a fresh session working in this repo.
> This is the **bridge phase** (CONCEPT §6, §7) — the experiment that decides
> **bet #2's compile-time half**: "declaring an `OutputModel` and getting
> schema-checked typed extraction is meaningfully nicer than py-tree-sitter"
> (CONCEPT §12). Phase 1 proved the model-only surface at runtime; Phase 4
> builds the node-schema that makes it checked, and generalizes the record
> value-shape map beyond JSON. Reference docs live in `.scratch/`; findings go
> in `.scratch/006-query-bridge/FINDINGS.md`.

---

## Mission

You are working in the **`pydantree`** repo. **Phases 0–3 are done and
passed.** Phase 0 proved emission + conflict remapping; Phase 1 proved Product
A's model-only surface at runtime (the `OutputModel` IS the query — no `.scm`,
no builder); Phase 2 built Product B's core machinery at full schema fidelity;
Phase 3 (`.scratch/005-grammar-glr/`) proved B's GLR-ergonomics layer and
verdict **GO on bet #1**, recommending **Phase 4 — the bridge** as the single
most important next step, with a short Phase-3A hardening pass folded into its
first sprint.

This session builds **the bridge** (CONCEPT §7): a **node-schema** derived from
the grammar, emitted by B, consumed by A, whose four jobs are (1) model↔grammar
validation beyond what the `Query()` constructor already gives for free, (2)
typed node access (assess; likely defer), (3) **value-shape derivation** — turn
spike-a2's hardcoded JSON record-shape map into a derived one that works over
any grammar, and (4) capture↔field-type cross-validation at class creation.
This is the experiment that decides **bet #2's bridge half**. Phase 1 proved
the runtime materializer; Phase 4 proves the *checked* half. Deliver a
**go / go-with-changes / no-go verdict with evidence** — an honest "the schema
adds nothing beyond `Query()`+runtime errors" is a valid, architecture-changing
result.

## Context: where we are

- **Phase 0 (done):** `.scratch/002-pydantic-treesitter/spike/` — emission +
  remapping proven.
- **Phase 1 (done):** `spike-a/`, `spike-a2/` — Product A's **model-only**
  surface (`OutputModel` IS the query) validated over Python + JSON against
  hand-computed ground truth; the emitter/materializer substrate in
  `spike-a/dsl.py` + `spike-a/materialize.py`, the model-only layer in
  `spike-a2/typed.py`. These are throwaway spikes — **port the proven layer,
  don't redesign it** (spike-a2 verdict: "proceed to Phase 4 as planned — the
  bridge is what generalizes the shape map, and treat this model-only layer as
  the Product A shape to build on, not the builder DSL").
- **Phase 2 (done):** `src/pydantree_sitter_grammar/` — full-schema IR, builder DSL, analyzer,
  native build pipeline, conflict remapping.
- **Phase 3 (done, THIS phase's foundation):** `.scratch/005-grammar-glr/` —
  the GLR-ergonomics layer (ladders, `ExpressionGrammar`, ambiguity opt-in,
  per-production conflict sites + `build_loop`), verdict **GO on bet #1**.
  Its FINDINGS §6 recommends Phase-3A hardening items to fold into the first
  sprint (see scope item 5 below), and §8: "The single most important next
  step is Phase 4 — the bridge (node-schema emission + Product A compile-time
  query checking): nothing Phase 3 surfaced blocks it."
- **`CONCEPT.md`** — §5 is the validated Product A design (model-only, post
  Phase-1); §6 is the artifact seam (the only coupling between A and B is the
  artifact: `grammar.so/.wasm + node-schema.json`); **§7 is THE bridge spec**
  (four jobs, and the community-grammar path: derive from `grammar.json` or,
  weaker, sample from the CLI's `node-types.json`); §11 risk 7 is the
  node-schema-completeness risk; §12 names bet #2.
- **`src/pydantree/`** — deprecated first-principles wrapper. **Do not touch.**

## Required reading (in this order — do not skip)

1. **`.scratch/002-pydantic-treesitter/CONCEPT.md`** — §5 (the validated
   model-only A surface — binding rules, result modes, error surface), §6
   (the artifact seam: A never imports B), **§7 (the bridge — read closely:
   the four jobs and the community-grammar derivation path)**, §8 (pydantree_sitter is
   the tiny shared package), §11 risk 7, §12 (bet #2).
2. **`spike-a2/FINDINGS.md`** — Phase 1's verdict and the adopted model-only
   design. Especially: §2.1 (the record VALUE shape map is grammar knowledge —
   THE central design fact Phase 4 must kill), §2.2 (types coerce, they don't
   filter — NodeKind and the int→numeric-kind question), §4 (the expressibility
   gaps: field-mode lists, non-JSON record shapes, descendant matching, string
   unescaping, nested-model limits), §3 (the failure-mode table — where each
   mistake surfaces today).
3. **`spike-a/FINDINGS.md`** — the 0.26 substrate facts that carry over
   unchanged. Especially §1 learned-the-hard-way (predicates inside pattern
   parens; per-match repeats — no accumulate-in-one; capture-suffix binding;
   `Query()` validates kinds/fields for free; alternation = multi-pattern;
   anchored patterns re-match per inner occurrence; duplicate capture names
   corrupt quantifiers), §3 (the nested-collision class and why it needs
   deeper anchoring), §4 (A's remaining gaps).
4. **`.scratch/005-grammar-glr/FINDINGS.md`** — Phase 3's verdict, and
   especially §6 (the Phase-3A hardening items to fold into this sprint: the
   ExpressionGrammar semantic-smoke corpus; the `cond=`/`non_call_primary`
   affordance) and §8 (recommendation).
5. **Phase-2 code you will extend (skim; base facts in the Phase-2 FINDINGS
   appendix):**
   - `src/pydantree_sitter_grammar/grammar.py` — the IR. The node-schema is derived from
     THIS (rules, fields, `AliasNode`, `inline`, hidden `_`-rules,
     `supertypes`, `start_rule`) — richer than the CLI's `node-types.json`,
     which is post-alias/post-inline flattened.
   - `src/pydantree_sitter_grammar/pipeline.py` — `BuildResult.node_types_json` (the CLI's
     byproduct, already on disk and currently unused — Phase 4's
     community-grammar path samples it).
   - `src/pydantree_sitter_grammar/expressions.py` + `builder.py` (`Ladder`) — for the
     Phase-3A hardening items.
6. **The layer to port (read before writing any pydantree_sitter code):**
   `spike-a2/typed.py` (the model-only derivation + metaclass — especially
   `_json_value_specs`, `_derive_field`, `_derive_record`), `spike-a/dsl.py`
   (the `.scm` emitter), `spike-a/materialize.py` (the materializer:
   `Span`, `AmbiguousCaptureError`, missing-capture semantics). The port is
   mechanical; the schema integration is the new work.
7. (Optional) `/tmp/tree-sitter/` CLI source — `cli/generate/src/node_types.rs`
   for exactly what `node-types.json` contains vs what the IR knows.

## The bridge in 60 seconds

```
pydantree_sitter_grammar (B) ──► grammar.json ──► node-schema.json (derived from the IR)
                                        │                     │
   community grammars ──► node-types.json (CLI byproduct) ────┘ (weaker path)
                                        ▼
   pydantree_sitter (A): Language.load(schema=…) ──► class-creation checks (jobs 1,3,4)
        OutputModel ──► derived .scm ──► validated against the schema ──► typed rows
```

The whole point is CONCEPT §7's promise: A's known **runtime** safety nets —
the hardcoded JSON shape map (`spike-a2` §2.1), `AmbiguousCaptureError` for
nested collisions (spike-a §3), `NodeKind` overrides for non-JSON shapes —
become **class-creation / `validate_with()` checks** backed by a schema derived
from the grammar. Phase 1 already gets kind/field typos free from the `Query()`
constructor; the schema must add checks *beyond* that (path validity, field-
on-kind existence, capture↔type compatibility, shape derivation) or it isn't
carrying its weight — say so plainly.

## Phase 4 scope

### Primary experiment (the go/no-go): does the bridge change the feel?

This is **bet #2's bridge half**, honest and evidence-backed. One realistic
task pair, three runs, one verdict.

**Run 1 — the pitch (B-built grammar, schema derived from the IR).** Build a
small **non-JSON config grammar** with pydantree_sitter_grammar (INI-like: sections,
`key = value`, comments, a few types — 10–15 rules; you may reuse patterns
from filtlang/qfilter but it must NOT be JSON, because the hardcoded JSON shape
map must be unable to express it). Then author `OutputModel`s in **record mode**
(section entries as order-independent records) and **field mode** (structured
statements). Bind the schema. Pipeline: B analyze → generate (ABI 15) → compile
→ load → **node-schema emitted** → A consumes it → checks active at class
creation → parse corpus → assert typed rows against hand-computed ground
truth. Record the metrics:

- where each check surfaces: **class creation / `validate_with()` / first
  `extract` / runtime loop** — the surface-layer table is the feel metric;
- record shape map: lines of `_json_value_specs`-style code that became a
  **schema lookup** vs lines that had to stay hand-written (0 hand-written is
  the goal for the common case);
- how many `NodeKind` overrides the non-JSON record task needs (spike-a2
  stand-in requires them per unmapped shape; 0 is the goal);
- whether the model surface stayed identical to spike-a2's (no new annotation
  vocabulary — the schema must be invisible when it works);
- that the derived map **reproduces the spike-a2 JSON v1 map** over
  `tree_sitter_json` (the derivation is sound, not a special case).

**Run 2 — the bite (schema catches it before text is parsed).** Plant the
failure classes that are runtime-only today, each must surface **at class
creation or `validate_with()`** with the schema entry cited (node kind, field,
supertype):

- an `int`-typed capture whose capture can only ever yield non-numeric kinds
  (the spike-a2 §2.2 question, decided by the schema);
- a `__match__` path node that cannot have the CST field a `capture("…")` uses;
- a record-mode field type with **no derivable shape** in the config grammar
  (schema says so, not `UnsupportedShapeError` at import of a hardcoded map);
- the nested-record collision class (spike-a §3): fixed by record-level
  anchoring against the schema, not flagged by `AmbiguousCaptureError` at
  extract time.

For each: record the error text, the surface layer, and that no text was
parsed. Raw outputs saved verbatim to evidence.

**Run 3 — the honest control.** The same two tasks through the Phase-1
stand-ins (no schema): hardcoded JSON shape map (cannot express the non-JSON
record task at all — that is the point), `NodeKind` overrides per field,
`Query()`-constructor typos as the free baseline, runtime
`ValidationError`/`AmbiguousCaptureError`. Compare surface layers and author
effort. **If Run 1's schema checks are a subset of what `Query()` + runtime
errors already catch, that is a no-go signal** — say so plainly.

**Verdict framing (be explicit):** Phase 4 proves the bridge's promise — checks
moved to class creation and the shape map generalized — or it doesn't. A
no-go means the schema format/derivation is wrong or the jobs were already
free, not that the machinery failed. Phase 3's GO must NOT rubber-stamp this.

### Supporting surface (the Phase-4 build)

1. **pydantree_sitter — the shared node-schema (keep it ONE small module, no more):**
   `src/pydantree_sitter/schema.py` — Pydantic models mirroring `node-types.json`'s
   per-type shape (`{type, named, fields {name: {multiple, required, types}},
   children {multiple, required, types}, subtypes?}`) plus a canonical
   serialization, and TWO derivation functions converging on that format:
   - `derive_from_ir(GrammarModel)` — the exact path: walks the IR's rules,
     `FieldNode`s, `AliasNode`s (aliased names!), hidden rules, `inline`
     list, `supertypes` list, `start_rule`. Richer than the CLI byproduct
     (which is post-alias/post-inline flattened — the `tuple` alias and
     hidden `_*` rules only exist here).
   - `derive_from_node_types(node_types_json)` — the weaker community path
     (sample from the CLI's byproduct; supertypes arrive as `subtypes`
     entries; aliases/inline are already flattened away).
   Wire `src/pydantree_sitter` into `pyproject.toml`'s wheel packages list. pydantree_sitter_grammar
   and pydantree_sitter both import it; **A still never imports B**.
2. **B side:** `pydantree_sitter_grammar.pipeline.build()` emits `node-schema.json` alongside
   `grammar.json` in the `BuildResult` (derived from the IR via
   `derive_from_ir`), so a B-built grammar ships the exact schema. Do not
   redesign the pipeline — one byproduct + a field on `BuildResult`.
3. **A side — port + integrate (`src/pydantree_sitter/`, the first real Product A
   package):**
   - port `spike-a2/typed.py` + the `spike-a` emitter/materializer substrate
     mechanically into `src/pydantree_sitter/` (same surface: `OutputModel`,
     `__match__ = M(…)`, `capture()`, `source_meta()`, `Matches`/`Eq`/`AnyOf`/
     `NodeKind`, strict/lenient, `validate_with`, `extract`). Keep the tests
     green before any schema code lands (port-first discipline).
   - **Job 1 — model↔grammar validation** sharpened: beyond the free
     `Query()` typos, check at `validate_with(language, schema=…)` (and at
     class creation when a schema is bound): the `__match__` ancestor chain is
     a *possible* descent in the schema; every capture's CST field exists on
     its node kind; the anchor can produce the matched node.
   - **Job 3 — value-shape derivation:** replace `_json_value_specs` with a
     `shape_for(field_type, schema)` lookup: for a record-mode field type,
     find the grammar's node kind(s) that (a) coerce to the Python type and
     (b) occur as a value under the record's key node — derived, not
     hardcoded; `NodeKind` stays as the typed override. Must reproduce the
     JSON v1 map over `tree_sitter_json` and express the config grammar.
   - **Job 4 — capture↔type cross-validation:** at class creation with a
     schema, compare a capture's possible node kinds against the field's
     Python type (numeric kinds ↔ int/float, etc.) and flag mismatches (the
     spike-a2 §2.2 question).
   - **record-level anchoring** (spike-a §3 fix): scope inner record queries
     against the schema so nested pairs can't collide with record-level keys.
   - **Job 2 — typed node access / `.pyi` stubs:** assess only. Note what it
     would take and whether it's worth it; do not build it in this phase.
   - `Language.load(..., schema=…)`: accept a `node-schema.json` path/dict,
     or auto-derive from the grammar's `node-types.json` when none is given
     (community path). A's `_resolve_language` may grow a small registry so
     `validate_with`/`extract` can find the schema.
4. **Phase-3A hardening (fold into the first sprint, small — from Phase-3
   FINDINGS §6):**
   - **ExpressionGrammar semantic-smoke:** a helper that emits + runs a small
     default precedence corpus (the probe-2 table: `-a^b → -(a^b)`,
     `-f(x) → -(f(x))`, `a.b.c`, `f(x)(y)`, `-a or b`) against the built
     grammar and asserts the CST shapes, so a wrong ladder order is caught at
     author time, not in the field. (The helper cannot verify intent — this is
     the systematic guard for the Phase-3 §4 leak.)
   - **`cond=`/`non_call_primary` affordance:** a typed spelling for the
     postfix×bare-cond-`if` interaction (Phase-3 FINDINGS §4.2) — e.g. an
     `expression(..., cond=...)` option or a `primary_without_call` knob the
     ladder uses for condition operands, so the documented parens-cond pattern
     has a declarative form instead of a documentation note.
5. **Cheap checks (trivial only):** every emitted grammar generates with exit
   0; `derive_from_ir` ↔ `derive_from_node_types` agree on the shared subset
   (field-bearing kinds, supertype `subtypes`) for the same grammar; each Run-2
   planted failure cites the schema entry + the model's `file:lineno`.

## Out of scope — say no to these (politely)

- **wasm distribution, wheel/package splitting beyond the one `src/pydantree_sitter`
  module, corpus-testing harness (Phase 5), incremental-reparse wrappers,
  performance work.** The `.pyi` stubs (Job 2) are assessed, not built.
- **New Product A surface.** The model-only surface is frozen as spike-a2
  validated it; Phase 4 adds *checks*, not new user-facing vocabulary. If a
  Run-1 metric forces a surface change (a new marker, a schema-aware
  annotation), treat it as a go-with-changes finding, not a license to expand.
- **B-side ergonomics beyond the Phase-3A items.** No new ladder features, no
  scanner library, no regex-subset validator (still noted, not built).
- **JSON string unescaping, descendant `...` matching, field-mode lists**
  (spike-a2 §4 gaps 2/4/5): note what the schema makes possible, don't build.
- **Ergonomics claims beyond the experiment.** Run 1's metrics are evidence,
  not marketing; if the checks don't surface earlier or the shape map doesn't
  generalize, say so.

## Environment setup (do this first)

1. `devenv shell` — works (fixed in Phase 0). If it isn't, tell the user
   immediately.
2. **Verified facts (don't re-derive):** tree-sitter CLI 0.25.3, bindings
   0.26.0 (`LANGUAGE_VERSION=15`, `MIN_COMPATIBLE=13`), pydantic 2.13.4, gcc
   14.2.1. ABI 15 via `tree-sitter.json`; conflicts = exit 1, first-only,
   `--json` on stderr; load via PyCapsule `tree_sitter.Language`. All in
   `src/pydantree_sitter_grammar/pipeline.py` + Phase-2 FINDINGS appendix.
3. **Wheels:** `tree-sitter-python` and `tree-sitter-json` are installed in the
   devenv venv (the Run-3 control and the JSON-map-reproduction check need
   them). `import pydantree_sitter_grammar` works (editable install); the spike-a2 layer runs
   via a sys.path shim — the port into `src/pydantree_sitter/` removes that shim.
4. **The CLI's `node-types.json` byproduct** is already produced by every
   `pydantree_sitter_grammar` build (see `BuildResult.node_types_json`); Phase 3 left it on
   disk unused. Its exact per-type shape (fields/children/subtypes) is in the
   appendix below.
5. **Before writing helpers:** re-run Phase 3's `experiment_phase3.py` (or at
   least its Run 1) so the B pipeline is warm, and re-run `spike-a2/main.py`
   so the model-only surface + the JSON shape map are fresh. Then hand-write
   Run 1's config grammar and its ground-truth corpus on paper before coding
   the schema derivation (the "hand-written first" discipline, repeated at the
   schema level).

## Working agreement

- **Commit after each meaningful step** (e.g.
  `pydantree_sitter: node-schema models + derive_from_ir (exact) and derive_from_node_types (community) converge`,
  `pydantree_sitter_grammar: build() emits node-schema.json alongside grammar.json`,
  `pydantree_sitter: port spike-a2 model-only layer (surface frozen, tests green)`,
  `pydantree_sitter: schema jobs 1+4 — model↔grammar and capture↔type checks at class creation`,
  `pydantree_sitter: job 3 — derived record value-shape map replaces the hardcoded JSON map`,
  `pydantree_sitter: record-level anchoring kills the nested-collision class`,
  `pydantree_sitter_grammar: Phase-3A — ExpressionGrammar semantic-smoke corpus + cond=/non_call_primary`,
  `phase4: experiment — bet #2 bridge verdict, evidence captured`).
- **Write findings as you go** into `.scratch/006-query-bridge/FINDINGS.md`.
  The code is the foundation; the findings are the deliverable.
- **Don't gold-plate.** 80%-done steps get a note and a move-on.
- **Don't fake the primary experiment.** Run 1's corpus, Run 2's planted
  failures, and Run 3's control must be real, CLI-validated, and
  ground-truthed by hand. Save raw outputs verbatim under
  `.scratch/006-query-bridge/evidence/`.
- **Ask before expanding scope** beyond this brief.

## Deliverables (end of session)

1. Working Phase-4 extensions, all committed:
   - `src/pydantree_sitter/schema.py` (node-schema models + both derivation paths,
     wired into the wheel packages);
   - `src/pydantree_sitter_grammar/` emits `node-schema.json` in `BuildResult`;
   - `src/pydantree_sitter/` — the ported model-only layer with Jobs 1, 3, 4, and
     record-level anchoring;
   - the Phase-3A hardening items (semantic-smoke corpus,
     `cond=`/`non_call_primary`);
   - pytest tests covering the schema round-trip, the derivation agreement
     check, each Run-2 failure class surfacing at class creation, and the
     port's surface staying green.
2. Demonstrated, with evidence:
   - (a) Run 1: config grammar → B build → node-schema → A model-only models
     → checks at class creation → correct typed rows vs hand-computed ground
     truth, with the surface-layer table and the shape-map metric;
   - (b) Run 2: each planted failure surfaces at class creation/`validate_with`
     citing the schema entry, no text parsed;
   - (c) Run 3: the Phase-1 stand-in control, with the comparison table.
3. `.scratch/006-query-bridge/FINDINGS.md` answering at minimum:
   - Does the bridge **change the feel** (the bet-#2 question)? Where do the
     schema checks leak (what still needs runtime errors, what stays
     hand-written)?
   - Which §7 jobs landed and which didn't (and what that says about the
     bridge as specced)?
   - What does the **full Product A + B** still need (gaps vs §5/§7) — and is
     any of it a blocker for Phase 5 (corpus harness, distribution)?
   - Re-assess **§11 risk 7** (node-schema completeness) from the
     derivation-side evidence, plus anything Phase 4 surfaced.
   - **Recommendation:** go / go-with-changes / no-go on the bridge, and the
     single most important next step (Phase 5 — polish & reach — or a
     Phase-4A hardening pass, or a rethink).
4. Everything committed and pushed.

## Appendix — durable facts Phase 4 builds on (all from prior phases, verified)

1. **Product A's surface is frozen as spike-a2 validated it**: `OutputModel`
   + `__match__ = M("a", "b", "c", record=True)` + `capture()` /
   `source_meta()` / `Matches`/`Eq`/`AnyOf`/`NodeKind`; pydantic type =
   coercion + optionality + list; class-creation derivation via a
   `ModelMetaclass` (`model_fields` is available there, not in
   `__init_subclass__`).
2. **The record VALUE shape map is grammar knowledge** (spike-a2 §2.1): "a
   JSON `str` is `string_content` inside `string`" is not logic. The
   hardcoded `_json_value_specs` is the thing to kill; `NodeKind` is the typed
   override that must remain.
3. **The 0.26 substrate** (spike-a §1, all probed): predicates must be inside
   the pattern's parens; quantified sub-patterns yield one match per
   occurrence (no accumulate-in-one) — list materialization = record-merge by
   an anchored ancestor; a capture suffix binds to the node whose `)` it
   follows; `Query()` validates node kinds and field names for free
   (kind/field typos are NOT the schema's job); alternation = multiple
   top-level patterns; anchored patterns re-match per inner occurrence;
   duplicate capture names corrupt quantifiers.
4. **The nested-collision class** (spike-a §3): scoped sub-queries can't
   distinguish record-level from nested pairs (`{"meta": {"name": …}}`)
   without deeper anchoring; `AmbiguousCaptureError` is the runtime
   safety net today; the schema + record-level anchoring is the fix.
5. **`node-types.json` (the CLI byproduct, community path):** a list of
   `{type, named}`, plus per-type `fields: {name: {multiple, required,
   types: [{type, named}]}}`, `children: {multiple, required, types}` (only on
   node kinds that have children), and `subtypes: [{type, named}]` on
   supertype nodes. It is post-alias/post-inline **flattened** — hidden `_*`
   rules and `alias` names do NOT appear; the IR does know them (the exact
   path).
6. **The IR (exact path):** `GrammarModel` has `rules` (first = start;
   `start_rule`), `FieldNode`s inside bodies, `AliasNode{value, named}`,
   `inline` list, `supertypes` list, hidden rules as `_`-prefixed names. This
   is what `derive_from_ir` walks; the supertype `subtypes` relation is
   declared, not inferred.
7. **B's pipeline facts** (Phase-2/3 appendix): start = first rule; unused
   rules silently pruned; non-start rules must not be nullable; `alias` wraps
   a single hidden symbol; named precedence ladders are descending (first =
   highest); ABI 15 via `tree-sitter.json`; generate is sub-second →
   fix-one-rerun viable; `BuildResult.node_types_json` is already on disk.
8. **Phase-3 facts relevant to the hardening items:** postfix must OUTRANK
   the unary in the ladder (postfix-below-unary parses `-f(x)` as `(-f)(x)`
   silently — generate clean, semantically wrong); `-a ^ b → -(a^b)` needs
   unary BELOW pow; expr-callee calls + bare-cond `if <expr>` conflict — real
   grammars parens-delimit. These exact cases are the semantic-smoke corpus's
   seeds.
9. **Package layout today:** `pyproject.toml` wheel packages =
   `["src/pydantree", "src/examples", "data", "src/pydantree_sitter_grammar"]`; Phase 4 adds
   `src/pydantree_sitter` and `src/pydantree_sitter`. `pydantree_sitter_grammar` is editable-installed;
   `import pydantree_sitter_grammar` works in the devenv venv.
