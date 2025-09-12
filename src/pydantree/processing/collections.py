# pydantree/processing/collections.py
from __future__ import annotations

import hashlib
import threading
from typing import (
    Callable, Generic, Iterator, TypeVar, Union, Any, List, Set, Optional, 
    Tuple, Dict, FrozenSet, Hashable
)
from abc import ABC, abstractmethod
from functools import reduce, lru_cache, cached_property
from operator import or_, and_
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

from pydantic import BaseModel, ConfigDict, Field

from ..core.nodes import TSNode, TraversalOrder
from ..core.profiler import PerformanceProfiler

T = TypeVar("T", bound=TSNode)


class NodeSelector(ABC):
    """Enhanced abstract base for node selection predicates with caching."""
    
    def __init__(self):
        self._cache: Dict[str, bool] = {}
        self._cache_enabled = True
        self._cache_size = 1000
    
    @abstractmethod
    def matches(self, node: TSNode) -> bool:
        """Return True if node matches this selector."""
        pass
    
    def matches_cached(self, node: TSNode) -> bool:
        """Cached version of matches for performance."""
        if not self._cache_enabled:
            return self.matches(node)
        
        # Use structural hash for cache key
        cache_key = node.structural_hash
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Check cache size and evict if necessary
        if len(self._cache) >= self._cache_size:
            # Remove oldest half
            items = list(self._cache.items())
            self._cache = dict(items[len(items)//2:])
        
        result = self.matches(node)
        self._cache[cache_key] = result
        return result
    
    def clear_cache(self) -> None:
        """Clear selector cache."""
        self._cache.clear()
    
    def __and__(self, other: NodeSelector) -> NodeSelector:
        """Combine selectors with AND logic."""
        return AndSelector(self, other)
    
    def __or__(self, other: NodeSelector) -> NodeSelector:
        """Combine selectors with OR logic."""
        return OrSelector(self, other)
    
    def __invert__(self) -> NodeSelector:
        """Negate selector with NOT logic."""
        return NotSelector(self)
    
    def __hash__(self) -> int:
        """Make selectors hashable for caching."""
        return hash(self.__class__.__name__)


class AndSelector(NodeSelector):
    """Logical AND combination of selectors with short-circuiting."""
    
    def __init__(self, left: NodeSelector, right: NodeSelector):
        super().__init__()
        self.left = left
        self.right = right
    
    def matches(self, node: TSNode) -> bool:
        # Short-circuit evaluation
        return self.left.matches_cached(node) and self.right.matches_cached(node)
    
    def __hash__(self) -> int:
        return hash(("and", hash(self.left), hash(self.right)))


class OrSelector(NodeSelector):
    """Logical OR combination of selectors with short-circuiting."""
    
    def __init__(self, left: NodeSelector, right: NodeSelector):
        super().__init__()
        self.left = left
        self.right = right
    
    def matches(self, node: TSNode) -> bool:
        # Short-circuit evaluation
        return self.left.matches_cached(node) or self.right.matches_cached(node)
    
    def __hash__(self) -> int:
        return hash(("or", hash(self.left), hash(self.right)))


class NotSelector(NodeSelector):
    """Logical NOT selector."""
    
    def __init__(self, selector: NodeSelector):
        super().__init__()
        self.selector = selector
    
    def matches(self, node: TSNode) -> bool:
        return not self.selector.matches_cached(node)
    
    def __hash__(self) -> int:
        return hash(("not", hash(self.selector)))


class TypeSelector(NodeSelector):
    """Select nodes by type name with pattern matching."""
    
    def __init__(self, type_name: Union[str, Set[str]], exact: bool = True):
        super().__init__()
        if isinstance(type_name, str):
            self.type_names = {type_name}
        else:
            self.type_names = type_name
        self.exact = exact
    
    def matches(self, node: TSNode) -> bool:
        if self.exact:
            return node.type_name in self.type_names
        else:
            # Pattern matching
            return any(pattern in node.type_name for pattern in self.type_names)
    
    def __hash__(self) -> int:
        return hash(("type", frozenset(self.type_names), self.exact))


class ClassSelector(NodeSelector):
    """Select nodes by Python class with inheritance support."""
    
    def __init__(self, node_class: Union[type, Tuple[type, ...]], strict: bool = False):
        super().__init__()
        self.node_classes = node_class if isinstance(node_class, tuple) else (node_class,)
        self.strict = strict
    
    def matches(self, node: TSNode) -> bool:
        if self.strict:
            return type(node) in self.node_classes
        else:
            return isinstance(node, self.node_classes)
    
    def __hash__(self) -> int:
        return hash(("class", self.node_classes, self.strict))


class PredicateSelector(NodeSelector):
    """Select nodes using a callable predicate with function caching."""
    
    def __init__(self, predicate: Callable[[TSNode], bool], name: Optional[str] = None):
        super().__init__()
        self.predicate = predicate
        self.name = name or getattr(predicate, '__name__', 'anonymous')
    
    def matches(self, node: TSNode) -> bool:
        return self.predicate(node)
    
    def __hash__(self) -> int:
        return hash(("predicate", self.name))


class TextSelector(NodeSelector):
    """Select nodes by text content with regex support."""
    
    def __init__(self, pattern: str, exact: bool = True, case_sensitive: bool = True, use_regex: bool = False):
        super().__init__()
        self.pattern = pattern
        self.exact = exact
        self.case_sensitive = case_sensitive
        self.use_regex = use_regex
        
        if use_regex:
            import re
            flags = 0 if case_sensitive else re.IGNORECASE
            self.regex = re.compile(pattern, flags)
    
    def matches(self, node: TSNode) -> bool:
        text = node.text if self.case_sensitive else node.text.lower()
        pattern = self.pattern if self.case_sensitive else self.pattern.lower()
        
        if self.use_regex:
            return bool(self.regex.search(text))
        elif self.exact:
            return text == pattern
        else:
            return pattern in text
    
    def __hash__(self) -> int:
        return hash(("text", self.pattern, self.exact, self.case_sensitive, self.use_regex))


class PositionSelector(NodeSelector):
    """Select nodes by position criteria."""
    
    def __init__(self, 
                 min_line: Optional[int] = None,
                 max_line: Optional[int] = None,
                 min_column: Optional[int] = None,
                 max_column: Optional[int] = None,
                 min_bytes: Optional[int] = None,
                 max_bytes: Optional[int] = None):
        super().__init__()
        self.min_line = min_line
        self.max_line = max_line
        self.min_column = min_column
        self.max_column = max_column
        self.min_bytes = min_bytes
        self.max_bytes = max_bytes
    
    def matches(self, node: TSNode) -> bool:
        if self.min_line is not None and node.start_point.row < self.min_line:
            return False
        if self.max_line is not None and node.end_point.row > self.max_line:
            return False
        if self.min_column is not None and node.start_point.column < self.min_column:
            return False
        if self.max_column is not None and node.end_point.column > self.max_column:
            return False
        if self.min_bytes is not None and node.start_byte < self.min_bytes:
            return False
        if self.max_bytes is not None and node.end_byte > self.max_bytes:
            return False
        return True
    
    def __hash__(self) -> int:
        return hash(("position", self.min_line, self.max_line, self.min_column, 
                    self.max_column, self.min_bytes, self.max_bytes))


class NodeGroup(BaseModel, Generic[T]):
    """Enhanced lazy, immutable collection of TSNode objects with advanced operations."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    
    # Core storage - using frozenset for immutability and fast set operations
    _nodes: FrozenSet[TSNode] = Field(default_factory=frozenset, alias="nodes")
    _selectors: Tuple[NodeSelector, ...] = Field(default_factory=tuple, alias="selectors")
    _cached_results: Optional[FrozenSet[TSNode]] = Field(default=None, exclude=True)
    _cache_valid: bool = Field(default=False, exclude=True)
    _metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Performance tracking
    _creation_time: float = Field(default_factory=lambda: __import__('time').time(), exclude=True)
    _access_count: int = Field(default=0, exclude=True)
    
    def __init__(self, input_nodes: Union[TSNode, Iterator[TSNode], List[TSNode], Set[TSNode], 
                                        FrozenSet[TSNode], None] = None, **data):
        if input_nodes is None:
            nodes_set = frozenset()
        elif isinstance(input_nodes, TSNode):
            nodes_set = frozenset([input_nodes])
        elif isinstance(input_nodes, (frozenset, set)):
            nodes_set = frozenset(input_nodes)
        elif isinstance(input_nodes, (list, tuple)):
            nodes_set = frozenset(input_nodes)
        else:
            # Iterator
            nodes_set = frozenset(input_nodes)
        
        super().__init__(nodes=nodes_set, **data)
    
    # ========================================================================
    # Enhanced Lazy Evaluation with Caching
    # ========================================================================
    
    def _invalidate_cache(self) -> None:
        """Invalidate cached results."""
        object.__setattr__(self, '_cache_valid', False)
        object.__setattr__(self, '_cached_results', None)
    
    def _apply_selectors(self) -> FrozenSet[TSNode]:
        """Apply all pending selectors with caching."""
        if self._cache_valid and self._cached_results is not None:
            return self._cached_results
        
        result_set = set(self._nodes)
        
        # Apply selectors in sequence
        for selector in self._selectors:
            if not result_set:  # Short-circuit if empty
                break
            result_set = {node for node in result_set if selector.matches_cached(node)}
        
        frozen_result = frozenset(result_set)
        
        # Cache the result
        object.__setattr__(self, '_cached_results', frozen_result)
        object.__setattr__(self, '_cache_valid', True)
        
        return frozen_result
    
    def _materialize(self) -> FrozenSet[TSNode]:
        """Force evaluation of lazy operations with access tracking."""
        object.__setattr__(self, '_access_count', self._access_count + 1)
        return self._apply_selectors()
    
    # ========================================================================
    # Enhanced Filtering and Selection
    # ========================================================================
    
    def filter(self, selector: NodeSelector) -> NodeGroup[T]:
        """Add a filter selector with selector optimization."""
        # Optimize selector chains
        optimized_selectors = self._optimize_selectors(self._selectors + (selector,))
        
        return self.__class__(
            input_nodes=self._nodes,
            selectors=optimized_selectors,
            metadata=self._metadata.copy()
        )
    
    def _optimize_selectors(self, selectors: Tuple[NodeSelector, ...]) -> Tuple[NodeSelector, ...]:
        """Optimize selector chain for performance."""
        if not selectors:
            return selectors
        
        # Combine consecutive type selectors
        optimized = []
        type_selectors = []
        
        for selector in selectors:
            if isinstance(selector, TypeSelector):
                type_selectors.append(selector)
            else:
                if type_selectors:
                    # Combine type selectors
                    combined_types = set()
                    for ts in type_selectors:
                        combined_types.update(ts.type_names)
                    optimized.append(TypeSelector(combined_types))
                    type_selectors = []
                optimized.append(selector)
        
        if type_selectors:
            combined_types = set()
            for ts in type_selectors:
                combined_types.update(ts.type_names)
            optimized.append(TypeSelector(combined_types))
        
        return tuple(optimized)
    
    def filter_type(self, type_names: Union[str, List[str], Set[str]], exact: bool = True) -> NodeGroup[T]:
        """Filter by node type name(s) with pattern support."""
        if isinstance(type_names, str):
            type_set = {type_names}
        elif isinstance(type_names, list):
            type_set = set(type_names)
        else:
            type_set = type_names
        
        return self.filter(TypeSelector(type_set, exact=exact))
    
    def filter_class(self, node_classes: Union[type, Tuple[type, ...]], strict: bool = False) -> NodeGroup[T]:
        """Filter by Python class with inheritance support."""
        return self.filter(ClassSelector(node_classes, strict=strict))
    
    def filter_text(self, pattern: str, exact: bool = False, case_sensitive: bool = True, 
                   use_regex: bool = False) -> NodeGroup[T]:
        """Filter by text content with regex support."""
        return self.filter(TextSelector(pattern, exact, case_sensitive, use_regex))
    
    def filter_position(self, **kwargs) -> NodeGroup[T]:
        """Filter by position criteria."""
        return self.filter(PositionSelector(**kwargs))
    
    def where(self, predicate: Callable[[TSNode], bool], name: Optional[str] = None) -> NodeGroup[T]:
        """Filter using custom predicate."""
        return self.filter(PredicateSelector(predicate, name))
    
    # ========================================================================
    # Advanced Set Operations
    # ========================================================================
    
    def union(self, *others: NodeGroup[T]) -> NodeGroup[T]:
        """Union with multiple NodeGroups."""
        all_nodes = set(self._materialize())
        metadata = self._metadata.copy()
        
        for other in others:
            all_nodes.update(other._materialize())
            metadata.update(other._metadata)
        
        return self.__class__(input_nodes=all_nodes, metadata=metadata)
    
    def intersection(self, *others: NodeGroup[T]) -> NodeGroup[T]:
        """Intersection with multiple NodeGroups."""
        result_nodes = set(self._materialize())
        
        for other in others:
            result_nodes &= set(other._materialize())
        
        return self.__class__(input_nodes=result_nodes, metadata=self._metadata.copy())
    
    def difference(self, *others: NodeGroup[T]) -> NodeGroup[T]:
        """Difference from multiple NodeGroups."""
        result_nodes = set(self._materialize())
        
        for other in others:
            result_nodes -= set(other._materialize())
        
        return self.__class__(input_nodes=result_nodes, metadata=self._metadata.copy())
    
    def symmetric_difference(self, other: NodeGroup[T]) -> NodeGroup[T]:
        """Symmetric difference with another NodeGroup."""
        self_nodes = set(self._materialize())
        other_nodes = set(other._materialize())
        
        return self.__class__(
            input_nodes=self_nodes ^ other_nodes,
            metadata={**self._metadata, **other._metadata}
        )
    
    # ========================================================================
    # Advanced Analysis and Grouping
    # ========================================================================
    
    def groupby(self, key: Union[str, Callable[[TSNode], Any]], 
               preserve_order: bool = False) -> Dict[Any, NodeGroup[T]]:
        """Group nodes by key function with metadata preservation."""
        groups: Dict[Any, List[TSNode]] = defaultdict(list)
        
        if isinstance(key, str):
            # Group by attribute
            key_func = lambda node: getattr(node, key, None)
        else:
            key_func = key
        
        for node in self._materialize():
            group_key = key_func(node)
            groups[group_key].append(node)
        
        # Create NodeGroups with metadata
        result = {}
        for group_key, nodes in groups.items():
            group_metadata = self._metadata.copy()
            group_metadata['group_key'] = group_key
            group_metadata['group_size'] = len(nodes)
            
            result[group_key] = self.__class__(
                input_nodes=nodes,
                metadata=group_metadata
            )
        
        return result
    
    def partition(self, predicate: Callable[[TSNode], bool]) -> Tuple[NodeGroup[T], NodeGroup[T]]:
        """Partition nodes into two groups based on predicate."""
        true_nodes = []
        false_nodes = []
        
        for node in self._materialize():
            if predicate(node):
                true_nodes.append(node)
            else:
                false_nodes.append(node)
        
        true_metadata = self._metadata.copy()
        true_metadata['partition'] = 'true'
        
        false_metadata = self._metadata.copy()
        false_metadata['partition'] = 'false'
        
        return (
            self.__class__(input_nodes=true_nodes, metadata=true_metadata),
            self.__class__(input_nodes=false_nodes, metadata=false_metadata)
        )
    
    def sample(self, n: int, seed: Optional[int] = None) -> NodeGroup[T]:
        """Random sample of n nodes."""
        import random
        if seed is not None:
            random.seed(seed)
        
        nodes = list(self._materialize())
        if len(nodes) <= n:
            return self
        
        sampled = random.sample(nodes, n)
        sample_metadata = self._metadata.copy()
        sample_metadata['sample_size'] = n
        sample_metadata['original_size'] = len(nodes)
        
        return self.__class__(input_nodes=sampled, metadata=sample_metadata)
    
    # ========================================================================
    # Similarity and Clustering
    # ========================================================================
    
    def find_similar(self, reference: TSNode, threshold: float = 0.8, 
                    similarity_func: Optional[Callable[[TSNode, TSNode], float]] = None) -> NodeGroup[T]:
        """Find nodes similar to reference node."""
        if similarity_func is None:
            similarity_func = lambda a, b: a.similarity_score(b)
        
        similar_nodes = []
        for node in self._materialize():
            if similarity_func(node, reference) >= threshold:
                similar_nodes.append(node)
        
        return self.__class__(input_nodes=similar_nodes, metadata=self._metadata.copy())
    
    def cluster_by_similarity(self, threshold: float = 0.8, 
                             max_clusters: int = 50) -> List[NodeGroup[T]]:
        """Cluster nodes by structural similarity."""
        nodes = list(self._materialize())
        if len(nodes) <= 1:
            return [self]
        
        # Simple clustering algorithm
        clusters = []
        remaining_nodes = set(nodes)
        
        while remaining_nodes and len(clusters) < max_clusters:
            # Pick a seed node
            seed = next(iter(remaining_nodes))
            cluster_nodes = {seed}
            remaining_nodes.remove(seed)
            
            # Find similar nodes
            to_remove = set()
            for node in remaining_nodes:
                if seed.similarity_score(node) >= threshold:
                    cluster_nodes.add(node)
                    to_remove.add(node)
            
            remaining_nodes -= to_remove
            
            cluster_metadata = self._metadata.copy()
            cluster_metadata['cluster_seed'] = seed.type_name
            cluster_metadata['cluster_size'] = len(cluster_nodes)
            
            clusters.append(self.__class__(
                input_nodes=cluster_nodes,
                metadata=cluster_metadata
            ))
        
        return clusters
    
    def deduplicate(self, 
                   key: Optional[Callable[[TSNode], Hashable]] = None,
                   similarity_threshold: float = 1.0) -> NodeGroup[T]:
        """Remove duplicate nodes based on key or similarity."""
        if key is None and similarity_threshold >= 1.0:
            # Simple deduplication using structural hash
            unique_nodes = {}
            for node in self._materialize():
                unique_nodes[node.structural_hash] = node
            return self.__class__(input_nodes=unique_nodes.values(), metadata=self._metadata.copy())
        
        elif key is not None:
            # Key-based deduplication
            unique_nodes = {}
            for node in self._materialize():
                node_key = key(node)
                if node_key not in unique_nodes:
                    unique_nodes[node_key] = node
            return self.__class__(input_nodes=unique_nodes.values(), metadata=self._metadata.copy())
        
        else:
            # Similarity-based deduplication
            nodes = list(self._materialize())
            unique_nodes = []
            
            for node in nodes:
                is_unique = True
                for unique_node in unique_nodes:
                    if node.similarity_score(unique_node) >= similarity_threshold:
                        is_unique = False
                        break
                if is_unique:
                    unique_nodes.append(node)
            
            return self.__class__(input_nodes=unique_nodes, metadata=self._metadata.copy())
    
    # ========================================================================
    # Performance and Statistics
    # ========================================================================
    
    @cached_property
    def statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about this NodeGroup."""
        nodes = self._materialize()
        
        if not nodes:
            return {
                'size': 0,
                'empty': True,
                'selectors_count': len(self._selectors),
                'creation_time': self._creation_time,
                'access_count': self._access_count
            }
        
        # Type distribution
        type_counts = Counter(node.type_name for node in nodes)
        
        # Size distribution
        sizes = [len(node.descendants()) for node in nodes]
        complexity_scores = [node.calculate_complexity() for node in nodes]
        
        return {
            'size': len(nodes),
            'empty': False,
            'selectors_count': len(self._selectors),
            'creation_time': self._creation_time,
            'access_count': self._access_count,
            'type_distribution': dict(type_counts),
            'most_common_type': type_counts.most_common(1)[0] if type_counts else None,
            'size_stats': {
                'min': min(sizes),
                'max': max(sizes),
                'avg': sum(sizes) / len(sizes)
            },
            'complexity_stats': {
                'min': min(complexity_scores),
                'max': max(complexity_scores),
                'avg': sum(complexity_scores) / len(complexity_scores)
            }
        }
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get caching information for performance analysis."""
        return {
            'cache_valid': self._cache_valid,
            'cached_results_size': len(self._cached_results) if self._cached_results else 0,
            'selectors_count': len(self._selectors),
            'access_count': self._access_count,
            'nodes_count': len(self._nodes)
        }
    
    # ========================================================================
    # Magic Methods and Collection Interface
    # ========================================================================
    
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
    
    def __hash__(self) -> int:
        """Hash based on node content."""
        if not hasattr(self, '_hash_cache'):
            node_hashes = tuple(sorted(node.structural_hash for node in self._nodes))
            selector_hashes = tuple(hash(s) for s in self._selectors)
            object.__setattr__(self, '_hash_cache', hash((node_hashes, selector_hashes)))
        return self._hash_cache
    
    # ========================================================================
    # Factory and Utility Methods
    # ========================================================================
    
    @classmethod
    def from_tree(cls, root: TSNode, traversal: TraversalOrder = TraversalOrder.DEPTH_FIRST) -> NodeGroup[TSNode]:
        """Create NodeGroup from entire tree with specified traversal."""
        nodes = [root] + list(root.descendants(traversal))
        
        metadata = {
            'source': 'tree',
            'root_type': root.type_name,
            'traversal_order': traversal.value,
            'tree_depth': root.max_depth
        }
        
        return cls(input_nodes=nodes, metadata=metadata)
    
    @classmethod
    def from_files(cls, file_results: List[Any]) -> NodeGroup[TSNode]:
        """Create NodeGroup from file processing results."""
        nodes = []
        metadata = {
            'source': 'files',
            'file_count': len(file_results),
            'languages': set()
        }
        
        for result in file_results:
            if hasattr(result, 'success') and result.success and hasattr(result, 'node'):
                nodes.append(result.node)
                if hasattr(result, 'language'):
                    metadata['languages'].add(result.language)
        
        metadata['successful_files'] = len(nodes)
        metadata['languages'] = list(metadata['languages'])
        
        return cls(input_nodes=nodes, metadata=metadata)
    
    @classmethod
    def empty(cls) -> NodeGroup[TSNode]:
        """Create empty NodeGroup."""
        return cls(metadata={'source': 'empty'})
    
    def to_graph(self):
        """Convert to rustworkx graph via GraphBuilder."""
        from ..graph.builder import GraphBuilder
        return GraphBuilder(self).to_graph()
    
    # ========================================================================
    # Export and Serialization
    # ========================================================================
    
    def export(self) -> 'ExportEngine':
        """Get ExportEngine for this NodeGroup."""
        from ..export.engine import ExportEngine
        return ExportEngine(self)
    
    def to_list(self) -> List[TSNode]:
        """Convert to list preserving order."""
        return list(self._materialize())
    
    def to_set(self) -> Set[TSNode]:
        """Convert to mutable set."""
        return set(self._materialize())
    
    def to_frozenset(self) -> FrozenSet[TSNode]:
        """Convert to frozen set."""
        return self._materialize()


# ========================================================================
# Factory Functions and Utilities
# ========================================================================

def nodes(*nodes: TSNode, metadata: Optional[Dict[str, Any]] = None) -> NodeGroup[TSNode]:
    """Create NodeGroup from individual nodes."""
    return NodeGroup(input_nodes=nodes, metadata=metadata or {})


def from_tree(root: TSNode, **kwargs) -> NodeGroup[TSNode]:
    """Create NodeGroup from entire tree."""
    return NodeGroup.from_tree(root, **kwargs)


def empty(**kwargs) -> NodeGroup[TSNode]:
    """Create empty NodeGroup."""
    return NodeGroup.empty()


def union(*groups: NodeGroup) -> NodeGroup[TSNode]:
    """Union multiple NodeGroups."""
    if not groups:
        return empty()
    
    first_group = groups[0]
    if len(groups) == 1:
        return first_group
    
    return first_group.union(*groups[1:])


def intersection(*groups: NodeGroup) -> NodeGroup[TSNode]:
    """Intersect multiple NodeGroups."""
    if not groups:
        return empty()
    
    first_group = groups[0]
    if len(groups) == 1:
        return first_group
    
    return first_group.intersection(*groups[1:])


# Performance utilities
def benchmark_nodegroup_operations(nodegroup: NodeGroup, operations: int = 1000) -> Dict[str, float]:
    """Benchmark common NodeGroup operations."""
    import time
    
    results = {}
    
    # Benchmark iteration
    start = time.time()
    for _ in range(operations):
        list(nodegroup)
    results['iteration'] = time.time() - start
    
    # Benchmark filtering
    start = time.time()
    for _ in range(operations):
        nodegroup.filter_type("identifier")
    results['filtering'] = time.time() - start
    
    # Benchmark set operations
    if len(nodegroup) > 0:
        half_group = nodegroup.sample(min(len(nodegroup) // 2, 100))
        start = time.time()
        for _ in range(operations // 10):  # Fewer iterations for expensive operations
            nodegroup.union(half_group)
        results['union'] = (time.time() - start) * 10  # Normalize
    
    return results
