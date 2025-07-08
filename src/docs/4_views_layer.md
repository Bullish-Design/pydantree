# Views Layer - High-Level Python Semantics

The Views layer provides semantic wrappers for Python language constructs with Django-inspired chainable queries and visitor pattern transformations.

## Core Classes

### PyView - Base Wrapper

Generic view wrapper maintaining reference to ParsedDocument:

```python
class PyView(Generic[_TNode]):
    node: _TNode              # Wrapped TSNode
    _doc: ParsedDocument      # Source document reference
    
    # Common properties
    text: str                 # Source text slice
    start_point: TSPoint      # Position in source
    
    def children(self, cls: type[TSNode] = None) -> Iterator[TSNode]
    def to_nodegroup(self) -> NodeGroup[TSNode]
    def descendants(self) -> NodeGroup[TSNode]
```

### PyModule - Module-Level Operations

Root wrapper for Python modules:

```python
class PyModule(PyView[ModuleNode]):
    @classmethod
    def parse(cls, code: str) -> PyModule
    @classmethod  
    def parse_file(cls, path: str | Path) -> PyModule
    
    def functions(self) -> QuerySet[PyFunction]
    def classes(self) -> QuerySet[PyClass]
    def imports(self) -> QuerySet[PyImport]
    def statements(self) -> NodeGroup[TSNode]
```

### QuerySet - Chainable Queries

Django-inspired lazy query interface:

```python
class QuerySet(Generic[_S]):
    def filter(self, selector: NodeSelector) -> QuerySet[_S]
    def named(self, name: str) -> QuerySet[_S]
    def where(self, predicate: Callable[[_S], bool]) -> QuerySet[_S]
    def containing_text(self, text: str) -> QuerySet[_S]
    
    # Set operations
    def union(self, other: QuerySet[_S]) -> QuerySet[_S]
    def intersection(self, other: QuerySet[_S]) -> QuerySet[_S]
    def difference(self, other: QuerySet[_S]) -> QuerySet[_S]
    
    # Materialization
    def first() -> Optional[_S]
    def all() -> List[_S]
    def count() -> int
    def exists() -> bool
```

## Module Operations

### Basic Parsing and Analysis

```python
from pydantree.views import PyModule

# Parse Python code
module = PyModule.parse("""
import os
from typing import List

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
        
    async def process(self, items: List[int]) -> None:
        for item in items:
            print(item)

def main():
    calc = Calculator()
    result = calc.add(1, 2)
""")

print(f"Module has {module.functions().count()} functions")
print(f"Module has {module.classes().count()} classes")
```

### Chainable Queries

```python
# Find specific functions
main_functions = module.functions().named("main")
async_functions = module.functions().where(lambda f: f.is_async())
functions_with_return = module.functions().where(lambda f: f.has_return())

# Complex queries
public_async_methods = (module.classes()
    .first()
    .methods()
    .where(lambda m: m.is_async())
    .where(lambda m: not m.name().startswith("_")))

# Set operations
all_definitions = module.functions().union(
    module.classes().map(lambda c: c.methods()).flatten()
)
```

## Function Analysis

### PyFunction - Function Wrapper

```python
class PyFunction(PyView[FunctionDefinitionNode]):
    def name(self) -> str
    def parameters(self) -> Optional[TSNode]
    def body(self) -> Optional[TSNode]
    def return_type(self) -> Optional[TSNode]
    def has_return(self) -> bool
    def decorators(self) -> List[TSNode]
    def is_async(self) -> bool
```

### Function Operations

```python
# Analyze function properties
for func in module.functions():
    print(f"Function: {func.name()}")
    print(f"  Async: {func.is_async()}")
    print(f"  Has return: {func.has_return()}")
    print(f"  Parameters: {func.parameters()}")
    
    # Access body for detailed analysis
    body = func.body()
    if body:
        statements = NodeGroup(body.children)
        return_stmts = statements.filter_type("return_statement")
        print(f"  Return statements: {len(return_stmts)}")

# Find functions with specific patterns
recursive_functions = module.functions().where(
    lambda f: f.name() in f.body().text if f.body() else False
)

# Type annotation analysis
typed_functions = module.functions().where(
    lambda f: f.return_type() is not None
)
```

## Class Analysis

### PyClass - Class Wrapper

```python
class PyClass(PyView[ClassDefinitionNode]):
    def name(self) -> str
    def superclasses(self) -> Optional[TSNode]
    def body(self) -> Optional[TSNode]
    def methods(self) -> QuerySet[PyFunction]
    def has_init(self) -> bool
```

### Class Operations

```python
# Analyze class structure
for cls in module.classes():
    print(f"Class: {cls.name()}")
    print(f"  Has __init__: {cls.has_init()}")
    
    methods = cls.methods()
    print(f"  Methods: {methods.count()}")
    
    # Method analysis
    public_methods = methods.where(lambda m: not m.name().startswith("_"))
    property_methods = methods.where(lambda m: "@property" in m.text)
    
    print(f"  Public methods: {public_methods.count()}")
    print(f"  Properties: {property_methods.count()}")

# Find inheritance relationships  
derived_classes = module.classes().where(
    lambda c: c.superclasses() is not None
)

# Find specific patterns
data_classes = module.classes().where(
    lambda c: "@dataclass" in c.text
)
```

## Import Analysis

### PyImport - Import Wrapper

```python
class PyImport(PyView[TSNode]):
    def module_name(self) -> str
    def imported_names(self) -> List[str]
    def is_from_import(self) -> bool
```

### Import Operations

