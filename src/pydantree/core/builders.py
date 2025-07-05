from __future__ import annotations

from typing import Any, List, Optional

from .classes import PyClass
from .functions import PyFunction
from .parameters import PyParameter
from ..exceptions import BuilderError


class PyFunctionBuilder:
    """Fluent builder for PyFunction objects."""
    
    def __init__(self, name: str) -> None:
        self._name = name
        self._parameters: List[PyParameter] = []
        self._return_type: Optional[str] = None
        self._docstring: Optional[str] = None
    
    def with_param(
        self, 
        name: str, 
        type_hint: Optional[str] = None,
        default: Any = None
    ) -> PyFunctionBuilder:
        """Add parameter to function."""
        param = PyParameter(
            name=name,
            type_hint=type_hint,
            default_value=default
        )
        self._parameters.append(param)
        return self
    
    def with_return_type(self, type_str: str) -> PyFunctionBuilder:
        """Set return type annotation."""
        self._return_type = type_str
        return self
    
    def with_docstring(self, docstring: str) -> PyFunctionBuilder:
        """Set function docstring."""
        self._docstring = docstring
        return self
    
    def build(self) -> PyFunction:
        """Build the PyFunction instance."""
        if not self._name:
            raise BuilderError("Function name is required")
            
        func = PyFunction(
            graphsitter_node=None,  # Will be populated by GraphSitter
            function_name=self._name,
            parameters=self._parameters,
            return_type=self._return_type,
            docstring=self._docstring
        )
        return func


class PyClassBuilder:
    """Fluent builder for PyClass objects."""
    
    def __init__(self, name: str) -> None:
        self._name = name
        self._bases: List[str] = []
        self._methods: List[PyFunction] = []
        self._attributes: List[str] = []
        self._docstring: Optional[str] = None
    
    def with_base(self, base_class: str) -> PyClassBuilder:
        """Add base class."""
        self._bases.append(base_class)
        return self
    
    def with_bases(self, base_classes: List[str]) -> PyClassBuilder:
        """Add multiple base classes."""
        self._bases.extend(base_classes)
        return self
    
    def with_method(self, method: PyFunction) -> PyClassBuilder:
        """Add method to class."""
        self._methods.append(method)
        return self
    
    def with_methods(self, methods: List[PyFunction]) -> PyClassBuilder:
        """Add multiple methods."""
        self._methods.extend(methods)
        return self
    
    def with_attribute(
        self, 
        name: str, 
        type_hint: Optional[str] = None,
        value: Any = None
    ) -> PyClassBuilder:
        """Add attribute to class."""
        attr_str = name
        if type_hint:
            attr_str += f": {type_hint}"
        if value is not None:
            attr_str += f" = {value}"
        self._attributes.append(attr_str)
        return self
    
    def with_docstring(self, docstring: str) -> PyClassBuilder:
        """Set class docstring."""
        self._docstring = docstring
        return self
    
    def build(self) -> PyClass:
        """Build the PyClass instance."""
        if not self._name:
            raise BuilderError("Class name is required")
            
        cls = PyClass(
            graphsitter_node=None,  # Will be populated by GraphSitter
            class_name=self._name,
            base_classes=self._bases,
            methods=self._methods,
            attributes=self._attributes,
            docstring=self._docstring
        )
        return cls
