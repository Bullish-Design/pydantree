#!/usr/bin/env python3
"""Novel Product A probe over the real vendored Rust community grammar."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

from pydantree_sitter import (
    Language,
    M,
    Matches,
    NodeKind,
    OutputModel,
    RawQuery,
    capture,
    source_meta,
)
from pydantree_sitter_grammar.schema_tool import build_community_bundle


REPO = Path(__file__).resolve().parents[3]
RUST = REPO / "tests" / "fixtures" / "rust"

SOURCE = """\
pub fn parse_config(text: &str) -> bool {
    assert_valid(text);
    true
}

fn helper() {
    process();
}

mod nested {
    pub fn validate_schema(schema: &str) {
        assert_schema(schema);
    }
}
"""


class PublicFunction(OutputModel):
    """Raw-query escape hatch: a sibling visibility token plus a predicate."""

    __raw_query__ = RawQuery(
        "((function_item "
        "(visibility_modifier) @visibility "
        "name: (identifier) @name) "
        '(#eq? @visibility "pub"))'
    )
    visibility: str = capture()
    name: str = capture()
    line: int = source_meta()


class AssertCall(OutputModel):
    """Descendant path plus kind and regex predicates over real Rust calls."""

    __match__ = M("source_file", ..., "call_expression")
    function: Annotated[
        str, NodeKind("identifier"), Matches(r"^assert_")
    ] = capture("function")
    line: int = source_meta()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: probe_realworld_a.py OUTPUT_DIR")
    out = Path(sys.argv[1]).resolve()
    bundle = build_community_bundle(RUST, out / "bundle", name="rust")
    lang = Language.load_bundle(bundle)

    # Both bind-time checks happen before the parse.
    public = lang.extractor(PublicFunction)
    calls = lang.extractor(AssertCall)
    tree = lang.parse(SOURCE)
    got = {
        "public_functions": [r.model_dump() for r in public.extract_tree(tree)],
        "assert_calls": [r.model_dump() for r in calls.extract_tree(tree)],
    }
    expected = {
        "public_functions": [
            {"visibility": "pub", "name": "parse_config", "line": 1},
            {"visibility": "pub", "name": "validate_schema", "line": 11},
        ],
        "assert_calls": [
            {"function": "assert_valid", "line": 2},
            {"function": "assert_schema", "line": 12},
        ],
    }
    print(json.dumps(got, indent=2))
    assert got == expected, {"got": got, "expected": expected}
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
