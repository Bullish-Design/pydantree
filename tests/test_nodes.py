"""Phase-1 tests for the additive typed-node-universe core."""

from pathlib import Path
from typing import Literal

import pytest
import tree_sitter_json

from pydantree_sitter import Grammar
from pydantree_sitter.errors import SchemaCheckError
from pydantree_sitter.nodes import GAP, Node, PathStep, normalize_under
from pydantree_sitter.schema import NodeSchema
from pydantree_sitter.span import Span


class Leaf(Node):
    __kind__ = "leaf"


class OtherLeaf(Node):
    __kind__ = "other_leaf"


class Shape(Node):
    left: Leaf
    maybe: Leaf | None
    items: list[Leaf]
    choice: Leaf | OtherLeaf
    token: Literal["="]
    text: str


def _json_schema() -> NodeSchema:
    return NodeSchema.from_node_types_json(
        Path(__file__).parent / "fixtures/jsonlike/node-types.json")


def _schema_model(name: str, annotations: dict[str, object]):
    return NodeMetaTest(name, annotations)


def NodeMetaTest(name: str, annotations: dict[str, object]):
    return type(
        name,
        (Node,),
        {
            "__module__": __name__,
            "__kind__": "pair",
            "__schema__": _json_schema(),
            "__annotations__": annotations,
        },
    )


def test_annotation_grammar_records_children_and_shape() -> None:
    by_name = {child.name: child for child in Shape.__children__}

    assert by_name["left"].kinds == ("leaf",)
    assert not by_name["left"].optional
    assert by_name["maybe"].kinds == ("leaf",)
    assert by_name["maybe"].optional
    assert by_name["items"].kinds == ("leaf",)
    assert by_name["items"].repeated
    assert by_name["choice"].kinds == ("leaf", "other_leaf")
    assert by_name["token"].literal == "="
    assert by_name["text"].kinds == ()


def test_schema_checks_reject_unknown_field_kind_and_shape() -> None:
    with pytest.raises(SchemaCheckError, match="missing"):
        _schema_model("MissingField", {"missing": str})
    with pytest.raises(SchemaCheckError, match="declared kinds"):
        _schema_model("WrongKind", {"key": Leaf})
    with pytest.raises(SchemaCheckError, match="optionality"):
        _schema_model("WrongOptional", {"key": str | None})
    with pytest.raises(SchemaCheckError, match="repetition"):
        _schema_model("WrongRepeated", {"key": list[str]})


def test_schema_checked_scalar_fields_can_resolve_text() -> None:
    Pair = _schema_model("Pair", {"key": str, "value": str})
    tree = Grammar.load(tree_sitter_json.language(), _json_schema(),
                        verify=False).parse(
        b'{"key": "value"}')
    pair = tree.root_node.named_children[0].named_children[0]

    assert Pair.resolver()(pair) == {"key": '"key"', "value": '"value"'}
    materialized = Pair.from_node(pair)
    assert materialized.key == '"key"'
    assert materialized.value == '"value"'
    assert materialized.__value__() == '"key": "value"'
    expected_span = Span.from_node(pair)
    assert materialized.span.line == expected_span.line
    assert materialized.span.text == expected_span.text


def test_under_normalization_builds_typed_path_steps() -> None:
    class Module(Node):
        __kind__ = "module"

    class Function(Node):
        __kind__ = "function"

    expected = (PathStep(("module",)), GAP, PathStep(("function",)))
    assert normalize_under((Module, Ellipsis, Function)) == expected
