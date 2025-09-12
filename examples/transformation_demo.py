#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.11",
#     "tree-sitter>=0.23",
#     "tree-sitter-python>=0.23.6",
# ]
# ///

"""Code transformation demonstration."""

from pydantree import parse_python
from pydantree.views import PyTransformer
from pydantree.nodegroup import PredicateSelector

ORIGINAL_CODE = '''
def process_data(items):
    for item in items:
        print(f"Processing: {item}")
        if item > 10:
            print("Large item detected")
    print("Processing complete")
    return len(items)
'''

class PrintToLogger(PyTransformer):
    """Transform print() calls to logger.info() calls."""
    
    def visit_expression_statement(self, node):
        text = node.text.strip()
        if text.startswith("print("):
            return text.replace("print(", "logger.info(", 1)
        return None

def main():
    print("=== Transformation Demo ===\n")
    
    print("Original code:")
    print(ORIGINAL_CODE)
    
    # Parse and transform
    module = parse_python(ORIGINAL_CODE)
    transformer = PrintToLogger(module)
    transformed_code = transformer.visit()
    
    print("\nTransformed code:")
    print(transformed_code)
    
    # Alternative: bulk transformation with NodeGroup
    print("\n=== Bulk Transformation ===")
    module2 = parse_python(ORIGINAL_CODE)
    nodegroup = module2.to_nodegroup()
    
    # Find all print calls
    print_calls = nodegroup.where(
        lambda n: n.text.strip().startswith("print(")
    )
    
    print(f"Found {len(print_calls)} print statements")
    
    # Transform using NodeGroup operations
    def transform_print(node):
        if node.text.strip().startswith("print("):
            return node.text.replace("print(", "logger.debug(", 1)
        return node.text
    
    # Note: This would require additional edit application logic
    # The PyTransformer approach above is more complete

if __name__ == "__main__":
    main()
