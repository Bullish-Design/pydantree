from __future__ import annotations

import pytest

from pydantree.core.builders import PyClassBuilder, PyFunctionBuilder
from pydantree.exceptions import BuilderError


class TestPyFunctionBuilder:
    
    def test_basic_function_build(self):
        """Test basic function builder."""
        func = PyFunctionBuilder("test_func")\
            .with_param("param1", "int")\
            .with_return_type("str")\
            .build()
        
        assert func.function_name == "test_func"
        assert len(func.parameters) == 1
        assert func.parameters[0].name == "param1"
        assert func.return_type == "str"
    
    def test_function_with_docstring(self):
        """Test function builder with docstring."""
        func = PyFunctionBuilder("test_func")\
            .with_docstring("Test function")\
            .build()
        
        assert func.docstring == "Test function"
    
    def test_empty_name_raises_error(self):
        """Test error handling for empty function name."""
        with pytest.raises(BuilderError):
            PyFunctionBuilder("").build()


class TestPyClassBuilder:
    
    def test_basic_class_build(self):
        """Test basic class builder."""
        cls = PyClassBuilder("TestClass")\
            .with_base("BaseClass")\
            .with_attribute("attr1", "int", 42)\
            .build()
        
        assert cls.class_name == "TestClass"
        assert "BaseClass" in cls.base_classes
        assert len(cls.attributes) == 1
    
    def test_class_with_method(self):
        """Test class builder with method."""
        method = PyFunctionBuilder("test_method").build()
        
        cls = PyClassBuilder("TestClass")\
            .with_method(method)\
            .build()
        
        assert len(cls.methods) == 1
        assert cls.methods[0].function_name == "test_method"
    
    def test_empty_name_raises_error(self):
        """Test error handling for empty class name."""
        with pytest.raises(BuilderError):
            PyClassBuilder("").build()


class TestBuilderChaining:
    
    def test_complex_class_build(self):
        """Test complex class with multiple components."""
        method1 = PyFunctionBuilder("method1")\
            .with_param("self")\
            .with_param("x", "int")\
            .with_return_type("str")\
            .build()
        
        method2 = PyFunctionBuilder("method2")\
            .with_param("self")\
            .build()
        
        cls = PyClassBuilder("ComplexClass")\
            .with_bases(["BaseClass", "MixinClass"])\
            .with_method(method1)\
            .with_method(method2)\
            .with_attribute("attr1", "str", '"default"')\
            .with_attribute("attr2", "int")\
            .with_docstring("Complex test class")\
            .build()
        
        assert cls.class_name == "ComplexClass"
        assert len(cls.base_classes) == 2
        assert len(cls.methods) == 2
        assert len(cls.attributes) == 2
        assert cls.docstring == "Complex test class"
