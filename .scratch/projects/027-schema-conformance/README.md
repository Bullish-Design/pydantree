# 027 — schema/language conformance

**Date:** 2026-09-09 · **Baseline:** 350 passed, 1 xfailed @ `b9cad4f` working tree
(`devenv shell -- python -m pytest -q`, 43.4 s). Ruff, ty, doc snippets, and all
four maintained examples are green at the same point.

**Origin:** the engineering review of Phase 024 item 5, "durable schema
distribution for community grammars" (the work recorded in
[`../025-schema-distribution/FINDINGS.md`](../025-schema-distribution/FINDINGS.md)).

---

## 1. The finding

Phase 025 answered "where does the schema live?" and answered it correctly.
Application-owned `node-types.json` is the right model. The review found direct
support for it that 025 did not cite: the installed `tree_sitter_python` wheel
ships no schema at all.

```text
tree_sitter_python 0.25.0 package contents:
  __init__.py  __init__.pyi  _binding.abi3.so  binding.c
  py.typed  queries/highlights.scm  queries/tags.scm
  node-types.json files: []
```

Phase 025 did not answer the second question: **how does the runtime know that
the schema it received describes the grammar it received?**

Today the runtime answers with a **filename comparison**. `load_schema` invents
a grammar name from the file name or the parent directory
(`schema.py:280-286`). `Grammar.load` compares that invented string to
`Language.name` (`grammar.py:71`). The check fails in both directions, and it
fails silently.

### Proven failure modes

Each row below is a probe that ran against this workspace.

| # | Input | Result |
|---|---|---|
| C1 | Rust schema copied to `python-node-types.json`, Python language | **Binds.** 278 Rust kinds, no error |
| C3 | Rust schema, `schema_name="rust"`, `tree_sitter_json` language | **Binds.** `Language.name` is `None` on ABI 14, so the guard short-circuits |
| H2 | Correct Python schema at `vendor/node-types.json` | **False `SchemaDriftError`**: "schema 'vendor' does not match loaded language 'python'" |
| H3 | `[]` | **Binds.** Zero-kind universe, no error |
| C2 | The shipped example schema, 9 of 274 kinds | **Binds.** `x = compute()` extracts as `right=None` |

C3 is the worst of these. The user passed the explicit `schema_name`, and passed
it accurately, and a Rust schema still bound to the JSON parser. `tree_sitter_json`
is ABI 14, it is installed in this repository's devenv, and
`tests/test_grammar_nodes.py` is built on it.

C2 is the most damaging. `examples/wheel-extract/vendor/python-node-types.json`
is a hand-authored 9-entry file. Its provenance record claims it came from
`tree-sitter-python==0.25.0` through `tree-sitter 0.25.3 generate`. The claim is
false. The artifact that demonstrates the architecture violates it, and 350
passing tests did not notice.

### Why the tests did not notice

The repository's test idiom is "write a small schema, bind it to whichever
language is at hand". `tests/test_grammar_nodes.py:16` binds the authored
`jsonlike` fixture to the real `tree_sitter_json` parser. `PROJECTION_SCHEMA`
at line 20 is a three-entry hand-written schema on the same real language.

That idiom made C2 look like ordinary practice. The fixtures normalised the one
thing the architecture forbids.

---

## 2. The concept

**Keep the distribution model. Replace trust with verification.**

The schema and the language are two independently versioned artifacts with no
link between them. Phase 025 tried to link them with metadata: a name, a
provenance file, a documented compatibility range. Metadata decays. The
repository's own flagship provenance record is already wrong.

The link is available in the artifacts themselves. A `tree_sitter.Language`
exposes its whole vocabulary:

```text
abi_version         node_kind_count      node_kind_for_id
semantic_version    node_kind_is_named   node_kind_is_visible
field_count         field_name_for_id    supertypes    subtypes
```

That is a large, precise subset of what `node-types.json` declares. The schema
and the language can therefore **check each other**, at bind time, with no name,
no sidecar file, no CLI, no network, and no Product B import.

This is the change: the runtime stops believing the schema and starts proving
it.

### Why this makes the 025 architecture correct rather than merely defensible

Application-owned artifacts are the right model only if the application cannot
get them wrong without being told. Today it can. With conformance, the
application owns a file and the runtime proves the file on every load. The
provenance record becomes a maintenance aid instead of the sole line of defence.

The same argument closes the rejected alternatives more firmly than 025 closed
them:

- **Ship schemas in Product A** — still wrong. The long tail is unbounded and
  the coupling inverts release cadence.
