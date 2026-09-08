# 027 — schema/language conformance findings

**Date:** 2026-09-09

**Status:** complete — implementation, final verification, save, and publish are
complete.

## Result

The runtime now verifies a schema against the loaded tree-sitter language at
bind time. The check rejects alien kinds and fields. It rejects schemas that
omit more than 25 percent of the language's concrete visible kinds. It allows
smaller omissions because real grammars can omit ABI-visible kinds. It exempts
schema supertypes from the existence check and uses `Language.supertypes`.

The check runs for `Grammar.load` and `Grammar.load_bundle`. Callers can pass
`verify=False` only for tests that intentionally bind synthetic schemas to an
unrelated language.

The repository’s off-canonical state was repaired by gitman’s divergent-lane
recovery: the unbookmarked sibling carrying the duplicate change-id was retired,
the remaining unrelated stray was adopted, and the Phase 027 lane was published.

## Phase results

- Phase 0: all nine baseline commands exited 0. Evidence is in
  `evidence/baseline-20260909/`.
- Phase 1: the wheel example now vendors the complete upstream Python schema.
  The schema has 217 entries and SHA-256
  `a2456847bea3adff5b2222b2f7b03a870159470d8908622204e6eb29ee2fe45e`.
- Phase 2: synthetic JSON schemas explicitly opt out in resolver tests.
- Phase 3: conformance tests cover wrong grammars, nameless languages, empty
  and partial schemas, arbitrary schema directories, supertypes, provenance,
  and five real community grammars.
- Phase 4: filename and parent-directory name inference is removed.
- Phase 5: distribution errors are public, empty schemas fail, schema I/O uses
  UTF-8, and both distributions pin tree-sitter to `>=0.26,<0.27`.
- Phase 6: the user guide and architecture document the verification rule,
  limits, provenance contract, and remediation steps.

## Upstream provenance

The vendored schema comes from the `v0.25.0` tree-sitter-python source at
commit [`293fdc02038ee2bf0e2e206711b69c90ac0d413f`](https://github.com/tree-sitter/tree-sitter-python/commit/293fdc02038ee2bf0e2e206711b69c90ac0d413f).
The source artifact is the upstream
[`src/node-types.json`](https://raw.githubusercontent.com/tree-sitter/tree-sitter-python/v0.25.0/src/node-types.json).

## Remaining risk

The missing-kind ratio remains a heuristic. The supported runtime range is
limited to tree-sitter 0.26.x because the supertype ABI behavior is version
sensitive. ABI 16 remains unverified.

## Re-run

Run the commands recorded in `evidence/final-20260909/`. All commands must
exit 0, and the wheel example transcript must match byte-for-byte.
