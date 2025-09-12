# NodeGroup - Lazy Collections

NodeGroup provides lazy, set-theoretic operations over heterogeneous TSNode collections with efficient bulk operations and graph conversion capabilities.

## Core Classes

### NodeGroup - Main Collection Type

```python
from pydantree.nodegroup import NodeGroup

class NodeGroup(Generic[T]):
    nodes: Set[TSNode]              # Internal node storage
    selectors: List[NodeSelector]   # Lazy filter chain
```

### Selector System

Abstract predicates for composable filtering:

```python
class NodeSelector(ABC):
    def matches(self, node: TSNode) -> bool: ...
    def __and__(self, other) -> NodeSelector: ...  # Combine with AND
    def __or__(self, other) -> NodeSelector: ...   # Combine with OR  
    def __invert__(self) -> NodeSelector: ...      # Negate with NOT

# Built-in selectors
TypeSelector(type_name: str)                    # Filter by node type
ClassSelector(node_class: type[TSNode])         # Filter by Python class
TextSelector(text: str, exact: bool = True)     # Filter by text content
PredicateSelector(predicate: Callable)          # Custom filter function
```

## Creation and Basic Operations

### Creating NodeGroups

```python
# From tree traversal
root = parser.parse(code)
all_nodes = NodeGroup.from_tree(root)

# From specific nodes
nodes = NodeGroup([node1, node2, node3])
single = NodeGroup(single_node)

# Empty collection
empty = NodeGroup.empty()

# Factory functions
from pydantree.nodegroup import nodes, from_tree, empty
collection = nodes(node1, node2, node3)
```

### Basic Filtering

```python
# Type-based filtering
functions = all_nodes.filter_type("function_definition")
identifiers = all_nodes.filter_type("identifier")

# Class-based filtering (for generated classes)
from data.python_nodes import FunctionDefinitionNode
typed_functions = all_nodes.filter_class(FunctionDefinitionNode)

# Text-based filtering
print_calls = all_nodes.filter_text("print", exact=False)
exact_matches = all_nodes.filter_text("def main():", exact=True)

# Custom predicates
async_functions = all_nodes.where(lambda n: "async" in n.text)
long_lines = all_nodes.where(lambda n: len(n.text) > 100)
```

## Lazy Evaluation

NodeGroup operations are lazy until materialized:

```python
# These operations are lazy - no computation yet
filtered = (all_nodes
    .filter_type("function_definition")
    .where(lambda n: "async" in n.text)
    .filter_text("def", exact=False))

# Computation happens on materialization
result_list = list(filtered)           # Forces evaluation
result_count = len(filtered)           # Forces evaluation
first_item = filtered.find_first()     # Forces evaluation
```

### Selector Chaining

Selectors accumulate in a chain:

```python
# Build complex filters step by step
funcs = all_nodes.filter_type("function_definition")
async_funcs = funcs.where(lambda n: "async" in n.text)  
public_async_funcs = async_funcs.where(lambda n: not n.text.startswith("_"))

# Equivalent to:
complex_filter = all_nodes.filter(
    TypeSelector("function_definition") &
    PredicateSelector(lambda n: "async" in n.text) &
    PredicateSelector(lambda n: not n.text.startswith("_"))
)
```

## Set Operations

Full set algebra with lazy evaluation:

```python
functions = all_nodes.filter_type("function_definition")
classes = all_nodes.filter_type("class_definition")
imports = all_nodes.filter_type("import_statement")

# Union - combine collections
definitions = functions.union(classes)
all_statements = functions | classes | imports  # Operator syntax

# Intersection - common elements
async_functions = functions.intersection(
    all_nodes.where(lambda n: "async" in n.text)
)
common = set1 & set2  # Operator syntax

# Difference - exclude elements
non_async_functions = functions.difference(async_functions)
excluding = set1 - set2  # Operator syntax

# Symmetric difference
unique_to_either = set1.symmetric_difference(set2)
sym_diff = set1 ^ set2  # Operator syntax
```

## Transformation Operations

### Mapping and Transformation

```python
# Map function to all nodes (returns new NodeGroup)
def uppercase_text(node: TSNode) -> TSNode:
    return node.model_copy(update={"text": node.text.upper()})

uppercased = collection.map(uppercase_text)

# Transform with filtering (None results filtered out)
def extract_function_names(node: TSNode) -> Optional[TSNode]:
    if node.type_name == "function_definition":
        name_child = node.child_by_field_name("name")
        return name_child
    return None

function_names = all_nodes.transform(extract_function_names)
```

### Bulk Operations

```python
# Apply transformation to matching nodes
def add_type_hints(func_node: TSNode) -> TSNode:
    # Add type hints to parameters
    return modified_function

typed_functions = functions.map(add_type_hints)

# Conditional transformations
def modernize_print(node: TSNode) -> Optional[TSNode]:
    if "print " in node.text:  # Old print statement
        return node.model_copy(update={"text": node.text.replace("print ", "print(") + ")"})
    return node

modernized = all_nodes.transform(modernize_print)
```

## Queries and Aggregation

### Finding Elements

