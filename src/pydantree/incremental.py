from __future__ import annotations

import bisect
from typing import Tuple

from tree_sitter import Tree
from pydantic import BaseModel, ConfigDict, model_validator

from .core import TSNode
from .parser import Parser


def _point_for_byte(byte_pos: int, buffer: bytes) -> Tuple[int, int]:
    """
    Compute the (row, column) *point* for a given byte offset in *buffer*.

    * Row = number of “\\n” bytes before *byte_pos*.
    * Column = bytes since the previous newline (or start of buffer).

    This is the same calculation Tree-sitter does internally, but we need it
    here because the new `Tree.edit` API (py-tree-sitter ≥ 0.23) requires you
    to pass explicit start/old_end/new_end *points* rather than a dict.
    """
    row = buffer.count(b"\n", 0, byte_pos)
    last_nl = buffer.rfind(b"\n", 0, byte_pos)
    column = byte_pos - (last_nl + 1 if last_nl != -1 else 0)
    return row, column


class ParsedDocument(BaseModel):
    """Pydantic wrapper holding source text, the raw `Tree`, and a validated `TSNode`."""

    text: str
    parser: Parser
    tree: Tree
    root: TSNode

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # --------------------------- Auto‑populate -------------------------
    @model_validator(mode="before")  # type: ignore[misc]
    @classmethod
    def _populate_tree_and_root(cls, data):
        # If the user supplied `tree` and `root`, leave untouched.
        if data.get("tree") is not None and data.get("root") is not None:
            return data
        text: str = data["text"]
        parser: Parser = data["parser"]
        byte_text = text.encode()
        tree = parser._parser.parse(byte_text)
        root = TSNode.from_tree_sitter(tree.root_node, byte_text)
        data["tree"] = tree
        data["root"] = root
        return data

    # Alternate explicit factory (kept for clarity / backward compat)
    @classmethod
    def create(cls, text: str, parser: Parser) -> "ParsedDocument":
        return cls(text=text, parser=parser)

    # --------------------------- Pretty helpers ------------------------
    def pretty(self, **kwargs) -> str:
        """Pretty‑print via the root node."""
        return self.root.pretty(**kwargs)

    def __str__(self) -> str:
        return self.pretty()

    # --------------------------- Edits --------------------------------
    def edit(
        self,
        start_byte: int,
        old_end_byte: int,
        new_end_byte: int,
        new_text: str,
    ) -> None:
        start_pt = _point_for_byte(start_byte, self.text.encode())
        old_end_pt = _point_for_byte(old_end_byte, self.text.encode())
        new_end_pt = _point_for_byte(new_end_byte, self.text.encode())
        self.tree.edit(
            start_byte,
            old_end_byte,
            new_end_byte,
            start_pt,
            old_end_pt,
            new_end_pt,
        )
        self.text = self.text[:start_byte] + new_text + self.text[old_end_byte:]
        byte_text = self.text.encode()
        self.tree = self.parser._parser.parse(byte_text, old_tree=self.tree)
        self.root = TSNode.from_tree_sitter(self.tree.root_node, byte_text)
