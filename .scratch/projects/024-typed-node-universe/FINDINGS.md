# Typed node universe — final gate evidence

Date: 2026-09-08
Final lane measurement: 2026-09-08, after the complete implementation and
verification run.

## Phase 9 commands

All commands were run in the pinned `devenv` shell with `--no-tui --no-reload`.

```text
python -m pytest -q
343 passed, 1 xfailed in 42.29s

python -m pytest -q -W error -m "not slow"
325 passed, 18 deselected, 1 xfailed in 41.04s

ruff check src tests examples
All checks passed!

ty check src
All checks passed!

python -m pytest -q tests/test_docs_snippets.py
1 passed in 0.02s
```

## Examples

```text
python examples/wheel-extract/extract.py
exit 0; transcript.txt matched byte-for-byte

python examples/bash-extract/extract.py
exit 0; bash corpus traversal completed

python examples/devenv-extract/extract.py
exit 0; Nix corpus traversal completed

python examples/devenv-subset/extract.py
exit 0; Product B build and Product A typed traversal completed
```

The subset example printed both halves of the D12 round trip and extracted
`host = example.com` and `port = 8080` from the generated bundle.

The final typed-node oracle also covers the eight committed evidence files;
the refactor's focused oracle run is 60 passed.

## Cleanup gates

The eight Appendix B grep patterns were run over `src tests docs examples
.agents README.md CLAUDE.md`; every pattern returned no matches.

The final public surface is exactly:

```text
Node, Grammar, Span, generate_module, build_namespace, load_bundle,
NodeSchema, PydantreeSitterError, SchemaCheckError, SchemaDriftError,
ShapeError, ExtractionError
```
