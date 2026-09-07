# Where project 022 should go next

> **Sections 1 and 2's step 1 are now IMPLEMENTED.** `syntax.py` carries the
> tier-3 seam; `replace_all` carries `on_overlap`, `reindent`, `single_node`
> and `validate`; `Language.register_astgrep()` carries dynamic registration.
> Tests: `tests/test_pattern_module.py`, `tests/test_pattern_dynamic.py`.
> What remains is scoped patterns and the Obsidian inline grammar (§2, steps
> 2 and 4).

Two questions, one answer each, both grounded in probes in this directory.

---

# 1. The rewrite gate is too blunt. Replace it, do not relax it.

## The problem

`Pattern._verify_reparse` refuses any rewrite whose edit does not occupy
exactly one node (IMPLEMENTATION.md §1.3a). It exists because tree-sitter's
`has_error` accepts source CPython rejects, and it caught 19 of 19 broken
rewrites. But it also forbids a legitimate and common thing:

```python
pat.replace_all(src, "$A = $B\nlog($A)")   # one statement -> two. Refused.
```

The gate cannot tell that apart from the broken case. Structurally they are
identical — two top-level nodes where there was one. The only difference is
that one is valid Python and the other is not, and **tree-sitter cannot see
that difference**.

## The fix: put the real parser behind a seam

Stop inferring validity from shape. Ask something that knows the language.

```python
Language.load(tree_sitter_python, syntax_check=compile_python)
```

A `syntax_check` is `Callable[[str], None]` that raises on invalid source.
Three tiers, in the order the module should try them:

| tier | check | strength | cost |
| --- | --- | --- | --- |
| 3 | the language's own parser (`compile`, `json.loads`) | exact | a dependency-free stdlib call for Python and JSON |
| 2 | tree-sitter `has_error` | weak — misses reparenting | free, universal |
| 1 | one-node edit sites | proxy — over-refuses | free, universal |

Python's tier-3 check catches all 19 broken rewrites AND admits all 35 valid
ones, because the 19 ARE `SyntaxError`s. It is strictly better than the
current gate in both directions.

So: **tier 2 always; tier 3 when the Language has one; tier 1 demoted from
default gate to opt-in `strict=True`.** A language with no tier-3 check
(markdown, an authored grammar) keeps tier 1 as its default, which is where
the conservative behaviour actually belongs — those are the cases with no
better answer available.

## Three more places the module is stricter than it needs to be

**Overlap.** `on_overlap="refuse" | "outermost" | "innermost"`, default
`refuse`. Refusing is right as a default and wrong as the only option: a
chained-call rewrite (`$O.$M($$$A)`) is an everyday ask and is simply
unavailable today.

**Indentation.** The `$$$BODY` collapse is not really a validity problem, it
is a splicing problem: ast-grep's templates are text-level and lose the
match's column. A `reindent=True` option that re-indents continuation lines
to the match's start column fixes the whole family at the cause. The
`ast-grep` CLI does not do this, so it is an addition, not a divergence.

**Dry runs.** `replace_all` already returns edits as data. Add
`validate=False` so a caller can get the edits and the diagnosis WITHOUT the
refusal, and decide for itself. The safety default stays on; the escape
hatch stops the tool being useless at the boundary.

The through-line: the module should be strict about what it CLAIMS and
generous about what it ATTEMPTS. Today it is strict about both.

---

# 2. Markdown and Obsidian

## What works today, for free

ast-grep ships `markdown` and `md` as built-in languages. `probe_markdown.py`
(`evidence/markdown.json`) measures what that buys:

```
section  atx_heading  paragraph  list  list_item  block_quote
fenced_code_block  info_string  language  minus_metadata (frontmatter)
task_list_marker_checked / _unchecked
```

Block-level patterns and rules both work:

```python
Pattern("# $TITLE", language=md)                       # 1 match
Pattern("- $ITEM", language=md)                        # 2 matches
Rule(kind="atx_heading", has=Rule(kind="atx_h2_marker"))
Rule(kind="fenced_code_block", has=Rule(kind="language", regex="^python$"))
```

That is already a real vault tool: retitle sections, rewrite task lists,
find every Python fence, read frontmatter blocks, restructure lists.

