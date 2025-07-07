#!/usr/bin/env python3
"""
file_parse_graphsitter_demo.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verify `PyFile` round‑trip and mutation using **Graph Sitter** only.

Steps
1. Build an in‑memory codebase via `Codebase.from_string()`.
2. Grab the first `PyFile` object from `codebase.files`.
3. Monkey‑patch a lightweight `to_source()` alias if the node only
   exposes `.source` (older GraphSitter builds).
4. Wrap the node with `pydantree.PyFile.from_graphsitter`.
5. Assert lossless round‑trip, print discovered symbols, mutate, and
   print updated source.
"""

from __future__ import annotations

from textwrap import dedent

from graph_sitter import Codebase  # GraphSitter high‑level API
from pydantree import PyFile, PyFunction

# ---------------------------------------------------------------------------
# Sample module we’ll parse and manipulate
# ---------------------------------------------------------------------------
SAMPLE_SRC = dedent(
    """#!/usr/bin/env python3
    '''Demo module.'''

    import math

    class Circle:
        def __init__(self, r: float):
            self.r = r

        def area(self) -> float:
            return math.pi * self.r ** 2
    """
).lstrip()

# ---------------------------------------------------------------------------
# Parse via Graph Sitter
# ---------------------------------------------------------------------------
codebase = Codebase.from_string(SAMPLE_SRC, language="python")
pyfile_node = codebase.files[0]  # graphsitter.PyFile instance

# Ensure compatibility with Pydantree’s `to_source()` expectation
if not hasattr(pyfile_node, "to_source"):
    pyfile_node.to_source = lambda: pyfile_node.source  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Wrap in validated Pydantree model
# ---------------------------------------------------------------------------
pyfile = PyFile.from_graphsitter(pyfile_node)

assert pyfile.to_source() == SAMPLE_SRC, "Round‑trip failed: source mismatch"
print("✅ Round‑trip OK — original source preserved.\n")

print("Imports:   ", [imp.to_source().strip() for imp in pyfile.imports])
print("Classes:   ", [cls.class_name for cls in pyfile.classes])
print("Functions: ", [func.name for func in pyfile.functions])
print("Docstring: ", pyfile.docstring)
print()

# ---------------------------------------------------------------------------
# Mutate — add a helper function and emit again
# ---------------------------------------------------------------------------
helper_fn = (
    PyFunction.builder("describe_circle")
    .with_param("c", "Circle")
    .with_return_type("str")
    .with_docstring("Return a human description of a circle.")
    .with_body("return f'Circle(radius={c.r})'")
    .build()
)
pyfile.add_function(helper_fn)

print("After adding describe_circle():\n")
print(pyfile.to_source())
