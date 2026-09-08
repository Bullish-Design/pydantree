"""Lazy materialization of nested typed nodes."""

import pytest
import tree_sitter
import tree_sitter_json
import tree_sitter_python
from pydantic import ValidationError

from pydantree_sitter import Grammar
from pydantree_sitter.find import find_in
from pydantree_sitter.nodes import Node
from pydantree_sitter.raw import RawQuery
from pydantree_sitter.schema import NodeSchema

PROJECTION_SCHEMA = NodeSchema.from_list([
    {"type": "object", "named": True, "children": {
        "multiple": True, "required": False,
        "types": [{"type": "pair", "named": True}]}},
    {"type": "pair", "named": True, "fields": {
        "key": {"multiple": False, "required": True,
                 "types": [{"type": "string", "named": True}]},
        "value": {"multiple": False, "required": True,
                   "types": [{"type": "string", "named": True}]} }},
    {"type": "string", "named": True},
])


def test_nested_fields_are_lazy_but_scalars_and_spans_are_eager() -> None:
    grammar = Grammar.load(tree_sitter_json.language(), PROJECTION_SCHEMA,
                           verify=False)

    class Config(grammar.nodes.Object):
        entries: dict[str, str]

    tree = grammar.parse('{"a": "b", "c": "d"}')
    raw = tree.root_node.named_children[0]
    eager = Config.resolver()(raw)
    row = tree.find(Config)[0]

    assert row.entries == {"a": "b", "c": "d"}
    assert row.entries == eager["entries"]
    assert "entries" in row.__dict__
    assert "content" not in row.__dict__
    assert set(row._lazy_fields) == {"content"}
    assert row.span.text == '{"a": "b", "c": "d"}'
    assert row.__value__() == '{"a": "b", "c": "d"}'

    content = row.content
    assert [item.__kind__ for item in content] == ["pair", "pair"]
    assert [(item.key.__value__(), item.value.__value__()) for item in content] == [
        (item.key.__value__(), item.value.__value__())
        for item in eager["content"]]
    assert row.content is content
    assert "content" in row.__dict__
    assert not row._lazy_fields

    dumped = row.model_dump()
    assert len(dumped["content"]) == 2


def test_nested_failure_is_local_and_cached() -> None:
    grammar = Grammar.load(tree_sitter_json.language(), PROJECTION_SCHEMA,
                           verify=False)

    class Leaf(Node):
        __kind__ = "leaf"

    class BrokenChild(Node):
        __kind__ = "pair"
        missing: Leaf

    class BrokenParent(Node):
        __kind__ = "object"
        content: BrokenChild

    raw = grammar.parse('{"a": "b"}').root_node
    row = find_in(raw, BrokenParent)[0]
    assert row.span.text == '{"a": "b"}'
    assert row.__value__() == '{"a": "b"}'

    with pytest.raises(ValidationError) as first:
        _ = row.content
    with pytest.raises(ValidationError) as second:
        _ = row.content
    assert second.value is first.value


def test_raw_query_nested_fields_are_lazy_too() -> None:
    language = tree_sitter.Language(tree_sitter_python.language())
    raw = tree_sitter.Parser(language).parse(b"answer = f()\n").root_node

    class Call(Node):
        __kind__ = "call"

    class Assignment(Node):
        __kind__ = "assignment"
        __raw_query__ = RawQuery("(assignment right: (call) @right)")
        right: Call

    row = find_in(raw, Assignment, language)[0]
    assert "right" not in row.__dict__
    assert set(row._lazy_fields) == {"right"}
    assert row.right.__kind__ == "call"
    assert not row._lazy_fields
