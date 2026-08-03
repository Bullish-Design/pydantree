"""Phase 7, Run A — the wasm runtime probe, step 3: load the real rust.wasm
grammar through a REAL wasm runtime (wasmtime 29.0.0, the version tree-sitter
0.25.3 pins) and do a real parse.

The runtime stack under test:

    libwasmtime.so            the wasmtime 29.0.0 C API runtime (the real
                              wasm engine — what the grammar .wasm runs on)
    libtree-sitter-wasm.so    the tree-sitter C library compiled with
                              TREE_SITTER_FEATURE_WASM (the official wasm
                              store: ts_wasm_store_load_language, the same
                              path the tree-sitter CLI/editor ecosystem uses)
    rust.wasm                 the grammar artifact (tree-sitter build --wasm)

The bridge is ctypes over the C API: ts_wasm_store_new(engine) ->
ts_wasm_store_load_language(store, name, wasm, len) -> ts_parser_* ->
ts_node_* tree walk. This is exactly the A-side surface py-tree-sitter would
need for a wasm bundle (it has none today — 0.26 links the non-wasm lib).
"""
from __future__ import annotations

import ctypes
import json
import time
from pathlib import Path

TS_WASM = Path("/tmp/ts-wasm")
RUST_WASM = Path("/tmp/rust-wasm-probe/rust.wasm")

libts = ctypes.CDLL(str(TS_WASM / "libtree-sitter-wasm.so"))
libwt = ctypes.CDLL(str(TS_WASM / "libwasmtime.so"))


# ---------------------------------------------------------------------------
# C types
# ---------------------------------------------------------------------------

class TSNode(ctypes.Structure):
    _fields_ = [("context", ctypes.c_uint32 * 4),
                ("id", ctypes.c_void_p),
                ("tree", ctypes.c_void_p)]


class TSWasmError(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_int), ("message", ctypes.c_char_p)]


c_void_p = ctypes.c_void_p
c_char_p = ctypes.c_char_p
c_uint32 = ctypes.c_uint32
c_size_t = ctypes.c_size_t
c_bool = ctypes.c_bool

# wasmtime C API
libwt.wasm_engine_new.restype = c_void_p
libwt.wasm_engine_delete.argtypes = [c_void_p]

# tree-sitter wasm store + parser + tree + node API
libts.ts_wasm_store_new.restype = c_void_p
libts.ts_wasm_store_new.argtypes = [c_void_p, ctypes.POINTER(TSWasmError)]
libts.ts_wasm_store_delete.argtypes = [c_void_p]
libts.ts_wasm_store_load_language.restype = c_void_p
libts.ts_wasm_store_load_language.argtypes = [
    c_void_p, c_char_p, c_char_p, c_uint32, ctypes.POINTER(TSWasmError)]
libts.ts_parser_new.restype = c_void_p
libts.ts_parser_delete.argtypes = [c_void_p]
libts.ts_parser_set_language.argtypes = [c_void_p, c_void_p]
libts.ts_parser_set_language.restype = c_bool
libts.ts_parser_set_wasm_store.argtypes = [c_void_p, c_void_p]
libts.ts_parser_parse_string.restype = c_void_p
libts.ts_parser_parse_string.argtypes = [c_void_p, c_void_p, c_char_p, c_uint32]
libts.ts_tree_delete.argtypes = [c_void_p]
libts.ts_tree_root_node.restype = TSNode
libts.ts_tree_root_node.argtypes = [c_void_p]
libts.ts_node_child.restype = TSNode
libts.ts_node_child.argtypes = [TSNode, c_uint32]
libts.ts_node_child_count.restype = c_uint32
libts.ts_node_child_count.argtypes = [TSNode]
libts.ts_node_named_child_count.restype = c_uint32
libts.ts_node_named_child_count.argtypes = [TSNode]
libts.ts_node_start_byte.restype = c_uint32
libts.ts_node_start_byte.argtypes = [TSNode]
libts.ts_node_end_byte.restype = c_uint32
libts.ts_node_end_byte.argtypes = [TSNode]
libts.ts_node_is_named.restype = c_bool
libts.ts_node_is_named.argtypes = [TSNode]
libts.ts_node_type.restype = c_char_p
libts.ts_node_type.argtypes = [TSNode]
libts.ts_node_symbol.restype = ctypes.c_uint16
libts.ts_node_symbol.argtypes = [TSNode]
libts.ts_language_symbol_name.restype = c_char_p
libts.ts_language_symbol_name.argtypes = [c_void_p, ctypes.c_uint16]
libts.ts_parser_language.restype = c_void_p
libts.ts_parser_language.argtypes = [c_void_p]
libts.ts_language_version.restype = c_uint32
libts.ts_language_version.argtypes = [c_void_p]


