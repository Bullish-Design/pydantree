# Typed node universe baseline and final measurement

Date: 2026-09-08

## Baseline

The Phase-0 baseline was measured at commit `b9cad4fae65ab44119a74b1e85af9dcf085de17b`:

```text
fast loop: 466 passed, 1 skipped, 46 deselected, 47 warnings
pydantree_sitter.__all__: 49
pydantree_sitter_grammar.__all__: 99
Product A total: 5,959 lines
Product A extraction core: 4,301 lines
Product A ast-grep layer: 1,658 lines
Product B: 4,092 lines
src/ total: 10,051 lines
```

## Final Phase-7–9 measurement

Final lane measurement: 2026-09-08, after the complete implementation and
verification run.

```text
full suite: 343 passed, 1 xfailed in 42.29s
warnings-as-errors fast loop: 325 passed, 18 deselected, 1 xfailed in 41.04s
pydantree_sitter.__all__: 12
pydantree_sitter_grammar.__all__: 99
Product A total: 3,879 lines
Product A extraction core: 2,239 lines
Product A ast-grep layer: 1,640 lines
Product B: 4,045 lines
src/ total: 7,924 lines
```

Per-file final counts:

| File | Lines |
|---|---:|
| `pydantree_sitter/__init__.py` | 44 |
| `pydantree_sitter/agreement.py` | 312 |
| `pydantree_sitter/codecs.py` | 49 |
| `pydantree_sitter/emit.py` | 5 |
| `pydantree_sitter/errors.py` | 144 |
| `pydantree_sitter/find.py` | 170 |
| `pydantree_sitter/generate.py` | 321 |
| `pydantree_sitter/grammar.py` | 172 |
| `pydantree_sitter/loader.py` | 198 |
| `pydantree_sitter/match.py` | 35 |
| `pydantree_sitter/nodes.py` | 689 |
| `pydantree_sitter/pattern.py` | 937 |
| `pydantree_sitter/raw.py` | 93 |
| `pydantree_sitter/rules.py` | 308 |
| `pydantree_sitter/schema.py` | 270 |
| `pydantree_sitter/span.py` | 49 |
| `pydantree_sitter/syntax.py` | 83 |
| `pydantree_sitter_grammar/__init__.py` | 206 |
| `pydantree_sitter_grammar/builder.py` | 792 |
| `pydantree_sitter_grammar/checks.py` | 580 |
| `pydantree_sitter_grammar/conflicts.py` | 201 |
| `pydantree_sitter_grammar/corpus.py` | 317 |
| `pydantree_sitter_grammar/expressions.py` | 246 |
| `pydantree_sitter_grammar/ir.py` | 286 |
| `pydantree_sitter_grammar/language.py` | 42 |
| `pydantree_sitter_grammar/patterns.py` | 82 |
| `pydantree_sitter_grammar/pipeline.py` | 685 |
| `pydantree_sitter_grammar/rules.py` | 424 |
| `pydantree_sitter_grammar/schema_tool.py` | 174 |
