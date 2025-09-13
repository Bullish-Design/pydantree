# examples/04_semantic_analysis.py

"""Semantic analysis examples using Language abstractions."""

from pathlib import Path
from pydantree import get_language, create_language
from pydantree.languages.base import SemanticRole, SemanticNode
from pydantree.languages.python import PythonLanguage
from pydantree import from_tree

# Example 1: Basic semantic analysis
def basic_semantic_analysis():
    """Analyze code semantics using language-specific analyzers."""
    
    # Get Python language implementation
    python_lang = get_language("python")
    
    code = '''
"""Module for data processing utilities."""

import json
from typing import List, Dict, Optional

def load_config(file_path: str) -> Dict:
    """Load configuration from JSON file."""
    with open(file_path) as f:
        return json.load(f)

class DataProcessor:
    """Process and transform data."""
    
    def __init__(self, config: Dict):
        self.config = config
        self._cache: Dict = {}
    
    def process_item(self, item: Dict) -> Optional[Dict]:
        """Process a single data item."""
        if not self._validate_item(item):
            return None
        
        # Apply transformations
        result = item.copy()
        for transform in self.config.get('transforms', []):
            result = self._apply_transform(result, transform)
        
        return result
    
    def _validate_item(self, item: Dict) -> bool:
        """Validate item structure."""
        required_fields = self.config.get('required_fields', [])
        return all(field in item for field in required_fields)
    
    def _apply_transform(self, data: Dict, transform: str) -> Dict:
        """Apply transformation to data."""
        # Implementation details...
        return data

# Global constants
DEFAULT_CONFIG = {
    'required_fields': ['id', 'name'],
    'transforms': ['normalize', 'validate']
}
'''
    
    # Parse and analyze
    ast_root = python_lang.parse_file_from_string(code)
    semantic_root = python_lang.analyze_file_from_string(code)
    
    print("Semantic Analysis Results:")
    print(f"Root semantic role: {semantic_root.role}")
    print(f"Module name: {semantic_root.name}")
    print(f"Docstring: {semantic_root.docstring}")
    
    # Extract definitions
    definitions = python_lang.analyzer.extract_definitions(ast_root)
    
    print(f"\nFound {len(definitions)} top-level definitions:")
    for defn in definitions:
        print(f"  {defn.role.value}: {defn.name}")
        if defn.docstring:
            print(f"    Doc: {defn.docstring[:50]}...")
    
    return semantic_root, definitions

# Example 2: Scope and hierarchy analysis
def scope_hierarchy_analysis():
    """Analyze scope hierarchies and nested structures."""
    
    python_lang = get_language("python")
    
    code = '''
class OuterClass:
    """Outer class with nested structures."""
    
    class_var = "shared"
    
    def __init__(self):
        self.instance_var = "instance"
    
    def outer_method(self):
        """Method in outer class."""
        
        def inner_function():
            """Function nested in method."""
            local_var = "local"
            return local_var
        
        class InnerClass:
            """Class nested in method."""
            
            def inner_method(self):
                return "inner"
        
        return inner_function(), InnerClass()
    
    class NestedClass:
        """Class nested in outer class."""
        
        def nested_method(self):
            """Method in nested class."""
            return OuterClass.class_var

def module_function():
    """Function at module level."""
    
    class LocalClass:
        pass
    
    return LocalClass()
'''
    
    semantic_root = python_lang.analyze_file_from_string(code)
    
    def print_hierarchy(node: SemanticNode, indent: int = 0):
        """Recursively print semantic hierarchy."""
        prefix = "  " * indent
        role_name = node.role.value if node.role else "unknown"
        name = node.name or "<anonymous>"
        
        print(f"{prefix}{role_name}: {name}")
        
        if node.docstring:
            doc_preview = node.docstring.split('\n')[0][:40]
            print(f"{prefix}  Doc: {doc_preview}...")
        
        # Print attributes
        if node.attributes:
            for key, value in node.attributes.items():
                print(f"{prefix}  {key}: {value}")
        
        # Recursively print children
        for child in node.children:
            print_hierarchy(child, indent + 1)
    
    print("Semantic Hierarchy:")
    print_hierarchy(semantic_root)
    
    return semantic_root

