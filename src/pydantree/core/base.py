from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel, Field, ConfigDict

from ..exceptions import GraphSitterIntegrationError, ValidationError


@runtime_checkable
class GraphSitterEditable(Protocol):
    """Interface for GraphSitter editable nodes."""
    
    def to_source(self) -> str:
        """Generate source code from node."""
        ...
    
    def validate_structure(self) -> bool:
        """Validate node structure."""
        ...


class BaseCodeNode(BaseModel):
    """Root Pydantic model for all code structures.
    
    Wraps GraphSitter editable nodes, providing validation, serialization,
    and type safety for all code structures.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    graphsitter_node: Any = Field(
        description="Underlying GraphSitter node"
    )
    validate_structure: bool = Field(
        default=True, 
        description="Enable structural validation"
    )
    
    @classmethod
    def from_graphsitter(cls, node: Any) -> BaseCodeNode:
        """Create instance from GraphSitter node."""
        if not hasattr(node, 'to_source'):
            raise GraphSitterIntegrationError(
                "Node must have to_source method"
            )
            
        return cls(graphsitter_node=node)
    
    def to_source(self) -> str:
        """Generate Python source code."""
        try:
            return self.graphsitter_node.to_source()
        except Exception as e:
            raise GraphSitterIntegrationError(
                f"Failed to generate source: {e}"
            ) from e
    
    def to_graphsitter(self) -> Any:
        """Export back to GraphSitter format."""
        return self.graphsitter_node
    
    def validate_integrity(self) -> bool:
        """Check structural consistency."""
        if not self.validate_structure:
            return True
            
        try:
            if hasattr(self.graphsitter_node, 'validate_structure'):
                return self.graphsitter_node.validate_structure()
            return True
        except Exception as e:
            raise ValidationError(
                f"Structure validation failed: {e}"
            ) from e
    
    def model_post_init(self, __context: Any) -> None:
        """Validate after model creation."""
        if self.validate_structure and not self.validate_integrity():
            raise ValidationError("Code structure validation failed")
