"""Phase-5 external-scanner tests: the escape hatch made airtight.

Covers: the pipeline raises a CLEAR ExternalScannerRequiredError when a
grammar declares externals but no scanner is supplied (instead of a gcc link
failure); the canonical indentation scanner (the library's seed) builds and
parses the pymini mini-Python grammar — INDENT/DEDENT/NEWLINE, nested blocks,
comment-only lines inside a block, EOF dedents.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar.corpus import Corpus, corpus_case


pytestmark = [pytest.mark.toolchain, pytest.mark.slow]


import pymini  # noqa: E402


def test_externals_without_scanner_raises_clear_error(tmp_path):
    g = pymini.build()
    with pytest.raises(tg.ExternalScannerRequiredError) as exc:
        tg.build_builder(g, cache_dir=tmp_path / "cache")
    assert "external scanner required" in str(exc.value)
    assert "NEWLINE" in str(exc.value) and "INDENT" in str(exc.value)


def test_pymini_builds_and_parses_with_scanner(tmp_path):
    g = pymini.build()
    issues = list(tg.run_checks(g))
    assert not tg.errors(g), issues
    result = tg.build_builder(g, scanner=tg.indent_scanner_path(),
                               cache_dir=tmp_path / "cache")
    lang = result.language()
    r = Corpus([corpus_case(pymini.GOOD, pymini.GOOD_EXPECTED,
                            name="plain blocks"),
                corpus_case(pymini.NESTED, pymini.NESTED_EXPECTED,
                            name="nested blocks")],
               name="pymini").run(build_result=result)
    assert r.ok(), r.report()


def test_pymini_comment_line_inside_block_keeps_block(tmp_path):
    """A comment-only line is not a NEWLINE token (Python semantics): the
    block does not break."""
    g = pymini.build()
    result = tg.build_builder(g, scanner=tg.indent_scanner_path(),
                              cache_dir=tmp_path / "cache")
    lang = result.language()
    tree = tg.parse(lang, pymini.COMMENT_IN_BLOCK)
    errs = []

    def walk(n):
        if n.type == "ERROR" or n.is_missing:
            errs.append(n.type)
        for c in n.children:
            walk(c)
    walk(tree.root_node)
    assert not errs, errs
    # the block has ONE statement (b = 1) — the comment is an extra
    ifs = tree.root_node.named_children[0]
    assert ifs.type == "if_stmt"
    assert ifs.child_by_field_name("cond").type == "expr"


def test_pymini_dedent_at_eof(tmp_path):
    """EOF with open indentation flushes the pending DEDENTs."""
    g = pymini.build()
    result = tg.build_builder(g, scanner=tg.indent_scanner_path(),
                              cache_dir=tmp_path / "cache")
    lang = result.language()
    tree = tg.parse(lang, "if a:\n    b = 1\n")
    errs = []

    def walk(n):
        if n.type == "ERROR" or n.is_missing:
            errs.append(n.type)
        for c in n.children:
            walk(c)
    walk(tree.root_node)
    assert not errs, errs
    assert tree.root_node.named_children[0].type == "if_stmt"


def test_indent_handling_is_lenient_at_invalid_states(tmp_path):
    """The scanner only emits INDENT/DEDENT where the grammar can use them;
    at a top-level state INDENT is never valid, so a stray indent is silently
    accepted (the lexer proceeds to the token). This is the seed's documented
    leniency — strictness is the grammar's job (e.g. requiring DEDENT)."""
    g = pymini.build()
    result = tg.build_builder(g, scanner=tg.indent_scanner_path(),
                              cache_dir=tmp_path / "cache")
    lang = result.language()
    tree = tg.parse(lang, "x = 1\n    y = 2\n")  # stray indent at top level
    errs = []

    def walk(n):
        if n.type == "ERROR" or n.is_missing:
            errs.append(n.type)
        for c in n.children:
            walk(c)
    walk(tree.root_node)
    assert not errs  # lenient: parses as two top-level assignments


# ---------------------------------------------------------------------------
# Phase 6 — the scanner library seeds (heredoc + matched delimiter)
# ---------------------------------------------------------------------------

