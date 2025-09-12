# Core Foundation - TSNode and Parser

The core foundation provides typed, immutable wrappers around Tree-sitter's AST nodes and parser, forming the base for all higher-level operations.

## Key Classes

### TSNode - Validated AST Node

Immutable Pydantic model representing a Tree-sitter node with full type safety.

```python
from pydantree.core import TSNode, TSPoint

class TSNode(BaseModel):
    type_name: str                    # Node type from grammar
    start_byte: int                   # Byte position in source
    end_byte: int                     # End byte position  
    start_point: TSPoint              # (row, column) position
    end_point: TSPoint                # End (row, column)
    text: str                         # Source text slice
    children: List[TSNode]            # Child nodes
    is_named: bool = True             # Named vs anonymous
    field_name: Optional[str] = None  # Field name if child
```

**Key Features:**
- **Immutable**: All edit operations return new nodes
- **Hashable**: Can be used in sets and as dict keys
- **Pattern Matching**: Supports `match/case` with `__match_args__`
- **Validated**: Pydantic ensures structural integrity

### TSPoint - Position Wrapper

Simple row/column coordinate representation:

```python
class TSPoint(BaseModel):
    row: int      # 0-indexed line number
    column: int   # 0-indexed column position
```

### Parser - Typed Wrapper

Wraps `tree_sitter.Parser` to return validated `TSNode` objects:

```python
from pydantree.parser import Parser

parser = Parser.for_python()
root_node = parser.parse(source_code)  # Returns TSNode
```

## Core Operations

### Tree Navigation

```python
# Direct child access
name_node = func_node.child_by_field_name("name")
params = func_node.child_by_field_name("parameters")

# Multiple children with same field
decorators = func_node.children_by_field_name("decorator")

# Depth-first traversal
all_descendants = root.descendants()

# Type-based search
identifiers = root.find_by_type("identifier")
first_function = root.find_first_by_type("function_definition")
```

### Structural Pattern Matching

```python
# Match with destructuring
match node:
    case FunctionDefinitionNode(name=name_node, body=body_block):
        print(f"Function: {name_node.text}")
    case ClassDefinitionNode(name=name_node):
        print(f"Class: {name_node.text}")
    case _:
        print(f"Other: {node.type_name}")
```

### Immutable Edits

All edit operations return new nodes:

```python
# Replace child
new_func = func_node.replace_child(old_param, new_param)

# Insert at position
new_block = block_node.insert_child(2, new_statement)

# Append/prepend
new_block = block_node.append_child(return_stmt)
new_block = block_node.prepend_child(docstring)

# Delete child
new_block = block_node.delete_child(unwanted_stmt)
```

## Advanced Features

### Subclass Registry

Generated node classes are automatically registered:

```python
# Generated classes register themselves
from data.python_nodes import FunctionDefinitionNode

# Registry enables dynamic dispatch
TSNode.register_subclasses({
    "function_definition": FunctionDefinitionNode,
    "class_definition": ClassDefinitionNode,
})

# Parser automatically creates correct subtype
node = parser.parse(code)  # Returns FunctionDefinitionNode if appropriate
```

### Custom Node Creation

For testing or programmatic AST construction:

```python
# Create nodes directly
identifier = TSNode(
    type_name="identifier",
    start_byte=0,
    end_byte=4,
    start_point=TSPoint(row=0, column=0),
    end_point=TSPoint(row=0, column=4),
    text="test",
    children=[]
)

# Build complex structures
function_def = FunctionDefinitionNode(
    type_name="function_definition",
    text="def test(): pass",
    children=[name_node, params_node, body_node],
    # ... other required fields
)
```

## Generated Node Classes

Classes are generated from Tree-sitter's `node-types.json`:

