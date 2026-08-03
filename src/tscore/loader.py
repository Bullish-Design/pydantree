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

Wasm artifacts (Phase 7): the metadata's ``artifact`` field may name a
``.wasm`` instead of the ``.so`` (the seam's natural extension point).
``load_bundle`` dispatches on the artifact extension and raises
``WasmRuntimeUnavailableError`` with the exact state of the wasm path when a
wasm bundle is loaded into a binding with no wasm runtime — the Phase-7 probe
(real rust.wasm + wasmtime + the wasm-enabled C library) showed the mechanism
works at ~1.6x the native parse cost, but py-tree-sitter 0.26 has NO wasm
support, so a wasm load requires a custom tree-sitter binding built with
TREE_SITTER_FEATURE_WASM (a fork, not a dependency pin). ``load_grammar_wasm``
implements the load for callers that DO have the wasm-capable runtime
(TSGRAMMAR_WASM_LIB / TSGRAMMAR_WASMTIME_LIB env-pointed, see the probe under
.scratch/009-phase7/).
"""

from __future__ import annotations

import ctypes
import json
import os
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
# the wasm load (Phase 7 probe — the seam's extension point)
# ---------------------------------------------------------------------------

class WasmRuntimeUnavailableError(RuntimeError):
    """A bundle names a .wasm artifact but no wasm-capable runtime is wired.

    py-tree-sitter (the standard binding, pinned >=0.26 by all four
    distributions) has NO wasm support — a wasm language needs a parser bound
    to a wasm store (tree-sitter's C library compiled with
    TREE_SITTER_FEATURE_WASM + a wasmtime engine). The Phase-7 probe built
    exactly that (rust.wasm through wasmtime 29.0.0, real parse, ~1.6x the
    native parse cost) — see .scratch/009-phase7/. Landing wasm in A means
    forking/replacing the py-tree-sitter binding, not pinning a new package,
    so the standard light install raises this instead of a silent mis-load.
    """


def _wasm_runtime_paths() -> tuple[Path, Path] | None:
    """The wasm-capable runtime libraries, env-pointed (the probe's layout):
    TSGRAMMAR_WASM_LIB = libtree-sitter built with TREE_SITTER_FEATURE_WASM,
    TSGRAMMAR_WASMTIME_LIB = the matching libwasmtime (wasmtime 29.x for
    tree-sitter 0.25.3). Returns None when either is unset/absent."""
    lib = os.environ.get("TSGRAMMAR_WASM_LIB")
    wt = os.environ.get("TSGRAMMAR_WASMTIME_LIB")
    if not lib or not wt:
        return None
    lib_p, wt_p = Path(lib), Path(wt)
    if not lib_p.exists() or not wt_p.exists():
        return None
    return lib_p, wt_p


def load_grammar_wasm(wasm_path: Path | str, grammar_name: str):
    """Load a compiled grammar .wasm through a wasm-capable runtime.

    The wasm twin of `load_grammar_so`: the grammar .wasm (tree-sitter CLI
    `build --wasm`) is loaded via tree-sitter's official wasm store
    (ts_wasm_store_load_language over wasmtime) — the same path the CLI and
    the editor ecosystem use. Requires the wasm-capable runtime libraries
    (TSGRAMMAR_WASM_LIB / TSGRAMMAR_WASMTIME_LIB — the Phase-7 probe's build:
    libtree-sitter compiled with TREE_SITTER_FEATURE_WASM + libwasmtime from
    the wasmtime Python wheel, version-matched to the tree-sitter pin).

    Returns (language, runtime) — `language` is a `WasmLanguage` (a minimal
    parse surface over the ctypes bridge: a wasm language cannot be wrapped
    in a tree_sitter.Language capsule, py-tree-sitter 0.26 has no wasm store).
    Raises WasmRuntimeUnavailableError when the runtime is not configured.
    """
    paths = _wasm_runtime_paths()
    if paths is None:
        raise WasmRuntimeUnavailableError(
            f"bundle artifact is a .wasm but no wasm-capable runtime is wired. "
            f"py-tree-sitter (the standard binding) has no wasm support; a "
            f"wasm load needs libtree-sitter built with TREE_SITTER_FEATURE_WASM "
            f"plus a wasmtime engine — set TSGRAMMAR_WASM_LIB=<that .so> and "
            f"TSGRAMMAR_WASMTIME_LIB=<libwasmtime.so> to use the Phase-7 probe "
            f"bridge (.scratch/009-phase7/evidence/ + probe_wasm_runtime.py)")
    from ._wasm_bridge import WasmRuntime
    rt = WasmRuntime(*paths)
    return rt.load_language(wasm_path, grammar_name), rt


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
    if so_path.suffix == ".wasm":
        # the wasm artifact path (Phase 7): a wasm language cannot be wrapped
        # in a tree_sitter.Language capsule — the wasm bridge returns its own
        # minimal parse surface, or raises the clear WasmRuntimeUnavailableError
        # when the wasm-capable runtime is not configured.
        language, lib = load_grammar_wasm(so_path, name)
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
