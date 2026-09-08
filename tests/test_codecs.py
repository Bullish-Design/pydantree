"""Phase-3 codec behavior and proposal printer tests."""

import json
from pathlib import Path

from pydantree_sitter.codecs import JsonString, unescape_json
from pydantree_sitter.generate import suggest_codecs
from pydantree_sitter.nodes import Node
from pydantree_sitter.schema import NodeSchema

SCHEMA = NodeSchema.from_node_types_json(
    Path(__file__).parent / "fixtures/jsonlike/node-types.json")


def test_json_value_table_matches_codec_fallback() -> None:
    table = json.loads((Path(__file__).parent / "fixtures" / "evidence" /
                        "oracle_024" / "json_value_table.json").read_text())
    assert [unescape_json(row["encoded"]) for row in table] == [
        row["decoded"] for row in table]


def test_json_codec_matches_the_legacy_unescape_surface() -> None:
    encoded = r'"a\nb\t\"c\"\\d\u0041"'
    assert unescape_json(encoded) == 'a\nb\t"c"\\dA'
    # Raw newlines use the documented manual fallback path.
    assert unescape_json('"a\nb"') == "a\nb"


def test_json_string_mixin_is_a_node_codec() -> None:
    class String(JsonString, Node):
        __kind__ = "string"

    assert String.value_type() is str
    assert String.__value__ is not Node.__value__


def test_suggest_codecs_only_prints_reviewable_stubs(capsys) -> None:
    assert suggest_codecs(SCHEMA) is None
    output = capsys.readouterr().out
    assert "class NumberCodec" in output
    assert "def __value__(self) -> int" in output
    assert not list(Path.cwd().glob("*Codec.py"))
