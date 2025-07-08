# Code Generation - Typed Node Classes

Automatically generate strongly-typed Pydantic node classes from Tree-sitter grammar specifications.

## Core Components

### Generator Architecture

```python
# Main entry point
generate_from_node_types(
    json_path: str | Path,           # node-types.json from Tree-sitter
    out_path: str | Path,            # Output Python file
    token_suffix: str = "TokenNode", # Suffix for anonymous tokens
    base_class: str = "TSNode"       # Base class for inheritance
)

# Core classes
NameResolver     # Convert Tree-sitter names to Python identifiers
InheritanceAnalyzer  # Build inheritance hierarchy from supertypes
CodeGenerator    # Generate complete Python module
```

### Name Resolution

Converts Tree-sitter node names to valid Python identifiers:

```python
class NameResolver:
    # Operator/punctuation mappings
    SYMBOL_MAP = {
        "(": "LeftParen",      ")": "RightParen",
        "[": "LeftBracket",    "]": "RightBracket", 
        "+": "Plus",           "-": "Minus",
        "==": "Equality",      "!=": "NotEquals",
        "is not": "IsNot",     "not in": "NotIn",
        # ... comprehensive operator mapping
    }
    
    def resolve(self, node_type: str, is_named: bool) -> str:
        # Convert to PascalCase with appropriate suffix
```

## Generated Class Structure

### Basic Node Classes

Generated classes inherit from TSNode with typed fields:

```python
# From function_definition node type
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
        
    @property
    def parameters(self) -> Optional[ParametersNode]:
        """Access optional parameters field."""
        # Handle optional fields
```

### Field Property Generation

Type-safe accessors based on grammar specification:

```python
# For required single field
@property
def field_name(self) -> SpecificNodeType:
    for child in self.children:
        if child.field_name == 'field_name':
            return child
    raise ValueError("Required field not found")

# For optional single field  
@property
def optional_field(self) -> Optional[NodeType]:
    for child in self.children:
        if child.field_name == 'optional_field':
            return child
    return None

# For multiple fields
@property
def decorators(self) -> List[DecoratorNode]:
    result = []
    for child in self.children:
        if child.field_name == 'decorators':
            result.append(child)
    return result
```

### Inheritance Hierarchy

Analyzes supertype relationships from grammar:

```python
# From node-types.json:
{
  "type": "expression", 
  "subtypes": [
    {"type": "binary_operator"},
    {"type": "call"},
    {"type": "identifier"}
  ]
}

# Generates hierarchy:
class ExpressionNode(TSNode): pass
class BinaryOperatorNode(ExpressionNode): pass  
class CallNode(ExpressionNode): pass
class IdentifierNode(ExpressionNode): pass
```

## CLI Usage

### Basic Generation

```bash
# Generate from Tree-sitter grammar
pydantree generate node-types.json --out python_nodes.py

# Custom configuration
pydantree generate grammar.json \
    --out custom_nodes.py \
    --token-suffix "Token" \
    --base-class "CustomTSNode"
```

### Integration Workflow

```bash
# 1. Extract grammar from Tree-sitter
tree-sitter generate --abi 14 > grammar.json

# 2. Generate typed classes  
pydantree generate grammar.json --out typed_nodes.py

# 3. Use in parser
python -c "from pydantree import Parser; parser = Parser.for_language('custom')"
```

## Advanced Features

### Grammar Validation

Generated classes include edit helpers with grammar awareness:

```python
class FunctionDefinitionNode(TSNode):
    def insert_parameter(self, param: ParameterNode) -> FunctionDefinitionNode:
        """Insert parameter with grammar validation."""
        params = self.parameters
        if not params:
            # Create parameters node if missing
            params = ParametersNode(children=[param])
            return self.model_copy(update={'children': self.children + [params]})
        
        # Insert into existing parameters
        new_params = params.append_child(param)
        return self.replace_child(params, new_params)
    
    def add_decorator(self, decorator: DecoratorNode) -> DecoratedDefinitionNode:
        """Convert to decorated function."""
        decorated = DecoratedDefinitionNode(
            decorators=[decorator],
            definition=self
        )
        return decorated
```

