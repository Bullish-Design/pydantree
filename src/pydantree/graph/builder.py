# pydantree/graph/builder.py
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Set, Tuple, Any, Callable, Union, Iterator
from dataclasses import dataclass, field
from collections import defaultdict

try:
    import rustworkx as rx
    HAS_RUSTWORKX = True
except ImportError:
    HAS_RUSTWORKX = False

from pydantic import BaseModel, ConfigDict

from ..core.nodes import TSNode
from ..processing.collections import NodeGroup
from ..core.profiler import PerformanceProfiler


@dataclass(frozen=True)
class NodeMetadata:
    """Enhanced metadata attached to graph nodes."""
    node: TSNode
    node_id: str
    type_name: str
    text_hash: str
    structural_hash: str
    depth: int
    semantic_role: Optional[str] = None
    complexity: int = 0
    size: int = 0
    
    @classmethod
    def from_node(cls, node: TSNode, depth: int = 0) -> 'NodeMetadata':
        """Create metadata from TSNode."""
        text_hash = hashlib.md5(node.text.encode()).hexdigest()[:8]
        node_id = f"{node.type_name}_{node.start_byte}_{node.end_byte}"
        
        return cls(
            node=node,
            node_id=node_id,
            type_name=node.type_name,
            text_hash=text_hash,
            structural_hash=node.structural_hash[:8],
            depth=depth,
            complexity=node.calculate_complexity(),
            size=node.descendants_count
        )


@dataclass(frozen=True)
class EdgeMetadata:
    """Enhanced metadata attached to graph edges."""
    edge_type: str
    label: Optional[str] = None
    weight: float = 1.0
    field_name: Optional[str] = None
    distance: int = 1
    relationship: Optional[str] = None
    
    def __post_init__(self):
        # Validate edge type
        valid_types = {'parent-child', 'sibling', 'control-flow', 'data-flow', 'custom'}
        if self.edge_type not in valid_types:
            object.__setattr__(self, 'edge_type', 'custom')


