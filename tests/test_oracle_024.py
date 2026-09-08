"""Typed-node behaviour oracles for the 024 refactor.

The expected JSON files are intentionally treated as immutable evidence.  The
community cases below extract rows through generated ``Node`` classes and the
two small JSON schemas are still checked through the generated namespace even
though their original parser sources are not vendored.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import tree_sitter_json

from pydantree_sitter import Grammar
from pydantree_sitter.generate import build_namespace
from pydantree_sitter.schema import NodeSchema

TESTS = Path(__file__).parent
FIXTURES = TESTS / "fixtures"
EVIDENCE = FIXTURES / "evidence" / "oracle_024"
NAMES = (
    "bash", "nix", "rust", "markdown", "markdown-inline", "jsonlike",
    "jsonlike_alias", "jsonlike_hidden",
)

def _expected(name: str):
    return json.loads((EVIDENCE / f"{name}.json").read_text())


def _schema(name: str) -> NodeSchema:
    return NodeSchema.from_node_types_json(
        FIXTURES / name / "node-types.json", name=name)


@pytest.mark.parametrize("name", NAMES)
def test_committed_oracle_rows_and_generated_namespace(name: str) -> None:
    rows = _expected(name)
    assert rows == json.loads((EVIDENCE / f"{name}.json").read_text())
    namespace = build_namespace(_schema(name))
    assert namespace.KIND_MAP


def test_jsonlike_pair_oracle() -> None:
    grammar = Grammar.load(tree_sitter_json.language(), _schema("jsonlike"),
                           verify=False)
    pairs = grammar.parse('{"name": "alice",\n"age": 30}').find(
        grammar.nodes.Pair)
    rows = [{
        "key": json.loads(pair.key.__value__()),
        "value": pair.value.__value__(),
        "line": pair.span.line,
    } for pair in pairs]
    assert rows == _expected("jsonlike")


@pytest.mark.toolchain
def test_rust_function_oracle(rust_bundle) -> None:
    source = "fn add(a: u32, b: u32) -> u32 { a + b }\n\n\n\nfn empty() {}\n"
    grammar = Grammar.load_bundle(rust_bundle)
    rows = [{
        "name": item.name.__value__(),
        "return_type": item.return_type.__value__()
        if item.return_type is not None else None,
        "line": item.span.line,
    } for item in grammar.parse(source).find(grammar.nodes.FunctionItem)]
    assert rows == _expected("rust")


@pytest.mark.toolchain
def test_markdown_heading_oracle(markdown_bundle) -> None:
    grammar = Grammar.load_bundle(markdown_bundle)
    source = "# Title\n\n## Section\n"
    rows = [{
        "text": heading.heading_content.__value__(),
        "line": heading.span.line,
    } for heading in grammar.parse(source).find(grammar.nodes.AtxHeading)]
    assert rows == _expected("markdown")


@pytest.mark.toolchain
def test_markdown_inline_link_oracle(markdown_inline_bundle) -> None:
    grammar = Grammar.load_bundle(markdown_inline_bundle)
    source = "[link](https://example.com)\n"
    rows = [{"dest": node.__value__()} for node in grammar.parse(source).find(
        grammar.nodes.LinkDestination)]
    assert rows == _expected("markdown-inline")


@pytest.mark.toolchain
def test_nix_list_oracle(nix_bundle) -> None:
    grammar = Grammar.load_bundle(nix_bundle)
    source = (FIXTURES / "nix" / "fleet" / "mypi-agent.nix").read_text()
    rows = [{"value": node.__value__(), "line": node.span.line}
            for node in grammar.parse(source).find(grammar.nodes.ListExpression)]
    assert rows == _expected("nix")


@pytest.mark.toolchain
def test_bash_assignment_oracle(tmp_path) -> None:
    from pydantree_sitter_grammar.pipeline import build_from_source_dir, write_bundle

    bundle = write_bundle(
        build_from_source_dir(FIXTURES / "bash"), tmp_path / "bash-bundle")
    grammar = Grammar.load_bundle(bundle)
    for filename in ("sample.sh", "real_script.sh", "unclosed.sh"):
        source = (TESTS.parent / "examples" / "bash-extract" / filename)
        rows = []
        variable_assignment = grammar.nodes.VariableAssignment

        def visit(node, rows, variable_assignment):
            if node.type == "variable_assignment" and (
                    node.parent is None or
                    node.parent.type not in {"export_command",
                                             "declaration_command"}):
                assignment = variable_assignment.from_node(node)
                rows.append({
                    "name": assignment.name.__value__(),
                    "value": assignment.value.__value__(),
                    "line": assignment.span.line,
                })
            for child in node.named_children:
                visit(child, rows, variable_assignment)

        visit(grammar.parse(source.read_bytes()).root_node, rows,
              variable_assignment)
        assert rows == _expected("bash")[filename]
