"""The ast-grep seam for bundles loaded by the typed Grammar runtime."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pydantree_sitter import Grammar
from pydantree_sitter.errors import PatternBuildError
from pydantree_sitter.pattern import (
    Pattern,
    register_bundle_languages,
    registered_languages,
)
from pydantree_sitter.rules import Rule

pytestmark = pytest.mark.toolchain

NIX = """\
{ pkgs, ... }:
{
  packages = [ pkgs.git ];
  env.FOO = "bar";
}
"""


def _copy_bundle(source: Path, destination: Path, *, name: str,
                 meta_var_char: str) -> Path:
    shutil.copytree(source, destination)
    metadata_path = destination / "tree-sitter.json"
    metadata = json.loads(metadata_path.read_text())
    metadata.update({"astgrep_name": name, "meta_var_char": meta_var_char})
    metadata_path.write_text(json.dumps(metadata, indent=2))
    return destination


def test_bundle_registration_uses_metadata_and_batches_languages(
        nix_bundle, rust_bundle, tmp_path):
    """Register two bundles in one engine call and bind Pattern implicitly."""
    nix_dir = _copy_bundle(nix_bundle, tmp_path / "nix",
                           name="pdtnix", meta_var_char="_")
    rust_dir = _copy_bundle(rust_bundle, tmp_path / "rust",
                            name="pdtrust", meta_var_char="$")
    nix_meta = json.loads((nix_dir / "tree-sitter.json").read_text())
    rust_meta = json.loads((rust_dir / "tree-sitter.json").read_text())

    registered = register_bundle_languages({
        "pdtnix": {
            "library_path": nix_dir / "grammar.so",
            "language_symbol": nix_meta.get(
                "language_symbol", f"tree_sitter_{nix_meta['name']}"),
            "meta_var_char": nix_meta["meta_var_char"],
        },
        "pdtrust": {
            "library_path": rust_dir / "grammar.so",
            "language_symbol": rust_meta.get(
                "language_symbol", f"tree_sitter_{rust_meta['name']}"),
            "meta_var_char": rust_meta["meta_var_char"],
        },
    })
    assert set(registered) == {"pdtnix", "pdtrust"}
    assert set(registered_languages()) == {"pdtnix", "pdtrust"}

    grammar = Grammar.load_bundle(nix_dir)
    assert grammar.register_astgrep() == "pdtnix"
    assert grammar.astgrep_name == "pdtnix"
    assert grammar.astgrep_is_bundle is True

    pattern = Pattern(Rule(kind="binding"), language=grammar)
    bindings = pattern.find_all(NIX)
    assert len(bindings) == 2
    typed = bindings[0].extract(grammar.nodes.Binding)
    assert len(typed) == 1
    assert typed[0].__kind__ == "binding"
    assert pattern.agreement.same_artifact is True
    assert bindings[0].agreement == pattern.agreement.digest

    metavariable = Pattern("{ _K = _V; }", language=grammar)
    matches = metavariable.find_all(NIX)
    assert len(matches) == 1
    assert set(matches[0].captures) == {"K", "V"}
    assert matches[0].captures["K"].text == "packages"
    assert matches[0].captures["V"].text == "[ pkgs.git ]"

    rewritten = metavariable.replace_all(NIX, "{ _K = _V; }")
    assert rewritten.original_source == NIX
    assert rewritten.count == 1
    assert rewritten.new_source == (
        "{ pkgs, ... }:\n"
        "{ packages = [ pkgs.git ]; }\n")

    assert grammar.register_astgrep() == "pdtnix"
    with pytest.raises(PatternBuildError, match="already registered"):
        register_bundle_languages({
            "pdtnix": {
                "library_path": rust_dir / "grammar.so",
                "language_symbol": "tree_sitter_rust",
            },
        })
    with pytest.raises(PatternBuildError, match="first registration call"):
        register_bundle_languages({
            "pdtextra": {
                "library_path": nix_dir / "grammar.so",
                "language_symbol": "tree_sitter_nix",
            },
        })
