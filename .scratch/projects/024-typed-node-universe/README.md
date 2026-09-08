# 024 — the typed node universe

**Date:** 2026-09-08 · **Baseline:** 466 passed, 1 skipped, 46 deselected @ `b9cad4f`
(fast loop, `python -m pytest -q -m "not slow"`, ~55 s, in-devenv).

A high-level architecture pass, requested with the instruction to ignore all
prior "decisions" and "requirements" and optimise only for conceptual and
architectural purity.

## The finding

The library has **five separate languages for "a piece of syntax"** and none of
them unify:

| Spelling | Where it lives |
|---|---|
| `M("module", "function_definition")` | Product A ancestor path |
| `RawQuery("(module ...)")` | Product A escape hatch |
| `Pattern("def $NAME($$$ARGS)")` | the ast-grep layer |
| `class Pair(Rule): key: NamePath` | Product B authoring |
| `FunctionItem` from `codegen.py` | generated, and used by nothing |

Each carries its own vocabulary, checker, error class and doc section. Product A
exports **49 public names** across 5,959 lines (4,301 of them in the extraction
core this project rewrites). That is the mental overhead.

## The change

Make the **node type** the one noun. Generate a real class per node kind from
the node-schema. Both products then become directions across one type universe:
Product B compiles classes forward into a grammar, Product A binds classes
backward against an existing grammar.

This is ideas 1-4 of the brainstorm, which are one change:

1. Promote `codegen` output from a side feature to the core.
2. Unify Product A's `OutputModel` and Product B's `Rule` into one node class.
3. Delete record mode; annotations decide the shape.
4. Move value decoding onto the node class; delete `ValueMap`.

## Contents

- **`REFACTOR_GUIDE.md`** — the step-by-step plan. Decision log (D1-D16),
  target end-state, phases 0-9 with a per-phase validation gate and a per-phase
  cleanup list, the full deletion inventory (Appendix A), grep gates
  (Appendix B), the old-to-new migration table (Appendix C), and the deferred
  ideas with what they would delete next (Appendix E).

## Out of scope (deliberately)

Ideas 5-12 of the brainstorm. Appendix E of the guide records them, says why
each is deferred, and names what each would delete. Idea 9 (remove schema-less
mode) is **forced** by idea 1 and is therefore inside this project — see D5.
