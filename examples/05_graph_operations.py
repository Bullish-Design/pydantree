# examples/05_graph_operations.py

"""Graph operations and pattern matching examples."""

from pathlib import Path
from pydantree import Parser, from_tree
from pydantree.graph.builder import GraphBuilder, PatternMatcher, GraphAnalyzer
from pydantree.processing.collections import NodeGroup

# Example 1: Convert AST to graph
def ast_to_graph():
    """Convert AST to graph representation."""
    
    parser = Parser.for_language("python")
    code = '''
def calculate_total(items):
    total = 0
    for item in items:
        if item.valid:
            total += item.value
        else:
            print(f"Invalid item: {item}")
    return total

class ShoppingCart:
    def __init__(self):
        self.items = []
    
    def add_item(self, item):
        self.items.append(item)
    
    def get_total(self):
        return calculate_total(self.items)
'''
    
    ast_root = parser.parse(code)
    nodegroup = from_tree(ast_root)
    
    # Create graph builder
    builder = GraphBuilder(nodegroup)
    
    # Build basic directed graph
    graph = builder.to_graph(
        directed=True,
        include_siblings=True,
        include_control_flow=True,
        include_data_flow=True
    )
    
    print(f"Graph created with {len(graph.nodes())} nodes and {len(graph.edges())} edges")
    
    # Analyze node types
    node_types = {}
    for node_data in graph.nodes():
        type_name = node_data.get('type_name', 'unknown')
        node_types[type_name] = node_types.get(type_name, 0) + 1
    
    print("\nNode type distribution:")
    for type_name, count in sorted(node_types.items()):
        print(f"  {type_name}: {count}")
    
    # Analyze edge types
    edge_types = {}
    for edge_data in graph.edges():
        edge_type = edge_data.get('edge_type', 'unknown')
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
    
    print("\nEdge type distribution:")
    for edge_type, count in edge_types.items():
        print(f"  {edge_type}: {count}")
    
    return graph, builder

# Example 2: Pattern matching in graphs
def pattern_matching():
    """Find patterns in AST graphs."""
    
    parser = Parser.for_language("python")
    
    # Target code to search in
    target_code = '''
def process_user(user_id):
    user = get_user(user_id)
    if user is None:
        return None
    
    if user.active:
        return user
    else:
        return None

def process_order(order_id):
    order = get_order(order_id)
    if order is None:
        return None
    
    if order.valid:
        return order
    else:
        return None

def simple_add(a, b):
    return a + b

def complex_calculation(data):
    result = 0
    for item in data:
        result += item * 2
    return result
'''
    
    # Pattern: if-else with None return
    pattern_code = '''
if condition:
    return value
else:
    return None
'''
    
    # Parse both
    target_ast = parser.parse(target_code)
    pattern_ast = parser.parse(pattern_code)
    
    # Create graphs
    target_nodes = from_tree(target_ast)
    pattern_nodes = from_tree(pattern_ast)
    
    target_builder = GraphBuilder(target_nodes)
    pattern_builder = GraphBuilder(pattern_nodes)
    
    target_graph = target_builder.to_graph(directed=True)
    pattern_graph = pattern_builder.to_graph(directed=True)
    
    # Find if-statement patterns
    if_statements = target_nodes.filter_type("if_statement")
    print(f"Found {len(if_statements)} if statements to analyze")
    
    # Create pattern matcher
    matcher = PatternMatcher(pattern_graph)
    
    # Find matches
    matches = matcher.find_matches(target_graph, max_matches=10)
    print(f"Found {len(matches)} pattern matches")
    
    # Analyze matches
    for i, match in enumerate(matches):
        print(f"\nMatch {i + 1}:")
        for pattern_idx, target_idx in match.items():
            pattern_node = pattern_graph.get_node_data(pattern_idx)
            target_node = target_graph.get_node_data(target_idx)
            
            pattern_type = pattern_node.get('type_name', 'unknown')
            target_type = target_node.get('type_name', 'unknown')
            
            print(f"  {pattern_type} -> {target_type}")
    
    return matches, target_graph, pattern_graph

