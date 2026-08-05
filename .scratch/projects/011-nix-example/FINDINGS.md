# Phase 9 — the real-world Nix adoption pass: Findings & Verdict

**Date:** 2026-08-04
**Status:** COMPLETE
**Verdict: GO — the seam is ready for real users over a SIXTH, again
different-shaped grammar (tree-sitter-nix v0.3.0: attrsets with dotted
attr paths, `${...}` interpolation, `''...''` multiline strings with
`''${...}` escapes, `let ... in`, function formals), with the strongest
real-user evidence the project has ever had — the corpus is the user's OWN
52-repo `devenv.nix` fleet.** The consumer story held end-to-end through the
LIGHT install in BOTH real-user shapes (bundle + PyPI wheel), B-free,
byte-identical; the fleet inventory (packages / env / scripts / tasks /
enabled switches / enterShell+enterTest, aggregated per repo) matched the
hand-written truth **130/130 rows over all seven vendored configs** — real
configs, not hand-authored samples. The nix pass ALSO surfaced the biggest
ecosystem finding of the whole project: **the nix grammar is position-UNSTABLE
under the tree-sitter 0.26 runtime on large multiline-string-heavy files
(the user's own 526-line flora config segfaults ~always on start-point
walks; the upstream wheel and our from-source build both; the tree-sitter
CLI 0.25.3 runtime parses it correctly)** — a real user with a big config
would hit it, and the phase's workaround (byte-offset line numbers) is the
escape hatch. The wheel-version question from the kickoff is RESOLVED: the
PyPI wheel 0.1.0 corresponds to the pre-`bae4c4f` grammar (trailing-comma-
in-formals is the ONLY behavioral delta; probe trees identical over a devenv
corpus; the fleet never uses that formals shape). Record mode does NOT fit
nix's attrset (the pair-kind detection is JSON-shaped) — the flagged probe
answered: no, with the precise reason. Next step stays the **publishing
rehearsal** (still deferred by the user, per the Phase-8 recommendation).

Re-run (all in the devenv):

```bash
devenv shell -- python .scratch/011-nix-example/experiment_run1.py  # acquisition + derivation + wheel probe
devenv shell -- python .scratch/011-nix-example/experiment_run2.py  # both light-install shapes, byte-identical
devenv shell -- python .scratch/011-nix-example/experiment_run3.py  # compiled_source + stubs + record probe + position-bug evidence
devenv shell -- python -m pytest tests/                             # 171 green + 1 skip (baseline recaptured)
```

Evidence (verbatim, under `evidence/`): `r9_r1_*` (acquisition, schema
agreement, oracle delta, schema shape, wheel probe), `r9_r2_*` (the three
consumer runs + bundle manifest + byte-identical + verdict), `r9_r3_*`
(compiled .scm, nix stubs, record-mode probe, position-bug summary + fleet
stability table), `r9_r4_example_fresh_venv.txt` (the example run in a fresh
venv exactly as a new user runs it).

---

## 1. Run 1 — acquire + derive the Nix grammar: GO

**Acquisition honesty (same policy as rust/bash, Phase 6/8):** the PyPI
sdist of `tree-sitter-nix` ships only the compiled `parser.c` + `scanner.c`
— NOT the grammar source. The source comes from `nix-community/
tree-sitter-nix` tag **v0.3.0** (`ea1d87f`, 2025-07-18, MIT, maintainer
@cstrahan) and is vendored under `tests/fixtures/nix/` (hermetic):
`grammar.json` (46 KB, 49 rules — 10 hidden), `scanner.c` (7.6 KB — the 6
externals: string/path fragment scanning), `tree_sitter/` headers, and the
repo's checked-in `node-types.json` as the ORACLE. Compiled `parser.c` is
NOT vendored (the byproduct, same policy). Provenance documented in
`tests/fixtures/nix/PROVENANCE.md`.

