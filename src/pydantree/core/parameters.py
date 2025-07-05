from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class PyParameter(BaseModel):
    """Function parameter with type information."""
    
    name: str = Field(description="Parameter name")
    type_hint: Optional[str] = Field(
        None, 
        description="Type annotation"
    )
    default_value: Any = Field(
        None, 
        description="Default value"
    )
    is_required: bool = Field(
        True, 
        description="Whether parameter is required"
    )
    
    def model_post_init(self, __context: Any) -> None:
        """Set required flag based on default value."""
        if self.default_value is not None:
            self.is_required = False
    
    def to_source(self) -> str:
        """Generate parameter source code."""
        parts = [self.name]
        
        if self.type_hint:
            parts.append(f": {self.type_hint}")
            
        if self.default_value is not None:
            parts.append(f" = {self.default_value}")
            
        return "".join(parts)