class GraphBuilder:
    """Enhanced graph builder with pattern matching and analysis capabilities."""
    
    def __init__(self, nodegroup: NodeGroup, profiler: Optional[PerformanceProfiler] = None):
        if not HAS_RUSTWORKX:
            raise ImportError(
                "rustworkx is required for graph operations. "
                "Install with: pip install rustworkx"
            )
        
        self.nodegroup = nodegroup
        self.profiler = profiler or PerformanceProfiler(enabled=False)
        
        # Graph storage
        self.node_to_index: Dict[TSNode, int] = {}
        self.index_to_node: Dict[int, TSNode] = {}
        self.metadata_cache: Dict[int, NodeMetadata] = {}
        
        # Analysis cache
        self._pattern_cache: Dict[str, List[Dict[int, int]]] = {}
        self._subgraph_cache: Dict[str, Union[rx.PyDiGraph, rx.PyGraph]] = {}
    
    def to_graph(self,
                directed: bool = True,
                include_siblings: bool = False,
                include_control_flow: bool = False,
                include_data_flow: bool = False,
                edge_predicate: Optional[Callable[[TSNode, TSNode], bool]] = None,
                node_filter: Optional[Callable[[TSNode], bool]] = None,
                max_depth: Optional[int] = None) -> Union[rx.PyDiGraph, rx.PyGraph]:
        """
        Convert NodeGroup to enhanced rustworkx graph with multiple edge types.
        
        Args:
            directed: Create directed graph
            include_siblings: Add sibling relationships
            include_control_flow: Add control flow edges
            include_data_flow: Add data flow edges
            edge_predicate: Custom edge creation function
            node_filter: Filter nodes before adding to graph
            max_depth: Maximum depth to include
        """
        with self.profiler.profile('graph_construction'):
            # Create graph
            graph = rx.PyDiGraph() if directed else rx.PyGraph()
            
            # Filter nodes
            nodes = list(self.nodegroup)
            if node_filter:
                nodes = [node for node in nodes if node_filter(node)]
            
            if max_depth is not None:
                nodes = [node for node in nodes if self._get_node_depth(node) <= max_depth]
            
            # Add nodes with metadata
            self._add_nodes_to_graph(graph, nodes)
            
            # Add edges based on options
            if len(nodes) > 0:
                self._add_parent_child_edges(graph, nodes)
                
                if include_siblings:
                    self._add_sibling_edges(graph, nodes)
                
                if include_control_flow:
                    self._add_control_flow_edges(graph, nodes)
                
                if include_data_flow:
                    self._add_data_flow_edges(graph, nodes)
                
                if edge_predicate:
                    self._add_custom_edges(graph, nodes, edge_predicate)
        
        return graph
    
    def _add_nodes_to_graph(self, graph: Union[rx.PyDiGraph, rx.PyGraph], nodes: List[TSNode]) -> None:
        """Add nodes to graph with enhanced metadata."""
        for i, node in enumerate(nodes):
            depth = self._get_node_depth(node)
            metadata = NodeMetadata.from_node(node, depth)
            
            # Create node attributes
            attrs = {
                'metadata': metadata,
                'type_name': node.type_name,
                'text_preview': node.text[:50].replace('\n', ' '),
                'depth': depth,
                'complexity': metadata.complexity,
                'size': metadata.size,
                'structural_hash': metadata.structural_hash
            }
            
            node_index = graph.add_node(attrs)
            self.node_to_index[node] = node_index
            self.index_to_node[node_index] = node
            self.metadata_cache[node_index] = metadata
    
    def _get_node_depth(self, node: TSNode) -> int:
        """Calculate depth of node in tree."""
        # Simple heuristic based on byte position
        # In a full implementation, this would track actual tree depth
        return len([n for n in self.nodegroup if 
                   n.start_byte <= node.start_byte and n.end_byte >= node.end_byte]) - 1
    
    def _add_parent_child_edges(self, graph: Union[rx.PyDiGraph, rx.PyGraph], nodes: List[TSNode]) -> None:
        """Add parent-child edges with field information."""
        for parent in nodes:
            for child in parent.children:
                if child in self.node_to_index:
                    parent_idx = self.node_to_index[parent]
                    child_idx = self.node_to_index[child]
                    
                    edge_metadata = EdgeMetadata(
                        edge_type='parent-child',
                        label='child',
                        field_name=child.field_name,
                        distance=1
                    )
                    
                    attrs = {
                        'metadata': edge_metadata,
                        'edge_type': 'parent-child',
                        'field_name': child.field_name or '',
                        'weight': 1.0
                    }
                    
                    graph.add_edge(parent_idx, child_idx, attrs)
    
    def _add_sibling_edges(self, graph: Union[rx.PyDiGraph, rx.PyGraph], nodes: List[TSNode]) -> None:
        """Add sibling edges between children of same parent."""
        parent_children: Dict[TSNode, List[TSNode]] = defaultdict(list)
        
        # Group children by parent
        for node in nodes:
            for child in node.children:
                if child in self.node_to_index:
                    parent_children[node].append(child)
        
        # Add sibling edges
        for siblings in parent_children.values():
            for i, sibling1 in enumerate(siblings):
                for sibling2 in siblings[i + 1:]:
                    idx1 = self.node_to_index[sibling1]
                    idx2 = self.node_to_index[sibling2]
                    
                    edge_metadata = EdgeMetadata(
                        edge_type='sibling',
                        label='sibling',
                        distance=1
                    )
                    
                    attrs = {
                        'metadata': edge_metadata,
                        'edge_type': 'sibling',
                        'weight': 0.5
                    }
                    
                    graph.add_edge(idx1, idx2, attrs)
    
    def _add_control_flow_edges(self, graph: Union[rx.PyDiGraph, rx.PyGraph], nodes: List[TSNode]) -> None:
        """Add control flow edges (if/else, loops, etc.)."""
        control_flow_types = {
            'if_statement', 'while_statement', 'for_statement',
            'try_statement', 'match_statement', 'function_definition'
        }
        
        for node in nodes:
            if node.type_name in control_flow_types:
                # Add edges to control flow targets
                targets = self._find_control_flow_targets(node)
                node_idx = self.node_to_index.get(node)
                
                if node_idx is not None:
                    for target in targets:
                        target_idx = self.node_to_index.get(target)
                        if target_idx is not None:
                            edge_metadata = EdgeMetadata(
                                edge_type='control-flow',
                                label='flows_to',
                                distance=self._calculate_control_distance(node, target)
                            )
                            
                            attrs = {
                                'metadata': edge_metadata,
                                'edge_type': 'control-flow',
                                'weight': 2.0
                            }
                            
                            graph.add_edge(node_idx, target_idx, attrs)
    
    def _add_data_flow_edges(self, graph: Union[rx.PyDiGraph, rx.PyGraph], nodes: List[TSNode]) -> None:
        """Add data flow edges (variable definitions and usages)."""
        # Simple data flow based on identifier usage
        identifiers = {}
        
        for node in nodes:
            if node.type_name == 'identifier':
                identifier_name = node.text.strip()
                if identifier_name not in identifiers:
                    identifiers[identifier_name] = []
                identifiers[identifier_name].append(node)
        
        # Connect identifiers with same name
        for identifier_nodes in identifiers.values():
            if len(identifier_nodes) > 1:
                # Connect in sequence (definition -> usage)
                for i in range(len(identifier_nodes) - 1):
                    source = identifier_nodes[i]
                    target = identifier_nodes[i + 1]
                    
                    source_idx = self.node_to_index.get(source)
                    target_idx = self.node_to_index.get(target)
                    
                    if source_idx is not None and target_idx is not None:
                        edge_metadata = EdgeMetadata(
                            edge_type='data-flow',
                            label='uses',
                            distance=abs(target.start_byte - source.start_byte)
                        )
                        
                        attrs = {
                            'metadata': edge_metadata,
                            'edge_type': 'data-flow',
                            'weight': 1.5
                        }
                        
                        graph.add_edge(source_idx, target_idx, attrs)
    
    def _add_custom_edges(self, graph: Union[rx.PyDiGraph, rx.PyGraph], 
                         nodes: List[TSNode], 
                         edge_predicate: Callable[[TSNode, TSNode], bool]) -> None:
        """Add custom edges based on predicate."""
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i + 1:]:
                if edge_predicate(node1, node2):
                    idx1 = self.node_to_index[node1]
                    idx2 = self.node_to_index[node2]
                    
                    edge_metadata = EdgeMetadata(
                        edge_type='custom',
                        label='custom',
                        distance=abs(node2.start_byte - node1.start_byte)
                    )
                    
                    attrs = {
                        'metadata': edge_metadata,
                        'edge_type': 'custom',
                        'weight': 1.0
                    }
                    
                    graph.add_edge(idx1, idx2, attrs)
    
    def _find_control_flow_targets(self, node: TSNode) -> List[TSNode]:
        """Find control flow targets for a node."""
        targets = []
        
        # Simple heuristic: look at immediate children that could be targets
        if node.type_name == 'if_statement':
            # Add condition and body
            condition = node.child_by_field_name('condition')
            consequence = node.child_by_field_name('consequence')
            alternative = node.child_by_field_name('alternative')
            
            for target in [condition, consequence, alternative]:
                if target is not None:
                    targets.append(target)
        
        elif node.type_name in ['while_statement', 'for_statement']:
            # Add condition and body
            condition = node.child_by_field_name('condition')
            body = node.child_by_field_name('body')
            
            for target in [condition, body]:
                if target is not None:
                    targets.append(target)
        
        return targets
    
    def _calculate_control_distance(self, source: TSNode, target: TSNode) -> int:
        """Calculate control flow distance between nodes."""
        return abs(target.start_byte - source.start_byte) // 100


