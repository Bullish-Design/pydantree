# Project 022 — implementation record

**Status: complete.** Phase 0 GO (see `FINDINGS.md`), then steps 2-8 of
CONCEPT.md §14.

```
src/pydantree_sitter/rules.py       Rule + validators + bounds
src/pydantree_sitter/agreement.py   offsets, GrammarAgreement, the record
src/pydantree_sitter/pattern.py     Pattern/PatternMatch/Edit/ReplaceResult
src/pydantree_sitter/errors.py      + PatternError and its four children
src/pydantree_sitter/binding.py     + Language.astgrep_name
tests/test_pattern_rules.py         19 tests
tests/test_pattern_module.py        34 tests
tests/test_pattern_agreement.py     55 tests (incl. the §4 regression guard)
```

Suite: 455 passed, 1 skipped. `ruff` and `mypy` are clean on the new files.
Both were ALREADY failing repo-wide before this work (959 ruff findings, 40
mypy errors); this project added none and removed four mypy errors.

---

# 1. Where the concept did not survive contact

Six places. Each is a decision, not a workaround, and each is reversible.

## 1.1 ast-grep reports character offsets (§16)

The Phase 0 finding. `FINDINGS.md` §2 has the detail. §16 says "use them to
obtain byte offsets, then discard them"; there is no byte offset to obtain,
and the conversion is now `agreement.char_to_byte_table`.

## 1.2 `SgNode.replace()` does not expand metavariables (§8)

`ast_grep_py` returns the replacement template with its `$NAME` tokens
untouched. Verified on 0.42.0 and 0.45.3, and for every pattern form. The
`ast-grep` CLI expands correctly, so this is a gap in the Python binding.

`pattern.py` therefore expands templates itself. Two consequences:

- A `$$$NAME` sequence expands to the ORIGINAL source text spanning its first
  through last node, delimiters included. Joining node texts with a guessed
  separator would drop the commas and whitespace the caller wrote.
- The template's metavariables are checked against the rule's own
  `metavariables()` FIRST. §6 wanted the caller to be able to run that check;
  the module now runs it, and refuses an unbound name.

Checked against the reference: the CLI and this module produce byte-identical
output on the same rewrite.

## 1.3 §15's round-trip invariant needs a formatter — and asking that question found a bug

> "a replacement whose template equals the pattern must return
> `new_source == source`, for every corpus file"

Raw text equality is false, and the `ast-grep` CLI is no different:
`def $N($$$A): $$$B` over an indented block loses the newline and indent,
because the template puts a literal space where the source had a line break.

**The proposal — compare formatted forms — works, and it is now the test.**
`probe_format_roundtrip.py` measured it (`evidence/format_roundtrip.json`):

| | raw equality | after `ruff format` |
| --- | --- | --- |
| before the fix below | 28 / 54 | 35 / 54 |
| after | 28 / 35 | **35 / 35** |

But the interesting number is the one that did NOT move. The 19 cases that
formatting failed to rescue were not formatting noise: **they were broken
rewrites the module was returning as success.** See §1.3a. Once those are
refused, the formatted round trip is total.

`ruff` is a dev dependency and the check lives in
`tests/test_pattern_roundtrip.py`, never in the module — `pattern.py` is
language-generic and takes no formatter dependency. The module's own
guarantee is the stronger, formatter-free one: everything `replace_all`
returns parses with CPython (`test_every_surviving_rewrite_is_valid_python`).

## 1.3a §8.1's re-parse check was not sufficient — the bug the probe found

CONCEPT §8.1 calls the re-parse "the single strongest safety property the
module can offer its consumer". As specified — no NEW `ERROR` node — it is
not strong enough, because **tree-sitter's error recovery is weaker than the
language's own parser**:

```python
def f(a): x = 1
    return x
```

`root_node.has_error` is **False**. tree-sitter recovers by reparenting
`return x` to MODULE level, out of the function, and reports a clean tree.
CPython raises `SyntaxError: unexpected indent`. This is precisely the
"silently wrong" failure the project exists to prevent, sitting inside the
safety net itself.

Over this package's own source: `has_error` missed **19 of 19** broken
rewrites.

The fix is structural, not lexical. A replacement that produced valid code
occupies exactly one node in the result; one that leaked into its
surroundings does not. `Pattern._verify_reparse` now checks both, and the
edit-site check caught **19 of 19 with no false positive over 35 valid
rewrites**.

This makes a contract explicit that was previously implicit: **a replacement
is ONE syntactic unit.** A template expanding to two statements is now
refused. That is a real restriction, and it is the deliberate one — for a
caller that cannot inspect its own edit, a rewrite that half-applies is worse
than a rewrite that does not run. It is also consistent with §8's existing
refusal to resolve overlapping edits.

## 1.4 Relational operands default to `stopBy: "end"`

**This is the one deviation from ast-grep's own semantics, and it is worth a
second opinion.**

