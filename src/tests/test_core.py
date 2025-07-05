from __future__ import annotations

import pytest
from unittest.mock import Mock

from pydantree.core.base import BaseCodeNode
from pydantree.core.classes import PyClass
from pydantree.core.functions import PyFunction
from pydantree.core.assignments import PyAssignment
from pydantree.core.parameters import PyParameter
from pydantree.exceptions import ValidationError


class TestBaseCodeNode:
    
    def test_from_graphsitter_with_valid_node(self):
        """Test BaseCodeNode creation from valid GraphSitter node."""
        mock_node = Mock()
        mock_node.to_source.return_value = "test code"
        
        node = BaseCodeNode.from_graphsitter(mock_node)
        
        assert node.graphsitter_node == mock_node
        assert node.to_source() == "test code"
    
    def test_from_graphsitter_with_invalid_node(self):
        """Test error handling for invalid GraphSitter nodes."""
        mock_node = Mock(spec=[])  # No to_source method
        
        with pytest.raises(Exception):
            BaseCodeNode.from_graphsitter(mock_node)


class TestPyClass:
    
    def test_add_method_with_valid_signature(self):
        """Test method addition with type validation."""
        cls = PyClass(
            graphsitter_node=None,
            class_name="TestClass"
        )
        
        method = cls.add_method("test_method", return_type="str")
        
        assert method.function_name == "test_method"
        assert method.return_type == "str"
        assert cls.has_method("test_method")
    
    def test_add_duplicate_method_raises_error(self):
        """Test error handling for duplicate methods."""
        cls = PyClass(
            graphsitter_node=None,
            class_name="TestClass"
        )
        cls.add_method("test_method")
        
        with pytest.raises(ValidationError):
            cls.add_method("test_method")
    
    def test_add_attribute(self):
        """Test attribute addition."""
        cls = PyClass(
            graphsitter_node=None,
            class_name="TestClass"
        )
        
        cls.add_attribute("attr1", type_hint="int", value=42)
        
        assert cls.has_attribute("attr1")
        assert "attr1: int = 42" in cls.attributes


class TestPyFunction:
    
    def test_add_parameter(self):
        """Test parameter addition."""
        func = PyFunction(
            graphsitter_node=None,
            function_name="test_func"
        )
        
        func.add_parameter("param1", "int", default=0)
        
        assert len(func.parameters) == 1
        assert func.parameters[0].name == "param1"
        assert func.parameters[0].type_hint == "int"
        assert func.parameters[0].default_value == 0
    
    def test_duplicate_parameter_raises_error(self):
        """Test error handling for duplicate parameters."""
        func = PyFunction(
            graphsitter_node=None,
            function_name="test_func"
        )
        func.add_parameter("param1")
        
        with pytest.raises(ValidationError):
            func.add_parameter("param1")


class TestPyAssignment:
    
    def test_valid_assignment(self):
        """Test valid assignment creation."""
        assignment = PyAssignment(
            graphsitter_node=None,
            variable_name="test_var",
            value="hello",
            type_hint="str"
        )
        
        assert assignment.variable_name == "test_var"
        assert assignment.value == "hello"
        assert assignment.type_hint == "str"
    
    def test_type_consistency_validation(self):
        """Test type consistency validation."""
        with pytest.raises(ValidationError):
            PyAssignment(
                graphsitter_node=None,
                variable_name="test_var",
                value=42,  # int value
                type_hint="str"  # but str type hint
            )
