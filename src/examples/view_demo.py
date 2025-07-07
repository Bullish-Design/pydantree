"""
demo_views_usage.py – quick tour of the high-level Pydantree views layer
-----------------------------------------------------------------------

Run it with:  python demo_views_usage.py
"""

import importlib

from typing import Tuple
from pathlib import Path
from pydantree.views import PyModule, PyTransformer  # <-- the file you just added
from pydantree import ParsedDocument, Parser, generate_from_node_types
from tree_sitter import Language

# ---------------------------------------------------------------------
# 1) Parse some Python source (from a string or a file)
# ---------------------------------------------------------------------


def _language_from_wheel() -> Tuple[Language, Path]:
    """Try to import *tree_sitter_python* and return its Language + base path."""
    import tree_sitter_python as tspy  # type: ignore

    lang = Language(tspy.language())  # helper provided by the wheel
    base = Path(importlib.resources.files("tree_sitter_python")).parent
    return lang, base


def _language_from_source() -> Tuple[Language, Path]:
    """Fallback: build the shared library from the grammar source repo."""
    repo = Path.home() / ".cache" / "tree-sitter-python"
    so_path = Path("build/python.so")
    if not so_path.exists():
        print("Compiling Python grammar… (first run only)")
        Language.build_library(str(so_path), [str(repo)])
    lang = Language(str(so_path), "python")
    return lang, repo


def load_python_language() -> Tuple[Language, Path]:
    """Unified wrapper that favours the wheel but falls back to source."""
    try:
        return _language_from_wheel()
    except Exception:  # pragma: no cover – wheel not available
        return _language_from_source()


lang, base_path = load_python_language()

SOURCE = """
class Greeter:
    def greet(self, name):
        print(f"Hello, {name}!")

def add(a, b):
    return a + b
"""

module = PyModule.parse(SOURCE)  # same as PyModule.parse_file(<path>)
parser = Parser(lang)
doc = ParsedDocument(text=SOURCE, parser=parser)

# ---------------------------------------------------------------------
# 2) Explore the code with the chainable selector API
# ---------------------------------------------------------------------

"""
print(f"Doc:\n\n{doc.text}\n")

print(f"All function names: ")  # "{[fn.name for fn in module.functions()]}\n")
for fn in doc.functions():
    print(f"  - {fn.__class__.__name__} '{fn.name()}'")


print(f"Functions named 'add': {[fn.name() for fn in doc.functions().named('add')]}\n")

print(
    f"Functions that contain a return statement: {[fn.name() for fn in doc.functions().where(lambda f: f.has_return())]}\n"
)
"""
print(f"\n{'=' * 50}\n")

print(f"Module:\n\n{module.text}\n")
# print(f"Module:\n\n{[child for child in module.children()]}\n")

print(f"All function names: ")  # "{[fn.name for fn in module.functions()]}\n")
for fn in module.functions():
    print(f"  - {fn.__class__.__name__} '{fn.name()}'")


print(
    f"Functions named 'add': {[fn.name() for fn in module.functions().named('add')]}\n"
)

print(
    f"Functions that contain a return statement: {[fn.name() for fn in module.functions().where(lambda f: f.has_return())]}\n"
)

# ---------------------------------------------------------------------
# 3) Perform a simple codemod with PyTransformer
# ---------------------------------------------------------------------


class PrintToLogger(PyTransformer):
    """
    Naïvely rewrite   print(...)  ->  logger.info(...)
    (Real code would use the full CST to be safer, but this keeps the
    example short and shows the edit workflow.)
    """

    def visit_expression_statement(self, node):
        text = node.text.lstrip()
        if text.startswith("print("):
            return node.text.replace("print(", "logger.info(", 1)


transformed_src = PrintToLogger(module).visit()

# ---------------------------------------------------------------------
# 4) Show the result
# ---------------------------------------------------------------------

print("\n--------- transformed code ----------\n")
print(transformed_src)
