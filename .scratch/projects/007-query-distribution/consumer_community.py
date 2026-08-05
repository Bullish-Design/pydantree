"""Run 2 — the community path, B-free.

A community wheel (tree_sitter_json) ships no node-schema; the Phase-5
community-schema tool derived one from its node-types.json byproduct. This
process binds the derived schema to the wheel and extracts the Phase-1/4
Person ground truth — checks active, no pydantree_sitter_grammar in the process.

Usage: python consumer_community.py <node-schema.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import pydantree_sitter_grammar  # noqa: F401
    print(json.dumps({"ok": False,
                      "error": "pydantree_sitter_grammar IS importable — B leaked"}))
    sys.exit(1)
except ModuleNotFoundError:
    pass

import tree_sitter_json  # noqa: E402
from pydantree_sitter.schema import NodeSchema  # noqa: E402
from pydantree_sitter import Language, M, OutputModel, source_meta  # noqa: E402

JSON_SAMPLE = """\
[
  {
    "name": "alice",
    "age": 30,
    "tags": ["red", "blue", "green"],
    "nickname": "ali",
    "active": true
  },
  {
    "name": "bob",
    "age": 41,
    "tags": ["dev"],
    "active": false
  },
  {
    "name": "carol",
    "age": 25,
    "tags": [],
    "score": 98.5,
    "address": {"city": "Paris"}
  },
  {
    "name": "dave",
    "age": 55,
    "tags": ["x", "y", "z", "w"],
    "active": true
  }
]
"""

JSON_GROUND_TRUTH = [
    {"name": "alice", "age": 30, "tags": ["red", "blue", "green"],
     "nickname": "ali", "active": True, "line": 2},
    {"name": "bob", "age": 41, "tags": ["dev"],
     "nickname": None, "active": False, "line": 9},
    {"name": "carol", "age": 25, "tags": [],
     "nickname": None, "active": False, "line": 15},
    {"name": "dave", "age": 55, "tags": ["x", "y", "z", "w"],
     "nickname": None, "active": True, "line": 22},
]


class Person(OutputModel):
    """Person records from a JSON array; keys order-independent/optional."""

    __match__ = M("document", "array", "object", record=True)
    name: str
    age: int
    tags: list[str]
    nickname: str | None = None
    active: bool = False
    line: int = source_meta()


def main() -> int:
    schema = NodeSchema.from_node_types_json(sys.argv[1], name="json")
    lang = Language.load(tree_sitter_json.language(), schema=schema)
    Person.validate_with(lang)
    rows = [r.model_dump() for r in Person.extract(JSON_SAMPLE, language=lang)]
    ok = rows == JSON_GROUND_TRUTH
    print(json.dumps({"ok": ok, "rows": rows}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
