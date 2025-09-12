# Graph Operations - AST Analysis and Pattern Matching

Graph operations convert NodeGroup collections into rustworkx graphs for advanced analysis, pattern matching, and structural algorithms.

## Core Classes

### GraphBuilder - NodeGroup to Graph Conversion

```python
class GraphBuilder:
    def __init__(self, nodegroup: NodeGroup)
    
    def to_graph(
        self,
        directed: bool = True,
        include_siblings: bool = False,
        edge_predicate: Optional[Callable[[TSNode, TSNode], bool]] = None,
        node_attrs: Optional[Callable[[TSNode], Dict]] = None,
        edge_attrs: Optional[Callable[[TSNode, TSNode], Dict]] = None,
    ) -> Union[rx.PyDiGraph, rx.PyGraph]
```

### PatternMatcher - VF2 Isomorphism

```python
class PatternMatcher:
    def __init__(self, pattern_graph: Union[rx.PyDiGraph, rx.PyGraph])
    
    def find_matches(
        self,
        target_graph: Union[rx.PyDiGraph, rx.PyGraph],
        node_matcher: Optional[Callable] = None,
        edge_matcher: Optional[Callable] = None,
    ) -> List[Dict[int, int]]
```

### GraphAnalyzer - Algorithm Suite

```python
class GraphAnalyzer:
    def __init__(self, graph: Union[rx.PyDiGraph, rx.PyGraph])
    
    def find_paths(self, source: int, target: int) -> List[List[int]]
    def shortest_path(self, source: int, target: int) -> Optional[List[int]]
    def find_cycles(self) -> List[List[int]]
    def connected_components(self) -> List[List[int]]
    def centrality_scores(self) -> Dict[int, float]
    def graph_metrics(self) -> Dict[str, Any]
```

## Basic Graph Construction

### Simple Tree Graphs

```python
from pydantree import parse_python, NodeGroup
from pydantree.graph import GraphBuilder

code = """
def process_data(items):
    for item in items:
        if item > 10:
            print(f"Large: {item}")
    return len(items)
"""

module = parse_python(code)
nodegroup = NodeGroup.from_tree(module.node)

# Build basic tree graph
builder = GraphBuilder(nodegroup)
graph = builder.to_graph(directed=True)

print(f"Nodes: {len(graph.nodes())}")
print(f"Edges: {len(graph.edges())}")
```

### Enhanced Graphs with Siblings

```python
# Include sibling relationships
sibling_graph = builder.to_graph(
    directed=True,
    include_siblings=True
)

print(f"With siblings - Edges: {len(sibling_graph.edges())}")
```

### Custom Edge Predicates

```python
def semantic_relationship(node1: TSNode, node2: TSNode) -> bool:
    """Define custom semantic relationships."""
    # Variables used in same scope
    if (node1.type_name == "identifier" and 
        node2.type_name == "identifier" and
        node1.text == node2.text):
        return True
    
    # Function calls to function definitions
    if (node1.type_name == "call" and 
        node2.type_name == "function_definition"):
        call_name = node1.child_by_field_name("function")
        func_name = node2.child_by_field_name("name")
        return call_name and func_name and call_name.text == func_name.text
    
    return False

semantic_graph = builder.to_graph(
    directed=True,
    edge_predicate=semantic_relationship
)
```

## Advanced Graph Analysis

### Centrality and Importance

```python
from pydantree.graph import GraphAnalyzer

analyzer = GraphAnalyzer(graph)

# Find most important nodes
centrality = analyzer.centrality_scores()
sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)

print("Most central nodes:")
for node_idx, score in sorted_nodes[:5]:
    node = builder.index_to_node[node_idx]
    print(f"  {node.type_name}: {node.text[:30]} (score: {score:.3f})")
```

### Path Analysis

```python
# Find paths between specific nodes
function_nodes = [idx for idx, node in builder.index_to_node.items() 
                  if node.type_name == "function_definition"]

if len(function_nodes) >= 2:
    paths = analyzer.find_paths(function_nodes[0], function_nodes[1])
    print(f"Paths between functions: {len(paths)}")
    
    # Shortest path
    shortest = analyzer.shortest_path(function_nodes[0], function_nodes[1])
    if shortest:
        print(f"Shortest path length: {len(shortest)}")
```

### Structural Metrics

