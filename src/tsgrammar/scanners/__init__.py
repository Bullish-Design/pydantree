"""tsgrammar.scanners — the external-scanner library (Phase 5 seed + Phase 6
library). Each scanner is a canonical mechanism with a mini-grammar:

    indent_scanner.c           INDENT/DEDENT/NEWLINE (pymini seed, Phase 5)
    heredoc_scanner.c          HEREDOC_START/BODY   (hmini, Phase 6)
    matched_delimiter_scanner.c BALANCED parens     (dmini, Phase 6)

Grammar authors declare the externals in the scanner's expected order and
pass the path to the build:

    g.external(tg.tok("NEWLINE"), tg.tok("INDENT"), tg.tok("DEDENT"))
    ...
    result = tg.build_builder(g, scanner=tg.indent_scanner_path())

The library table (`scanner_for`) maps grammar names to their canonical
scanner; a scanner build and a scanner-less build are content-addressed
separately in the pipeline cache.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "indent_scanner_path",
    "heredoc_scanner_path",
    "matched_delimiter_scanner_path",
    "scanner_for",
]

_CANONICAL = {
    # grammar name -> scanner.c
    "pymini": "indent_scanner.c",
    "hmini": "heredoc_scanner.c",
    "dmini": "matched_delimiter_scanner.c",
}


def indent_scanner_path() -> Path:
    """Path to the canonical indentation scanner (pymini seed)."""
    return Path(__file__).parent / "indent_scanner.c"


def heredoc_scanner_path() -> Path:
    """Path to the canonical heredoc scanner (HEREDOC_START/BODY, hmini)."""
    return Path(__file__).parent / "heredoc_scanner.c"


def matched_delimiter_scanner_path() -> Path:
    """Path to the canonical balanced-parens scanner (BALANCED, dmini)."""
    return Path(__file__).parent / "matched_delimiter_scanner.c"


def scanner_for(name: str) -> Path | None:
    """Path to the canonical scanner for `name`, or None (the library table:
    pymini/hmini/dmini so far — the full per-language library is Phase 7)."""
    rel = _CANONICAL.get(name)
    return Path(__file__).parent / rel if rel is not None else None
