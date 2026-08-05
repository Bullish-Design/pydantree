"""The two primary tasks, model-only. The model is the whole declaration."""

from __future__ import annotations

from typing import Annotated

from typed import M, Matches, NodeKind, OutputModel, capture, source_meta

# ==========================================================================
# Task 1 — Python: module-level integer constant assignments (field mode)
# ==========================================================================

PY_SAMPLE = """\
WIDTH = 1920
HEIGHT = 1080
SCALE = 2
TITLE = "My Window"
DEBUG_MODE = 1

local_count = 42

def main():
    x = 10
    TIMEOUT = 30
    return x + WIDTH

MAX_RETRIES = 5
"""

#   TITLE      -> string value, excluded by NodeKind("integer") at query level
#   local_count -> lowercase, excluded by Matches at query level
#   x, TIMEOUT  -> nested in main(), excluded by the anchored path
PY_GROUND_TRUTH = [
    {"name": "WIDTH", "value": 1920, "line": 1},
    {"name": "HEIGHT", "value": 1080, "line": 2},
    {"name": "SCALE", "value": 2, "line": 3},
    {"name": "DEBUG_MODE", "value": 1, "line": 5},
    {"name": "MAX_RETRIES", "value": 5, "line": 14},
]


class Assignment(OutputModel):
    """Module-level integer constant assignments."""

    __match__ = M("module", "expression_statement", "assignment")

    name: Annotated[str, Matches(r"^[A-Z][A-Z_]*$")] = capture("left")
    value: Annotated[int, NodeKind("integer")] = capture("right")
    line: int = source_meta()


# ==========================================================================
# Task 2 — JSON: person records (record mode)
# ==========================================================================

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