# Example 3: Graph analysis and metrics
def graph_analysis():
    """Analyze graph structure and compute metrics."""
    
    parser = Parser.for_language("python")
    code = '''
class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = []
    
    def add_node(self, node_id, data=None):
        self.nodes[node_id] = data or {}
    
    def add_edge(self, from_id, to_id, weight=1):
        self.edges.append({
            'from': from_id,
            'to': to_id,
            'weight': weight
        })
    
    def get_neighbors(self, node_id):
        neighbors = []
        for edge in self.edges:
            if edge['from'] == node_id:
                neighbors.append(edge['to'])
        return neighbors
    
    def dijkstra(self, start, end):
        distances = {node: float('inf') for node in self.nodes}
        distances[start] = 0
        visited = set()
        
        while visited != set(self.nodes.keys()):
            current = min(
                (node for node in self.nodes if node not in visited),
                key=lambda x: distances[x]
            )
            visited.add(current)
            
            for neighbor in self.get_neighbors(current):
                edge_weight = next(
                    edge['weight'] for edge in self.edges
                    if edge['from'] == current and edge['to'] == neighbor
                )
                
                new_distance = distances[current] + edge_weight
                if new_distance < distances[neighbor]:
                    distances[neighbor] = new_distance
        
        return distances[end]
'''
    
    ast_root = parser.parse(code)
    nodegroup = from_tree(ast_root)
    
    builder = GraphBuilder(nodegroup)
    graph = builder.to_graph(
        directed=True,
        include_control_flow=True,
        include_data_flow=True
    )
    
    # Create analyzer
    analyzer = GraphAnalyzer(graph)
    
    # Compute graph metrics
    metrics = analyzer.compute_graph_metrics()
    print("Graph Metrics:")
    print(f"  Nodes: {metrics['num_nodes']}")
    print(f"  Edges: {metrics['num_edges']}")
    print(f"  Density: {metrics['density']:.3f}")
    print(f"  Unique types: {metrics['unique_types']}")
    
    if 'diameter' in metrics and metrics['diameter']:
        print(f"  Diameter: {metrics['diameter']:.1f}")
    
    # Compute centrality metrics
    centrality = analyzer.compute_centrality_metrics()
    
    # Find most central nodes
    if centrality:
        by_betweenness = sorted(
            centrality.items(),
            key=lambda x: x[1].get('betweenness', 0),
            reverse=True
        )[:5]
        
        print("\nMost central nodes (by betweenness):")
        for node_idx, metrics in by_betweenness:
            node_data = graph.get_node_data(node_idx)
            type_name = node_data.get('type_name', 'unknown')
            text_preview = node_data.get('text_preview', '')[:20]
            betweenness = metrics.get('betweenness', 0)
            
            print(f"  {type_name}: {text_preview}... (centrality: {betweenness:.3f})")
    
    # Detect patterns
    patterns = analyzer.detect_structural_patterns()
    print(f"\nStructural Patterns:")
    print(f"  Cycles: {len(patterns.get('cycles', []))}")
    print(f"  Components: {len(patterns.get('strongly_connected', []))}")
    
    # Find communities
    communities = analyzer.find_communities()
    print(f"  Communities: {len(communities)}")
    
    return analyzer, metrics

# Example 4: Custom graph transformations
def custom_graph_operations():
    """Custom graph transformations and filtering."""
    
    parser = Parser.for_language("python")
    code = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)

def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

def sieve_of_eratosthenes(limit):
    primes = [True] * (limit + 1)
    primes[0] = primes[1] = False
    
    for i in range(2, int(limit**0.5) + 1):
        if primes[i]:
            for j in range(i*i, limit + 1, i):
                primes[j] = False
    
    return [i for i in range(limit + 1) if primes[i]]
'''
    
    ast_root = parser.parse(code)
    nodegroup = from_tree(ast_root)
    
    # Custom node filter for complex expressions
    def is_complex_expression(node):
        """Filter for complex expressions."""
        complexity_indicators = {
            'binary_operator', 'call', 'subscript',
            'attribute', 'list_comprehension'
        }
        return node.type_name in complexity_indicators
    
    # Custom edge predicate for function calls
    def calls_function(node1, node2):
        """Check if node1 calls a function defined in node2."""
        if (node1.type_name == 'call' and 
            node2.type_name == 'function_definition'):
            # Simple heuristic: check if function name appears in call
            if hasattr(node1, 'children') and hasattr(node2, 'children'):
                call_text = node1.text
                func_name_node = node2.child_by_field_name('name')
                if func_name_node:
                    return func_name_node.text in call_text
        return False
    
    builder = GraphBuilder(nodegroup)
    
    # Build graph with custom filters and edges
    graph = builder.to_graph(
        directed=True,
        node_filter=is_complex_expression,
        edge_predicate=calls_function,
        include_control_flow=True
    )
    
    print(f"Filtered graph: {len(graph.nodes())} nodes, {len(graph.edges())} edges")
    
    # Analyze the filtered graph
    analyzer = GraphAnalyzer(graph)
    
    # Custom analysis: find recursive patterns
    recursive_calls = 0
    for edge_data in graph.edges():
        if edge_data.get('edge_type') == 'custom':
            recursive_calls += 1
    
    print(f"Potential recursive calls: {recursive_calls}")
    
    # Get subgraphs for each function
    functions = ast_root.find_all_by_type("function_definition")
    print(f"\nFunction complexity (in filtered graph):")
    
    for func in functions:
        func_name_node = func.child_by_field_name("name")
        if func_name_node:
            func_name = func_name_node.text
            
            # Find nodes belonging to this function
            func_nodes = []
            for node_idx in graph.node_indices():
                node_data = graph.get_node_data(node_idx)
                metadata = node_data.get('metadata')
                if metadata and func.start_byte <= metadata.node.start_byte <= func.end_byte:
                    func_nodes.append(node_idx)
            
            if func_nodes:
                subgraph = analyzer.get_subgraph(func_nodes)
                print(f"  {func_name}: {len(subgraph.nodes())} complex expressions")
    
    return graph, analyzer

# Example 5: Graph export and visualization
def graph_export():
    """Export graphs for visualization."""
    
    parser = Parser.for_language("python")
    code = '''