- **A schema-data package** — still wrong, but for a better reason. The review
  identified a variant 025 did not consider: per-grammar sidecar distributions,
  version-locked to each grammar wheel. That variant solves *acquisition*, which
  is already easy. It does nothing about *verification*, which is the real
  problem, and it multiplies maintained distributions. Once conformance exists,
  acquisition is one download and one provenance line.
- **Regenerate at runtime** — impossible, not merely costly. The ABI exposes the
  vocabulary. It does not expose the field-to-type relation, `required`, or
  `multiple`. Those are LR-analysis outputs from `node_types.rs`, discarded at
  compile time. No runtime work recovers them from a `.so`.
- **Infer a schema from consumer models** — still wrong. It destroys the closed
  universe.

---

## 3. Decision log

**D1 — Conformance is a bind-time check inside `Grammar.load`.** It runs where
the schema and the language first meet. It does not run at parse time.

**D2 — The check uses only tree-sitter ABI data.** No CLI, no network, no
Product B, no new artifact. The light wheel gains no dependency.

**D3 — Alien entries are a hard error.** A schema kind or field that the
language does not have proves the pair is wrong. This direction has no
legitimate cause.

**D4 — Missing kinds are a ratio, not a rule.** The language legitimately holds
kinds that `node-types.json` omits. Nix has one (`keyword`). A hard rule here
produces false positives on real grammars.

**D5 — Supertype entries are exempt from the existence check.** `node-types.json`
declares supertypes the compiled parser never exposes. Bash declares
`_expression`, `_primary_expression`, and `_statement`; only `_expression`
exists in the ABI.

**D6 — Use `Language.supertypes`, never `Language.node_kind_is_supertype()`.**
The per-id predicate is unreliable in tree-sitter 0.26.0. For bash it reports
226 of 280 ids as supertypes, including `word` and `for`. `Language.supertypes`
reports the correct single entry.

**D7 — Delete name inference.** It causes both failure directions. `schema_name`
stays as an opt-in extra check. An absent name becomes harmless.

**D8 — Conformance replaces the name check as the primary gate.** The name
comparison stays only when the caller supplies `schema_name` and the language
reports a name. It is no longer load-bearing.

**D9 — Provide one documented opt-out, `verify=False`.** Resolver unit tests
need synthetic schemas on real languages. Shipped artifacts must never use it.
Its docstring says so.

**D10 — The error stays `SchemaDriftError`.** The taxonomy does not grow. The
message carries a bounded sample of alien kinds, alien fields, and missing
kinds.

**D11 — Replace the example artifact with the real upstream file.** C2 is not
fixable by documentation. Conformance would reject the current file, so the fix
is a prerequisite, not a follow-up.

**D12 — Rebind synthetic-schema tests before enabling the check.** Otherwise the
suite fails for the right reason at the wrong time.

---

## 4. The check, and its validation

```python
def _conformance(schema: NodeSchema, lang: tree_sitter.Language) -> dict:
    # D6: Language.node_kind_is_supertype() is not reliable in tree-sitter
    # 0.26.0 (226/280 ids report True for bash). Language.supertypes is.
    lang_supertypes = {lang.node_kind_for_id(i) for i in lang.supertypes}
    lang_concrete = {lang.node_kind_for_id(i) for i in range(lang.node_kind_count)
                     if lang.node_kind_is_named(i)
                     and lang.node_kind_is_visible(i)} - lang_supertypes
    lang_fields = {lang.field_name_for_id(i)
                   for i in range(1, lang.field_count + 1)}

    # D5: supertype entries are exempt. node-types.json declares supertypes the
    # compiled ABI never exposes.
    schema_concrete = {t.type for t in schema.node_types
                       if t.named and t.subtypes is None}
    schema_fields = {f for t in schema.node_types for f in (t.fields or {})}

    missing = sorted(lang_concrete - schema_concrete)
    return {"alien_kinds":  sorted(schema_concrete - lang_concrete - lang_supertypes),
            "alien_fields": sorted(schema_fields - lang_fields),
            "missing_kinds": missing,
            "missing_ratio": len(missing) / max(len(lang_concrete), 1)}
```

Reject on any alien kind or alien field (D3). Reject when `missing_ratio`
exceeds 0.25 (D4).

### Measured verdicts

The five community grammars were built here with Product B from the vendored
sources, using the real CLI 0.25.3 and gcc.

