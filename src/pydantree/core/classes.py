from __future__ import annotations

from typing import Any, List, Optional
from pydantic import Field

from .base import BaseCodeNode
from .functions import PyFunction
from ..exceptions import ValidationError


class PyClass(BaseCodeNode):
    """Pydantic wrapper for GraphSitter PyClass with validation.
    
    Validates class structure on creation, supports adding/removing 
    methods with validation, and manages attributes with type hints.
    """
    
    class_name: str = Field(description="Name of the class")
    base_classes: List[str] = Field(
        default_factory=list, 
        description="Parent classes"
    )
    docstring: Optional[str] = Field(
        None, 
        description="Class docstring"
    )
    methods: List[PyFunction] = Field(
        default_factory=list,
        description="Class methods"
    )
    attributes: List[str] = Field(
        default_factory=list,
        description="Class attributes"
    )
    
    def add_method(
        self, 
        name: str, 
        return_type: Optional[str] = None
    ) -> PyFunction:
        """Add validated method to class."""
        if self.has_method(name):
            raise ValidationError(f"Method '{name}' already exists")
            
        method = PyFunction(
            graphsitter_node=None,  # Will be populated by GraphSitter
            function_name=name,
            return_type=return_type
        )
        self.methods.append(method)
        return method
    
    def add_attribute(
        self, 
        name: str, 
        type_hint: Optional[str] = None, 
        value: Any = None
    ) -> None:
        """Add typed attribute to class."""
        if name in self.attributes:
            raise ValidationError(f"Attribute '{name}' already exists")
            
        attr_str = name
        if type_hint:
            attr_str += f": {type_hint}"
        if value is not None:
            attr_str += f" = {value}"
            
        self.attributes.append(attr_str)
    
    def get_method(self, name: str) -> Optional[PyFunction]:
        """Retrieve method by name."""
        return next(
            (m for m in self.methods if m.function_name == name), 
            None
        )
    
    def has_method(self, name: str) -> bool:
        """Check if method exists."""
        return self.get_method(name) is not None
    
    def has_attribute(self, name: str) -> bool:
        """Check if attribute exists."""
        return any(name in attr for attr in self.attributes)
    
    def set_docstring(self, docstring: str) -> None:
        """Set class docstring."""
        self.docstring = docstring
    
    def to_class_definition(self) -> str:
        """Generate class definition source."""
        bases_str = ""
        if self.base_classes:
            bases_str = f"({', '.join(self.base_classes)})"
            
        return f"class {self.class_name}{bases_str}:"