class BinaryTree:
    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None
    
    def insert(self, value):
        if value < self.value:
            if self.left is None:
                self.left = BinaryTree(value)
            else:
                self.left.insert(value)
        else:
            if self.right is None:
                self.right = BinaryTree(value)
            else:
                self.right.insert(value)
    
    def search(self, value):
        if value == self.value:
            return True
        elif value < self.value and self.left:
            return self.left.search(value)
        elif value > self.value and self.right:
            return self.right.search(value)
        return False
'''
    
    ast_root = parser.parse(code)
    nodegroup = from_tree(ast_root)
    
    builder = GraphBuilder(nodegroup)
    graph = builder.to_graph(
        directed=True,
        include_siblings=False,  # Cleaner visualization
        include_control_flow=True
    )
    
    # Export to DOT format for Graphviz
    def export_to_dot(graph, output_path: Path):
        """Export graph to DOT format."""
        lines = ["digraph AST {"]
        lines.append("  rankdir=TB;")
        lines.append("  node [shape=box, style=filled];")
        
        # Add nodes
        for node_idx in graph.node_indices():
            node_data = graph.get_node_data(node_idx)
            type_name = node_data.get('type_name', 'unknown')
            text_preview = node_data.get('text_preview', '')[:15]
            
            # Escape quotes and newlines
            label = f"{type_name}\\n{text_preview}".replace('"', '\\"').replace('\n', '\\n')
            
            # Color by type
            color = {
                'function_definition': 'lightblue',
                'class_definition': 'lightgreen',
                'if_statement': 'yellow',
                'for_statement': 'orange',
                'identifier': 'lightgray'
            }.get(type_name, 'white')
            
            lines.append(f'  {node_idx} [label="{label}", fillcolor="{color}"];')
        
        # Add edges
        for source, target, edge_data in graph.edge_list():
            edge_type = edge_data.get('edge_type', 'unknown')
            
            # Style by edge type
            style = {
                'parent-child': 'solid',
                'control-flow': 'dashed',
                'data-flow': 'dotted',
                'sibling': 'bold'
            }.get(edge_type, 'solid')
            
            color = {
                'parent-child': 'black',
                'control-flow': 'blue',
                'data-flow': 'red',
                'sibling': 'green'
            }.get(edge_type, 'gray')
            
            lines.append(f'  {source} -> {target} [style="{style}", color="{color}"];')
        
        lines.append("}")
        
        output_path.write_text('\n'.join(lines))
        print(f"Graph exported to {output_path}")
    
    # Export to file
    output_path = Path("ast_graph.dot")
    export_to_dot(graph, output_path)
    
    # Generate simple statistics
    analyzer = GraphAnalyzer(graph)
    metrics = analyzer.compute_graph_metrics()
    
    print(f"\nGraph Statistics:")
    print(f"  Nodes: {metrics['num_nodes']}")
    print(f"  Edges: {metrics['num_edges']}")
    print(f"  Types: {metrics['unique_types']}")
    
    return graph, output_path

if __name__ == "__main__":
    print("=== Graph Operations Examples ===\n")
    
    print("1. AST to graph conversion:")
    ast_to_graph()
    
    print("\n2. Pattern matching:")
    pattern_matching()
    
    print("\n3. Graph analysis:")
    graph_analysis()
    
    print("\n4. Custom graph operations:")
    custom_graph_operations()
    
    print("\n5. Graph export:")
    graph_export()