CONSUMERS = Path(__file__).resolve().parent / "fixtures" / "consumers"

import dmini  # noqa: E402
import hmini  # noqa: E402


def _parse_errs(lang, text) -> list:
    tree = tg.parse(lang, text)
    errs = []

    def walk(n):
        if n.type == "ERROR" or n.is_missing:
            errs.append((n.type, n.start_point.row + 1))
        for c in n.children:
            walk(c)
    walk(tree.root_node)
    return errs


def test_heredoc_scanner_builds_and_parses(tmp_path):
    """The heredoc seed (HEREDOC_START/BODY): `<<TAG` + content lines + the
    delimiter line — the BODY token includes the delimiter line (bash-like),
    the trailing newline is a regular token."""
    g = hmini.build()
    result = tg.build_builder(g, scanner=tg.heredoc_scanner_path(),
                              cache_dir=tmp_path / "cache")
    lang = result.language()
    r = Corpus([corpus_case(hmini.GOOD, hmini.GOOD_EXPECTED, name="heredoc")],
               name="hmini").run(build_result=result)
    assert r.ok(), r.report()


def test_heredoc_empty_body_and_nested_markers(tmp_path):
    """An empty heredoc body (two consecutive delimiter lines) parses; content
    that LOOKS like a nested marker (parens, braces) is inert inside the
    body — only the exact delimiter line ends it."""
    g = hmini.build()
    result = tg.build_builder(g, scanner=tg.heredoc_scanner_path(),
                              cache_dir=tmp_path / "cache")
    lang = result.language()
    assert not _parse_errs(lang, hmini.EMPTY_BODY)
    assert not _parse_errs(lang, hmini.NESTED_MARKER)


def test_heredoc_scanner_for_registered_in_library():
    """The scanner library table now covers the three seeds."""
    assert tg.scanner_for("hmini") == tg.heredoc_scanner_path()
    assert tg.scanner_for("dmini") == tg.matched_delimiter_scanner_path()
    assert tg.scanner_for("pymini") == tg.indent_scanner_path()
    assert tg.scanner_for("no_such_grammar") is None


def test_matched_delimiter_scanner_builds_and_parses(tmp_path):
    """The balanced-parens seed: a `(...)` group with arbitrary nesting is
    ONE external token (the inner parens never reach the grammar)."""
    g = dmini.build()
    result = tg.build_builder(g, scanner=tg.matched_delimiter_scanner_path(),
                              cache_dir=tmp_path / "cache")
    lang = result.language()
    r = Corpus([corpus_case(dmini.GOOD, dmini.GOOD_EXPECTED, name="groups")],
               name="dmini").run(build_result=result)
    assert r.ok(), r.report()
    # the nested group is ONE token
    tree = tg.parse(lang, "a = (1 + (2))\n")
    group = tree.root_node.named_children[0].child_by_field_name("value")
    assert group.type == "group"
    assert group.child(0).type == "BALANCED"


def test_matched_delimiter_scanner_is_strict(tmp_path):
    """An unbalanced group at EOF is REFUSED by the scanner (strict): the
    parse falls back and errors — the open paren is not silently swallowed."""
    g = dmini.build()
    result = tg.build_builder(g, scanner=tg.matched_delimiter_scanner_path(),
                              cache_dir=tmp_path / "cache")
    lang = result.language()
    assert _parse_errs(lang, dmini.UNBALANCED)


# ---------------------------------------------------------------------------
# Phase 7 — the scanner library's per-language copies (pyindent + bashmini)
# ---------------------------------------------------------------------------



import bashmini  # noqa: E402
import pyindent  # noqa: E402


def _corpus(name, mod, scanner, tmp_path, cases):
    g = mod.build()
    result = tg.build_builder(g, scanner=scanner, cache_dir=tmp_path / "cache")
    r = Corpus([corpus_case(text, expected, name=label)
                for label, (text, expected) in cases.items()],
               name=name).run(build_result=result)
    assert r.ok(), r.report()