class PatternMatcher:
    """Enhanced VF2 isomorphism matching with caching and optimization."""
    
    def __init__(self, pattern_graph: Union[rx.PyDiGraph, rx.PyGraph]):
        if not HAS_RUSTWORKX:
            raise ImportError("rustworkx required for pattern matching")
        
        self.pattern = pattern_graph
        self.pattern_signature = self._compute_graph_signature(pattern_graph)
        self._match_cache: Dict[str, List[Dict[int, int]]] = {}
    
    def find_matches(self,
                    target_graph: Union[rx.PyDiGraph, rx.PyGraph],
                    node_matcher: Optional[Callable[[Dict, Dict], bool]] = None,
                    edge_matcher: Optional[Callable[[Dict, Dict], bool]] = None,
                    max_matches: int = 100,
                    use_cache: bool = True) -> List[Dict[int, int]]:
        """
        Find all subgraph isomorphisms with caching and limits.
        
        Args:
            target_graph: Graph to search in
            node_matcher: Function to match nodes
            edge_matcher: Function to match edges
            max_matches: Maximum number of matches to return
            use_cache: Whether to use caching
        
        Returns:
            List of mappings from pattern indices to target indices
        """
        # Check cache
        target_signature = self._compute_graph_signature(target_graph)
        cache_key = f"{self.pattern_signature}:{target_signature}"
        
        if use_cache and cache_key in self._match_cache:
            return self._match_cache[cache_key][:max_matches]
        
        # Set up default matchers
        if node_matcher is None:
            node_matcher = self._semantic_node_matcher
        if edge_matcher is None:
            edge_matcher = self._semantic_edge_matcher
        
        # Perform VF2 matching
        try:
            if isinstance(self.pattern, rx.PyDiGraph) and isinstance(target_graph, rx.PyDiGraph):
                mappings = rx.digraph_vf2_mapping(
                    self.pattern,
                    target_graph,
                    node_matcher=node_matcher,
                    edge_matcher=edge_matcher,
                    subgraph=True,
                    id_order=False
                )
            else:
                mappings = rx.graph_vf2_mapping(
                    self.pattern,
                    target_graph,
                    node_matcher=node_matcher,
                    edge_matcher=edge_matcher,
                    subgraph=True,
                    id_order=False
                )
            
            matches = list(mappings)[:max_matches]
            
            # Cache results
            if use_cache:
                self._match_cache[cache_key] = matches
            
            return matches
            
        except Exception as e:
            # Fallback to empty matches if VF2 fails
            return []
    
    def _semantic_node_matcher(self, pattern_node: Dict, target_node: Dict) -> bool:
        """Enhanced semantic node matching."""
        pattern_meta = pattern_node.get('metadata')
        target_meta = target_node.get('metadata')
        
        if not pattern_meta or not target_meta:
            # Fallback to type matching
            return pattern_node.get('type_name') == target_node.get('type_name')
        
        # Primary match: type name
        if pattern_meta.type_name != target_meta.type_name:
            return False
        
        # Secondary matches (can be relaxed)
        # Size similarity (within 50%)
        if pattern_meta.size > 0 and target_meta.size > 0:
            size_ratio = min(pattern_meta.size, target_meta.size) / max(pattern_meta.size, target_meta.size)
            if size_ratio < 0.5:
                return False
        
        # Complexity similarity (within reasonable bounds)
        complexity_diff = abs(pattern_meta.complexity - target_meta.complexity)
        if complexity_diff > 5:  # Allow some variance
            return False
        
        return True
    
    def _semantic_edge_matcher(self, pattern_edge: Dict, target_edge: Dict) -> bool:
        """Enhanced semantic edge matching."""
        pattern_meta = pattern_edge.get('metadata')
        target_meta = target_edge.get('metadata')
        
        if not pattern_meta or not target_meta:
            # Fallback to edge type matching
            return pattern_edge.get('edge_type') == target_edge.get('edge_type')
        
        # Primary match: edge type
        if pattern_meta.edge_type != target_meta.edge_type:
            return False
        
        # Secondary match: field names (for parent-child edges)
        if pattern_meta.edge_type == 'parent-child':
            return pattern_meta.field_name == target_meta.field_name
        
        return True
    
    def _compute_graph_signature(self, graph: Union[rx.PyDiGraph, rx.PyGraph]) -> str:
        """Compute a signature for graph caching."""
        node_count = len(graph.nodes())
        edge_count = len(graph.edges())
        
        # Type distribution
        type_counts = {}
        for node_data in graph.nodes():
            type_name = node_data.get('type_name', 'unknown')
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        # Create signature
        signature_parts = [
            f"nodes:{node_count}",
            f"edges:{edge_count}",
            f"types:{len(type_counts)}"
        ]
        
        # Add top types
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        for type_name, count in sorted_types[:5]:
            signature_parts.append(f"{type_name}:{count}")
        
        signature = "|".join(signature_parts)
        return hashlib.md5(signature.encode()).hexdigest()[:16]
    
    def clear_cache(self):
        """Clear pattern matching cache."""
        self._match_cache.clear()


