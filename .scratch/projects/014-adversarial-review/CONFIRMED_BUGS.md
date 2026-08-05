# Confirmed bugs (live repros in this directory)

All reproduced against the current tree (199-passed baseline) with
`probe_findings.py`, `probe_nested_schema.py`, `probe_b_side.py`.

## A1 — Cross-language query-compile cache returns silent wrong results
`src/pydantree_sitter/dsl.py:244` (`Query.compile` caches `self._compiled` ignoring
`lang`) + `src/pydantree_sitter/typed.py:640` (`_derived_cache` is class-level).
A model extracted against language X then language Y reuses X's compiled
query. Repro: `Assign.extract(..., tree_sitter_python)` then
`Assign.extract(..., tree_sitter_json)` → **returns `[]` silently**; a fresh
identical model raises `QueryBuildError` as it should. This is exactly the
"silent empty result at runtime" failure class CONCEPT §7.1 claims the
project eliminates.

## A2 — Schema binding breaks nested record models
`src/pydantree_sitter/typed.py:996-1006` (`_record_kwargs`): nested models recurse
with `b.nested._derived_cache` (the schema-LESS derivation, whose inner
query never captures `@__anchor__`) while passing the OUTER `record_kind`.
The anchor filter `if not anc or anc[0].id != rec.id: continue` then drops
every nested match. Repro: Person/Address over JSON — works schema-less,
raises `ExtractionError: Field required (city)` with the schema bound.
Binding the schema (the flagship differentiator) breaks working extraction.

## A3 — NodeKind tuple alternation silently dropped in field mode
`src/pydantree_sitter/typed.py:426` (`k = kind.kinds[0]`) and
`src/pydantree_sitter/schema.py:469` (`return override[0]`). `NodeKind(("true",
"false"))` docstring promises one pattern per kind; field mode emits only
`(true)` — rows whose node is `false` are silently excluded. Repro: 2
assignments, 1 row returned.

## A4 — Job-2 stubs are typing fiction with no runtime
`src/pydantree_sitter/stubs.py` emits `.pyi` accessors (`fn.name()`, `.get("name")`,
`.children("kind")`) that do not exist on `tree_sitter.Node`. mypy passes
(tests/test_stubs.py is mypy-only); executing the type-checked code raises
`AttributeError`. "Typed node access" currently type-checks programs that
crash.

## B1 — `g.rule(..., alias="y")` emits garbage
`src/pydantree_sitter_grammar/builder.py:363-364`: appends the alias NAME to the
grammar-level `inline` list (no rule of that name exists) and emits no
AliasNode. Repro: `build().inline == ['pretty']`, no alias anywhere.

## B2 — Multi-value `Literal["+", "-"]` in rule classes
`src/pydantree_sitter_grammar/rules.py:312` top-level: raises raw `ValueError: too many
values to unpack (expected 1)`. `rules.py:282` nested: silently drops all
but the first value. Natural semantics (choice of anonymous tokens) is
neither implemented nor cleanly rejected.

## B3 — `_snake` mangles acronyms
`HTTPServer -> h_t_t_p_server`, `JSONValue -> j_s_o_n_value`
(`src/pydantree_sitter_grammar/rules.py:83`).

## B4 — Author's own whitespace extra doesn't suppress the `\s` default
`src/pydantree_sitter_grammar/builder.py:428-430` only recognizes the exact pattern `\s`;
`g.extra(tg.pattern(r"[ \t]+"))` still gets `\s` prepended → overlapping
extras the author explicitly tried to control.

## Misc (verified by reading, no probe needed)
- `typed._extract_tree` prints binding warnings to stderr with `print()` on
  EVERY extract call (probe 4: 3 calls → 3 prints). Should be
  `warnings.warn` (once) or logging.
- `schema_derive` cache keyed by `language_name or "?"`
  (`typed.py:646`, `schema.py:344`): two nameless languages with different
  schemas collide on "?"; same-name grammar with an updated schema is
  never re-derived.
- `pydantree_sitter.Language.load_bundle` (`typed.py:729-735`) drops `bundle.lib`,
  violating pydantree_sitter.loader's own stated keep-alive contract
  (`loader.py:53`). Harmless in CPython today (ctypes never dlcloses) but
  the contract and the code disagree.
- Two distinct `ExtractionError` classes exist (`typed.py:1055`,
  `materialize.py:285`); `Query.extract()` raises the materialize one,
  `pydantree_sitter.ExtractionError` is the typed one — `except pydantree_sitter.ExtractionError`
  does not catch DSL-path failures.
- Two distinct `OutputModel` classes exist (`typed.py:602`,
  `materialize.py:38`); `__init__.py` imports both (one under an unused
  alias).
- `derive_schema_for_dir(workdir=..., keep=False)` `shutil.rmtree`s a
  CALLER-supplied directory (`schema_tool.py:129`); same in
  `build_community_bundle`.
- `schema_tool.py:100`: dead assignment immediately overwritten at :108.
- `corpus.py:246`: `cache_dir = cache_dir or default_cache_dir()` — dead.
- `assemble()` requires module-level rule classes (function-local classes →
  misleading "no rule classes found in module '__main__'" error), and
  sweeps EVERY Rule subclass bound in the module namespace (imports
  included) into the grammar.
- `pydantree_sitter/__init__.py` docstring: "One module, no more: pydantree_sitter.schema" —
  false; loader.py/_ir_derive.py/_wasm_bridge.py all live there and
  loader is load-bearing for A.
- `Language.reparse(old_source=...)` parameter accepted and ignored
  (`typed.py:757`).
- `expressions.py` module docstring shows `g.expression(...)` — no such
  method exists (free function `expression(g, ...)`); DEFAULT_PRECEDENCE_CORPUS
  expected-renders differ between docstring and constant.
