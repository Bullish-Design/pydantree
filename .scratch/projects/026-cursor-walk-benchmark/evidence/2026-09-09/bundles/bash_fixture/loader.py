"""Load this bundle's grammar into a tree_sitter.Language (B-free)."""
from pathlib import Path
from pydantree_sitter.loader import load_bundle


def language():
    return load_bundle(Path(__file__).resolve().parent).language
