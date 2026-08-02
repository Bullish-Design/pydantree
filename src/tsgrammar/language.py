"""
tsgrammar.language — loading a compiled grammar .so into tree_sitter.Language
and parsing.

Uses the PyCapsule path from Phase 0 (`spike/pipeline.py`): the .so exports
`tree_sitter_<name>()`; we wrap the returned pointer in a PyCapsule named
`"tree_sitter.Language"` and hand it to `tree_sitter.Language(capsule)`.
Integer-pointer loading is deprecated in py-tree-sitter 0.26 and warns.
"""

from __future__ import annotations

import ctypes
from pathlib import Path

import tree_sitter


def load_language(so_path: Path | str, grammar_name: str | None = None):
    """Load a compiled grammar .so into a tree_sitter.Language.

    `grammar_name` is the export symbol (`tree_sitter_<name>`) and defaults to
    the .so's file stem. Returns `(language, lib)` — keep `lib` alive for the
    language's lifetime (the PyCapsule does not own the C library).
    """
    so_path = Path(so_path).resolve()
    name = grammar_name or so_path.stem
    lib = ctypes.CDLL(str(so_path))
    fn = getattr(lib, f"tree_sitter_{name}")
    fn.restype = ctypes.c_void_p
    ptr = fn()
    pycapsule_new = ctypes.pythonapi.PyCapsule_New
    pycapsule_new.restype = ctypes.py_object
    pycapsule_new.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    capsule = pycapsule_new(ptr, b"tree_sitter.Language", None)
    return tree_sitter.Language(capsule), lib


def parse(lang, source: str, encoding: str = "utf-8"):
    """Parse text with the loaded language (a small convenience wrapper)."""
    parser = tree_sitter.Parser(lang)
    return parser.parse(source.encode(encoding))