def test_pyindent_real_python_logical_lines(tmp_path):
    """The real-Python indentation scanner (adapted from tree-sitter-python):
    comment-only lines and blank lines emit NO NEWLINE; a backslash
    continuation keeps the logical line open; the header's NEWLINE and the
    block's INDENT come from the two-call zero-width cadence."""
    _corpus("pyindent", pyindent, tg.py_indent_scanner_path(), tmp_path, {
        "plain blocks": (pyindent.GOOD, pyindent.GOOD_EXPECTED),
        "comment in block": (pyindent.COMMENT_IN_BLOCK,
                              pyindent.COMMENT_IN_BLOCK_EXPECTED),
        "continuation": (pyindent.CONTINUATION,
                         pyindent.CONTINUATION_EXPECTED),
        "trailing comment": (pyindent.TRAILING_COMMENT,
                              pyindent.TRAILING_COMMENT_EXPECTED),
        "dedent at eof": (pyindent.DEDENT_AT_EOF,
                           pyindent.DEDENT_AT_EOF_EXPECTED),
    })


def test_pyindent_blank_line_in_block(tmp_path):
    """Blank lines inside a block are skipped (no NEWLINE, block continues) —
    a real Python semantic."""
    g = pyindent.build()
    result = tg.build_builder(g, scanner=tg.py_indent_scanner_path(),
                              cache_dir=tmp_path / "cache")
    lang = result.language()
    assert not _parse_errs(lang, pyindent.BLANK_IN_BLOCK)
    tree = tg.parse(lang, pyindent.BLANK_IN_BLOCK)
    blk = tree.root_node.named_children[0]
    assert blk.type == "if_stmt"


def test_pyindent_empty_block_is_parse_error(tmp_path):
    """A header with no body is a parse ERROR (the real shape needs at least
    one statement inside the block)."""
    g = pyindent.build()
    result = tg.build_builder(g, scanner=tg.py_indent_scanner_path(),
                              cache_dir=tmp_path / "cache")
    lang = result.language()
    assert _parse_errs(lang, pyindent.EMPTY_BLOCK)


def test_bashmini_multi_heredoc_pending_queue(tmp_path):
    """The bash-style heredoc scanner (adapted from tree-sitter-bash): the
    MULTI-heredoc case — `cat <<A <<B` queues BOTH delimiters and the bodies
    are served in OPENING order, one BODY token each."""
    _corpus("bashmini", bashmini, tg.bash_heredoc_scanner_path(), tmp_path, {
        "plain heredoc": (bashmini.GOOD, bashmini.GOOD_EXPECTED),
        "multi heredoc": (bashmini.MULTI, bashmini.MULTI_EXPECTED),
        "indent-stripped": (bashmini.INDENTED, bashmini.INDENTED_EXPECTED),
        "quoted delimiter": (bashmini.QUOTED, bashmini.QUOTED_EXPECTED),
        "empty body": (bashmini.EMPTY, bashmini.EMPTY_EXPECTED),
        "prefix not delimiter": (bashmini.PREFIX_LINE,
                                  bashmini.PREFIX_LINE_EXPECTED),
        "unterminated at eof": (bashmini.UNTERMINATED,
                                 bashmini.UNTERMINATED_EXPECTED),
    })


def test_bashmini_no_delimiter_is_parse_error(tmp_path):
    """`<<` with no delimiter word is a parse ERROR (the scanner declines)."""
    g = bashmini.build()
    result = tg.build_builder(g, scanner=tg.bash_heredoc_scanner_path(),
                              cache_dir=tmp_path / "cache")
    lang = result.language()
    assert _parse_errs(lang, bashmini.NO_DELIMITER)


def test_phase7_scanners_registered_in_library():
    """The scanner library table now covers the Phase-7 per-language copies."""
    assert tg.scanner_for("pyindent") == tg.py_indent_scanner_path()
    assert tg.scanner_for("bashmini") == tg.bash_heredoc_scanner_path()
    assert tg.scanner_for("hmini") == tg.heredoc_scanner_path()
    assert tg.scanner_for("pymini") == tg.indent_scanner_path()
    assert tg.scanner_for("no_such_grammar") is None
