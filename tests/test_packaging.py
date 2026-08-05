"""Packaging tests: the two-distribution split (014 refactor, D1/D2).

`pydantree-sitter` is LIGHT (no pydantree_sitter_grammar, no scanner data,
tree-sitter>=0.26); `pydantree-sitter-grammar` is HEAVY and carries the
external-scanner package data and depends on the light package. These tests
build the wheels (uv build, fast) and assert the split contents +
dependencies; the full fresh-venv end-to-end installs only the light wheel
and proves the B-free boundary against real artifacts (the Phase-9 floor
extends this to py.typed/LICENSE/metadata checks).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# the two distributions (imports: pydantree_sitter / pydantree_sitter_grammar)
DIST = {"light": "pydantree-sitter",
        "heavy": "pydantree-sitter-grammar"}


def _uv_available() -> bool:
    return shutil.which("uv") is not None


pytestmark = pytest.mark.skipif(
    not _uv_available(), reason="uv not on PATH")


def _build_wheel(which: str, out: Path) -> Path:
    pkg_dir = SRC / ("pydantree_sitter" if which == "light"
                     else "pydantree_sitter_grammar")
    proc = subprocess.run(
        ["uv", "build", "--out-dir", str(out)],
        capture_output=True, text=True, cwd=str(pkg_dir), check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    whl = next(out.glob(f"{DIST[which].replace('-', '_')}-*.whl"))
    return whl


def _wheel_contents(whl: Path) -> set[str]:
    with zipfile.ZipFile(whl) as z:
        return set(z.namelist())


def _wheel_requires(whl: Path) -> list[str]:
    with zipfile.ZipFile(whl) as z:
        meta = z.read([n for n in z.namelist() if n.endswith("METADATA")][0]).decode()
    return [l.split("Requires-Dist: ")[1] for l in meta.splitlines()
            if l.startswith("Requires-Dist:") and "extra" not in l]


def test_light_wheel_carries_no_b_and_no_scanner(tmp_path):
    """The light install: pydantree_sitter only, no pydantree_sitter_grammar
    package, no scanner package data; dependencies are pydantic +
    tree-sitter>=0.26 only (no edge to the heavy package)."""
    light = _build_wheel("light", tmp_path)
    contents = _wheel_contents(light)
    assert any(n.startswith("pydantree_sitter/") for n in contents)
    assert not any("pydantree_sitter_grammar" in n for n in contents), \
        f"{light.name} leaks the heavy package"
    assert not any("scanner" in n for n in contents), \
        f"{light.name} leaks scanner package data"
    deps = _wheel_requires(light)
    assert not any(d.startswith("pydantree-sitter-grammar") for d in deps), \
        "the light package must not depend on the heavy one"
    assert "pydantic>=2.11" in deps
    assert "tree-sitter>=0.26" in deps


def test_heavy_wheel_carries_the_scanner_and_depends_on_light(tmp_path):
    """The heavy build tool additionally carries the scanner package data
    (scanners/indent_scanner.c) and the tree-sitter>=0.26 dependency floor;
    its one package edge is pydantree-sitter (A still never imports B; B
    depending on A is the free direction)."""
    heavy = _build_wheel("heavy", tmp_path)
    contents = _wheel_contents(heavy)
    assert "pydantree_sitter_grammar/scanners/indent_scanner.c" in contents
    deps = _wheel_requires(heavy)
    assert "pydantree-sitter>=0.1" in deps
    assert "tree-sitter>=0.26" in deps


def test_root_pyproject_is_workspace_only_and_ships_no_distribution():
    """The root project is the uv-workspace + dev-tooling envelope ONLY
    (Phase 1 of the 014 refactor deleted the legacy island and its wheel
    config). No wheel-build config, no console scripts; the real products
    are workspace members under src/."""
    text = (ROOT / "pyproject.toml").read_text()
    assert "[tool.hatch.build.targets.wheel]" not in text, \
        "root pyproject must not configure a wheel (no distribution of its own)"
    assert "[project.scripts]" not in text, \
        "root pyproject must not ship console scripts"
    assert "src/pydantree_sitter" in text \
        and "src/pydantree_sitter_grammar" in text  # the workspace members


def test_light_wheel_pins_0_26(tmp_path):
    """The tree-sitter pin tightened >=0.23 -> >=0.26 in both distributions."""
    for which in ("light", "heavy"):
        whl = _build_wheel(which, tmp_path / which)
        deps = _wheel_requires(whl)
        pins = [d for d in deps if d.startswith("tree-sitter>=")]
        assert pins, f"{which} has no tree-sitter pin"
        assert pins[0] == "tree-sitter>=0.26", f"{which} pin is {pins[0]}"


def test_importing_light_never_imports_heavy():
    """The B-free guarantee, trivially stated (D2: A never imports B; B
    depends on A, not the other way). A fresh interpreter that imports only
    pydantree_sitter must not have the heavy package in sys.modules — the
    dev `.pth` puts both on the path, so a stray import would show up here."""
    code = (
        "import sys; import pydantree_sitter; "
        "assert 'pydantree_sitter_grammar' not in sys.modules, "
        "'importing the light package pulled in the heavy one'"
    )
    proc = subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout


# ---------------------------------------------------------------------------
# the fresh-venv install boundary (the B-free claim against real artifacts)
# ---------------------------------------------------------------------------

_TOOLCHAIN = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None


@pytest.mark.skipif(not _uv_available() or not _TOOLCHAIN,
                    reason="uv and/or the tree-sitter CLI + gcc not on PATH")
def test_fresh_venv_light_install_delivers_a_without_b(tmp_path):
    """The CONCEPT §8 claim at the INSTALL boundary, in a test: a fresh venv
    (no editable src/, no heavy wheel) installs only the light wheel and runs
    the checked cfg-bundle round-trip; `import pydantree_sitter_grammar`
    fails against the real artifact."""
    import json
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    _build_wheel("light", wheels)
    venv = tmp_path / "fresh-venv"
    proc = subprocess.run(["uv", "venv", "--python", sys.executable,
                           str(venv)], capture_output=True, text=True,
                          check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    proc = subprocess.run(
        ["uv", "pip", "install", "--python", str(venv / "bin" / "python"),
         "--find-links", str(wheels), "pydantree-sitter==0.1.0"],
        capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    # the seam does not leak: the heavy package is not importable
    proc = subprocess.run([str(venv / "bin" / "python"), "-c",
                           "import pydantree_sitter_grammar"],
                          capture_output=True, text=True, check=False)
    assert proc.returncode != 0, \
        "pydantree_sitter_grammar IS importable in the light install"

    # build the cfg bundle (B-side) and round-trip it in the fresh venv
    from cfg_grammar import CORPUS, LISTEN_GROUND_TRUTH, SECTION_GROUND_TRUTH, build as _cfg
    import pydantree_sitter_grammar as tg
    result = tg.build_builder(_cfg())
    bundle = result.package(tmp_path / "bundle")
    consumer = tmp_path / "consumer.py"
    consumer.write_text(f"""
