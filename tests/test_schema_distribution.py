"""The application-owned schema distribution contract."""

import json
from importlib.metadata import version
from pathlib import Path

import pytest

from pydantree_sitter.errors import SchemaDataError, SchemaMissingError
from pydantree_sitter.schema import NodeSchema, load_schema

ROOT = Path(__file__).resolve().parents[1]


def test_missing_schema_data_has_a_distribution_error(tmp_path):
    with pytest.raises(SchemaMissingError, match="distribution data is missing"):
        load_schema(tmp_path / "python-node-types.json")


def test_malformed_schema_data_has_a_data_error(tmp_path):
    path = tmp_path / "python-node-types.json"
    path.write_text("not json")
    with pytest.raises(SchemaDataError, match="malformed"):
        load_schema(path)


def test_structurally_invalid_schema_has_a_data_error(tmp_path):
    path = tmp_path / "python-node-types.json"
    path.write_text("[{\"type\": 42}]")
    with pytest.raises(SchemaDataError, match="invalid"):
        load_schema(path)


def test_empty_schema_has_a_data_error(tmp_path):
    path = tmp_path / "node-types.json"
    path.write_text("[]")
    with pytest.raises(SchemaDataError, match="zero node types"):
        load_schema(path)


def test_real_community_schema_loads_without_product_b():
    schema = load_schema(ROOT / "tests/fixtures/rust/node-types.json")
    assert isinstance(schema, NodeSchema)
    assert schema.name is None
    assert "source_file" in schema.kinds()


def test_toolchain_free_schema_artifact_has_reviewable_provenance():
    path = ROOT / "examples/wheel-extract/vendor/python-node-types.provenance.json"
    data = json.loads(path.read_text())
    assert data["schema_file"] == "python-node-types.json"
    assert data["grammar"] == "python"
    assert data["source_repository"].endswith("tree-sitter-python")
    assert data["tree_sitter_runtime"] == ">=0.26,<0.27"
    assert data["source_commit"] == \
        "293fdc02038ee2bf0e2e206711b69c90ac0d413f"
    assert data["grammar_semantic_version"] == [
        int(part) for part in version("tree-sitter-python").split(".")]
