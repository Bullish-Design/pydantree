"""Phase-5/6 consumer environment: makes tsgrammar (B) genuinely NOT
importable in the B-free subprocess.

Two mechanisms, both needed since the Phase-6 distribution split:

  * Phase 5: the devenv's site-packages used to hold a .pth pointing at the
    repo's src/ (the monolith editable). This sitecustomize removes that
    entry, so the only path to tscore/tsquery in the consumer process is the
    copies this directory's lib/ provides (made by the experiment runner).
  * Phase 6: the per-package editable installs (tscore/tsquery/tsgrammar)
    now live DIRECTLY in site-packages (hatchling hard-links the flat-layout
    packages), so stripping the src path is no longer enough. A meta-path
    finder blocks `tsgrammar` at the finder level — the B-free boundary is
    enforced by construction, not by path hygiene.

The consumer script itself also asserts `import tsgrammar` fails, so a leak
fails the run loudly.
"""

from __future__ import annotations

import importlib.abc
import sys

_MARKER = "pydantree/src"

sys.path = [p for p in sys.path if _MARKER not in p]


class _BFreeBlocker(importlib.abc.MetaPathFinder):
    """Block tsgrammar (B) for this process regardless of what sys.path
    resolution would find (the editable install is in site-packages)."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "tsgrammar" or fullname.startswith("tsgrammar."):
            raise ModuleNotFoundError(
                f"No module named {fullname!r} (B-free consumer: tsgrammar "
                f"is deliberately unimportable in this process)")
        return None


sys.meta_path.insert(0, _BFreeBlocker())

# keep a record for the experiment's evidence
import site  # noqa: E402
try:
    _log = site.getusersitepackages()  # noqa: F841  (touch site module)
except Exception:  # pragma: no cover
    pass