**The wheel-consistency question — RESOLVED by source archaeology + a parse
probe** (`r9_r1_acquisition.txt`). The PyPI wheel `tree-sitter-nix` 0.1.0
(uploaded 2025-02-20, homepage metadata pointing at a nonexistent repo) was
built from a grammar source that was **frozen between `04e5dca`
(2022-09-07) and `bae4c4f` (2025-07-16)** — its scanner.c is byte-identical
to v0.3.0's (unchanged since 2023-07-08), and its parser.c (ABI 14 vs the
repo's checked-in ABI 13 — a CLI-generation difference, not a grammar one)
matches a source state whose ONLY delta to v0.3.0 is
`bae4c4f` "fix: handle trailing comma in formals (#131)": v0.3.0 allows a
trailing comma WITHOUT ellipses in function formals; the wheel-era grammar
requires the comma to pair with ellipses. The parse probe confirms it
exactly: a devenv-shaped corpus parses to **identical trees** in the wheel
and the v0.3.0 build (0 errors both), while `{ a, b, }: ...` errors in the
wheel (a MISSING identifier) and parses cleanly in v0.3.0
(`r9_r1_probe_*`). And the fleet NEVER uses that formals shape (verified:
no trailing-comma formals in any of the 52 configs) — so the wheel shape's
extraction over real configs is byte-identical to the bundle's (Run 2,
unqualified). **A stale wheel is REAL user friction** (catalog entry 8):
a user on the wheel gets a grammar one release behind on ONE rule, invisible
unless they hit that formals shape.

