from __future__ import annotations

from typing import Any, List, Optional
from pydantic import Field

from .base import BaseCodeNode
from .parameters import PyParameter
from ..exceptions import ValidationError


class PyFunction(BaseCodeNode):
    """Validated function definition wrapper.
    
    Pydantic model for GraphSitter's PyFunction supporting parameter 
    validation and return type checking.
    """
    
    function_name: str = Field(description="Function name")
    parameters: List[PyParameter] = Field(
        default_factory=list, 
        description="Function parameters"
    )
    return_type: Optional[str] = Field(
        None, 
        description="Return type annotation"
    )
    docstring: Optional[str] = Field(
        None, 
        description="Function docstring"
    )
    
    def add_parameter(
        self, 
        name: str, 
        type_hint: Optional[str] = None, 
        default: Any = None
    ) -> None:
        """Add parameter with validation."""
        if any(p.name == name for p in self.parameters):
            raise ValidationError(f"Parameter '{name}' already exists")
            
        param = PyParameter(
            name=name,
            type_hint=type_hint,
            default_value=default
        )
        self.parameters.append(param)
    
    def set_return_type(self, type_str: str) -> None:
        """Set return type annotation."""
        self.return_type = type_str
    
    def set_docstring(self, docstring: str) -> None:
        """Set function docstring."""
        self.docstring = docstring
    
    def get_parameter(self, name: str) -> Optional[PyParameter]:
        """Get parameter by name."""
        return next((p for p in self.parameters if p.name == name), None)
    
    def has_parameter(self, name: str) -> bool:
        """Check if parameter exists."""
        return self.get_parameter(name) is not None
    
    def to_signature(self) -> str:
        """Generate function signature."""
        params_str = ", ".join(p.to_source() for p in self.parameters)
        return_part = f" -> {self.return_type}" if self.return_type else ""
        return f"def {self.function_name}({params_str}){return_part}:"
