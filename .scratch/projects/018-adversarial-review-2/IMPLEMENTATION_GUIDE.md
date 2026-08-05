# Pydantree — Implementation Guide (fixes for review 018)

This is a sequenced, do-this-then-that plan to resolve every finding in
`REVIEW.md`. It is ordered so that (a) you always have a green baseline to fall
back to, (b) every bug gets a **failing regression test first**, then the fix, and
(c) later steps depend only on earlier ones.

Finding IDs (A#, B#, P#) match `REVIEW.md`. Each step lists **files**, the **change**
(with code), the **test**, and a **verify** command.

Convention for every command below:
```
run() { devenv shell -- python -m pytest "$@"; }   # or: .venv/bin/python -m pytest
```

---

## Phase 0 — Safety net (do this before touching any source)

**0.1 Branch.**
```
git switch -c fix/review-018
```

**0.2 Pin the toolchain (fixes the invisible CLI-drift, part of B7).**
`devenv.nix` currently takes `pkgs.tree-sitter` unpinned, so the suite is green on
0.25.3 and red on 0.26.8. Pin it.
- In `devenv.nix`, replace the bare `pkgs.tree-sitter` package with a pinned
  0.25.3 derivation (an overlay or `tree-sitter` from a pinned nixpkgs rev), OR add
  a hard version assertion in `conftest.py` (see 0.3). Do **both** for belt-and-suspenders.

**0.3 Add a CLI-version guard test (turns silent drift into a loud, early skip/fail).**
New file `tests/test_toolchain_version.py`:
```python
import re, subprocess, pytest

SUPPORTED = {"0.25"}  # major.minor ranges the conflict/schema code is verified against

def _cli_mm():
    out = subprocess.run(["tree-sitter", "--version"], capture_output=True, text=True)
    m = re.search(r"(\d+)\.(\d+)\.\d+", out.stdout or out.stderr)
    return f"{m.group(1)}.{m.group(2)}" if m else None

@pytest.mark.toolchain
def test_cli_version_is_supported():
    mm = _cli_mm()
    assert mm in SUPPORTED, (
        f"tree-sitter CLI {mm} is outside the verified set {SUPPORTED}; "
        f"the conflict-report parser (conflicts.py) and the byte-for-byte "
        f"schema test are CLI-version-coupled — see REVIEW 018 §1.4/B7")
```
This is the structural defense §1.4 asks for. When you later support 0.26.x
(step 1.5.c), add `"0.26"` here.

**0.4 Baseline.** With the toolchain present:
```
run -q            # expect 232 passed, 1 skipped on 0.25.3
```
Record the number. This is your regression anchor.

---

## Phase 1 — Tier 1: wrong behavior & broken selling points

### Step 1.1 — B1 + B2: fix `_nullable` (analyzer correctness core)

**Test first** — new `tests/test_checks_nullable.py`:
```python
import pytest
import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar.checks import _nullable, _view

def _g():
    g = tg.Grammar("t"); g.rule("x", tg.pattern("a")); return g

@pytest.mark.parametrize("body_factory, expected", [
    (lambda: tg.field("p", tg.opt(tg.ref("x"))),        True),   # FIELD wrapper
    (lambda: tg.prec(1, tg.opt(tg.ref("x"))),           True),   # PREC wrapper
    (lambda: tg.alias("t", True, tg.opt(tg.ref("x"))),  True),   # ALIAS wrapper
    (lambda: tg.repeat1(tg.opt(tg.ref("x"))),           True),   # REPEAT1 of nullable
    (lambda: tg.repeat1(tg.ref("x")),                   False),  # REPEAT1 of non-nullable
    (lambda: tg.seq(tg.ref("x"), tg.ref("x")),          False),
])
def test_nullable_truth_table(body_factory, expected):
    g = _g(); view = _view(g)
    assert _nullable(body_factory().node if hasattr(body_factory(), "node")
                     else body_factory(), view, set()) is expected

def test_nullable_non_start_rule_catches_wrapped():
    g = _g()
    g.rule("params", tg.field("p", tg.opt(tg.ref("x"))))
    g.rule("loop", tg.repeat1(tg.opt(tg.ref("x"))))
    g.rule("source_file", tg.seq(tg.ref("params"), tg.ref("loop")))
    g.start("source_file")
    from pydantree_sitter_grammar.checks import check_nullable_non_start_rule
    flagged = {i.rule for i in check_nullable_non_start_rule(g)}
    assert {"params", "loop"} <= flagged
```
Run — it fails today.

**Fix** — `src/pydantree_sitter_grammar/checks.py`, `_nullable` (lines 191-211):
```python
    if isinstance(node, Repeat1Node):
        return _nullable(node.content, view, seen)   # was: return False
    ...
    if isinstance(node, SymbolNode):
        ...
    # transparent wrappers (FIELD / ALIAS / PREC* / TOKEN / IMMEDIATE_TOKEN /
    # RESERVED) are nullable iff their content is — mirror _first_set's fallback
    content = getattr(node, "content", None)
    if isinstance(content, RuleNode):
        return _nullable(content, view, seen)
    return False
```
Verify: `run -q tests/test_checks_nullable.py` green; then full `run -q`.

### Step 1.2 — A1: the bind checker must use the ValueMap, not the banned heuristic (D6)

**Test first** — add to `tests/test_schema.py` (or new `tests/test_valuemap_check.py`):
```python
from pydantree_sitter import M, OutputModel, Language
from pydantree_sitter.schema import NodeSchema
from pydantree_sitter.valuemap import ValueMap

def _json_like_schema_with_named_int():
    return NodeSchema.from_list([
      {"type":"document","named":True,"fields":{},"children":{"multiple":False,"required":True,"types":[{"type":"object","named":True}]}},
      {"type":"object","named":True,"fields":{},"children":{"multiple":True,"required":False,"types":[{"type":"pair","named":True}]}},
      {"type":"pair","named":True,"fields":{"key":{"multiple":False,"required":True,"types":[{"type":"ident","named":True}]},"value":{"multiple":False,"required":True,"types":[{"type":"qty","named":True}]}}},
      {"type":"ident","named":True},{"type":"qty","named":True}])

def test_committed_valuemap_is_authoritative_in_the_check():
    from pydantree_sitter.compiler import _scalar_of   # signature changes below
    schema = _json_like_schema_with_named_int()
    vm = ValueMap(scalars={"qty": "int"})
    # the checker must agree with the emitter: qty -> int (declared data wins)
    assert _scalar_of(schema, vm, "qty") == "int"
```
(You can't easily bind without a real `.so`; this pins the unit that broke. Add a
full record-extract integration test once you have a grammar with a named-int kind.)

**Fix** — `src/pydantree_sitter/compiler.py`:
1. Thread the ValueMap into the check path. `_scalar_of` (408-413) → consult the
   ValueMap first, fall back to the (memoized) heuristic only for unmapped kinds:
   ```python
   import functools

   @functools.lru_cache(maxsize=None)
   def _proposed(schema):                     # memoize: was recomputed per call
       from .valuemap import propose_value_map
       return propose_value_map(schema)

   def _scalar_of(schema, vm, kind):
       if vm is not None and kind in vm.scalars:
           return vm.scalars[kind]
       return _proposed(schema).scalars.get(kind)
   ```
   (`NodeSchema` is a pydantic model; if it isn't hashable for `lru_cache`, key on
   `id(schema)` via a manual dict instead.)
2. `_kind_coerces` (388) gains `vm`: `def _kind_coerces(schema, vm, target, kind)`
   and passes `vm` into `_scalar_of`. For the `str` branch, also treat
   `kind in vm.wrappers` (or `vm.scalars.get(kind)=="str"`) as text-yielding so the
   check matches record-mode emission.
3. Thread `vm` down from the callers that already hold it (`compiled.value_map`):
   `_check_field_bindings`, `_check_record_bindings`, `_check_type`,
   `_infer_field_kind` each take `vm` and pass it through. `_compile_field` /
   `_compile_record` already have `compiled.value_map` — pass it in.

Verify: new unit green; full `run -q` unchanged.

### Step 1.3 — B13 + B14: pipeline cache correctness

**Test first** — add to `tests/test_pipeline.py` (toolchain):
```python
@pytest.mark.toolchain
def test_cache_key_distinguishes_grammar_name(tmp_path):
    from pydantree_sitter_grammar.pipeline import build
    g = _tiny_builder_grammar()   # any minimal buildable IR
    m = g.build()
    r1 = build(m, cache_dir=tmp_path, grammar_name="alpha")
    r2 = build(m, cache_dir=tmp_path, grammar_name="beta")
    assert r1.so_path.exists() and r2.so_path.exists()
    assert r1.so_path != r2.so_path
```

**Fix** — `src/pydantree_sitter_grammar/pipeline.py`, `build()`:
1. B13 — fold `name` into the key (295-301):
   ```python
   key = f"{h}-{name}-{tc_digest}"
   if scanner is not None and scanner.exists():
       scanner_digest = hashlib.sha256(scanner.read_bytes()).hexdigest()[:12]
       key = f"{h}-{name}-{scanner_digest}-{tc_digest}"
   ```
2. B14 — the promote race (362-365): `os.rename` onto a populated dir raises
   `OSError(ENOTEMPTY)` on Linux, not `FileExistsError`:
   ```python
   try:
       os.rename(work, entry)
   except OSError:                      # ENOTEMPTY/EEXIST: a concurrent build won
       shutil.rmtree(work, ignore_errors=True)
       if not (entry / f"{name}.so").exists():
           raise                        # a real failure, not the race
   ```
Verify: new test green; `run -q`.

### Step 1.4 — B10: make the rule-class conflict sites point at the author's file

**Test first** — new `tests/test_rules_sites.py`:
```python
import sys, types
from pydantree_sitter_grammar.builder import site_of, _iter_body_nodes, as_node

AUTHOR_SRC = '''
from pydantree_sitter_grammar import Rule, assemble
class Name(Rule):
    __pattern__ = r"[a-z]+"
class Pair(Rule):
    key: Name
    value: Name
'''

def test_rule_class_nodes_point_at_author_file(tmp_path):
    f = tmp_path / "authorgram.py"; f.write_text(AUTHOR_SRC)
    mod = types.ModuleType("authorgram"); mod.__file__ = str(f)
    sys.modules["authorgram"] = mod
    exec(compile(AUTHOR_SRC, str(f), "exec"), mod.__dict__)
    g = mod.assemble("g", start=mod.Pair, rules=[mod.Name, mod.Pair])
    files = {site_of(n).file for n in _iter_body_nodes(as_node(g.rules["pair"]))
             if site_of(n) is not None}
    assert files == {str(f)}, f"sites leaked into internals: {files}"
```

**Fix** — `src/pydantree_sitter_grammar/rules.py`, `_stamp` (284-295): overwrite sites
that currently point into `rules.py` (that's why `_RULES_FILE` exists):
```python
    for n in _iter_body_nodes(as_node(body)):
        existing = site_of(n)
        if existing is None or existing.file == _RULES_FILE:
            n._site = site
```
Verify: new test green; `run -q`.

### Step 1.5 — B7 + CLI drift (conflict remapper robustness + schema drift)

**1.5.a — stop json-loading the whole stderr.** `src/pydantree_sitter_grammar/conflicts.py`,
`parse_conflict_json` (64-77): extract the JSON object rather than assuming stderr
is pure JSON (the CLI also emits flag warnings to stderr):
```python
def _extract_json_object(raw: str):
    start = raw.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == "{": depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    try: return json.loads(raw[start:i+1])
                    except json.JSONDecodeError: break
        start = raw.find("{", start + 1)
    return None

def parse_conflict_json(raw):
    data = _extract_json_object(raw)
    try:
        conflict = data["BuildTables"]["Conflict"]
    except (KeyError, TypeError):
        return None
    return Conflict(... as before ...)
```
Test: feed a stderr string with a leading `warning: ...` line + the JSON and assert
a `Conflict` is returned (`tests/test_conflicts.py`).

**1.5.b — B9:** in `conflicts._render` (129) coerce symbols: `", ".join(map(str, payload.get("symbols", [])))`.

**1.5.c — schema byte-for-byte drift on 0.26.x** (`test_bundle.py::...byte_for_byte`).
The shipped schema is already a byte copy of the CLI's node-types.json
(`pipeline._cache_node_schema` uses `shutil.copyfile`), so the *artifact* is correct.
The failing assertion is the library's **round-trip** (`NodeSchema.to_json()`) vs the
CLI file. Two honest options — pick one:
  - **(preferred, minimal)** Scope the round-trip test to the supported CLI range
    (skip it via the 0.3 guard when the CLI is outside `SUPPORTED`), since the
    shipped schema is the literal copy regardless.
  - **(if you want 0.26 support now)** Capture a 0.26.x `node-types.json` fixture,
    diff `NodeSchema.model_validate(...).to_json()` against it, and update
    `schema.py` (`NodeTypeInfo` fields, `_emit_node_type`, `_canonical_sorted`) to
    match 0.26's emission; then add `"0.26"` to `SUPPORTED` (0.3).

**1.5.d — B19:** fix the stale `build_builder` docstring (426-429) — it does NOT
re-run; it reuses the single `--json` run's stderr. Delete "re-runs with `--json`".

Verify: `run -q` on 0.25.3 green; on 0.26.8 the version guard now fails *loudly* at
`test_toolchain_version.py` instead of 7 scattered failures.

---

## Phase 2 — Tier 2: guarantees that silently don't hold

### Step 2.1 — A2: the sugar path must not recompile every call

**Test first** — `tests/test_extract.py`:
```python
def test_sugar_reuses_compiled_query(monkeypatch):
    from pydantree_sitter import emit
    import tree_sitter_json as tsj
    n = {"c": 0}; orig = emit.Query.compile
    def counting(self, lang):
        if self._compiled is None: n["c"] += 1
        return orig(self, lang)
    monkeypatch.setattr(emit.Query, "compile", counting)

    class Rec(OutputModel):
        __match__ = M("document", "object", record=True)
        a: int | None = None
    text = '{"a": 1}'
    for _ in range(5):
        Rec.extract(text, language=tsj)
    assert n["c"] <= 2, f"recompiled {n['c']}x for 5 identical sugar calls"
```

**Fix** — `src/pydantree_sitter/binding.py`, `_language_for` (74-82): memoize the
built `Language` for a given input when no explicit schema is supplied (the common
`Model.extract(text, language=module)` one-liner):
```python
import weakref
_LANGUAGE_CACHE: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()

def _language_for(language):
    if language is None:
        return None
    if isinstance(language, Language):
        return language
    try:
        cached = _LANGUAGE_CACHE.get(language)
    except TypeError:
        cached = None                     # unhashable/unweakable input
    if cached is not None:
        return cached
    lang, schema = _resolve_language(language)
    built = Language(lang, schema=schema)
    try:
        _LANGUAGE_CACHE[language] = built
    except TypeError:
        pass
    return built
```
(Modules, `tree_sitter.Language`, and the `.language` callable are weak-referenceable.
When the caller passes an explicit `schema=`, `_sugar_extractor` already builds a
transient Language — leave that path uncached, it's the explicit route.)
Verify: new test green (`n["c"] == 2`); full `run -q`.

### Step 2.2 — B15: stop discarding analyzer warnings

**Fix** — `src/pydantree_sitter_grammar/pipeline.py`:
1. Add a field to `BuildResult` (161-172): `warnings: list = field(default_factory=list)`
   (import `field` from dataclasses).
2. In `build()` (284-288) collect instead of discarding:
   ```python
   build_warnings = []
   if check:
       from .checks import assert_clean, warnings as check_warnings
       assert_clean(model)
       build_warnings = list(check_warnings(model))
   ```
   and set `warnings=build_warnings` on both `BuildResult(...)` returns.
3. **m7/B-analysis:** run checks against the builder `Grammar` (which has sites) in
   `build_builder` so warning messages cite the author's source — pass the collected
   warnings out, or run `check_warnings(g)` there and attach to the result.

**Test** — `tests/test_pipeline.py` (toolchain): a grammar with a mixed-precedence
CHOICE (a `check_precedence_mixing` warning) → `result.warnings` is non-empty.

### Step 2.3 — B16: bundle `abi` must match what was built

**Fix** — `src/pydantree_sitter_grammar/pipeline.py`, `write_bundle` metadata (232):
```python
"abi": _python_abi(),          # was: os.environ.get("TSGRAMMAR_ABI", "15")
```
so the bundle records the same ABI the cache key used. **Test:** build a bundle,
`json.loads(tree-sitter.json)["abi"] == str(tree_sitter.LANGUAGE_VERSION)`.

---

## Phase 3 — Tier 3: truth, dead code, elegance

### Step 3.1 — P1/P2/P3: root packaging & version truth

**Fix** — root `pyproject.toml`:
1. P2 — make the root a non-package so `uv run` stops trying to build a `pydantree`
   wheel:
   ```toml
   [tool.uv]
   package = false
   ```
   and remove `[build-system]` (and the `[project]` runtime `dependencies`/`readme`
   that imply a shippable dist). Keep only what the workspace root needs
   (`[tool.uv.workspace]`, `[tool.uv.sources]`, dev extras).
2. P1 — reconcile versions: the two dists and both `__init__.__version__` are
   `0.1.0`; drop the root `version = "0.1.2"` (or set `0.1.0`).
3. P3 — delete the stale comment block ("Phase 2 renames these … until then the
   workspace members keep the old names"; the duplicated "shared seam"/"Product A"
   line). Replace with a one-line accurate description.

**Test** — new `tests/test_metadata.py`:
```python
import tomllib, pathlib, pydantree_sitter, pydantree_sitter_grammar
ROOT = pathlib.Path(__file__).resolve().parents[1]

def _ver(p): return tomllib.loads((ROOT/p).read_text())["project"]["version"]

def test_dist_versions_agree():
    a = _ver("src/pydantree_sitter/pyproject.toml")
    b = _ver("src/pydantree_sitter_grammar/pyproject.toml")
    assert a == b == pydantree_sitter.__version__ == pydantree_sitter_grammar.__version__

def test_root_declares_no_distribution():
    root = tomllib.loads((ROOT/"pyproject.toml").read_text())
    assert root.get("tool", {}).get("uv", {}).get("package") is False
```
Verify: `uv run python -m pytest -q` now *starts* (P2 gone).

### Step 3.2 — P4/P5: wheel contents & doc drift

- P4 — light/heavy `pyproject.toml` `force-include "." = "..."` ships
  `pyproject.toml`/`README.md`/`PKG-INFO` inside the import package. Prefer an
  explicit include list (`scanners/*.c` for the heavy wheel) or a hatch
  `exclude` for `pyproject.toml`/`PKG-INFO` so build metadata stays out of the
  runtime namespace. Re-run `tests/test_packaging.py`.
- P5 — `docs/development.md`: "there is no `.venv` in the repo root" (there is —
  fix or remove); scanner/packaging examples show `force-include "." =
  "pydantree_sitter_grammar"` for the *light* package — correct to `pydantree_sitter`.
- §1.5 — `docs/architecture.md` §3.1 + `CONCEPT.md` §4.7/§5.2/§8/§9: move the wasm
  narrative to an explicit **"assessed — no-go"** appendix so the authoritative
  concept doc stops describing a capability that returns `WasmRuntimeUnavailableError`.

### Step 3.3 — Product A cleanups

- **A4** — `compiler.emitted_source` (122) / `spec.compiled_source` (421): the
  diagnostic must not raise the error you called it to inspect. Add `check=False`:
  ```python
  def emitted_source(model_cls, schema=None, *, check=False):
      ...
      if schema is not None and check:
          _check_path(model_cls, spec, schema)
  ```
  and have `compiled_source` call it with `check=False`. Test: `compiled_source(schema=bad)`
  returns a string, doesn't raise.
- **A5** — `emit.py` (259-293): delete the dead `_source`. Drop `self._source =
  root.text or b""` and the `source` param threaded into `MatchView`; remove
  `_source` from both `__slots__`. (`MatchView.text()` already uses `ns[0].text`.)
- **A6** — `schema.py` (155): index once. Add a `PrivateAttr` cache:
  ```python
  from pydantic import PrivateAttr
  _by_type_cache: dict | None = PrivateAttr(default=None)
  def by_type(self):
      if self._by_type_cache is None:
          self._by_type_cache = {t.type: t for t in self.node_types}
      return self._by_type_cache
  ```
  (Assumes `node_types` isn't mutated post-construction — true in this codebase.)
  Micro-bench `is_possible_descendant` on a large schema before/after.
- **A7** — dedupe the two identical `AmbiguousCaptureError` raises
  (`match.merge_group:125`, `materialize.build_kwargs:195`): route both through one
  helper `_raise_ambiguous(fname, cap, n)` so the message can't drift.
- **A8** — `materialize.extract_field` raw-query anchor fallback (242-247): make the
  anchor deterministic (first capture in the query's declared order, not dict
  order) and document that `source_meta()` on a raw query uses that capture.
- **A9** — `spec._try_resolve_forward_ref` (210-224): replace the `" | "` string
  hack with a real eval against the model's module globals
  (`eval(ref.__forward_arg__, vars(module))` guarded by try/except) so `A | B`
  forward refs resolve, not just `A | None`.
- **A10** — `codegen.py` (169-175): add a progress guard so a cyclic/undefined
  union dep can't infinite-loop:
  ```python
  while len(order) < len(union_defs):
      ready = sorted(...)
      if not ready:                      # unsatisfiable: emit the rest as-is
          for k, (name, rhs) in union_defs.items():
              if name not in emitted:
                  order.append((k, name, rhs)); emitted.add(name)
          break
      for k in ready: ...
  ```
- **A11 / §1.8** — collapse the language-normalizer cluster: `Language.__init__`
  (104-116) re-handles the `isinstance(lang, Language)` case that `_resolve_language`
  already handles. Pick one owner. Then do the import-layering pass (markers → spec
  → schema/valuemap → emit → compiler → match/materialize → binding) and lift the
  function-local imports to module top where the layering now allows it.

### Step 3.4 — Product B analyzer & DSL cleanups

- **B3** — `checks.py` `_GrammarView`: expose `reserved` and fold its symbol refs
  into `check_unused_rules`'s `used` set (so `g.reserved_word(ctx, ref("kw"))` isn't
  a false "unused"). Test with a reserved-word grammar.
- **B4** — `check_undefined_symbols` (278): also harvest string/token external names
  (`_external_name` from pipeline) into `external_names`, so `tok("NEWLINE")`
  externals referenced by name aren't false "undefined".
- **B5** — `check_precedence_mixing` (377): also inspect prec nodes nested in seqs,
  or downgrade the docstring to match the narrow (direct-CHOICE-member) scope it
  actually implements — don't claim more than it checks.
- **B6** — `check_alias_on_seq` (463) is `warning` while `builder.alias()` raises:
  make them one severity (recommend: analyzer error to match the builder), or
  document why imported IR is lenient.
- **B8** — `builder._production_symbols` (687): add a `ReservedNode` case
  (`return _production_symbols(node.content)`); note in the docstring that PATTERN/
  repeat rendering is approximate and falls back to the rule site.
- **B11** — `rules._child` multi-value `Literal` (259-264): field-wrap it so
  `op: Literal["+","-"]` becomes `field("op", choice("+","-"))`:
  ```python
  if origin is Literal:
      values = get_args(t)
      if len(values) == 1:
          return str(values[0])
      return _wrap(tg_choice(*[str(v) for v in values]), attr)
  ```
  (drop the pointless `toks = [...]; return toks[0]`.) Update the byte-identity gate
  fixture if it asserts the old anonymous shape.
- **B12** — `rules.assemble` External fallback (393-397, 414-415): a bodyless
  `External` should declare the external and give the rule an external-token body,
  not `tok("NAME")` (a literal-text token). Verify against a real External grammar
  (e.g. the `StringFragment` example) and fix the fallback so the emitted rule
  matches the scanner token, not the string "NAME".
- **B23 (expressions)** — `semantic_smoke` (204) passes `selector=expr` to `Corpus`
  but the compact renderer defaults `expr_kind="expr"`. Thread `expr` through:
  add an `expr_kind` field to `Corpus` (corpus.py ~268) and to `render_compact`
  (corpus.py:133), and pass `expr` from `semantic_smoke`. Test with an expression
  rule named something other than `"expr"`.
- **B24 (builder)** — `_only_whitespace` (111-117) recognizes a fixed literal set,
  so `pattern(r"[ \t\n]+")` as an extra doesn't suppress the injected `\s` default
  (→ two whitespace extras). Broaden the recognizer or detect "regex whose language
  ⊆ whitespace" more generally; test that a custom-whitespace extra prevents the
  default injection.
- **B21** — dedupe the ABI-15 literal (`pipeline.py:37` vs `ir.py:267` — one
  module-level constant); finish the env rename (`TSGRAMMAR_ABI` → `PYDANTREE_SITTER_ABI`
  with the old name honored as fallback, mirroring the cache-dir migration);
  `debug_states` (489) → `tempfile.TemporaryDirectory`; delete dead `generate()`
  wrapper and `Node = Rule` (builder.py:108) if truly unused.
- **word() guard** — `builder.word()` (438) lacks the "already set" guard
  `rule(word=True)` has; add it for symmetry.

### Step 3.5 — Product B pipeline & schema_tool cleanups

- **B17** — `detect_toolchain` (71-81): wrap each probe in
  `try/except (FileNotFoundError, OSError)` → `"unknown"`, so a missing CLI/gcc
  degrades instead of raising inside `build()`.
- **B18** — `_cache_node_schema` (241-263): when backfilling, regenerate in a
  `TemporaryDirectory` and copy only `node-types.json` in — never re-`generate`
  inside the immutable, content-addressed cache entry.
- **B20** — `language.load_language` (16-26) + `BuildResult.language()` return the
  `(language, lib)` tuple, but `parse()`/`Parser()` want a bare language. Return the
  language only and keep `lib` alive via a module-level registry:
  ```python
  _KEEPALIVE = []
  def load_language(so_path, grammar_name=None):
      from pydantree_sitter.loader import load_grammar_so
      language, lib = load_grammar_so(so_path, grammar_name)
      _KEEPALIVE.append(lib)
      return language
  ```
  Update the docstring; `BuildResult.language()` now returns something `parse()`
  accepts. Test `parse(result.language(), src)`.
- **B22** — `schema_tool.py`: delete `_grammar_name` (143, never called); remove the
  dead `grammar_json, _scanner = _resolve_grammar_json(...), None` (88, overwritten
  at 96); either forward `workdir=`/`keep=` from `build_community_bundle` (121) or
  drop the params; fix `main` (178-179) to write once and not leak the temp dir
  (call `derive_schema_for_dir(..., out=out)` without `keep=True`).

---

## Phase 4 — Tier 4: concept-level (design decisions, not just patches)

### Step 4.1 — §1.1/A3: decide the honest scope of the high-level surfaces
Two acceptable outcomes — **choose and document**:
- **(a) Grow `M()` one tier** toward the common next need. The highest-value
  addition is a *sibling/ordinal anchor* (extract a node relative to a sibling),
  which today forces `__raw_query__`. Design a marker (e.g. `M(..., before=..., after=...)`
  or a `Sibling(...)` predicate) that compiles to an emitted pattern, keeping the
  typed/checked path. Spike it against 3 realistic tasks before committing.
- **(b) State the narrow sweet spot** explicitly in `CONCEPT.md` §5 and the README:
  "M() covers anchored ancestor extraction; anything relational is `__raw_query__`,
  which is typed-checked only for capture↔field existence." Then **close the
  raw-query gap** partway (A3): run the capture↔type schema checks on raw-query
  captures too (you know each capture's field; you can look up its possible kinds),
  so the escape hatch keeps *some* of the differentiator.

### Step 4.2 — §1.4/B7: golden conflict-report corpus
Record real `tree-sitter generate --json` stderr for a handful of canonical
conflicts (shift/reduce, reduce/reduce, dangling-else) as checked-in fixtures, and
test `parse_conflict_json` + `GrammarConflictError._render` against them **without**
invoking the CLI. This defends B's raison d'être against CLI drift structurally
(pairs with the version guard from 0.3). Add a fixture per supported CLI minor.

### Step 4.3 — §1.6: record-mode determinism & honest scope
- `compiler._find_pair_kind` (514-523) picks `candidates[0]` (alphabetical) when a
  grammar has several key+value child kinds. Make it deterministic-and-explicit:
  raise a `ShapeError` naming the candidates and asking for an explicit
  `record_pair=`/`NodeKind` when >1, instead of silently guessing.
- Document record mode's real scope in the user guide: "a pair kind with `key`+`value`
  fields (JSON/INI-shaped); other document shapes use field mode or `__raw_query__`."

---

## Phase 5 — Close-out

**5.1 The discipline (prevents recurrence — this is the meta-fix from the review).**
Every "the code does X (F-A?, D?)" claim in a docstring is now a **test obligation**:
- Add the missing positive tests the audit named: `AmbiguousCaptureError` raise-path
  (`match.py:125`); a "one compiler" guard (assert field/record/raw all call
  `compile_spec`); the sugar recompile test (2.1); the rule-class site test (1.4);
  the ValueMap-authoritative test (1.2).
- Delete claims you won't test: fix `test_oracles.py:13-21` (it says F-A1/2/3 are
  `xfail(strict=True)` — there are no xfail markers) to describe the fixed,
  positively-tested reality.

**5.2 Full verification.**
```
run -q                                   # 0.25.3: green, higher count than baseline
uv run python -m pytest -q               # now starts (P2 fixed)
# spot-check the two products' surfaces still import cleanly:
python -c "import pydantree_sitter, pydantree_sitter_grammar"
```

**5.3 Update `docs/` counts and `REVIEW.md`.** Bump the "233 green" baseline in
architecture.md/development.md to the new number, and append a "resolved in 018"
note to this folder.

---

## Traceability — every finding maps to a step

| Finding | Step | Finding | Step | Finding | Step |
|---|---|---|---|---|---|
| A1 | 1.2 | A2 | 2.1 | A3 | 4.1(b) |
| A4 | 3.3 | A5 | 3.3 | A6 | 3.3 |
| A7 | 3.3 | A8 | 3.3 | A9 | 3.3 |
| A10 | 3.3 | A11 | 3.3 | B1 | 1.1 |
| B2 | 1.1 | B3 | 3.4 | B4 | 3.4 |
| B5 | 3.4 | B6 | 3.4 | B7 | 1.5 / 4.2 |
| B8 | 3.4 | B9 | 1.5.b | B10 | 1.4 |
| B11 | 3.4 | B12 | 3.4 | B13 | 1.3 |
| B14 | 1.3 | B15 | 2.2 | B16 | 2.3 |
| B17 | 3.5 | B18 | 3.5 | B19 | 1.5.d |
| B20 | 3.5 | B21 | 3.4 | B22 | 3.5 |
| B23 (smoke) | 3.4 | B24 (ws-extra) | 3.4 | P1 | 3.1 |
| P2 | 3.1 | P3 | 3.1 | P4 | 3.2 |
| P5 | 3.2 | §1.5 wasm doc | 3.2 | §1.7 perf | 3.3 (A5/A6) |
| §1.8 imports | 3.3 (A11) | CLI pin | 0.2/0.3 | discipline | 5.1 |

**Suggested commit cadence:** one commit per step (or per phase for the small
cleanups in 3.3–3.5), each with its regression test, message prefixed
`pydantree_sitter:` / `pydantree_sitter_grammar:` / `pkg:` / `docs:` per the project's
convention. Land Phase 1 first — those four are the only ones that produce *wrong
results*, not just bad messages.
