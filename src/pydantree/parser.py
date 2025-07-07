from __future__ import annotations

from typing import Optional

from tree_sitter import Language, Parser as _TSParser

from .core import TSNode
from .loader import NodeTypesBootstrap


class Parser:
    """Thin wrapper around `tree_sitter.Parser` that returns typed nodes."""

    def __init__(self, language: Language, *, module_name: str = "data.python_nodes"):
        # ensure the generated classes are available before any parse
        NodeTypesBootstrap.ensure(module_name)
        self._parser = _TSParser(language)

    # ------------------------------------------------------------------
    # Basic parse
    # ------------------------------------------------------------------
    def parse(self, text: str) -> TSNode:
        byte_text = text.encode()
        tree = self._parser.parse(byte_text)
        return TSNode.from_tree_sitter(tree.root_node, byte_text)

    # ------------------------------------------------------------------
    # Incremental re‑parse with an existing Tree
    # ------------------------------------------------------------------
    def parse_incremental(self, text: str, old_tree) -> TSNode:
        byte_text = text.encode()
        tree = self._parser.parse(byte_text, old_tree=old_tree)
        return TSNode.from_tree_sitter(tree.root_node, byte_text)
