"""Phase-6 packaging tests: the distribution split (Run 1).

The CONCEPT §8 split is now real at the packaging level: tscore + tsquery are
LIGHT installables (no tsgrammar, no scanner data, tree-sitter>=0.26), and
tsgrammar is the HEAVY one that carries the external-scanner package data.
The root pyproject ships ONLY the legacy wrapper + examples + data. These
tests build the wheels (uv build, fast) and assert the split contents +
dependencies; the full fresh-venv end-to-end is the Run-1 experiment
(.scratch/projects/008-consumer-seam/experiment_run1.py).
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

# the pydantree-branded distribution names (imports stay tscore/tsquery/…)
DIST = {"tscore": "pydantree-tscore",
        "tsquery": "pydantree-tsquery",
        "tsgrammar": "pydantree-tsgrammar"}


def _uv_available() -> bool:
    import shutil
    return shutil.which("uv") is not None


pytestmark = pytest.mark.skipif(
    not _uv_available(), reason="uv not on PATH")


def _build_wheel(pkg: str, out: Path) -> Path:
    proc = subprocess.run(
        ["uv", "build", "--out-dir", str(out)],
        capture_output=True, text=True, cwd=str(SRC / pkg), check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    whl = next(out.glob(f"{DIST[pkg].replace('-', '_')}-*.whl"))
    return whl


def _wheel_contents(whl: Path) -> set[str]:
    with zipfile.ZipFile(whl) as z:
        return set(z.namelist())


def _wheel_requires(whl: Path) -> list[str]:
    with zipfile.ZipFile(whl) as z:
        meta = z.read([n for n in z.namelist() if n.endswith("METADATA")][0]).decode()
    return [l.split("Requires-Dist: ")[1] for l in meta.splitlines()
            if l.startswith("Requires-Dist:") and "extra" not in l]


def test_light_wheels_carry_no_tsgrammar_and_no_scanner(tmp_path):
    """tscore + tsquery install WITHOUT tsgrammar: no tsgrammar package, no
    scanner package data, and the dependency lists resolve only pydantic +
    tree-sitter>=0.26 (+ tscore for tsquery)."""
    tscore = _build_wheel("tscore", tmp_path)
    tsquery = _build_wheel("tsquery", tmp_path)
    ts_wheel = _wheel_contents(tscore)
    tq_wheel = _wheel_contents(tsquery)
    for whl, contents, pkg in [(tscore, ts_wheel, "tscore"),
                               (tsquery, tq_wheel, "tsquery")]:
        assert any(n.startswith(f"{pkg}/") for n in contents)
        assert not any("tsgrammar" in n for n in contents), \
            f"{whl.name} leaks tsgrammar"
        assert not any("scanner" in n for n in contents), \
            f"{whl.name} leaks scanner package data"
        assert not any("pydantree/" in n for n in contents), \
            f"{whl.name} leaks the legacy wrapper"
    assert "pydantree-tscore>=0.1" in _wheel_requires(tsquery)
    for dep in _wheel_requires(tscore):
        assert not dep.startswith("pydantree-tsgrammar"), \
            "tscore depends on tsgrammar"


def test_heavy_wheel_carries_the_scanner_and_0_26_pin(tmp_path):
    """tsgrammar (the heavy build tool) additionally carries the scanner
    package data (scanners/indent_scanner.c) and the tree-sitter>=0.26
    dependency floor (the code uses 0.26-only APIs)."""
    tsg = _build_wheel("tsgrammar", tmp_path)
    contents = _wheel_contents(tsg)
    assert "tsgrammar/scanners/indent_scanner.c" in contents
    deps = _wheel_requires(tsg)
    assert "pydantree-tscore>=0.1" in deps
    assert any(d.startswith("tree-sitter>=") for d in deps)
    tree_pin = [d for d in deps if d.startswith("tree-sitter>=")][0]
    major = tree_pin.split(">=")[1].split(".")[0]
    assert int(major) >= 0.26 or tree_pin >= "tree-sitter>=0.26"


def test_root_pyproject_excludes_the_three_packages():
    """The root distribution is the legacy wrapper only — the split is a
    package-level fact, not just a build-script detail."""
    text = (ROOT / "pyproject.toml").read_text()
    # the packages config line (the comment above may mention the split docs)
    pkg_section = text.split("[tool.hatch.build.targets.wheel]")[1]
    packages_line = [l for l in pkg_section.splitlines()
                     if l.strip().startswith("packages")]
    assert packages_line, "no packages config in the root pyproject"
    for pkg in ("tsgrammar", "tsquery", "tscore"):
        assert pkg not in packages_line[0], \
            f"root pyproject still ships {pkg}"
    assert "src/pydantree" in packages_line[0]
    assert "src/examples" in packages_line[0]
    assert "data" in packages_line[0]


def test_light_wheel_pins_0_26(tmp_path):
    """The tree-sitter pin tightened >=0.23 -> >=0.26 in every distribution."""
    for pkg in ("tscore", "tsquery", "tsgrammar"):
        whl = _build_wheel(pkg, tmp_path / pkg)
        deps = _wheel_requires(whl)
        pins = [d for d in deps if d.startswith("tree-sitter>=")]
        assert pins, f"{pkg} has no tree-sitter pin"
        assert pins[0] == "tree-sitter>=0.26", f"{pkg} pin is {pins[0]}"


# ---------------------------------------------------------------------------
# the fresh-venv install boundary (the Run-1 centerpiece, in-test form)
# ---------------------------------------------------------------------------

_TOOLCHAIN = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None


@pytest.mark.skipif(not _uv_available() or not _TOOLCHAIN,
                    reason="uv and/or the tree-sitter CLI + gcc not on PATH")
def test_fresh_venv_light_install_delivers_a_without_b(tmp_path):
    """The CONCEPT §8 claim at the INSTALL boundary, in a test: a fresh venv
    (no editable src/, no tsgrammar) installs only the light wheels and runs
    the checked cfg-bundle round-trip; `import tsgrammar` fails."""
    import json
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    for pkg in ("tscore", "tsquery"):
        _build_wheel(pkg, wheels)
    venv = tmp_path / "fresh-venv"
    proc = subprocess.run(["uv", "venv", "--python", sys.executable,
                           str(venv)], capture_output=True, text=True,
                          check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    proc = subprocess.run(
        ["uv", "pip", "install", "--python", str(venv / "bin" / "python"),
         "--find-links", str(wheels),
         "pydantree-tscore==0.1.0", "pydantree-tsquery==0.1.0"],
        capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    # the seam does not leak: tsgrammar is not importable in the light install
    proc = subprocess.run([str(venv / "bin" / "python"), "-c",
                           "import tsgrammar"],
                          capture_output=True, text=True, check=False)
    assert proc.returncode != 0, "tsgrammar IS importable in the light install"

    # build the cfg bundle (B-side) and round-trip it in the fresh venv
    from pathlib import Path as _P
    bridge = _P(__file__).resolve().parents[1] / ".scratch" / "projects" / "006-tsquery-bridge"
    if str(bridge) not in sys.path:
        sys.path.insert(0, str(bridge))
    from cfg_grammar import CORPUS, LISTEN_GROUND_TRUTH, SECTION_GROUND_TRUTH, build as _cfg
    import tsgrammar as tg
    result = tg.build_builder(_cfg())
    bundle = result.package(tmp_path / "bundle")
    consumer = tmp_path / "consumer.py"
    consumer.write_text(f"""
import json, sys
from tsquery import Language, M, OutputModel, capture, source_meta

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
