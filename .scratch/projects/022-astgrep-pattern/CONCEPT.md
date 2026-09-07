# Pattern matching and structural rewrite for pydantree-sitter

## Concept and implementation blueprint — project 022

**Status:** IMPLEMENTED. Phase 0 gate passed (`FINDINGS.md`); the module
ships. Six places where this document did not survive contact with the
engine are recorded in `IMPLEMENTATION.md` — read that alongside this one,
because §8, §10, §15 and §16 are each wrong in a specific way.
**Product:** `pydantree-sitter` (`src/pydantree_sitter/`)
**New module:** `pydantree_sitter/pattern.py`
**Engine:** `ast-grep-py`, behind an optional extra
**Consumer:** `codeman` — the code toolset of the constrained local agent
runtime (Projects/.scratch/projects/024)

---

# 1. Executive summary

pydantree-sitter extracts **typed records** from source. A model declares a
path, and the extractor returns validated rows. That surface is complete and
it answers one question: "give me every X in this file, as a model".

It does not answer the two questions a coding agent asks:

```text
Where is this shape?          -> structural search
Change this shape to that.    -> structural rewrite
```

Those need a pattern language, metavariable binding, and text rewriting.
ast-grep has all three, proven over years of edge cases.

This project adds a `pattern` module. It **wraps ast-grep, and does not
reimplement it**. pydantree contributes what ast-grep does not have:

1. **Pydantic-modeled rules.** The caller sends a validated `Rule` object, not
   a free string. The rule is checkable before it runs.
2. **Typed match results.** A match carries a `Span`, a re-resolved
   `tree_sitter.Node`, and named captures. It serializes.
3. **The bridge to `OutputModel`.** A match scopes an extraction:
   `m.extract(Model)`. The seam already exists —
   `Extractor.extract_tree_scoped` (`binding.py:341`).
4. **Edits as data.** A rewrite returns `Edit` records. The caller applies
   them. The module performs no file input or output.

Point 1 is the reason this project exists. The consumer is an untrusted
language model. A validated rule object is a **semantic capability**; a raw
pattern string is closer to an argument vector. See §11.

---

# 2. Scope

## In scope

```text
Pattern         a compiled pattern or rule, bound to a Language
Rule            a Pydantic model of ast-grep's rule object
PatternMatch    span + node + captures + extract()
Edit            a byte-range replacement
find / find_all / replace_all
grammar agreement checking at bind time
the error taxonomy additions
```

## Out of scope

```text
file walking            file input or output      .gitignore handling
the ast-grep CLI        sgconfig.yml              YAML rule files
the ast-grep LSP        rule packs                fix suggestions
multi-file operations   custom pydantree grammars (see §7)
```

The module is text in, data out. `codeman` owns paths, walking, and writing.

---

# 3. The public surface

```python
from pydantree_sitter import Language, Pattern, Rule

lang = Language.from_module(tree_sitter_python)

# a pattern string
pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=lang)

for m in pat.find_all(source):
    m.span                 # Span — the existing type
    m.node                 # tree_sitter.Node, in pydantree's own tree
    m.text                 # str
    m.captures["NAME"]     # Span
    m.captures["ARGS"]     # tuple[Span, ...] for $$$ captures
    m.extract(FunctionDef) # list[OutputModel], scoped to this match

# a validated rule object
rule = Rule(
    pattern="$OBJ.$METHOD($$$ARGS)",
    inside=Rule(kind="class_definition"),
    not_=Rule(pattern="self.$METHOD($$$ARGS)"),
)
pat = Pattern(rule, language=lang)

# rewrite — edits as data, never applied in place
result = pat.replace_all(source, "def $NAME($$$ARGS) -> None: $$$BODY")
result.count      # int
result.edits      # tuple[Edit, ...]
result.new_source # str, the edits applied
```

`Pattern` mirrors `Extractor`: **all checks run once, at construction.** This
is the repository's core idiom (`binding.py`, §4.2 of project 014). A built
`Pattern` either works or it raised.

---

# 4. The central risk: two parsers

**Read this section before writing code. It decides the project.**

`ast-grep-py` vendors its own tree-sitter grammars, compiled into its wheel.
pydantree parses with `tree_sitter_python` 0.25.0, or with a bundle built by
`pydantree-sitter-grammar`. Two parses of one source, from two grammar
revisions.

Grammar revisions change node kind names and node boundaries. If the two trees
disagree, a byte range from ast-grep resolves to a different node in
pydantree's tree, or to no node at all.

The failure mode is the one `binding.py` already names about incremental
reparse: **silently wrong**. A match resolves to a plausible neighbouring node,
extraction succeeds, and the row is incorrect.

## 4.1 The handoff rule

