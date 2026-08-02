"""IR tests: the Grammar model mirrors the real 0.25.3 grammar.json schema and
round-trips structurally."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tsgrammar.grammar import (
    AliasNode,
    BlankNode,
    ChoiceNode,
    FieldNode,
    Grammar,
    ImmediateTokenNode,
    PatternNode,
    PrecDynamicNode,
    PrecLeftNode,
    PrecNode,
    PrecRightNode,
    Repeat1Node,
    RepeatNode,
    ReservedNode,
    SeqNode,
    StrNode,
    SymbolNode,
    TokenNode,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE = REPO_ROOT / ".scratch" / "004-tsgrammar" / "reference" / "grammar.json"

ALL_NODE_TYPES = {
    "SYMBOL", "STRING", "PATTERN", "BLANK", "SEQ", "CHOICE", "REPEAT",
    "REPEAT1", "FIELD", "ALIAS", "TOKEN", "IMMEDIATE_TOKEN",
    "PREC", "PREC_LEFT", "PREC_RIGHT", "PREC_DYNAMIC", "RESERVED",
}


def _norm(d):
    return {k: v for k, v in d.items() if v not in ([], {}, None)}


def test_minimal_grammar_roundtrip():
    g = Grammar.model_validate_json(json.dumps({
        "name": "mini",
        "rules": {
            "source_file": {"type": "REPEAT",
                            "content": {"type": "SYMBOL", "name": "number"}},
            "number": {"type": "PATTERN", "value": r"\d+"},
        },
    }))
    assert g.start_rule == "source_file"
    again = Grammar.model_validate_json(g.model_dump_json())
    assert again == g


def test_all_node_types_instantiate_and_roundtrip():
    """Each node type constructs and serializes with its discriminator."""
    cases = [
        SymbolNode(name="x"),
        StrNode(value=";"),
        PatternNode(value=r"\d+", flags="i"),
        BlankNode(),
        SeqNode(members=[StrNode(value="a")]),
        ChoiceNode(members=[StrNode(value="a"), StrNode(value="b")]),
        RepeatNode(content=StrNode(value="a")),
        Repeat1Node(content=StrNode(value="a")),
        FieldNode(name="f", content=StrNode(value="a")),
        AliasNode(value="t", named=True, content=SymbolNode(name="x")),
        TokenNode(content=StrNode(value="a")),
        ImmediateTokenNode(content=StrNode(value=":")),
        PrecNode(value=1, content=StrNode(value="a")),
        PrecLeftNode(value="name", content=StrNode(value="a")),
        PrecRightNode(value=2, content=StrNode(value="a")),
        PrecDynamicNode(value=1, content=StrNode(value="a")),
        ReservedNode(context_name="ctx", content=StrNode(value="x")),
    ]
    for node in cases:
        d = json.loads(node.model_dump_json())
        assert d["type"] == node.type
        assert type(node).model_validate_json(node.model_dump_json()) == node


def test_precedence_value_accepts_int_or_name():
    """PREC* value is an untagged int|name union."""
    assert PrecNode(value=4, content=BlankNode()).value == 4
    assert PrecNode(value="or", content=BlankNode()).value == "or"
    with pytest.raises(ValidationError):
        PrecDynamicNode(value="or", content=BlankNode())  # dynamic is int-only


@pytest.mark.skipif(not REFERENCE.exists(), reason="reference grammar not checked out")
def test_full_schema_reference_roundtrip():
    """The Experiment-A reference exercises every node type; the IR must import
    it and re-emit it semantically equal."""
    ref = json.loads(REFERENCE.read_text())
    model = Grammar.model_validate_json(json.dumps(ref))

    re_emitted = json.loads(model.model_dump_json(indent=2, exclude_none=True))
    assert _norm(re_emitted) == _norm(ref)

    # node-type audit over the round-tripped output
    types = set()

    def walk(node):
        if isinstance(node, dict):
            if node.get("type"):
                types.add(node["type"])
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(re_emitted)
    assert types == ALL_NODE_TYPES

    # grammar-level surface
    assert model.name == "kitsink"
    assert model.word == "identifier"
    assert model.start_rule == "source_file"
    assert model.precedences == [[StrNode(value="and"), StrNode(value="or")]]
    assert model.conflicts == [["if_stmt"]]
    assert model.externals == [SymbolNode(name="TERM")]
    assert model.inline == ["params", "member"]
    assert model.supertypes == ["statement"]
    assert model.reserved == {
        "global": [StrNode(value="if")],
        "property": [],
    }


def test_start_rule_is_first_entry():
    g = Grammar.model_validate(
        {"name": "s", "rules": {"a": {"type": "BLANK"}, "b": {"type": "BLANK"}}})
    assert g.start_rule == "a"
