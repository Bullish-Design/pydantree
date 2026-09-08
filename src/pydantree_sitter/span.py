"""Source spans for typed syntax nodes."""

from __future__ import annotations

import tree_sitter


class Span:
    """A source span with 1-based line numbers."""

    __slots__ = (
        "column",
        "end_byte",
        "end_column",
        "end_line",
        "line",
        "start_byte",
        "text",
    )

    def __init__(self, line, column, end_line, end_column,
                 start_byte, end_byte, text):
        self.line = line
        self.column = column
        self.end_line = end_line
        self.end_column = end_column
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.text = text

    @classmethod
    def from_node(cls, node: tree_sitter.Node) -> Span:
        # `Point` is a tuple — unpack it, never read `.row` / `.column`.
        #
        # tree-sitter 0.26.0 reworked Point into a tuple subclass whose
        # `.row` / `.column` getters return a BORROWED reference instead of a
        # new one. Every read of a non-immortal int can leave the int one
        # refcount short. Tuple access is safe on affected and fixed builds.
        r = node.range
        start_row, start_column = r.start_point
        end_row, end_column = r.end_point
        text = node.text.decode("utf-8", "replace") if node.text else ""
        return cls(start_row + 1, start_column,
                   end_row + 1, end_column,
                   r.start_byte, r.end_byte, text)

    def __repr__(self) -> str:  # pragma: no cover
        return (f"Span({self.line}:{self.column}-"
                f"{self.end_line}:{self.end_column} {self.text!r})")
