import pytest

from pydantree.core.nodes import TSNode
from pydantree.processing.collections import NodeGroup, from_tree, PredicateSelector


def test_nodegroup_creation_from_tree(parsed_python_ast: TSNode):
    """Tests creating a NodeGroup from a full AST."""
    group = from_tree(parsed_python_ast)
    assert isinstance(group, NodeGroup)
    # The group should contain the root node + all descendants
    assert len(group) == len(list(parsed_python_ast.descendants())) + 1


def test_nodegroup_filtering(parsed_python_ast: TSNode):
    """Tests various filtering methods on a NodeGroup."""
    group = from_tree(parsed_python_ast)

    # Filter by a single type
    identifiers = group.filter_type("identifier")
    assert len(identifiers) > 10
    assert all(node.type_name == "identifier" for node in identifiers)

    # Filter by multiple types
    defs = group.filter_type({"class_definition", "function_definition"})
    assert len(defs) == 3  # MyClass, __init__, greet, my_function (Note: __init__ is a function_definition)
    # Actually, __init__ and greet are inside the class, so there are 4
    # Let's adjust based on the sample code. MyClass, def __init__, def greet, def my_function
    all_defs = parsed_python_ast.find_all_by_type({"class_definition", "function_definition"})
    assert len(defs) == len(all_defs)


def test_nodegroup_chaining_filters(parsed_python_ast: TSNode):
    """Tests chaining multiple filter operations."""
    group = from_tree(parsed_python_ast)
    greet_method_id = group.filter_type("function_definition").where(lambda node: "greet" in node.text)
    assert len(greet_method_id) == 1
    assert greet_method_id.to_list()[0].child_by_field_name("name").text == "greet"


def test_nodegroup_set_operations(parsed_python_ast: TSNode):
    """Tests union, intersection, and difference operations."""
    group = from_tree(parsed_python_ast)
    identifiers = group.filter_type("identifier")
    strings = group.filter_type("string")
    decorators = group.filter_type("decorator")  # This is empty in our sample

    # Union
    id_and_strings = identifiers.union(strings)
    assert len(id_and_strings) == len(identifiers) + len(strings)

    # Intersection (should be empty)
    common = identifiers.intersection(strings)
    assert len(common) == 0

    # Difference
    ids_not_in_union = id_and_strings.difference(strings)
    assert len(ids_not_in_union) == len(identifiers)


def test_nodegroup_grouping(parsed_python_ast: TSNode):
    """Tests the groupby functionality."""
    group = from_tree(parsed_python_ast)

    # Group all nodes by their type name
    grouped_by_type = group.groupby("type_name")
    assert isinstance(grouped_by_type, dict)
    assert "class_definition" in grouped_by_type
    assert "identifier" in grouped_by_type
    assert isinstance(grouped_by_type["identifier"], NodeGroup)
    assert len(grouped_by_type["identifier"]) > 10
