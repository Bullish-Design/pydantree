#!/usr/bin/env python3
"""
Phase 6 — Run 1: the packaging seam at the INSTALL boundary.

The centerpiece: a FRESH venv (no editable src/ on the path, no tsgrammar)
installs ONLY the light wheels (tscore + tsquery) + the community wheel deps,
and runs the full checked extraction there:

  * `import tsgrammar` must FAIL (the seam does not leak);
  * the Phase-5 cfg bundle round-trip (Language.load_bundle -> Jobs 1/3/4 ->
    the cfg record + field ground truth) passes;
  * the community extraction (json schema over tree_sitter_json -> Person
    ground truth) passes;
  * the A surface is byte-identical to the in-repo results (in-process with
    B importable) and to the Phase-5 run_bfree results (B stripped).

Evidence saved verbatim under evidence/ (r1_*).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / ".scratch" / "006-tsquery-bridge"))
sys.path.insert(0, str(ROOT / ".scratch" / "007-tsquery-distribution"))

EVIDENCE = Path(__file__).parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

from bfree import run_bfree  # noqa: E402
from cfg_grammar import (  # noqa: E402
    CORPUS,
    LISTEN_GROUND_TRUTH,
    SECTION_GROUND_TRUTH,
    build as build_cfg,
)
from json_grammar import build as build_json  # noqa: E402
from tsgrammar.schema_tool import derive_schema_for_dir  # noqa: E402


def banner(t: str, width: int = 72) -> None:
    print("\n" + "=" * width + f"\n{t}\n" + "=" * width)


def save(name: str, text: str) -> None:
    (EVIDENCE / name).write_text(text)


def _cfg_bundle(tmp: Path) -> Path:
    import tsgrammar as tg
    result = tg.build_builder(build_cfg())
    return result.package(tmp / "cfg-bundle")


def _json_schema(tmp: Path) -> Path:
    json_model = build_json().build()
    src_dir = tmp / "json-grammar"
    json_model.emit_bundle(src_dir)
    out = tmp / "json-community-schema.json"
    derive_schema_for_dir(src_dir, name="json", out=out, keep=True)
    return out


def _inproc_results(cfg_bundle: Path, json_schema: Path) -> dict:
    """The A surface in-process, with B importable (the Phase-5 in-process
    path): the same models the consumers run, extracted directly."""
    from tscore.schema import NodeSchema
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

    class Person(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        age: int
        tags: list[str]
        nickname: str | None = None
        active: bool = False
        line: int = source_meta()

    import tree_sitter_json

    cfg = Language.load_bundle(cfg_bundle)
    secs = [r.model_dump() for r in ServerSection.extract(CORPUS, language=cfg)]
    listens = [r.model_dump() for r in Listen.extract(CORPUS, language=cfg)]
    schema = NodeSchema.from_node_types_json(json_schema, name="json")
    jlang = Language.load(tree_sitter_json.language(), schema=schema)
    sample_txt = """\
