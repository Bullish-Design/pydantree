"""Tests for the deliberately small raw tree-sitter query escape hatch."""

from __future__ import annotations

from pathlib import Path

import pytest
import tree_sitter
import tree_sitter_python

from pydantree_sitter import Grammar, Node
from pydantree_sitter.errors import QueryBuildError, SchemaCheckError
from pydantree_sitter.raw import Cursor, Query, RawQuery
from pydantree_sitter.schema import NodeSchema


def _language():
    return tree_sitter.Language(tree_sitter_python.language())


def _grammar():
    schema = NodeSchema.from_node_types_json(
        Path(__file__).parent.parent / "examples/wheel-extract/vendor/python-node-types.json")
    return Grammar.load(_language(), schema)


def test_raw_query_compiles_and_exposes_matches():
    query = Query.raw(
        "(module (expression_statement (assignment "
        "left: (identifier) @name right: (_) @value)))")
    compiled = query.compile(_language())
    assert query.capture_names(_language()) == {"name", "value"}

    tree = tree_sitter.Parser(_language()).parse(b"x = 1\ny = f(2)\n")
    matches = Cursor(compiled, tree).matches()
    assert [(match.text("name"), match.text("value")) for match in matches] == [
        ("x", "1"), ("y", "f(2)")]


def test_raw_query_checks_capture_names():
    query = Query.raw(
        "(module (expression_statement (assignment "
        "left: (identifier) @nope)))")
    with pytest.raises(SchemaCheckError, match="nope"):
        query.check_captures(_language(), {"name"})


def test_raw_query_reports_query_build_errors():
    query = Query.raw("(no_such_kind (identifier) @name)")
    with pytest.raises(QueryBuildError):
        query.compile(_language())


def test_raw_query_supports_multiple_patterns():
    query = Query.raw(
        "(module (expression_statement (assignment "
        "left: (identifier) @name right: (_) @value)))\n"
        "(module (expression_statement (augmented_assignment "
        "left: (identifier) @name right: (_) @value)))")
    tree = tree_sitter.Parser(_language()).parse(b"x = 1\ny += 2\n")
    matches = Cursor(query.compile(_language()), tree).matches()
    assert [(m.text("name"), m.text("value")) for m in matches] == [
        ("x", "1"), ("y", "2")]


def test_raw_query_binds_a_node_subclass_through_grammar_find():
    class Assignment(Node):
        __kind__ = "assignment"
        __raw_query__ = RawQuery(
            "(module (expression_statement (assignment "
            "left: (identifier) @name right: (_) @value)))")
        name: str
        value: str

    rows = _grammar().parse("x = 1\ny = f(2)\n").find(Assignment)
    assert [(row.name, row.value) for row in rows] == [
        ("x", "1"), ("y", "f(2)")]


def test_raw_query_unknown_capture_is_rejected_at_bind():
    class Bad(Node):
        __kind__ = "assignment"
        __raw_query__ = RawQuery("(assignment left: (identifier) @unknown)")
        name: str

    with pytest.raises(SchemaCheckError, match="unknown"):
        _grammar().parse("x = 1\n").find(Bad)