```text
ast-grep finds.   pydantree resolves.   Disagreement is an error, never a guess.
```

Concretely:

1. ast-grep matches, and yields byte ranges for the match and every capture.
2. pydantree parses the same bytes with its own Language.
3. For each range, find the node whose `start_byte` and `end_byte` match
   **exactly**.
4. No exact node means `PatternResolutionError`. Do not fall back to the
   smallest enclosing node. Do not warn and continue.

An exact-range requirement is strict on purpose. It converts a silent
correctness bug into a loud, reproducible failure with a byte offset in the
message.

## 4.2 Agreement checking at bind time

`Pattern.__init__` runs a **grammar agreement probe** once per Language, and
caches the outcome on the Language instance — the same pattern
`Language.extractor` uses for compiled state.

The probe:

```text
parse a fixed per-language fixture with ast-grep
parse the same fixture with the bound Language
compare the full (kind, start_byte, end_byte) node sets
```

Report the result as data:

```python
class GrammarAgreement(BaseModel):
    language: str
    astgrep_version: str
    astgrep_grammar_kinds: int
    pydantree_grammar_kinds: int
    fixture_nodes: int
    exact_matches: int
    kind_mismatches: tuple[str, ...]
    range_mismatches: tuple[tuple[int, int], ...]

    @property
    def digest(self) -> str: ...   # stable hash of the whole record
```

Full agreement means the module runs unrestricted. Partial agreement means
`Pattern` construction emits a bind warning naming the divergent kinds —
warnings are data on the object, surfaced once, never printed (§4.2 of project
014). Gross disagreement means `Pattern` construction raises.

`GrammarAgreement.digest` goes into every result. §11 explains why.

---

# 5. Module layout

```text
src/pydantree_sitter/
  pattern.py        Pattern, PatternMatch, Edit, ReplaceResult
  rules.py          Rule — the Pydantic rule model
  agreement.py      GrammarAgreement, the probe, the fixtures
  errors.py         extended (§9)
  __init__.py       extended exports
```

`match.py` is **taken**. It holds the ancestor-path matcher for `M()` specs.
Do not add to it, and do not rename it. The new module is `pattern.py`, and the
two never import each other.

Naming discipline, per the repository's own rule of one word for one meaning:

| Term | Meaning |
| --- | --- |
| `match` (existing) | an `M()` ancestor path over a tree-sitter query |
| `pattern` (new) | an ast-grep pattern or rule |
| `PatternMatch` | one result of a pattern |
| `capture` (existing) | an `OutputModel` field binding |
| `metavariable` | a `$NAME` in a pattern |

`PatternMatch.captures` holds metavariables. This is the one place the two
vocabularies touch, and the docstring must say so.

---

# 6. `Rule` — the validated rule model

ast-grep's rule object is a nested dictionary. Model it in Pydantic.

```python
class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # atomic
    pattern: str | None = None
    kind: str | None = None
    regex: str | None = None

    # relational
    inside: "Rule | None" = None
    has: "Rule | None" = None
    precedes: "Rule | None" = None
    follows: "Rule | None" = None

    # composite
    all_: tuple["Rule", ...] | None = Field(None, alias="all")
    any_: tuple["Rule", ...] | None = Field(None, alias="any")
    not_: "Rule | None" = Field(None, alias="not")

    def to_astgrep(self) -> dict: ...
    def metavariables(self) -> frozenset[str]: ...
```

`all`, `any`, and `not` are Python keywords. Use trailing-underscore fields
with aliases, and populate by alias, so JSON stays idiomatic ast-grep.

Validators to write:

- at least one atomic or composite key is set;
- `regex` compiles;
- `kind` exists in the bound Language's `NodeSchema`, when a schema is bound.
  This reuses the existing schema seam and it is the check with the highest
  value — it rejects a typo before any parsing happens.

`metavariables()` supports the caller's own checks. `codeman` uses it to verify
that a replacement template references only metavariables the rule binds. That
check belongs to the caller, and the method exists to make it one line.

## 6.1 Depth limit

Recursive models with a model-supplied payload need a bound. Reject nesting
deeper than a fixed limit — 8 is generous for real rules. Untrusted input is
the design assumption.

---

# 7. Language support

ast-grep supports a fixed set of languages, compiled into its wheel. pydantree
supports any grammar its builder produces. These sets are not the same, and the
mismatch must be explicit.

```python
class Language:
    @property
    def astgrep_name(self) -> str | None:
        """The ast-grep language identifier, or None if unsupported."""
```

Resolution order:

1. an explicit `astgrep_name=` given to `Language.load` / `from_module`;
2. a bundle metadata key `astgrep_name`;
3. a small built-in mapping from `Language.name`.

