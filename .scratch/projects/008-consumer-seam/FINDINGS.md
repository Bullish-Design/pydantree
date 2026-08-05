# Phase 6 — the consumer seam (packaging, real community grammars, and the
# deferred surface): Findings & Verdict

**Date:** 2026-08-02
**Status:** COMPLETE
**Verdict: GO on the consumer seam.** Run 1 (the install boundary) and Run 2
(the grammar-ownership boundary) both passed their go/no-go tests; Run 3
landed three of five deferred items and assessed the other two honestly. Two
real surprises surfaced and were fixed: the exact-path node-schema derivation
(`derive_from_ir`) was **never actually byte-for-byte** with the CLI (Phase 4's
"0-diff" agreement used a normalizer that masked serialization-shape
differences, and over a real grammar the derivation diverged in 16 missing / 7
extra kinds until this phase ported `node_types.rs` faithfully), and the
schema-registry leak was **worse than documented** (wheel-loaded languages
report `name=None`, so a bundle's schema registered under the `None` key and
silently applied to EVERY schema-less consumer of any nameless language — the
new rust bundle test broke the suite with a JSON Person model validated
against the RUST schema). Everything ran against the real toolchain
(tree-sitter CLI 0.25.3, bindings 0.26.0, gcc 14.2.1, pydantic 2.13.4).
Raw outputs saved verbatim under `evidence/` (r1_*, r2_*, r3_*).

Re-run:

```bash
devenv shell -- python -m pytest tests/                 # 159 green
devenv shell -- python .scratch/008-consumer-seam/experiment_run1.py
devenv shell -- python .scratch/008-consumer-seam/experiment_run2.py
devenv shell -- python .scratch/007-tsquery-distribution/experiment_phase5.py
devenv shell -- python .scratch/006-tsquery-bridge/experiment_phase4.py
```

---

## 0. The three verdicts in one screen

| run | go/no-go | verdict | evidence |
|---|---|---|---|
| **1 — the packaging seam** | a FRESH venv with only the light wheels (tscore+tsquery) runs the full checked extraction, B's toolchain stays out | **GO** | `r1_*`: fresh venv import graph, tsgrammar unimportable (rc 1), bundle round-trip + community extraction pass, **byte-identical** vs the in-repo (B importable) AND the run_bfree (B stripped) results |
| **2 — the community seam** | the schema path holds over a real grammar we don't own | **GO** | `r2_*`: schema tool + `derive_from_ir` both **byte-for-byte** vs the CLI's fresh node-types.json over tree-sitter-rust (182 rules, 11 externals); the community bundle built from the real source; a B-free consumer extracts a hand-authored rust task, checks active |
| **3 — the deferred surface** | Job-2 stubs, scanner seeds, wasm probe, registry leak, residuals | **4 LANDED, 1 ASSESSED** (+1 DSL fix in the 6.5 follow-up) | Job-2 `.pyi` stubs landed (mypy-checked); 2 scanner seeds landed (heredoc + matched-delimiter); **registry leak fixed** (worse than documented); wasm **assessed-not-built** (as specced); name-inference + wrapper-field residuals documented-and-moved-on; **the optional-field-capture DSL gap FIXED** (§3.5 — `?` quantifiers) |

---

## 1. Run 1 — the packaging seam at the INSTALL boundary: GO

The CONCEPT §8 distribution (tscore tiny / tsquery light / tsgrammar heavy)
is now real at the packaging level — the monolith (`pyproject.toml`
publishing one wheel with all six packages and `tree-sitter>=0.23`) is gone.

