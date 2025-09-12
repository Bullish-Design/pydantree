#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.11",
# ]
# ///

"""
pydantree.nodegroup – Lazy collections and set operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

NodeGroup provides lazy, set-theoretic operations over heterogeneous
TSNode collections with bulk mutation and graph conversion capabilities.
"""

from __future__ import annotations

from typing import (
    Callable,
    Generic,
    Iterator,
    TypeVar,
    Union,
    Any,
    List,
    Set,
    Optional,
    Tuple,
)
from abc import ABC, abstractmethod
from functools import reduce
from operator import or_, and_

from pydantic import BaseModel, ConfigDict, Field
from .core import TSNode

T = TypeVar("T", bound=TSNode)


class NodeSelector(ABC):
    """Abstract base for node selection predicates."""

    @abstractmethod
    def matches(self, node: TSNode) -> bool:
        """Return True if node matches this selector."""
        pass

    def __and__(self, other: NodeSelector) -> NodeSelector:
        """Combine selectors with AND logic."""
        return _AndSelector(self, other)

    def __or__(self, other: NodeSelector) -> NodeSelector:
        """Combine selectors with OR logic."""
        return _OrSelector(self, other)

    def __invert__(self) -> NodeSelector:
        """Negate selector with NOT logic."""
        return _NotSelector(self)


class _AndSelector(NodeSelector):
    def __init__(self, left: NodeSelector, right: NodeSelector):
        self.left = left
        self.right = right

    def matches(self, node: TSNode) -> bool:
        return self.left.matches(node) and self.right.matches(node)


class _OrSelector(NodeSelector):
    def __init__(self, left: NodeSelector, right: NodeSelector):
        self.left = left
        self.right = right

    def matches(self, node: TSNode) -> bool:
        return self.left.matches(node) or self.right.matches(node)


class _NotSelector(NodeSelector):
    def __init__(self, selector: NodeSelector):
        self.selector = selector

    def matches(self, node: TSNode) -> bool:
        return not self.selector.matches(node)


class TypeSelector(NodeSelector):
    """Select nodes by type name."""

    def __init__(self, type_name: str):
        self.type_name = type_name

    def matches(self, node: TSNode) -> bool:
        return node.type_name == self.type_name


class ClassSelector(NodeSelector):
    """Select nodes by Python class."""

    def __init__(self, node_class: type[TSNode]):
        self.node_class = node_class

    def matches(self, node: TSNode) -> bool:
        return isinstance(node, self.node_class)


class PredicateSelector(NodeSelector):
    """Select nodes using a callable predicate."""

    def __init__(self, predicate: Callable[[TSNode], bool]):
        self.predicate = predicate

    def matches(self, node: TSNode) -> bool:
        return self.predicate(node)


class TextSelector(NodeSelector):
    """Select nodes by text content."""

    def __init__(self, text: str, exact: bool = True):
        self.text = text
        self.exact = exact

    def matches(self, node: TSNode) -> bool:
        if self.exact:
            return node.text == self.text
        return self.text in node.text


