"""Run 2 — the B-free consumer (the artifact seam in production).

Consumes a packaged grammar bundle in a SEPARATE process where pydantree_sitter_grammar is
NOT importable (its only path — the editable src/ install — is stripped by
consumer_env/sitecustomize.py). A never imports B; the bundle + pydantree_sitter's
shared loader are the whole seam. Runs the Phase-4 record + field tasks
against the hand-computed ground truth with the schema checks active.

Usage: python consumer.py <bundle-dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# the honest assertion: B must NOT be importable in this process
try:
    import pydantree_sitter_grammar  # noqa: F401
    print(json.dumps({"ok": False,
                      "error": "pydantree_sitter_grammar IS importable — B leaked into the "
                               "consumer process"}))
    sys.exit(1)
except ModuleNotFoundError:
    pass

from pydantree_sitter import Language, M, OutputModel, capture, source_meta  # noqa: E402

BUNDLE = Path(sys.argv[1])

# ---- the two Phase-4 tasks, model-only (identical surface to in-process) ---

class ServerSection(OutputModel):
    """Record mode: a [section] is an order-independent key/value record."""

    __match__ = M("source_file", "section", record=True)
    host: str
    port: int
    debug: bool = False
    title: str | None = None
    line: int = source_meta()


class Listen(OutputModel):
    """Field mode: structured directives; `port: int` derives its kind
    constraint from the schema (no NodeKind override)."""

    __match__ = M("source_file", "directive")
    name: str = capture("name")
    port: int = capture("arg")
    line: int = source_meta()


CORPUS = """\
; app.cfg
[server]
host = example.com
port = 8080
debug = true
title = "My App"
ratio = 0.75

[client]
host = localhost
port = 9090
debug = false

listen 8080
include "base.conf"
reload 5
"""

SECTION_GROUND_TRUTH = [
    {"host": "example.com", "port": 8080, "debug": True,
     "title": "My App", "line": 2},
    {"host": "localhost", "port": 9090, "debug": False,
     "title": None, "line": 9},
]
LISTEN_GROUND_TRUTH = [
    {"name": "listen", "port": 8080, "line": 14},
    {"name": "reload", "port": 5, "line": 16},
]


def main() -> int:
    lang = Language.load_bundle(BUNDLE)
    # checks active BEFORE any text is parsed
    ServerSection.validate_with(lang)
    Listen.validate_with(lang)
    secs = [r.model_dump() for r in
            ServerSection.extract(CORPUS, language=lang)]
    listens = [r.model_dump() for r in Listen.extract(CORPUS, language=lang)]
    ok = (secs == SECTION_GROUND_TRUTH) and (listens == LISTEN_GROUND_TRUTH)
    print(json.dumps({
        "ok": ok,
        "sections": secs,
        "directives": listens,
        "schema_bound": lang.schema is not None,
    }, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
