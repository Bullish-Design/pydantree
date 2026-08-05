"""__raw_query__ — the escape hatch (014 D11): a literal .scm whose captures
map to fields by name. The query DSL is not public; sibling order, negation,
and multi-anchor joins are out of scope and expressed here.
"""

from __future__ import annotations

import pytest

import tree_sitter_python

from pydantree_sitter import (
    Language,
    M,
    OutputModel,
    QueryBuildError,
    RawQuery,
    SchemaCheckError,
    capture,
    source_meta,
)


class PythonAssignments(OutputModel):
    """The same task as the model surface, as a raw query: every top-level
    `name = value` — including ones a child-chain M() cannot express (e.g. a
    pattern with sibling structure)."""

    __raw_query__ = RawQuery(
        "(module (expression_statement (assignment "
        "left: (identifier) @name right: (_) @value)))")

    name: str = capture()
    value: str = capture()


def test_raw_query_extracts_and_binds():
    lang = Language.from_module(tree_sitter_python)
    rows = [r.model_dump() for r in lang.extractor(PythonAssignments).extract(
        "x = 1\ny = f(2)\n")]
    assert [(r["name"], r["value"]) for r in rows] == [("x", "1"), ("y", "f(2)")]


def test_raw_query_unknown_capture_is_a_bind_error():
    class Bad(OutputModel):
        __raw_query__ = RawQuery(
            "(module (expression_statement (assignment "
            "left: (identifier) @nope right: (_))))")
        name: str = capture()

    lang = Language.from_module(tree_sitter_python)
    with pytest.raises(SchemaCheckError) as exc:
        lang.extractor(Bad)
    assert "nope" in str(exc.value)
    assert "name" in str(exc.value)  # the model's fields are listed


def test_raw_query_rejected_scm_is_a_query_build_error():
    class Bad(OutputModel):
        __raw_query__ = RawQuery("(no_such_kind (identifier) @name)")
        name: str = capture()

    lang = Language.from_module(tree_sitter_python)
    with pytest.raises(QueryBuildError):
        lang.extractor(Bad)


def test_raw_query_with_source_meta_and_predicates():
    class WithMeta(OutputModel):
        __raw_query__ = RawQuery(
            "(module (expression_statement (assignment "
            "left: (identifier) @name right: (_))))")
        name: str = capture()
        line: int = source_meta()

    lang = Language.from_module(tree_sitter_python)
    rows = [r.model_dump() for r in lang.extractor(WithMeta).extract("x = 1\n")]
    assert rows == [{"name": "x", "line": 1}]


def test_raw_query_multi_pattern_does_not_index_error():
    """A1/REVIEW 020: a raw query with 2+ top-level patterns (the `a | b`
    sibling/negation cases the hatch exists for) used to crash
    Cursor.matches with IndexError — the quantifier maps were built as a
    length-1 list for raw queries while tree-sitter reports the REAL
    pattern index."""

    class Multi(OutputModel):
        __raw_query__ = RawQuery(
            "(module (expression_statement (assignment "
            "left: (identifier) @name right: (_) @value)))\n"
            "(module (expression_statement (augmented_assignment "
            "left: (identifier) @name right: (_) @value)))")
        name: str = capture()
        value: str = capture()

    lang = Language.from_module(tree_sitter_python)
    rows = [r.model_dump() for r in lang.extractor(Multi).extract(
        "x = 1\ny += 2\n")]
    assert [(r["name"], r["value"]) for r in rows] == [("x", "1"), ("y", "2")]


def test_match_and_raw_query_are_mutually_exclusive():
    with pytest.raises(Exception):

        class Both(OutputModel):
            __match__ = M("module", "expression_statement")
            __raw_query__ = RawQuery("(module)")
            name: str = capture()
