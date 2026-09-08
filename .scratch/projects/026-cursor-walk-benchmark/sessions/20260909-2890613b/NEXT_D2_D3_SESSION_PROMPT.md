# Kickoff prompt — pydantree Phases D2 and D3

Paste everything below the line into a clean new session.

---

You are working in `/home/andrew/Documents/Projects/pydantree`.

Execute **Phase D2, then Phase D3** of the cursor-walk benchmark plan. Work
phase by phase. Do not start D3 until D2 is green and reported. Earlier phases
(A, B, C, and D1) are complete in the repository; verify that fact from the
files and tests before changing code. Do not repeat the earlier investigation
or re-open decisions that the evidence already settled.

## 1. Read first

Read these files completely before taking task action:

- `AGENTS.md` (also exposed as `CLAUDE.md`)
- `.agents/skills/my-ai/SKILL.md`
- `.agents/skills/gitman/SKILL.md`
- `.agents/skills/pydantree-dev/SKILL.md`
- `.agents/skills/pydantree-extraction/SKILL.md`
- `docs/architecture.md`
- `docs/development.md`
- `.scratch/projects/002-pydantic-treesitter/CONCEPT.md`
- `.scratch/projects/009-phase7/FINDINGS.md`
- `.scratch/projects/026-cursor-walk-benchmark/sessions/20260909-2890613b/NEXT_SESSION_PROMPT.md`
- `.scratch/projects/026-cursor-walk-benchmark/sessions/20260909-2890613b/REPORT.md`
- this prompt

Then inspect the current implementations and tests:

- `src/pydantree_sitter/pattern.py`
- `src/pydantree_sitter/agreement.py`
- `src/pydantree_sitter/grammar.py`
- `src/pydantree_sitter/syntax.py`
- `src/pydantree_sitter/find.py`
- `src/pydantree_sitter/nodes.py`
- `src/pydantree_sitter/raw.py`
- `src/pydantree_sitter/__init__.py`
- `tests/test_astgrep_bundle.py`
- `tests/test_find_cache.py`
- `tests/test_selector_equivalence.py`
- `tests/test_lazy_nodes.py`
- relevant rule, grammar, and documentation tests found with `rg`

Use the durable evidence copy only if the session directory is missing:

`/home/andrew/pydantree-evidence-026-20260909-2890613b/`

The old probes in `probes/` are historical evidence. After Phase C, generated
query rendering was removed. Do not reintroduce `query_source`, `_query_walk`,
or `emit.py` merely to make an old probe run. Use the current `bench.py`, the
permanent selector-equivalence test, and new focused probes when evidence is
needed.

## 2. Working rules

- Run every project command inside `devenv shell`.
- Prefer the documented batched form:
  `devenv shell --no-tui --no-reload -- bash -c '...'`.
- Use `rg` or `rg --files` for repository searches.
- Use `apply_patch` for source, test, documentation, and evidence-file edits.
- Write in Simplified Technical English: short sentences, active voice, one
  term per idea.
- Preserve the Product A/Product B boundary and the schema-backed typed-node
  model.
- Keep `raw.py`, `__raw_query__`, `Query`, `Cursor`, `MatchView`, and raw
  capture support. Raw queries remain the escape hatch for sibling order,
  negation, and multi-anchor joins.
- Keep `SyntaxCheck`. It is a safety net, not a replacement for tree-sitter.
- Do not silently guess a node when an ast-grep range or kind cannot resolve.
- Do not write files from the library rewrite API. Return edit data and new
  source; the caller decides whether to persist it.
- Do not broaden this task into a new parser, a new grammar DSL, or a general
  refactor.

### Version control

Route **all** version control through gitman. Never run raw `git` or `jj`.
gitman is not on the devenv PATH; use:

`/home/andrew/.local/share/repoman/venv/bin/gitman`

Check status before any VCS mutation. If status is canonical, make a focused
lane for this work. If it is off-canonical, stop and report the exact status;
do not run `gitman reconcile --abandon`, and do not repair another session's
lane without explicit user direction.

