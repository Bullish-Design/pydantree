# Pydantree Architecture Overview

Pydantree is a typed Tree-sitter wrapper that combines incremental parsing with Pydantic validation, providing a comprehensive toolkit for Python AST analysis, transformation, and graph operations.

## Design Philosophy

Pydantree bridges the gap between Tree-sitter's efficient incremental parsing and Python's type system, offering:

- **Type Safety**: All AST nodes are validated Pydantic models
- **Incremental Efficiency**: Leverages Tree-sitter's incremental re-parsing
- **Composable Operations**: Lazy collections with set-theoretic operations
- **Graph Analysis**: Convert ASTs to graphs for advanced pattern matching
- **Semantic Views**: High-level wrappers for common programming constructs

## Architecture Layers

### 1. Core Foundation (`core.py`, `parser.py`)

The foundational layer provides typed wrappers around Tree-sitter primitives:

```python
# Base validated models
TSNode     # Immutable AST node with Pydantic validation
TSPoint    # Row/column position wrapper
Parser     # Typed wrapper around tree_sitter.Parser
```

**Key Features:**
- Immutable, hashable nodes for structural pattern matching
- Automatic subclass registration from generated node types
- Navigation helpers (descendants, find_by_type, etc.)
- Edit operations returning new nodes

### 2. Incremental Parsing (`incremental.py`)

Maintains synchronization between source text and AST:

```python
ParsedDocument  # Text + Tree + validated root node
```

**Capabilities:**
- Efficient incremental re-parsing on edits
- Automatic point calculation for byte positions
- Tree/text consistency guarantees

### 3. Code Generation (`codegen.py`)

Generates strongly-typed node classes from Tree-sitter grammars:

```python
generate_from_node_types(json_path, output_path)
```

**Features:**
- Inheritance hierarchy analysis
- Field property generation with type annotations
- Grammar-aware edit helpers
- Symbol name resolution for operators/punctuation

### 4. Lazy Collections (`nodegroup.py`)

Set-theoretic operations over heterogeneous node collections:

```python
NodeGroup        # Lazy collection with set operations
NodeSelector     # Composable filtering predicates
TypeSelector     # Filter by node type
PredicateSelector # Custom filter functions
```

**Operations:**
- Lazy evaluation with selector chaining
- Set algebra: union, intersection, difference
- Bulk transformations and mutations
- Graph conversion capabilities

### 5. High-Level Views (`views.py`)

Semantic wrappers for common programming constructs:

```python
PyModule      # Module-level operations
PyFunction    # Function analysis and queries
PyClass       # Class structure and methods
QuerySet      # Django-inspired chainable queries
PyTransformer # Visitor pattern for codemods
```

**Features:**
- Chainable query API
- Semantic analysis methods (has_return, is_async, etc.)
- Code transformation framework
- Integration with NodeGroup operations

### 6. Graph Operations (`graph.py`)

Convert ASTs to graphs for advanced analysis:

```python
GraphBuilder    # NodeGroup → rustworkx graphs
PatternMatcher  # VF2 isomorphism matching
GraphAnalyzer   # Centrality, paths, components
```

**Capabilities:**
- Multiple graph representations (tree, sibling, custom)
- VF2 pattern matching for code patterns
- Graph algorithms (centrality, shortest paths, cycles)
- Performance metrics and analysis

## Data Flow Architecture

```
Source Code
    ↓
Parser (tree-sitter)
    ↓
ParsedDocument (text + tree sync)
    ↓
TSNode (validated models)
    ↓
┌─────────────────┬─────────────────┬─────────────────┐
│   NodeGroup     │   Views Layer   │  Graph Layer    │
│  (collections)  │   (semantics)   │  (analysis)     │
│                 │                 │                 │
│ • Set ops       │ • PyModule      │ • GraphBuilder  │
│ • Lazy eval     │ • PyFunction    │ • PatternMatch  │
│ • Bulk ops      │ • QuerySet      │ • GraphAnalyzer │
│ • Filtering     │ • Transformer   │ • VF2 matching  │
└─────────────────┴─────────────────┴─────────────────┘
                    ↓
            Transformed Code / Analysis Results
```

## Core Concepts

### Immutability and Structural Sharing

All TSNode objects are immutable Pydantic models, enabling:
- Safe concurrent access
- Structural pattern matching with `match/case`
- Hashability for use in sets and as dict keys
- Edit operations return new trees with structural sharing

### Lazy Evaluation

NodeGroup operations are lazy until materialized:
- Selector chains build up without computation
- Only evaluated on iteration or explicit materialization
- Enables efficient composition of complex queries

### Type Safety

Generated node classes provide compile-time type checking:
- Field access with proper typing
- Pattern matching with `__match_args__`
- IDE support for autocompletion and navigation

### Incremental Efficiency

ParsedDocument leverages Tree-sitter's incremental parsing:
- Only re-parses changed regions on edits
- Maintains byte/point position accuracy
- Efficient for interactive editing scenarios

## Usage Patterns

### 1. One-Shot Analysis

```python
# Parse and analyze code
module = parse_python(source_code)
functions = find_functions(source_code, name="specific_function")
```

### 2. Interactive Editing

```python
# Incremental parsing for editors
doc = ParsedDocument(text=code, parser=parser)
doc.edit(start_byte=10, old_end_byte=20, new_end_byte=15, new_text="new")
# Tree automatically re-parsed
```

### 3. Bulk Code Analysis

```python
# Large-scale analysis with lazy evaluation
nodegroup = NodeGroup.from_tree(root)
async_functions = (nodegroup
    .filter_type("function_definition")
    .where(lambda n: "async" in n.text)
)
```

### 4. Code Transformation

```python
# Visitor pattern transformations
class RefactorTransformer(PyTransformer):
    def visit_function_definition(self, node):
        # Transform function definitions
        return modified_text

result = RefactorTransformer(module).visit()
```

### 5. Pattern Matching

```python
# Graph-based pattern detection
pattern = build_pattern_graph(pattern_nodes)
matches = PatternMatcher(pattern).find_matches(target_graph)
```

## Extension Points

### Custom Node Types

Generate domain-specific node classes:
```bash
pydantree generate custom-grammar/node-types.json --out custom_nodes.py
```

### Custom Selectors

Implement `NodeSelector` for specialized filtering:
```python
class CustomSelector(NodeSelector):
    def matches(self, node: TSNode) -> bool:
        return custom_logic(node)
```

### Custom Graph Edges

Define specialized relationships:
```python
def custom_edge_predicate(node1: TSNode, node2: TSNode) -> bool:
    return semantic_relationship(node1, node2)

graph = builder.to_graph(edge_predicate=custom_edge_predicate)
```

## Performance Characteristics

- **Memory**: Immutable nodes with structural sharing
- **Parsing**: Incremental with Tree-sitter (logarithmic re-parse)
- **Collections**: Lazy evaluation minimizes computation
- **Graph**: Efficient rustworkx backend for algorithms
- **Type Checking**: Zero runtime overhead with Pydantic

## Integration Ecosystem

Pydantree integrates with:
- **Tree-sitter**: Core parsing engine
- **Pydantic**: Type validation and serialization
- **rustworkx**: High-performance graph algorithms  
- **Rich/Typer**: CLI tooling and output formatting

This architecture enables pydantree to serve as a foundation for static analysis tools, code transformation pipelines, and interactive development environments.