[
  {
    "name": "alice",
    "age": 30,
    "tags": ["red", "blue", "green"],
    "nickname": "ali",
    "active": true
  },
  {
    "name": "bob",
    "age": 41,
    "tags": ["dev"],
    "active": false
  },
  {
    "name": "carol",
    "age": 25,
    "tags": [],
    "score": 98.5,
    "address": {"city": "Paris"}
  },
  {
    "name": "dave",
    "age": 55,
    "tags": ["x", "y", "z", "w"],
    "active": true
  }
]
"""
    people = [r.model_dump() for r in Person.extract(sample_txt, language=jlang)]
    return {"sections": secs, "directives": listens, "people": people}


def _fresh_venv_setup(tmp: Path, wheels: Path) -> Path:
    """Create a fresh venv and install ONLY the light wheels + the community
    wheel deps. Returns the venv dir."""
    venv = tmp / "fresh-venv"
    py = subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(venv)],
        capture_output=True, text=True, check=False)
    if py.returncode != 0:
        raise RuntimeError(f"uv venv failed: {py.stderr or py.stdout}")
    inst = subprocess.run(
        ["uv", "pip", "install", "--python", str(venv / "bin" / "python"),
         "--find-links", str(wheels),
         "pydantree-tscore==0.1.0", "pydantree-tsquery==0.1.0", "tree-sitter-json"],
        capture_output=True, text=True, check=False)
    if inst.returncode != 0:
        raise RuntimeError(f"uv pip install failed: {inst.stderr or inst.stdout}")
    return venv


def _run_in_venv(venv: Path, script: Path, *args) -> str:
    proc = subprocess.run(
        [str(venv / "bin" / "python"), str(script), *args],
        capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{script.name} failed in the fresh venv (rc {proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
    return proc.stdout


def main() -> int:
    banner("Run 1 — the packaging seam at the install boundary")
    tmp = Path(tempfile.mkdtemp(prefix="phase6-run1-"))
    P5 = ROOT / ".scratch" / "007-tsquery-distribution"

    # 1. build the artifacts (B-side, in-repo) — the bundle + community schema
    cfg_bundle = _cfg_bundle(tmp)
    json_schema = _json_schema(tmp)
    print(f"cfg bundle: {cfg_bundle}")
    print(f"json community schema: {json_schema}")

    # 2. build the light wheels (tscore + tsquery only)
    wheels = tmp / "wheels"
    wheels.mkdir()
    for pkg in ("tscore", "tsquery"):
        proc = subprocess.run(
            ["uv", "build", "--out-dir", str(wheels)],
            capture_output=True, text=True, cwd=str(SRC / pkg), check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"uv build {pkg} failed: {proc.stderr or proc.stdout}")
    print(f"light wheels: {sorted(p.name for p in wheels.iterdir())}")

    # 3. the fresh venv: light install only
    venv = _fresh_venv_setup(tmp, wheels)
    banner("fresh venv — import graph")
    graph = subprocess.run(
        [str(venv / "bin" / "python"), "-c",
         "import json; import tscore, tsquery; import tree_sitter;\n"
         "print(json.dumps({'tscore': tscore.__file__, 'tsquery': tsquery.__file__}))"],
        capture_output=True, text=True, check=False)
    print(graph.stdout, graph.stderr)
    save("r1_fresh_import_graph.txt",
         graph.stdout + graph.stderr + f"(rc {graph.returncode})\n")

    # 4. the honest assertion: tsgrammar must NOT be importable
    banner("fresh venv — tsgrammar unimportable (the seam does not leak)")
    no_b = subprocess.run(
        [str(venv / "bin" / "python"), "-c", "import tsgrammar"],
        capture_output=True, text=True, check=False)
    print(f"import tsgrammar -> rc {no_b.returncode}: "
          f"{no_b.stderr.strip()[:120]}")
    assert no_b.returncode != 0, "tsgrammar IS importable in the light install!"
    save("r1_fresh_tsgrammar_unimportable.txt",
         f"rc {no_b.returncode}\n{no_b.stderr}\n")

    # 5. the end-to-end extraction in the fresh venv
    banner("fresh venv — the Phase-5 bundle round-trip + community extraction")
    cfg_out = _run_in_venv(venv, P5 / "consumer.py", str(cfg_bundle))
    com_out = _run_in_venv(venv, P5 / "consumer_community.py", str(json_schema))
    print(cfg_out)
    print(com_out)
    save("r1_fresh_cfg_consumer.txt", cfg_out)
    save("r1_fresh_json_consumer.txt", com_out)
    fresh_cfg = json.loads(cfg_out)
    fresh_com = json.loads(com_out)

    # 6. byte-identical vs the in-repo results (B importable, in-process)
    banner("byte-identical A surface: fresh venv vs in-repo (B importable)")
    inproc = _inproc_results(cfg_bundle, json_schema)
    ok_cfg = fresh_cfg["sections"] == inproc["sections"] and \
        fresh_cfg["directives"] == inproc["directives"] and \
        fresh_cfg["sections"] == SECTION_GROUND_TRUTH and \
        fresh_cfg["directives"] == LISTEN_GROUND_TRUTH
    ok_com = fresh_com["rows"] == inproc["people"]
    print(f"cfg sections byte-identical: {fresh_cfg['sections'] == inproc['sections']}")
    print(f"cfg directives byte-identical: {fresh_cfg['directives'] == inproc['directives']}")
    print(f"json people byte-identical: {ok_com}")
    print(f"cfg ground truth: {ok_cfg}")
    save("r1_byte_identical.txt",
         json.dumps({
             "fresh_vs_inproc_cfg_sections":
                 fresh_cfg["sections"] == inproc["sections"],
             "fresh_vs_inproc_cfg_directives":
                 fresh_cfg["directives"] == inproc["directives"],
             "fresh_vs_inproc_json_people": ok_com,
             "cfg_ground_truth": ok_cfg,
             "fresh_cfg_sections": fresh_cfg["sections"],
             "fresh_json_rows": fresh_com["rows"],
         }, indent=2))

    # 7. the Phase-5 B-free subprocess comparison (same consumer, B stripped)
    banner("byte-identical A surface: fresh venv vs run_bfree (B stripped)")
    rc, bfree_cfg = run_bfree(P5 / "consumer.py", str(cfg_bundle))
    assert rc == 0, bfree_cfg
    print(f"fresh vs bfree cfg sections: "
          f"{fresh_cfg['sections'] == json.loads(bfree_cfg)['sections']}")

    verdict = ok_cfg and ok_com
    print()
    print("VERDICT:", "GO — the light install delivers A without B at the "
          "install boundary" if verdict else "NO-GO")
    save("r1_verdict.txt", f"verdict: {'GO' if verdict else 'NO-GO'}\n")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