### Symbol Mapping

Comprehensive operator and keyword handling:

```python
# Punctuation and operators
"(": "LeftParenNode"        ")": "RightParenNode"
"+": "PlusNode"             "-": "MinusNode"  
"==": "EqualityNode"        "!=": "NotEqualsNode"
"//": "FloorDivNode"        "**": "PowerNode"
"<<": "LeftShiftNode"       ">>": "RightShiftNode"

# Multi-character operators
"is not": "IsNotNode"       "not in": "NotInNode"
"except*": "ExceptStarNode"

# Keywords with context
"and": "LogicalAndNode"     "or": "LogicalOrNode"
"async": "AsyncKeywordNode" "await": "AwaitKeywordNode"
"lambda": "LambdaNode"      "yield": "YieldNode"
```

## Customization

### Custom Base Classes

```python
# Define custom base with domain-specific methods
class MyTSNode(TSNode):
    def custom_navigation(self): 
        # Domain-specific traversal
        pass
    
    def semantic_analysis(self):
        # Custom analysis methods
        pass

# Generate with custom base
generate_from_node_types(
    "grammar.json", 
    "nodes.py",
    base_class="MyTSNode"
)
```

### Field Extensions

```python
# Generated class with extensions
class FunctionDefinitionNode(TSNode):
    # Generated properties
    @property
    def name(self) -> IdentifierNode: ...
    
    # Custom extensions via inheritance
    def is_async(self) -> bool:
        return "async" in self.text
    
    def parameter_count(self) -> int:
        params = self.parameters
        return len(params.children) if params else 0
    
    def has_return_annotation(self) -> bool:
        return self.return_type is not None
```

### Multi-Language Support

```python
# Language-specific generators
class PythonCodeGenerator(CodeGenerator):
    def generate_imports(self):
        return [
            "from typing import List, Optional, Union",
            "from pydantree.core import TSNode"
        ]

class JavaScriptCodeGenerator(CodeGenerator):  
    def generate_imports(self):
        return [
            "from pydantree.core import TSNode",
            "from pydantree.js_types import JSNode"
        ]

# Use appropriate generator
generator = PythonCodeGenerator(node_specs, "TokenNode", "TSNode")
```

## Integration Examples

### Runtime Registration

Generated classes auto-register with TSNode:

```python
# Generated at end of module
NODE_MAP: dict[str, type[TSNode]] = {
    'function_definition': FunctionDefinitionNode,
    'class_definition': ClassDefinitionNode,
    'identifier': IdentifierNode,
    # ... all node types
}

# Automatic registration
TSNode.register_subclasses(NODE_MAP)

# Parser automatically uses correct types
parser = Parser.for_python()
root = parser.parse(code)  # Returns correctly typed nodes
```

### Dynamic Loading

```python
from pydantree.loader import NodeTypesBootstrap

# Ensure generated classes are loaded
NodeTypesBootstrap.ensure("data.python_nodes")

# Now parser will use typed classes
parser = Parser.for_python()
```

### Custom Grammar Integration

```python
# For custom Tree-sitter grammars
class CustomParser(Parser):
    @classmethod
    def for_custom_language(cls):
        # Load custom grammar
        import tree_sitter_custom as tsc
        language = Language(tsc.language())
        
        # Ensure custom nodes are loaded
        NodeTypesBootstrap.ensure("grammars.custom_nodes")
        
        return cls(language, module_name="grammars.custom_nodes")

# Use custom parser
parser = CustomParser.for_custom_language()
```

## Performance Considerations

Generated code optimizes for:

- **Type Safety**: Full static typing with minimal runtime overhead
- **Pattern Matching**: `__match_args__` enables efficient structural matching  
- **Memory**: Properties computed on-demand, no eager field materialization
- **Inheritance**: Proper MRO for complex grammar hierarchies

The code generation system enables type-safe AST manipulation with zero runtime penalty and full IDE support.