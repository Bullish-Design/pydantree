from __future__ import annotations

from typing import List, ClassVar, Optional, Dict, Any

from pydantic import BaseModel, ConfigDict, Field


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
    children: List[TSNode] = Field(default_factory=list)
    is_named: bool = True  # `is_named` is always true for TSNode
    field_name: Optional[str] = None  # Named field if this is a field child

    # Allow nested models + immutability for structural pattern matching safety
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    # Enable `match … case` ergonomics
    __match_args__ = ("type_name", "children")

    _registry: ClassVar[Dict[str, type[TSNode]]] = {}

    @classmethod
    def register_subclasses(cls, mapping: Dict[str, type[TSNode]]) -> None:
        """Merge *mapping* (token → subclass) into the global registry."""
        cls._registry.update(mapping)

    # Construction helpers
    @classmethod
    def from_tree_sitter(cls, node, text_bytes: bytes) -> TSNode:
        """Recursively convert a `tree_sitter.Node` into a validated `TSNode`."""
        sub_cls = cls._registry.get(node.type, cls)

        # Process children
        children = []
        for child in node.children:
            child_node = cls.from_tree_sitter(child, text_bytes)
            children.append(child_node)

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

    # Tree navigation helpers
    def child_by_field_name(self, field_name: str) -> Optional[TSNode]:
        """Get first child with given field name."""
        for child in self.children:
            if child.field_name == field_name:
                return child
        return None

    def children_by_field_name(self, field_name: str) -> List[TSNode]:
        """Get all children with given field name."""
        return [child for child in self.children if child.field_name == field_name]

    def descendants(self) -> List[TSNode]:
        """Get all descendant nodes via depth-first traversal."""
        result = []
        for child in self.children:
            result.append(child)
            result.extend(child.descendants())
        return result

    def find_by_type(self, type_name: str) -> List[TSNode]:
        """Find all descendants with given type."""
        return [node for node in self.descendants() if node.type_name == type_name]

    def find_first_by_type(self, type_name: str) -> Optional[TSNode]:
        """Find first descendant with given type."""
        for node in self.descendants():
            if node.type_name == type_name:
                return node
        return None

    # Edit operations (return new immutable nodes)
    def replace_child(self, old_child: TSNode, new_child: TSNode) -> TSNode:
        """Return new node with child replaced."""
        new_children = [
            new_child if child == old_child else child for child in self.children
        ]
        return self.model_copy(update={"children": new_children})

    def insert_child(self, index: int, new_child: TSNode) -> TSNode:
        """Return new node with child inserted at index."""
        new_children = list(self.children)
        new_children.insert(index, new_child)
        return self.model_copy(update={"children": new_children})

    def delete_child(self, child: TSNode) -> TSNode:
        """Return new node with child removed."""
        new_children = [c for c in self.children if c != child]
        return self.model_copy(update={"children": new_children})

    def append_child(self, new_child: TSNode) -> TSNode:
        """Return new node with child appended."""
        return self.insert_child(len(self.children), new_child)

    def prepend_child(self, new_child: TSNode) -> TSNode:
        """Return new node with child prepended."""
        return self.insert_child(0, new_child)

    # Serialization helpers
    def dict(self, *args, **kwargs):
        return super().model_dump(*args, **kwargs)

    # Pretty‑print helpers
    def pretty(
        self,
        indent: int = 0,
        indent_str: str = "  ",
        max_text: int = 40,
    ) -> str:
        """Return a string that looks like nested `TSNode(…)` constructor calls."""
        ind = indent_str * indent
        nxt = indent_str * (indent + 1)

        class_name = self.__class__.__name__

        # Core scalar fields – skip `children` for now
        scalar_parts = []

        # Optional text snippet
        if max_text and self.text.strip():
            snippet = self.text.strip().replace("\n", " ")
            if len(snippet) > max_text:
                snippet = snippet[: max_text - 1] + "…"
            scalar_parts.append(f"text={snippet!r}")

        # Field name if present
        if self.field_name:
            scalar_parts.append(f"field={self.field_name!r}")

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

    def __hash__(self) -> int:
        """Hash based on position and type for use in sets."""
        return hash((self.type_name, self.start_byte, self.end_byte))
