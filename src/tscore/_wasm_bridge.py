"""tscore._wasm_bridge — the wasm-capable runtime bridge (Phase 7 probe).

The grammar .wasm (tree-sitter CLI `build --wasm`) is a standalone SIDE_MODULE
with the full parse tables + lex functions; the HOST parse engine is the
tree-sitter C library, and a wasm language needs a parser bound to a wasm
store. This bridge drives that official path (ts_wasm_store_load_language)
through ctypes — the same mechanism the tree-sitter CLI/editor ecosystem uses,
with wasmtime as the wasm engine.

Runtime requirements (the Phase-7 probe's build, see .scratch/009-phase7/):

    libtree-sitter-with-wasm.so   libtree-sitter compiled with
                                  TREE_SITTER_FEATURE_WASM against the
                                  wasmtime C API headers (version-matched to
                                  the tree-sitter pin: wasmtime 29.x for CLI
                                  0.25.3)
    libwasmtime.so                from the wasmtime Python wheel of the same
                                  version

Wired via TSGRAMMAR_WASM_LIB / TSGRAMMAR_WASMTIME_LIB (see
tscore.loader.load_grammar_wasm). Returns WasmLanguage — a minimal parse
surface; a wasm language CANNOT be wrapped in a tree_sitter.Language capsule
(py-tree-sitter 0.26 has no wasm store), which is the heart of the Phase-7
wasm verdict.
"""

from __future__ import annotations

import ctypes
from pathlib import Path

c_void_p = ctypes.c_void_p
c_char_p = ctypes.c_char_p
c_uint32 = ctypes.c_uint32
c_bool = ctypes.c_bool


class TSNode(ctypes.Structure):
    _fields_ = [("context", ctypes.c_uint32 * 4),
                ("id", ctypes.c_void_p),
                ("tree", ctypes.c_void_p)]


class TSWasmError(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_int), ("message", ctypes.c_char_p)]


class WasmRuntime:
    """A wasmtime engine + tree-sitter wasm store over the C API."""

    def __init__(self, libts: Path, libwt: Path):
        self._libwt = ctypes.CDLL(str(libwt))
        self._libts = ctypes.CDLL(str(libts))
        self._bind(self._libwt, self._libts)
        self._engine = self._libwt.wasm_engine_new()
        if not self._engine:
            raise RuntimeError("wasm_engine_new failed")
        err = TSWasmError()
        self._store = self._libts.ts_wasm_store_new(self._engine,
                                                    ctypes.byref(err))
        if not self._store:
            raise RuntimeError(f"ts_wasm_store_new: {err.message}")

    @staticmethod
    def _bind(libwt, libts) -> None:
        libwt.wasm_engine_new.restype = c_void_p
        libwt.wasm_engine_delete.argtypes = [c_void_p]
        libts.ts_wasm_store_new.restype = c_void_p
        libts.ts_wasm_store_new.argtypes = [c_void_p,
                                            ctypes.POINTER(TSWasmError)]
        libts.ts_wasm_store_load_language.restype = c_void_p
        libts.ts_wasm_store_load_language.argtypes = [
            c_void_p, c_char_p, c_char_p, c_uint32,
            ctypes.POINTER(TSWasmError)]
        libts.ts_parser_new.restype = c_void_p
        libts.ts_parser_delete.argtypes = [c_void_p]
        libts.ts_parser_set_language.restype = c_bool
        libts.ts_parser_set_language.argtypes = [c_void_p, c_void_p]
        libts.ts_parser_set_wasm_store.argtypes = [c_void_p, c_void_p]
        libts.ts_parser_parse_string.restype = c_void_p
        libts.ts_parser_parse_string.argtypes = [c_void_p, c_void_p,
                                                 c_char_p, c_uint32]
        libts.ts_tree_delete.argtypes = [c_void_p]
        libts.ts_tree_root_node.restype = TSNode
        libts.ts_tree_root_node.argtypes = [c_void_p]
        libts.ts_node_has_error.restype = c_bool
        libts.ts_node_has_error.argtypes = [TSNode]
        libts.ts_node_child_count.restype = c_uint32
        libts.ts_node_child_count.argtypes = [TSNode]
        libts.ts_language_version.restype = c_uint32
        libts.ts_language_version.argtypes = [c_void_p]
        libts.ts_language_name.restype = c_char_p
        libts.ts_language_name.argtypes = [c_void_p]
        libts.ts_language_symbol_name.restype = c_char_p
        libts.ts_language_symbol_name.argtypes = [c_void_p, ctypes.c_uint16]
        libts.ts_node_type.restype = c_char_p
        libts.ts_node_type.argtypes = [TSNode]
        libts.ts_node_is_named.restype = c_bool
        libts.ts_node_is_named.argtypes = [TSNode]
        libts.ts_node_is_missing.restype = c_bool
        libts.ts_node_is_missing.argtypes = [TSNode]
        libts.ts_node_child.restype = TSNode
        libts.ts_node_child.argtypes = [TSNode, c_uint32]
        libts.ts_node_start_byte.restype = c_uint32
        libts.ts_node_start_byte.argtypes = [TSNode]
        libts.ts_node_end_byte.restype = c_uint32
        libts.ts_node_end_byte.argtypes = [TSNode]

    def load_language(self, wasm_path: Path | str, name: str) -> "WasmLanguage":
        wasm = Path(wasm_path).read_bytes()
        err = TSWasmError()
        lang = self._libts.ts_wasm_store_load_language(
            self._store, name.encode(), wasm, len(wasm), ctypes.byref(err))
        if not lang:
            raise RuntimeError(f"ts_wasm_store_load_language: {err.message}")
        return WasmLanguage(self, lang)

    def close(self) -> None:
        self._libwt.wasm_engine_delete(self._engine)