# Example 3: Cross-reference analysis
def cross_reference_analysis():
    """Analyze variable usage and cross-references."""
    
    python_lang = get_language("python")
    
    code = '''
# Configuration constants
DATABASE_URL = "postgresql://localhost/mydb"
API_KEY = "secret-key"

class DatabaseConnection:
    def __init__(self, url=DATABASE_URL):
        self.url = url
        self.connection = None
    
    def connect(self):
        # Use the URL to connect
        print(f"Connecting to {self.url}")
        return True

class APIClient:
    def __init__(self, api_key=API_KEY):
        self.api_key = api_key
        self.db = DatabaseConnection()
    
    def fetch_data(self):
        if self.db.connect():
            return {"key": self.api_key}
        return None

def main():
    client = APIClient()
    data = client.fetch_data()
    
    if data:
        print(f"Data: {data}")
    
    # Direct usage of constants
    backup_url = DATABASE_URL + "_backup"
    return backup_url
'''
    
    ast_root = python_lang.parse_file_from_string(code)
    semantic_root = python_lang.analyze_file_from_string(code)
    
    # Find all identifiers
    from pydantree import from_tree
    all_nodes = from_tree(ast_root)
    identifiers = all_nodes.filter_type("identifier")
    
    # Group by identifier name
    identifier_usage = {}
    for identifier in identifiers:
        name = identifier.text.strip()
        if name not in identifier_usage:
            identifier_usage[name] = []
        identifier_usage[name].append({
            'line': identifier.start_point.row + 1,
            'column': identifier.start_point.column,
            'context': 'definition' if identifier.parent.type_name in 
                      {'variable_declaration', 'function_definition', 'class_definition'} else 'usage'
        })
    
    print("Cross-Reference Analysis:")
    
    # Show variables used multiple times
    for name, usages in identifier_usage.items():
        if len(usages) > 1 and name.isupper():  # Focus on constants
            print(f"\n{name} ({len(usages)} usages):")
            for usage in usages:
                print(f"  Line {usage['line']:2d}: {usage['context']}")
    
    return identifier_usage

# Example 4: Code complexity analysis
def complexity_analysis():
    """Analyze code complexity using semantic information."""
    
    python_lang = get_language("python")
    
    code = '''
def simple_function(x):
    """Simple function with low complexity."""
    return x * 2

def complex_function(data, options=None):
    """Complex function with high complexity."""
    if options is None:
        options = {}
    
    results = []
    
    for item in data:
        try:
            if isinstance(item, dict):
                if 'process' in options:
                    for key, value in item.items():
                        if isinstance(value, str):
                            if len(value) > 10:
                                processed = value.upper()
                            else:
                                processed = value.lower()
                        elif isinstance(value, (int, float)):
                            if value > 0:
                                processed = value * 2
                            else:
                                processed = abs(value)
                        else:
                            processed = str(value)
                        
                        item[key] = processed
                
                results.append(item)
            
            elif isinstance(item, str):
                if 'transform' in options:
                    if options['transform'] == 'upper':
                        results.append(item.upper())
                    elif options['transform'] == 'lower':
                        results.append(item.lower())
                    else:
                        results.append(item.title())
                else:
                    results.append(item)
            
            else:
                if 'convert' in options and options['convert']:
                    results.append(str(item))
                else:
                    results.append(item)
        
        except Exception as e:
            if 'ignore_errors' in options and options['ignore_errors']:
                continue
            else:
                raise e
    
    return results

class ComplexClass:
    """Class with multiple methods of varying complexity."""
    
    def __init__(self, config):
        self.config = config
        self.cache = {}
    
    def simple_method(self):
        return self.config.get('value', 0)
    
    def complex_method(self, data):
        if not data:
            return []
        
        processed = []
        
        for item in data:
            if item in self.cache:
                result = self.cache[item]
            else:
                if self.config.get('validate', True):
                    if not self._validate(item):
                        continue
                
                if self.config.get('transform', False):
                    result = self._transform(item)
                else:
                    result = item
                
                self.cache[item] = result
            
            processed.append(result)
        
        return processed
    
    def _validate(self, item):
        return item is not None and str(item).strip()
    
    def _transform(self, item):
        return str(item).upper() if isinstance(item, str) else item
'''
    
    semantic_root = python_lang.analyze_file_from_string(code)
    ast_root = python_lang.parse_file_from_string(code)
    
    # Analyze complexity for each function/method
    functions = ast_root.find_all_by_type("function_definition")
    
    print("Complexity Analysis:")
    print(f"{'Function':<20} {'Complexity':<10} {'Lines':<6} {'Nodes':<6}")
    print("-" * 50)
    
    for func in functions:
        name_node = func.child_by_field_name("name")
        if name_node:
            func_name = name_node.text
            
            # Get metrics
            metrics = func.get_metrics()
            complexity = metrics['cyclomatic_complexity']
            line_count = metrics['line_count']
            node_count = metrics['total_nodes']
            
            print(f"{func_name:<20} {complexity:<10} {line_count:<6} {node_count:<6}")
    
    # Categorize by complexity
    simple_funcs = []
    complex_funcs = []
    
    for func in functions:
        name_node = func.child_by_field_name("name")
        if name_node:
            metrics = func.get_metrics()
            complexity = metrics['cyclomatic_complexity']
            
            if complexity <= 5:
                simple_funcs.append(name_node.text)
            else:
                complex_funcs.append(name_node.text)
    
    print(f"\nComplexity Categories:")
    print(f"Simple (≤5): {', '.join(simple_funcs)}")
    print(f"Complex (>5): {', '.join(complex_funcs)}")
    
    return functions

