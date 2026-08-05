"""Phase-7 wasm tests: the loader seam's wasm extension point (014 refactor).

The Phase-7 probe (Run A) showed the wasm mechanism works — a real rust.wasm
built with the tree-sitter CLI + emcc, parsed through wasmtime 29.0.0 via the
tree-sitter C library's official wasm store, at ~1.6x the native parse cost.
The standard binding (py-tree-sitter 0.26) has NO wasm support, so A's
`Language.load_bundle` over a `.wasm` artifact raises the clear
`WasmRuntimeUnavailableError`. In the 014 refactor the probe's bridge moved
out of the shipped seam (`.scratch/projects/009-phase7/wasm_bridge.py`) and
the wasm branch raises unconditionally — there is no env-var protocol in the
shipped path anymore. These tests pin the dispatch + the error; the real-load
and `/tmp/rust-bundle` tests were deleted with the bridge.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pydantree_sitter.loader import (
    WasmRuntimeUnavailableError,
    load_bundle,
)


def _wasm_bundle(tmp_path: Path, artifact: bytes = b"not real wasm") -> Path:
    """A 4-file bundle whose artifact is a .wasm (the seam's extension point)."""
    bundle = tmp_path / "wasm-bundle"
    bundle.mkdir()
    (bundle / "grammar.wasm").write_bytes(artifact)
    (bundle / "node-schema.json").write_text('{"node_types": []}')
    (bundle / "tree-sitter.json").write_text(
        '{"name": "rust", "artifact": "grammar.wasm", "schema": '
        '"node-schema.json", "abi": "15"}')
    (bundle / "loader.py").write_text("# shim")
    return bundle


def test_wasm_artifact_raises_clear_error(tmp_path):
    """A bundle naming a .wasm artifact raises WasmRuntimeUnavailableError
    unconditionally (py-tree-sitter has no wasm store; the wasm-capable
    runtime is a custom build, not a pip dependency; the probe bridge no
    longer ships in the seam — the error names its new home)."""
    bundle = _wasm_bundle(tmp_path)
    with pytest.raises(WasmRuntimeUnavailableError) as exc:
        load_bundle(bundle)
    msg = str(exc.value)
    assert "wasm" in msg
    assert "TREE_SITTER_FEATURE_WASM" in msg
    # the error names the probe's bridge home, not a silent mis-load
    assert ".scratch/projects/009-phase7/wasm_bridge.py" in msg
