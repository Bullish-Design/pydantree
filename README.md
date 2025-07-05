# Pydantree

[![PyPI version](badge-url)](pypi-url)
[![Python versions](badge-url)](compatibility-url)
[![License](badge-url)](license-url)

A Pydantic-powered abstraction layer over GraphSitter that treats code as structured data.

Pydantree enables type-safe manipulation, validation, and composition of code structures for generation and transformation workflows. It bridges the gap between raw AST manipulation and type-safe code generation by providing Pydantic models that wrap GraphSitter's parsing capabilities.

## Installation

### Using UV (Recommended)
```bash
uv add pydantree
```

### Using pip
```bash
pip install pydantree
```

### CLI Usage

Pydantree includes a command-line interface for common code generation and analysis tasks:

```bash
# Analyze existing codebase
pydantree analyze myorg/django-project --output analysis.json

# Generate new library structure
pydantree create user-api --template django-api

# Add model to existing project
pydantree add model User --fields "id:UUIDField(primary_key=True)" "email:EmailField(unique=True)"

# Transform existing code
pydantree transform add-type-hints ./src/myproject/

# Validate code structure
pydantree validate ./models.py --strict
```

### CLI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `analyze` | Parse codebase and output structure | `pydantree analyze myrepo/` |
| `create` | Generate new library/module from template | `pydantree create api --template fastapi` |
| `add` | Add components to existing project | `pydantree add model User` |
| `transform` | Apply transformations to existing code | `pydantree transform add-docstrings src/` |
| `validate` | Check code structure integrity | `pydantree validate models.py` |

### Template-Based Generation

```bash
# Create Django project structure
pydantree create ecommerce-api --template django \
  --models Product,Order,Customer \
  --database postgresql

# Generate FastAPI microservice
pydantree create user-service --template fastapi \
  --endpoints users,auth \
  --database mongodb
``` Installation
```bash
git clone https://github.com/user/pydantree.git
cd pydantree
uv sync --dev
```

## Quick Start

```python
from pydantree import PyClass, PyFunction
from graph_sitter import Codebase

# Load existing code with type-safe wrappers
codebase = Codebase.from_repo("myproject/myrepo")
raw_class = codebase.get_class("UserAPI")

# Wrap in Pydantic model for validation
validated_class = PyClass.from_graphsitter(raw_class)
validated_class.add_method("get_user", return_type="User")
print(validated_class.to_source())
```

## Core Concepts

### Key Abstractions
- **BaseCodeNode**: Root Pydantic model wrapping GraphSitter editables. Provides validation, serialization, and type safety for all code structures.
- **PyClass**: Validated wrapper around GraphSitter's PyClass. Enables type-safe class manipulation with builder patterns and structural validation.
- **PyFunction**: Pydantic model for GraphSitter's PyFunction. Supports parameter validation, return type checking, and docstring management.
- **PyAssignment**: Type-safe wrapper for variable assignments with value validation and type inference support.

### Design Philosophy

**Code-as-Data First**: Every code construct becomes a first-class Python object with full type safety and validation.

**Fail-Fast Validation**: Validate code structures immediately upon creation or modification to catch errors early.

**GraphSitter Fidelity**: Maintain full access to underlying GraphSitter capabilities while providing higher-level abstractions.

**Composable Architecture**: Low-level primitives aggregate into high-level semantic concepts through composition over inheritance.

## Usage

### Basic Operations

```python
from pydantree import PyClass, PyFunction
from graph_sitter import Codebase

# Load existing codebase
codebase = Codebase.from_repo("myorg/myproject")

# Wrap GraphSitter classes with Pydantic validation
raw_class = codebase.get_class("DatabaseModel")
validated_class = PyClass.from_graphsitter(raw_class)

# Type-safe mutations with immediate validation
validated_class.add_method("save", return_type="bool")
validated_class.add_attribute("created_at", type_hint="datetime")

# Export validated code
result = validated_class.to_source()
```

### Advanced Features

```python
# Builder pattern for complex construction
api_class = PyClass.builder("UserAPI")\
    .with_base("BaseAPI")\
    .with_methods([
        PyFunction.builder("get_user")\
            .with_param("user_id", "int")\
            .with_return_type("User")\
            .with_docstring("Retrieve user by ID")\
            .build()
    ])\
    .build()

# Functional transformation pipeline
enhanced_code = validated_class\
    .transform(add_type_hints)\
    .transform(add_docstrings)\
    .validate()

# JSON serialization for caching/APIs
serialized = validated_class.model_dump_json()
restored = PyClass.model_validate_json(serialized)
```

