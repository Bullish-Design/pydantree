from __future__ import annotations

from typing import Any, Optional
from pydantic import Field

from .base import BaseCodeNode
from ..exceptions import ValidationError


class PyAssignment(BaseCodeNode):
    """Type-safe wrapper for variable assignments.

    Provides value validation and type inference for variable assignments
    with support for type hints and value consistency checking.
    """

    variable_name: str = Field(description="Variable name")
    value: Any = Field(description="Assigned value")
    type_hint: Optional[str] = Field(None, description="Type annotation")

    def set_value(self, value: Any) -> None:
        """Set assignment value with validation."""
        self.value = value

    def set_type_annotation(self, type_str: str) -> None:
        """Set type annotation for assignment."""
        self.type_hint = type_str

    def to_assignment(self) -> str:
        """Generate assignment source code."""
        parts = [self.variable_name]

        if self.type_hint:
            parts.append(f": {self.type_hint}")

        parts.append(f" = {self.value}")

        return "".join(parts)

    def validate_type_consistency(self) -> bool:
        """Validate value consistency with type hints."""
        if not self.type_hint:
            return True

        # Basic type checking - can be extended
        try:
            if self.type_hint == "str" and not isinstance(self.value, str):
                return False
            if self.type_hint == "int" and not isinstance(self.value, int):
                return False
            if self.type_hint == "bool" and not isinstance(self.value, bool):
                return False
            return True
        except Exception:
            return False

    def model_post_init(self, __context: Any) -> None:
        """Validate after model creation."""
        super().model_post_init(__context)

        if not self.validate_type_consistency():
            raise ValidationError(
                f"Value type doesn't match hint on variable '{self.variable_name}' ==> Value '{self.value}' is not of type '{self.type_hint}'"
            )
