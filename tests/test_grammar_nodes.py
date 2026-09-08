"""The Phase-4 typed tree seam, exercised before query extraction lands."""

from pathlib import Path
from typing import Annotated

import pytest
import tree_sitter_json
import tree_sitter_python

from pydantree_sitter import Grammar
from pydantree_sitter.errors import SchemaDriftError, ShapeError
from pydantree_sitter.nodes import Matches
from pydantree_sitter.schema import NodeSchema

SCHEMA = NodeSchema.from_node_types_json(
    Path(__file__).parent / "fixtures/jsonlike/node-types.json")

PROJECTION_SCHEMA = NodeSchema.from_list([
    {"type": "object", "named": True, "children": {
        "multiple": True, "required": False,
        "types": [{"type": "pair", "named": True}]}},
    {"type": "pair", "named": True, "fields": {
        "key": {"multiple": False, "required": True,
                 "types": [{"type": "string", "named": True}]},
        "value": {"multiple": False, "required": True,
                   "types": [{"type": "string", "named": True}]}}},
    {"type": "string", "named": True},
])


def test_grammar_requires_schema_and_finds_node_subclasses() -> None:
    with pytest.raises(TypeError):
        Grammar.load(tree_sitter_json.language())
    with pytest.raises(TypeError, match="requires a node schema"):
        Grammar.load(tree_sitter_json.language(), None)

    grammar = Grammar.load(tree_sitter_json.language(), SCHEMA, verify=False)

    class Pair(grammar.nodes.Pair):
        key: str
        value: str

    rows = grammar.parse('{"key": "value"}').find(Pair)
    assert [(row.key, row.value) for row in rows] == [
        ('"key"', '"value"')]


def test_grammar_can_name_a_schema_file_for_drift_check() -> None:
    with pytest.raises(SchemaDriftError, match="rust.*json"):
        Grammar.load(tree_sitter_python.language(),
                     Path(__file__).parent / "fixtures/rust/node-types.json",
                     schema_name="rust", verify=False)


def test_grammar_fingerprint_rejects_drift() -> None:
    grammar = Grammar.load(tree_sitter_json.language(), SCHEMA, verify=False)
    with pytest.raises(SchemaDriftError):
        grammar.check_fingerprint(("different",))


def test_dict_projection_and_nested_content_use_one_resolver() -> None:
    grammar = Grammar.load(tree_sitter_json.language(), PROJECTION_SCHEMA,
                           verify=False)

    class Config(grammar.nodes.Object):
        entries: dict[str, str]

    rows = grammar.parse('{"a": "b", "c": "d"}').find(Config)
    assert [row.entries for row in rows] == [{"a": "b", "c": "d"}]
    assert [item.__kind__ for item in rows[0].content] == ["pair", "pair"]


def test_dict_projection_rejects_ambiguous_candidates() -> None:
    schema = NodeSchema.from_list([
        {"type": "object", "named": True, "children": {
            "multiple": True, "required": False,
            "types": [{"type": "first_pair", "named": True},
                      {"type": "second_pair", "named": True}]}},
        *[
            {"type": kind, "named": True, "fields": {
                "key": {"multiple": False, "required": True, "types": []},
                "value": {"multiple": False, "required": True,
                           "types": []}}}
            for kind in ("first_pair", "second_pair")
        ],
    ])
    from pydantree_sitter.generate import build_namespace
    nodes = build_namespace(schema)
    with pytest.raises(ShapeError, match="first_pair.*second_pair"):
        type("Projection", (nodes.Object,),
             {"__annotations__": {"values": dict[str, str]}})


def test_annotated_predicate_filters_required_and_optional_fields() -> None:
    grammar = Grammar.load(tree_sitter_json.language(), SCHEMA, verify=False)

    class Pair(grammar.nodes.Pair):
        key: Annotated[str, Matches(r'"alice"')]
        value: str

    rows = grammar.parse('{"alice": 1, "bob": 2}').find(Pair)
    assert [(row.key, row.value) for row in rows] == [("\"alice\"", "1")]
