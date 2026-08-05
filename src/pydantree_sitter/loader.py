"""pydantree_sitter.loader — the shared artifact-loading contract (CONCEPT §8, Phase 5).

The ONE place a compiled grammar ``.so`` becomes a ``tree_sitter.Language``.
Both Product B (``pydantree_sitter_grammar.language``) and Product A (``pydantree_sitter.Language``)
load through here, and a packaged bundle's ``loader.py`` delegates here — so a
consumer who never imports pydantree_sitter_grammar gets the identical loading path.

Loading uses the PyCapsule path (Phase-0 verified): the .so exports
``tree_sitter_<name>()``; we wrap the returned pointer in a PyCapsule named
``"tree_sitter.Language"`` and hand it to ``tree_sitter.Language(capsule)``.
Integer-pointer loading is deprecated in py-tree-sitter 0.26 and warns.

Bundle layout (produced by ``BuildResult.package()`` — see pydantree_sitter_grammar.pipeline):

    grammar.so          the compiled parser (export: tree_sitter_<name>)
    node-schema.json    the derived node-schema (the bridge artifact)
    tree-sitter.json    bundle metadata: {"name": ..., "abi": ...}
    loader.py           a thin shim: from pydantree_sitter.loader import load_bundle

Wasm artifacts (Phase 7): the metadata's ``artifact`` field may name a
``.wasm`` instead of the ``.so`` (the seam's natural extension point).
``load_bundle`` dispatches on the artifact extension and raises
``WasmRuntimeUnavailableError`` unconditionally for a wasm artifact: the
Phase-7 probe (real rust.wasm + wasmtime + the wasm-enabled C library) showed
the mechanism works at ~1.6x the native parse cost, but py-tree-sitter 0.26
has NO wasm support, so a wasm load requires a custom tree-sitter binding
built with TREE_SITTER_FEATURE_WASM (a fork, not a dependency pin). The
probe's bridge lives at `.scratch/projects/009-phase7/wasm_bridge.py` (moved
out of the shipped seam in the 014 refactor) — a consumer that genuinely
needs wasm forks the binding and uses that code directly.
"""

from __future__ import annotations

import ctypes
import json
from dataclasses import dataclass
from pathlib import Path

import tree_sitter

from .errors import BundleError

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
# the wasm load (Phase 7 probe — the seam's extension point)
# ---------------------------------------------------------------------------

class WasmRuntimeUnavailableError(RuntimeError):
    """A bundle names a .wasm artifact; there is no wasm path in the light
    seam anymore.

    py-tree-sitter (the standard binding, pinned >=0.26) has NO wasm support —
    a wasm language needs a parser bound to a wasm store (tree-sitter's C
    library compiled with TREE_SITTER_FEATURE_WASM + a wasmtime engine). The
    Phase-7 probe built exactly that (rust.wasm through wasmtime 29.0.0, real
    parse, ~1.6x the native parse cost) — its bridge lives at
    `.scratch/projects/009-phase7/wasm_bridge.py` (moved out of the shipped
    seam in the 014 refactor). Landing wasm in A means forking/replacing the
    py-tree-sitter binding, not pinning a new package, so the standard light
    install raises this instead of a silent mis-load.
    """


# ---------------------------------------------------------------------------
# the bundle contract
# ---------------------------------------------------------------------------


@dataclass
class Bundle:
    """A packaged grammar bundle, loaded and schema-bound (A's entry point)."""

    language: tree_sitter.Language
    lib: object                     # keep alive for the language's lifetime
    schema: object | None           # pydantree_sitter.NodeSchema (None when absent)
    metadata: dict
    path: Path


def load_bundle(dir: Path | str) -> Bundle:
    """Load a bundle directory: grammar.so + node-schema.json + metadata.

    The grammar name (the .so's export symbol) comes from the metadata's
    `name` field — the bundle's .so is renamed `grammar.so`, so the stem is
    not the symbol. The schema is loaded from node-schema.json when present.

    Bundle format (D12): the metadata's `bundle_format` int versioning the
    artifact contract. Absent = format 1 (the original layout — accepted);
    an unknown (>2) format is rejected with `BundleError` naming both
    versions, so the artifact contract can never silently shift.
    """
    dir = Path(dir)
    meta_path = dir / "tree-sitter.json"
    if not meta_path.exists():
        raise BundleError(
            f"not a grammar bundle: {dir} (no tree-sitter.json metadata; "
            f"see pydantree_sitter_grammar BuildResult.package())")
    metadata = json.loads(meta_path.read_text())
    fmt = metadata.get("bundle_format", 1)
    if not isinstance(fmt, int):
        raise BundleError(
            f"bundle {dir}: bundle_format must be an int, got {fmt!r}")
    if fmt > 2:
        raise BundleError(
            f"bundle {dir}: unknown bundle_format {fmt} — this loader "
            f"understands formats 1 and 2 (2 is the current; 1 is the "
            f"original layout, still accepted)")
    name = metadata.get("name")
    if not name:
        raise BundleError(
            f"bundle metadata {dir / 'tree-sitter.json'} has no 'name' "
            f"(the grammar's export symbol)")
    so_path = dir / (metadata.get("artifact", "grammar.so"))
    if not so_path.exists():
        raise BundleError(
            f"bundle {dir}: {so_path.name} missing (metadata says "
            f"artifact={so_path.name!r})")
    if so_path.suffix == ".wasm":
        # the wasm artifact path (Phase 7 probe, retired from the shipped
        # seam in the 014 refactor): py-tree-sitter cannot wrap a wasm
        # language — the bridge is at
        # `.scratch/projects/009-phase7/wasm_bridge.py`. The seam raises the
        # clear error unconditionally (no env-var protocol in the shipped
        # path; a consumer that needs wasm forks the binding and uses the
        # probe code directly).
        raise WasmRuntimeUnavailableError(
            f"bundle {dir} names a .wasm artifact but the shipped seam has no "
            f"wasm path: py-tree-sitter (the standard binding) has no wasm "
            f"support, and a wasm load needs libtree-sitter built with "
            f"TREE_SITTER_FEATURE_WASM plus a wasmtime engine (a fork, not a "
            f"dependency pin). The Phase-7 probe bridge lives at "
            f".scratch/projects/009-phase7/wasm_bridge.py — see its README "
            f"for the env-var protocol (TSGRAMMAR_WASM_LIB / "
            f"TSGRAMMAR_WASMTIME_LIB).")
    else:
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
