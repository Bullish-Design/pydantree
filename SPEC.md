# **Pydantree Technical Specification**

## **Document Information**

* **Version:** 1.0.0
* **Last Updated:** July 4, 2025
* **Status:** Draft

## **Executive Summary**

Pydantree is a Pydantic-powered abstraction layer over GraphSitter that treats code as structured data. It provides type-safe manipulation, validation, and composition of code structures for generation and transformation workflows by wrapping GraphSitter's parsing capabilities in validated Pydantic models.

## **Requirements**

### **Functional Requirements**

#### **Core Features**

**REQ-001: BaseCodeNode Foundation**

* **Description:** Root Pydantic model that wraps GraphSitter editable nodes, providing validation, serialization, and type safety for all code structures
* **Inputs:** GraphSitter editable nodes, validation configuration
* **Outputs:** Validated Pydantic models with type safety
* **Priority:** Critical
* **Acceptance Criteria:**
  * [ ] Wraps any GraphSitter editable node
  * [ ] Provides structural validation on creation
  * [ ] Supports serialization to/from JSON
  * [ ] Maintains bidirectional GraphSitter compatibility

**REQ-002: PyClass Wrapper**

* **Description:** Pydantic model wrapping GraphSitter's PyClass with validation for class manipulation
* **Inputs:** GraphSitter PyClass nodes, class metadata (name, bases, docstring)
* **Outputs:** Validated class objects with type-safe mutation methods
* **Priority:** Critical
* **Acceptance Criteria:**
  * [ ] Validates class structure on creation
  * [ ] Supports adding/removing methods with validation
  * [ ] Supports adding/removing attributes with type hints
  * [ ] Generates valid Python source code

**REQ-003: PyFunction Wrapper**

* **Description:** Pydantic model for GraphSitter's PyFunction supporting parameter validation and return type checking
* **Inputs:** GraphSitter PyFunction nodes, function metadata
* **Outputs:** Validated function objects with parameter/return type safety
* **Priority:** Critical
* **Acceptance Criteria:**
  * [ ] Validates function signature on creation
  * [ ] Supports parameter addition/modification with type hints
  * [ ] Validates return type annotations
  * [ ] Manages docstring content

**REQ-004: PyAssignment Wrapper**

* **Description:** Type-safe wrapper for variable assignments with value validation and type inference
* **Inputs:** GraphSitter assignment nodes, variable metadata
* **Outputs:** Validated assignment objects
* **Priority:** High
* **Acceptance Criteria:**
  * [ ] Validates assignment syntax
  * [ ] Supports type hint inference
  * [ ] Validates value consistency with type hints

#### **Extended Features**

**REQ-005: Builder Pattern Support**

* **Description:** Fluent builder interfaces for complex code construction
* **Priority:** Medium
* **Dependencies:** REQ-001, REQ-002, REQ-003

**REQ-006: Configuration Management**

* **Description:** Confidantic-based settings management for validation rules and behavior
* **Priority:** High
* **Dependencies:** REQ-001

## **Architecture**

### **System Overview**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Code     │───▶│   Pydantree     │───▶│  GraphSitter    │
│                 │    │   (Validation)  │    │   (AST/Parse)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         └──────────────│  Source Code    │◀─────────────┘
                        │   Generation    │
                        └─────────────────┘
```

### **Core Components**

#### **Class Hierarchy**

```python
# Core class structure using Pydantic
from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import Protocol, runtime_checkable, Any, Optional, List, Dict
from graph_sitter import Editable

@runtime_checkable
class GraphSitterEditable(Protocol):
    """Interface for GraphSitter editable nodes"""
    def to_source(self) -> str: ...
    def validate_structure(self) -> bool: ...

