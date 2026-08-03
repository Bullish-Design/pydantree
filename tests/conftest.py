"""Development flow: resolve the packages from `src/` FIRST.

The per-package editable installs (hatchling, flat-layout) HARD-LINK the
package files into site-packages — in-place edits propagate, but any file
replacement (a new inode, e.g. `git checkout`, a rewrite, a new module)
leaves the installed copy stale. Putting the repo's `src/` ahead of
site-packages makes the suite always exercise the current code (the same
resolution the `.scratch` experiments use via `sys.path.insert(0, "src")`).

The PACKAGING claims are still tested against the installed/wheel artifacts:
`tests/test_packaging.py` builds and inspects the actual wheels, the
fresh-venv test installs them, and the B-free consumers copy `src/` into a
consumer env — all independent of this path ordering.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
# unconditional: an existing (late) src entry must not let the hard-linked
# site-packages copies win
sys.path.insert(0, str(SRC))
