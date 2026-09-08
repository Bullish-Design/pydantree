# Schema distribution — design and implementation report

Date: 2026-09-09

## Chosen distribution architecture

Keep community `node-types.json` files as application-owned data. Do not add a
generic schema data wheel to `pydantree-sitter`. The light runtime already has
the correct boundary: it consumes a schema and a grammar wheel, but it does
not contain Product B or a compiler toolchain.

Product B bundles remain the second distribution path. A generated bundle
contains `grammar.so`, `node-schema.json`, `nodes.py`, `tree-sitter.json`, and
`loader.py`. Community consumers copy the exact upstream schema beside their
generated nodes, or use a Product B bundle when they build from grammar source.

The runtime now provides `pydantree_sitter.schema.load_schema`. It accepts a
validated `NodeSchema`, a schema path, or schema data. `Grammar.load` accepts a
schema path and an optional `schema_name`. This makes the installation path
explicit and keeps schema loading free of Product B imports and compiler calls.

## Rejected alternatives

- Ship common community schemas in the runtime wheel. This couples a small
  runtime to unrelated grammar release schedules and does not cover the long
  tail of community grammars.
- Create a separate schema data wheel. A schema is coupled to one grammar
  source, grammar version, generated ABI, and runtime compatibility range.
  A global data package would create an ambiguous ownership and upgrade path.
- Regenerate schemas during normal imports or pytest runs. This requires the
  tree-sitter CLI, a compiler in some workflows, and often network access.
- Infer a schema from a consumer model. This violates the no-schema-less
  typed-binding rule and loses the closed node-kind universe.

## Provenance and update workflow

The retained community fixture manifest records the upstream repository, exact
commit or tag, commit date, license, acquired date, source files, and the
supported tree-sitter CLI range. `tests/test_community_fixtures.py` regenerates
the real fixtures and compares the CLI output byte-for-byte. Normal pytest
runs never write them. Refresh requires the explicit
`tests/regenerate_community_node_types.py --write` command and a review of the
diff.

The toolchain-free Python example records its schema provenance in
`examples/wheel-extract/vendor/python-node-types.provenance.json`. It records
the source repository, source package, runtime range, ABI, generation tool, and
refresh policy. The schema is from `tree-sitter-python==0.25.0`; the installed
runtime probe used tree-sitter 0.26.0, language ABI 15, and the pinned
tree-sitter CLI 0.25.3 for generation claims.

## Compatibility policy

The checked-in community schema is the exact `node-types.json` byproduct for
the supported CLI range, currently tree-sitter 0.25.x and pinned 0.25.3.
Generated bundles carry a language fingerprint and reject drift with
`SchemaDriftError`. Path-based community loading can name the grammar with
`schema_name`; a mismatch with the loaded language raises the same error.

`SchemaMissingError` means the application did not install its schema data.
`SchemaDataError` means the file exists but is unreadable, malformed, or fails
schema validation. These errors are distinct from language/schema drift.
Tree-sitter runtime compatibility for the maintained wheel example is
`>=0.26,<0.27`, with ABI 15 recorded in its provenance file.

## Package-size and installation implications

The light wheel remains B-free and contains no community schema files. The
measured artifacts from `uv build` were:

| artifact | size |
|---|---:|
| `pydantree_sitter-0.3.0-py3-none-any.whl` | 56,291 bytes |
| `pydantree_sitter_grammar-0.3.0-py3-none-any.whl` | 69,362 bytes |

The application pays only for the schemas it uses. Product A installs without
the CLI, compiler, or Product B. Product B remains the heavy build dependency.

## Test evidence

- Phase 024 baseline before this work: `344 passed, 1 xfailed`.
- Final full suite: `350 passed, 1 xfailed`.
- Final warnings-as-errors suite: `350 passed, 1 xfailed`.
- Focused distribution, grammar, and wheel-example tests: `15 passed`.
- Fresh-venv light-wheel install, B-free import boundary, and installed
  schema-loader probe: `1 passed`.
- `ruff check src tests examples`: passed.
- `ty check src`: passed.
- Documentation snippets: `1 passed`.
- Maintained examples: wheel-extract, bash-extract, devenv-extract, and
  devenv-subset all exited successfully. The wheel transcript matched.

## Remaining risks

- A schema with no explicit grammar name cannot prove language identity from
  its shape alone. Applications should pass `schema_name` and record
  provenance beside the schema.
- The Python example's source distribution records a package release rather
  than a full upstream commit. A future refresh should record the exact
  source commit if the upstream package publishes it.
- The compatibility policy is intentionally tied to the pinned CLI and
  tree-sitter runtime ranges. Upgrading either requires an intentional fixture
  regeneration and review.

## VCS handoff limitation

The requested task lane could not be created. `gitman start
task/schema-distribution-20260909-0912` and the final `gitman save` both
refused because the inherited `024-typed-node-universe` lane is
OFF-CANONICAL: one change has multiple commits. The only offered recovery is
`gitman reconcile`, which would repair another session's history. This task
did not run reconcile, modify Phase 024 history, publish a branch, land a
lane, or create a tag. The implementation remains in the current workspace
for a clean integration session to adopt after the VCS state is repaired by
its owner.