```python
# Example generated class
class FunctionDefinitionNode(TSNode):
    """Generated node for function_definition."""
    __match_args__ = ('type_name', 'body', 'name', 'parameters', 'return_type')
    
    @property
    def name(self) -> IdentifierNode:
        """Access name field."""
        for child in self.children:
            if child.field_name == 'name':
                return child
        raise ValueError("Required field name not found")
    
    @property  
    def body(self) -> BlockNode:
        """Access body field."""
        # Similar implementation
        
    # Grammar-aware edit helpers
    def insert_child(self, index: int, child: TSNode) -> TSNode:
        """Insert child with grammar validation."""
        # TODO: Add grammar validation logic
        new_children = list(self.children)
        new_children.insert(index, child)
        return self.model_copy(update={'children': new_children})
```

## Usage Patterns

### Basic Parsing

```python
from pydantree import Parser

# Create parser for Python
parser = Parser.for_python()

# Parse source code
code = """
def hello(name: str) -> str:
    return f"Hello, {name}!"
"""

root = parser.parse(code)
print(f"Root type: {root.type_name}")
print(f"Children: {len(root.children)}")
```

### Tree Inspection

```python
# Pretty printing
print(root.pretty(max_text=30))

# JSON serialization
import json
data = root.model_dump()
print(json.dumps(data, indent=2))

# Type-specific operations
for node in root.descendants():
    if isinstance(node, FunctionDefinitionNode):
        print(f"Function: {node.name.text}")
    elif isinstance(node, IdentifierNode):
        print(f"Identifier: {node.text}")
```

### Immutable Transformations

```python
def add_docstring(func_node: FunctionDefinitionNode, docstring: str) -> FunctionDefinitionNode:
    """Add docstring to function if missing."""
    body = func_node.body
    
    # Check if first child is already a string (docstring)
    if body.children and body.children[0].type_name == "expression_statement":
        first_expr = body.children[0]
        if first_expr.children and first_expr.children[0].type_name == "string":
            return func_node  # Already has docstring
    
    # Create docstring node
    docstring_node = create_string_node(f'"""{docstring}"""')
    
    # Insert at beginning of body
    new_body = body.prepend_child(docstring_node)
    
    # Return new function with updated body
    return func_node.replace_child(body, new_body)
```

### Error Handling

```python
try:
    root = parser.parse(malformed_code)
    # Tree-sitter produces best-effort parse even with errors
    
    # Check for error nodes
    errors = root.find_by_type("ERROR")
    if errors:
        print(f"Found {len(errors)} parse errors")
        for error in errors:
            print(f"Error at {error.start_point}: {error.text}")
            
except Exception as e:
    print(f"Parse failed: {e}")
```

## Performance Considerations

### Memory Efficiency

- **Structural Sharing**: Immutable nodes share unchanged subtrees
- **Lazy Loading**: Children computed on demand where possible
- **Compact Representation**: Minimal overhead over raw Tree-sitter nodes

### Time Complexity

- **Tree Navigation**: O(1) for field access, O(n) for searches
- **Edit Operations**: O(log n) with structural sharing
- **Pattern Matching**: O(1) for type checks, O(n) for deep matching

### Best Practices

```python
# Efficient: Use field access when possible
name = func_node.name  # O(1) field access
body = func_node.body

# Less efficient: Generic search
name = func_node.find_first_by_type("identifier")  # O(n) search

# Batch operations: Collect changes then apply
changes = []
for node in nodes_to_modify:
    changes.append((node, transform(node)))

# Apply all changes at once
result = apply_batch_edits(root, changes)
```

## Integration with Higher Layers

The core foundation integrates seamlessly with higher layers:

```python
# NodeGroup operations
from pydantree.nodegroup import NodeGroup
nodegroup = NodeGroup.from_tree(root)

# Views layer
from pydantree.views import PyModule
module = PyModule(root, doc)

# Graph operations  
from pydantree.graph import GraphBuilder
graph = GraphBuilder(nodegroup).to_graph()
```

This foundation ensures type safety and immutability throughout the entire pydantree ecosystem.