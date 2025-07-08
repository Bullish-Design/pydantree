#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.11",
#     "tree-sitter>=0.23",
#     "tree-sitter-python>=0.23.6",
# ]
# ///

"""Basic parsing demonstration."""

from pathlib import Path
from pydantree import parse_python, find_functions, find_classes

# Sample code to parse
SAMPLE_CODE = '''
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

class Person:
    def __init__(self, name: str):
        self.name = name
    
    def speak(self):
        print(greet(self.name))
'''

def main():
    print("=== Basic Parsing Demo ===\n")
    
    # Parse code into PyModule
    module = parse_python(SAMPLE_CODE)
    print(f"Parsed module with {len(module.node.children)} top-level nodes")
    
    # Find functions
    functions = find_functions(SAMPLE_CODE)
    print(f"\nFound {len(functions)} functions:")
    for func in functions:
        print(f"  - {func.name()}: {func.has_return()}")
    
    # Find classes  
    classes = find_classes(SAMPLE_CODE)
    print(f"\nFound {len(classes)} classes:")
    for cls in classes:
        print(f"  - {cls.name()}: {len(list(cls.methods()))} methods")
    
    # Demonstrate AST navigation
    print(f"\nAST Structure:")
    print(module.node.pretty(max_text=20))

if __name__ == "__main__":
    main()
