# pydantree/core/nodes.py
from __future__ import annotations

import json
import hashlib
from typing import List, ClassVar, Optional, Dict, Any, Set, Union, Iterator, Callable
from enum import Enum
from functools import cached_property
from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field, computed_field


class SerializationMode(Enum):
    """Available serialization modes for TSNode export."""

    FULL = "full"
    CLEAN = "clean"
    MINIMAL = "minimal"
    METRICS = "metrics"
    STRUCTURE = "structure"


class TraversalOrder(Enum):
    """Tree traversal order options."""

    PREORDER = "preorder"
    POSTORDER = "postorder"
    BREADTH_FIRST = "breadth_first"
    DEPTH_FIRST = "depth_first"


class TSPoint(BaseModel):
    """Represents a point in a source file (row, column)."""

    model_config = ConfigDict(frozen=True)
    row: int
    column: int


class TSNode(BaseModel):
    """An enhanced, Pydantic-validated representation of a tree-sitter node."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    __match_args__ = ("type_name", "children")

    # Core fields from tree-sitter
    type_name: str
    start_byte: int
    end_byte: int
    start_point: TSPoint
    end_point: TSPoint
    text: str
    children: List[TSNode] = Field(default_factory=list)
    is_named: bool = True
    field_name: Optional[str] = None

    # Class-level registry for mapping tree-sitter types to specific classes
    _registry: ClassVar[Dict[str, type[TSNode]]] = {}

    # ========================================================================
    # Factory Method
    # ========================================================================
    @classmethod
    def from_tree_sitter(cls, node: Any, text_bytes: bytes) -> TSNode:
        """
        Recursively construct a Pydantree TSNode from a tree-sitter node.
        This factory method dynamically dispatches to registered subclasses.
        """
        # Look up the specific class in the registry, fall back to TSNode
        sub_cls = cls._registry.get(node.type, cls)

        children = []
        for i, child in enumerate(node.children):
            # The field name is retrieved from the parent node for each child
            child_field_name = node.field_name_for_child(i)
            child_node = cls.from_tree_sitter(child, text_bytes)
            # Use model_copy to create a new instance with the field name
            children.append(child_node.model_copy(update={"field_name": child_field_name}))

        return sub_cls(
            type_name=node.type,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_point=TSPoint(row=node.start_point[0], column=node.start_point[1]),
            end_point=TSPoint(row=node.end_point[0], column=node.end_point[1]),
            text=text_bytes[node.start_byte : node.end_byte].decode(errors="ignore"),
            children=children,
            is_named=node.is_named,
        )

    # ========================================================================
    # Computed & Cached Properties
    # ========================================================================
    @computed_field
    @cached_property
    def byte_length(self) -> int:
        """The byte length of this node's source text."""
        return self.end_byte - self.start_byte

    @computed_field
    @cached_property
    def line_count(self) -> int:
        """The number of lines spanned by this node."""
        return self.end_point.row - self.start_point.row + 1

    @cached_property
    def structural_hash(self) -> str:
        """A hash representing the structural signature of the node and its descendants."""
        components = [self.type_name]
        for child in self.children:
            components.append(child.structural_hash)
        content = "|".join(components)
        return hashlib.md5(content.encode()).hexdigest()

    # ========================================================================
    # Tree Traversal & Querying
    # ========================================================================
    def descendants(self, order: TraversalOrder = TraversalOrder.DEPTH_FIRST) -> Iterator[TSNode]:
        """Iterate over all descendant nodes with a specified traversal order."""
        if order == TraversalOrder.BREADTH_FIRST:
            from collections import deque

            queue = deque(self.children)
            while queue:
                node = queue.popleft()
                yield node
                queue.extend(node.children)
        else:  # DEPTH_FIRST / PREORDER
            for child in self.children:
                yield child
                yield from child.descendants(order)

    def find_all_by_type(self, type_names: Union[str, Set[str]]) -> List[TSNode]:
        """Find all descendant nodes matching one or more type names."""
        target_types = {type_names} if isinstance(type_names, str) else type_names
        return [node for node in self.descendants() if node.type_name in target_types]

    def child_by_field_name(self, name: str) -> Optional[TSNode]:
        """Get the first direct child with the given field name."""
        for child in self.children:
            if child.field_name == name:
                return child
        return None

    # ========================================================================
    # Analysis
    # ========================================================================
    def get_metrics(self) -> Dict[str, Any]:
        """Calculate and return a dictionary of structural metrics for this node."""
        descendants = list(self.descendants())
        type_counts = defaultdict(int)
        for d in descendants:
            type_counts[d.type_name] += 1

        return {
            "total_nodes": len(descendants) + 1,
            "line_count": self.line_count,
            "byte_length": self.byte_length,
            "cyclomatic_complexity": self._calculate_complexity(descendants),
            "type_distribution": dict(type_counts),
        }

    def _calculate_complexity(self, descendants: List[TSNode]) -> int:
        """Calculate cyclomatic complexity."""
        complexity_nodes = {
            "if_statement",
            "elif_clause",
            "for_statement",
            "while_statement",
            "except_clause",
            "case_statement",
            "conditional_expression",
            "binary_operator",  # for 'and'/'or'
        }
        complexity = 1
        for d in descendants:
            if d.type_name in complexity_nodes:
                if d.type_name == "binary_operator" and d.text in ("and", "or"):
                    complexity += 1
                elif d.type_name != "binary_operator":
                    complexity += 1
        return complexity

    # ========================================================================
    # Magic Methods & Display
    # ========================================================================
    def __hash__(self) -> int:
        return hash(self.structural_hash)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} type={self.type_name} hash={self.structural_hash[:7]}>"