```python
metrics = analyzer.graph_metrics()
print("Graph Metrics:")
for key, value in metrics.items():
    print(f"  {key}: {value}")

# Connected components analysis
components = analyzer.connected_components()
print(f"Connected components: {len(components)}")
for i, component in enumerate(components):
    print(f"  Component {i}: {len(component)} nodes")
```

## Pattern Matching

### Simple Pattern Detection

```python
from pydantree.graph import PatternMatcher, build_pattern_graph

# Define a simple pattern
pattern_code = """
def example():
    pass
"""

pattern_module = parse_python(pattern_code)
pattern_nodes = NodeGroup.from_tree(pattern_module.node).filter_type("function_definition")
pattern_graph = build_pattern_graph(list(pattern_nodes))

# Find matches in target
target_functions = nodegroup.filter_type("function_definition")
target_graph = GraphBuilder(target_functions).to_graph()

matcher = PatternMatcher(pattern_graph)
matches = matcher.find_matches(target_graph)

print(f"Pattern matches: {len(matches)}")
```

### Complex Pattern Matching

```python
# More complex pattern: function with specific structure
complex_pattern = """
def template(param):
    if condition:
        return value
"""

def enhanced_node_matcher(pattern_node: dict, target_node: dict) -> bool:
    """Custom node matching logic."""
    pattern_meta = pattern_node.get("metadata")
    target_meta = target_node.get("metadata")
    
    if not (pattern_meta and target_meta):
        return True
    
    # Match by structure, not exact text
    if pattern_meta.type_name != target_meta.type_name:
        return False
    
    # Allow flexible identifier matching
    if pattern_meta.type_name == "identifier":
        return True  # Any identifier matches
        
    return pattern_meta.type_name == target_meta.type_name

matches = matcher.find_matches(
    target_graph,
    node_matcher=enhanced_node_matcher
)
```

### Anti-Pattern Detection

```python
def find_anti_patterns(nodegroup: NodeGroup) -> dict:
    """Find common code anti-patterns using graph analysis."""
    
    graph = GraphBuilder(nodegroup).to_graph(directed=True, include_siblings=True)
    analyzer = GraphAnalyzer(graph)
    
    anti_patterns = {}
    
    # Deep nesting (high path lengths)
    for node_idx in graph.node_indices():
        descendants = list(graph.successor_indices(node_idx))
        if len(descendants) > 10:  # Arbitrary threshold
            node = nodegroup.nodes[node_idx] if node_idx < len(nodegroup.nodes) else None
            anti_patterns[f"deep_nesting_{node_idx}"] = {
                "type": "deep_nesting",
                "node": node.text[:50] if node else "unknown",
                "depth": len(descendants)
            }
    
    # Cycles (potential infinite loops or circular dependencies)
    cycles = analyzer.find_cycles()
    for i, cycle in enumerate(cycles):
        anti_patterns[f"cycle_{i}"] = {
            "type": "cycle",
            "length": len(cycle),
            "nodes": cycle
        }
    
    return anti_patterns
```

## Specialized Graph Types

### Call Graphs

```python
def build_call_graph(module_nodegroup: NodeGroup) -> rx.PyDiGraph:
    """Build function call relationship graph."""
    
    # Get all functions and calls
    functions = module_nodegroup.filter_type("function_definition")
    calls = module_nodegroup.filter_type("call")
    
    # Create mapping from names to function nodes
    func_map = {}
    for func in functions:
        name_node = func.child_by_field_name("name")
        if name_node:
            func_map[name_node.text] = func
    
    def is_call_relationship(call_node: TSNode, func_node: TSNode) -> bool:
        call_func = call_node.child_by_field_name("function")
        func_name = func_node.child_by_field_name("name")
        return (call_func and func_name and 
                call_func.text == func_name.text)
    
    combined = NodeGroup(list(functions) + list(calls))
    return GraphBuilder(combined).to_graph(
        directed=True,
        edge_predicate=is_call_relationship
    )

call_graph = build_call_graph(nodegroup)
call_analyzer = GraphAnalyzer(call_graph)

# Find most called functions
call_centrality = call_analyzer.centrality_scores()
```

### Dependency Graphs

