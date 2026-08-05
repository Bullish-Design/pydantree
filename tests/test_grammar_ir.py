"""IR tests: the GrammarModel model mirrors the real 0.25.3 grammar.json schema and
round-trips structurally."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pydantree_sitter_grammar.ir import (
    AliasNode,
    BlankNode,
    ChoiceNode,
    FieldNode,
    GrammarModel,
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
REFERENCE = REPO_ROOT / ".scratch" / "projects" / "004-grammar" / "reference" / "grammar.json"

ALL_NODE_TYPES = {
    "SYMBOL", "STRING", "PATTERN", "BLANK", "SEQ", "CHOICE", "REPEAT",
    "REPEAT1", "FIELD", "ALIAS", "TOKEN", "IMMEDIATE_TOKEN",
    "PREC", "PREC_LEFT", "PREC_RIGHT", "PREC_DYNAMIC", "RESERVED",
}


def _norm(d):
    return {k: v for k, v in d.items() if v not in ([], {}, None)}


def test_minimal_grammar_roundtrip():
    g = GrammarModel.model_validate_json(json.dumps({
        "name": "mini",
        "rules": {
            "source_file": {"type": "REPEAT",
                            "content": {"type": "SYMBOL", "name": "number"}},
            "number": {"type": "PATTERN", "value": r"\d+"},
        },
    }))
    assert g.start_rule == "source_file"
    again = GrammarModel.model_validate_json(g.model_dump_json())
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
    model = GrammarModel.model_validate_json(json.dumps(ref))

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


def test_grammar_level_fields_reject_unknowns():
    with pytest.raises(ValidationError):
        GrammarModel.model_validate_json(json.dumps({
            "name": "s", "rules": {"a": {"type": "BLANK"}},
            "start": "a",  # no such field in 0.25.3
        }))


def test_schema_pointer_key_tolerated():
    """Published grammar.json files carry `$schema`; import must drop it
    while staying strict about everything else."""
    g = GrammarModel.model_validate_json(json.dumps({
        "$schema": "https://example.com/schema.json",
        "name": "s",
        "rules": {"a": {"type": "BLANK"}, "b": {"type": "BLANK"}},
    }))
    assert g.name == "s"
    assert "$schema" not in json.loads(g.model_dump_json())


def test_start_rule_is_first_entry():
    g = GrammarModel.model_validate(
        {"name": "s", "rules": {"a": {"type": "BLANK"}, "b": {"type": "BLANK"}}})
    assert g.start_rule == "a"


COMMUNITY_BASH = REPO_ROOT / ".scratch" / "projects" / "004-grammar" / "community" / "bash" / "grammar.json"


@pytest.mark.skipif(not COMMUNITY_BASH.exists(),
                    reason="community grammar fixture not checked out")
def test_community_bash_roundtrips_semantically():
    """A REAL published grammar (tree-sitter-bash 0.25.1, 101 rules) imports,
    re-emits semantically equal, and the re-emitted form regenerates with the
    stock CLI (exit 0) — the strongest fidelity check available offline."""
    import shutil
    import subprocess

    raw = COMMUNITY_BASH.read_text()
    ref = json.loads(raw)
    ref.pop("$schema", None)
    model = GrammarModel.model_validate_json(raw)
    assert len(model.rules) == 101
    assert model.start_rule == "program"

    re_emitted = json.loads(model.model_dump_json(indent=2, exclude_none=True))
    assert _norm(re_emitted) == _norm(ref)

    if not shutil.which("tree-sitter"):
        pytest.skip("tree-sitter CLI not on PATH")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        json_path = model.emit_bundle(d)
        proc = subprocess.run(
            ["tree-sitter", "generate", str(json_path)],
            capture_output=True, text=True, cwd=d, check=False)
        assert proc.returncode == 0, proc.stderr[-800:]