# Example 5: Documentation analysis
def documentation_analysis():
    """Analyze documentation coverage and quality."""
    
    python_lang = get_language("python")
    
    code = '''
"""
High-quality module docstring.

This module provides utilities for data processing
and analysis with comprehensive documentation.
"""

def documented_function(param1: str, param2: int = 10) -> str:
    """
    Well-documented function with detailed docstring.
    
    Args:
        param1: First parameter description
        param2: Second parameter with default value
    
    Returns:
        Processed string result
    
    Raises:
        ValueError: When param1 is empty
    """
    if not param1:
        raise ValueError("param1 cannot be empty")
    return param1 * param2

def undocumented_function(x, y):
    return x + y

class DocumentedClass:
    """
    Well-documented class with comprehensive docstring.
    
    This class demonstrates good documentation practices
    with detailed descriptions of methods and attributes.
    
    Attributes:
        value: The stored value
        count: Number of operations performed
    """
    
    def __init__(self, value: int):
        """Initialize with a value."""
        self.value = value
        self.count = 0
    
    def documented_method(self, factor: float) -> int:
        """
        Multiply value by factor.
        
        Args:
            factor: Multiplication factor
        
        Returns:
            Result of multiplication
        """
        self.count += 1
        return int(self.value * factor)
    
    def undocumented_method(self, x):
        self.count += 1
        return self.value + x

class UndocumentedClass:
    def __init__(self, data):
        self.data = data
    
    def process(self):
        return len(self.data)
'''
    
    semantic_root = python_lang.analyze_file_from_string(code)
    
    def analyze_documentation(node: SemanticNode, stats: dict = None):
        """Recursively analyze documentation coverage."""
        if stats is None:
            stats = {'total': 0, 'documented': 0, 'by_type': {}}
        
        # Count documentable items
        if node.role in {SemanticRole.FUNCTION, SemanticRole.CLASS, SemanticRole.MODULE}:
            stats['total'] += 1
            role_name = node.role.value
            
            if role_name not in stats['by_type']:
                stats['by_type'][role_name] = {'total': 0, 'documented': 0}
            
            stats['by_type'][role_name]['total'] += 1
            
            if node.docstring and node.docstring.strip():
                stats['documented'] += 1
                stats['by_type'][role_name]['documented'] += 1
        
        # Recurse into children
        for child in node.children:
            analyze_documentation(child, stats)
        
        return stats
    
    doc_stats = analyze_documentation(semantic_root)
    
    print("Documentation Analysis:")
    print(f"Overall coverage: {doc_stats['documented']}/{doc_stats['total']} "
          f"({doc_stats['documented']/doc_stats['total']*100:.1f}%)")
    
    print("\nBy type:")
    for type_name, type_stats in doc_stats['by_type'].items():
        coverage = type_stats['documented'] / type_stats['total'] * 100
        print(f"  {type_name}: {type_stats['documented']}/{type_stats['total']} ({coverage:.1f}%)")
    
    # List undocumented items
    def find_undocumented(node: SemanticNode, undoc_list: list = None):
        if undoc_list is None:
            undoc_list = []
        
        if (node.role in {SemanticRole.FUNCTION, SemanticRole.CLASS} and
            (not node.docstring or not node.docstring.strip())):
            undoc_list.append(f"{node.role.value}: {node.name}")
        
        for child in node.children:
            find_undocumented(child, undoc_list)
        
        return undoc_list
    
    undocumented = find_undocumented(semantic_root)
    
    if undocumented:
        print(f"\nUndocumented items:")
        for item in undocumented:
            print(f"  - {item}")
    
    return doc_stats, undocumented

if __name__ == "__main__":
    print("=== Semantic Analysis Examples ===\n")
    
    print("1. Basic semantic analysis:")
    basic_semantic_analysis()
    
    print("\n2. Scope hierarchy analysis:")
    scope_hierarchy_analysis()
    
    print("\n3. Cross-reference analysis:")
    cross_reference_analysis()
    
    print("\n4. Complexity analysis:")
    complexity_analysis()
    
    print("\n5. Documentation analysis:")
    documentation_analysis()
