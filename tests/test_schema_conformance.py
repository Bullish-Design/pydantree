"""The schema and language must describe the same grammar vocabulary."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import tree_sitter
import tree_sitter_json
import tree_sitter_python
from community_fixture_manifest import COMMUNITY_FIXTURES

from pydantree_sitter import Grammar
from pydantree_sitter.errors import SchemaDataError, SchemaDriftError
from pydantree_sitter.grammar import _conformance
from pydantree_sitter.schema import NodeSchema

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
PYTHON_SCHEMA = ROOT / "examples" / "wheel-extract" / "vendor" / \
    "python-node-types.json"


def test_wrong_grammar_schema_rejected_even_when_filename_matches(tmp_path):
    path = tmp_path / "python-node-types.json"
    shutil.copyfile(FIXTURES / "rust" / "node-types.json", path)

    with pytest.raises(SchemaDriftError, match="alien kinds"):
        Grammar.load(tree_sitter_python.language(), path)


def test_wrong_grammar_schema_rejected_on_nameless_language():
    with pytest.raises(SchemaDriftError, match="alien kinds"):
        Grammar.load(
            tree_sitter_json.language(),
            FIXTURES / "rust" / "node-types.json",
        )


def test_correct_schema_in_any_directory_binds(tmp_path):
    path = tmp_path / "vendor" / "node-types.json"
    path.parent.mkdir()
    shutil.copyfile(PYTHON_SCHEMA, path)

    grammar = Grammar.load(tree_sitter_python.language(), path)
    assert grammar.schema is not None
    assert grammar.nodes is not None


def test_empty_schema_rejected():
    with pytest.raises(SchemaDataError, match="zero node types"):
        Grammar.load(tree_sitter_python.language(), [])


def test_partial_schema_rejected():
    partial = json.loads(PYTHON_SCHEMA.read_text())[:9]
    with pytest.raises(SchemaDriftError, match="missing ratio"):
        Grammar.load(tree_sitter_python.language(), partial)


def test_supertype_entries_are_exempt_from_existence_check():
    schema = NodeSchema.from_list([
        {"type": "_synthetic_supertype", "named": True,
         "subtypes": [{"type": "identifier", "named": True}]},
        {"type": "identifier", "named": True},
    ])

    verdict = _conformance(
        schema, tree_sitter.Language(tree_sitter_python.language())
    )
    assert verdict["alien_kinds"] == []


@pytest.mark.toolchain
@pytest.mark.parametrize(
    "fixture",
    [pytest.param(item, id=item.dir_name) for item in COMMUNITY_FIXTURES],
)
def test_community_schemas_conform_to_their_languages(fixture, tmp_path):
    from pydantree_sitter_grammar.pipeline import (
        build_from_source_dir,
        write_bundle,
    )

    result = build_from_source_dir(
        FIXTURES / fixture.dir_name, name=fixture.grammar_name)
    bundle = write_bundle(result, tmp_path / fixture.dir_name)
    grammar = Grammar.load_bundle(bundle)
    verdict = _conformance(grammar.schema, grammar.language)
    assert verdict["alien_kinds"] == []
    assert verdict["alien_fields"] == []
    assert verdict["missing_ratio"] <= 0.25


def test_provenance_hash_matches_the_schema_file():
    provenance = json.loads(
        (PYTHON_SCHEMA.parent / "python-node-types.provenance.json").read_text()
    )
    import hashlib

    digest = hashlib.sha256(PYTHON_SCHEMA.read_bytes()).hexdigest()
    assert provenance["schema_sha256"] == digest