`None` means `Pattern(..., language=lang)` raises `UnsupportedLanguageError`,
naming the language and listing the supported set. A custom grammar built by
`pydantree-sitter-grammar` has no ast-grep support, and the message must say
that plainly rather than implying a missing install.

**Ship v1 with Python only.** JSON second. The agreement probe needs a real
fixture per language, and a fixture is the expensive part.

---

# 8. Rewrite

```python
class Edit(BaseModel):
    start_byte: int
    end_byte: int
    new_text: str

class ReplaceResult(BaseModel):
    count: int
    edits: tuple[Edit, ...]
    new_source: str
    agreement: str          # GrammarAgreement.digest
```

Rules:

- **Never write a file.** Text in, text out.
- **Reject overlapping edits.** Sort by `start_byte`, verify no overlap, raise
  `PatternRewriteError` if any two overlap. Overlap means the pattern matched
  nested occurrences, and the correct behaviour is to refuse, not to pick.
- **Apply right to left**, so earlier offsets stay valid.
- **`count` is authoritative.** The caller compares it against its own expected
  count. `codeman`'s `expected_matches` contract depends on this number being
  the true match count, before any edit is applied.
- **Bytes, not characters.** Every offset in this module is a byte offset.
  Source is UTF-8. Say so in every docstring that names an offset.

## 8.1 Re-parse verification

After applying edits, parse `new_source` with the bound Language. If the parse
produces an `ERROR` node that the original did not, raise
`PatternRewriteError`. A rewrite that breaks the syntax tree is a defect, and
the caller — an agent making an edit it cannot inspect directly — has no other
way to learn this.

This check is cheap and it is the single strongest safety property the module
can offer its consumer. Do not make it optional.

---

# 9. Errors

Extend the taxonomy in `errors.py`. Follow its existing rules: one class per
failure kind, and one raise site per message.

```text
PydantreeSitterError
  PatternError                    new base
    PatternBuildError             ast-grep rejected the pattern or rule
    PatternResolutionError        a byte range did not resolve exactly (§4.1)
    PatternRewriteError           overlapping edits, or a broken re-parse
    UnsupportedLanguageError      no ast-grep grammar for this Language
```

`PatternResolutionError` carries the byte range, the pattern index, the
nearest node kind, and the `GrammarAgreement.digest`. That is enough to
reproduce the divergence without the original session.

---

# 10. The `OutputModel` bridge

The payoff of putting this in pydantree rather than in `codeman`.

```python
class FunctionDef(OutputModel):
    __match__ = M("function_definition", record=True)
    name: str = capture("name")
    line: int = source_meta()

pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=lang)
rows = [m.extract(FunctionDef) for m in pat.find_all(src)]
```

`PatternMatch.extract(Model)` calls `lang.extractor(Model).extract_tree_scoped(
self.node, self.tree)`. That method already exists and already does the right
thing: the node **is** the record, and the outer anchored path is not
re-verified.

This composes the two halves cleanly. ast-grep locates by shape. pydantree
types the result. Neither does the other's job.

Keep the parse tree on the `Pattern` result set, not on each match. One parse
per `find_all` call, shared by every match.

---

# 11. Why the consumer needs this

`codeman` serves an untrusted language model. Its rule from project 024 §10:

> The trusted implementation translates intent into a safe concrete command.
> The model never supplies an argument vector.

A raw ast-grep pattern string is close to an argument vector. A `Rule` object
is not. It is a typed, bounded, validated structure, checked against the
grammar's own node schema before anything runs.

Three consequences for the consumer:

1. **Fail fast, precisely.** An invalid `kind` is rejected by name at
   validation, in one round trip, before a parser starts.
2. **Rules serialize.** A rule goes into the trajectory record as JSON, and
   replays exactly.
3. **Invalid-rule rate is measurable per field.** Project 024 collects
   trajectories to train an adapter. Knowing *which* rule forms a model gets
   wrong is the evidence that decides whether a native pydantree pattern
   language is worth building later. A free string yields no such signal.

Every result therefore carries `GrammarAgreement.digest`, and the digest covers
the ast-grep version and both grammar revisions. Two trajectories recorded
months apart are comparable only if that value matches. This mirrors the
capability-profile store path in project 024 §7.2, applied to the one
dependency whose behaviour reaches the model.

---

# 12. Dependency and packaging

Keep the base lean. ast-grep is an optional extra.

```toml
[project.optional-dependencies]
pattern = ["ast-grep-py>=0.39"]
```

- `pattern.py` imports `ast_grep_py` **inside** `Pattern.__init__`, not at
  module import.
- A missing dependency raises `PatternError` naming the extra to install.
- `__init__.py` exports `Pattern`, `Rule`, `Edit`, and the new errors
  unconditionally. Importing the name must never require the extra.
