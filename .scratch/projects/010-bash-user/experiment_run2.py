#!/usr/bin/env python3
"""
Phase 8 — Run 2: the bash consumer through the LIGHT install, BOTH
real-user shapes, byte-identical.

  1. the wheels: pydantree-tscore + pydantree-tsquery built from src/
     (uv build) into a wheelhouse;
  2. a FRESH venv with ONLY the light wheels + tree-sitter-bash from the
     REAL index (the wheel shape's "hundreds of grammars" install);
  3. the community bundle built in-repo (B available);
  4. the SAME consumer (consumer_bash.py) runs in three shapes:
       a. in-repo bundle shape  (B importable)
       b. fresh-venv bundle shape (B-free — Language.load_bundle)
       c. fresh-venv WHEEL shape  (B-free — tree_sitter_bash.language()
          + the derived schema bound explicitly)
  5. the extraction payloads must be byte-identical across all three.

Evidence saved verbatim under evidence/ (r8_r2_*).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

EVIDENCE = Path(__file__).parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

CONSUMER = Path(__file__).parent / "consumer_bash.py"
CORPUS = ROOT / "examples" / "bash-extract"
SITECUSTOMIZE = (ROOT / ".scratch" / "007-tsquery-distribution"
                 / "consumer_env" / "sitecustomize.py")
BASH_FIXTURE = ROOT / "tests" / "fixtures" / "bash"


def banner(t: str, width: int = 72) -> None:
    print("\n" + "=" * width + f"\n{t}\n" + "=" * width)


def save(name: str, text: str) -> None:
    (EVIDENCE / name).write_text(text)


def run(cmd: list[str], cwd: Path | None = None,
        env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          cwd=str(cwd) if cwd else None, env=env, check=False)


def consumer_payload(out: str) -> str:
    """The byte-identical comparison payload: the extraction rows + checks,
    minus the run-shape markers (mode, tsgrammar_importable — those differ
    BY DESIGN between the B-importable and B-free runs)."""
    d = json.loads(out)
    canon = {"ok": d["ok"], "schema_bound": d["schema_bound"],
             "schema_kinds": d["schema_kinds"], "files": d["files"]}
    return json.dumps(canon, indent=2)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="phase8-run2-"))
    banner("Run 2 — the light-install bash consumer, both shapes")

    # 0. build the light wheels
    banner("0. build the light wheels (tscore + tsquery)")
    wheelhouse = tmp / "wheels"
    wheelhouse.mkdir()
    for pkg in ("tscore", "tsquery"):
        p = run(["uv", "build", "--out-dir", str(wheelhouse)],
                cwd=SRC / pkg)
        assert p.returncode == 0, p.stderr or p.stdout
        print(f"  built {pkg}: {sorted(w.name for w in wheelhouse.glob('*'))}")

    # 1. the fresh venv: ONLY the light wheels + tree-sitter-bash (real index)
    banner("1. fresh venv: light wheels + tree-sitter-bash from the real index")
    venv = tmp / "fresh-venv"
    p = run(["uv", "venv", "--python", sys.executable, str(venv)])
    assert p.returncode == 0, p.stderr or p.stdout
    p = run(["uv", "pip", "install", "--python", str(venv / "bin" / "python"),
             "--find-links", str(wheelhouse),
             "pydantree-tscore==0.1.0", "pydantree-tsquery==0.1.0",
             "tree-sitter-bash"],
            env={**os.environ, "UV_HTTP_TIMEOUT": "300"})
    assert p.returncode == 0, p.stderr or p.stdout
    # the seam does not leak: tsgrammar unimportable in the light install
    p = run([str(venv / "bin" / "python"), "-c",
             "import tsgrammar"])
    tsg_rc = p.returncode
    print(f"  fresh venv `import tsgrammar` rc: {tsg_rc} (must be != 0)")
    p = run([str(venv / "bin" / "python"), "-c",
             "import tree_sitter_bash, importlib.metadata; "
             "print(importlib.metadata.version('tree-sitter-bash'))"])
    wheel_version = p.stdout.strip()
    print(f"  tree-sitter-bash wheel: {wheel_version!r}")

    # 2. the community bundle (in-repo, B available)
    banner("2. the community bundle from the vendored source")
    from tsgrammar.schema_tool import build_community_bundle
    bundle = build_community_bundle(BASH_FIXTURE, tmp / "bundle",
                                    name="bash", keep=True)
    sizes = {p.name: p.stat().st_size for p in bundle.iterdir()}
    print(json.dumps(sizes, indent=2))
    save("r8_r2_bundle_manifest.txt", json.dumps(sizes, indent=2) + "\n")

    # 3. the consumer env (sitecustomize blocks tsgrammar by construction)
    banner("3. consumer env (B-free boundary by construction)")
    env = tmp / "consumer_env"
    (env / "lib").mkdir(parents=True)
    shutil.copyfile(SITECUSTOMIZE, env / "sitecustomize.py")
    shutil.copyfile(CONSUMER, env / "consumer_bash.py")
    pyenv = dict(os.environ)
    pyenv["PYTHONPATH"] = os.pathsep.join([
        str(env), str(env / "lib"),
        pyenv.get("PYTHONPATH", "")])

    # 4. the three runs
    banner("4. run the consumer in all three shapes")
    corpus = str(CORPUS)

    def go(label: str, python: str, extra_env: dict, *args: str) -> str:
        e = dict(os.environ) if label.startswith("inrepo") else {**pyenv, **extra_env}
        if label.startswith("inrepo"):
            # the in-repo run resolves tscore/tsquery from src/ via the
            # devenv's _pydantree_src.pth — NO sitecustomize (it strips
            # the src/ path), and B stays importable
            e = {**os.environ, **extra_env}
        p = run([python, str(env / "consumer_bash.py"), corpus, *args],
                cwd=tmp, env=e)
        if p.returncode != 0:
            print(f"  {label}: rc {p.returncode}\n{p.stdout}\n{p.stderr}")
            save(f"r8_r2_{label}.txt", f"rc {p.returncode}\n{p.stdout}\n{p.stderr}")
            raise SystemExit(f"{label} failed (rc {p.returncode})")
        (EVIDENCE / f"r8_r2_{label}.txt").write_text(p.stdout)
        print(f"  {label}: ok={json.loads(p.stdout)['ok']}")
        return p.stdout

    a = go("inrepo_bundle", sys.executable, {},
           "bundle", str(bundle))
    b = go("bfree_bundle", str(venv / "bin" / "python"),
           {"BFREE_REQUIRED": "1"}, "bundle", str(bundle))
    schema_dir = tmp / "schema"
    schema_dir.mkdir()
    shutil.copyfile(bundle / "node-schema.json",
                    schema_dir / "node-schema.json")
    c = go("bfree_wheel", str(venv / "bin" / "python"),
           {"BFREE_REQUIRED": "1"}, "wheel", str(schema_dir))

    # 5. the byte-identical comparison
    banner("5. byte-identical comparison (extraction payloads)")
    pa, pb, pc = consumer_payload(a), consumer_payload(b), consumer_payload(c)
    print(f"  in-repo bundle == fresh bundle: {pa == pb}")
    print(f"  in-repo bundle == fresh wheel: {pa == pc}")
    print(f"  fresh bundle == fresh wheel:   {pb == pc}")
    identical = pa == pb == pc
    save("r8_r2_byte_identical.txt",
         f"in-repo bundle == fresh-venv bundle: {pa == pb}\n"
         f"in-repo bundle == fresh-venv wheel:  {pa == pc}\n"
         f"fresh-venv bundle == fresh-venv wheel: {pb == pc}\n"
         f"all three byte-identical: {identical}\n")

    banner("VERDICT")
    ok = tsg_rc != 0 and wheel_version and identical
    print("Run 2:", "GO — the light install delivers the bash consumer in "
          "BOTH shapes, B-free, byte-identical"
          if ok else "NO-GO")
    save("r8_r2_verdict.txt",
         f"verdict: {'GO' if ok else 'NO-GO'}\n"
         f"fresh `import tsgrammar` rc: {tsg_rc} (seam does not leak)\n"
         f"tree-sitter-bash wheel: {wheel_version}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