## What does NOT work, and why

**Every piece of Obsidian-specific syntax is invisible.**

```
[[Wiki Link]]   ![[Embed.png]]   #tag/nested   > [!note]   `= this.file`
```

None of them are nodes. tree-sitter-markdown is a TWO-parser design: the
block parser emits an opaque `inline` node and a separate inline parser is
supposed to run over it. ast-grep runs only the block half. Inside an
`inline` node there are no `link`, `emphasis` or `wiki_link` nodes — only
bare punctuation tokens (`[`, `[`, `]`, `]`).

So `[[Wiki Link]]` is four punctuation tokens and some text, and no rule can
address it.

## The way in: register a pydantree-built grammar into ast-grep

**CONCEPT §7 is wrong.** It says a grammar built by
`pydantree-sitter-grammar` "has no ast-grep support". `ast_grep_py` exports
`register_dynamic_language(langs: Dict[str, CustomLang])`, which takes a
plain tree-sitter shared library — exactly what `write_bundle` produces.

`probe_dynamic_language.py` (`evidence/dynamic_language.json`) proves it end
to end: one bundle, `grammar.so` loaded into BOTH engines, node sets
**identical**.

```python
register_dynamic_language({"obsidian": {
    "library_path": str(bundle / "grammar.so"),
    "language_symbol": "tree_sitter_obsidian",
    "extensions": ["md"],
    "meta_var_char": "$",       # must LEX as an identifier in the grammar
    "expando_char": "_",
}})
```

The consequence is larger than a feature. **§4's entire two-parser risk
disappears for a bundle-backed language**: one grammar, one revision, one
artifact, so agreement is not a measurement but a construction.
`GrammarAgreement` for such a language is `verified` by identity, and the
exact-range handoff cannot diverge.

That also reverses the project's own advice. Today §7 says a custom grammar
is the UNSUPPORTED case. It is the BEST-supported case.

## What to actually build for Obsidian

Do NOT write a whole Obsidian markdown grammar. Mirror tree-sitter-markdown's
own split and write only the missing half.

**An Obsidian INLINE grammar**, small and well-bounded:

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

Then run it SCOPED over each `inline` node the block parser produced. That is
the same shape as `Extractor.extract_tree_scoped`, which already exists — a
scoped Pattern is the analogue, and it is the natural next module-level
addition.

Two-level, one artifact each:

```
ast-grep markdown (built in)  ->  blocks, headings, lists, fences, frontmatter
pydantree obsidian_inline     ->  wikilinks, embeds, tags, callouts, fields
```

**Frontmatter is a third level.** `minus_metadata` is opaque YAML text.
ast-grep ships `yaml`, so a scoped parse of that node's text gives typed
frontmatter — and `OutputModel` record mode over YAML's pair shape is exactly
the case §10's bridge was built for. This is the one place the `.extract()`
bridge works today with no new machinery.

## Order of work

1. `register_dynamic_language` support on `Language` / `Pattern` — the seam,
   with the JSON bundle as its test. Small, and it unlocks everything else.
2. Scoped patterns (`Pattern.find_all_in(node)`), the analogue of
   `extract_tree_scoped`. Needed by both the inline grammar and frontmatter.
3. Markdown as a recorded agreement language (needs a `tree-sitter-markdown`
   wheel on pydantree's side, OR — better — skip it entirely by building
   markdown as a bundle and registering that, per §2 above).
4. The Obsidian inline grammar.

Step 3 is where the current design fights itself: pinning ast-grep's built-in
markdown against a separately-versioned `tree-sitter-markdown` wheel
reintroduces the two-parser risk that step 1 makes optional. Prefer bundles.

---

# 3. One defect found while probing

`ast_grep_py` raises pyo3 `PanicException` for an unsupported language, and
`PanicException` inherits from **BaseException**, not `Exception`. The
module's `except Exception` did not see it and a panic escaped the taxonomy.
Fixed by `_engine_errors` in `pattern.py`, which catches `BaseException` and
re-raises only `KeyboardInterrupt` / `SystemExit` / `GeneratorExit`. Test:
`test_a_rust_panic_stays_inside_the_taxonomy`.