import json, sys
from pydantree_sitter import (Language, M, OutputModel, capture,
                              propose_value_map, source_meta)

class ServerSection(OutputModel):
    __match__ = M("source_file", "section", record=True)
    host: str
    port: int
    debug: bool = False
    title: str | None = None
    line: int = source_meta()

class Listen(OutputModel):
    __match__ = M("source_file", "directive")
    name: str = capture("name")
    port: int = capture("arg")
    line: int = source_meta()

CORPUS = {CORPUS!r}
GT_SEC = {SECTION_GROUND_TRUTH!r}
GT_LIS = {LISTEN_GROUND_TRUTH!r}
lang = Language.load_bundle(sys.argv[1])
lang = Language.load_bundle(sys.argv[1],
                            value_map=propose_value_map(lang.schema))
ServerSection.validate_with(lang)
Listen.validate_with(lang)
secs = [r.model_dump() for r in ServerSection.extract(CORPUS, language=lang)]
lis = [r.model_dump() for r in Listen.extract(CORPUS, language=lang)]
print(json.dumps({{'ok': secs == GT_SEC and lis == GT_LIS}}))
""")
    proc = subprocess.run(
        [str(venv / "bin" / "python"), str(consumer), str(bundle)],
        capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert json.loads(proc.stdout)["ok"] is True
