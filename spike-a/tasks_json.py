"""Task 2 (JSON grammar): extract person records from a JSON array.

Each record: `{name, age, tags[], nickname?, active?}`. Record keys are NOT in
a fixed order and some are optional — this is what makes tree-sitter's strict
structural patterns awkward and the record (outer+inner sub-query) approach
necessary.

Stresses: anchored record pattern, sub-query materialization (nested models),
repeated captures -> list (tags), Optional fields (nickname, active), bool and
int coercion, `#eq?` predicates on keys, and a nested object + an extra key
(`score`) that must be ignored.

The three implementations sit side by side for the FINDINGS comparison.
"""

from __future__ import annotations

import tree_sitter

from dsl import Query, cap, node
from materialize import OutputModel, capture, extract_records, source_meta

SAMPLE = """\
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

# Hand-computed ground truth:
#   bob    -> no nickname; active: false explicit
#   carol  -> no tags (empty array), no nickname, no active -> defaults
#   carol  -> extra key `score` and nested `address` must be ignored
#   line   = 1-based line of the record object's `{`
GROUND_TRUTH = [
    {"name": "alice", "age": 30, "tags": ["red", "blue", "green"],
     "nickname": "ali", "active": True, "line": 2},
    {"name": "bob", "age": 41, "tags": ["dev"],
     "nickname": None, "active": False, "line": 9},
    {"name": "carol", "age": 25, "tags": [],
     "nickname": None, "active": False, "line": 15},
    {"name": "dave", "age": 55, "tags": ["x", "y", "z", "w"],
     "nickname": None, "active": True, "line": 22},
]


# --------------------------------------------------------------------------
# (a) RAW py-tree-sitter — hand-written .scm, manual per-key dispatch
# --------------------------------------------------------------------------

RAW_RECORDS_SCM = "(document (array (object) @record))"

RAW_FIELDS_SCM = """\
(pair key: (string (string_content) @key) value: (string (string_content) @name) (#eq? @key "name"))
(pair key: (string (string_content) @key) value: (number) @age (#eq? @key "age"))
(pair key: (string (string_content) @key) value: (array (string (string_content) @tag)) (#eq? @key "tags"))
(pair key: (string (string_content) @key) value: (string (string_content) @nickname) (#eq? @key "nickname"))
(pair key: (string (string_content) @key) value: (true) @active (#eq? @key "active"))
(pair key: (string (string_content) @key) value: (false) @active (#eq? @key "active"))
"""

# NOTE: predicates must be INSIDE the pattern's parens. The naive top-level
# form `(pair ...) (#eq? @key "name")` compiles to a SECOND pattern (a bare
# predicate with no node) that matches EVERY node with empty captures — the
# raw consumer then sees junk matches and KeyErrors. Documented in FINDINGS.


def raw_extract(lang, source: bytes) -> list[dict]:
    tree = tree_sitter.Parser(lang).parse(source)
    rec_q = tree_sitter.Query(lang, RAW_RECORDS_SCM)
    fld_q = tree_sitter.Query(lang, RAW_FIELDS_SCM)
    out = []
    for _pi, caps in tree_sitter.QueryCursor(rec_q).matches(tree.root_node):
        rec = caps["record"][0]
        person = {"name": None, "age": None, "tags": [],
                  "nickname": None, "active": False,
                  "line": rec.start_point.row + 1}
        for _fpi, fc in tree_sitter.QueryCursor(fld_q).matches(rec):
            key = fc["key"][0].text.decode()          # manual dispatch
            if key == "name":
                person["name"] = fc["name"][0].text.decode()
            elif key == "age":
                person["age"] = int(fc["age"][0].text.decode())
            elif key == "tags":                       # repeated match -> append
                person["tags"].append(fc["tag"][0].text.decode())
            elif key == "nickname":
                person["nickname"] = fc["nickname"][0].text.decode()
            elif key == "active":
                person["active"] = fc["active"][0].text.decode() == "true"
        out.append(person)
    return out


# --------------------------------------------------------------------------
# (b) DSL, lazy mode — same queries through the DSL, manual dispatch remains
# --------------------------------------------------------------------------

def _pair(value_spec, key):
    """(pair key: (string (string_content) @key) value: <value_spec>)
       (#eq? @key "<key>")"""
    return (node("pair")
            .child(field="key",
                   node=node("string")
                   .child(node=node("string_content").capture("key")))
            .child(field="value", node=value_spec)
            .where(cap("key").eq(key)))


RECORDS_QUERY = Query(
    node("document")
    .child(node("array")
           .child(node("object").capture("record"))
           .capture("root"))
)

FIELDS_QUERY = Query(
    _pair(node("string").child(node=node("string_content").capture("name")),
          "name"),
    _pair(node("number").capture("age"), "age"),
    _pair(node("array").child(node("string")
                              .child(node=node("string_content")
                                     .capture("tag"))), "tags"),
    _pair(node("string").child(node=node("string_content")
                               .capture("nickname")), "nickname"),
    _pair(node("true").capture("active"), "active"),
    _pair(node("false").capture("active"), "active"),
)


def dsl_lazy_extract(lang, source: bytes) -> list[dict]:
    tree = tree_sitter.Parser(lang).parse(source)
    out = []
    for rm in RECORDS_QUERY.run(tree).matches():
        rec = rm.first("record")
        person = {"name": None, "age": None, "tags": [],
                  "nickname": None, "active": False,
                  "line": rec.line}
        for fm in FIELDS_QUERY.run(tree).matches_on(rec._node):
            key = fm.text("key")
            if key == "name":
                person["name"] = fm.text("name")
            elif key == "age":
                person["age"] = int(fm.text("age"))
            elif key == "tags":
                person["tags"].append(fm.text("tag"))
            elif key == "nickname":
                person["nickname"] = fm.text("nickname")
            elif key == "active":
                person["active"] = fm.text("active") == "true"
        out.append(person)
    return out


# --------------------------------------------------------------------------
# (c) DSL, typed mode — record query + field query -> Person models
# --------------------------------------------------------------------------

class Person(OutputModel):
    name: str
    age: int
    tags: list[str] = capture("tag")        # capture renamed -> list field
    nickname: str | None = None
    active: bool = False
    line: int = source_meta(capture="record")


def dsl_typed_extract(lang, source: bytes) -> list[Person]:
    tree = tree_sitter.Parser(lang).parse(source)
    return extract_records(tree, RECORDS_QUERY, FIELDS_QUERY, into=Person)