**The tool's contract, byte-for-byte:** `derive_schema_for_dir(
tests/fixtures/nix)` → **83 unique kinds / 84 node-types entries**;
byte-for-byte vs the CLI 0.25.3's fresh node-types.json
(`r9_r1_schema_tool_agreement.txt`). The vendored oracle (v0.3.0, generated
by a NEWER CLI) differs by **20 diff lines** — the `root: true` / `extra:
true` serialization flags only (the exact class of the rust 38-byte delta;
bash was 0) — upstream churn, and the community tool tracks the installed
CLI by construction (`r9_r1_oracle_delta.txt`).

**The schema shape over nix** (`r9_r1_schema_shape.txt`): 42 named + 42
anonymous kinds; the 6 externals (string_fragment, _indented_string_fragment,
_path_start, path_fragment, dollar_escape, _indented_dollar_escape) appear
in node-types.json as named kinds; the `_expression` supertype is the schema
shape's skeleton (hidden-but-visible, the Phase-6 rule); repeated fields:
`attrpath.attr`, `binding_set.binding`, `list_expression.element`,
`formals.formal`, `inherited_attrs.attr`; the `inherit` keyword is BOTH a
named kind and an anonymous keyword (the 84-entries-vs-83-kinds detail);
**no declared GLR conflicts** — `build_community_bundle` generates and gcc
compiles cleanly (the grammar.json declares `conflicts: []`).

## 2. Run 2 — the light-install consumer, BOTH real-user shapes: GO

`experiment_run2.py` builds the light wheels, creates a FRESH venv with ONLY
those + `tree-sitter-nix` **0.1.0 from the real index**, builds the community
bundle in-repo, and runs the SAME consumer in three shapes:

| run | interpreter | pydantree_sitter_grammar | rows vs hand truth |
|---|---|---|---|
| in-repo bundle | devenv python (B importable) | importable | ok=True |
| fresh-venv bundle | fresh venv, `Language.load_bundle(dir)` | **unimportable (rc 1)** | ok=True |
| fresh-venv wheel | fresh venv, `tree_sitter_nix.language()` + derived schema | **unimportable (rc 1)** | ok=True |

The extraction payloads are **byte-identical across all three**
(`r9_r2_byte_identical.txt`) — including over flora, because the line
numbers are byte-computed (the position-bug workaround) and the value
captures are byte-based. The seam does not leak: `import pydantree_sitter_grammar` fails in
the light install.

**Where the wheel and bundle shapes differ for a real user THIS time:**

1. **The wheel-version mismatch** (the kickoff's question): the wheel is a
   RELEASE behind the source (0.1.0 vs v0.3.0) — the one-rule delta
   documented above. The bundle shape is unambiguous (v0.3.0 source →
   schema + parser, consistent). A user on the wheel silently gets the older
   grammar unless they hit `{ a, b, }:` formals. Stale-wheels-are-friction:
   REAL, documented, escaped by building from source (the bundle shape).
2. **The wheel's `language()` returns a bare PyCapsule** — this wheel was
   built against an OLD binding API. pydantree_sitter converts it internally
   (`tree_sitter.Language(capsule)`), so the A surface just works; a user
   probing with raw bindings hits the capsule (catalog entry 10).
3. **`lang.name` is None in BOTH shapes** (the Phase-8 residual, new flavor):
   the wheel's capsule language is nameless (an old-binding artifact), so the
   wheel shape does NOT report "nix" — it reports None like the bundle.
   Harmless for extraction (the example prints kinds instead).

## 3. Run 3 — the fleet inventory vs hand truth: PASS (130/130), plus the
## position-bug finding and the record-mode probe result

**The corpus is the user's own fleet.** Seven real `devenv.nix` configs
vendored under `tests/fixtures/nix/fleet/` with per-file provenance
(`FLEET_PROVENANCE.md`): mypi-agent (8 lines), pydantree (85 — its task
nests a bash heredoc INSIDE a nix multiline string), terminal-state (192),
structured-agents-v2 (221), nixvim (240), fsdantic (250), flora (526). The
`/home/andrew` paths in two files are sanitized to `/home/nixuser`
(same-shape string literals, documented); a review found no secrets.

**Hand truth written FIRST** (`ground_truth.json`, 130 rows: 55 packages, 14
env, 36 scripts, 3 tasks, 16 dotted `.enable` switches, 5 enterShell, 1
enterTest) — from nix semantics, before any model existed; verified against
the raw file text (every body slice and env value present in the file, every
line pinned). The names are the full dotted attr paths (the raw-text
contract: `scripts.hello.exec`, `tasks."pydantree:venv-src-pth".exec`, env
values keep their quotes, multiline bodies keep their `''` delimiters).

**The models** (the whole A surface the task needed): two generic models —
`Binding` (every `attrpath = expression;` binding: the value's raw text +
source_meta line/span) and `List` (every list literal: the repeated
`element` field as a field-mode list). Both use descendant matching
(`M("source_code", ..., "binding")`) and `validate_with` runs Jobs 1/3/4
before parsing. **The extraction matches the hand truth 130/130 across all
seven files** (`r9_r2_*` payloads, ok=True in all three run shapes).

**Which A-surface features nix's shape needed (and what it didn't):**

- **`capture_kind`: NOT needed** — nix's bindings are field-shaped (the
  field surface sufficed; bash's positional heredocs were the reason it
  exists).
- **Optional captures / predicates / `Matches`/`Eq`**: used lightly (the
  `enable = true` switch filter uses the raw value text), no surprises.
- **`Span`-typed source_meta: WORKED but needed `model_config =
  {"arbitrary_types_allowed": True}`** — the OutputModel base doesn't set it,
  so a `span: Span = source_meta()` field fails pydantic class creation with
  `PydanticSchemaGenerationError` (a real UX gap — catalog entry 11; the
  docs say Span is usable, but no test model had ever used it).
- **Record mode: does NOT fit nix's attrset** (the flagged probe, answered):
  `M(..., record=True)` over `binding_set` raises `UnsupportedShapeError` —
  the record machinery's pair-kind detection looks for a CHILD KIND with
  `key`/`value` fields (the JSON pair shape); nix's `binding_set` carries a
  `binding` FIELD, and the binding has `attrpath`/`expression` fields
  (`r9_r3_record_mode_probe.txt`). Phase 8 said record mode fits
  config-file grammars "not bash's statement list" — over nix the shape is
  the right KIND of thing (attrset = key/value document) but the machinery's
  pair detection is JSON-hardcoded. Not a regression — a documented
  parameterization opportunity (a "binding-shaped pair" hook), explicitly
  NOT this phase's job.

**The position-bug finding (the phase's biggest ecosystem result):** the
nix grammar under the tree-sitter **0.26 runtime** corrupts node start
POINTS on large multiline-string-heavy files. Measured
(`r9_r3_fleet_stability.txt`, `r9_r3_position_bug_summary.txt`):
- upstream wheel parser, full start_point walk: **flora 30/30 SIGSEGV**; the
  other six fleet files 0/30 each;
- our gcc build of the same source: ~6/10 direct walks;
- the pydantree_sitter EXTRACTION path (query engine, start_point read on anchor
  nodes only): 0/24 crashes, but **22/55 flora binding lines are garbage**
  (start_point degenerates to start_byte) — the consumer's `line` fields
  over flora are wrong, not crashing;
- the **tree-sitter CLI 0.25.3 runtime parses flora with CORRECT positions**
  (the same grammar source) — so this is a runtime-version interaction, not
  the grammar source;
- trigger isolated: flora line 258 (`case "$answer" in` inside a multiline
  string body) — the first 257 lines are stable, 258+ crashes ~always;
- start_BYTE / node text / children reads are ALWAYS safe (0/30) — only the
  POINT computation corrupts.

**The escape hatch (used by the consumer + example):** line numbers are
computed from BYTE offsets (`src[:start_byte].count(b"\n") + 1`) — start_byte
is reliable even in corrupt trees — and start_POINT reads are avoided on the
large file. The models still carry `source_meta`; the consumer cross-checks
the model lines against the byte-computed lines: **agreement on all six
stable files (0 disagreements), 22 flora disagreements** — the corruption,
measured per file. This is a candidate upstream bug report
(nix-community/tree-sitter-nix + tree-sitter 0.26).

**`compiled_source` + stubs** (`r9_r3_compiled_source.scm`,
`r9_r3_nix_stubs.pyi`): the two derived patterns are
`(binding expression:(_) @value)` and
`(list_expression element:(_) @element)` — the schema checks passed
byte-compatible derivation. The Job-2 stubs are good quality over nix:
`binding` gets field_attrpath/expression accessors, `binding_set`
field_binding (list of binding|inherit|inherit_from), `list_expression`
element() with the full expression-kind alternation, `attrpath` attr()
(list of identifier|interpolation|string_expression),
`indented_string_expression` children(kind) overloads for the externals.

## 4. Run 4 — the example + the friction catalog

**The artifact** (`examples/devenv-extract/`): `extract.py` (the two models
+ the fleet inventory over the vendored six-repo subset — prints typed rows
per task, self-checks vs `ground_truth.json`), `node-schema.json` (derived
from the v0.3.0 source, committed for the wheel shape), the self-contained
corpus (`fleet/`, 102 rows of hand truth), and a README a new user follows:
`uv venv` + light wheels + `tree-sitter-nix` + `python extract.py` → typed
rows. **Verified in a FRESH venv exactly as a new user runs it**
(`r9_r4_example_fresh_venv.txt`: `import pydantree_sitter_grammar` fails, rc 0, 102 rows
match). Also runs from the dev venv via `--bundle`. **flora is deliberately
NOT in the example** — including it made the fresh-venv run segfault at
interpreter teardown 3/5 (the corrupted tree's C destructor); the six-file
example runs 0/6 crashes. The seven-file extraction remains the Run-3
evidence (the byte-line workaround), and flora's crash is documented in the
README with the evidence pointer.

### The friction catalog — every real-user stumble over nix (Phase-8 baseline
### re-assessed), with the escape hatch

| # | what happened | real gap or residual? | escape hatch / status |
|---|---|---|---|
| 1 | **THE POSITION BUG**: node start_POINT reads on large multiline-string-heavy nix files (flora 526 lines) return garbage (start_point == start_byte) or SIGSEGV (wheel 30/30 on a full walk; our build ~60%); extraction lines wrong over flora; teardown segfault in the fresh-venv example | **real upstream ecosystem bug** (grammar × tree-sitter 0.26 runtime; CLI 0.25.3 parses correctly; trigger = line 258 of flora) | compute lines from BYTE offsets (start_byte is always reliable); avoid start_point reads on big files; report upstream (candidate nix-community/tree-sitter-nix issue) |
| 2 | The binding's ATTRPATH is not str-capturable: `attrpath: str = capture("attrpath")` → SchemaCheckError (attrpath is a structural node — a chain of identifiers + dots — not text-yielding) | **real gap** (the Phase-8 "no raw text of any node" residual, TRIGGERED hard over nix — the KEY of every nix binding) | the key becomes consumer-side context (a tree walk); the VALUE stays a capture |
| 3 | Full dotted paths need RECONSTRUCTION: `venv.enable` inside `languages.python` captures only the local attrpath — the ancestor attrset chain is context, not a capture | real gap (context class) | the `dotted_path` ancestor walk (documented helper; the consumer + example ship it) |
| 4 | The nixvim/flora `config = { ... }` module wrapper: devenv option paths must strip a single top-level `config.` segment | real behavior (their module convention) | the helper strips it; documented in the README |
| 5 | Record mode does NOT fit nix's attrset: `binding_set` as a record → UnsupportedShapeError (pair-kind detection wants child kinds with key/value fields; nix has a `binding` FIELD with attrpath/expression) | honest assessment (the flagged probe: answered NO, with the precise reason) | field-mode (this phase's models); a "binding-shaped pair" parameterization is a documented machinery candidate |
| 6 | `Span`-typed source_meta fails class creation without `arbitrary_types_allowed` on the model | **real UX gap** (documented surface, never exercised by a test model) | set `model_config` (the example does); a base-config fix is a machinery candidate |
| 7 | The wheel shape's one extra step (bind the schema explicitly — a wheel ships none) | by design (the schema is the bridge) | ship node-schema.json (this example does) |
| 8 | **The stale-wheel mismatch**: `tree-sitter-nix` 0.1.0 is a RELEASE behind the source (the trailing-comma-in-formals delta, #131); the wheel's homepage metadata points at a nonexistent repo | **real ecosystem fact** | resolved in Run 1 (wheel = pre-bae4c4f grammar); probe trees identical over real configs; build from source for the current grammar |
| 9 | `lang.name` is None in BOTH shapes over nix (the wheel's capsule language is nameless — old-binding artifact) | residual (Phase 6), new flavor | harmless; the example prints kinds |
| 10 | The wheel's `language()` returns a bare PyCapsule (old binding API) | real behavior | pydantree_sitter converts internally; raw bindings need `tree_sitter.Language(capsule)` (documented in the README) |
| 11 | `packages = [ ... ] ++ expr` appends (flora's `lib.optional ... llamaCpp`, nixvim's `++ cfg.extraPackages`): appended expressions are NOT list elements — only direct elements of list literals count | real behavior (nix semantics) | documented; the ancestor-aware list filter counts only the literal's elements |
| 12 | env values are structural expressions (`lib.mkDefault (...)` calls, `+`/`++` chains) — captured WHOLE as raw text (the check passes because the expression field's kinds include text-yielding leaves) | pleasant surprise (the Phase-8 item-3 class did NOT block here) | raw node text is the contract; the value is the full expression text |
| 13 | `''${...}` ESCAPED interpolations inside multiline strings (structured-agents-v2's bash) — parsed as string content, no interference | non-event (the grammar's externals handle them) | — |
| 14 | `tasks."quoted-name".exec` — string attrs keep their quotes in the dotted path (`tasks."pydantree:venv-src-pth".exec`) | real behavior (raw text) | strip in a property if wanted; documented |
| 15 | Name-based kind inference / field-mode-list wrapper-field residuals — NOT triggered by nix | residual (Phase 6) | moved on |
| 16 | capture_kind optionality (the Phase-8 FIX) — NOT re-triggered; the regression test holds | non-event | pinned by `test_capture_kind_optionality_quantifies_only_optional_fields` |

## 5. Risks re-assessed from this side

- **§11.4 upstream churn** — the nix oracle delta is 20 lines (root/extra
  serialization flags only); the community tool path tracks the installed CLI
  by construction. The WHEEL is a release behind (the stale-wheel fact) —
  the honest "distribution lag" risk is real and documented.
- **The wheel-vs-bundle distribution question** — both shapes proven over a
  sixth grammar; the wheel's extra step (explicit schema bind) + the
  capsule-language + the release lag are the honest real-user differences,
  all with escape hatches.
- **The "real-user stumbles are surface bugs" class** — CONFIRMED AGAIN, at
  a higher level: this phase's real-user surprise is an UPSTREAM grammar/
  runtime bug (the position corruption), not a pydantree surface bug. The
  seam absorbed it with a documented workaround; the phase's value is the
  honest measurement + escape hatch, and the candidate upstream report.

## 6. Recommendation

**GO — the seam is ready for real users over a sixth grammar.** The
"hundreds of grammars" claim holds over nix (attrsets, dotted attr paths,
`${...}` interpolation, `''...''` multiline strings with escapes, `let...in`,
function formals): the light install delivers the full checked extraction in
both real-user shapes, B-free, byte-identical, over the user's OWN fleet —
130/130 rows matching hand truth across seven real configs (the strongest
real-user evidence the project has ever had). The two machine-side gaps this
phase surfaced are real but small (the attrpath capture rejection — the
"key is context" class — and the Span model_config); the BIG finding is
upstream: **the nix grammar is position-unstable under the tree-sitter 0.26
runtime on large files** (the user's 526-line flora), with a working escape
hatch (byte-offset lines) and a candidate bug report. Record mode over nix's
attrset: does not fit (the pair-kind detection is JSON-shaped) — a
documented parameterization candidate, not a blocker.

**The single most important next step: the PUBLISHING REHEARSAL** — still
deferred by the user, and the Phase-8 recommendation stands unchanged (and
now better-motivated: the stale-wheel mismatch is a live example of why
installable-by-name distribution matters — the PyPI nix wheel is a release
behind and its user cannot see it). A rehearsal would publish the three
pydantree distributions to a real index, install them BY NAME into a fresh
venv, and run this exact nix example. The natural user-facing follow-up once
the user lifts the deferral: **a whole-fleet scan tool** — this phase's
inventory over all 52 repos (the vendored seven are the seed; the byte-line
workaround makes the big configs safe).