| Pair | missing | alien kinds / fields | Verdict |
|---|---:|---|---|
| bash schema, bash language | 0 (0 %) | 0 / 0 | ACCEPT |
| rust schema, rust language | 0 (0 %) | 0 / 0 | ACCEPT |
| nix schema, nix language | 1 (2.4 %) | 0 / 0 | ACCEPT |
| markdown schema, markdown language | 0 (0 %) | 0 / 0 | ACCEPT |
| markdown-inline schema, its language | 0 (0 %) | 0 / 0 | ACCEPT |
| bash schema, rust language | 158 (96.9 %) | 54 / 9 | REJECT |
| rust schema, nix language | 36 (85.7 %) | 157 / 20 | REJECT |
| nix schema, markdown language | 51 (100 %) | 41 / 22 | REJECT |
| markdown schema, bash language | 58 (98.3 %) | 50 / 1 | REJECT |
| shipped 9-entry subset, python language (C2) | 114 (92.7 %) | 0 / 0 | REJECT |
| empty `[]`, python language (H3) | 123 (100 %) | 0 / 0 | REJECT |
| rust schema misnamed python (C1) | 111 (90.2 %) | 150 / 14 | REJECT |
| rust schema, nameless json language (C3) | — | 161 / 30 | REJECT |
| bash schema, nameless json language (C3) | — | 54 / 18 | REJECT |

Correct pairs sit at 0 % to 2.4 % missing with zero alien entries. Every
defective pair sits at 85.7 % to 100 %, and every wrong-grammar pair is caught
by the alien rule alone. The separation is about 35 times the threshold.

### A warning from the first attempt

The naive form of this check rejected bash, rust, and nix against their own
correct schemas. Three false positives out of five. D5 and D6 are the
corrections. Do not implement this from the concept alone. Validate against real
grammars at every step.

---

## 5. Phases

Each phase ends with its own gate. Do not start the next phase until the gate
passes.

### Phase 0 — record the baseline

Capture `pytest -q`, `pytest -q -W error`, `ruff check src tests examples`,
`ty check src`, doc snippets, and all four examples into
`evidence/baseline-20260909/`. Record exit codes.

**Gate:** the evidence directory holds one log and one exit file per command.

### Phase 1 — fix the example artifact (D11)

Replace `examples/wheel-extract/vendor/python-node-types.json` with the genuine
`node-types.json` from the `tree-sitter-python` 0.25.0 source distribution.

Update `python-node-types.provenance.json`:

- set `source_commit` to the upstream `v0.25.0` tag SHA;
- add `schema_sha256` of the schema file;
- add `grammar_semantic_version`, which is `(0, 25, 0)` for this wheel;
- correct or remove the `generation` claim.

Fix `examples/wheel-extract/README.md:3`, which says "vendors the small schema
slice it needs".

Regenerate `examples/wheel-extract/transcript.txt` with `--update`. Step 1 will
report the real kind count instead of 9. Read the diff before committing it.

**Gate:** `pytest -q tests/test_wheel_example.py` passes; the example exits 0
and matches its transcript.

### Phase 2 — rebind the synthetic-schema tests (D12)

`tests/test_grammar_nodes.py` binds the authored `jsonlike` fixture and
`PROJECTION_SCHEMA` to the real `tree_sitter_json` language. Conformance rejects
both.

Choose per test:

- build a matching synthetic language with Product B, as the community fixture
  tests already do; or
- pass the `verify=False` opt-out from D9, with a comment naming the reason.

Sweep the suite for the same idiom. `test_generate.py`, `test_nodes.py`, and
`test_schema.py` are the likely sites.

**Gate:** the full suite passes with the check present but disabled by a
temporary flag.

### Phase 3 — land the conformance check (D1 to D6, D8, D10)

Add `_conformance` and the verdict to `grammar.py`. Call it from `Grammar.load`
after `load_schema` and before `build_namespace`. Raise `SchemaDriftError` with
a bounded sample of each evidence set.

Keep the name comparison. Run it only when the caller gives `schema_name` and
the language reports a name.

**Gate:** the full suite passes. The twelve verdicts in section 4 reproduce as
tests.

### Phase 4 — delete name inference (D7)

Remove the file-name and parent-directory inference at `schema.py:280-286`.
`load_schema` sets `name` only from its `name=` argument.

Update `tests/test_schema_distribution.py:36`, which asserts the inferred name
and so pins the defect.

**Gate:** a correct schema at `vendor/node-types.json` binds without error.

### Phase 5 — close the smaller findings

- Export `SchemaMissingError`, `SchemaDataError`, and `SchemaDistributionError`
  from `pydantree_sitter/__init__.py`. Update the pinned surface test.
