"""The public ast-grep front end and exact typed handoff."""

from pathlib import Path

import pytest
import tree_sitter
import tree_sitter_python

from pydantree_sitter import Grammar, Pattern
from pydantree_sitter.errors import PatternBuildError
from pydantree_sitter.rules import Rule
from pydantree_sitter.schema import NodeSchema

ROOT = Path(__file__).parents[1]


def _python_grammar() -> Grammar:
    schema = NodeSchema.from_node_types_json(
        ROOT / "examples/wheel-extract/vendor/python-node-types.json",
        name="python")
    return Grammar.load(
        tree_sitter.Language(tree_sitter_python.language()), schema)


def test_wheel_pattern_extracts_exact_typed_node_and_utf8_spans() -> None:
    grammar = _python_grammar()
    source = "😀 = 1\ndef greet(name):\n    return name\n"

    pattern = Pattern(Rule(kind="function_definition"), language=grammar)
    matches = pattern.find_all(source)

    assert len(matches) == 1
    match = matches[0]
    assert match.node.type == "function_definition"
    assert match.span.start_byte == len("😀 = 1\n".encode())
    assert match.span.end_byte == len(source.encode()) - 1
    assert pattern.agreement.same_artifact is False
    assert pattern.agreement.verified is True
    assert match.agreement == pattern.agreement.digest

    function_cls = grammar.nodes.FunctionDefinition
    typed = match.extract(function_cls)
    assert len(typed) == 1
    assert typed[0].__class__ is function_cls
    assert typed[0].span.start_byte == match.span.start_byte


def test_wheel_pattern_captures_use_utf8_byte_offsets() -> None:
    grammar = _python_grammar()
    source = "# café\ndef naïve(value):\n    return value\n"

    match = Pattern("def $NAME($$$ARGS): $$$BODY", language=grammar) \
        .find(source)

    assert match is not None
    name = match.captures["NAME"]
    assert name.text == "naïve"
    assert name.start_byte == len("# café\ndef ".encode())
    assert name.end_byte == name.start_byte + len("naïve".encode())


def test_pattern_rejects_unknown_kinds_and_malformed_text() -> None:
    grammar = _python_grammar()

    with pytest.raises(PatternBuildError, match="unknown node kind"):
        Pattern(Rule(kind="not_a_python_kind"), language=grammar)

    with pytest.raises(PatternBuildError, match="ast-grep rejected"):
        Pattern("", language=grammar)
