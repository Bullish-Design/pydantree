"""Phase-7 wasm tests: the loader seam's wasm extension point.

The Phase-7 probe (Run A) showed the wasm mechanism works — a real rust.wasm
built with the tree-sitter CLI + emcc, parsed through wasmtime 29.0.0 via the
tree-sitter C library's official wasm store, at ~1.6x the native parse cost.
The standard binding (py-tree-sitter 0.26) has NO wasm support, so A's
`Language.load_bundle` over a `.wasm` artifact raises the clear
`WasmRuntimeUnavailableError` unless a wasm-capable runtime is wired
(TSGRAMMAR_WASM_LIB / TSGRAMMAR_WASMTIME_LIB — the probe's env-pointed
extension point). These tests pin the dispatch + the error, and exercise the
real load when the runtime is present.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tscore.loader import (
    WasmRuntimeUnavailableError,
    load_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


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


def test_wasm_artifact_raises_clear_error_without_runtime(tmp_path, monkeypatch):
    """A bundle naming a .wasm artifact raises WasmRuntimeUnavailableError
    with the exact state of the wasm path (py-tree-sitter has no wasm store;
    the wasm-capable runtime is a custom build, not a pip dependency)."""
    monkeypatch.delenv("TSGRAMMAR_WASM_LIB", raising=False)
    monkeypatch.delenv("TSGRAMMAR_WASMTIME_LIB", raising=False)
    bundle = _wasm_bundle(tmp_path)
    with pytest.raises(WasmRuntimeUnavailableError) as exc:
        load_bundle(bundle)
    msg = str(exc.value)
    assert "wasm" in msg
    assert "TSGRAMMAR_WASM_LIB" in msg and "TSGRAMMAR_WASMTIME_LIB" in msg
    # the error names the probe evidence, not a silent mis-load
    assert "TREE_SITTER_FEATURE_WASM" in msg


def test_so_bundle_still_loads_after_wasm_dispatch(tmp_path):
    """The .so path is untouched by the dispatch (regression guard)."""
    from tscore.loader import load_bundle as _lb
    # reuse the smallest existing native bundle build? no — the dispatch test
    # needs a real .so; guard via the probe's own native bundle when present.
    so_bundle = Path("/tmp/rust-bundle")
    if not (so_bundle / "grammar.so").exists():
        pytest.skip("native rust bundle not built (see probe)")
    b = _lb(so_bundle)
    assert b.language is not None
    assert b.schema is not None


_HAS_RUNTIME = (os.environ.get("TSGRAMMAR_WASM_LIB") is not None
                and os.environ.get("TSGRAMMAR_WASMTIME_LIB") is not None)


@pytest.mark.skipif(not _HAS_RUNTIME,
                    reason="TSGRAMMAR_WASM_LIB / TSGRAMMAR_WASMTIME_LIB unset "
                           "(the Phase-7 probe's wasm-capable runtime)")
def test_wasm_bundle_loads_and_parses_with_runtime(tmp_path):
    """The one-line load_bundle over a REAL .wasm artifact through the
    wasm-capable runtime (the probe's evidence artifact): real parse, real
    schema binding."""
    artifact = (ROOT / ".scratch" / "009-phase7" / "evidence"
                / "rA_rust_grammar.wasm")
    if not artifact.exists():
        pytest.skip("probe wasm artifact missing")
    bundle = _wasm_bundle(tmp_path, artifact=artifact.read_bytes())
    b = load_bundle(bundle)
    lang = b.language
    assert lang.name == "rust"
    tree = lang.parse("fn main() { let x = 1; }\n")
    assert not tree.has_error()
    assert "function_item" in tree.sexp()
