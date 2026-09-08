"""D5 sentinel: community grammar wheels do not ship node-types.json."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path

import pytest


@pytest.mark.xfail(
    strict=True,
    reason="D5: community wheels ship no node-types.json",
)
def test_community_wheel_does_not_ship_node_types_json() -> None:
    spec = find_spec("tree_sitter_json")
    assert spec is not None and spec.submodule_search_locations
    package_dir = Path(next(iter(spec.submodule_search_locations)))
    # This assertion intentionally fails today. If the wheel starts shipping
    # the schema, pytest reports XPASS(strict=True) and forces a D5 review.
    assert list(package_dir.rglob("node-types.json"))