class NodeGroup(BaseModel, Generic[T]):
    """
    Lazy, immutable collection of TSNode objects with set operations.

    Supports:
    - Set-theoretic operations (union, intersection, difference)
    - Lazy filtering and transformation
    - Bulk mutation operations
    - Graph conversion via GraphBuilder
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    # Internal storage
    nodes: Set[TSNode] = Field(default_factory=set)
    selectors: List[NodeSelector] = Field(default_factory=list)

    def __init__(
        self,
        input_nodes: Union[
            TSNode, Iterator[TSNode], List[TSNode], Set[TSNode], None
        ] = None,
        **data,
    ):
        if input_nodes is None:
            nodes_set = set()
        elif isinstance(input_nodes, TSNode):
            nodes_set = {input_nodes}
        elif isinstance(input_nodes, (list, set)):
            nodes_set = set(input_nodes)
        else:
            nodes_set = set(input_nodes)

        super().__init__(nodes=nodes_set, selectors=data.get("selectors", []), **data)

    @classmethod
    def from_tree(cls, root: TSNode) -> NodeGroup[TSNode]:
        """Create NodeGroup from entire tree via depth-first traversal."""

        def walk(node: TSNode) -> Iterator[TSNode]:
            yield node
            for child in node.children:
                yield from walk(child)

        return cls(walk(root))

    @classmethod
    def empty(cls) -> NodeGroup[TSNode]:
        """Create empty NodeGroup."""
        return cls()

    # ---- Lazy evaluation ----

    def _apply_selectors(self, nodes: Set[TSNode]) -> Set[TSNode]:
        """Apply all pending selectors to node set."""
        result = nodes
        for selector in self.selectors:
            result = {n for n in result if selector.matches(n)}
        return result

    def _materialize(self) -> Set[TSNode]:
        """Force evaluation of lazy operations."""
        return self._apply_selectors(self.nodes)

    # ---- Core set operations ----

    def filter(self, selector: NodeSelector) -> NodeGroup[T]:
        """Add a filter selector (lazy)."""
        new_selectors = self.selectors + [selector]
        return self.model_copy(update={"selectors": new_selectors})

    def filter_type(self, type_name: str) -> NodeGroup[T]:
        """Filter by node type name."""
        return self.filter(TypeSelector(type_name))

    def filter_class(self, node_class: type[TSNode]) -> NodeGroup[T]:
        """Filter by Python class."""
        return self.filter(ClassSelector(node_class))

    def filter_text(self, text: str, exact: bool = True) -> NodeGroup[T]:
        """Filter by text content."""
        return self.filter(TextSelector(text, exact))

    def where(self, predicate: Callable[[TSNode], bool]) -> NodeGroup[T]:
        """Filter using custom predicate."""
        return self.filter(PredicateSelector(predicate))

    # ---- Set algebra ----

    def union(self, other: NodeGroup[T]) -> NodeGroup[T]:
        """Union with another NodeGroup."""
        combined_nodes = self._materialize() | other._materialize()
        return NodeGroup(combined_nodes)

    def intersection(self, other: NodeGroup[T]) -> NodeGroup[T]:
        """Intersection with another NodeGroup."""
        intersected_nodes = self._materialize() & other._materialize()
        return NodeGroup(intersected_nodes)

    def difference(self, other: NodeGroup[T]) -> NodeGroup[T]:
        """Difference from another NodeGroup."""
        diff_nodes = self._materialize() - other._materialize()
        return NodeGroup(diff_nodes)

    def symmetric_difference(self, other: NodeGroup[T]) -> NodeGroup[T]:
        """Symmetric difference with another NodeGroup."""
        sym_diff_nodes = self._materialize() ^ other._materialize()
        return NodeGroup(sym_diff_nodes)

    # ---- Bulk operations ----

    def map(self, func: Callable[[TSNode], TSNode]) -> NodeGroup[T]:
        """Apply function to all nodes."""
        mapped_nodes = {func(node) for node in self._materialize()}
        return NodeGroup(mapped_nodes)

    def transform(
        self, transformer: Callable[[TSNode], Optional[TSNode]]
    ) -> NodeGroup[T]:
        """Transform nodes, filtering out None results."""
        transformed = set()
        for node in self._materialize():
            result = transformer(node)
            if result is not None:
                transformed.add(result)
        return NodeGroup(transformed)

    # ---- Queries and aggregation ----

    def find_first(self, selector: Optional[NodeSelector] = None) -> Optional[TSNode]:
        """Find first matching node."""
        nodes = self._materialize()
        if selector:
            nodes = {n for n in nodes if selector.matches(n)}
        return next(iter(nodes)) if nodes else None

    def find_all(self, selector: Optional[NodeSelector] = None) -> List[TSNode]:
        """Find all matching nodes."""
        nodes = self._materialize()
        if selector:
            nodes = {n for n in nodes if selector.matches(n)}
        return list(nodes)

    def count(self, selector: Optional[NodeSelector] = None) -> int:
        """Count matching nodes."""
        nodes = self._materialize()
        if selector:
            nodes = {n for n in nodes if selector.matches(n)}
        return len(nodes)

    def groupby(self, key: Callable[[TSNode], Any]) -> dict[Any, NodeGroup[T]]:
        """Group nodes by key function."""
        groups: dict[Any, List[TSNode]] = {}
        for node in self._materialize():
            group_key = key(node)
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(node)

        return {k: NodeGroup(nodes) for k, nodes in groups.items()}

    # ---- Traversal ----

    def descendants(self) -> NodeGroup[TSNode]:
        """Get all descendant nodes."""

        def get_descendants(node: TSNode) -> Iterator[TSNode]:
            for child in node.children:
                yield child
                yield from get_descendants(child)

        all_descendants = set()
        for node in self._materialize():
            all_descendants.update(get_descendants(node))

        return NodeGroup(all_descendants)

    def ancestors(self, root: TSNode) -> NodeGroup[TSNode]:
        """Get all ancestor nodes up to root."""
        # This requires parent pointers, which TSNode doesn't have
        # For now, we'd need to walk from root to find ancestors
        # Implementation would require tree walking algorithm
        raise NotImplementedError(
            "Ancestor traversal requires parent pointers or root reference"
        )

    def siblings(self, parent: TSNode) -> NodeGroup[TSNode]:
        """Get sibling nodes within parent."""
        current_nodes = self._materialize()
        siblings = set()

        for child in parent.children:
            if child not in current_nodes:
                siblings.add(child)

        return NodeGroup(siblings)

    # ---- Magic methods and iteration ----

    def __iter__(self) -> Iterator[TSNode]:
        """Iterate over materialized nodes."""
        return iter(self._materialize())

    def __len__(self) -> int:
        """Get count of materialized nodes."""
        return len(self._materialize())

    def __bool__(self) -> bool:
        """True if group contains any nodes."""
        return len(self._materialize()) > 0

    def __contains__(self, node: TSNode) -> bool:
        """Check if node is in group."""
        return node in self._materialize()

    def __or__(self, other: NodeGroup[T]) -> NodeGroup[T]:
        """Union operator."""
        return self.union(other)

    def __and__(self, other: NodeGroup[T]) -> NodeGroup[T]:
        """Intersection operator."""
        return self.intersection(other)

    def __sub__(self, other: NodeGroup[T]) -> NodeGroup[T]:
        """Difference operator."""
        return self.difference(other)

    def __xor__(self, other: NodeGroup[T]) -> NodeGroup[T]:
        """Symmetric difference operator."""
        return self.symmetric_difference(other)

    # ---- Conversion ----

    def to_list(self) -> List[TSNode]:
        """Convert to list."""
        return list(self._materialize())

    def to_set(self) -> Set[TSNode]:
        """Convert to set."""
        return self._materialize().copy()

    def to_graph(self):
        """Convert to rustworkx graph via GraphBuilder."""
        from .graph import GraphBuilder  # Avoid circular import

        return GraphBuilder(self).to_graph()


# ---- Factory functions ----


def nodes(*nodes: TSNode) -> NodeGroup[TSNode]:
    """Create NodeGroup from individual nodes."""
    return NodeGroup(nodes)


def from_tree(root: TSNode) -> NodeGroup[TSNode]:
    """Create NodeGroup from entire tree."""
    return NodeGroup.from_tree(root)


def empty() -> NodeGroup[TSNode]:
    """Create empty NodeGroup."""
    return NodeGroup.empty()
