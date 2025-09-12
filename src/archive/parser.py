from __future__ import annotations

from typing import Optional

from tree_sitter import Language, Parser as _TSParser

from .core import TSNode
from .loader import NodeTypesBootstrap

NODE_MODULE = "data.pydantree_nodes"


class Parser:
    """Thin wrapper around `tree_sitter.Parser` that returns typed nodes."""

    def __init__(self, language: Language, *, module_name: str = NODE_MODULE):
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

    # ------------------------------------------------------------------
    # Convenience factory methods
    # ------------------------------------------------------------------
    @classmethod
    def for_python(cls, module_name: str = NODE_MODULE) -> Parser:
        """Create parser for Python language."""
        try:
            import tree_sitter_python as tspy

            language = Language(tspy.language())
            return cls(language, module_name=module_name)
        except ImportError:
            raise ImportError(
                "tree-sitter-python is required for Python parsing. "
                "Install with: pip install tree-sitter-python"
            )

    @classmethod
    def for_language(
        cls, language_name: str, module_name: Optional[str] = None
    ) -> Parser:
        """Create parser for named language (requires appropriate tree-sitter package)."""
        if language_name == "python":
            return cls.for_python(module_name or NODE_MODULE)
        else:
            raise NotImplementedError(
                f"Language '{language_name}' not yet supported. "
                "Use Parser(language) constructor directly."
            )
