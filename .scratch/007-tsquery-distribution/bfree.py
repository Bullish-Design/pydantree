"""B-free subprocess machinery for Run 2 (tests + experiment).

`run_bfree(script, *args)` runs a consumer script in a SEPARATE interpreter
where tsgrammar is genuinely NOT importable:

  * a fresh consumer env dir gets copies of `tscore` and `tsquery` (A's own
    packages — never tsgrammar);
  * a `sitecustomize.py` (this directory's consumer_env/) strips the editable
    `src/` install entry from sys.path at interpreter startup, so the only
    path to tsgrammar is gone;
  * the consumer script itself asserts `import tsgrammar` raises
    ModuleNotFoundError, so any leak fails the run loudly.

Returns (returncode, stdout_text). The interpreter is the caller's
(sys.executable), so the venv's tree_sitter/pydantic wheels are available.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
ENV_TEMPLATE = Path(__file__).resolve().parent / "consumer_env"


def build_consumer_env(workdir: Path) -> Path:
    """Materialize the consumer env: sitecustomize + lib/ copies of
    tscore/tsquery. Returns the env dir."""
    env = workdir / "consumer_env"
    if env.exists():
        shutil.rmtree(env)
    (env / "lib").mkdir(parents=True)
    shutil.copyfile(ENV_TEMPLATE / "sitecustomize.py", env / "sitecustomize.py")
    for pkg in ("tscore", "tsquery"):
        shutil.copytree(SRC / pkg, env / "lib" / pkg)
    return env


def run_bfree(script: Path, *args: str, workdir: Path | None = None,
              env_dir: Path | None = None) -> tuple[int, str]:
    """Run `script` in a B-free subprocess. `workdir` is where the consumer
    env lives (a temp dir by default); `env_dir` may be passed to reuse one.
    Returns (returncode, stdout)."""
    import tempfile
    work = workdir if workdir is not None \
        else Path(tempfile.mkdtemp(prefix="phase5-bfree-"))
    env = env_dir if env_dir is not None else build_consumer_env(work)
    env_vars = dict(os.environ)
    env_vars["PYTHONPATH"] = os.pathsep.join([
        str(env), str(env / "lib"),
        env_vars.get("PYTHONPATH", "")])
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, env=env_vars, cwd=str(work),
        check=False)
    return proc.returncode, proc.stdout


def ensure_consumer_env(workdir: Path) -> Path:
    """Idempotent env materialization for the experiment runner."""
    return build_consumer_env(workdir)
