"""Phase 0 schema inventory for the typed-node-universe refactor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EVIDENCE = FIXTURES / "evidence" / "oracle_024" / "inventory.md"

EXPECTED = {
    "bash": (62, 3, 20, 37, 13),
    "nix": (42, 1, 23, 8, 11),
    "rust": (169, 6, 73, 104, 17),
    "markdown": (51, 0, 2, 25, 17),
    "markdown-inline": (26, 0, 0, 16, 7),
    "jsonlike": (10, 1, 1, 3, 5),
    "jsonlike_alias": (2, 0, 0, 1, 1),
    "jsonlike_hidden": (4, 0, 1, 1, 2),
}


def _counts(name: str) -> tuple[int, int, int, int, int]:
    data = json.loads((FIXTURES / name / "node-types.json").read_text())
    return (
        sum(item["named"] for item in data),
        sum(bool(item.get("subtypes")) for item in data),
        sum(item.get("fields") is not None and bool(item["fields"])
            for item in data),
        sum(item.get("children") is not None for item in data),
        sum(
            item["named"]
            and item.get("fields") is None
            and item.get("children") is None
            and not item.get("subtypes")
            for item in data
        ),
    )


@pytest.mark.parametrize("name", EXPECTED)
def test_schema_inventory(name: str) -> None:
    assert _counts(name) == EXPECTED[name]


def test_inventory_evidence_is_committed() -> None:
    expected = [
        "fixture | named | supertypes | fields | children | text_leaves",
        "---|---:|---:|---:|---:|---:",
    ]
    for name, counts in EXPECTED.items():
        expected.append(f"{name} | " + " | ".join(map(str, counts)))
    assert EVIDENCE.read_text().splitlines() == expected
