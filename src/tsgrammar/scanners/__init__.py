"""tsgrammar.scanners — the external-scanner library (Phase 5 seed + Phase 6
library + Phase 7 per-language copies). Each scanner is a canonical mechanism
with a mini-grammar:

    indent_scanner.c           INDENT/DEDENT/NEWLINE (pymini seed, Phase 5)
    heredoc_scanner.c          HEREDOC_START/BODY   (hmini, Phase 6)
    matched_delimiter_scanner.c BALANCED parens     (dmini, Phase 6)
    py_indent_scanner.c        NEWLINE/INDENT/DEDENT with REAL Python
                               logical-line semantics (pyindent, Phase 7 —
                               adapted from tree-sitter-python's scanner.c)
    bash_heredoc_scanner.c     HEREDOC_START/BODY/END with the MULTI-heredoc
                               pending queue + `<<-` indent-stripped + quoted
                               delimiters (bashmini, Phase 7 — adapted from
                               tree-sitter-bash's scanner.c)

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
    "py_indent_scanner_path",
    "bash_heredoc_scanner_path",
    "scanner_for",
]

_CANONICAL = {
    # grammar name -> scanner.c
    "pymini": "indent_scanner.c",
    "hmini": "heredoc_scanner.c",
    "dmini": "matched_delimiter_scanner.c",
    "pyindent": "py_indent_scanner.c",
    "bashmini": "bash_heredoc_scanner.c",
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


def py_indent_scanner_path() -> Path:
    """Path to the real-Python-semantics indentation scanner (NEWLINE/INDENT/
    DEDENT over logical lines, adapted from tree-sitter-python; pyindent)."""
    return Path(__file__).parent / "py_indent_scanner.c"


def bash_heredoc_scanner_path() -> Path:
    """Path to the bash-style heredoc scanner (HEREDOC_START/BODY/END with the
    multi-heredoc pending queue, adapted from tree-sitter-bash; bashmini)."""
    return Path(__file__).parent / "bash_heredoc_scanner.c"


def scanner_for(name: str) -> Path | None:
    """Path to the canonical scanner for `name`, or None (the library table:
    pymini/hmini/dmini/pyindent/bashmini — the per-language copies grow on
    the same airtight mechanism)."""
    rel = _CANONICAL.get(name)
    return Path(__file__).parent / rel if rel is not None else None