```python
# Find first matching element
first_function = all_nodes.find_first(TypeSelector("function_definition"))
first_class = classes.find_first()  # No selector needed if already filtered

# Find all matches
all_functions = all_nodes.find_all(TypeSelector("function_definition"))
async_funcs = functions.find_all(PredicateSelector(lambda n: "async" in n.text))

# Count elements
function_count = all_nodes.count(TypeSelector("function_definition"))
total_nodes = len(all_nodes)  # Forces materialization
```

### Grouping Operations

```python
# Group by type
by_type = all_nodes.groupby(lambda n: n.type_name)
for type_name, group in by_type.items():
    print(f"{type_name}: {len(group)} nodes")

# Group by custom criteria
by_depth = all_nodes.groupby(lambda n: len(n.text.split('\n')))
by_first_char = identifiers.groupby(lambda n: n.text[0] if n.text else '')

# Complex grouping
def complexity_level(node: TSNode) -> str:
    lines = len(node.text.split('\n'))
    if lines < 5: return "simple"
    elif lines < 20: return "medium"
    else: return "complex"

by_complexity = functions.groupby(complexity_level)
```

## Tree Traversal

### Descendant Operations

```python
# Get all descendants of current nodes
all_descendants = functions.descendants()

# Find nested structures
nested_functions = functions.descendants().filter_type("function_definition")
nested_classes = classes.descendants().filter_type("class_definition")

# Deep analysis
def find_deep_nesting(node: TSNode) -> bool:
    return len(list(node.descendants())) > 100

complex_nodes = all_nodes.where(find_deep_nesting)
```

### Sibling Relationships

```python
# Get siblings within a parent context
def get_function_siblings(parent_node: TSNode) -> NodeGroup:
    return all_nodes.siblings(parent_node).filter_type("function_definition")

# Find related nodes
class_methods = class_node.children().filter_type("function_definition")
```

## Advanced Selector Composition

### Boolean Logic

```python
# Complex selector combinations
is_async = PredicateSelector(lambda n: "async" in n.text)
is_function = TypeSelector("function_definition")
has_return = PredicateSelector(lambda n: "return" in n.text)

# AND combination
async_functions_with_return = all_nodes.filter(is_async & is_function & has_return)

# OR combination  
functions_or_classes = all_nodes.filter(
    TypeSelector("function_definition") | TypeSelector("class_definition")
)

# NOT combination
non_private = all_nodes.filter(~PredicateSelector(lambda n: n.text.startswith("_")))
```

### Custom Selectors

```python
class DocstringSelector(NodeSelector):
    """Select nodes that have docstrings."""
    
    def matches(self, node: TSNode) -> bool:
        if node.type_name not in ["function_definition", "class_definition"]:
            return False
        
        body = node.child_by_field_name("body")
        if not body or not body.children:
            return False
            
        first_stmt = body.children[0]
        return (first_stmt.type_name == "expression_statement" and
                first_stmt.children and 
                first_stmt.children[0].type_name == "string")

documented = all_nodes.filter(DocstringSelector())
```

## Integration with Other Layers

### Graph Conversion

```python
# Convert to graph for analysis
from pydantree.graph import GraphBuilder

graph = collection.to_graph()  # Direct conversion
builder = GraphBuilder(collection)
custom_graph = builder.to_graph(
    directed=True,
    include_siblings=True,
    edge_predicate=lambda n1, n2: semantic_relationship(n1, n2)
)
```

### Views Integration

```python
# NodeGroup can be used within Views
from pydantree.views import PyModule

module = PyModule.parse(code)
module_nodegroup = module.to_nodegroup()

# Combine with semantic queries
async_methods = (module_nodegroup
    .filter_type("function_definition")
    .where(lambda n: "async" in n.text))
```

## Performance and Best Practices

### Efficient Patterns

```python
# Good: Chain filters before materialization
result = (all_nodes
    .filter_type("function_definition")
    .where(lambda n: "async" in n.text)
    .filter_text("await", exact=False))
final_list = list(result)  # Single materialization

# Avoid: Multiple materializations
functions = list(all_nodes.filter_type("function_definition"))  # Materializes
async_funcs = [f for f in functions if "async" in f.text]       # Re-iterates
```

### Memory Efficiency

```python
# Lazy operations don't consume extra memory
huge_collection = NodeGroup.from_tree(massive_ast)
filtered = huge_collection.filter_type("identifier")  # No memory overhead

# Materialization only when needed
if filtered.count() > 1000:  # Efficient count
    sample = list(itertools.islice(filtered, 100))  # Partial materialization
```

### Batch Operations

```python
# Efficient bulk transformations
def batch_rename(nodegroup: NodeGroup, mapping: dict) -> NodeGroup:
    def rename_if_needed(node: TSNode) -> TSNode:
        if node.text in mapping:
            return node.model_copy(update={"text": mapping[node.text]})
        return node
    
    return nodegroup.map(rename_if_needed)

# Apply to large collections
renamed = batch_rename(all_identifiers, {"old_name": "new_name"})
```

NodeGroup's lazy evaluation and set operations make it ideal for large-scale AST analysis and transformation workflows.