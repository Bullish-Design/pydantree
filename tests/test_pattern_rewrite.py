"""Tree-owned structural rewrite behavior."""

from pathlib import Path

import pytest
import tree_sitter
import tree_sitter_python

from pydantree_sitter import Edit, Grammar, Pattern
from pydantree_sitter.errors import PatternRewriteError
from pydantree_sitter.pattern import _apply
from pydantree_sitter.schema import NodeSchema

ROOT = Path(__file__).parents[1]


def _python_grammar() -> Grammar:
    schema = NodeSchema.from_node_types_json(
        ROOT / "examples/wheel-extract/vendor/python-node-types.json",
        name="python")
    return Grammar.load(
        tree_sitter.Language(tree_sitter_python.language()), schema)


def test_rewrite_uses_exact_ranges_and_keeps_input_in_memory() -> None:
    grammar = _python_grammar()
    source = "😀 = 1\nx = 2\ny = 3\n"
    pattern = Pattern("x = $VALUE", language=grammar)

    result = pattern.replace_all(source, "x = ($VALUE)")

    assert source == "😀 = 1\nx = 2\ny = 3\n"
    assert result.count == 1
    assert result.original_source == source
    assert result.new_source == "😀 = 1\nx = (2)\ny = 3\n"
    assert [(edit.start_byte, edit.end_byte) for edit in result.edits] == [
        (len("😀 = 1\n".encode()), len("😀 = 1\nx = 2".encode()))]


def test_rewrite_applies_multiple_disjoint_edits_right_to_left() -> None:
    pattern = Pattern("x = $VALUE", language=_python_grammar())

    result = pattern.replace_all("x = 1\nx = 2\n", "x = ($VALUE)")

    assert result.count == 2
    assert result.new_source == "x = (1)\nx = (2)\n"
    assert [edit.new_text for edit in result.edits] == ["x = (1)", "x = (2)"]


def test_rewrite_accepts_a_pure_replacement_function() -> None:
    pattern = Pattern("x = $VALUE", language=_python_grammar())

    result = pattern.replace_all(
        "x = 1\n", lambda match: f"x = {match.captures['VALUE'].text} + 1")

    assert result.new_source == "x = 1 + 1\n"
    assert result.edits[0].new_text == "x = 1 + 1"


def test_invalid_edit_ranges_are_rejected_before_splicing() -> None:
    with pytest.raises(PatternRewriteError, match="outside"):
        _apply("café", (Edit(start_byte=0, end_byte=99, new_text="x"),))

    with pytest.raises(PatternRewriteError, match="UTF-8"):
        _apply("café", (Edit(start_byte=4, end_byte=5, new_text="x"),))


def test_nested_rewrites_refuse_or_select_an_explicit_policy() -> None:
    pattern = Pattern("$LEFT + $RIGHT", language=_python_grammar())
    source = "value = a + b + c\n"

    with pytest.raises(PatternRewriteError, match="overlapping edits"):
        pattern.replace_all(source, "($LEFT) + ($RIGHT)")

    outer = pattern.replace_all(
        source, "($LEFT) + ($RIGHT)", on_overlap="outermost")
    inner = pattern.replace_all(
        source, "($LEFT) + ($RIGHT)", on_overlap="innermost")
    assert outer.dropped_for_overlap == 1
    assert inner.dropped_for_overlap == 1
    assert outer.new_source == "value = (a + b) + (c)\n"
    assert inner.new_source == "value = (a) + (b) + c\n"


def test_invalid_rewrite_is_rejected_or_returned_as_diagnostic() -> None:
    pattern = Pattern("pass", language=_python_grammar())
    source = "pass\n"

    with pytest.raises(PatternRewriteError, match="does not parse"):
        pattern.replace_all(source, "(")

    result = pattern.replace_all(source, "(", validate=False)
    assert result.new_source == "(\n"
    assert result.edits[0].new_text == "("
    assert result.diagnostics and "does not parse" in result.diagnostics[0]


def test_syntax_check_rejects_tree_sitter_recovery() -> None:
    pattern = Pattern("x = $VALUE", language=_python_grammar())
    source = "def f():\n    x = 1\n    return x\n"
    template = "x = 1\n        return x"

    with pytest.raises(PatternRewriteError, match="parser rejects"):
        pattern.replace_all(source, template, single_node=False)

    result = pattern.replace_all(
        source, template, single_node=False, validate=False)
    assert result.new_source != source
    assert result.diagnostics and "parser rejects" in result.diagnostics[0]
