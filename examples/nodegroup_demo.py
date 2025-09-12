#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.11",
#     "tree-sitter>=0.23",
#     "tree-sitter-python>=0.23.6",
# ]
# ///

"""NodeGroup operations demonstration."""

from pydantree import parse_python, NodeGroup, TypeSelector, TextSelector

SAMPLE_CODE = '''
def calculate(x, y):
    result = x + y
    print(f"Result: {result}")
    return result

class Math:
    def add(self, a, b):
        return a + b
    
    def subtract(self, a, b):
        return a - b

def main():
    calc = Math()
    print(calc.add(5, 3))
'''

def main():
    print("=== NodeGroup Demo ===\n")
    
    # Parse and create NodeGroup
    module = parse_python(SAMPLE_CODE)
    all_nodes = NodeGroup.from_tree(module.node)
    print(f"Total nodes in AST: {len(all_nodes)}")
    
    # Filter by type
    identifiers = all_nodes.filter_type("identifier")
    print(f"Identifiers: {len(identifiers)}")
    
    # Filter by text content
    print_calls = all_nodes.filter_text("print", exact=False)
    print(f"Nodes containing 'print': {len(print_calls)}")
    
    # Set operations
    functions = all_nodes.filter_type("function_definition")
    classes = all_nodes.filter_type("class_definition")
    definitions = functions.union(classes)
    print(f"Function + class definitions: {len(definitions)}")
    
    # Chain filters
    return_stmts = all_nodes.filter_type("return_statement")
    print(f"Return statements: {len(return_stmts)}")
    
    # Group by type
    grouped = all_nodes.groupby(lambda n: n.type_name)
    print(f"\nNode types and counts:")
    for type_name, group in grouped.items():
        if len(group) > 1:
            print(f"  {type_name}: {len(group)}")
    
    # Find specific patterns
    binary_ops = all_nodes.filter_type("binary_operator")
    print(f"\nBinary operators: {len(binary_ops)}")
    for op in binary_ops:
        print(f"  {op.text.strip()}")

if __name__ == "__main__":
    main()
