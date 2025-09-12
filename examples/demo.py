# examples/demo_pydantree.py
"""End-to-end showcase for *pydantree* wrapped in tidy helper functions.

Run with:

    pydantree-demo          # installed via the pyproject console-script

or

    python -m examples.demo_pydantree  # from project root in editable install

The demo performs six steps:

1. Load the Tree-sitter **Python** grammar (wheel first, compile fallback).
2. Auto-generate typed subclasses from *node-types.json*.
3. Parse a hard-coded snippet to a validated **TSNode** tree.
4. Match on the first **FunctionDefinition** using structural pattern-matching.
5. Apply an incremental edit (swap `print` for `return`) and re-parse cheaply.
6. Dump the modified root to JSON so you can inspect/compare.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import pathlib
import textwrap
import sys
from types import ModuleType
from typing import Tuple
# from pathlib import Path

from pydantree import ParsedDocument, Parser, generate_from_node_types
from tree_sitter import Language

# ---------------------------------------------------------------------------
# 1. Grammar loading helpers
# ---------------------------------------------------------------------------


def _language_from_wheel() -> Tuple[Language, pathlib.Path]:
    """Try to import *tree_sitter_python* and return its Language + base path."""
    import tree_sitter_python as tspy  # type: ignore

    lang = Language(tspy.language())  # helper provided by the wheel
    base = pathlib.Path(importlib.resources.files("tree_sitter_python")).parent
    return lang, base


def _language_from_source() -> Tuple[Language, pathlib.Path]:
    """Fallback: build the shared library from the grammar source repo."""
    repo = pathlib.Path.home() / ".cache" / "tree-sitter-python"
    so_path = pathlib.Path("build/python.so")
    if not so_path.exists():
        print("Compiling Python grammar… (first run only)")
        Language.build_library(str(so_path), [str(repo)])
    lang = Language(str(so_path), "python")
    return lang, repo


def load_python_language() -> Tuple[Language, pathlib.Path]:
    """Unified wrapper that favours the wheel but falls back to source."""
    try:
        return _language_from_wheel()
    except Exception:  # pragma: no cover – wheel not available
        return _language_from_source()


# ---------------------------------------------------------------------------
# 2. Typed-model generation helpers
# ---------------------------------------------------------------------------


def generate_python_types(node_types_json: pathlib.Path) -> ModuleType:
    """Generate subclasses → write to `python_nodes.py` → import + return module."""
    out_path = pathlib.Path("src/data/python_nodes.py")
    generate_from_node_types(str(node_types_json), str(out_path))
    spec = importlib.util.spec_from_file_location("python_nodes", out_path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["python_nodes"] = module
    assert spec.loader  # for mypy
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


# ---------------------------------------------------------------------------
# 3. Demo workflow helpers
# ---------------------------------------------------------------------------


def build_parser(lang: Language) -> Parser:
    return Parser(lang)


def parse_initial_code(parser: Parser) -> ParsedDocument:
    code = textwrap.dedent(
        """
        def greet(name):
            print(f"Hello, {name}!")
        """
    ).lstrip()
    return ParsedDocument(text=code, parser=parser)


def match_first_function(doc: ParsedDocument, types_mod: ModuleType) -> None:
    from python_nodes import FunctionDefinition  # imported dynamically

    node = doc.root.children[0]
    match node:
        case FunctionDefinition(name=id_node, body=body_block):
            print("\nMatched FunctionDefinition ✓")
            print("  name:", id_node.text)
            print("  starts on line", body_block.start_point.row + 1)
        case _:
            print("Unexpected root child:", node.type_name)


def apply_incremental_edit(doc: ParsedDocument) -> None:
    # Replace `print(...)` with `return ...`
    new_line = '    return f"Hello, {name}!"\n'
    old_start = doc.text.find("print")
    old_end = doc.text.find(")", old_start) + 1
    doc.edit(
        start_byte=old_start,
        old_end_byte=old_end,
        new_end_byte=old_start + len(new_line),
        new_text=new_line,
    )
    print(
        "\nIncremental re-parse complete (new byte size:",
        doc.tree.root_node.end_byte,
        ")\n",
    )


def dump_root_json(doc: ParsedDocument) -> None:
    print("\nRoot serialised to JSON (formatted)…\n")
    data = json.loads(doc.root.model_dump_json())
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# 4. main() orchestrator
# ---------------------------------------------------------------------------


def main() -> None:
    lang, base_path = load_python_language()
    print("Loaded Python grammar from", base_path)
    root = pathlib.Path(__file__).parent.parent.parent  # project root
    print("Project root:", root)

    node_types_json = root / "src" / "data" / "node-types.json"
    # types_mod = generate_python_types(node_types_json)
    # print("Generated typed subclasses →", types_mod.__file__)

    parser = build_parser(lang)
    doc = parse_initial_code(parser)
    print("Initial parse complete (bytes:", doc.tree.root_node.end_byte, ")")

    # match_first_function(doc, types_mod)
    # apply_incremental_edit(doc)
    # dump_root_json(doc)
    print(
        f"\nDemo complete!  You can inspect the modified `ParsedDocument`:\n{doc.pretty()}\n"
    )


# ---------------------------------------------------------------------------
# 5. Standard script guard
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