- Make `examples/wheel-extract/extract.py` use `Grammar.load(language, path,
  schema_name="python")`, matching its own README.
- Reject a zero-node-type schema in `load_schema` with `SchemaDataError`.
- Read schema files with `encoding="utf-8"` at `schema.py:138`, `276`, and
  `314`, and in `NodeSchema.write`.
- Reconcile the tree-sitter range. Either cap the light wheel at `<0.27` or
  correct the provenance file. Assert the decision in one place.
- Extract one `_parse_node_types(data)` helper. Three copies of the
  dict-or-list branch exist at `schema.py:139`, `288`, and `315`.
- Move the `find_spec` guard in `tests/test_wheel_schema_gap.py` outside the
  strict xfail, so the sentinel cannot stop watching in silence.

**Gate:** Ruff, ty, and the full suite pass.

### Phase 6 — documentation

- Correct `docs/user-guide.md:6-8`. The claim that `Grammar` rejects drift
  becomes true after Phase 3. State what the check proves and what it does not.
- Add remediation steps for each distribution error.
- Document the required provenance fields as a list.
- Record the conformance rule in `docs/architecture.md`, including D5 and D6.

**Gate:** `pytest -q tests/test_docs_snippets.py` passes.

### Phase 7 — final verification

Run the full gate set and all four examples. Record the output and exit codes in
`evidence/final-<date>/`. Write `FINDINGS.md` in this directory.

**Gate:** every command exits 0. The wheel transcript matches byte for byte.

---

## 6. Tests to add

| Test | Proves |
|---|---|
| `test_wrong_grammar_schema_rejected_even_when_filename_matches` | C1 |
| `test_wrong_grammar_schema_rejected_on_nameless_language` | C3, the ABI-14 case |
| `test_correct_schema_in_any_directory_binds` | H2, no false drift |
| `test_empty_schema_rejected` | H3 |
| `test_partial_schema_rejected` | C2, the subset class |
| `test_community_schemas_conform_to_their_languages` | no false positives, five real grammars |
| `test_supertype_entries_are_exempt` | D5, bash `_statement` |
| `test_provenance_hash_matches_the_schema_file` | provenance becomes a contract |
| `test_provenance_grammar_version_matches_the_installed_language` | provenance becomes a contract |

The five-grammar conformance test needs the CLI and gcc. Mark it `toolchain`.
Every other test runs without a toolchain.

---

## 7. Out of scope

- Any schema-data package, in any form.
- Any change to the two-product split.
- Any restoration of a deleted legacy API.
- Any path that binds without a schema.
- The `pattern` extra, and the deferred decision to remove it.
- Product B's authoring pipeline, except where the tests build fixtures.

---

## 8. Risks

- **The missing-ratio threshold is a heuristic.** It has about 35 times the
  headroom on the grammars measured here. A grammar that hides most of its kinds
  would trip it. `verify=False` is the escape, and the error message names the
  ratio.
- **Phase 2 is the real cost.** The number of tests that bind a synthetic schema
  to a real language is not yet counted. Count it before starting Phase 3.
- **`Language.node_kind_is_supertype()` may change behaviour.** D6 pins the
  workaround to tree-sitter 0.26.0. Recheck on any runtime bump.
- **ABI 16 is unverified.** No grammar outside ABI 14 and 15 was available for
  this work.
- **The upstream Python schema is not in the workspace.** Phase 1 must fetch it
  and then revalidate, because Phase 3 depends on it conforming.

---

## 9. What the review proved, and what it did not

**Proven here:** the wheel ships no schema; all five failure modes above; the
twelve conformance verdicts; toolchain-free operation with `tree-sitter`, `gcc`,
and `cc` absent from `PATH`; Product-A operation with Product B blocked at the
import system; generated modules inline their schema, so a later edit to the
schema file has no effect.

**Not proven:** behaviour on any tree-sitter runtime other than 0.26.0;
behaviour on any ABI other than 14 and 15; behaviour under a non-UTF-8 locale.

---

## 10. VCS

The workspace is OFF-CANONICAL. The `024-typed-node-universe` lane has one
change with several commits, and `gitman` refuses to start a lane or save until
its owner runs `gitman reconcile`. See the handoff note at the end of
[`../025-schema-distribution/FINDINGS.md`](../025-schema-distribution/FINDINGS.md).

This work needs a clean lane. Repair the VCS state first, or agree explicitly to
work in the current workspace and integrate later.