```python
def build_import_graph(modules: List[PyModule]) -> rx.PyDiGraph:
    """Build module dependency graph."""
    
    all_imports = []
    module_names = []
    
    for module in modules:
        module_names.append(module.file_path)  # Assuming file_path attribute
        imports = module.imports()
        all_imports.extend(imports.all())
    
    def creates_dependency(import_node: TSNode, module_node: TSNode) -> bool:
        imported_name = import_node.module_name()
        return imported_name in module_node.text
    
    # Build graph of module dependencies
    combined_nodes = NodeGroup(all_imports + [m.node for m in modules])
    return GraphBuilder(combined_nodes).to_graph(
        edge_predicate=creates_dependency
    )
```

### Control Flow Graphs

```python
def build_control_flow_graph(function_node: TSNode) -> rx.PyDiGraph:
    """Build control flow graph for a function."""
    
    body = function_node.child_by_field_name("body")
    if not body:
        return rx.PyDiGraph()
    
    statements = NodeGroup(body.children)
    
    def control_flow_edge(stmt1: TSNode, stmt2: TSNode) -> bool:
        # Sequential statements
        stmt1_end = stmt1.end_byte
        stmt2_start = stmt2.start_byte
        return abs(stmt2_start - stmt1_end) < 10  # Approximate adjacency
    
    return GraphBuilder(statements).to_graph(
        directed=True,
        edge_predicate=control_flow_edge
    )
```

## Performance Optimization

### Graph Caching

```python
class CachedGraphBuilder:
    def __init__(self):
        self.cache = {}
    
    def get_graph(self, nodegroup: NodeGroup, config: tuple) -> rx.PyDiGraph:
        cache_key = (id(nodegroup), config)
        if cache_key not in self.cache:
            builder = GraphBuilder(nodegroup)
            self.cache[cache_key] = builder.to_graph(*config)
        return self.cache[cache_key]

cached_builder = CachedGraphBuilder()
graph = cached_builder.get_graph(nodegroup, (True, False))  # directed, no siblings
```

### Incremental Graph Updates

```python
def update_graph_incrementally(graph: rx.PyDiGraph, 
                             added_nodes: List[TSNode],
                             removed_nodes: List[TSNode]) -> rx.PyDiGraph:
    """Update graph with minimal recomputation."""
    
    # Remove nodes and their edges
    for node in removed_nodes:
        # Find and remove node index
        pass  # Implementation depends on tracking node->index mapping
    
    # Add new nodes and edges
    for node in added_nodes:
        node_idx = graph.add_node({"node": node})
        # Add edges based on relationships
        
    return graph
```

## Integration Examples

### With Views Layer

```python
def analyze_class_complexity(module: PyModule) -> dict:
    """Analyze class complexity using graph metrics."""
    
    results = {}
    
    for cls in module.classes():
        # Build method interaction graph
        methods = cls.methods().to_nodegroup()
        method_graph = GraphBuilder(methods).to_graph(
            edge_predicate=lambda m1, m2: m1.name() in m2.text  # Method calls
        )
        
        analyzer = GraphAnalyzer(method_graph)
        metrics = analyzer.graph_metrics()
        
        results[cls.name()] = {
            "method_count": len(methods),
            "interaction_density": metrics["density"],
            "complexity_score": metrics["num_edges"] / max(metrics["num_nodes"], 1)
        }
    
    return results
```

### With NodeGroup Operations

```python
# Combine graph analysis with lazy collections
def find_hotspots(nodegroup: NodeGroup) -> NodeGroup:
    """Find nodes that are central in multiple graph representations."""
    
    # Build different graph views
    tree_graph = GraphBuilder(nodegroup).to_graph(directed=True)
    sibling_graph = GraphBuilder(nodegroup).to_graph(include_siblings=True)
    
    # Get centrality from both
    tree_centrality = GraphAnalyzer(tree_graph).centrality_scores()
    sibling_centrality = GraphAnalyzer(sibling_graph).centrality_scores()
    
    # Find nodes with high centrality in both
    hotspot_indices = []
    for idx in tree_centrality:
        if (tree_centrality.get(idx, 0) > 0.1 and 
            sibling_centrality.get(idx, 0) > 0.1):
            hotspot_indices.append(idx)
    
    # Convert back to NodeGroup
    hotspot_nodes = [GraphBuilder(nodegroup).index_to_node[idx] 
                     for idx in hotspot_indices]
    return NodeGroup(hotspot_nodes)
```

Graph operations enable sophisticated structural analysis and pattern detection that goes beyond simple tree traversal.