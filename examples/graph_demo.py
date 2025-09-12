#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.11",
#     "tree-sitter>=0.23",
#     "tree-sitter-python>=0.23.6",
#     "rustworkx>=0.14.0",
# ]
# ///

"""Graph operations demonstration."""

from pydantree import parse_python, NodeGroup

try:
    from pydantree.graph import GraphBuilder, GraphAnalyzer, PatternMatcher

    HAS_GRAPH = True
except ImportError:
    HAS_GRAPH = False

SAMPLE_CODE = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

class Counter:
    def __init__(self):
        self.count = 0
    
    def increment(self):
        self.count += 1
        return self.count
"""

PATTERN_CODE = """
def example():
    pass
"""


def main():
    print("=== Graph Operations Demo ===\n")

    if not HAS_GRAPH:
        print("⚠️  Graph operations require rustworkx")
        print("   Install with: pip install rustworkx")
        return

    # Parse code
    module = parse_python(SAMPLE_CODE)
    nodegroup = NodeGroup.from_tree(module.node)

    # Build graph
    builder = GraphBuilder(nodegroup)
    graph = builder.to_graph(directed=True, include_siblings=False)

    print(f"Graph nodes: {len(graph.nodes())}")
    print(f"Graph edges: {len(graph.edges())}")

    # Analyze graph
    analyzer = GraphAnalyzer(graph)
    metrics = analyzer.graph_metrics()

    print(f"\nGraph metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    # Find connected components
    components = analyzer.connected_components()
    print(f"\nConnected components: {len(components)}")

    # Pattern matching demo - use a simple function pattern
    print(f"\n=== Pattern Matching ===")

    # Create a simple pattern that should match function definitions
    pattern_module = parse_python(PATTERN_CODE)

    # Get just the function definition nodes for pattern
    pattern_group = NodeGroup.from_tree(pattern_module.node)
    pattern_functions = pattern_group.filter_type("function_definition")

    # Get function definitions from target too
    target_functions = nodegroup.filter_type("function_definition")

    if len(pattern_functions) > 0 and len(target_functions) > 0:
        # Build simpler graphs with just function structures
        pattern_graph = GraphBuilder(pattern_functions).to_graph(directed=True)
        target_graph = GraphBuilder(target_functions).to_graph(directed=True)

        # More lenient matching
        def lenient_node_matcher(pattern_node, target_node):
            return True  # Match any function to any function

        matcher = PatternMatcher(pattern_graph)
        matches = matcher.find_matches(
            target_graph
        )  # , node_matcher=lenient_node_matcher)

        print(f"Function pattern matches: {len(matches)}")

        print(f"Pattern functions: {len(pattern_functions)}")
        for match in pattern_functions:
            print(f"  Match found: {match}")
        print(f"Target functions: {len(target_functions)}")
        for match in target_functions:
            print(f"  Match found: {match}")
    else:
        print("No function definitions found for pattern matching")


if __name__ == "__main__":
    main()
