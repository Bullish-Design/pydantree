"""Wheel-grammar binding tests — run WITHOUT the toolchain.

REVIEW 020 §3/§4 (reviewer gap #4): Product A's core (`binding.py`,
`materialize.py`, `emit.py`) was exercised mainly through toolchain-gated
integration tests, so it was effectively untested in any environment
lacking the CLI+gcc. These tests use only the tree_sitter_python WHEEL (no
CLI, no gcc, no bundle build) and are deliberately NOT toolchain-marked —
they run in a plain shell with the venv.

Covered here: incremental reparse (the A3 edit-application fix), the
materializer's source_meta() into optional int, and the friendly
not-an-extraction-model error.
"""

from __future__ import annotations

import pytest

import tree_sitter_python

from pydantree_sitter import (
    Language,
    M,
    OutputModel,
    ShapeError,
    capture,
    source_meta,
)


def test_reparse_incremental():
    lang = Language.load(tree_sitter_python.language())
    t1 = lang.parse("x = 1\n")
    t2 = lang.reparse(t1, "x = 1\ny = 2\n")
    assert t2.root_node.named_child_count == 2
    # unchanged left subtree is shared (tree-sitter's incremental machinery):
    # the reparse tree extracts identically
    class Assignment(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str = capture("left")

    rows = [r.model_dump() for r in lang.extractor(Assignment).extract_tree(t2)]
    assert [r["name"] for r in rows] == ["x", "y"]


def test_reparse_mid_buffer_edit_applies_the_edit():
    """A3/REVIEW 020: reparse() used to never call old_tree.edit() — a
    mid-buffer edit re-used the old tree's subtrees at shifted offsets,
    producing silently wrong trees. The old->new diff is now computed and
    applied (only the edited region is reparsed)."""
    lang = Language.load(tree_sitter_python.language())
    t1 = lang.parse("x = 1\ny = 2\nz = 3\n")
    # a LENGTH-CHANGING mid-buffer edit: inserting a byte shifts every later
    # offset — without old_tree.edit() the old tree's subtrees are reused at
    # their stale positions and `z` parses as garbage.
    t2 = lang.reparse(t1, "x = 1\ny = 22\nz = 3\n")

    texts = []

    def collect(n):
        if n.type == "assignment":
            texts.append(n.text.decode())
        for c in n.children:
            collect(c)

    collect(t2.root_node)
    assert texts == ["x = 1", "y = 22", "z = 3"]
    # without the edit, tree-sitter's stale-subtree reuse leaves an ERROR
    # node (verified empirically) — the proper edit protocol parses clean
    assert not t2.root_node.has_error


def test_source_meta_into_optional_int():
    """REVIEW 020 minor: `line: int | None = source_meta()` used to take the
    Span branch (the annotation is not exactly `int`) and fail validation."""
    lang = Language.load(tree_sitter_python.language())

    class WithMeta(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str = capture("left")
        line: int | None = source_meta()

    rows = [r.model_dump() for r in
            WithMeta.extract("x = 1\ny = 2\n", language=lang)]
    assert rows == [{"name": "x", "line": 1}, {"name": "y", "line": 2}]


def test_model_without_declaration_raises_friendly_shape_error():
    """REVIEW 020 minor: a subclass with no __match__/__raw_query__ used to
    surface a raw AttributeError at bind."""
    class Bare(OutputModel):
        label: str = "x"

    lang = Language.load(tree_sitter_python.language())
    with pytest.raises(ShapeError, match="not an extraction model"):
        lang.extractor(Bare)
