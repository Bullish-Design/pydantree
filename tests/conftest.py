"""Development flow: resolve the packages from `src/` FIRST.

The devenv venv resolves pydantree_sitter / pydantree_sitter_grammar straight from `src/` via a
`_pydantree_src.pth` (see devenv.nix — uv sync with --no-install-workspace,
so no copies exist to go stale). This conftest does the same resolution as
belt-and-suspenders (and keeps the suite honest when the devenv is bypassed
or a bare venv with editable copies is used) — the same resolution the
`.scratch` experiments use via `sys.path.insert(0, "src")`.

The PACKAGING claims are still tested against the installed/wheel artifacts:
`tests/test_packaging.py` builds and inspects the actual wheels, the
fresh-venv test installs them, and the B-free consumers copy `src/` into a
consumer env — all independent of this path ordering.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
# unconditional: an existing (late) src entry must not let the
# site-packages copies win
sys.path.insert(0, str(SRC))
