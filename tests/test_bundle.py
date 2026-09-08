"""Typed-node bundle round trips across the Product B/A seam."""

from __future__ import annotations

import json

import pytest
from cfg_grammar import build as build_cfg

import pydantree_sitter_grammar as tg
from pydantree_sitter import Grammar, load_bundle
from pydantree_sitter.errors import BundleError, SchemaDriftError
from pydantree_sitter.grammar import _fingerprint

pytestmark = pytest.mark.toolchain


def test_package_bundle_contains_the_typed_artifacts(tmp_path):
    result = tg.build_builder(build_cfg())
    bundle = result.package(tmp_path / "bundle")

    assert {path.name for path in bundle.iterdir()} == {
        "grammar.so", "node-schema.json", "nodes.py", "tree-sitter.json",
        "loader.py"}
    metadata = json.loads((bundle / "tree-sitter.json").read_text())
    assert metadata["bundle_format"] == 2
    assert metadata["schema"] == "node-schema.json"
    assert metadata["meta_var_char"] == "$"
    assert "pydantree_sitter_grammar" not in (bundle / "loader.py").read_text()


def test_load_bundle_parses_and_finds_schema_backed_nodes(tmp_path):
    result = tg.build_builder(build_cfg())
    bundle = result.package(tmp_path / "bundle")
    grammar = Grammar.load_bundle(bundle)

    assert grammar.schema is not None
    assert grammar.nodes is not None
    section = grammar.nodes.Section
    tree = grammar.parse("[server]\nhost = example.com\n")
    sections = tree.find(section)

    assert len(sections) == 1
    assert sections[0].__kind__ == "section"
    assert sections[0].span.line == 1
    assert load_bundle(bundle).nodes.Section.__schema__ is not None


def test_generated_fingerprint_names_both_grammars(nix_bundle, rust_bundle):
    nix = Grammar.load_bundle(nix_bundle)
    rust = Grammar.load_bundle(rust_bundle)
    with pytest.raises(SchemaDriftError) as exc:
        rust.check_fingerprint(_fingerprint(nix.language))
    assert "nix" in str(exc.value)
    assert "rust" in str(exc.value)


def test_public_bundle_loader_rejects_missing_schema(tmp_path):
    result = tg.build_builder(build_cfg())
    bundle = result.package(tmp_path / "bundle")
    (bundle / "node-schema.json").unlink()
    with pytest.raises(BundleError, match="requires a schema-backed bundle"):
        load_bundle(bundle)
