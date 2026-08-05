# Evidence — runtime verification of the [verified] findings (018)

All run from repo root with `.venv/bin/python`, `sys.path.insert(0,'src')`.

## A2 — sugar path recompiles every call
```
sugar Model.extract(language=module): 10 compiles for 5 identical calls
explicit reused Extractor        : 2 compiles for 5 identical calls
```
Instrumented `emit.Query.compile` to count first-time compilations. Record-mode
model has 2 queries (outer+inner) → 10 = 2×5 (fresh Language per sugar call);
persisted Extractor compiles both once = 2.

## A1 — D6 violated in the checker
```
propose_value_map (the heuristic) says qty -> str   (name regex misses 'qty')
checker _scalar_of(qty) = str                       (check path IGNORES the ValueMap)
```
Grammar with numeric leaf named `qty`; committed `ValueMap{scalars={'qty':'int'}}`.
Emission uses the ValueMap (qty→int); `compiler._scalar_of` (on the bind-check
path) uses `propose_value_map` → `str` → a record field `n:int` would raise a
false `SchemaCheckError`.

## A4 — diagnostic helper raises the error it should show
```
compiled_source(schema=) RAISED instead of showing source: SchemaCheckError
no-schema source ok: True
```
`Bad.compiled_source(schema=sch)` on a model with a bad `__match__` kind raises
`SchemaCheckError` instead of returning the derived `.scm`.

## A5 — dead `_source`
`grep 'self\._source'` in emit.py: assigned in `Cursor.__init__` (`root.text or
b""`) and `MatchView.__init__`, passed to MatchView — never read anywhere.
`MatchView.text()` uses `ns[0].text`, not `_source`.

## B1 / B2 — `_nullable` misses wrapped + repeat1 nullability
```
nullable(field("p", opt(x))) = False   (should be True)
nullable(repeat1(opt(x)))    = False   (should be True)
check_nullable_non_start_rule flagged: []   (should include params & loop)
```

## B10 — rule-class per-node sites point into library internals
```
_RULES_FILE referenced only at its definition line (grep: rules.py:76 only)
SEQ    site_file=rules.py
FIELD  site_file=rules.py
SYMBOL site_file=rules.py    <- should be the author's file (e.g. Pair.value)
```
Assembled a rule-class grammar defined in a synthetic module at
`/home/andrew/AUTHOR_FILE.py`; every annotation node's `_site.file` is `rules.py`.

## B14 — os.rename race catches the wrong exception (Linux)
```
os.rename(a, non_empty_b) -> PLAIN OSError (NOT FileExistsError), errno=39 ENOTEMPTY
```

## P1/P2/P3/P6 — packaging
```
root pyproject: name="pydantree", version="0.1.2", full [project] + build-system
light/heavy pyproject + both __init__.__version__: 0.1.0
grep pydantree_sitter_grammar in src/pydantree_sitter/: only docstrings/comments (A never imports B)
```

## Static: toolchain gating
13 of ~26 test files carry the `toolchain` marker (CLI+gcc); B's build behavior is
skipped in a toolchain-less run.
