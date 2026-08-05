"""Phase 7, Run A — the wasm perf probe: native .so vs wasm grammar, same
parse engine (libtree-sitter compiled with TREE_SITTER_FEATURE_WASM), same
text, same loop. The ~1.5-2x wasm note (CONCEPT 11.5) measured over rust.
"""
from __future__ import annotations

import ctypes
import json
import time
from pathlib import Path

TS_WASM = Path("/tmp/ts-wasm")
RUST_WASM = Path("/tmp/rust-wasm-probe/rust.wasm")
RUST_SO = Path("/tmp/rust-bundle/grammar.so")

libts = ctypes.CDLL(str(TS_WASM / "libtree-sitter-wasm.so"))
libwt = ctypes.CDLL(str(TS_WASM / "libwasmtime.so"))


class TSNode(ctypes.Structure):
    _fields_ = [("context", ctypes.c_uint32 * 4),
                ("id", ctypes.c_void_p),
                ("tree", ctypes.c_void_p)]


class TSWasmError(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_int), ("message", ctypes.c_char_p)]


c_void_p = ctypes.c_void_p
c_char_p = ctypes.c_char_p
c_uint32 = ctypes.c_uint32

libwt.wasm_engine_new.restype = c_void_p
libwt.wasm_engine_delete.argtypes = [c_void_p]

libts.ts_wasm_store_new.restype = c_void_p
libts.ts_wasm_store_new.argtypes = [c_void_p, ctypes.POINTER(TSWasmError)]
libts.ts_wasm_store_load_language.restype = c_void_p
libts.ts_wasm_store_load_language.argtypes = [
    c_void_p, c_char_p, c_char_p, c_uint32, ctypes.POINTER(TSWasmError)]
libts.ts_parser_new.restype = c_void_p
libts.ts_parser_delete.argtypes = [c_void_p]
libts.ts_parser_set_language.restype = ctypes.c_bool
libts.ts_parser_set_language.argtypes = [c_void_p, c_void_p]
libts.ts_parser_set_wasm_store.argtypes = [c_void_p, c_void_p]
libts.ts_parser_parse_string.restype = c_void_p
libts.ts_parser_parse_string.argtypes = [c_void_p, c_void_p, c_char_p, c_uint32]
libts.ts_tree_delete.argtypes = [c_void_p]
libts.ts_tree_root_node.restype = TSNode
libts.ts_tree_root_node.argtypes = [c_void_p]
libts.ts_node_has_error.restype = ctypes.c_bool
libts.ts_node_has_error.argtypes = [TSNode]
libts.ts_node_child_count.restype = c_uint32
libts.ts_node_child_count.argtypes = [TSNode]


def load_native_parser() -> tuple:
    """A parser over the native grammar.so (no wasm)."""
    lib = ctypes.CDLL(str(RUST_SO))
    fn = lib.tree_sitter_rust
    fn.restype = c_void_p
    lang = fn()
    parser = libts.ts_parser_new()
    assert libts.ts_parser_set_language(parser, lang)
    return parser, lib, lang


def load_wasm_parser() -> tuple:
    """A parser over the wasm grammar, through the real wasmtime runtime."""
    err = TSWasmError()
    engine = libwt.wasm_engine_new()
    store = libts.ts_wasm_store_new(engine, ctypes.byref(err))
    assert store, f"store: {err.message}"
    wasm = RUST_WASM.read_bytes()
    lang = libts.ts_wasm_store_load_language(store, b"rust", wasm, len(wasm),
                                             ctypes.byref(err))
    assert lang, f"load_language: {err.message}"
    parser = libts.ts_parser_new()
    libts.ts_parser_set_wasm_store(parser, store)  # parser owns the store
    assert libts.ts_parser_set_language(parser, lang)
    return parser, engine


def bench(parser, text: bytes, rounds: int = 200) -> float:
    """Parse `text` `rounds` times; return median ms/parse. Warms up first."""
    tree = libts.ts_parser_parse_string(parser, None, text, len(text))
    root = libts.ts_tree_root_node(tree)
    assert not libts.ts_node_has_error(root), "parse had errors"
    libts.ts_tree_delete(tree)
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        tree = libts.ts_parser_parse_string(parser, None, text, len(text))
        times.append((time.perf_counter() - t0) * 1000)
        libts.ts_tree_delete(tree)
    times.sort()
    return times[len(times) // 2]


def main() -> int:
    sample = Path("/tmp/rust-corpus/lib.rs").read_text()
    # a larger real corpus: repeat the sample module to ~256KB
    corpus = sample * max(1, (256 * 1024) // len(sample))
    text = corpus.encode("utf-8")
    print(f"corpus: {len(text)} bytes")

    native = load_native_parser()
    wasm = load_wasm_parser()
    try:
        native_ms = bench(native[0], text)
        wasm_ms = bench(wasm[0], text)
    finally:
        libts.ts_parser_delete(native[0])
        libts.ts_parser_delete(wasm[0])
        libwt.wasm_engine_delete(wasm[1])
    ratio = wasm_ms / native_ms
    print(f"native: {native_ms:.3f} ms/parse "
          f"({len(text) / 1024 / 1024 / (native_ms / 1000):.2f} MB/s)")
    print(f"wasm:   {wasm_ms:.3f} ms/parse "
          f"({len(text) / 1024 / 1024 / (wasm_ms / 1000):.2f} MB/s)")
    print(f"ratio:  wasm/native = {ratio:.2f}x")
    result = {"corpus_bytes": len(text),
              "native_ms": native_ms, "wasm_ms": wasm_ms, "ratio": ratio}
    out = Path("/tmp/wasm-perf.json")
    out.write_text(json.dumps(result, indent=2))
    print("saved", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
