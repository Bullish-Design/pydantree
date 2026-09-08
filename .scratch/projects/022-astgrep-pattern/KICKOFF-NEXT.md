# Kickoff — project 022 continuation: scoped patterns and Obsidian markdown

Paste everything below the line into a fresh session.

---

You are continuing work in `/home/andrew/Documents/Projects/pydantree`.

Read these first, in this order. They are the state of the world and they
contain measured facts you must not re-derive:

1. `.scratch/projects/022-astgrep-pattern/DESIGN-NEXT.md` — the plan. §2 is
   your brief.
2. `.scratch/projects/022-astgrep-pattern/IMPLEMENTATION.md` — six places the
   original concept did not survive contact with the engine.
3. `.scratch/projects/022-astgrep-pattern/FINDINGS.md` — the Phase 0 grammar
   agreement spike and its §4a addendum.
4. `docs/architecture.md` §7a and durable facts 9-15.
5. `src/pydantree_sitter/pattern.py`, `agreement.py`, `rules.py`, `syntax.py`.

`.scratch/projects/022-astgrep-pattern/CONCEPT.md` is the original spec. It is
wrong in six specific places, all catalogued in IMPLEMENTATION.md. Treat
CONCEPT as history and IMPLEMENTATION as truth where they disagree.

## What already exists and works

`pydantree_sitter.pattern` — structural search and rewrite wrapping
`ast-grep-py`, behind the optional `pattern` extra.

```python
lang = Language.from_module(tree_sitter_python)
pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=lang)
for m in pat.find_all(src):
    m.span, m.node, m.captures["NAME"], m.captures["ARGS"]
result = pat.replace_all(src, "def $NAME($$$ARGS) -> None: $$$BODY",
                         on_overlap="outermost", reindent=True, validate=True)
```

- `Rule` — a validated Pydantic model of ast-grep's rule object, with
  grammar-checked `kind`s and depth/width/length bounds.
- `agreement.py` — the char-to-byte boundary and the recorded grammar
  agreement, with `same_artifact` for registered bundles.
- `syntax.py` — the per-language validity check (`compile` for Python,
  `json.loads` for JSON).
- `Language.register_astgrep()` — hands a bundle's `grammar.so` to ast-grep
  via `register_dynamic_language`, so both engines load ONE artifact.

Suite: 486 passed, 1 skipped. `ruff` and `mypy` are clean on the 022 files.
Both tools already fail repo-wide on pre-existing issues (~959 ruff findings,
36 mypy errors, none in the 022 modules) — do not try to fix those, and do not
let them block you.

## Your task

Two pieces, in this order. Do NOT start the second before the first is green.

### Piece 1 — scoped patterns

Add the pattern-side analogue of `Extractor.extract_tree_scoped`
(`binding.py:341`): search WITHIN a node rather than over a whole document.

```python
pat.find_all_in(node, source)     # or whatever signature you can defend
```

Why it matters: it is the prerequisite for both remaining pieces of the
Obsidian work. tree-sitter-markdown is a two-parser design, so the Obsidian
inline grammar must run over the text span of each `inline` node the block
parser produced, and frontmatter needs a scoped YAML parse of the
`minus_metadata` node.

Design questions you must answer, not assume:

- ast-grep parses the whole source. Do you re-parse the node's text as a
  standalone document, or filter whole-document matches by containment?
  They differ: a fragment may not parse standalone, and containment keeps
  the parent context that `inside`/`follows` rules need. Measure before
  choosing, and record the answer.
- Byte offsets must stay ABSOLUTE with respect to the original document. A
  scoped parse produces offsets relative to the fragment, and every offset in
  this module is an absolute byte offset over UTF-8 (invariant 6). If you
  re-parse a fragment, you rebase; if you rebase, prove it with a non-ASCII
  test.
- `_Parse` currently indexes a whole document. Decide whether a scoped search
  reuses the outer `_Parse` (cheap, keeps §4.1 resolution exact) or builds its
  own.

### Piece 2 — Obsidian markdown

Measured facts, from `probe_markdown.py` and `evidence/markdown.json`. Do not
re-derive these:

- ast-grep ships `markdown` and `md` as built-in languages.
- Its BLOCK structure is rich and usable: `section`, `atx_heading`,
  `paragraph`, `list`, `list_item`, `block_quote`, `fenced_code_block` (with
  `info_string` / `language`), `minus_metadata` (YAML frontmatter),
  `task_list_marker_checked` / `_unchecked`.
- Block-level patterns work: `Pattern("# $TITLE")`, `Pattern("- $ITEM")`.
- The INLINE half is not parsed at all. An `inline` node's children are bare
  punctuation tokens. There is no `link`, no `emphasis`, no `wiki_link`.
- Therefore NONE of Obsidian's syntax is addressable today: `[[Wiki Link]]`,
  `![[Embed.png]]`, `#tag/nested`, `> [!note]`, `key:: value`, `^block-id`,
  `==highlight==`, `%%comment%%`.

Build, in this order:

**2a. Frontmatter — the free win, no new grammar.** `minus_metadata` holds
opaque YAML text. ast-grep ships `yaml`. A scoped parse of that node gives
typed frontmatter, and YAML's key/value pair shape is exactly what record mode
wants — so `PatternMatch.extract(Model)` works here with no new machinery.
This is the only place §10's `OutputModel` bridge works today for a document
format, and it validates Piece 1.

**2b. An Obsidian INLINE grammar**, authored with `pydantree_sitter_grammar`
and registered into ast-grep with `Language.register_astgrep()`. Keep it
small and bounded — it is the missing half of a two-parser design, not a whole
markdown grammar:

