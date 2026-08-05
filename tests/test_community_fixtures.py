"""The vendored community node-types.json byproducts are real oracles (V5).

Every retained community fixture (`tests/fixtures/{bash,rust,nix,markdown,
markdown-inline}/node-types.json`) is regenerated fresh through the current
pipeline (derive_schema_for_dir -> the CLI's own byproduct) and compared
BYTE FOR BYTE to the checked-in file — no normalization, no in-memory
regeneration, no self-comparison. The committed file is expected output.

Marked `toolchain` (needs the real CLI + gcc) and `cli_byte_for_byte`
(skipped when the installed CLI is outside the verified 0.25.x range — the
loud guard lives in tests/test_toolchain_version.py).

The manifest (`tests/community_fixture_manifest.py`) is the single list;
refresh happens ONLY through the explicit command:

    devenv shell -- python tests/regenerate_community_node_types.py --write
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

from community_fixture_manifest import COMMUNITY_FIXTURES

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"

pytestmark = [pytest.mark.toolchain, pytest.mark.cli_byte_for_byte]


@pytest.mark.parametrize(
    "fixture",
    [pytest.param(f, id=f.dir_name) for f in COMMUNITY_FIXTURES],
)
def test_community_node_types_byte_for_byte(fixture, tmp_path):
    """Fresh CLI generation over the committed source == the tracked file."""
    from pydantree_sitter_grammar.schema_tool import derive_schema_for_dir

    src = FIXTURES / fixture.dir_name
    assert src.is_dir(), src
    out = tmp_path / "node-schema.json"
    derive_schema_for_dir(src, name=fixture.grammar_name,
                          workdir=tmp_path / "cw", out=out, keep=True)
    fresh = (tmp_path / "cw" / "gen" / "node-types.json").read_bytes()
    # the schema serialization must still be the CLI byproduct (D3)
    assert out.read_bytes() == fresh, (
        f"{fixture.dir_name}: schema serialization drifted from the raw CLI "
        f"byproduct — investigate before blaming the fixture")

    tracked_path = src / fixture.byproduct_path
    tracked = tracked_path.read_bytes()
    if tracked != fresh:
        diff = "\n".join(difflib.unified_diff(
            tracked.decode(errors="replace").splitlines(),
            fresh.decode(errors="replace").splitlines(),
            fromfile=f"{fixture.dir_name}/{fixture.byproduct_path} (tracked)",
            tofile=f"{fixture.dir_name}/{fixture.byproduct_path} (fresh)",
            lineterm=""))
        pytest.fail(
            f"{fixture.dir_name}/node-types.json drifted from the supported "
            f"CLI's byproduct ({len(tracked)} tracked vs {len(fresh)} fresh "
            f"bytes). Refresh intentionally with:\n"
            f"  devenv shell -- python tests/regenerate_community_node_types.py "
            f"--write {fixture.dir_name}\n\n{diff}")
