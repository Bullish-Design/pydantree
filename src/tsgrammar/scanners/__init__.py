"""tsgrammar.scanners — the external-scanner library seed (Phase 5).

One canonical scanner ships now: the INDENT/DEDENT/NEWLINE scanner for
indentation-sensitive languages (`indent_scanner_path()`). Grammar authors
declare the externals in the scanner's expected order and pass the path to
the build:

    g.external(tg.tok("NEWLINE"), tg.tok("INDENT"), tg.tok("DEDENT"))
    ...
    result = tg.build_builder(g, scanner=tg.indent_scanner_path())

The scanner hard-codes the `tree_sitter_<grammar>` export name for the
`pymini` seed grammar; the full scanner library (per-language copies) is a
Phase-6 item.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["indent_scanner_path"]

_CANONICAL = {
    # grammar name -> scanner.c: the INDENT/DEDENT/NEWLINE scanner
    "pymini": "indent_scanner.c",
}


def indent_scanner_path() -> Path:
    """Path to the canonical indentation scanner (pymini seed)."""
    return Path(__file__).parent / "indent_scanner.c"


def scanner_for(name: str) -> Path | None:
    """Path to the canonical scanner for `name`, or None (the library has one
    seed so far — pymini)."""
    rel = _CANONICAL.get(name)
    return Path(__file__).parent / rel if rel is not None else None
