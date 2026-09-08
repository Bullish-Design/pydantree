"""Measured D5/D8 readiness contracts."""

from __future__ import annotations

import json

import tree_sitter_json
import tree_sitter_python

from pydantree_sitter import (
    ExtractionError,
    Language,
    M,
    OutputModel,
    TreeLanguageError,
    capture,
)


class Assignment(OutputModel):
    __match__ = M("module", "expression_statement", "assignment")
    value: str = capture("right")


def main() -> None:
    python = Language.load(tree_sitter_python.language())
    foreign = Language.load(tree_sitter_json.language())
    ext = python.extractor(Assignment)
    rows = [r.model_dump() for r in ext.extract("x = 'ok'\n")]
    result = {"same_language": {"rows": rows}}
    try:
        ext.extract_tree(foreign.parse("{}"))
    except TreeLanguageError as exc:
        result["foreign_language"] = {
            "exception": type(exc).__name__, "message": str(exc)}
    try:
        ext.extract("x = (")
    except ExtractionError as exc:
        result["malformed_default_strict"] = {
            "exception": type(exc).__name__, "message": str(exc),
            "span": exc.failures[0].span.text}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
