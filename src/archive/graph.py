#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.11",
#     "rustworkx>=0.14.0",
# ]
# ///

"""
pydantree.graph – Graph analysis and pattern matching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

GraphBuilder converts NodeGroup collections into rustworkx graphs
for VF2 isomorphism matching, path analysis, and graph algorithms.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, Any, Callable, Union
from dataclasses import dataclass

try:
    import rustworkx as rx

    HAS_RUSTWORKX = True
except ImportError:
    HAS_RUSTWORKX = False

    # Fallback for when rustworkx is not available
    class rx:
        class PyDiGraph:
            pass

        class PyGraph:
            pass


from pydantic import BaseModel, ConfigDict
from .core import TSNode
from .nodegroup import NodeGroup


@dataclass(frozen=True)
class NodeMetadata:
    """Metadata attached to graph nodes."""

    node: TSNode
    type_name: str
    text: str
    start_byte: int
    end_byte: int
    depth: int


@dataclass(frozen=True)
class EdgeMetadata:
    """Metadata attached to graph edges."""

    edge_type: str  # 'parent-child', 'sibling', 'custom'
    label: Optional[str] = None
    weight: float = 1.0


class GraphBuilder:
    """
    Build rustworkx graphs from NodeGroup collections.

    Supports various graph representations:
    - Tree structure (parent-child edges)
    - Sibling relationships
    - Custom edge predicates
    - Weighted/labeled graphs
    """

    def __init__(self, nodegroup: NodeGroup):
        if not HAS_RUSTWORKX:
            raise ImportError(
                "rustworkx is required for graph operations. "
                "Install with: pip install rustworkx"
            )

        self.nodegroup = nodegroup
        self.node_to_index: Dict[TSNode, int] = {}
        self.index_to_node: Dict[int, TSNode] = {}

    def to_graph(
        self,
        directed: bool = True,
        include_siblings: bool = False,
        edge_predicate: Optional[Callable[[TSNode, TSNode], bool]] = None,
        node_attrs: Optional[Callable[[TSNode], Dict[str, Any]]] = None,
        edge_attrs: Optional[Callable[[TSNode, TSNode], Dict[str, Any]]] = None,
    ) -> Union[rx.PyDiGraph, rx.PyGraph]:
        """
        Convert NodeGroup to rustworkx graph.

        Args:
            directed: Create directed graph if True, undirected if False
            include_siblings: Add sibling edges between children of same parent
            edge_predicate: Custom function to determine edges
            node_attrs: Function to generate node attributes
            edge_attrs: Function to generate edge attributes
        """
        # Create appropriate graph type
        if directed:
            graph = rx.PyDiGraph()
        else:
            graph = rx.PyGraph()

        # Add nodes to graph
        nodes = list(self.nodegroup)
        for i, node in enumerate(nodes):
            metadata = self._create_node_metadata(node, i)
            attrs = node_attrs(node) if node_attrs else {}
            attrs.update({"metadata": metadata})

            node_index = graph.add_node(attrs)
            self.node_to_index[node] = node_index
            self.index_to_node[node_index] = node

        # Add parent-child edges
        self._add_parent_child_edges(graph, nodes, edge_attrs)

        # Add sibling edges if requested
        if include_siblings:
            self._add_sibling_edges(graph, nodes, edge_attrs)

        # Add custom edges if predicate provided
        if edge_predicate:
            self._add_custom_edges(graph, nodes, edge_predicate, edge_attrs)

        return graph

    def _create_node_metadata(self, node: TSNode, depth: int) -> NodeMetadata:
        """Create metadata for a graph node."""
        return NodeMetadata(
            node=node,
            type_name=node.type_name,
            text=node.text[:50] + "..." if len(node.text) > 50 else node.text,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            depth=depth,
        )

    def _add_parent_child_edges(
        self,
        graph: Union[rx.PyDiGraph, rx.PyGraph],
        nodes: List[TSNode],
        edge_attrs: Optional[Callable[[TSNode, TSNode], Dict[str, Any]]] = None,
    ) -> None:
        """Add parent-child edges to graph."""
        for parent in nodes:
            for child in parent.children:
                if child in self.node_to_index:
                    parent_idx = self.node_to_index[parent]
                    child_idx = self.node_to_index[child]

                    attrs = edge_attrs(parent, child) if edge_attrs else {}
                    attrs.update(
                        {
                            "metadata": EdgeMetadata(
                                edge_type="parent-child", label="child"
                            )
                        }
                    )

                    graph.add_edge(parent_idx, child_idx, attrs)

    def _add_sibling_edges(
        self,
        graph: Union[rx.PyDiGraph, rx.PyGraph],
        nodes: List[TSNode],
        edge_attrs: Optional[Callable[[TSNode, TSNode], Dict[str, Any]]] = None,
    ) -> None:
        """Add sibling edges between children of same parent."""
        # Group nodes by parent
        parent_children: Dict[TSNode, List[TSNode]] = {}

        for node in nodes:
            for child in node.children:
                if child in self.node_to_index:
                    if node not in parent_children:
                        parent_children[node] = []
                    parent_children[node].append(child)

        # Add sibling edges
        for siblings in parent_children.values():
            for i, sibling1 in enumerate(siblings):
                for sibling2 in siblings[i + 1 :]:
                    idx1 = self.node_to_index[sibling1]
                    idx2 = self.node_to_index[sibling2]

                    attrs = edge_attrs(sibling1, sibling2) if edge_attrs else {}
                    attrs.update(
                        {"metadata": EdgeMetadata(edge_type="sibling", label="sibling")}
                    )

                    graph.add_edge(idx1, idx2, attrs)

    def _add_custom_edges(
        self,
        graph: Union[rx.PyDiGraph, rx.PyGraph],
        nodes: List[TSNode],
        edge_predicate: Callable[[TSNode, TSNode], bool],
        edge_attrs: Optional[Callable[[TSNode, TSNode], Dict[str, Any]]] = None,
    ) -> None:
        """Add custom edges based on predicate."""
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i + 1 :]:
                if edge_predicate(node1, node2):
                    idx1 = self.node_to_index[node1]
                    idx2 = self.node_to_index[node2]

                    attrs = edge_attrs(node1, node2) if edge_attrs else {}
                    attrs.update(
                        {"metadata": EdgeMetadata(edge_type="custom", label="custom")}
                    )

                    graph.add_edge(idx1, idx2, attrs)


class PatternMatcher:
    """VF2 isomorphism matching for AST patterns."""

    def __init__(self, pattern_graph: Union[rx.PyDiGraph, rx.PyGraph]):
        if not HAS_RUSTWORKX:
            raise ImportError("rustworkx required for pattern matching")

        self.pattern = pattern_graph

    def find_matches(
        self,
        target_graph: Union[rx.PyDiGraph, rx.PyGraph],
        node_matcher: Optional[Callable[[Dict, Dict], bool]] = None,
        edge_matcher: Optional[Callable[[Dict, Dict], bool]] = None,
    ) -> List[Dict[int, int]]:
        """
        Find all subgraph isomorphisms using VF2 algorithm.

        Returns list of mappings from pattern node indices to target node indices.
        """
        if node_matcher is None:
            node_matcher = self._default_node_matcher

        if edge_matcher is None:
            edge_matcher = self._default_edge_matcher

        # Use correct VF2 function based on graph type
        if isinstance(self.pattern, rx.PyDiGraph) and isinstance(
            target_graph, rx.PyDiGraph
        ):
            mappings = rx.digraph_vf2_mapping(
                self.pattern,
                target_graph,
                node_matcher=node_matcher,
                edge_matcher=edge_matcher,
                subgraph=True,
            )
        else:
            mappings = rx.graph_vf2_mapping(
                self.pattern,
                target_graph,
                node_matcher=node_matcher,
                edge_matcher=edge_matcher,
                subgraph=True,
            )

        return list(mappings)

    def _default_node_matcher(self, pattern_node: Dict, target_node: Dict) -> bool:
        """Default node matching based on type_name."""
        pattern_meta = pattern_node.get("metadata")
        target_meta = target_node.get("metadata")

        if pattern_meta and target_meta:
            return pattern_meta.type_name == target_meta.type_name

        return True

    def _default_edge_matcher(self, pattern_edge: Dict, target_edge: Dict) -> bool:
        """Default edge matching based on edge_type."""
        pattern_meta = pattern_edge.get("metadata")
        target_meta = target_edge.get("metadata")

        if pattern_meta and target_meta:
            return pattern_meta.edge_type == target_meta.edge_type

        return True


class GraphAnalyzer:
    """Graph analysis utilities for AST graphs."""

    def __init__(self, graph: Union[rx.PyDiGraph, rx.PyGraph]):
        self.graph = graph

    def find_paths(
        self, source: int, target: int, max_length: Optional[int] = None
    ) -> List[List[int]]:
        """Find all paths between source and target nodes."""
        if max_length is None:
            max_length = len(self.graph.nodes())

        return rx.all_simple_paths(self.graph, source, target, max_length)

    def shortest_path(self, source: int, target: int) -> Optional[List[int]]:
        """Find shortest path between nodes."""
        try:
            return rx.dijkstra_shortest_paths(self.graph, source, target=target)[target]
        except KeyError:
            return None

    def find_cycles(self) -> List[List[int]]:
        """Find all cycles in the graph."""
        return rx.simple_cycles(self.graph)

    def topological_sort(self) -> List[int]:
        """Topological sort (for directed graphs only)."""
        if not isinstance(self.graph, rx.PyDiGraph):
            raise ValueError("Topological sort requires directed graph")

        try:
            return rx.topological_sort(self.graph)
        except rx.DAGHasCycle:
            raise ValueError("Graph contains cycles")

    def connected_components(self) -> List[List[int]]:
        """Find connected components."""
        if isinstance(self.graph, rx.PyDiGraph):
            return rx.weakly_connected_components(self.graph)
        else:
            return rx.connected_components(self.graph)

    def centrality_scores(self) -> Dict[int, float]:
        """Calculate betweenness centrality scores."""
        return rx.betweenness_centrality(self.graph)

    def graph_metrics(self) -> Dict[str, Any]:
        """Calculate various graph metrics."""
        num_nodes = len(self.graph.nodes())
        num_edges = len(self.graph.edges())

        metrics = {
            "num_nodes": num_nodes,
            "num_edges": num_edges,
            "density": num_edges / (num_nodes * (num_nodes - 1))
            if num_nodes > 1
            else 0,
            "is_connected": rx.is_connected(self.graph)
            if not isinstance(self.graph, rx.PyDiGraph)
            else rx.is_weakly_connected(self.graph),
        }

        if isinstance(self.graph, rx.PyDiGraph):
            metrics["is_dag"] = rx.is_directed_acyclic_graph(self.graph)

        return metrics


# ---- Convenience functions ----


def build_tree_graph(nodegroup: NodeGroup) -> Union[rx.PyDiGraph, rx.PyGraph]:
    """Build basic tree graph from NodeGroup."""
    return GraphBuilder(nodegroup).to_graph(directed=True)


def build_pattern_graph(
    pattern_nodes: List[TSNode], include_siblings: bool = False
) -> rx.PyDiGraph:
    """Build pattern graph for VF2 matching."""
    pattern_group = NodeGroup(pattern_nodes)
    return GraphBuilder(pattern_group).to_graph(
        directed=True, include_siblings=include_siblings
    )


def find_pattern_matches(
    pattern: Union[rx.PyDiGraph, NodeGroup, List[TSNode]],
    target: Union[rx.PyDiGraph, NodeGroup],
) -> List[Dict[int, int]]:
    """Find pattern matches in target graph."""
    # Convert inputs to graphs if needed
    if isinstance(pattern, (NodeGroup, list)):
        pattern_nodes = pattern if isinstance(pattern, list) else list(pattern)
        pattern_graph = build_pattern_graph(pattern_nodes)
    else:
        pattern_graph = pattern

    if isinstance(target, NodeGroup):
        target_graph = build_tree_graph(target)
    else:
        target_graph = target

    matcher = PatternMatcher(pattern_graph)
    return matcher.find_matches(target_graph)
