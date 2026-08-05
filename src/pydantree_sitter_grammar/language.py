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


def load_language(so_path, grammar_name: str | None = None):
    """Load a compiled grammar .so into a tree_sitter.Language.

    Delegates to pydantree_sitter.loader.load_grammar_so (the shared contract — a
    bundle's loader.py uses the same path). `grammar_name` is the export
    symbol (`tree_sitter_<name>`) and defaults to the .so's file stem.
    Returns `(language, lib)` — keep `lib` alive for the language's lifetime.
    """
    from pydantree_sitter.loader import load_grammar_so
    return load_grammar_so(so_path, grammar_name)


def parse(lang, source: str, encoding: str = "utf-8"):
    """Parse text with the loaded language (a small convenience wrapper)."""
    parser = tree_sitter.Parser(lang)
    return parser.parse(source.encode(encoding))