ast-grep's `stopBy` default is `"neighbor"` — the immediate parent, sibling
or child only. CONCEPT §3's own example,

```python
Rule(pattern="$OBJ.$METHOD($$$ARGS)", inside=Rule(kind="class_definition"))
```

reads as "anywhere inside a class" and, with ast-grep's default, matches
NOTHING. It returns an empty result set rather than an error.

For this module's consumer that is the worst possible answer: a model reads
"no matches" as "the code does not contain this", and acts on it. So a
relational operand that does not set `stop_by` gets `"end"`. The choice is
emitted explicitly in `to_astgrep()`, so it is inspectable and never hidden,
and `stop_by="neighbor"` restores ast-grep's default.

Reverse this by deleting `Rule._DEFAULT_STOP_BY` and the `setdefault` in
`to_astgrep`.

`stop_by` and `field` were also missing from §6's field list — ast-grep calls
a relational operand a `Relation`, which is a rule PLUS those two keys.

## 1.5 §10's `OutputModel` bridge does not work with the example it gives

The bridge itself is real and is implemented over `extract_tree_scoped`, as
§10 specifies. The EXAMPLE cannot work:

```python
class FunctionDef(OutputModel):          # from CONCEPT §3 and §10
    __match__ = M("function_definition", record=True)
    name: str = capture("name")
```

pydantree's record mode is defined over key/value **pair** grammars — it
looks for a `pair_kind` and value shapes under it. A Python
`function_definition` is not a pair shape, and binding this model raises
`ShapeError` before any pattern runs. The bridge works where record mode
works: JSON, and authored pair shapes such as the devenv-subset grammar.
`test_extract_scopes_a_record_model_to_the_match` proves it over JSON.

`PatternMatch.extract` now rejects a FIELD-mode model by name rather than
doing something surprising with it. Making the bridge work for field-mode
models means an anchored scoped variant of `extract_field`, which does not
exist today — that is a real follow-up, and it is the thing that would make
§10 true as written for Python.

## 1.6 §4.2's bind-time fixture probe is replaced by a recorded artifact

`FINDINGS.md` §4 argues this. `GrammarAgreement` is now committed evidence
(`agreement.AGREEMENT_RECORDS`) plus a bind-time check that the INSTALLED
dependency versions are the measured ones. A drift, or a language with no
record, produces `verified=False` and a warning — data on the object,
surfaced once, never printed.

---

# 2. Two smaller corrections

**Exact-range resolution keys on (start, end, KIND).** §4.1 says "find the
node whose `start_byte` and `end_byte` match exactly". Several nodes can
share one byte range — an `expression_statement` wrapping its expression is
the common case — so range alone would still require picking one, which is
the guess §4.1 forbids. Adding ast-grep's reported kind to the key makes the
lookup total. A range that exists with a different kind gets its own message.

**§15 cites "the existing hypothesis practice in `match.py`".** There is no
hypothesis in this repository and none in that file. The edit-arithmetic
property test generates its own cases from a fixed seed instead of adding a
dependency; it is reproducible and prints the failing case.

---

# 3. Test-file naming

`tests/test_patterns.py` and `tests/test_rules.py` already exist and belong to
`pydantree_sitter_grammar`. The new files are `test_pattern_module.py`,
`test_pattern_rules.py` and `test_pattern_agreement.py`. The §5 warning about
`match.py` being taken applies to the test tree too.

---

# 4. Environment

`devenv.nix` carries both halves:

- `pkgs.ast-grep` — the CLI, **0.37.0** from nixpkgs. A debugging tool only
  (`--debug-query` prints ast-grep's own parse of a pattern).
- `ast-grep-py>=0.39` — the library, resolved to **0.45.3** in `uv.lock`, in
  the root `dev` extra AND the `pydantree-sitter` `pattern` extra.

The two versions differ and carry independent grammars. Never read library
behaviour off the CLI. The root `dev` extra is the one that reaches the
managed venv, because devenv syncs with `--no-install-workspace`.

---

# 5. Follow-ups, in order of value

0. **Check the edit-site gate against a second language.** It was measured
   on Python only. The reasoning is language-generic, but tree-sitter's
   recovery behaviour is per-grammar, and the false-positive rate is the
   number that decides whether the one-syntactic-unit contract is
   comfortable.
1. **Scoped field-mode extraction**, so §10 is true for grammars without a
   pair shape. This is the gap between what §10 promises and what ships.
2. **A second language.** JSON binds and searches today but has no agreement
   record, so it warns. `measure_agreement` is the tool; a corpus is the
   work.
3. **A rewrite mode that resolves nesting** — outermost-only, say. Refusing
   overlap is correct and specified, but it makes a chained-call rewrite
   simply unavailable, and that is a common ask.
4. **`regex` runtime bounds.** `re.compile` succeeding says nothing about
   runtime, and the caller owns the timeout today. Untrusted input makes
   this real.