class GraphAnalyzer:
    """Enhanced graph analysis with pattern detection and metrics."""
    
    def __init__(self, graph: Union[rx.PyDiGraph, rx.PyGraph]):
        self.graph = graph
        self._analysis_cache: Dict[str, Any] = {}
    
    def find_patterns(self, pattern_graphs: List[Union[rx.PyDiGraph, rx.PyGraph]], 
                     max_matches_per_pattern: int = 10) -> Dict[str, List[Dict[int, int]]]:
        """Find multiple patterns in the graph."""
        results = {}
        
        for i, pattern in enumerate(pattern_graphs):
            pattern_id = f"pattern_{i}"
            matcher = PatternMatcher(pattern)
            matches = matcher.find_matches(self.graph, max_matches=max_matches_per_pattern)
            results[pattern_id] = matches
        
        return results
    
    def detect_structural_patterns(self) -> Dict[str, List[List[int]]]:
        """Detect common structural patterns."""
        patterns = {}
        
        # Find cycles
        if isinstance(self.graph, rx.PyDiGraph):
            try:
                cycles = rx.simple_cycles(self.graph)
                patterns['cycles'] = cycles
            except Exception:
                patterns['cycles'] = []
        
        # Find strongly connected components
        if isinstance(self.graph, rx.PyDiGraph):
            try:
                sccs = rx.strongly_connected_components(self.graph)
                patterns['strongly_connected'] = sccs
            except Exception:
                patterns['strongly_connected'] = []
        
        # Find cliques (for undirected graphs)
        if isinstance(self.graph, rx.PyGraph):
            try:
                # Note: rustworkx doesn't have clique finding, this is a placeholder
                patterns['cliques'] = []
            except Exception:
                patterns['cliques'] = []
        
        return patterns
    
    def compute_centrality_metrics(self) -> Dict[int, Dict[str, float]]:
        """Compute various centrality metrics for nodes."""
        if 'centrality' in self._analysis_cache:
            return self._analysis_cache['centrality']
        
        metrics = {}
        
        try:
            # Betweenness centrality
            betweenness = rx.betweenness_centrality(self.graph)
            
            # Degree centrality
            if isinstance(self.graph, rx.PyDiGraph):
                in_degrees = self.graph.in_degree_for_index
                out_degrees = self.graph.out_degree_for_index
            else:
                degrees = self.graph.degree_for_index
            
            # Closeness centrality
            closeness = rx.closeness_centrality(self.graph)
            
            # Combine metrics
            for node_idx in self.graph.node_indices():
                metrics[node_idx] = {
                    'betweenness': betweenness.get(node_idx, 0.0),
                    'closeness': closeness.get(node_idx, 0.0)
                }
                
                if isinstance(self.graph, rx.PyDiGraph):
                    metrics[node_idx]['in_degree'] = in_degrees(node_idx)
                    metrics[node_idx]['out_degree'] = out_degrees(node_idx)
                else:
                    metrics[node_idx]['degree'] = degrees(node_idx)
            
        except Exception:
            # Fallback to basic degree metrics
            for node_idx in self.graph.node_indices():
                if isinstance(self.graph, rx.PyDiGraph):
                    metrics[node_idx] = {
                        'in_degree': self.graph.in_degree(node_idx),
                        'out_degree': self.graph.out_degree(node_idx),
                        'betweenness': 0.0,
                        'closeness': 0.0
                    }
                else:
                    metrics[node_idx] = {
                        'degree': self.graph.degree(node_idx),
                        'betweenness': 0.0,
                        'closeness': 0.0
                    }
        
        self._analysis_cache['centrality'] = metrics
        return metrics
    
    def find_communities(self) -> List[List[int]]:
        """Find communities in the graph."""
        try:
            # Simple community detection (placeholder)
            # In a full implementation, this would use proper community detection algorithms
            components = rx.weakly_connected_components(self.graph) if isinstance(self.graph, rx.PyDiGraph) else rx.connected_components(self.graph)
            return components
        except Exception:
            return []
    
    def compute_graph_metrics(self) -> Dict[str, Any]:
        """Compute comprehensive graph metrics."""
        if 'graph_metrics' in self._analysis_cache:
            return self._analysis_cache['graph_metrics']
        
        num_nodes = len(self.graph.nodes())
        num_edges = len(self.graph.edges())
        
        metrics = {
            'num_nodes': num_nodes,
            'num_edges': num_edges,
            'density': num_edges / (num_nodes * (num_nodes - 1)) if num_nodes > 1 else 0,
        }
        
        try:
            # Connectivity
            if isinstance(self.graph, rx.PyDiGraph):
                metrics['is_weakly_connected'] = rx.is_weakly_connected(self.graph)
                metrics['is_dag'] = rx.is_directed_acyclic_graph(self.graph)
            else:
                metrics['is_connected'] = rx.is_connected(self.graph)
            
            # Diameter (max shortest path)
            if num_nodes > 1 and num_nodes < 1000:  # Avoid expensive computation on large graphs
                try:
                    distances = rx.distance_matrix(self.graph)
                    if distances.size > 0:
                        metrics['diameter'] = float(distances.max())
                        metrics['average_path_length'] = float(distances[distances != float('inf')].mean())
                except Exception:
                    metrics['diameter'] = None
                    metrics['average_path_length'] = None
        
        except Exception:
            pass
        
        # Node type distribution
        type_counts = {}
        for node_data in self.graph.nodes():
            type_name = node_data.get('type_name', 'unknown')
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        metrics['type_distribution'] = type_counts
        metrics['unique_types'] = len(type_counts)
        
        # Edge type distribution
        edge_type_counts = {}
        for edge_data in self.graph.edges():
            edge_type = edge_data.get('edge_type', 'unknown')
            edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
        
        metrics['edge_type_distribution'] = edge_type_counts
        
        self._analysis_cache['graph_metrics'] = metrics
        return metrics
    
    def get_subgraph(self, node_indices: List[int]) -> Union[rx.PyDiGraph, rx.PyGraph]:
        """Extract subgraph containing specified nodes."""
        return self.graph.subgraph(node_indices)
    
    def clear_cache(self):
        """Clear analysis cache."""
        self._analysis_cache.clear()


