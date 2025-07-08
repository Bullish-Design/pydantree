from __future__ import annotations

from typing import List, ClassVar

from pydantic import BaseModel, ConfigDict


class TSPoint(BaseModel):
    """A simple row/column point (0‑indexed) mirroring Tree‑sitter's `Point`."""

    row: int
    column: int

    model_config = ConfigDict(frozen=True)

    def __str__(self) -> str:
        return f"({self.row},{self.column})"


class TSNode(BaseModel):
    """Language‑agnostic representation of a Tree‑sitter `Node`."""

    type_name: str
    start_byte: int
    end_byte: int
    start_point: TSPoint
    end_point: TSPoint
    text: str
    children: List[TSNode] = []
    is_named: bool  # `is_named` is always true for TSNode

    # Allow nested models + immutability for structural pattern matching safety
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    # Enable `match … case` ergonomics
    __match_args__ = ("type_name", "children")

    _registry: ClassVar[dict[str, type[TSNode]]] = {}

    @classmethod
    def register_subclasses(cls, mapping: dict[str, type[TSNode]]) -> None:
        """Merge *mapping* (token → subclass) into the global registry."""
        cls._registry.update(mapping)

    # Construction helpers
    @classmethod
    def from_tree_sitter(cls, node, text_bytes: bytes) -> TSNode:
        """Recursively convert a `tree_sitter.Node` into a validated `TSNode`."""

        sub_cls = cls._registry.get(node.type, cls)
        children = [cls.from_tree_sitter(c, text_bytes) for c in node.children]
        text = text_bytes[node.start_byte : node.end_byte].decode(errors="ignore")
        return sub_cls(
            type_name=node.type,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_point=TSPoint(row=node.start_point[0], column=node.start_point[1]),
            end_point=TSPoint(row=node.end_point[0], column=node.end_point[1]),
            text=text,
            children=children,
            is_named=node.is_named,
        )

    # Convenient JSON dump while preserving child order
    def dict(self, *args, **kwargs):
        return super().model_dump(*args, **kwargs)

    # Pretty‑print helpers
    def pretty(
        self,
        indent: int = 0,
        indent_str: str = "  ",
        max_text: int = 40,
    ) -> str:
        """Return a string that looks like nested `TSNode(…)` constructor calls.

        Example output (truncated):
        ```
        TSNode(
          type_name='module',
          children=[
            TSNode(type_name='function_definition', children=[ … ]),
          ]
        )
        ```
        """
        ind = indent_str * indent
        nxt = indent_str * (indent + 1)

        class_name = self.__class__.__name__
        # print(f"{ind}{class_name}(")
        # Core scalar fields – skip `children` for now
        scalar_parts = [
            # f"type_name={self.type_name!r}",
            # f"start_byte={self.start_byte}",
            # f"end_byte={self.end_byte}",
            # f"start_point={repr(self.start_point)}",
            # f"end_point={repr(self.end_point)}",
        ]
        # Optional text snippet
        if max_text and self.text.strip():
            snippet = self.text.strip().replace("\n", " ")
            if len(snippet) > max_text:
                snippet = snippet[: max_text - 1] + "…"
            scalar_parts.append(f"text={snippet!r}")

        # Children
        if self.children:
            child_strs = [
                c.pretty(indent + 2, indent_str, max_text) for c in self.children
            ]
            children_block = "children=[\n" + ",\n".join(child_strs) + f"\n{nxt}]"
            scalar_parts.append(children_block)

        joined = ",\n".join(f"{nxt}{part}" for part in scalar_parts)
        return f"{ind}{class_name}(\n{joined}\n{ind})"

    # Make `print(node)` use the pretty representation
    def __str__(self) -> str:
        return self.pretty()

    def __repr__(self) -> str:
        return f"TSNode({self.type_name!r}, …)"  # short repr
