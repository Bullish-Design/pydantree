# examples/01_basic_usage.py

"""Basic usage examples for Pydantree library."""

from pathlib import Path
from pydantree import parse_file, Parser, TSNode, nodes, from_tree

# Example 1: Parse a single Python file
def parse_single_file():
    """Parse a single Python file and explore the AST."""
    file_path = f"/home/andrew/Documents/Projects/pydantree/examples/example.py" 
    # Parse using auto-detection
    file_path = Path(file_path)
    root_node = parse_file(file_path)
    
    print(f"Root node type: {root_node.type_name}")
    print(f"File spans {root_node.line_count} lines")
    print(f"Contains {len(list(root_node.descendants()))} total nodes")
    
    # Access basic properties
    print(f"Byte range: {root_node.start_byte}-{root_node.end_byte}")
    print(f"Structural hash: {root_node.structural_hash}")
    
    return root_node

# Example 2: Parse with explicit language
def parse_with_language():
    """Parse code with explicit language specification."""
    
    # Create language-specific parser
    parser = Parser.for_language("python")
    
    # Parse inline code
    code = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

class Calculator:
    def add(self, a, b):
        return a + b
'''
    
    root_node = parser.parse(code)
    
    # Find specific node types
    functions = root_node.find_all_by_type("function_definition")
    classes = root_node.find_all_by_type("class_definition")
    
    print(f"Found {len(functions)} functions and {len(classes)} classes")
    
    for func in functions:
        func_name = func.child_by_field_name("name")
        if func_name:
            print(f"Function: {func_name.text}")
    
    return root_node, functions, classes

# Example 3: Working with NodeGroups
def working_with_nodegroups():
    """Demonstrate NodeGroup collection operations."""
    
    parser = Parser.for_language("python")
    code = '''
x = 10
y = "hello"
z = [1, 2, 3]

def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result

class DataProcessor:
    def __init__(self):
        self.data = []
    
    def add_item(self, item):
        self.data.append(item)
'''
    
    root_node = parser.parse(code)
    
    # Create NodeGroup from entire tree
    all_nodes = from_tree(root_node)
    print(f"Total nodes in tree: {len(all_nodes)}")
    
    # Filter operations
    identifiers = all_nodes.filter_type("identifier")
    strings = all_nodes.filter_type("string")
    
    print(f"Identifiers: {len(identifiers)}")
    print(f"String literals: {len(strings)}")
    
    # Custom filtering with predicates
    long_identifiers = identifiers.where(lambda node: len(node.text) > 5)
    print(f"Long identifiers (>5 chars): {len(long_identifiers)}")
    
    # Set operations
    literals = all_nodes.filter_type({"string", "integer", "float"})
    print(f"All literals: {len(literals)}")
    
    return all_nodes, identifiers, literals

# Example 4: Node analysis and metrics
def analyze_nodes():
    """Analyze nodes and extract metrics."""
    
    parser = Parser.for_language("python")
    code = '''
def complex_function(data, options=None):
    """Process data with various options."""
    if options is None:
        options = {}
    
    results = []
    for item in data:
        if isinstance(item, dict):
            processed = item.copy()
            if "transform" in options:
                for key, value in processed.items():
                    if isinstance(value, str):
                        processed[key] = value.upper()
                    elif isinstance(value, (int, float)):
                        processed[key] = value * 2
            results.append(processed)
        elif isinstance(item, str):
            if "prefix" in options:
                results.append(options["prefix"] + item)
            else:
                results.append(item.upper())
        else:
            results.append(str(item))
    
    return results
'''
    
    root_node = parser.parse(code)
    
    # Get comprehensive metrics
    metrics = root_node.get_metrics()
    print("Code Metrics:")
    print(f"  Total nodes: {metrics['total_nodes']}")
    print(f"  Lines: {metrics['line_count']}")
    print(f"  Bytes: {metrics['byte_length']}")
    print(f"  Cyclomatic complexity: {metrics['cyclomatic_complexity']}")
    print(f"  Type distribution: {metrics['type_distribution']}")
    
    # Find the function definition
    functions = root_node.find_all_by_type("function_definition")
    if functions:
        func = functions[0]
        func_metrics = func.get_metrics()
        print(f"\nFunction complexity: {func_metrics['cyclomatic_complexity']}")
    
    return metrics

if __name__ == "__main__":
    print("=== Basic Pydantree Usage Examples ===\n")
    
    print("1. Parse single file:")
    parse_single_file()  # Uncomment if you have example.py
    
    print("\n2. Parse with explicit language:")
    parse_with_language()
    
    print("\n3. Working with NodeGroups:")
    working_with_nodegroups()
    
    print("\n4. Analyze nodes:")
    analyze_nodes()
