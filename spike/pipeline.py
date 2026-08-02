"""
Pipeline glue: grammar.json -> tree-sitter generate -> gcc -> .so -> load ->
parse. All CLI/toolchain interaction lives here so the conflict experiment can
capture raw output verbatim.

Toolchain notes (validated in this spike):
  * `tree-sitter generate <path.json>` works directly; grammar.js is bypassed.
  * Without a `tree-sitter.json` config the CLI falls back to ABI 14; with
    `{"metadata": {"version": "0.1.0"}}` it generates ABI 15 (matches the
    Python bindings 0.26.0, which support ABI 13..15).
  * On unresolved conflicts: exit code 1, NO parser.c written (fail-fast, only
    the FIRST conflict is reported), and with `--json` the report goes to
    STDERR.
  * The compiled .so exports `tree_sitter_<grammar_name>`; load it via a
    PyCapsule named "tree_sitter.Language" (int pointer is deprecated in
    py-tree-sitter 0.26).
"""

from __future__ import annotations

import ctypes
import json
import subprocess
from pathlib import Path

import tree_sitter

ABI_15_CONFIG = {"metadata": {"version": "0.1.0"}}


def ensure_abi15_config(dirpath: Path) -> None:
    """Write a minimal tree-sitter.json so the CLI generates ABI 15."""
    cfg = dirpath / "tree-sitter.json"
    if not cfg.exists():
        cfg.write_text(json.dumps(ABI_15_CONFIG))


def run_generate(grammar_json: Path, *, json_report: bool = False,
                 abi15: bool = True) -> subprocess.CompletedProcess:
    """Run `tree-sitter generate` on the given grammar.json. Returns the raw
    CompletedProcess (stdout/stderr/returncode) for verbatim capture."""
    dirpath = grammar_json.parent
    if abi15:
        ensure_abi15_config(dirpath)
    cmd = ["tree-sitter", "generate", str(grammar_json)]
    if json_report:
        cmd.append("--json")
    return subprocess.run(cmd, capture_output=True, text=True,
                          cwd=str(dirpath))


def compile_parser(src_dir: Path, so_path: Path) -> subprocess.CompletedProcess:
    """gcc -O2 -fPIC -shared parser.c -> .so (standard tree-sitter build)."""
    cmd = ["gcc", "-O2", "-fPIC", "-shared",
           "-I", str(src_dir / "tree_sitter"),
           str(src_dir / "parser.c"),
           "-o", str(so_path)]
    return subprocess.run(cmd, capture_output=True, text=True)


def load_language(so_path: Path, grammar_name: str):
    """Load a compiled grammar .so into a tree_sitter.Language.

    Uses a PyCapsule named "tree_sitter.Language" — the non-deprecated path
    in py-tree-sitter 0.26 (int pointers trigger a DeprecationWarning).
    """
    lib = ctypes.CDLL(str(so_path))
    fn = getattr(lib, f"tree_sitter_{grammar_name}")
    fn.restype = ctypes.c_void_p
    ptr = fn()
    pycapsule_new = ctypes.pythonapi.PyCapsule_New
    pycapsule_new.restype = ctypes.py_object
    pycapsule_new.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    capsule = pycapsule_new(ptr, b"tree_sitter.Language", None)
    return tree_sitter.Language(capsule), lib


def parse(lang, source: str):
    parser = tree_sitter.Parser(lang)
    return parser.parse(source.encode("utf-8"))

