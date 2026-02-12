from pathlib import Path

import pytest

from pydantree.registry import (
    InvalidLayoutNameError,
    RepositoryRootNotFoundError,
    WorkshopLayout,
    resolve_repository_root,
)


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


def test_resolve_repository_root_from_nested_directory(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname=\"pydantree\"\n", encoding="utf-8")
    nested = repo_root / "a" / "b" / "c"
    nested.mkdir(parents=True)

    assert resolve_repository_root(nested) == repo_root


def test_resolve_repository_root_raises_when_not_found(tmp_path: Path) -> None:
    start = tmp_path / "norepo"
    start.mkdir()

    with pytest.raises(RepositoryRootNotFoundError):
        resolve_repository_root(start)