class WasmGrammar:
    """The A-side runtime: a wasm grammar artifact, loaded and parsed."""

    def __init__(self, wasm_path: Path, name: str):
        wasm_bytes = wasm_path.read_bytes()
        err = TSWasmError()
        self.engine = libwt.wasm_engine_new()
        assert self.engine, "wasm_engine_new failed"
        self.store = libts.ts_wasm_store_new(self.engine, ctypes.byref(err))
        if not self.store:
            raise RuntimeError(f"ts_wasm_store_new: {err.message}")
        self.language = libts.ts_wasm_store_load_language(
            self.store, name.encode(), wasm_bytes, len(wasm_bytes),
            ctypes.byref(err))
        if not self.language:
            raise RuntimeError(f"load_language: {err.message}")
        self.abi = libts.ts_language_version(self.language)
        self._parser = None

    def parse(self, text: str) -> TSNode:
        if self._parser is None:
            self._parser = libts.ts_parser_new()
            # for a wasm language the parser needs the wasm store FIRST
            # (parser.c: ts_parser_set_language checks self->wasm_store)
            libts.ts_parser_set_wasm_store(self._parser, self.store)
            assert libts.ts_parser_set_language(self._parser, self.language)
        data = text.encode("utf-8")
        # the tree references the source buffer — keep it alive for the walk
        self._src = data
        self._tree = libts.ts_parser_parse_string(
            self._parser, None, data, len(data))
        assert self._tree, "parse returned NULL"
        return libts.ts_tree_root_node(self._tree)

    def __del__(self):
        # the parser OWNS the wasm store after ts_parser_set_wasm_store
        # (ts_parser_delete -> ts_wasm_store_delete) — deleting it again is
        # a double free. Only the engine + tree + parser are ours to free.
        for fn, arg in ((libts.ts_parser_delete, self._parser),
                        (libts.ts_tree_delete, getattr(self, "_tree", None)),
                        (libwt.wasm_engine_delete, self.engine)):
            if arg:
                fn(arg)


def sexp(node: TSNode, src: bytes, lang: c_void_p, depth: int = 0) -> str:
    """Render a node subtree in the tree-sitter corpus sexp style."""
    kind = libts.ts_node_type(node)
    if not kind:
        return ""
    kind = kind.decode()
    is_named = bool(libts.ts_node_is_named(node))
    start = libts.ts_node_start_byte(node)
    end = libts.ts_node_end_byte(node)
    nkids = libts.ts_node_child_count(node)
    text = src[start:end].decode("utf-8", "replace") if not is_named else ""
    if is_named:
        parts = [kind]
        for i in range(nkids):
            child = libts.ts_node_child(node, i)
            if libts.ts_node_is_missing(child):
                parts.append("MISSING")
                continue
            parts.append(sexp(child, src, lang, depth + 1))
        return f"({' '.join(parts)})"
    return f"'{text}'"


libts.ts_node_is_missing.restype = c_bool
libts.ts_node_is_missing.argtypes = [TSNode]

RUST_SAMPLE = """\
fn main() {
    let x = 42;
    println!("hello {}", x);
    if x > 10 {
        println!("big");
    } else {
        println!("small");
    }
}

pub fn add(a: u32, b: u32) -> u32 {
    a + b
}

struct Point {
    x: f64,
    y: f64,
}

enum Color {
    Red,
    Green(u8),
    Blue { r: u8, g: u8, b: u8 },
}
"""


def main() -> int:
    g = WasmGrammar(RUST_WASM, "rust")
    print(f"wasm grammar loaded: abi={g.abi} "
          f"(bindings 0.26 accepts 13-15)")
    node = g.parse(RUST_SAMPLE)
    print(sexp(node, g._src, g.language)[:400], "...")
    print("has_error:", libts.ts_node_has_error(node))
    return 0


libts.ts_node_has_error.restype = c_bool
libts.ts_node_has_error.argtypes = [TSNode]


if __name__ == "__main__":
    raise SystemExit(main())
