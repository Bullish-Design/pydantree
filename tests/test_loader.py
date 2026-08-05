"""Loader tests: the bundle contract's error paths + the D12 bundle format.

The TS report §7 flagged the loader's error paths as untested; the 014
refactor (D12) versions the artifact contract with `bundle_format` (absent =
format 1, accepted; unknown >2 = `BundleError` naming both versions). These
tests pin all of it, plus a real format-1 bundle still loading after the
format-2 rollout.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pydantree_sitter.errors import BundleError
from pydantree_sitter.loader import load_bundle

ROOT = Path(__file__).resolve().parents[1]

TOOLCHAIN_AVAILABLE = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None
requires_toolchain = pytest.mark.skipif(
    not TOOLCHAIN_AVAILABLE, reason="tree-sitter CLI / gcc not on PATH")


def _metadata_bundle(tmp_path: Path, metadata: dict) -> Path:
    """A bundle dir with the given metadata and (optionally) a fake artifact."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "tree-sitter.json").write_text(json.dumps(metadata))
    if metadata.get("artifact"):
        (bundle / metadata["artifact"]).write_bytes(b"not a real .so")
    return bundle


def test_missing_tree_sitter_json_is_a_bundle_error(tmp_path):
    bundle = tmp_path / "empty"
    bundle.mkdir()
    with pytest.raises(BundleError) as exc:
        load_bundle(bundle)
    assert "tree-sitter.json" in str(exc.value)


def test_missing_name_is_a_bundle_error(tmp_path):
    bundle = _metadata_bundle(tmp_path, {"artifact": "grammar.so"})
    with pytest.raises(BundleError) as exc:
        load_bundle(bundle)
    assert "'name'" in str(exc.value)


def test_missing_artifact_is_a_bundle_error(tmp_path):
    bundle = _metadata_bundle(tmp_path, {"name": "cfg"})
    with pytest.raises(BundleError) as exc:
        load_bundle(bundle)
    assert "grammar.so" in str(exc.value)


def test_unknown_bundle_format_is_rejected_naming_both_versions(tmp_path):
    bundle = _metadata_bundle(
        tmp_path, {"bundle_format": 99, "name": "cfg",
                   "artifact": "grammar.so"})
    with pytest.raises(BundleError) as exc:
        load_bundle(bundle)
    msg = str(exc.value)
    assert "99" in msg
    assert "1" in msg and "2" in msg  # names both versions


def test_non_int_bundle_format_is_rejected(tmp_path):
    bundle = _metadata_bundle(
        tmp_path, {"bundle_format": "two", "name": "cfg",
                   "artifact": "grammar.so"})
    with pytest.raises(BundleError) as exc:
        load_bundle(bundle)
    assert "bundle_format" in str(exc.value)


@requires_toolchain
def test_format_1_bundle_still_loads(tmp_path):
    """Absent bundle_format = format 1 (the original layout) — accepted, not
    rejected; the format-2 rollout must not break existing bundles."""
    import sys
    sys.path.insert(0, str(ROOT / ".scratch" / "projects" / "006-query-bridge"))
    import pydantree_sitter_grammar as tg
    from cfg_grammar import build as build_cfg

    result = tg.build_builder(build_cfg())
    bundle = result.package(tmp_path / "bundle")
    metadata = json.loads((bundle / "tree-sitter.json").read_text())
    assert metadata["bundle_format"] == 2
    del metadata["bundle_format"]            # roll back to format 1
    (bundle / "tree-sitter.json").write_text(json.dumps(metadata))

    b = load_bundle(bundle)
    assert b.language is not None
    assert b.schema is not None
    assert "source_file" in b.schema.kinds()


@requires_toolchain
def test_format_2_bundle_loads(tmp_path):
    """The current format: bundle_format 2 in the metadata, loaded normally."""
    import sys
    sys.path.insert(0, str(ROOT / ".scratch" / "projects" / "006-query-bridge"))
    import pydantree_sitter_grammar as tg
    from cfg_grammar import build as build_cfg

    result = tg.build_builder(build_cfg())
    bundle = result.package(tmp_path / "bundle")
    metadata = json.loads((bundle / "tree-sitter.json").read_text())
    assert metadata.get("bundle_format") == 2
    assert metadata["schema"] == "node-schema.json"
    b = load_bundle(bundle)
    assert b.schema is not None and "source_file" in b.schema.kinds()
