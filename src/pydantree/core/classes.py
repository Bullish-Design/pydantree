from __future__ import annotations


import ast
import re
import textwrap

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
    base_classes: List[str] = Field(default_factory=list, description="Parent classes")
    docstring: Optional[str] = Field(None, description="Class docstring")
    methods: List[PyFunction] = Field(default_factory=list, description="Class methods")
    attributes: List[str] = Field(default_factory=list, description="Class attributes")

    def add_method(self, name: str, return_type: Optional[str] = None) -> PyFunction:
        """Add validated method to class."""
        if self.has_method(name):
            raise ValidationError(f"Method '{name}' already exists")

        method = PyFunction(
            graphsitter_node=None,  # Will be populated by GraphSitter
            function_name=name,
            return_type=return_type,
        )
        self.methods.append(method)
        return method

    def add_attribute(
        self, name: str, type_hint: Optional[str] = None, value: Any = None
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
        return next((m for m in self.methods if m.function_name == name), None)

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

    @classmethod
    def from_graphsitter(cls, node: GraphSitterEditable) -> "PyClass":  # noqa: D401
        """Create a :class:`PyClass` by introspecting the given node.

        1. **Validates** that the incoming object implements
           ``to_source`` (GraphSitter integration contract).
        2. Uses a *single* regex pass to locate the ``class`` header line
           and capture:

           * **class name** – mandatory.
           * **base‑class list** – optional, comma‑separated.
        3. Falls back to *AST parsing* (via :pymod:`ast`) to extract the
           first‑level class docstring in a robust, version‑independent
           way.  Errors here are swallowed because a missing docstring
           should never block object creation.
        4. Returns a fully‑populated :class:`PyClass` instance that
           **always** contains at least ``class_name``.

        Any additional validation (naming conventions, reserved words,
        etc.) is delegated to existing Pydantic field validators.
        """

        # 1) Basic contract enforcement -------------------------------------------------
        if not hasattr(node, "to_source"):
            raise GraphSitterIntegrationError("Node must implement to_source()")

        source: str = node.to_source()

        # 2) Regex‑based header extraction ---------------------------------------------
        header_pat = re.compile(
            r"^class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
            r"(?:\((?P<bases>[^)]*)\))?\s*:",
            re.MULTILINE,
        )
        header_match = header_pat.search(source)
        if header_match is None:
            raise ValidationError(
                "Unable to locate Python class definition in node source"
            )

        class_name: str = header_match.group("name")
        bases_raw: Optional[str] = header_match.group("bases")
        base_classes: List[str] = (
            [b.strip() for b in bases_raw.split(",") if b.strip()] if bases_raw else []
        )

        # 3) AST‑based docstring extraction --------------------------------------------
        docstring: Optional[str] = None
        try:
            mod_ast = ast.parse(textwrap.dedent(source))
            if mod_ast.body and isinstance(mod_ast.body[0], ast.ClassDef):
                docstring = ast.get_docstring(mod_ast.body[0])
        except Exception:  # pragma: no cover – non‑fatal diagnostics only
            docstring = None

        # 4) Build and return the validated model --------------------------------------
        return cls(
            graphsitter_node=node,
            class_name=class_name,
            base_classes=base_classes,
            docstring=docstring,
        )
