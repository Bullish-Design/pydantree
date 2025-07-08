# Pydantree

**Typed Tree-sitter wrapper with graph operations for Python AST analysis and transformation.**

Pydantree combines Tree-sitter's incremental parsing with Pydantic's type safety, providing a powerful toolkit for static analysis, code transformation, and AST pattern matching.

## Features

- 🔒 **Type-safe AST nodes** with Pydantic validation
- ⚡ **Incremental parsing** for efficient code editing
- 🔍 **Lazy collections** with Django-inspired query API
- 📊 **Graph analysis** using rustworkx algorithms
- 🎯 **Pattern matching** with VF2 isomorphism detection
- 🔄 **Code transformation** framework
- 🛠️ **CLI tools** for analysis and generation

## Installation

```bash
# Basic installation
pip install pydantree

# With graph operations
pip install pydantree[graph]

# With CLI tools
pip install pydantree[cli]

# Development installation
pip install pydantree[dev]
```

## Quick Start

### Basic Parsing

```python
from pydantree import parse_python, find_functions, find_classes

code = '''
def greet(name: str) -> str:
    return f"Hello, {name}!"

class Person:
    def __init__(self, name: str):
        self.name = name
'''

# Parse into typed AST
module = parse_python(code)
print(f"Parsed {len(module.node.children)} top-level nodes")

# Find specific constructs
functions = find_functions(code)
classes = find_classes(code)

print(f"Functions: {[f.name() for f in functions]}")
print(f"Classes: {[c.name() for c in classes]}")
```

### High-Level Views

```python
from pydantree.views import PyModule

module = PyModule.parse(code)

# Chainable queries
async_functions = (module.functions()
                  .where(lambda f: f.is_async())
                  .named("process_data"))

# Method analysis
for cls in module.classes():
    methods = cls.methods()
    print(f"{cls.name()}: {len(methods)} methods")
    if cls.has_init():
        print(f"  Has __init__ method")
```

### NodeGroup Collections

```python
from pydantree import NodeGroup

# Create from AST tree
nodegroup = NodeGroup.from_tree(module.node)

# Lazy filtering and set operations
identifiers = nodegroup.filter_type("identifier")
functions = nodegroup.filter_type("function_definition")
print_calls = nodegroup.filter_text("print", exact=False)

# Combine with set algebra
all_defs = functions.union(nodegroup.filter_type("class_definition"))
print(f"Total definitions: {len(all_defs)}")

# Group by type
grouped = nodegroup.groupby(lambda n: n.type_name)
for type_name, group in grouped.items():
    if len(group) > 1:
        print(f"{type_name}: {len(group)}")
```

### Code Transformation

```python
from pydantree.views import PyTransformer

class PrintToLogger(PyTransformer):
    def visit_expression_statement(self, node):
        text = node.text.strip()
        if text.startswith("print("):
            return text.replace("print(", "logger.info(", 1)

# Apply transformation
transformer = PrintToLogger(module)
transformed_code = transformer.visit()
```

### Graph Analysis

```python
from pydantree.graph import GraphBuilder, GraphAnalyzer

# Build graph from AST
builder = GraphBuilder(nodegroup)
graph = builder.to_graph(directed=True, include_siblings=False)

# Analyze structure
analyzer = GraphAnalyzer(graph)
metrics = analyzer.graph_metrics()
components = analyzer.connected_components()

print(f"Nodes: {metrics['num_nodes']}, Edges: {metrics['num_edges']}")
print(f"Components: {len(components)}")
```

## Core Concepts

### TSNode - Typed AST Nodes

All AST nodes inherit from `TSNode`, providing immutable, validated representations:

```python
from pydantree.core import TSNode

# Generated from node-types.json
class FunctionDefinitionNode(TSNode):
    __match_args__ = ('type_name', 'body', 'name', 'parameters')
    
    def name(self) -> str:
        return self.child_by_field_name("name").text
```

### ParsedDocument - Incremental Parsing

Maintains text and AST synchronization for efficient editing:

```python
from pydantree import ParsedDocument, Parser

doc = ParsedDocument(text=code, parser=parser)

# Apply incremental edit
doc.edit(
    start_byte=10,
    old_end_byte=20,
    new_end_byte=25,
    new_text="replacement"
)
# AST automatically re-parsed with Tree-sitter's incremental algorithm
```

### NodeGroup - Lazy Collections

Set-theoretic operations with lazy evaluation:

```python
# Lazy filtering - no computation until iteration
filtered = nodegroup.filter_type("function_definition")
methods = filtered.where(lambda n: "def " in n.text)

# Set operations
union_result = set1.union(set2)
intersection = set1.intersection(set2)
difference = set1.difference(set2)

# Materialization
concrete_list = list(filtered)  # Forces evaluation
```

## API Reference

### Core Classes

- **`TSNode`** - Base AST node with validation and navigation
- **`Parser`** - Wrapper around tree-sitter with typed output
- **`ParsedDocument`** - Incremental parsing with text sync
- **`NodeGroup`** - Lazy collections with set operations