```
wiki_link      [[Target]]  [[Target|Alias]]  [[Target#Heading]]  [[Target#^block]]
embed          ![[Target]]
tag            #tag  #nested/tag
callout_marker [!note]  [!warning]-        (first inline of a block_quote)
inline_field   key:: value                 (Dataview)
block_id       ^abc123                     (end of a block)
highlight      ==text==
comment        %%text%%
```

Run it scoped over each `inline` node.

Do NOT try to pin ast-grep's built-in markdown against a separately-versioned
`tree-sitter-markdown` wheel. That reintroduces the two-parser divergence risk
that `register_astgrep()` makes optional. If you need markdown on both sides,
build markdown as a bundle and register it.

## Traps that will cost you hours if you skip them

These are all measured. They are in `docs/architecture.md` durable facts 9-15.

1. **`ast_grep_py` reports CHARACTER offsets** (`Pos.index`), never byte
   offsets. Convert with `agreement.char_to_byte_table`. Skipping it drops
   node agreement from 100% to 0.54% on non-ASCII source.
2. **`SgNode.replace()` does not expand metavariables** (0.42 and 0.45),
   unlike the CLI. `pattern.py` expands templates itself.
3. **`root_node.has_error` is weaker than the language's own parser.**
   `def f(a): x = 1\n    return x` has NO error node — tree-sitter reparents
   `return x` to module level — while CPython raises SyntaxError. It missed
   19 of 19 broken rewrites. Use `syntax.py`.
4. **pyo3 `PanicException` inherits from `BaseException`**, so `except
   Exception` does not catch it. Use `pattern._engine_errors`.
5. **`meta_var_char` must lex as an identifier in the target grammar**, or
   pattern strings do not parse and every search silently returns nothing
   (`$H` finds nothing in JSON). For a markdown-family grammar `$` is fine
   because the content is free-form text — but VERIFY it for your grammar
   rather than assuming.
6. **`register_dynamic_language` requires `extensions`** even though the
   shipped type stub marks it optional, and registration is PROCESS-GLOBAL.
7. **Never read `Point.row` / `Point.column`** — py-tree-sitter 0.26.0
   refcount bug. Build every `Span` through `Span.from_node`.
   `tests/test_point_access.py` enforces this over every package file.
8. **Record mode is pair-grammar-shaped.** `M(..., record=True)` needs a
   key/value pair kind. This is why §10's Python `function_definition`
   example cannot work, and why frontmatter (2a) can.
9. **Test file names collide.** `tests/test_patterns.py` and
   `tests/test_rules.py` already exist and belong to
   `pydantree_sitter_grammar`. The 022 files are `test_pattern_module.py`,
   `test_pattern_rules.py`, `test_pattern_agreement.py`,
   `test_pattern_roundtrip.py`, `test_pattern_dynamic.py`. Follow that.
10. **`match.py` is taken** — it is the `M()` ancestor-path matcher and has
    nothing to do with `pattern.py`. The two never import each other. In this
    codebase a *capture* is an `OutputModel` field binding and a
    *metavariable* is a `$NAME`; keep the words apart.

## How to work here

Environment — everything runs through devenv. There is no pip; uv only.

```bash
devenv shell -- python -m pytest -q          # ~90s
devenv shell -- ruff check <your files>
devenv shell -- mypy src
devenv shell -- python .scratch/projects/022-astgrep-pattern/spike_agreement.py
```

`ast-grep` (CLI 0.37.0, debugging only) and `ast-grep-py` (0.45.3, the
library) are BOTH in the shell and are DIFFERENT versions with independent
grammars. Never read library behaviour off the CLI.

Run scripts from the repo root: `devenv shell -- bash -c 'cd
/home/andrew/Documents/Projects/pydantree && python <script>'`. A bare
`devenv shell -- python <relpath>` resolves the path wrongly.

Repository culture, which you should follow:

- **Spike, measure, save evidence, then decide.** Every claim in this project
  is backed by a probe under `.scratch/projects/022-astgrep-pattern/` writing
  JSON to `evidence/`. Do the same. If you assert a behaviour, prove it.
- **All checks run at construction.** A built `Pattern` or `Extractor` either
  works or it raised. Do not defer a check to first use.
- **Warnings are data**, surfaced once at bind, never printed.
- **Errors: one class per failure kind, one raise site per message.**
- **Refuse rather than guess.** §4.1's exact-range rule and §8's overlap
  refusal both exist because a plausible wrong answer is worse than a loud
  failure. Keep that, but see the next point.
- **Be strict about what you CLAIM and generous about what you ATTEMPT.**
  The tiered validator and `on_overlap` exist because the first cut was
  strict about both and that made the tool less useful than it should be.
- **Writing style: Simplified Technical English.** Short sentences, active
  voice, one word for one meaning, no filler ("simply", "just", "note that").
  This applies to docstrings, comments, commit messages and your replies.
- Every offset is a BYTE offset over UTF-8. Say so in any docstring that
  names one.

Registering new package files: `src/pydantree_sitter/pyproject.toml` has an
explicit `force-include` list and `tests/test_packaging.py` asserts the wheel's
`.py` set equals the source directory's. Add your file there or the suite
fails.

## Version control

The repo law routes all VC through `gitman` (jj + colocated git). As of the
last session `gitman` was NOT on PATH, including inside `devenv shell`, and
the repo is jj-colocated with a detached HEAD. Check for `gitman` first; if it
is still missing, say so and ask before touching git yourself.

## Definition of done

- The full suite passes. `ruff` and `mypy` clean on the files you add.
- Probes and their `evidence/*.json` committed alongside the code.
- `docs/architecture.md` updated: module map, §7a, and any new durable fact.
- A findings document recording what you measured and every place the plan
  did not survive contact — including things that turned out to be wrong in
  DESIGN-NEXT.md. That document is the deliverable that makes the next
  session cheap.
