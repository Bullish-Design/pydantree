"""REVIEW 018 P1/P2: metadata truth — the three pyproject versions and both
__version__ singletons agree, and the root declares no distribution of its
own (a future drift fails here, not in a stale README)."""

import pathlib
import tomllib

import pydantree_sitter
import pydantree_sitter_grammar

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _ver(p):
    return tomllib.loads((ROOT / p).read_text())["project"]["version"]


def test_dist_versions_agree():
    a = _ver("src/pydantree_sitter/pyproject.toml")
    b = _ver("src/pydantree_sitter_grammar/pyproject.toml")
    assert a == b == pydantree_sitter.__version__ == pydantree_sitter_grammar.__version__


def test_root_declares_no_distribution():
    root = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert root.get("tool", {}).get("uv", {}).get("package") is False
    # no build-system -> `pip install .` at the root cannot build a wheel
    assert "build-system" not in root