### Configuration

```python
from confidantic import PluginRegistry, SettingsType
from pydantic import Field

# Create configuration mixin
class PydantreeSettings(SettingsType):
    validation_strict: bool = Field(default=True, env="PYDANTREE_VALIDATION_STRICT")
    allow_partial_types: bool = Field(default=False, env="PYDANTREE_ALLOW_PARTIAL_TYPES") 
    auto_format_code: bool = Field(default=True, env="PYDANTREE_AUTO_FORMAT")

# Register with Confidantic
PluginRegistry.register(PydantreeSettings)

# Import to get auto-initialized settings
from confidantic import Settings
print(Settings.validation_strict)  # Uses .env files + OS environment
```

### Error Handling

```python
from pydantic import ValidationError
from pydantree.exceptions import CodeStructureError

try:
    invalid_class = PyClass.from_graphsitter(malformed_node)
except ValidationError as e:
    print(f"Validation failed: {e}")
except CodeStructureError as e:
    print(f"Invalid code structure: {e}")
```

## API Reference

### Classes

#### BaseCodeNode
Root Pydantic model for all code structures.

**Parameters:**
- `graphsitter_node` (Editable): The underlying GraphSitter node
- `validate_structure` (bool, default=True): Enable structural validation

**Methods:**
- `from_graphsitter(node)`: Create instance from GraphSitter node
- `to_source()`: Generate Python source code
- `to_graphsitter()`: Export back to GraphSitter format
- `validate_integrity()`: Check structural consistency

#### PyClass
Pydantic wrapper for GraphSitter PyClass with validation.

**Parameters:**
- `class_name` (str): Name of the class
- `base_classes` (List[str], optional): Parent classes
- `docstring` (str, optional): Class docstring

**Methods:**
- `add_method(name, return_type=None)`: Add validated method
- `add_attribute(name, type_hint=None, value=None)`: Add typed attribute
- `get_method(name)`: Retrieve method by name
- `builder(name)`: Create fluent builder instance

**Example:**
```python
user_class = PyClass(
    class_name="User",
    base_classes=["BaseModel"],
    docstring="User model with validation"
)
```

#### PyFunction
Validated function definition wrapper.

**Parameters:**
- `function_name` (str): Function name
- `parameters` (List[PyParameter]): Function parameters
- `return_type` (str, optional): Return type annotation

**Methods:**
- `add_parameter(name, type_hint=None, default=None)`: Add parameter
- `set_return_type(type_str)`: Set return type
- `set_docstring(docstring)`: Update docstring

### Functions

#### builder_for(graphsitter_class)
Factory function for creating builder instances.

**Returns:** Appropriate builder class for the GraphSitter node type

## Architecture

### Overview
Pydantree sits between GraphSitter's AST manipulation and your application code, providing Pydantic validation layer for type safety. GraphSitter handles parsing and incremental computation while Pydantree ensures structural integrity and developer experience.

### Data Flow
1. **Parse**: GraphSitter creates AST from source code
2. **Wrap**: Pydantree wraps GraphSitter nodes in Pydantic models
3. **Validate**: Type checking and structural validation on every operation
4. **Transform**: Type-safe mutations through validated methods
5. **Export**: Generate source code or serialize to JSON

### Extension Points
- **Language Plugins**: Add support for TypeScript, JavaScript via GraphSitter parsers
- **Validation Hooks**: Custom validation rules for domain-specific patterns
- **Transformation Registry**: Pluggable code transformation functions
- **Builder Extensions**: Framework-specific builders (Django models, FastAPI routes)

### Performance Considerations
Leverages GraphSitter's incremental parsing for minimal recomputation. Pydantic validation adds ~10-20% overhead but provides significant safety benefits. Use builder patterns for complex constructions to avoid multiple validation passes.

## Examples

### Use Case 1: Library-Level Code Analysis
```python
from pydantree import Library, Models, Database, Utilities

# Parse existing codebase with composed abstractions
library = Library.from_repo("myorg/django-project")

# Access high-level components
models = library.models  # ModuleBase containing all model files
database = library.database  # FileBase or ModuleBase for DB utilities
utilities = library.utilities  # Collection of utility functions

# Analyze model structure
for model_class in models.classes:
    print(f"Model: {model_class.name}")
    print(f"Fields: {[attr.name for attr in model_class.attributes]}")
    print(f"Methods: {[method.name for method in model_class.methods]}")
```