Use gitman `save`, `sync`, `publish`, `land`, and `push` according to its skill.
Do not land or push `main` from this clean implementation session unless the
user separately requests that handoff. Keep unrelated existing changes in
place and inspect the commit scope before saving.

Exit codes are part of the project contract:

- `0`: success
- `1`: finding or decision that needs handling
- `2`: infrastructure failure
- `3`: usage error

## 3. Verified baseline and decisions

The 2026-09-09 investigation ran on real files in Python, Bash, Nix, Rust,
and Markdown. Its measured environment was Python 3.13.5, tree-sitter
bindings 0.26.0, tree-sitter CLI 0.25.3, pydantic 2.11.1, and ast-grep-py
0.45.3.

The important conclusions are fixed:

1. A cursor/tree-cursor walk was identical to the existing recursive walk:
   zero mismatches in 1326 cases. Do not spend D2/D3 effort on cursor-walk
   optimisation.
2. The generated query path was not equivalent to the walk path. Phase C
   therefore removed generated query rendering, `_query_walk`, and
   `src/pydantree_sitter/emit.py` after Phase B made selector semantics
   authoritative. Raw query support remains.
3. Phase A added compiled-query caching for raw queries, keyed by class and
   language, including cached `QueryBuildError` failures.
4. Phase B defined filter semantics. A declaration that does not fit a node is
   a non-match. It is not an extraction error. Genuine malformed source or
   codec failures remain errors.
5. Phase D1 made direct nested `Node` fields lazy and cached. Scalar fields,
   `span`, and `__value__` remain eager. Serialization materialises the lazy
   tree. A failure in one nested field is local and cached.
6. D1 measured Python `ClassDefinition` on the large corpus at 14 matches:
   lazy anchor discovery plus anchor materialisation was 24.693 ms total,
   about 1.764 ms per match. The old fully materialised path was about 3941.5
   ms total, about 281.5 ms per match. The reduction was about 85.8x for this
   case. The exact logs and gates are in the session `evidence/` directory.
7. D1 completed with `369 passed, 1 xfailed`; the warnings-as-errors suite,
   Ruff, ty, documentation snippets, and all four maintained examples also
   passed. Re-run the gates in the current checkout instead of trusting this
   summary if the repository changed.

The ast-grep seam repaired in Phase A is also fixed:

- `Grammar` has `metadata`, `astgrep_name`, `astgrep_is_bundle`, and
  `register_astgrep()` for grammars loaded from a bundle.
- Bundle metadata supplies the shared-library artifact, export symbol,
  registration name, extensions, and `meta_var_char` where present.
- `register_bundle_languages()` is the collection point for several dynamic
  languages because ast-grep-py accepts dynamic-language registration only in
  its first registration call.
- Registration is process-global. Identical re-registration is idempotent;
  conflicting re-registration raises a `PatternBuildError` instead of
  silently rebinding an existing language.
- A Nix grammar whose metavariable sigil is `$` produces no useful matches
  because `$` is not an identifier in that grammar. The custom `_` sigil
  works. Never hide this constraint behind a fallback.
- When a bundle is registered, ast-grep and pydantree load the same `.so`.
  Agreement is then by construction. Do not perform a second-parser corpus
  measurement for that bundle path just to manufacture a digest.

## 4. Phase D2 — promote `Pattern`, reduce `agreement.py`

### Objective

Make ast-grep the documented expressive front end for structural search:

```python
pattern = Pattern(rule_or_text, language=grammar)
matches = pattern.find_all(source)
typed_rows = matches[0].extract(TypedClass)
```

The engine finds. `PatternMatch.extract(TypedClass)` resolves through the same
typed `Grammar.parse(source)` tree and returns exact pydantree nodes. Do not
create a second typed-node representation and do not resolve by nearest,
smallest, or enclosing range.

### D2.1 Map the existing public boundary

Before editing, search all imports and call sites for:

`Pattern`, `PatternMatch`, `Edit`, `ReplaceResult`, `GrammarAgreement`,
`agreement_for`, `measure_agreement`, and `char_to_byte_table`.

