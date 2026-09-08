"""The selector contract: query and walk must resolve the same rows."""

from __future__ import annotations

from pathlib import Path

import pytest
import tree_sitter
import tree_sitter_python

from pydantree_sitter import Grammar, Node
from pydantree_sitter.find import Selector, find_in
from pydantree_sitter.schema import NodeSchema

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

pytestmark = pytest.mark.toolchain


def _value(value):
    if isinstance(value, Node):
        return {"node": [value.span.start_byte, value.span.end_byte]}
    if isinstance(value, list):
        return [_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _value(item) for key, item in value.items()}
    return value


def _rows(rows):
    return [{
        "span": [row.span.start_byte, row.span.end_byte],
        "fields": {name: _value(getattr(row, name, None))
                   for name in type(row).model_fields},
    } for row in rows]


def _outcome(fn):
    try:
        return ("rows", _rows(fn()))
    except Exception as error:  # noqa: BLE001 - compare both public paths
        failures = tuple(
            (getattr(failure.span, "start_byte", None),
             getattr(failure.span, "end_byte", None), failure.detail)
            for failure in getattr(error, "failures", ()))
        return ("error", type(error).__name__, failures)


def _selector_spans(raw, selector):
    spans = []

    def visit(candidate):
        if selector.matches(candidate):
            spans.append((candidate.start_byte, candidate.end_byte))
        for child in candidate.named_children:
            visit(child)

    visit(raw)
    return tuple(spans)


def _classes(grammar: Grammar):
    assert grammar.nodes is not None
    kind_map = getattr(grammar.nodes, "KIND_MAP", {})
    return tuple(sorted(kind_map.values(), key=lambda cls: cls.__kind__))


def _assert_equivalent(grammar: Grammar, paths: tuple[Path, ...]) -> None:
    classes = _classes(grammar)
    assert classes
    for path in paths:
        raw = grammar.parse(path.read_bytes()).root_node
        for node_cls in classes:
            selected = _outcome(
                lambda node_cls=node_cls, raw=raw,
                language=grammar.language: find_in(raw, node_cls, language))
            walk = _outcome(
                lambda node_cls=node_cls, raw=raw: find_in(raw, node_cls, None))
            assert selected == walk, (
                f"selector disagreement for {grammar.language.name} / "
                f"{path} / {node_cls.__name__}")
            if selected[0] == "rows":
                assert tuple(tuple(row["span"]) for row in selected[1]) == \
                    _selector_spans(raw, Selector.from_class(node_cls))


def test_selector_expands_anchor_and_records_child_filters() -> None:
    schema = NodeSchema.from_list([
        {"type": "expression", "named": True, "subtypes": [
            {"type": "identifier", "named": True},
            {"type": "number", "named": True},
        ]},
        {"type": "identifier", "named": True},
        {"type": "number", "named": True},
    ])

    class Expression(Node):
        __kind__ = "expression"
        __schema__ = schema

    selector = Selector.from_class(Expression)

    assert selector.anchor_kind == "expression"
    assert selector.anchor_kinds == {"identifier", "number"}
    assert selector.ancestor_path[-1].kinds == ("expression",)
    assert selector.children == ()


def test_walk_filters_a_required_child_before_materialization() -> None:
    schema = NodeSchema.from_node_types_json(
        ROOT / "examples/wheel-extract/vendor/python-node-types.json",
        name="python")
    grammar = Grammar.load(
        tree_sitter.Language(tree_sitter_python.language()), schema)

    IdentifierAssignment = type(
        "IdentifierAssignment", (grammar.nodes.Assignment,), {
            "__annotations__": {"left": grammar.nodes.Identifier},
        })

    raw = grammar.parse("answer = 42\nconfig.answer = 43\n").root_node
    query = find_in(raw, IdentifierAssignment, grammar.language)
    walk = find_in(raw, IdentifierAssignment, None)

    assert [(row.left.__value__(), row.span.start_byte) for row in query] == [
        ("answer", 0)]
    assert [(row.left.__value__(), row.span.start_byte) for row in walk] == [
        ("answer", 0)]


def test_generated_selector_matches_finder_over_fixture_corpora(
        nix_bundle, rust_bundle, markdown_bundle, tmp_path):
    from pydantree_sitter_grammar.pipeline import build_from_source_dir, write_bundle

    bash = write_bundle(
        build_from_source_dir(FIXTURES / "bash"), tmp_path / "bash-bundle")
    markdown_inline = write_bundle(
        build_from_source_dir(FIXTURES / "markdown-inline"),
        tmp_path / "markdown-inline-bundle")

    python_schema = NodeSchema.from_node_types_json(
        ROOT / "examples/wheel-extract/vendor/python-node-types.json",
        name="python")
    grammars = {
        "python": Grammar.load(
            tree_sitter.Language(tree_sitter_python.language()),
            python_schema),
        "bash": Grammar.load_bundle(bash),
        "nix": Grammar.load_bundle(nix_bundle),
        "rust": Grammar.load_bundle(rust_bundle),
        "markdown": Grammar.load_bundle(markdown_bundle),
        "markdown-inline": Grammar.load_bundle(markdown_inline),
    }
    corpora = {
        "python": (ROOT / "src/pydantree_sitter/nodes.py",
                    ROOT / "src/pydantree_sitter/find.py"),
        "bash": (ROOT / "examples/bash-extract/sample.sh",
                  ROOT / "examples/bash-extract/real_script.sh",
                  ROOT / "examples/bash-extract/unclosed.sh"),
        "nix": (ROOT / "devenv.nix",
                ROOT / "tests/fixtures/nix/fleet/mypi-agent.nix",
                ROOT / "tests/fixtures/nix/fleet/pydantree.nix"),
        "markdown": (ROOT / "docs/README.md",
                      ROOT / "docs/development.md",
                      ROOT / "docs/typed-node-universe.md"),
        "markdown-inline": (ROOT / "docs/typed-node-universe.md",),
    }
    rust_path = next(Path("/nix/store").glob(
        "*-rust-lib-src/core/src/mem/type_info.rs"), None)
    if rust_path is None:
        pytest.skip("the pinned Rust corpus is not installed")
    corpora["rust"] = (rust_path,)

    for name, grammar in grammars.items():
        _assert_equivalent(grammar, corpora[name])
