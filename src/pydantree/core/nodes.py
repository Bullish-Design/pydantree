# pydantree/core/nodes.py
from __future__ import annotations

import json
import hashlib
from typing import List, ClassVar, Optional, Dict, Any, Set, Union, Iterator, Callable
from enum import Enum
from functools import cached_property, lru_cache
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
    """Enhanced point with utility methods."""
    row: int
    column: int
    
    model_config = ConfigDict(frozen=True)
    
    def __str__(self) -> str:
        return f"({self.row},{self.column})"
    
    def to_dict(self) -> Dict[str, int]:
        return {"row": self.row, "column": self.column}
    
    def distance_to(self, other: TSPoint) -> int:
        """Calculate Manhattan distance to another point."""
        return abs(self.row - other.row) + abs(self.column - other.column)


class TSNode(BaseModel):
    """Enhanced TSNode with integrated analysis, export, and performance optimizations."""
    
    # Core fields
    type_name: str
    start_byte: int
    end_byte: int
    start_point: TSPoint
    end_point: TSPoint
    text: str
    children: List[TSNode] = Field(default_factory=list)
    is_named: bool = True
    field_name: Optional[str] = None
    
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    __match_args__ = ("type_name", "children")
    
    # Enhanced registry with metadata and caching
    _registry: ClassVar[Dict[str, type[TSNode]]] = {}
    _reverse_registry: ClassVar[Dict[type[TSNode], str]] = {}
    _registry_metadata: ClassVar[Dict[str, Dict[str, Any]]] = {}
    _metrics_cache: ClassVar[Dict[str, Dict[str, Any]]] = {}
    
    # ========================================================================
    # Computed Properties (Cached for Performance)
    # ========================================================================
    
    @computed_field
    @property
    def byte_length(self) -> int:
        """Byte length of this node."""
        return self.end_byte - self.start_byte
    
    @computed_field
    @property
    def line_count(self) -> int:
        """Number of lines spanned by this node."""
        return self.end_point.row - self.start_point.row + 1
    
    @computed_field
    @property
    def column_span(self) -> int:
        """Column span for single-line nodes."""
        if self.line_count == 1:
            return self.end_point.column - self.start_point.column
        return 0
    
    @cached_property
    def descendants_count(self) -> int:
        """Total number of descendant nodes."""
        return len(list(self.descendants()))
    
    @cached_property
    def max_depth(self) -> int:
        """Maximum depth of tree rooted at this node."""
        return self._calculate_depth()
    
    @cached_property
    def leaf_count(self) -> int:
        """Number of leaf nodes in subtree."""
        return len([node for node in self.descendants() if not node.children])
    
    @cached_property
    def structural_hash(self) -> str:
        """Structural hash for fast comparison."""
        return self.get_structural_hash(include_text=False)
    
    @cached_property
    def fan_out(self) -> float:
        """Average branching factor."""
        internal_nodes = [node for node in self.descendants() if node.children]
        if not internal_nodes:
            return 0.0
        return sum(len(node.children) for node in internal_nodes) / len(internal_nodes)
    
    def _calculate_depth(self, current: int = 0) -> int:
        """Recursively calculate maximum depth."""
        if not self.children:
            return current
        return max(child._calculate_depth(current + 1) for child in self.children)
    
    # ========================================================================
    # Enhanced Tree Traversal
    # ========================================================================
    
    def descendants(self, order: TraversalOrder = TraversalOrder.DEPTH_FIRST) -> Iterator[TSNode]:
        """Get all descendant nodes with specified traversal order."""
        if order == TraversalOrder.BREADTH_FIRST:
            yield from self._breadth_first_traversal()
        elif order == TraversalOrder.PREORDER:
            yield from self._preorder_traversal()
        elif order == TraversalOrder.POSTORDER:
            yield from self._postorder_traversal()
        else:  # DEPTH_FIRST (default)
            yield from self._depth_first_traversal()
    
    def _depth_first_traversal(self) -> Iterator[TSNode]:
        """Depth-first traversal (children first)."""
        for child in self.children:
            yield child
            yield from child._depth_first_traversal()
    
    def _breadth_first_traversal(self) -> Iterator[TSNode]:
        """Breadth-first traversal using queue."""
        from collections import deque
        queue = deque(self.children)
        while queue:
            node = queue.popleft()
            yield node
            queue.extend(node.children)
    
    def _preorder_traversal(self) -> Iterator[TSNode]:
        """Preorder traversal (node before children)."""
        for child in self.children:
            yield child
            yield from child._preorder_traversal()
    
    def _postorder_traversal(self) -> Iterator[TSNode]:
        """Postorder traversal (children before node)."""
        for child in self.children:
            yield from child._postorder_traversal()
            yield child
    
    def find_all_by_type(self, type_names: Union[str, Set[str]]) -> List[TSNode]:
        """Find all descendants matching one or more types."""
        if isinstance(type_names, str):
            type_names = {type_names}
        return [node for node in self.descendants() if node.type_name in type_names]
    
    def find_by_predicate(self, predicate: Callable[[TSNode], bool]) -> List[TSNode]:
        """Find all descendants matching predicate function."""
        return [node for node in self.descendants() if predicate(node)]
    
    def find_nearest_ancestor(self, predicate: Callable[[TSNode], bool]) -> Optional[TSNode]:
        """Find nearest ancestor matching predicate (requires parent tracking)."""
        # This would require parent pointers - placeholder for now
        return None
    
    @lru_cache(maxsize=1024)
    def find_first_by_type_cached(self, type_name: str) -> Optional[TSNode]:
        """Cached version of find_first_by_type for frequently queried types."""
        for node in self.descendants():
            if node.type_name == type_name:
                return node
        return None
    
    # ========================================================================
    # Advanced Analysis Methods
    # ========================================================================
    
    def get_metrics(self, include_advanced: bool = False) -> Dict[str, Any]:
        """Get comprehensive structural metrics with optional caching."""
        cache_key = f"{self.structural_hash}:{include_advanced}"
        if cache_key in self._metrics_cache:
            return self._metrics_cache[cache_key]
        
        descendants = list(self.descendants())
        
        # Basic type distribution
        type_counts = defaultdict(int)
        for desc in descendants:
            type_counts[desc.type_name] += 1
        
        # Language-specific constructs
        constructs = self._extract_language_constructs(descendants)
        
        metrics = {
            # Basic metrics
            'total_nodes': len(descendants),
            'max_depth': self.max_depth,
            'byte_length': self.byte_length,
            'line_count': self.line_count,
            'leaf_count': self.leaf_count,
            'fan_out': self.fan_out,
            
            # Type distribution
            'type_distribution': dict(type_counts),
            'unique_types': len(type_counts),
            'most_common_type': max(type_counts, key=type_counts.get) if type_counts else None,
            
            # Structural metrics
            'branching_factor': self.fan_out,
            'balance_factor': self._calculate_balance_factor(descendants),
            
            # Language constructs
            **constructs,
            
            # Complexity
            'cyclomatic_complexity': self.calculate_complexity(),
            'cognitive_complexity': self._calculate_cognitive_complexity() if include_advanced else 0,
        }
        
        if include_advanced:
            metrics.update({
                'nesting_depth': self._calculate_nesting_depth(),
                'halstead_metrics': self._calculate_halstead_metrics(descendants),
                'maintainability_index': self._calculate_maintainability_index(metrics),
            })
        
        # Cache for performance
        self._metrics_cache[cache_key] = metrics
        return metrics
    
    def _extract_language_constructs(self, descendants: List[TSNode]) -> Dict[str, int]:
        """Extract language-specific construct counts."""
        return {
            'functions': len([d for d in descendants if 'function' in d.type_name.lower()]),
            'classes': len([d for d in descendants if 'class' in d.type_name.lower()]),
            'conditionals': len([d for d in descendants if d.type_name in {
                'if_statement', 'conditional_expression', 'case_statement', 'match_statement'
            }]),
            'loops': len([d for d in descendants if d.type_name in {
                'for_statement', 'while_statement', 'do_statement', 'for_in_statement'
            }]),
            'assignments': len([d for d in descendants if 'assignment' in d.type_name.lower()]),
            'identifiers': len([d for d in descendants if d.type_name == 'identifier']),
            'literals': len([d for d in descendants if 'literal' in d.type_name.lower()]),
            'calls': len([d for d in descendants if 'call' in d.type_name.lower()]),
        }
    
    def _calculate_balance_factor(self, descendants: List[TSNode]) -> float:
        """Calculate tree balance factor (0 = perfectly balanced, 1 = completely unbalanced)."""
        if not descendants:
            return 0.0
        
        depths = []
        for node in descendants:
            if not node.children:  # Leaf node
                depth = self._get_node_depth(node)
                depths.append(depth)
        
        if not depths:
            return 0.0
        
        min_depth, max_depth = min(depths), max(depths)
        return (max_depth - min_depth) / max_depth if max_depth > 0 else 0.0
    
    def _get_node_depth(self, target: TSNode, current_depth: int = 0) -> int:
        """Get depth of specific node in tree."""
        if self == target:
            return current_depth
        for child in self.children:
            result = child._get_node_depth(target, current_depth + 1)
            if result >= 0:
                return result
        return -1  # Not found
    
    def calculate_complexity(self) -> int:
        """Calculate cyclomatic complexity."""
        complexity_nodes = {
            'if_statement', 'elif_clause', 'else_clause',
            'for_statement', 'while_statement', 'do_statement',
            'try_statement', 'except_clause', 'catch_clause',
            'match_statement', 'case_clause', 'when_clause',
            'conditional_expression', 'ternary_expression',
            'switch_statement', 'default_clause',
            'and', 'or', '&&', '||'
        }
        
        complexity = 1  # Base complexity
        for descendant in self.descendants():
            if (descendant.type_name in complexity_nodes or 
                descendant.text.strip() in complexity_nodes):
                complexity += 1
        
        return complexity
    
    def _calculate_cognitive_complexity(self) -> int:
        """Calculate cognitive complexity (more sophisticated than cyclomatic)."""
        cognitive_complexity = 0
        nesting_level = 0
        
        for node in self.descendants(order=TraversalOrder.PREORDER):
            # Increment for control flow structures
            if node.type_name in {'if_statement', 'for_statement', 'while_statement'}:
                cognitive_complexity += 1 + nesting_level
                nesting_level += 1
            elif node.type_name in {'else_clause', 'elif_clause'}:
                cognitive_complexity += 1
            elif node.type_name in {'try_statement', 'catch_clause', 'except_clause'}:
                cognitive_complexity += 1
            # TODO: Add logic for function boundaries that reset nesting
        
        return cognitive_complexity
    
    def _calculate_nesting_depth(self) -> int:
        """Calculate maximum nesting depth of control structures."""
        max_nesting = 0
        current_nesting = 0
        
        control_structures = {
            'if_statement', 'for_statement', 'while_statement', 
            'try_statement', 'function_definition', 'class_definition'
        }
        
        for node in self.descendants(order=TraversalOrder.PREORDER):
            if node.type_name in control_structures:
                current_nesting += 1
                max_nesting = max(max_nesting, current_nesting)
            # In a real implementation, we'd track when we exit structures
        
        return max_nesting
    
    def _calculate_halstead_metrics(self, descendants: List[TSNode]) -> Dict[str, float]:
        """Calculate Halstead complexity metrics."""
        operators = set()
        operands = set()
        operator_count = 0
        operand_count = 0
        
        operator_types = {'binary_operator', 'unary_operator', 'assignment_operator'}
        operand_types = {'identifier', 'number', 'string'}
        
        for node in descendants:
            if node.type_name in operator_types:
                operators.add(node.text.strip())
                operator_count += 1
            elif node.type_name in operand_types:
                operands.add(node.text.strip())
                operand_count += 1
        
        n1, n2 = len(operators), len(operands)
        N1, N2 = operator_count, operand_count
        
        if n1 == 0 or n2 == 0:
            return {'vocabulary': 0, 'length': 0, 'volume': 0, 'difficulty': 0, 'effort': 0}
        
        vocabulary = n1 + n2
        length = N1 + N2
        volume = length * (vocabulary.bit_length() if vocabulary > 0 else 0)
        difficulty = (n1 / 2) * (N2 / n2) if n2 > 0 else 0
        effort = difficulty * volume
        
        return {
            'vocabulary': vocabulary,
            'length': length,
            'volume': volume,
            'difficulty': difficulty,
            'effort': effort
        }
    
    def _calculate_maintainability_index(self, metrics: Dict[str, Any]) -> float:
        """Calculate maintainability index (0-100 scale)."""
        volume = metrics.get('halstead_metrics', {}).get('volume', 1)
        complexity = metrics.get('cyclomatic_complexity', 1)
        lines = metrics.get('line_count', 1)
        
        # Simplified maintainability index formula
        mi = max(0, (171 - 5.2 * (volume ** 0.23) - 0.23 * complexity - 16.2 * (lines ** 0.5)))
        return min(100, mi)  # Cap at 100
    
    # ========================================================================
    # Enhanced Export Methods
    # ========================================================================
    
    def export_json(self,
                   mode: Union[str, SerializationMode] = SerializationMode.FULL,
                   include_spans: bool = True,
                   include_children: bool = True,
                   include_computed: bool = False,
                   indent: Optional[int] = 2,
                   **kwargs) -> str:
        """Export node as JSON with flexible options."""
        if isinstance(mode, str):
            mode = SerializationMode(mode)
        
        data = self._serialize_by_mode(mode, include_spans, include_children, include_computed)
        return json.dumps(data, indent=indent, default=str, **kwargs)
    
    def export_dict(self,
                   mode: Union[str, SerializationMode] = SerializationMode.FULL,
                   include_spans: bool = True,
                   include_children: bool = True,
                   include_computed: bool = False) -> Dict[str, Any]:
        """Export node as dictionary with flexible options."""
        if isinstance(mode, str):
            mode = SerializationMode(mode)
        
        return self._serialize_by_mode(mode, include_spans, include_children, include_computed)
    
    def export_sexp(self) -> str:
        """Export as S-expression for Lisp-like representation."""
        if not self.children:
            return f"({self.type_name} {repr(self.text)})"
        
        children_sexp = ' '.join(child.export_sexp() for child in self.children)
        return f"({self.type_name} {children_sexp})"
    
    def export(self) -> 'ExportEngine':
        """Get ExportEngine instance for this node."""
        from ..export.engine import ExportEngine
        return ExportEngine(self)
    
    def _serialize_by_mode(self,
                          mode: SerializationMode,
                          include_spans: bool,
                          include_children: bool,
                          include_computed: bool) -> Dict[str, Any]:
        """Internal serialization based on mode."""
        
        if mode == SerializationMode.MINIMAL:
            return {
                'type': self.type_name,
                'children_count': len(self.children),
                'hash': self.structural_hash
            }
        
        elif mode == SerializationMode.METRICS:
            return self.get_metrics(include_advanced=True)
        
        elif mode == SerializationMode.STRUCTURE:
            data = {
                'type': self.type_name,
                'field_name': self.field_name,
                'depth': self.max_depth,
                'descendants': self.descendants_count
            }
            if include_children:
                data['children'] = [
                    child._serialize_by_mode(mode, include_spans, include_children, include_computed)
                    for child in self.children
                ]
            return data
        
        elif mode == SerializationMode.CLEAN:
            data = {
                'type': self.type_name,
                'text': self.text[:100] + '...' if len(self.text) > 100 else self.text,
                'field_name': self.field_name
            }
            if include_children:
                data['children'] = [
                    child._serialize_by_mode(mode, include_spans, include_children, include_computed)
                    for child in self.children
                ]
            return data
        
        else:  # FULL mode
            data = self.model_dump()
            
            if not include_spans:
                for key in ['start_byte', 'end_byte', 'start_point', 'end_point']:
                    data.pop(key, None)
            
            if not include_children:
                data.pop('children', None)
            
            if include_computed:
                data['computed_metrics'] = self.get_metrics(include_advanced=True)
                data['structural_hash'] = self.structural_hash
            
            return data
    
    # ========================================================================
    # Structural Comparison and Similarity
    # ========================================================================
    
    def structural_equals(self, other: TSNode,
                         ignore_text: bool = False,
                         ignore_spans: bool = True) -> bool:
        """Compare structural equality with another node."""
        if self.type_name != other.type_name:
            return False
        
        if not ignore_text and self.text != other.text:
            return False
        
        if len(self.children) != len(other.children):
            return False
        
        return all(
            child.structural_equals(other_child, ignore_text, ignore_spans)
            for child, other_child in zip(self.children, other.children)
        )
    
    def get_structural_hash(self, include_text: bool = False) -> str:
        """Get hash representing structural signature."""
        components = [self.type_name]
        if include_text:
            components.append(self.text[:50])  # Limit text for consistent hashing
        
        for child in self.children:
            components.append(child.get_structural_hash(include_text))
        
        content = '|'.join(components)
        return hashlib.md5(content.encode()).hexdigest()
    
    def similarity_score(self, other: TSNode) -> float:
        """Calculate structural similarity score (0.0 to 1.0)."""
        if self.type_name != other.type_name:
            return 0.0
        
        # Compare children
        max_children = max(len(self.children), len(other.children))
        if max_children == 0:
            return 1.0
        
        matching_children = 0
        for i in range(min(len(self.children), len(other.children))):
            if self.children[i].type_name == other.children[i].type_name:
                matching_children += 1
        
        child_similarity = matching_children / max_children
        
        # Text similarity (simplified)
        text_similarity = 1.0 if self.text.strip() == other.text.strip() else 0.5
        
        return (child_similarity + text_similarity) / 2
    
    def find_similar_nodes(self, threshold: float = 0.8) -> List[TSNode]:
        """Find similar nodes in the tree."""
        similar = []
        for node in self.descendants():
            if node != self and self.similarity_score(node) >= threshold:
                similar.append(node)
        return similar
    
    # ========================================================================
    # Enhanced Registry Management
    # ========================================================================
    
    @classmethod
    def register_subclasses(cls,
                          mapping: Dict[str, type[TSNode]],
                          metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        """Enhanced registration with metadata support."""
        cls._registry.update(mapping)
        
        for type_name, node_class in mapping.items():
            cls._reverse_registry[node_class] = type_name
        
        if metadata:
            cls._registry_metadata.update(metadata)
    
    @classmethod
    def get_registered_types(cls) -> Dict[str, type[TSNode]]:
        """Get all registered node types."""
        return cls._registry.copy()
    
    @classmethod
    def get_type_metadata(cls, type_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for registered type."""
        return cls._registry_metadata.get(type_name)
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached metrics and computations."""
        cls._metrics_cache.clear()
    
    # ========================================================================
    # Factory Method (Enhanced)
    # ========================================================================
    
    @classmethod
    def from_tree_sitter(cls, node, text_bytes: bytes) -> TSNode:
        """Convert tree-sitter node to TSNode with enhanced features."""
        sub_cls = cls._registry.get(node.type, cls)
        
        children = []
        child_counter = 0
        for child in node.children:
            child_node = cls.from_tree_sitter(child, text_bytes)
            
            field_name = None
            if hasattr(node, "field_name_for_child"):
                try:
                    field_name = node.field_name_for_child(child_counter)
                    child_counter += 1
                except:
                    pass
            
            if field_name:
                child_node = child_node.model_copy(update={"field_name": field_name})
            children.append(child_node)
        
        text = text_bytes[node.start_byte:node.end_byte].decode(errors="ignore")
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
    
    # ========================================================================
    # Display Methods (Enhanced)
    # ========================================================================
    
    def pretty(self, indent: int = 0, indent_str: str = "  ", max_text: int = 40,
              show_metrics: bool = False) -> str:
        """Enhanced pretty printing with optional metrics."""
        ind = indent_str * indent
        nxt = indent_str * (indent + 1)
        
        class_name = self.__class__.__name__
        
        scalar_parts = []
        
        if show_metrics:
            scalar_parts.extend([
                f"depth={self.max_depth}",
                f"nodes={self.descendants_count}",
                f"complexity={self.calculate_complexity()}"
            ])
        
        if max_text and self.text.strip():
            snippet = self.text.strip().replace("\n", " ")
            if len(snippet) > max_text:
                snippet = snippet[:max_text - 1] + "…"
            scalar_parts.append(f"text={snippet!r}")
        
        if self.field_name:
            scalar_parts.append(f"field={self.field_name!r}")
        
        if self.children:
            child_strs = [
                c.pretty(indent + 2, indent_str, max_text, show_metrics)
                for c in self.children[:5]
            ]
            if len(self.children) > 5:
                child_strs.append(f"{nxt}... ({len(self.children) - 5} more)")
            children_block = "children=[\n" + ",\n".join(child_strs) + f"\n{nxt}]"
            scalar_parts.append(children_block)
        
        joined = ",\n".join(f"{nxt}{part}" for part in scalar_parts)
        return f"{ind}{class_name}(\n{joined}\n{ind})"
    
    def __str__(self) -> str:
        return self.pretty()
    
    def __repr__(self) -> str:
        return f"TSNode({self.type_name!r}, nodes={self.descendants_count}, hash={self.structural_hash[:8]})"
    
    def __hash__(self) -> int:
        """Hash based on structural signature."""
        return hash(self.structural_hash)
    
    # Backward compatibility
    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        """Backward compatible dict method."""
        return self.export_dict(*args, **kwargs)
