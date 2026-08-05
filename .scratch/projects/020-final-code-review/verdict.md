# Review 020 — verdict

**Verdict: CONDITIONAL.** The core is solid, unusually well-tested, and
genuinely ready for *careful* personal use on the happy paths — but four real
defects live on the advanced/escape-hatch surfaces, two diagnostics
regressions undermine Product B's headline promise by default, and a
SIGSEGV-on-teardown makes the suite exit 139 despite all 272 tests passing.

## Three strongest reasons to trust it

1. **The happy paths are verified end to end.** 272/272 tests pass inside
   `devenv` (68s). Three real-world examples (bash 0.25.1, the author's own
   nix files, a from-scratch DSL grammar) extract hand-checked rows, match
   saved oracle JSON that regenerates byte-for-byte, and are re-run as
   subprocesses to prove they stay runnable.
2. **The binding-time-check differentiator is real.** Schema bind produces
   actionable `SchemaCheckError`s on the common paths — verified by the suite
   and by the two prior adversarial reviews (018/019, all V1–V7 closed).
3. **The codebase is disciplined.** 19 project phases, 152 commits, 4 TODOs,
   3 `type: ignore`, no bare excepts, no `shell=True`, no unchecked
   subprocess returncodes. Prior findings demonstrably landed.

## Three biggest gaps

1. **Exit code is broken.** The full suite and full `test_oracles.py` module
   segfault on native teardown (exit 139) even though every test passes —
   masked as exit 0 only when piped. Any `pytest && …` gate or CI reading the
   raw exit code sees failure.
2. **The live-fixture story stops at saved *data*; saved *steps* don't exist.**
   The per-step transcripts the examples print are committed nowhere; only
   final row counts are asserted. Several headline Product A features
   (`RawQuery`, `Matches`/`Eq`/`AnyOf`, `NodeKind` alternation, `Unescaped`,
   `derived()`, nested models) have no live example with saved output at all.
3. **Everything is toolchain-gated.** In a plain shell 127 tests skip —
   including every oracle test — and the library won't even import without
   `tree_sitter`. There is no toolchain-free example.

## Ship condition

Before claiming "fully ready": fix/guard A1 (raw-query `IndexError`) and A2
(empty-list anchor drop), implement or delete `reparse` (A3), re-run analyzer
errors over the sited builder (B1), and either root-cause the exit-139
segfault or stop masking it. Do the trivial sweep (example `want` NameError,
two doc snippets, README 265→272) immediately — they are the first things any
reader hits. Then add one toolchain-free live example with a committed
per-step transcript oracle to fully answer the saved-outputs question.

**Bottom line:** yes for careful personal use with the §2 caveats in hand; not
"ship it and forget the sharp edges."
