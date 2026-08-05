"""Development flow + Phase-7 hygiene (014).

- src-first resolution: the devenv venv resolves the packages straight from
  `src/` via a `_pydantree_src.pth`; this conftest does the same as
  belt-and-suspenders (and keeps the suite honest when the devenv is
  bypassed).
- The PROMOTED fixture dirs (7.1): `tests/fixtures/grammars/` (the
  mini-grammars the suite stands on — json_grammar, cfg_grammar, qfilter,
  pymini, hmini, dmini, pyindent, bashmini) and `tests/fixtures/bfree/`
  (the B-free subprocess machinery) are on sys.path — test files never
  sys.path.insert or import from .scratch (grep-gate).
- The `toolchain` marker (7.2): tests needing the tree-sitter CLI + gcc are
  marked `@pytest.mark.toolchain`; an auto-skip hook skips them when the
  toolchain is absent (no per-file TOOLCHAIN_AVAILABLE blocks).
- Hermetic cache isolation (7.3): every test's TSGRAMMAR_CACHE /
  PYDANTREE_SITTER_CACHE points at a session tmp dir — tests never touch
  ~/.cache.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
# unconditional: an existing (late) src entry must not let the
# site-packages copies win
sys.path.insert(0, str(SRC))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
for _d in ("grammars", "bfree"):
    sys.path.insert(0, str(FIXTURES / _d))

TOOLCHAIN_AVAILABLE = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "toolchain: needs the tree-sitter CLI + gcc on PATH "
                   "(auto-skipped when absent)")
    config.addinivalue_line(
        "markers", "slow: slow (generate + gcc) — skip with -m 'not slow'")


def pytest_collection_modifyitems(config, items):
    """Auto-skip `toolchain`-marked tests when the CLI/gcc are absent (7.2):
    the whole suite then SKIPS cleanly instead of erroring."""
    if TOOLCHAIN_AVAILABLE:
        return
    skip = pytest.mark.skip(reason="tree-sitter CLI / gcc not on PATH")
    for item in items:
        if item.get_closest_marker("toolchain"):
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _hermetic_cache(tmp_path_factory, monkeypatch):
    """Point the pipeline cache at a session tmp dir (7.3) — tests never
    touch ~/.cache (both the current and the legacy env-var spellings)."""
    cache = tmp_path_factory.mktemp("pydantree-cache") / "cache"
    monkeypatch.setenv("PYDANTREE_SITTER_CACHE", str(cache))
    monkeypatch.setenv("TSGRAMMAR_CACHE", str(cache))


@pytest.fixture(autouse=True)
def _no_sys_modules_leaks():
    """Kill sys.modules leaks from the exec'd test grammars (7.3): any module
    a test registers (the `g_*` class-surface namespaces) is removed after
    the test."""
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        if name.startswith("g_") or name.startswith("oracle_example"):
            sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# session-scoped community bundle fixtures (7.4: build once per session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def rust_bundle(tmp_path_factory):
    """The community rust bundle (generate + gcc), built ONCE per session."""
    from pydantree_sitter_grammar.pipeline import build_from_source_dir, write_bundle
    result = build_from_source_dir(FIXTURES / "rust")
    return write_bundle(result, tmp_path_factory.mktemp("rust-bundle") / "bundle")


@pytest.fixture(scope="session")
def nix_bundle(tmp_path_factory):
    from pydantree_sitter_grammar.pipeline import build_from_source_dir, write_bundle
    result = build_from_source_dir(FIXTURES / "nix")
    return write_bundle(result, tmp_path_factory.mktemp("nix-bundle") / "bundle")


@pytest.fixture(scope="session")
def markdown_bundle(tmp_path_factory):
    from pydantree_sitter_grammar.pipeline import build_from_source_dir, write_bundle
    result = build_from_source_dir(FIXTURES / "markdown")
    return write_bundle(result, tmp_path_factory.mktemp("md-bundle") / "bundle")