Record which are public, which are test-only, and which are dead. Inspect the
current `pydantree_sitter.pattern.__all__` and top-level package exports. Make
the public API decision explicit in the report. If `Pattern` and its match
types become top-level exports, add the exports, documentation, and tests as
one change. If they remain module-level, document the stable import path and
why.

Do not remove `char_to_byte_table`: ast-grep reports character offsets and the
runtime uses UTF-8 byte offsets. Build one conversion table per parse and
test non-ASCII source.

### D2.2 Bundle-first binding

Use the repaired bundle seam as the preferred path:

1. Load a real fixture bundle with `Grammar.load_bundle`.
2. Register it through `Grammar.register_astgrep()` or the documented batch
   collection point before constructing a `Pattern`.
3. Construct `Pattern(Rule(...), language=grammar)` without a caller-supplied
   `astgrep_name`.
4. Search source and call `PatternMatch.extract(TypedClass)`.
5. Assert exact match count, class, field values, and UTF-8 byte spans.
6. Assert the agreement/provenance result identifies the same-artifact path,
   if that result remains part of the public match record.

Keep process-global registration visible in the API and errors. Do not make a
second dynamic-language registration call appear reliable when the engine
rejects it. Test both a successful batch registration and the error for a
late or conflicting registration. Test custom metavariable sigils and
metadata-derived language symbols/extensions.

The registration API must not make a bundle Pattern depend on ast-grep's
vendored grammar. The bundle `.so` is the source of truth for both sides.

### D2.3 Wheel-grammar compatibility

Retain and test the wheel-grammar path for languages that have an installed
ast-grep grammar, especially Python. It may continue to use the recorded
`GrammarAgreement` data and version checks. Do not claim same-artifact
agreement for this path.

Use repository search before deleting anything from `agreement.py`:

- `GrammarAgreement` and `agreement_for` may still be needed for the wheel
  grammar path and for `PatternMatch.agreement`/rewrite records.
- `measure_agreement` is a regeneration/evidence helper, not a bundle bind
  requirement. Retire it only if no supported path or test uses it, and then
  remove its exports, stale documentation, and stale tests together.
- Keep only code that has a live caller or a deliberate evidence/regeneration
  role. Do not leave a dead two-grammar story in the user-facing docs.

If the final design needs a smaller provenance type instead of
`GrammarAgreement`, define the invariant and update all record consumers in
one pass. Preserve stable digest behavior where existing public result types
expose it, or document and test the API delta.

### D2.4 D2 tests and documentation

Add or update focused tests for:

- wheel Python `Pattern` search plus typed extraction;
- bundle search plus typed extraction without `astgrep_name` at the call
  site;
- exact kind/range resolution and capture spans;
- Unicode/UTF-8 byte offsets;
- two bundles registered in one initial collection call;
- idempotent same-artifact registration;
- conflicting and late registration errors;
- custom `meta_var_char` behavior;
- unknown rule kinds and malformed patterns with clear typed errors;
- no accidental reintroduction of generated query rendering.

Update `docs/user-guide.md`, `docs/filter-semantics.md`, and any relevant API
reference. Show the division of labour: ast-grep finds, pydantree types. State
that bundle registration is preferred when a project owns the grammar. State
that raw queries remain the escape hatch.

Run focused tests before the full gates. Save raw outputs and any benchmark or
probe JSON/logs under this session's `evidence/` directory. Report every
command with its exit code.

### D2 acceptance

D2 is complete only when all of these are true:

- A documented bundle example works with `Pattern(..., language=grammar)` and
  `.extract(TypedClass)`.
- Wheel and bundle paths are both tested, with their different provenance
  semantics explicit.
- Returned rows, typed values, and UTF-8 byte spans are exact.
- `agreement.py` contains no dead bundle-only measurement path. Any retained
  wheel-only measurement code has a live caller or documented regeneration
  purpose.
- Registration, sigil, and error behavior are deterministic and tested.
- The full project gates below are green.
- The D2 report names every changed file, API/artifact delta, evidence path,
  and deliberate non-change.

If D2 acceptance fails, stop. Do not begin D3.

## 5. Phase D3 — tree-owned rewrite

Start only after D2 acceptance is met and recorded.

