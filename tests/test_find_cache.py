"""Regression tests for the per-class, per-language raw-query cache."""

from __future__ import annotations

from pathlib import Path

import tree_sitter
import tree_sitter_python

from pydantree_sitter import Grammar, Node
from pydantree_sitter.find import _QUERY_CACHE
from pydantree_sitter.raw import Query, RawQuery
from pydantree_sitter.schema import NodeSchema

SCHEMA = NodeSchema.from_node_types_json(
    Path(__file__).parents[1] / "examples/wheel-extract/vendor/python-node-types.json")


def _grammar() -> Grammar:
    language = tree_sitter.Language(tree_sitter_python.language())
    return Grammar.load(language, SCHEMA)


def test_raw_query_compiles_once_per_class_and_language(monkeypatch):
    grammar = _grammar()

    class Assignment(Node):
        __kind__ = "assignment"
        __raw_query__ = RawQuery(
            "(assignment left: (identifier) @left right: (_) @right)")
        left: str
        right: str

    calls = 0
    original = Query.compile

    def counted(self, language):
        nonlocal calls
        calls += 1
        return original(self, language)

    _QUERY_CACHE.clear()
    monkeypatch.setattr(Query, "compile", counted)
    try:
        first = grammar.parse("a = 1\n").find(Assignment)
        second = grammar.parse("b = 2\n").find(Assignment)
    finally:
        _QUERY_CACHE.clear()

    assert [(row.left, row.right) for row in first + second] == [
        ("a", "1"), ("b", "2")]
    assert calls == 1