```python
# Analyze imports
imports = module.imports()

for imp in imports:
    print(f"Import: {imp.module_name()}")
    if imp.is_from_import():
        names = imp.imported_names()
        print(f"  Names: {names}")

# Find specific import patterns
standard_library = imports.where(
    lambda i: i.module_name() in ["os", "sys", "json", "re"]
)

third_party = imports.where(
    lambda i: not i.module_name().startswith(".")
)

relative_imports = imports.where(
    lambda i: i.module_name().startswith(".")
)
```

## Code Transformation

### PyTransformer - Visitor Pattern

```python
class PyTransformer:
    def __init__(self, mod: PyModule)
    def visit(self) -> str
    def bulk_transform(self, selector: NodeSelector, transformer: Callable)
```

### Custom Transformers

```python
class ModernizeTransformer(PyTransformer):
    """Modernize Python code patterns."""
    
    def visit_function_definition(self, node):
        """Add type hints to functions missing them."""
        if "def " in node.text and "->" not in node.text:
            # Add return type annotation
            lines = node.text.split('\n')
            if lines[0].endswith(':'):
                lines[0] = lines[0].replace(':', ' -> Any:')
                return '\n'.join(lines)
    
    def visit_expression_statement(self, node):
        """Convert print statements to f-strings."""
        text = node.text.strip()
        if text.startswith('print(') and '%" ' in text:
            # Convert % formatting to f-strings
            return convert_to_fstring(text)

# Apply transformation
transformer = ModernizeTransformer(module)
modernized_code = transformer.visit()
```

### Bulk Transformations

```python
class RefactorTransformer(PyTransformer):
    def __init__(self, module, old_name: str, new_name: str):
        super().__init__(module)
        self.old_name = old_name
        self.new_name = new_name
    
    def visit(self) -> str:
        # Use bulk transformation for efficiency
        self.bulk_transform(
            TypeSelector("identifier").where(lambda n: n.text == self.old_name),
            lambda node: node.text.replace(self.old_name, self.new_name)
        )
        return self.mod._doc.text

# Rename all occurrences
refactored = RefactorTransformer(module, "old_function", "new_function").visit()
```

## Advanced Patterns

### Complex Queries

```python
# Find all async methods in classes that inherit from specific base
async_methods_in_derived = (
    module.classes()
    .where(lambda c: "BaseClass" in c.superclasses().text if c.superclasses() else False)
    .map(lambda c: c.methods())
    .flatten()
    .where(lambda m: m.is_async())
)

# Find functions with specific decorator patterns
decorated_functions = module.functions().where(
    lambda f: any("@" in line for line in f.text.split('\n')[:5])
)

# Complex method analysis
def has_complex_logic(func: PyFunction) -> bool:
    body_text = func.body().text if func.body() else ""
    return (body_text.count('if ') > 3 or 
            body_text.count('for ') > 2 or
            len(body_text.split('\n')) > 20)

complex_methods = (module.classes()
    .map(lambda c: c.methods())
    .flatten()
    .where(has_complex_logic))
```

### Cross-Reference Analysis

```python
def find_function_calls(module: PyModule, function_name: str) -> List[TSNode]:
    """Find all calls to a specific function."""
    all_nodes = module.to_nodegroup()
    calls = all_nodes.filter_type("call")
    
    matching_calls = []
    for call in calls:
        func_node = call.child_by_field_name("function")
        if func_node and func_node.text == function_name:
            matching_calls.append(call)
    
    return matching_calls

def analyze_dependencies(module: PyModule) -> dict:
    """Analyze function call dependencies."""
    functions = {f.name(): f for f in module.functions()}
    dependencies = {}
    
    for name, func in functions.items():
        calls = find_function_calls(module, name)
        dependencies[name] = len(calls)
    
    return dependencies
```

## Integration Examples

### With NodeGroup

```python
# Views to NodeGroup
module_nodes = module.to_nodegroup()
function_nodes = module.functions().to_nodegroup()

# Combined analysis
complex_structures = (module_nodes
    .filter_type("function_definition")
    .union(module_nodes.filter_type("class_definition"))
    .where(lambda n: len(n.text) > 500))
```

### With Graph Operations

```python
from pydantree.graph import GraphBuilder

# Build call graph
function_calls = module.to_nodegroup().filter_type("call")
call_graph = GraphBuilder(function_calls).to_graph(
    edge_predicate=lambda n1, n2: is_function_call(n1, n2)
)

# Analyze with graph algorithms
from pydantree.graph import GraphAnalyzer
analyzer = GraphAnalyzer(call_graph)
centrality = analyzer.centrality_scores()
```

## Performance Tips

```python
# Efficient: Use chainable queries without premature materialization
result = (module.functions()
    .where(lambda f: f.is_async())
    .named("process_data")
    .first())  # Single materialization

# Inefficient: Multiple materializations
all_funcs = module.functions().all()
async_funcs = [f for f in all_funcs if f.is_async()]
named_funcs = [f for f in async_funcs if f.name() == "process_data"]

# Batch operations for large transformations
class BulkRenamer(PyTransformer):
    def __init__(self, module, rename_map):
        super().__init__(module)
        self.rename_map = rename_map
    
    def visit(self):
        for old_name, new_name in self.rename_map.items():
            self.bulk_transform(
                TypeSelector("identifier").where(lambda n: n.text == old_name),
                lambda node: new_name
            )
        return self.mod._doc.text
```

The Views layer bridges low-level AST manipulation with high-level semantic analysis, providing an intuitive API for Python code understanding and transformation.