class WasmLanguage:
    """A wasm-loaded grammar: a minimal parse surface (name, abi, parse)."""

    def __init__(self, runtime: WasmRuntime, lang: int):
        self._rt = runtime
        self._lang = lang
        self._parser = None
        self.name = (runtime._libts.ts_language_name(lang) or b"").decode()
        self.abi_version = runtime._libts.ts_language_version(lang)

    def parse(self, source: str | bytes) -> "WasmTree":
        if self._parser is None:
            parser = self._rt._libts.ts_parser_new()
            # the parser OWNS the wasm store (parser.c requires it BEFORE
            # set_language for a wasm language)
            self._rt._libts.ts_parser_set_wasm_store(parser, self._rt._store)
            if not self._rt._libts.ts_parser_set_language(parser, self._lang):
                raise RuntimeError("ts_parser_set_language failed")
            self._parser = parser
        data = source if isinstance(source, bytes) else source.encode("utf-8")
        tree = self._rt._libts.ts_parser_parse_string(
            self._parser, None, data, len(data))
        if not tree:
            raise RuntimeError("ts_parser_parse_string returned NULL")
        return WasmTree(self._rt, tree, data)


class WasmTree:
    """A parsed tree over the wasm bridge: root_node + a sexp renderer."""

    def __init__(self, runtime: WasmRuntime, tree: int, src: bytes):
        self._rt = runtime
        self._tree = tree
        self.src = src
        self.root_node = runtime._libts.ts_tree_root_node(tree)

    def has_error(self) -> bool:
        return bool(self._rt._libts.ts_node_has_error(self.root_node))

    def _sexp(self, node) -> str:
        rt = self._rt
        kind = (rt._libts.ts_node_type(node) or b"").decode()
        is_named = bool(rt._libts.ts_node_is_named(node))
        if not is_named:
            start = rt._libts.ts_node_start_byte(node)
            end = rt._libts.ts_node_end_byte(node)
            return f"'{self.src[start:end].decode('utf-8', 'replace')}'"
        n = rt._libts.ts_node_child_count(node)
        parts = [kind]
        for i in range(n):
            child = rt._libts.ts_node_child(node, i)
            if rt._libts.ts_node_is_missing(child):
                parts.append("MISSING")
            else:
                parts.append(self._sexp(child))
        return f"({' '.join(parts)})"

    def sexp(self) -> str:
        return self._sexp(self.root_node)
