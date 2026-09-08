"""Phase-2 generator round trips over every vendored node schema."""

from pathlib import Path
from types import ModuleType

import pytest

from pydantree_sitter.generate import (
    _class_specs,
    build_namespace,
    generate_module,
)
from pydantree_sitter.schema import NodeSchema

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = (
    "bash", "nix", "rust", "markdown", "markdown-inline",
    "jsonlike", "jsonlike_alias", "jsonlike_hidden",
)


def _schema(name: str) -> NodeSchema:
    return NodeSchema.from_node_types_json(FIXTURES / name / "node-types.json",
                                           name=name)


def _exec_module(source: str, name: str) -> ModuleType:
    module = ModuleType(name)
    exec(compile(source, f"{name}.py", "exec"), module.__dict__)  # noqa: S102
    return module


@pytest.mark.parametrize("name", NAMES)
def test_source_and_namespace_renderings_have_the_same_node_shapes(name: str):
    schema = _schema(name)
    source = generate_module(schema)
    compile(source, f"{name}.py", "exec")
    imported = _exec_module(source, f"generated_{name.replace('-', '_')}")
    built = build_namespace(schema)

    expected_classes = [item for item in schema.node_types
                        if item.named and not item.subtypes]
    assert len(imported.KIND_MAP) == len(expected_classes)
    assert len([item for item in _class_specs(schema)
                if item.is_supertype]) == sum(
                    bool(item.subtypes) for item in schema.node_types)
    for kind, source_class in imported.KIND_MAP.items():
        memory_class = built.KIND_MAP[kind]
        assert source_class.__kind__ == memory_class.__kind__ == kind
        assert source_class.__children__ == memory_class.__children__


def test_cyclic_supertype_dependencies_fail_before_import() -> None:
    schema = NodeSchema.from_list([
        {"type": "a", "named": True,
         "subtypes": [{"type": "b", "named": True}]},
        {"type": "b", "named": True,
         "subtypes": [{"type": "a", "named": True}]},
    ])
    with pytest.raises(ValueError, match="cyclic or undefined"):
        generate_module(schema)


def test_jsonlike_golden_module_is_regeneration_oracle() -> None:
    golden = (FIXTURES / "evidence/oracle_024/jsonlike_nodes.py").read_text()
    assert golden == generate_module(_schema("jsonlike"))


def test_named_alias_reference_gets_a_generated_leaf_class() -> None:
    schema = NodeSchema.from_node_types_json(
        Path(__file__).parents[1] /
        "examples/wheel-extract/vendor/python-node-types.json",
        name="python",
    )

    source = generate_module(schema)
    imported = _exec_module(source, "generated_python")
    built = build_namespace(schema)

    assert "as_pattern_target" in imported.KIND_MAP
    assert "as_pattern_target" in built.KIND_MAP
    assert imported.KIND_MAP["as_pattern_target"].__children__ == ()
    assert built.KIND_MAP["as_pattern_target"].__children__ == ()
