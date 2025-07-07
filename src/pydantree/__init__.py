"""pydantree – MVP implementation of a typed Tree‑sitter wrapper.

This package exposes:

* **TSNode / TSPoint** – language‑agnostic Pydantic core primitives mirroring tree‑sitter `Node` metadata.
* **Parser** – thin convenience wrapper around `tree_sitter.Parser` that returns validated models.
* **ParsedDocument** – incremental‑parsing helper that keeps text + tree in sync and lets you apply byte‑range edits.
* **generate_from_node_types** – utility that reads a grammar's `node-types.json` and emits strongly‑typed subclasses plus a `NODE_MAP` registry.
* **CLI** – `python -m pydantree gen node-types.json --out mylang_types.py` for code‑generation.

The goal is to provide the smallest complete feature‑set promised in the README while keeping the code easy to follow.  No extraneous dependencies beyond Pydantic v2 and py‑tree‑sitter.
"""

from __future__ import annotations

from .core import TSNode, TSPoint
from .parser import Parser
from .incremental import ParsedDocument
from .generator import generate_from_node_types
from .loader import NodeTypesBootstrap
from .views import PyView, PyModule, PyFunction, PyClass, QuerySet, PyTransformer

__all__ = [
    "TSNode",
    "TSPoint",
    "Parser",
    "ParsedDocument",
    "generate_from_node_types",
    "NodeTypesBootstrap",
    "PyView",
    "PyModule",
    "PyFunction",
    "PyClass",
    "QuerySet",
    "PyTransformer",
]
__version__ = "0.1.2"
