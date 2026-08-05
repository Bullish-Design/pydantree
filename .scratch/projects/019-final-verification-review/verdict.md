# Review 019 — ship verdict

**Verdict: CONDITIONAL.** The executable behavior is strong, but the repository
is not yet solid enough to ship under its strongest verification claim: that
real-world usage and every saved expected artifact are continuously verified.

## Three strongest reasons to trust it

1. **Real behavior is genuinely end to end.** All 265 tests pass. The Bash,
   Nix, and authored-devenv examples produce 34, 102, and 56 hand-checked rows;
   their saved oracle JSON regenerates byte-for-byte. Real CLI/gcc builds,
   scanners, bundles, and typed extraction are exercised.
2. **The package boundary is real.** Actual wheels are built; wheel contents
   are checked against source; a fresh venv installs only Product A, cannot
   import Product B, and successfully consumes a real bundle. Rust, Markdown,
   and Nix also run through B-free subprocess consumers.
3. **The guards can fail.** Three sampled Review 018 tests are red on their
   pre-fix parents and green now. Novel Rust and rule-class/scanner/conflict
   probes caught bad assumptions and wrong saved expectations before passing.
   Simulated CLI 0.26 drift fails clearly in 0.12 seconds; two sequential full
   runs both finish at 265 passed.

## Three biggest gaps

1. **`tests/oracles/.built` is outside the suite and partly stale.** No test
   reads it. Fresh rebuilds differ for Bash/Nix native artifacts and metadata;
   only the subset bundle reproduces completely. There is no bundle provenance
   or regeneration command.
2. **Several checked-in community node-type byproducts are not drift-tested.**
   Rust is the exception. Bash/Markdown are consumed via freshly generated
   schemas, while Nix compares fresh output to itself rather than its saved
   fixture. Presence is being mistaken for an asserted oracle.
3. **The supposedly CLI-free golden conflict guard is blanket toolchain-marked.**
   Both saved-stderr parser/renderer tests skip when the CLI is absent—the exact
   environment they should protect.

## Ship condition

Close V1/V4/V5 before making the strong saved-output claim: directly test and
document regeneration for retained artifacts, remove stale/uncontracted files,
and let the golden conflict tests run toolchain-free. The remaining README,
fresh-worktree, provenance-detail, and source-line assertion issues are minor
follow-ups.
