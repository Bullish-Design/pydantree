import pytest

from pydantree.languages.base import Language, SemanticRole, SemanticNode, get_language
from pydantree.core.nodes import TSNode


def test_language_factory():
    """Tests the ability to get a language-specific service instance."""
    py_lang = get_language("python")
    assert isinstance(py_lang, Language)
    assert py_lang.name == "python"
    assert py_lang.analyzer is not None
    assert py_lang.parser is not None


def test_python_semantic_analysis_function(python_language: Language, parsed_python_ast: TSNode):
    """Tests the semantic analysis of a Python function."""
    semantic_tree = python_language.analyzer.analyze_semantics(parsed_python_ast)
    assert semantic_tree.role == SemanticRole.MODULE

    # Find the function 'my_function'
    func_sem_node = None
    for child in semantic_tree.children:
        if child.role == SemanticRole.FUNCTION and child.name == "my_function":
            func_sem_node = child
            break

    assert func_sem_node is not None
    assert func_sem_node.role == SemanticRole.FUNCTION
    assert func_sem_node.name == "my_function"
    assert func_sem_node.docstring == "A simple function."
    assert func_sem_node.parent_scope == semantic_tree


def test_python_semantic_analysis_class(python_language: Language, parsed_python_ast: TSNode):
    """Tests the semantic analysis of a Python class and its methods."""
    semantic_tree = python_language.analyzer.analyze_semantics(parsed_python_ast)

    # Find the class 'MyClass'
    class_sem_node = next(
        (c for c in semantic_tree.children if c.role == SemanticRole.CLASS and c.name == "MyClass"), None
    )

    assert class_sem_node is not None
    assert class_sem_node.role == SemanticRole.CLASS
    assert class_sem_node.name == "MyClass"
    assert class_sem_node.docstring == "A sample class with a method."

    # Find the 'greet' method within the class
    greet_method_node = next(
        (m for m in class_sem_node.children if m.role == SemanticRole.FUNCTION and m.name == "greet"), None
    )
    assert greet_method_node is not None
    assert greet_method_node.name == "greet"
    assert greet_method_node.docstring == "Returns a greeting string."
    assert greet_method_node.parent_scope == class_sem_node


def test_python_extract_definitions(python_language: Language, parsed_python_ast: TSNode):
    """Tests the extraction of top-level definitions."""
    definitions = python_language.analyzer.extract_definitions(parsed_python_ast)
    assert len(definitions) == 2  # MyClass and my_function

    def_names = {d.name for d in definitions}
    assert "MyClass" in def_names
    assert "my_function" in def_names

    class_def = next(d for d in definitions if d.name == "MyClass")
    assert class_def.role == SemanticRole.CLASS
