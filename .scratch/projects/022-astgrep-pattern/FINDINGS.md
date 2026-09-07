# Phase 0 — the grammar agreement spike

**Project 022. CONCEPT.md §13.**
**Status:** complete. **Verdict: GO.** Build §3 as written, `.extract()` included.

Script: `spike_agreement.py`. Raw output: `evidence/agreement.json`,
`evidence/agreement-naive.json`.

```
devenv shell -- python .scratch/projects/022-astgrep-pattern/spike_agreement.py
```

---

## 1. The result

| Measurement | Total | Resolved exactly | Failure rate |
| --- | --- | --- | --- |
| Named nodes, full set | 20 296 | 20 296 | **0 %** |
| All nodes, anonymous included | 30 686 | 30 686 | **0 %** |
| Pattern whole-match ranges | 2 948 | 2 948 | **0 %** |
| Pattern capture ranges | 7 663 | 7 663 | **0 %** |

Corpus: the 13 files of `src/pydantree_sitter/`, 3 834 lines. 24 patterns.
Zero kind disagreements. Zero range mismatches. No file diverged.

Versions measured: `ast-grep-py` 0.45.3, `tree-sitter-python` 0.25.0,
`tree-sitter` 0.26.0.

The gate in §13 reads "resolution failure rate == 0 -> GO". It is zero on
both halves. **§10's `OutputModel` bridge is viable, and the §13.1 fallback
is not needed.**

## 2. The one real finding — offsets are CHARACTERS, not bytes

`ast_grep_py` reports positions as `Range(start=Pos, end=Pos)`, and
`Pos.index` is a **character** offset. CONCEPT.md §16 assumes ast-grep yields
byte offsets and says only "use them to obtain byte offsets, then discard
them". That step does not exist as stated: there is no byte offset to obtain.

```python
src = 'x = "ééé"\ny = 1\n'      # 16 characters, 19 bytes
SgRoot(src, "python").root().children()[0].range()
#   start.index == 0, end.index == 9     <- characters
#   the same node in bytes is            0 .. 12
```

A conversion table is mandatory on every range crossing the boundary:

```python
def char_to_byte_table(text: str) -> list[int]:  # index N == len(text) is the end
    table, b = [0] * (len(text) + 1), 0
    for i, ch in enumerate(text):
        table[i] = b
        b += len(ch.encode("utf-8"))
    table[len(text)] = b
    return table
```

**This finding is load-bearing, and the spike proves it rather than asserting
it.** All 13 corpus files carry non-ASCII text, so the conversion is
exercised throughout. Re-running with `--naive-offsets`, which treats the
character offsets as byte offsets, collapses agreement from 100 % to
**0.54 %** (110 of 20 296 nodes) — see `evidence/agreement-naive.json`.

Two consequences for the implementation:

- §16 must gain a third paragraph naming this conversion, in the same voice
  as the `Point` refcount hazard. It is the same class of bug: a plausible
  wrong answer, not a crash.
- The table is O(len(text)) per parse. Build it **once per `find_all` call**
  and keep it beside the parse tree on the result set, exactly as §10 says to
  keep the tree. Do not rebuild it per match.

Had the conversion been missed, §4.1's exact-range rule would have converted
the bug into a loud `PatternResolutionError` on almost every ASCII-adjacent
match — which is the design working. The spike found it in an hour instead.

## 3. What the perfect score does and does not license

It says: at these three pinned versions, over this corpus, the two grammars
agree completely. Real divergence between grammar revisions remains the
standing risk, and nothing here removes it.

So the §4.1 exact-range rule stays exactly as written. **Do not weaken it to
a nearest-node fallback on the strength of this result.** A 0 % failure rate
is the reason the strict rule is cheap to keep, not a reason to drop it.

## 4. What this changes in the concept

**§4.2 — replace the bind-time fixture probe.** A single fixture per language
cannot demonstrate what this corpus run demonstrated, and shipping one would
imply a guarantee it does not provide. Make `GrammarAgreement` a **recorded**
artifact: the three dependency versions plus the corpus result committed from
CI, with `digest` over that record. Bind time reads the versions and compares
them to the recorded ones; a mismatch raises the bind warning. That is honest
about what was actually measured, and it costs nothing per `Pattern`.

**§13's binary gate should have been split, and now permanently is.** The
script counts whole-match and capture resolution separately. Both are zero
today. When a dependency bump breaks one and not the other, the numbers will
say which — a single blended rate would not.

**§15's regression guard is this script.** Promote it to `tests/` largely
unchanged; it already emits machine-readable output and runs in about a
second. Assert both failure rates are zero and both node-set rates are 1.0.

## 4a. A later finding, recorded here because it belongs with §4

The Phase 0 question was whether the two GRAMMARS agree. A second question
turned out to matter as much: whether tree-sitter's notion of "this parses"
agrees with the language's.

It does not.

```python
def f(a): x = 1
    return x
```

`root_node.has_error` is False; tree-sitter reparents `return x` to module
level. CPython raises `SyntaxError`. CONCEPT §8.1's re-parse verification,
built on `has_error` alone, therefore passed 19 of 19 broken rewrites over
this same corpus.

`IMPLEMENTATION.md` §1.3a carries the fix and the measurement. The lesson for
anyone reading this file first: **an ERROR-node check is a smoke alarm, not a
correctness proof.** Structure — does the edit still occupy one node? — is
the check that holds.

## 5. Incidental

The `ast-grep` CLI in the devenv shell is **0.37.0** (nixpkgs), while the
`ast-grep-py` wheel is **0.45.3** (uv.lock). The CLI is a debugging aid only.
Never read library behaviour off the CLI, and never quote a CLI result as
evidence about the module. `devenv.nix` records this.

Neither `ast_grep_py` nor `tree_sitter_python` exposes `__version__`. Read
versions with `importlib.metadata.version`, or `GrammarAgreement.digest`
records the string `"unknown"` and two runs become incomparable.
