"""tsgrammar.patterns — the helper set, pinned byte-for-byte.

Each helper's output must equal the EXACT regex string it replaces in the
hand-written grammar — grammar.json carries the raw string, so any helper
drift is an IR change (the byte-identity gate would catch it too; these
tests pin each helper directly, including the parameter variants).
"""

from __future__ import annotations

import tsgrammar as tg
from tsgrammar.patterns import (
    dotted_path,
    ident,
    integer,
    path_literal,
    quoted,
    rest_of_line,
    slug,
)


def test_ident():
    assert ident() == r"[a-zA-Z_][a-zA-Z0-9_]*"
    assert ident(hyphen=True) == r"[a-zA-Z_][a-zA-Z0-9_-]*"


def test_integer():
    assert integer() == r"[0-9]+"


def test_quoted():
    # the probe-caught bug: the quote char class must exclude ONLY the quote
    # (`[^"]`, never `[^""]`)
    assert quoted() == r'"[^"]*"'
    assert quoted("'") == r"'[^']*'"
    assert quoted("`") == r"`[^`]*`"


def test_slug():
    assert slug() == r"[A-Za-z0-9_./-]+"


def test_path_literal():
    assert path_literal() == r"\.[/][A-Za-z0-9_./-]+"


def test_dotted_path_matches_the_handwritten_regex():
    """The devenv example's exact name_path pattern — the shape helper's
    default must reproduce it byte-for-byte (the gate depends on it)."""
    assert dotted_path() == (
        r'("[^"]*"|[a-zA-Z_][a-zA-Z0-9_-]*)'
        r'(\.[a-zA-Z_][a-zA-Z0-9_-]*|"[^"]*")*')


def test_dotted_path_custom_segment():
    """The segment override is the first alternative; the continuation is
    always ident-or-quoted."""
    assert dotted_path(segment=r"[a-z]+") == (
        r'([a-z]+)(\.[a-zA-Z_][a-zA-Z0-9_-]*|"[^"]*")*')

def test_rest_of_line():
    assert rest_of_line() == r"[^\n]*"


def test_helpers_are_plain_strings():
    """The helpers return strings — composable with `+`, carried raw in the
    IR, no second DSL."""
    assert isinstance(quoted() + rest_of_line(), str)
