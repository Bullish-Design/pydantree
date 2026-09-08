"""D12: the Product B and Product A directions share one child declaration."""

from typing import Literal

from pydantree_sitter.generate import build_namespace
from pydantree_sitter.schema import NodeSchema
from pydantree_sitter_grammar import Rule, assemble


def _schema() -> NodeSchema:
    return NodeSchema.from_list([
        {"type": "root", "named": True, "fields": {
            "pair": {"multiple": False, "required": False,
                      "types": [{"type": "pair", "named": True}]}}},
        {"type": "pair", "named": True, "fields": {
            "key": {"multiple": False, "required": True,
                    "types": [{"type": "leaf", "named": True}]},
            "value": {"multiple": False, "required": True,
                      "types": [{"type": "leaf", "named": True}]},
            "eq": {"multiple": False, "required": True,
                   "types": [{"type": "=", "named": False}]} }},
        {"type": "leaf", "named": True},
    ])


def _signature(cls) -> tuple:
    return tuple(sorted(
        (child.name, child.kinds, child.optional, child.repeated,
         child.literal) for child in cls.__children__))


def test_authored_rules_and_generated_nodes_have_equal_child_shapes() -> None:
    class Leaf(Rule):
        __pattern__ = r"[a-z]+"

    class Pair(Rule):
        key: Leaf
        eq: Literal["="] = "="
        value: Leaf

    class Root(Rule):
        pair: Pair | None

    # Assembly is deliberately part of this test: the forward direction must
    # remain a valid grammar declaration before its schema is consumed.
    assemble("roundtrip", start=Root, rules=[Leaf, Pair, Root])
    generated = build_namespace(_schema())

    assert _signature(Pair) == _signature(generated.Pair)
    assert _signature(Root) == _signature(generated.Root)
