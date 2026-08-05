"""pydantree_sitter port tests: the spike-a2 model-only surface, ported into
src/pydantree_sitter/ and verified against the real community wheels (tree-sitter-python
+ tree-sitter-json) and hand-computed ground truth — port-first discipline
(surface frozen as spike-a2 validated it, before any schema code)."""

from __future__ import annotations

from typing import Annotated

import pytest
import tree_sitter_json
import tree_sitter_python

from pydantree_sitter import (
    M,
    AnyOf,
    Eq,
    Language,
    Matches,
    NodeKind,
    OutputModel,
    ShapeError,
    capture,
    derived,
    source_meta,
)

# ---------------------------------------------------------------------------
# Task 1 — Python: module-level integer constant assignments (field mode)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task 2 — JSON: person records (record mode)
# ---------------------------------------------------------------------------

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


def norm(models):
    return [m.model_dump() for m in models]


def test_task1_python_field_mode():
    got = norm(Assignment.extract(PY_SAMPLE, language=tree_sitter_python))
    assert got == PY_GROUND_TRUTH


def test_task2_json_record_mode():
    got = norm(Person.extract(JSON_SAMPLE, language=tree_sitter_json))
    assert got == JSON_GROUND_TRUTH


def test_validate_with_accepts_both_queries():
    Assignment.validate_with(tree_sitter_python)
    Person.validate_with(tree_sitter_json)


# ---------------------------------------------------------------------------
# the expressibility battery (spike-a2 main.py §3, ported)
# ---------------------------------------------------------------------------

class Addr(OutputModel):
    __match__ = M("document", "object", record=True)
    city: str


class PersonNested(OutputModel):
    __match__ = M("document", "array", "object", record=True)
    name: str
    address: Addr | None = None


def test_no_arg_capture():
    class Func(OutputModel):
        __match__ = M("module", "function_definition")
        name: str = capture()  # no-arg: attr name IS the CST field
        line: int = source_meta()

    funcs = Func.extract("def main():\n    pass\ndef helper():\n    pass\n",
                         language=tree_sitter_python)
    assert [(f.name, f.line) for f in funcs] == [("main", 1), ("helper", 3)]


def test_eq_predicate_filters():
    class EqName(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: Annotated[str, Eq("alice")] = capture()
        age: int

    rows = norm(EqName.extract(JSON_SAMPLE, language=tree_sitter_json))
    assert rows == [{"name": "alice", "age": 30}]


def test_anyof_predicate():
    class AnyName(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: Annotated[str, AnyOf("alice", "dave")] = capture()
        age: int

    rows = norm(AnyName.extract(JSON_SAMPLE, language=tree_sitter_json))
    assert [r["name"] for r in rows] == ["alice", "dave"]


def test_nodekind_alternation():
    class Flags(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        active: Annotated[bool, NodeKind(("true", "false"))]

    src = '[{"name": "a", "active": true}, {"name": "b", "active": false}]'
    rows = norm(Flags.extract(src, language=tree_sitter_json))
    assert [(r["name"], r["active"]) for r in rows] == [("a", True), ("b", False)]


def test_lenient_mode():
    class Lenient(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str = capture()
        age: int = capture()  # carol has age 25 (fine); no row fails here
        port: int | None = None  # derived field

    rows = norm(Lenient.extract(JSON_SAMPLE, language=tree_sitter_json,
                                strict=False))
    assert len(rows) == 4


def test_derived_field_constant():
    class WithConst(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: Annotated[str, Matches(r"^[A-Z][A-Z_]*$")] = capture("left")
        value: Annotated[int, NodeKind("integer")] = capture("right")
        source: str = derived("spike")   # a computed/constant field (4.1)

    rows = norm(WithConst.extract(PY_SAMPLE, language=tree_sitter_python))
    assert rows[0]["source"] == "spike"


def test_unmappable_shape_raises_at_bind():
    """A record shape the ValueMap cannot express (list[dict]) raises
    ShapeError at BIND (shapes resolve against the ValueMap, D6) - never a
    silent wrong row."""
    lang = Language.load(tree_sitter_json.language())

    class BadList(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        flags: list[dict]  # no JSON shape maps dict elements

    with pytest.raises(ShapeError):
        lang.extractor(BadList)


def test_nested_record_models():
    rows = norm(PersonNested.extract(JSON_SAMPLE, language=tree_sitter_json))
    # carol's address is materialized; others are None
    carol = [r for r in rows if r["name"] == "carol"][0]
    assert carol["address"] == {"city": "Paris"}
    assert all(r["address"] is None for r in rows if r["name"] != "carol")


def test_compiled_source_never_user_facing_but_available():
    src = Person.compiled_source()
    assert "(document" in src and "(pair" in src
    src2 = Assignment.compiled_source()
    assert "(module" in src2 and "@__anchor__" in src2
