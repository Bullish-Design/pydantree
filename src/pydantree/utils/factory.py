from __future__ import annotations

from typing import Any, Union

from ..core.base import BaseCodeNode
from ..core.classes import PyClass  # , PyClassBuilder
from ..core.functions import PyFunction  # , PyFunctionBuilder
from ..core.assignments import PyAssignment
from ..core.builders import PyClassBuilder, PyFunctionBuilder
from ..exceptions import ValidationError


def from_graphsitter(node: Any) -> BaseCodeNode:
    """Create appropriate Pydantic wrapper for GraphSitter node."""
    if not hasattr(node, "to_source"):
        raise ValidationError("Invalid GraphSitter node")

    # Determine node type from GraphSitter node
    node_type = getattr(node, "type", None) or type(node).__name__

    if "Class" in node_type:
        return PyClass.from_graphsitter(node)
    elif "Function" in node_type or "Method" in node_type:
        return PyFunction.from_graphsitter(node)
    elif "Assignment" in node_type:
        return PyAssignment.from_graphsitter(node)
    else:
        return BaseCodeNode.from_graphsitter(node)


def builder_for(node_type: str) -> Union[PyClassBuilder, PyFunctionBuilder]:
    """Factory function for creating builder instances."""
    if node_type.lower() == "class":
        return lambda name: PyClassBuilder(name)
    elif node_type.lower() == "function":
        return lambda name: PyFunctionBuilder(name)
    else:
        raise ValidationError(f"Unsupported builder type: {node_type}")
