"""Task 1 (Python grammar): module-level integer constant assignments.

Extract `Assignment(name, value, line)` for every MODULE-LEVEL assignment whose
left side is an ALL-CAPS identifier and whose right side is an integer literal.

Stresses: anchored `(module ...)` pattern, `#match?` predicate, text -> int
coercion, span/line injection, nested-statement exclusion (the function body
has its own assignments that must NOT match).

The three implementations (raw / DSL lazy / DSL typed) sit side by side so the
FINDINGS comparison is honest.
"""

from __future__ import annotations

import tree_sitter

from dsl import Query, cap, node
from materialize import OutputModel, source_meta

SAMPLE = """\
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

# Hand-computed ground truth (module-level, ALL-CAPS, int-valued only):
#   TITLE  -> string value, excluded by `right: (integer)`
#   local_count -> lowercase, excluded by the predicate
#   x, TIMEOUT  -> nested in main(), excluded by the anchored (module ...)
GROUND_TRUTH = [
    {"name": "WIDTH", "value": 1920, "line": 1},
    {"name": "HEIGHT", "value": 1080, "line": 2},
    {"name": "SCALE", "value": 2, "line": 3},
    {"name": "DEBUG_MODE", "value": 1, "line": 5},
    {"name": "MAX_RETRIES", "value": 5, "line": 14},
]


# --------------------------------------------------------------------------
# (a) RAW py-tree-sitter — hand-written .scm, manual slicing + coercion
# --------------------------------------------------------------------------

RAW_SCM = """\
(module
  (expression_statement
    (assignment
      left: (identifier) @name
      right: (integer) @value)
    (#match? @name "^[A-Z][A-Z_]*$")) @stmt) @root
"""


def raw_extract(lang, source: bytes) -> list[dict]:
    tree = tree_sitter.Parser(lang).parse(source)
    query = tree_sitter.Query(lang, RAW_SCM)
    out = []
    for _pi, caps in tree_sitter.QueryCursor(query).matches(tree.root_node):
        name = caps["name"][0].text.decode()
        value = int(caps["value"][0].text.decode())      # manual coercion
        line = caps["stmt"][0].start_point.row + 1       # manual span math
        out.append({"name": name, "value": value, "line": line})
    return out


# --------------------------------------------------------------------------
# (b) DSL, lazy mode — same query via the DSL, cursor-first, no models
# --------------------------------------------------------------------------

ASSIGN_QUERY = Query(
    node("module")
    .child(node("expression_statement")
           .child(node("assignment")
                  .child(field="left",
                         node=node("identifier").capture("name"))
                  .child(field="right",
                         node=node("integer").capture("value")))
           .capture("stmt"))
    .capture("root")
    .where(cap("name").matches(r"^[A-Z][A-Z_]*$"))
)


def dsl_lazy_extract(lang, source: bytes) -> list[dict]:
    tree = tree_sitter.Parser(lang).parse(source)
    out = []
    for m in ASSIGN_QUERY.run(tree).matches():
        out.append({
            "name": m.text("name"),
            "value": int(m.text("value")),               # manual coercion
            "line": m.first("stmt").line,                # helper, still manual
        })
    return out


# --------------------------------------------------------------------------
# (c) DSL, typed mode — `q.extract(tree, into=Model)`
# --------------------------------------------------------------------------

class Assignment(OutputModel):
    name: str
    value: int
    line: int = source_meta(capture="stmt")


def dsl_typed_extract(lang, source: bytes) -> list[Assignment]:
    tree = tree_sitter.Parser(lang).parse(source)
    return ASSIGN_QUERY.extract(tree, into=Assignment)
