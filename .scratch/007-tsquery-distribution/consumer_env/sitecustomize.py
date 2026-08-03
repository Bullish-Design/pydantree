"""Phase-5 consumer environment: strips the editable src/ install so tsgrammar
(B) is genuinely NOT importable in the B-free subprocess.

The devenv venv's site-packages contains a .pth pointing at the repo's src/
(which holds tsgrammar, tscore, tsquery). This sitecustomize runs at
interpreter startup (after .pth processing) and removes that entry — so the
only way to reach tscore/tsquery in the consumer process is the copies this
directory's lib/ provides (made by the experiment runner). The consumer
script itself also asserts `import tsgrammar` fails, so a leak fails the run.
"""

from __future__ import annotations

import sys

_MARKER = "pydantree/src"

sys.path = [p for p in sys.path if _MARKER not in p]

# keep a record for the experiment's evidence
import site  # noqa: E402
try:
    _log = site.getusersitepackages()  # noqa: F841  (touch site module)
except Exception:  # pragma: no cover
    pass
