"""tscore.loader — the shared artifact-loading contract (CONCEPT §8, Phase 5).

The ONE place a compiled grammar ``.so`` becomes a ``tree_sitter.Language``.
Both Product B (``tsgrammar.language``) and Product A (``tsquery.Language``)
load through here, and a packaged bundle's ``loader.py`` delegates here — so a
consumer who never imports tsgrammar gets the identical loading path.

Loading uses the PyCapsule path (Phase-0 verified): the .so exports
``tree_sitter_<name>()``; we wrap the returned pointer in a PyCapsule named
``"tree_sitter.Language"`` and hand it to ``tree_sitter.Language(capsule)``.
Integer-pointer loading is deprecated in py-tree-sitter 0.26 and warns.

Bundle layout (produced by ``BuildResult.package()`` — see tsgrammar.pipeline):

    grammar.so          the compiled parser (export: tree_sitter_<name>)
    node-schema.json    the derived node-schema (the bridge artifact)
    tree-sitter.json    bundle metadata: {"name": ..., "abi": ...}
    loader.py           a thin shim: from tscore.loader import load_bundle
"""

from __future__ import annotations

import ctypes
import json
from dataclasses import dataclass
from pathlib import Path

import tree_sitter

# ---------------------------------------------------------------------------
# the low-level load (shared by B and A)
# ---------------------------------------------------------------------------


def load_grammar_so(so_path: Path | str, grammar_name: str | None = None):
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


# ---------------------------------------------------------------------------
# the bundle contract
# ---------------------------------------------------------------------------


@dataclass
class Bundle:
    """A packaged grammar bundle, loaded and schema-bound (A's entry point)."""

    language: tree_sitter.Language
    lib: object                     # keep alive for the language's lifetime
    schema: object | None           # tscore.NodeSchema (None when absent)
    metadata: dict
    path: Path


def load_bundle(dir: Path | str) -> Bundle:
    """Load a bundle directory: grammar.so + node-schema.json + metadata.

    The grammar name (the .so's export symbol) comes from the metadata's
    `name` field — the bundle's .so is renamed `grammar.so`, so the stem is
    not the symbol. The schema is loaded from node-schema.json when present.
    """
    dir = Path(dir)
    meta_path = dir / "tree-sitter.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"not a grammar bundle: {dir} (no tree-sitter.json metadata; "
            f"see tsgrammar BuildResult.package())")
    metadata = json.loads(meta_path.read_text())
    name = metadata.get("name")
    if not name:
        raise ValueError(
            f"bundle metadata {dir / 'tree-sitter.json'} has no 'name' "
            f"(the grammar's export symbol)")
    so_path = dir / (metadata.get("artifact", "grammar.so"))
    if not so_path.exists():
        raise FileNotFoundError(
            f"bundle {dir}: {so_path.name} missing (metadata says "
            f"artifact={so_path.name!r})")
    language, lib = load_grammar_so(so_path, name)

    schema = None
    schema_rel = metadata.get("schema")
    if schema_rel:
        schema_path = dir / schema_rel
        if schema_path.exists():
            from .schema import NodeSchema
            schema = NodeSchema.from_node_types_json(schema_path, name=name)
    return Bundle(language=language, lib=lib, schema=schema,
                  metadata=metadata, path=dir)