# Convenience functions
def build_ast_graph(nodegroup: NodeGroup, **kwargs) -> Union[rx.PyDiGraph, rx.PyGraph]:
    """Build AST graph from NodeGroup with default settings."""
    builder = GraphBuilder(nodegroup)
    return builder.to_graph(directed=True, include_siblings=True, **kwargs)


def find_pattern_in_ast(pattern_nodes: List[TSNode], 
                       target_nodegroup: NodeGroup,
                       max_matches: int = 10) -> List[Dict[int, int]]:
    """Find pattern matches in target AST."""
    # Build pattern graph
    pattern_group = NodeGroup(pattern_nodes)
    pattern_graph = GraphBuilder(pattern_group).to_graph(directed=True)
    
    # Build target graph
    target_graph = build_ast_graph(target_nodegroup)
    
    # Find matches
    matcher = PatternMatcher(pattern_graph)
    return matcher.find_matches(target_graph, max_matches=max_matches)


def analyze_ast_patterns(nodegroup: NodeGroup) -> Dict[str, Any]:
    """Comprehensive AST pattern analysis."""
    graph = build_ast_graph(nodegroup, include_control_flow=True, include_data_flow=True)
    analyzer = GraphAnalyzer(graph)
    
    return {
        'graph_metrics': analyzer.compute_graph_metrics(),
        'centrality_metrics': analyzer.compute_centrality_metrics(),
        'structural_patterns': analyzer.detect_structural_patterns(),
        'communities': analyzer.find_communities()
    }
