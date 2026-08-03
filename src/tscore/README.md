# tscore

The tiny shared package between tsgrammar (B) and tsquery (A): the grammar
node-schema + the artifact-loading contract (CONCEPT §8). Pure Python, no
toolchain.

- `tscore.schema` — the node-schema format (`NodeSchema`,
  `derive_from_ir` — the exact-path derivation, byte-for-byte with the
  CLI's node-types.json over rust/python/markdown/markdown-inline;
  `derive_from_node_types` — the community path).
- `tscore.loader` — the ONE place a compiled grammar becomes a
  `tree_sitter.Language`: `load_grammar_so` (PyCapsule load),
  `load_bundle` (the 4-file bundle contract), and the wasm seam (artifact
  dispatch + `WasmRuntimeUnavailableError` + the env-wired wasmtime
  bridge in `_wasm_bridge.py`).

See [docs/architecture.md](../../docs/architecture.md) (the seams) and
[docs/development.md](../../docs/development.md) (the workflow). Users:
[docs/user-guide.md](../../docs/user-guide.md).
