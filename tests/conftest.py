"""Development flow: resolve the packages from `src/` FIRST.

The per-package editable installs (hatchling, flat-layout) place a COPY of
each package in site-packages (a `_editable_impl_*.pth` also adds `src/` to
sys.path, but site-packages precedes it, so the COPY is what plain imports
resolve to). ANY change under `src/` — in-place, a rewrite, or a new module
— is invisible to plain imports until the editable install is re-run. Putting
the repo's `src/` ahead of site-packages makes the suite always exercise the
current code (the same resolution the `.scratch` experiments use via
`sys.path.insert(0, "src")`).

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
