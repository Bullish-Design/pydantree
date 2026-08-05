# Review 019 — post-review resolution

**Date:** 2026-08-05

## V1 resolved by removing the compatibility fixture

The project does not guarantee—and does not want—backward compatibility for
previously generated native bundles. Accordingly,
`tests/oracles/.built/{bash,nix,subset}` was removed instead of adding tests
that would turn stale, platform-specific `.so` files into a supported contract.

The retained verification model is simpler:

1. `tests/oracles/*.json` is the durable observable-behavior contract.
2. `tests/test_oracles.py` rebuilds every grammar from committed sources through
   the current pipeline and toolchain.
3. The freshly built bundle must reproduce the saved extraction JSON and the
   examples' independent ground truth.
4. Generated bundles may be release/CI outputs, but they are not repository
   fixtures and carry no cross-version compatibility promise.

The Review 019 findings remain unchanged as the historical record of what was
observed. This resolution closes V1 by removing the unverified artifact claim;
it does not claim to close the independent V4/V5 findings.
