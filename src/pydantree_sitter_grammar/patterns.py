"""pydantree_sitter_grammar.patterns — composable regex STRINGS for the rule-class surface.

Helpers return plain strings in the tree-sitter lexer regex subset (no
backreferences, no lookaround, no escapes the generator rejects) — grammar.json
carries the raw string, so the helper output IS the IR, and plain string
composition is the whole composition story (no second DSL).

Each helper is pinned by a byte-identity test against the exact hand-written
regex it replaces (see tests/test_rules.py / test_patterns.py) — the helpers
are trustworthy only because the gate compares their output to the builder-DSL
spelling of the same grammar.

Shape helpers (`dotted_path`, `path_literal`) are opinionated by construction;
their docstrings document the shape they encode.

    from pydantree_sitter_grammar.patterns import dotted_path, integer, quoted

    class NamePath(Token):
        __pattern__ = dotted_path()          # one token, dotted segments
    class Number(Pattern):
        __pattern__ = integer()              # bare regex leaf
"""

from __future__ import annotations

__all__ = [
    "ident", "integer", "quoted", "slug", "path_literal", "dotted_path",
    "rest_of_line",
]


def ident(*, hyphen: bool = False) -> str:
    """An identifier: `[a-zA-Z_][a-zA-Z0-9_]*`; `hyphen=True` allows `-` in
    the continuation (nix attr names, css classes): `[a-zA-Z_][a-zA-Z0-9_-]*`."""
    return r"[a-zA-Z_][a-zA-Z0-9_-]*" if hyphen else r"[a-zA-Z_][a-zA-Z0-9_]*"


def integer() -> str:
    """A bare integer: `[0-9]+`."""
    return r"[0-9]+"


def quoted(quote: str = '"') -> str:
    """A quoted string with NO escapes inside: `"[^"]*"`. The quote char is
    the only one excluded from the char class (the byte-identity gate caught
    a `[^""]` double-inclusion in the probes)."""
    return f'{quote}[^{quote}]*{quote}'


def slug() -> str:
    """A path-ish chunk: letters, digits, `_`, `.`, `/`, `-`:
    `[A-Za-z0-9_./-]+`."""
    return r"[A-Za-z0-9_./-]+"


def path_literal() -> str:
    """A nix path literal — `./relative/or/absolute`: `\.[/]` + a slug."""
    return r"\.[/]" + slug()


def dotted_path(segment: str | None = None) -> str:
    """A dotted path as ONE token: `pkgs`  `config.env.DEVENV_ROOT`
    `scripts.hello.exec`  `tasks."quoted".exec`.

    Shape: `(SEGMENT)(\.ident|"quoted")*` — the FIRST segment may be quoted
    too (a standalone quoted key); later segments are `\.` + ident-or-quoted
    (nix attr names allow hyphens). The default `segment` reproduces the
    devenv example's exact pattern string:
    `("[^"]*"|[a-zA-Z_][a-zA-Z0-9_-]*)(\.[a-zA-Z_][a-zA-Z0-9_-]*|"[^"]*")*`
    """
    seg = segment or f"{quoted()}|{ident(hyphen=True)}"
    return f"({seg})(\\.{ident(hyphen=True)}|{quoted()})*"


def rest_of_line() -> str:
    """The rest of the line, no newline: `[^\n]*` (comment bodies)."""
    return r"[^\n]*"