**The split.** Each of the three products gets its own `pyproject.toml` under
`src/` (the kickoff's "pyproject per package" shape). The pyproject lives
INSIDE the package dir and force-includes the dir's contents into the wheel
under the package name — a pragmatic choice that keeps the flat `src/` layout
(so the editable `.pth` and every `.scratch` experiment keep resolving
packages straight from `src/`). Known artifact: `pyproject.toml`/`PKG-INFO`
ride inside the wheel package — harmless, documented in the pyproject comment.
The root `pyproject.toml` is now the LEGACY distribution only (the deprecated
`pydantree` wrapper + examples + data — untouched) plus the dev flow.

**The wheel evidence** (`r1_split_wheels.txt`):

| wheel | contents | deps |
|---|---|---|
| `pydantree-tscore-0.1.0` | 4 modules (`schema`, `loader`, `_ir_derive`, `__init__`) | pydantic>=2.11, **tree-sitter>=0.26** — **no tsgrammar** |
| `pydantree-tsquery-0.1.0` | 6 modules | pydantree-tscore>=0.1, pydantic, **tree-sitter>=0.26** — **no tsgrammar** |
| `pydantree-tsgrammar-0.1.0` | heavy: all modules + **`scanners/indent_scanner.c`** (package data) | pydantree-tscore>=0.1, pydantic, **tree-sitter>=0.26** |
| `pydantree-0.1.2` | legacy wrapper + examples + data only | pydantic, tree-sitter>=0.26, tree-sitter-python |

The `tree-sitter>=0.23` → `>=0.26` pin is tightened everywhere (the code uses
0.26-only APIs: reparse, `field_name_for_child`, `node.id`, `is_missing`).

**The fresh-venv end-to-end** (`experiment_run1.py`): `uv venv` + `uv pip
install tscore==0.1.0 tsquery==0.1.0 tree-sitter-json` (a wheelhouse built
from the split wheels; the index resolves pydantic/tree-sitter/tree-sitter-json).
Results, all in the fresh venv with tsgrammar genuinely absent:

- `import tsgrammar` → **ModuleNotFoundError** (rc 1) — the seam does not leak;
- the Phase-5 cfg bundle round-trip (`Language.load_bundle` → Jobs 1/3/4 →
  the record + field ground truth) **passes**;
- the community extraction (json schema over `tree_sitter_json` → Person
  ground truth) **passes**;
- the A surface is **byte-identical** to the in-repo results (B importable,
  in-process) AND to the Phase-5 `run_bfree` results (B stripped) —
  `r1_byte_identical.txt`: all three comparisons true.

**Two real distribution findings:**

1. **The `tsquery` name is TAKEN on PyPI — RESOLVED by keeping pydantree.**
   A real, GPL-licensed `tsquery` (Greg Werbin, 0.1.1) won the resolution
   against our wheelhouse wheel (the fresh-venv install silently pulled it
   and the consumer broke). The Phase-6.5 decision: the distributions are
   pydantree-BRANDED — `pydantree-tscore`, `pydantree-tsquery`,
   `pydantree-tsgrammar` — while the import packages stay `tscore`/`tsquery`/
   `tsgrammar` (no code churn; the dependency graph becomes
   pydantree-tscore). The project identity is pydantree and the bare
   `tsquery` collision no longer blocks publishing.
2. **The dev flow has a hardlink-staleness caveat.** Hatchling's editable
   install for the flat-layout packages hard-links the package files into
   site-packages. In-place edits propagate, but adding NEW files or rewriting
   a file (a new inode) leaves the installed copy stale — `uv pip install -e
   src/tscore -e src/tsquery -e src/tsgrammar` must be re-run. This bit the
   suite twice this phase (new modules). Documented; a `devenv` task wrapping
   the editable install is the natural fix.

**The B-free boundary needed a fix.** The Phase-5 sitecustomize stripped the
editable `src/` path from `sys.path`; with the per-package editable installs
the packages now live directly in site-packages (hard links), so the strip is
no longer enough. The consumer sitecustomize now ALSO blocks `tsgrammar` at
the meta-path-finder level — the B-free boundary is enforced by construction,
not by path hygiene, and the consumers still assert `import tsgrammar` fails.

---

## 2. Run 2 — the community seam over the real tree-sitter-rust: GO

The community-schema tool was only ever exercised over grammars WE authored.
This phase took the real **tree-sitter-rust** source (182 rules, 11 externals,
hidden supertypes, merged aliases, reserved words — a grammar we don't own),
derived the schema, built the grammar, and extracted a real task B-free.

**Acquisition honesty.** The PyPI sdist of `tree-sitter-rust` ships only the
compiled `parser.c` + `scanner.c` — NOT the grammar source. The real source
(grammar.json + scanner.c + headers) comes from the GitHub repo; it is
vendored under `tests/fixtures/rust/` for hermetic tests (the fixture includes
the repo's own checked-in `node-types.json` as the oracle).

**The tool's contract, held byte-for-byte.** `derive_schema_for_dir` accepts
the community layout (`src/grammar.json` — and, with the `-o` flag, produces
layout-independent byproducts), and the derived schema is **byte-for-byte**
the CLI's own node-types.json (278 kinds; `r2_schema_tool_agreement.txt`).
`build_community_bundle` (source → `grammar.so` 1.1MB + `node-schema.json` +
metadata + loader, the same 4-file bundle B's pipeline produces) builds the
real grammar and a B-free consumer (`consumer_rust.py`, tsgrammar
unimportable) extracts a hand-authored task with the checks active:
4 function definitions (name/line), 2 with return types (add→u32,
greet→String), 2 tuple structs' field types as a **field-mode list** over
rust's ONE repeated field (`ordered_field_declaration_list.type`:
Point [f64,f64], Tuple [i32,String,bool]) — `r2_bfree_consumer.txt` shows
`ok: true`.

**The exact path now holds over a grammar we don't own — this was the
phase's biggest finding.** Phase 4 claimed `derive_from_ir` reproduced the
CLI's node-types.json "with zero diffs", but the check used a `_norm` that
stripped the serialization shape (`fields: {}` vs absent, `root:false`,
`extra:false`) — the byte-for-byte claim was never actually verified, and
over rust the RAW derivation diverged badly: **16 kinds missing** (the hidden
supertypes `_expression`/`_type`/..., named externals `string_content`/
`float_literal`, alias-derived kinds `type_identifier`/`field_identifier`/
`let_chain`/`primitive_type`/..., the `doc_comment` markers) and **7 kinds
extra** (unused rules the CLI prunes — `comment`, `delim_token_tree`,
`last_match_arm`, `scoped_type_identifier_in_expression_position` — plus
PATTERN-based anonymous tokens `.*`, `[^+*?]+`, `\/\/` that never appear in
node-types.json). `derive_from_ir` is now a faithful port of
`cli/generate/src/{parse_grammar,node_types,extract_tokens}.rs`:

- **reachability actually enforced** — the old code pre-initialized every
  rule's info, so the "unreachable → pruned" branch never fired; now the
  CLI's `variable_is_used` port decides, and the unreachable rules vanish;
- **aliases-by-symbol** — the CLI's merged-alias semantics (fields
  required-AND across rules aliased to one kind), alias-derived kinds
  (`type_identifier` via the `identifier` terminal's aliases), `let_chain`
  inheriting the hidden `_let_chain` rule's children, and anonymous-alias
  entries (`is not` with `fields: {}` over the hidden `_is_not`);
- **hidden non-inline refs are fixed-point inherit steps** (rust's recursive
  `_let_chain` converges through them — `multiple=true` — instead of being
  inlined to nothing); **field steps over hidden children inherit the
  child's children** (python's `assignment.right`);
- **hidden externals are empty inherit steps** (`_block_comment_content`
  contributes nothing); **supertypes are never hidden** (a hidden supertype
  referenced in a rule is a visible kind step);
- **STRING-only anonymous kinds** — probed: PATTERN tokens never appear in
  node-types.json, even `token()`-wrapped anonymous patterns; the token-rename
  semantics (`extract_tokens`: a bare-string rule becomes a NAMED terminal,
  a PREC-wrapped string stays a rule entry with `fields: {}` plus the
  anonymous string — python's `break_statement`);
- **emission shape** — `NodeTypeInfo.fields` is now Optional; `root`/`extra`
  only when true; entries keyed by `(type, named)` so rust's `block` rule and
  the anonymous `block` string coexist.

Verified **byte-for-byte over rust (280 kinds) AND python (218 kinds)** —
`r2_derive_from_ir_agreement.txt`, the hermetic test
`test_derive_from_ir_byte_for_byte_over_real_rust`, and the byte-compatible
serialization test. The 38-byte delta between the repo's checked-in
node-types.json (a newer CLI) and our CLI 0.25.3's fresh output is upstream
churn, not our derivation — documented.

**The honest leak catalog over a grammar we don't own (what's still weak):**
(a) the derivation mirrors CLI **0.25.3** exactly; a newer CLI's output can
drift (the 38-byte delta proves it) — the agreement is pinned to the CLI
version, which is exactly what the schema-tool's byproduct path sidesteps;
(b) the name-based kind→type inference residue (documented, `NodeKind` is the
escape); (c) the field-mode-list wrapper-field case (documented, moved on —
see §3.5). The "IR-shaped byproduct" concern the kickoff raised: NOT needed —
the exact path now agrees with the CLI byte-for-byte over a real grammar, so
the "hundreds of community grammars" claim rests on the same derivation the
CLI itself embodies.

---

## 2b. The markdown rehearsal (the Phase-6.5 follow-up): FOUR real grammars, byte-for-byte

The second real-grammar rehearsal (requested with markdown — both inline and
block elements). tree-sitter-markdown is a genuinely different beast than
rust: **47 externals**, hidden rules wrapping repeats, **structured-content
aliases** (`inline` over `REPEAT1(choice(_line, ...))`), and **positional
children instead of CST fields**. The exact-path derivation is now
byte-for-byte over FOUR real grammars (rust, python, markdown-block,
markdown-inline) — two more calibrations landed to get there:

1. **Hidden-rule non-top-level repeats are 0+.** The CLI wraps a repeat
   inside a hidden rule (seq/PREC-wrapped) in an auxiliary binary-tree rule
   whose children_without_fields quantity is OPTIONAL (required=false), while
   a bare top-level REPEAT1 body becomes the recursion ITSELF (required=true).
   Probed and isolated case-by-case; `_relax_hidden_repeat` encodes it.
2. **Structured-content alias entries.** `alias(REPEAT1(choice(_line,
   ...)), "inline")` — the alias value gets its own entry inheriting the
   content's SUMMARY, MERGED with any rule-loop contribution of the same kind
   (the `_summarize` refactor + the merge).

**The consumer rehearsal exposed a real surface gap, now fixed: `capture_kind()`.** Both markdown grammars use POSITIONAL CHILDREN (fenced-code's content, inline's emphasis/code spans/links have no CST fields) — the field-keyed `capture()` could not express them. A minimal, honest extension landed: `= capture_kind("code_span")` captures a CHILD BY KIND (Job 1 checks the kind is a possible child of the anchor — it caught `language` under info_string and `link_destination` under inline_link live — and Job 4 checks the kind's own types against the field type).

The B-free rehearsal extracts BLOCK elements (headings via markdown's one
field `heading_content`; fenced code via `capture_kind`) and INLINE elements
(code spans, emphasis, strong, links via a nested parse of each `inline`
node's text — the injection the full markdown parser does) against hand
truth: `r2b_markdown.txt` / `r2b_markdown_consumer.txt`, `ok: true`.

## 3. Run 3 — the deferred surface: 3 landed, 2 assessed

### 3.1 Job-2 `.pyi` stubs — LANDED
`tsquery.stubs.generate_stubs(schema, out=...)` emits a `.pyi` beside the
schema (the Phase-4 "worth it after distribution" item — distribution is
proven). Per named kind: field accessors (`def name(self) -> identifier |
metavariable | None`, repeated fields `-> list[T]`), a `get(field)` overload
per field, and a `children(kind)` overload per possible child kind;
supertypes become aliases over their subtypes; anonymous kinds map to `Node`;
colliding accessor names get a `field_` prefix. The test generates the stub
over the real rust fixture, asserts it parses and every annotation name
resolves, and runs **mypy** over a consumer that casts a real
`tree_sitter.Node` to the generated classes and exercises the accessors —
clean. `out=` writes it beside the schema (the packaging surface).

### 3.2 Scanner library seeds — LANDED (2 of the library's growth)
- **`heredoc_scanner.c`** (hmini): the canonical HEREDOC_START/BODY pair.
  START scans `<<` + the delimiter (captured in scanner state, serialized);
  BODY scans the content lines ending at the delimiter line (the token
  INCLUDES the delimiter line, bash-like; the trailing newline is a regular
  token). Two real scanner gotchas landed as tests: the lexer calls the
  scanner **mid-whitespace** (skip it first), and **both externals can be
  valid in ONE parser state** (the source disambiguates: a `<` is always a
  START — the docs' scanners hit the same state-merging). Empty bodies and
  nested-marker content pass.
- **`matched_delimiter_scanner.c`** (dmini): the docs' balanced-parens
  example — a `(...)` group with arbitrary nesting is ONE `BALANCED` token;
  unbalanced groups at EOF are refused (strict, not silently swallowed).
- `scanner_for()` grows to pymini/hmini/dmini; both follow the airtight
  mechanism (scanner=, content-addressed cache keying, the
  `ExternalScannerRequiredError` escape hatch). The full per-language library
  stays Phase 7.

### 3.3 wasm — ASSESSED, NOT BUILT (as specced)
Probe (`r3_wasm_probe.txt`): **no emscripten toolchain** (no emcc/em++/emsdk
in the devenv — adding it is a real toolchain install), and **no wasm runtime
importable in A** (no wasmtime/wasmer/pyodide). What it would take: the
emscripten SDK at BUILD time (B-side) to emit a `.wasm` alongside (or instead
of) the `.so` in the 4-file bundle; a wasm runtime dependency in A's light
install (wasmtime/wasmer — a new runtime dependency on the light side), and
the documented ~1.5–2× parse perf cost. **The native bundle + per-platform
wheels are enough for the distribution claim**: the consumer seam is B-free
consumption, and Run 1 proved a light install over native wheels delivers it.
wasm buys portability (no per-platform native build) — a genuine Phase-7 item
for the "install anywhere" story, not a gap in the current claim.

### 3.4 The schema-registry leak — FIXED (worse than documented)
The `_SCHEMA_REGISTRY` name-keyed global was documented as a leak
("a bound schema silently applies to later schema-less consumers of the same
language name"). The Phase-6 reality was worse: **wheel-loaded languages
report `name=None`**, so the rust bundle's schema registered under
`_SCHEMA_REGISTRY[None]` and applied to EVERY schema-less consumer of ANY
nameless language — the new rust bundle test made it break the whole suite
(a JSON Person model validated against the RUST schema). Fixed properly:
`Language.load` binds the schema to the INSTANCE (per-Language scoping);
the name-keyed convenience is an explicit opt-in (`register=True`); a
nameless language is refused registration. The convenience
(`validate_with(lang)` finds the schema via the wrapper) survives — the
tests updated and new opt-in/refusal tests added.

### 3.5 The residuals — documented-and-moved-on (as specced)
- **Name-based kind inference** (`"number" → int` is a convention; `NodeKind`
  is the typed escape) — re-documented, moved on. The schema restricts WHICH
  kinds are candidates exactly; the Python-type half is a name pattern.
- **Field-mode-list wrapper-field case** (`list[X] = capture("arguments")`
  where the field points at a wrapper node — the repeated field must sit ON
  the anchor) — re-documented, moved on. Rust's real grammar confirmed the
  case is about the grammar's field shape, not the machinery.
- **NEW (Phase 6, FIXED in the 6.5 follow-up): optional field-mode captures
  used to still require the field** — a `str | None = capture("return_type")`
  field-mode capture emitted `return_type:(_)` in the query, so functions
  WITHOUT the field never matched (found live over real rust: `fn
  no_return() {}`). The fix: a field-mode capture is query-optional iff the
  model can materialize without the field (an Optional annotation or a REAL
  default — a `= capture(...)` marker is NOT a default, pydantic's
  `is_required()` treats it as one), and the derived pattern emits `?`
  (`return_type:(_)? @return_type`). Probed first: the 0.26 query engine
  supports child `?` quantifiers and captures the node when present while
  still matching when absent; the predicates already use the `#pred?`
  optional form, so they compose. The materializer also learned that an
  absent capture with a marker default means None (not the marker object).
  `consumer_rust.py`'s `RustFnReturn` now extracts ALL FOUR functions
  (main/no_return with `return_type: null`) — the workaround model is gone.

**The dev-flow hardlink staleness is mitigated for the suite**: the tests now
resolve `src/` first via `tests/conftest.py` (the same resolution the
`.scratch` experiments use), so the suite always exercises the current code
— the packaging claims are still tested against the installed/wheel
artifacts (test_packaging builds+inspects the wheels, the fresh-venv test
installs them, the B-free consumers copy `src/`).

---

## 4. §11 risks re-assessed from the Phase-6 side

- **§11.3 toolchain packaging for B** — CONFIRMED FINE at the install
  boundary: B's toolchain (Rust CLI + gcc) lives entirely in the heavy
  wheel's world; the light install never resolves it (Run 1: `import
  tsgrammar` fails, and the light wheels declare no tsgrammar dependency).
  B's scanner package data rides the heavy wheel (`scanners/indent_scanner.c`
  present there, absent from the light wheels — tested).
- **§11.4 upstream churn** — the `tree-sitter>=0.26` pin is now a real
  dependency floor in every distribution (the code's 0.26-only APIs made
  `>=0.23` a lie). The derivation's byte-for-byte agreement is pinned to CLI
  0.25.3 — a newer CLI's node-types.json drifts (the 38-byte rust delta);
  the community TOOL path (CLI byproduct → schema) tracks the installed CLI
  by construction, which is the right answer for the "hundreds of grammars"
  claim.
- **§11.5 wasm perf** — post-probe: not built; native + per-platform wheels
  carry the current claim (§3.3).
- **Newly surfaced:** (a) the exact-path derivation was never actually
  byte-for-byte (Phase-4 `_norm` masked it) — now fixed and pinned by tests;
  (b) the registry `None`-key collision (§3.4); (c) the `tsquery` PyPI name
  collision (§1); (d) the optional-field-capture DSL gap (§3.5); (e) the
  editable hardlink staleness (§1); (f) PATTERN tokens are never anonymous
  kinds and both-externals-in-one-state scanner states (probed facts the
  scanner seeds rely on).

---

## 5. Recommendation

**GO on the consumer seam.** Run 1 proves the CONCEPT §8 claim at the
install boundary — a consumer who installs only the light packages gets the
full checked extraction, byte-identical to the in-repo results, and B's
toolchain stays out. Run 2 proves the community claim over a grammar we
don't own — the schema tool AND the exact path agree with the CLI
byte-for-byte over real rust, and a B-free consumer extracts a real task
against hand truth. The deferred surface landed where it was worth it
(Job-2 stubs, two scanner seeds, the registry fix) and was honestly assessed
where it wasn't (wasm — not needed for the claim).

**The single most important next step: Phase 7 — real-user adoption, not
more machinery.** The consumer seam is proven; what it needs now is a user.
Concretely, in order: (1) **resolve the `tsquery` name problem** before any
publishing (a renamed light distribution, or deliberate publishing to
outrank the GPL package — this is the one blocker between "proven" and
"installable-by-name"); (2) a real-user adoption pass (someone with a real
grammar + a real extraction task, through the light install, end to end —
the corpus harness, stubs, and scanners are polish to grow on demand, not
prereqs); (3) the remaining deferred surface when users ask for it — the
wasm runtime for the portability story and the per-language scanner library
(the optional-field-capture DSL item is DONE — the 6.5 follow-up landed
`?`-quantified optional captures; see §3.5).