### Views Layer

- **`PyModule`** - High-level module wrapper
- **`PyFunction`** - Function definition with semantic methods
- **`PyClass`** - Class definition with method analysis
- **`QuerySet`** - Django-inspired chainable queries
- **`PyTransformer`** - Visitor pattern for code transformation

### Graph Operations

- **`GraphBuilder`** - Convert NodeGroup to rustworkx graphs
- **`PatternMatcher`** - VF2 isomorphism for pattern detection
- **`GraphAnalyzer`** - Centrality, paths, and connectivity analysis

## Command Line Interface

### Generate Node Classes

```bash
# Generate typed classes from Tree-sitter grammar
pydantree generate node-types.json --out python_nodes.py
```

### AST Analysis

```bash
# Display AST structure
pydantree ast example.py --format tree --depth 3

# JSON output for programmatic use
pydantree ast example.py --format json > ast.json
```

### Query Operations

```bash
# Find specific node types
pydantree query example.py --type function_definition --count

# Text-based search
pydantree query example.py --text "async def" 

# Complex filtering
pydantree query example.py --type class_definition --text "__init__"
```

### Code Transformation

```bash
# Apply built-in transformations
pydantree transform example.py --transform print_to_logger --out modified.py

# View transformation without saving
pydantree transform example.py --transform print_to_logger
```

### Graph Analysis

```bash
# Graph metrics and statistics
pydantree graph example.py --format stats

# Include sibling relationships
pydantree graph example.py --siblings --format stats
```

## Advanced Usage

### Pattern Matching

```python
from pydantree.graph import PatternMatcher, build_pattern_graph

# Define pattern AST
pattern_code = "def example(): pass"
pattern_module = parse_python(pattern_code)
pattern_graph = build_pattern_graph([pattern_module.node])

# Find matches in target
target_graph = build_tree_graph(target_nodegroup)
matcher = PatternMatcher(pattern_graph)
matches = matcher.find_matches(target_graph)
```

### Custom Node Generation

```bash
# Generate from your own Tree-sitter grammar
pydantree generate my-grammar/node-types.json \
    --out custom_nodes.py \
    --base-class CustomTSNode \
    --token-suffix Token
```

### Bulk Operations

```python
# Bulk transformation with NodeGroup
def transform_function_names(nodegroup):
    functions = nodegroup.filter_type("function_definition")
    return functions.map(lambda f: f.replace_child(
        f.child_by_field_name("name"),
        create_identifier(f"new_{f.name()}")
    ))

# Apply to entire codebase
transformed = transform_function_names(codebase_nodegroup)
```

## Development

### Project Structure

```
pydantree/
├── src/pydantree/
│   ├── core.py           # Base TSNode and TSPoint models
│   ├── parser.py         # Parser wrapper
│   ├── incremental.py    # ParsedDocument for incremental parsing
│   ├── codegen.py        # Node class generation
│   ├── nodegroup.py      # Lazy collections
│   ├── graph.py          # Graph operations (requires rustworkx)
│   ├── views.py          # High-level Python views
│   └── cli.py            # Command-line interface
├── src/data/
│   ├── node-types.json   # Tree-sitter Python grammar
│   └── python_nodes.py   # Generated node classes
└── src/examples/         # Usage examples
```

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/pydantree.git
cd pydantree

# Install with uv (recommended)
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv sync --dev

# Or with pip
pip install -e ".[dev,graph,cli]"

# Run tests
pytest tests/

# Type checking
mypy src/pydantree/

# Code formatting
ruff format src/
ruff check src/ --fix
```

### Dependencies

**Core:**
- `pydantic>=2.11` - Type validation and serialization
- `tree-sitter>=0.23` - Incremental parsing
- `tree-sitter-python>=0.23.6` - Python grammar

**Optional:**
- `rustworkx>=0.14.0` - Graph algorithms (for graph operations)
- `typer>=0.12.0` - CLI framework
- `rich>=13.0.0` - Terminal formatting

## Performance Notes

- **Lazy evaluation**: NodeGroup operations are lazy until materialized
- **Incremental parsing**: Tree-sitter only re-parses changed regions
- **Memory efficiency**: Immutable nodes with structural sharing
- **Graph caching**: Graph conversions can be cached for repeated analysis

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes with tests
4. Run the test suite (`pytest`)
5. Submit a pull request

### Code Style

- Use `ruff` for formatting and linting
- Type hints required for public APIs
- Docstrings for all public functions
- Keep line length under 80 characters
- Follow Pydantic model conventions

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Related Projects

- [tree-sitter](https://tree-sitter.github.io/) - Incremental parsing library
- [pydantic](https://pydantic.dev/) - Data validation using Python type hints
- [rustworkx](https://rustworkx.readthedocs.io/) - High-performance graph algorithms
- [libcst](https://libcst.readthedocs.io/) - Concrete syntax tree library for Python


```