- Add `ast-grep-py` to the root `dev` extra so the suite runs it.
- Pin the lower bound and record the resolved version in `GrammarAgreement`.

---

# 13. Phase 0 — the agreement spike

This repository decides bets with a spike and saved evidence. Do that here.
The spike answers one question, and the answer decides the design.

> Do ast-grep's grammar and `tree_sitter_python` 0.25.0 agree on node kinds
> and byte ranges, over real Python source?

Method:

1. Choose a corpus: every `.py` file under `src/pydantree_sitter/`. About 3800
   lines, real code, already present.
2. Parse each file with both engines.
3. Compare the full `(kind, start_byte, end_byte)` node sets.
4. Record exact-match rate, kind mismatches, and range mismatches.
5. Run about 20 representative patterns. For every match and capture, attempt
   the exact-range resolution of §4.1. Record the failure rate.

Save raw output under `evidence/`, as projects 006 and 014 did.

## Gate

```text
resolution failure rate == 0        GO. Build §3 as written.
under 1%, structural causes only    GO with the failures enumerated in the doc.
above 1%, or scattered              NO GO on §10. Fall back to §13.1.
```

## 13.1 The fallback

If the trees do not agree well enough, drop the node handoff and keep the rest:

- `PatternMatch` carries `Span` and `text` only. No `.node`, no `.extract()`.
- ast-grep becomes a self-contained search and rewrite engine behind a
  pydantree-shaped API, with `Rule` validation and edit safety intact.
- `codeman` still gets everything it needs, minus typed extraction on matches.

This fallback is a good outcome, not a failure. Do not weaken §4.1 to avoid it.
A quiet approximate resolution is worse than no resolution.

---

# 14. Implementation order

1. **Phase 0 spike** (§13). Gate the rest on it.
2. `rules.py` — `Rule`, validators, `to_astgrep`, `metavariables`, depth limit.
   Pure Pydantic, no engine. Fully testable alone.
3. `agreement.py` — the probe, the fixtures, `GrammarAgreement`, the
   per-Language cache.
4. `pattern.py` search half — `Pattern`, `find`, `find_all`, `PatternMatch`,
   exact-range resolution.
5. `Language.astgrep_name` and `UnsupportedLanguageError`.
6. `pattern.py` rewrite half — `Edit`, `ReplaceResult`, overlap rejection,
   re-parse verification.
7. `PatternMatch.extract` over `extract_tree_scoped`.
8. Exports, docs, `docs/architecture.md` section.

Steps 2 and 3 have no dependency on each other and no dependency on step 4.

---

# 15. Testing

- **Agreement:** the Phase 0 corpus check runs as a test, and fails the suite
  when a dependency bump breaks it. This is the regression guard for §4.
- **Property test the rewrite.** Follow the existing hypothesis practice in
  `match.py`. Generate non-overlapping edit sets, apply them, and assert the
  result equals a naive left-to-right reference application. Right-to-left
  offset arithmetic is where this module will have its bug.
- **Round trip:** a replacement whose template equals the pattern must return
  `new_source == source`, for every corpus file.
- **`Rule` validation:** every validator has a rejecting case, asserted on the
  message, not only on the class.
- **Resolution failure:** construct a divergence deliberately, and assert
  `PatternResolutionError` rather than a wrong node.
- **Broken rewrite:** a replacement producing invalid syntax must raise.

---

# 16. Two hazards for the implementer

**The `Point` refcount bug.** py-tree-sitter 0.26.0 carries
tree-sitter/py-tree-sitter#472: reading `Point.row` or `Point.column` returns a
borrowed reference and corrupts the allocator. `materialize.py` documents this
at length, and `Span.from_node` unpacks the tuple instead. **Build every `Span`
through `Span.from_node`.** Never read `.row` or `.column` in the new module,
and never construct a `Span` from raw node points by hand.

**ast-grep's own position objects are a separate code path.** They are safe.
Use them only to obtain byte offsets, then discard them. Every offset that
crosses into pydantree is a byte offset.

---

# 17. Invariants

1. ast-grep locates. pydantree resolves and types.
2. A byte range resolves to an exact node, or it raises.
3. Grammar agreement is checked once, at bind, and recorded as data.
4. All checks run at construction. A built `Pattern` works or it raised.
5. Rules are validated Pydantic models, never free dictionaries at the boundary.
6. Every offset is a byte offset over UTF-8.
7. Edits are data. The module writes no file.
8. Overlapping edits are refused, never resolved.
9. A rewrite that breaks the parse raises.
10. Every result carries the agreement digest.
11. `match.py` and `pattern.py` stay separate, and neither imports the other.
12. ast-grep stays an optional extra. Importing the names never requires it.