### Use Case 2: Generating New Project Structure
```python
from pydantree import Library, Models, Database, SettingsBase
from pydantree.fields import UUIDField, EmailField, DateTimeField

# Create new library from scratch
library = Library.create("user-management-api")

# Generate models module with typed field objects
models = Models.create_module("models")
user_model = models.add_class(
    PyClass.builder("User")
    .with_base("BaseModel")
    .with_attributes([
        UUIDField("id", primary_key=True),
        EmailField("email", unique=True),
        DateTimeField("created_at", auto_now_add=True)
    ])
    .build()
)

# Generate database utilities
database = Database.create_file("database.py")
database.add_function(
    PyFunction.builder("get_connection")
    .with_return_type("Connection")
    .with_docstring("Get database connection with retry logic")
    .build()
)

# Add to library
library.add_component(models)
library.add_component(database)

# Generate all files
library.generate_files()
```

### Use Case 3: Mixed Parsing and Generation
```python
from pydantree.fields import ForeignKey, TextField, ImageField

# Parse existing codebase
library = Library.from_repo("myorg/legacy-api")

# Analyze existing models
existing_models = library.models
user_model = existing_models.get_class("User")

# Generate new related model with typed fields
profile_model = PyClass.builder("UserProfile")
    .with_base("BaseModel")
    .with_attributes([
        ForeignKey("user", model=user_model.name, on_delete="CASCADE"),
        TextField("bio", blank=True),
        ImageField("avatar", upload_to="avatars/")
    ])
    .build()

# Add to existing models module
existing_models.add_class(profile_model)

# Generate settings configuration
settings = SettingsBase.create_file("settings.py")
settings.add_import("os")
settings.add_import("pathlib", "Path")
settings.add_assignment("BASE_DIR", "Path(__file__).resolve().parent.parent")
settings.add_assignment("SECRET_KEY", "os.environ.get('SECRET_KEY')")

library.add_component(settings)

# Apply all changes
library.sync_to_filesystem()
```

### Integration Examples
```python
# Django model generation with validation
django_models = Models.create_module("models", framework="django")
user_class = django_models.add_class(
    PyClass.builder("User")
    .with_base("AbstractUser")
    .with_meta_options({"db_table": "users"})
    .build()
)

# FastAPI route generation
api_utilities = Utilities.create_module("api")
user_routes = api_utilities.add_file("user_routes.py")
user_routes.add_function(
    PyFunction.builder("get_user")
    .with_decorators(["@router.get('/users/{user_id}')"])
    .with_param("user_id", "int")
    .with_return_type("UserResponse")
    .build()
)

# Configuration management with Confidantic integration
config = SettingsBase.create_file("config.py")
config.add_confidantic_settings([
    ("DATABASE_URL", "str", "postgresql://localhost/mydb"),
    ("REDIS_URL", "str", "redis://localhost:6379"),
    ("DEBUG", "bool", "False")
])
```

## Development

## Development

### Project Structure
```
pydantree/
├── src/pydantree/
│   ├── __init__.py
│   ├── core/
│   └── utils/
├── tests/
├── docs/
├── pyproject.toml
└── README.md
```

### Running Tests
```bash
uv run pytest
```

### Code Quality
```bash
uv run ruff check
uv run ruff format
uv run mypy src/
```

### Contributing

1. **Development setup**:
```bash
git clone https://github.com/user/pydantree.git
cd pydantree
uv sync --dev
```

2. **Code quality**: All PRs must pass ruff, mypy, and pytest
3. **Testing**: Add tests for new Pydantic wrappers and validation logic
4. **Documentation**: Update API reference for new classes/methods

## Technical Specifications

### Requirements
- Python 3.9+
- `pydantic>=2.7.0` - Core validation and serialization
- `graph-sitter` - AST parsing and manipulation 
- `confidantic>=0.3.0` - Configuration management
- `typing-extensions` - Advanced type hints for Python <3.10

### Performance
- Sub-second parsing and validation for codebases up to 10k LOC
- <100MB memory overhead for typical workflows
- Leverages GraphSitter's incremental computation for efficient updates

### Compatibility
- Works with any GraphSitter-supported language (Python, TypeScript, JavaScript)
- Compatible with Django, FastAPI, Flask for code generation
- Full mypy/pyright type checking support

### Limitations
- Code structure manipulation only (no execution)
- Requires valid GraphSitter AST as input
- Validation overhead for large codebases (10-20% performance impact)
- Memory usage scales with AST complexity