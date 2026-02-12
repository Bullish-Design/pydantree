from pathlib import Path

import pytest

from pydantree.registry import InvalidLayoutNameError, WorkshopLayout


def test_layout_resolves_canonical_paths() -> None:
    layout = WorkshopLayout.from_path("/repo")

    assert layout.queries_pack_dir("python", "core") == Path("/repo/workshop/queries/python/core")
    assert layout.query_file("python", "core", "highlights.scm") == Path(
        "/repo/workshop/queries/python/core/highlights.scm"
    )
    assert layout.ir_file("python", "core") == Path("/repo/workshop/ir/python/core/ir.v1.json")
    assert layout.generated_models_dir("python", "core") == Path("/repo/src/pydantree/generated/python/core")
    assert layout.manifest_file("python", "core") == Path("/repo/workshop/manifests/python/core.json")
    assert layout.workshop_log_file() == Path("/repo/logs/workshop.jsonl")


@pytest.mark.parametrize(
    ("language", "query_pack"),
    [
        ("", "core"),
        ("python", ""),
        ("../python", "core"),
        ("python", "core/pack"),
    ],
)
def test_layout_rejects_unsafe_segments(language: str, query_pack: str) -> None:
    layout = WorkshopLayout.from_path("/repo")

    with pytest.raises(InvalidLayoutNameError):
        layout.queries_pack_dir(language=language, query_pack=query_pack)


def test_query_file_requires_scm_extension() -> None:
    layout = WorkshopLayout.from_path("/repo")

    with pytest.raises(InvalidLayoutNameError):
        layout.query_file("python", "core", "highlights.txt")
