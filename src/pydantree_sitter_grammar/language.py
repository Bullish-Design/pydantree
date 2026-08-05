"""
pydantree_sitter_grammar.language — loading a compiled grammar .so into tree_sitter.Language
and parsing.

The loading contract lives in `pydantree_sitter.loader` (CONCEPT §8: pydantree_sitter owns the
artifact-loading contract, so a bundle consumed by Product A loads through
the same code path). This module is B's re-export of that contract plus the
parse convenience wrapper.
"""

from __future__ import annotations

import tree_sitter

# REVIEW 018 B20: the .so's library must stay alive for the language's
# lifetime; previously load_language returned the (language, lib) tuple and
# callers had to remember to keep `lib` — parse()/Parser() take a BARE
# language, so the shape mismatch bit exactly there. The registry holds the
# library for the process lifetime (a bounded, deliberate keep-alive —
# languages are few and long-lived).
_KEEPALIVE: list = []


def load_language(so_path, grammar_name: str | None = None):
    """Load a compiled grammar .so into a tree_sitter.Language.

    Delegates to pydantree_sitter.loader.load_grammar_so (the shared contract — a
    bundle's loader.py uses the same path). `grammar_name` is the export
    symbol (`tree_sitter_<name>`) and defaults to the .so's file stem.
    Returns the LANGUAGE — the underlying library is kept alive by this
    module's registry (parse()/Parser() take a bare language).
    """
    from pydantree_sitter.loader import load_grammar_so
    language, lib = load_grammar_so(so_path, grammar_name)
    _KEEPALIVE.append(lib)
    return language


def parse(lang, source: str, encoding: str = "utf-8"):
    """Parse text with the loaded language (a small convenience wrapper)."""
    parser = tree_sitter.Parser(lang)
    return parser.parse(source.encode(encoding))