First inspect the existing rewrite implementation in `pattern.py`, including
`Pattern.replace_all`, `Edit`, `ReplaceResult`, `_apply`, overlap handling,
metavariable expansion, `_verify_reparse`, and `SyntaxCheck`. The current
implementation is already text-in/text-out and returns edit data. Preserve
working compatibility unless the tree-owned design requires a deliberate API
change.

### D3 objective

Make the rewrite operation belong to the parsed typed tree boundary:

1. Parse the source once with the bound `Grammar`.
2. Let `Pattern` find matches through the selected ast-grep grammar.
3. Resolve each selected match and its captures to exact nodes in that same
   pydantree tree.
4. Build byte-range edits from those exact nodes and the caller's template or
   replacement function.
5. Reject unsafe edits before applying them.
6. Apply edits right-to-left to an in-memory string.
7. Reparse the new source with the bound grammar.
8. Run `SyntaxCheck` when one is available, and return the result as data.

The library must never write a file as a side effect. If a new ergonomic API
is added, keep the pure operation separate from any caller-owned file write.

### D3 safety requirements

Implement and test the smallest design that satisfies these invariants:

- exact UTF-8 byte/character conversion at the ast-grep boundary;
- stale or out-of-tree match spans are rejected;
- overlapping and nested edits are rejected by default;
- an explicit, tested policy may select outermost or innermost matches;
- duplicate edits are deterministic;
- an edit that creates a new tree-sitter error is rejected unless the source
  already had an error and the documented policy permits it;
- a language-level `SyntaxCheck` can reject a result that tree-sitter's error
  recovery accepts;
- malformed templates, unknown metavariables, failed extraction, and failed
  reparses use the existing typed error taxonomy;
- original source and edit data remain available when validation is requested
  as diagnostics rather than exceptions;
- no write, subprocess, or hidden global mutable state is introduced.

Do not weaken validation merely to make a test pass. If a replacement can
legitimately expand one node into several, make that an explicit policy and
test it rather than silently accepting every multi-node result.

### D3 tests

Cover at least:

- one Python replacement with typed extraction;
- multiple disjoint replacements and right-to-left application;
- nested matches under refuse, outermost, and innermost policies;
- overlapping non-nested edits;
- a valid replacement accepted after reparse;
- a tree-sitter-invalid replacement rejected;
- a Python `SyntaxCheck` rejection that tree-sitter accepts through recovery;
- `validate=False` diagnostics and unchanged input on failure;
- UTF-8 text before and inside an edited range;
- a bundle grammar rewrite and a wheel grammar rewrite;
- proof that no file is written;
- regression coverage for raw-query and typed-node extraction.

Use `tests/test_lazy_nodes.py`, existing pattern tests, and the fixture bundles
as starting points. Add a focused rewrite test module if that is clearer.

### D3 acceptance

D3 is complete only when the rewrite invariants and tests pass, the documented
API is coherent for both bundle and wheel grammars, and all full gates below
are green. Report the exact API delta. Do not call a text-only convenience
wrapper tree-owned unless its edits are actually anchored to the typed parse
and its safety checks are demonstrated.

## 6. Required gates

Run these inside `devenv shell` and preserve raw output under `evidence/`:

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

Also run the focused D2/D3 tests separately and record their exit codes. If
`examples/devenv-subset/extract.py` rewrites its tracked `dist/` bundle,
inspect the result and preserve/revert only the generated change according to
the repository's existing convention; do not use destructive VCS commands.

## 7. Phase report

After D2, and again after D3, append a dated section to the session
`REPORT.md` containing:

- changed files and the reason for each;
- focused and full gate commands verbatim with exit codes;
- benchmark/oracle numbers and evidence paths;
- public API, generated bundle, and metadata deltas;
- retained/deleted `agreement.py` symbols and why;
- what was not done and why;
- remaining risks or follow-up work.

Do not summarize a failing gate as passing. Do not proceed past a failed phase.

At the end, if the user asks for handoff, save the lane through gitman only
after the gates are green, publish the lane, and report the exact gitman
status. Do not conceal off-canonical state or resolve it by abandoning
changes.