class BaseCodeNode(BaseModel):
    """Root Pydantic model for all code structures"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    graphsitter_node: Editable = Field(description="Underlying GraphSitter node")
    validate_structure: bool = Field(default=True, description="Enable structural validation")
    
    @classmethod
    def from_graphsitter(cls, node: Editable) -> BaseCodeNode:
        """Create instance from GraphSitter node"""
        
    def to_source(self) -> str:
        """Generate Python source code"""
        
    def to_graphsitter(self) -> Editable:
        """Export back to GraphSitter format"""
        
    def validate_integrity(self) -> bool:
        """Check structural consistency"""

class PyClass(BaseCodeNode):
    """Pydantic wrapper for GraphSitter PyClass with validation"""
    class_name: str = Field(description="Name of the class")
    base_classes: List[str] = Field(default_factory=list, description="Parent classes")
    docstring: Optional[str] = Field(None, description="Class docstring")
    
    def add_method(self, name: str, return_type: Optional[str] = None) -> PyFunction:
        """Add validated method to class"""
        
    def add_attribute(self, name: str, type_hint: Optional[str] = None, value: Any = None) -> None:
        """Add typed attribute to class"""
        
    def get_method(self, name: str) -> Optional[PyFunction]:
        """Retrieve method by name"""
        
    @classmethod
    def builder(cls, name: str) -> PyClassBuilder:
        """Create fluent builder instance"""

class PyFunction(BaseCodeNode):
    """Validated function definition wrapper"""
    function_name: str = Field(description="Function name")
    parameters: List[PyParameter] = Field(default_factory=list, description="Function parameters")
    return_type: Optional[str] = Field(None, description="Return type annotation")
    docstring: Optional[str] = Field(None, description="Function docstring")
    
    def add_parameter(self, name: str, type_hint: Optional[str] = None, default: Any = None) -> None:
        """Add parameter with validation"""
        
    def set_return_type(self, type_str: str) -> None:
        """Set return type annotation"""

class PyAssignment(BaseCodeNode):
    """Type-safe wrapper for variable assignments"""
    variable_name: str = Field(description="Variable name")
    value: Any = Field(description="Assigned value")
    type_hint: Optional[str] = Field(None, description="Type annotation")
    
class PyParameter(BaseModel):
    """Function parameter with type information"""
    name: str = Field(description="Parameter name")
    type_hint: Optional[str] = Field(None, description="Type annotation")
    default_value: Any = Field(None, description="Default value")
    is_required: bool = Field(True, description="Whether parameter is required")
```

#### **Component Responsibilities**

* **BaseCodeNode:** Core validation, serialization, GraphSitter integration
* **PyClass:** Class structure validation, method/attribute management
* **PyFunction:** Function signature validation, parameter management
* **PyAssignment:** Variable assignment validation, type checking
* **Configuration:** Settings management via Confidantic

#### **Data Flow**

1. **Input Processing:** GraphSitter nodes wrapped in Pydantic models
2. **Core Processing:** Validation, type checking, structural integrity
3. **Output Generation:** Source code generation or JSON serialization

### **Design Patterns**

* **Wrapper Pattern:** Pydantic models wrap GraphSitter nodes for validation
* **Builder Pattern:** Fluent interfaces for complex object construction
* **Strategy Pattern:** Configurable validation strategies via settings

## **Data Structures**

### **Input/Output Schemas**

```python
class CodeNodeInput(BaseModel):
    """Schema for creating code nodes"""
    node_type: str = Field(..., description="Type of code node (class, function, etc.)")
    source_code: Optional[str] = Field(None, description="Raw source code")
    graphsitter_node: Optional[Any] = Field(None, description="Existing GraphSitter node")

class CodeNodeOutput(BaseModel):
    """Schema for code node results"""
    source_code: str = Field(..., description="Generated Python source")
    node_type: str = Field(..., description="Type of code node")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    validation_errors: List[str] = Field(default_factory=list, description="Validation issues")

class ValidationResult(BaseModel):
    """Schema for validation results"""
    is_valid: bool = Field(..., description="Whether validation passed")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
```

### **Internal Data Models**

```python
class ClassStructure(BaseModel):
    """Internal model for class analysis"""
    methods: List[str] = Field(default_factory=list, description="Method names")
    attributes: List[str] = Field(default_factory=list, description="Attribute names")
    inheritance_chain: List[str] = Field(default_factory=list, description="Parent classes")

class FunctionSignature(BaseModel):
    """Internal model for function analysis"""
    parameter_count: int = Field(description="Number of parameters")
    has_return_type: bool = Field(description="Whether return type is annotated")
    complexity_score: int = Field(description="Function complexity metric")
```

### **Validation Rules**

* **Class Names:** Must be valid Python identifiers, PascalCase recommended
* **Function Names:** Must be valid Python identifiers, snake_case recommended
* **Type Hints:** Must be valid Python type annotations
* **Structure:** Must represent syntactically valid Python code

## **API Specification**

### **Public Interface**

```python
# Main entry points
class PydantreeAPI:
    def __init__(self, config: PydantreeConfig) -> None: ...
    
    def parse_class(self, source: str) -> PyClass:
        """Parse source code into validated PyClass"""
        
    def parse_function(self, source: str) -> PyFunction:
        """Parse source code into validated PyFunction"""
        
    def validate_code(self, node: BaseCodeNode) -> ValidationResult:
        """Validate code structure and syntax"""

# Factory functions
def from_graphsitter(node: Editable) -> BaseCodeNode:
    """Create appropriate Pydantic wrapper for GraphSitter node"""
    
def builder_for(node_type: str) -> Any:
    """Factory function for creating builder instances"""
```

### **Configuration**

```python
from confidantic import SettingsType
from pydantic import Field

class PydantreeConfig(SettingsType):
    """Configuration options and defaults"""
    validation_strict: bool = Field(default=True, env="PYDANTREE_VALIDATION_STRICT", 
                                  description="Enable strict validation")
    allow_partial_types: bool = Field(default=False, env="PYDANTREE_ALLOW_PARTIAL_TYPES",
                                    description="Allow incomplete type annotations")
    auto_format_code: bool = Field(default=True, env="PYDANTREE_AUTO_FORMAT",
                                 description="Automatically format generated code")
    max_complexity: int = Field(default=10, env="PYDANTREE_MAX_COMPLEXITY",
                               description="Maximum allowed cyclomatic complexity")
```

### **Usage Examples**

```python
# Basic usage
from pydantree import PyClass, PyFunction, PydantreeConfig
from graph_sitter import Codebase

# Configure library
config = PydantreeConfig(validation_strict=True)

# Load existing code
codebase = Codebase.from_repo("myproject/myrepo")
raw_class = codebase.get_class("UserAPI")

# Wrap in Pydantic model
validated_class = PyClass.from_graphsitter(raw_class)
validated_class.add_method("get_user", return_type="User")
result = validated_class.to_source()

# Builder pattern usage
api_class = PyClass.builder("UserAPI")\
    .with_base("BaseAPI")\
    .with_method(
        PyFunction.builder("get_user")
        .with_param("user_id", "int")
        .with_return_type("User")
        .build()
    )\
    .build()

# Serialization
serialized = validated_class.model_dump_json()
restored = PyClass.model_validate_json(serialized)
```

## **Error Handling**

### **Exception Hierarchy**

```python
class PydantreeException(Exception):
    """Base exception for all library errors"""

class ValidationError(PydantreeException):
    """Raised when input validation fails"""

class CodeStructureError(PydantreeException):
    """Raised when code structure is invalid"""

class GraphSitterIntegrationError(PydantreeException):
    """Raised when GraphSitter integration fails"""

class BuilderError(PydantreeException):
    """Raised during builder pattern construction"""
```

### **Error Scenarios**

* **Invalid Input:** Malformed GraphSitter nodes raise ValidationError with detailed context
* **Structure Violations:** Invalid code structures raise CodeStructureError with correction hints
* **Integration Failures:** GraphSitter compatibility issues raise GraphSitterIntegrationError
* **Builder Failures:** Incomplete builder state raises BuilderError with missing requirements

### **Error Messages**

* Use clear, actionable error messages with specific failure details
* Include context about what failed and potential fixes
* Log appropriate details for debugging without exposing internals

## **Dependencies**

### **Core Dependencies**

```python
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pydantic>=2.7.0",
#     "graph-sitter>=0.20.0",
#     "confidantic>=0.3.0",
#     "typing-extensions>=4.0.0",
# ]
# ///
```

### **Optional Dependencies**

* **dev:** pytest, pytest-cov, ruff, mypy for development workflow

### **Development Dependencies**

* Testing: pytest, pytest-cov, pytest-mock
* Linting: ruff, mypy
* Documentation: mkdocs, mkdocs-material

## **Testing Strategy**

### **Unit Tests**

```python
# Test structure example
import pytest
from pydantree import PyClass, PyFunction
from pydantic import ValidationError

class TestPyClass:
    def test_from_graphsitter_with_valid_node(self):
        """Test PyClass creation from valid GraphSitter node"""
        # Arrange
        mock_node = create_mock_graphsitter_class()
        
        # Act
        py_class = PyClass.from_graphsitter(mock_node)
        
        # Assert
        assert py_class.class_name == "TestClass"
        assert py_class.validate_integrity()
    
    def test_add_method_with_valid_signature(self):
        """Test method addition with type validation"""
        # Arrange
        py_class = PyClass(class_name="TestClass", graphsitter_node=mock_node)
        
        # Act
        method = py_class.add_method("test_method", return_type="str")
        
        # Assert
        assert method.function_name == "test_method"
        assert method.return_type == "str"
        
    def test_invalid_class_name_raises_validation_error(self):
        """Test error handling for invalid class names"""
        with pytest.raises(ValidationError):
            PyClass(class_name="123InvalidName", graphsitter_node=mock_node)

class TestPyFunction:
    def test_parameter_validation(self):
        """Test function parameter validation"""
        function = PyFunction(function_name="test_func", graphsitter_node=mock_node)
        function.add_parameter("param1", "int", default=0)
        
        assert len(function.parameters) == 1
        assert function.parameters[0].name == "param1"
```

### **Integration Tests**

* **GraphSitter Integration:** Test bidirectional conversion between Pydantic models and GraphSitter nodes
* **Configuration Loading:** Test Confidantic integration with environment variables and config files
* **Source Generation:** Test complete round-trip from parsing to source generation

### **Test Coverage Requirements**

* Minimum 90% line coverage
* 100% coverage for critical validation paths
* Edge case coverage for all public methods

## **Implementation Guidelines**

### **File Organization**

```
pydantree/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── base.py          # BaseCodeNode
│   ├── classes.py       # PyClass
│   ├── functions.py     # PyFunction
│   ├── assignments.py   # PyAssignment
│   └── builders.py      # Builder classes
├── config/
│   ├── __init__.py
│   └── settings.py      # Confidantic configuration
├── exceptions.py
└── utils/
    ├── __init__.py
    ├── validation.py
    └── graphsitter_integration.py
```

### **Development Workflow**

1. Create feature branch from main
2. Implement with comprehensive tests
3. Run full test suite (pytest)
4. Code quality checks (ruff, mypy)
5. Update documentation if needed
6. Submit pull request for review

## **Security Considerations**

* **Input Validation:** Use Pydantic validation for all user inputs
* **Code Injection:** Sanitize all generated code through GraphSitter validation
* **Arbitrary Code Execution:** Never execute generated code within library

## **Monitoring and Logging**

* **Logging Levels:** Use standard Python logging with configurable levels
* **Performance Metrics:** Track validation time and memory usage for large codebases
* **Error Tracking:** Log validation failures with context for debugging

## **Migration and Versioning**

* **Semantic Versioning:** Use major.minor.patch versioning
* **Breaking Changes:** Allow breaking changes with clear migration guides
* **API Stability:** Maintain backward compatibility for core BaseCodeNode interface

---

## **Implementation Checklist**

* [ ] BaseCodeNode implemented with Pydantic validation
* [ ] PyClass wrapper with method/attribute management
* [ ] PyFunction wrapper with parameter validation
* [ ] PyAssignment wrapper with type checking
* [ ] Confidantic configuration integration
* [ ] Builder pattern implementation
* [ ] GraphSitter integration utilities
* [ ] Exception hierarchy and error handling
* [ ] Unit tests for all core components
* [ ] Integration tests for GraphSitter compatibility
* [ ] Documentation and usage examples
* [ ] Performance benchmarks established