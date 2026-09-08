"""Review 021 D2/D7 probe: schema-bound path and anchor alternatives."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))

import pydantree_sitter_grammar as tg
from pydantree_sitter import (
    Language,
    M,
    OutputModel,
    SchemaCheckError,
    ValueMap,
    capture,
)
from pydantree_sitter.schema import NodeSchema

TMP = Path(tempfile.mkdtemp(prefix="probe-d2-d7-"))
REPORT: dict = {}


def build_language(grammar: tg.Grammar, name: str, *, value_map=None):
    result = tg.build_builder(grammar, cache_dir=TMP / name)
    schema = NodeSchema.from_node_types_json(result.node_schema_json, name=name)
    return Language.load(result.language(), schema=schema, value_map=value_map)


def path_grammar() -> tg.Grammar:
    g = tg.Grammar("probe_path_alternation")
    g.rule("word", tg.pattern(r"[a-z]+"), word=True)
    g.rule("object", tg.seq("o", tg.field("value", tg.ref("word"))))
    g.rule("array", tg.seq("a", tg.field("value", tg.ref("word"))))
    g.rule("source_file", tg.repeat(
        tg.choice(tg.ref("object"), tg.ref("array"))))
    g.start("source_file")
    return g


path_lang = build_language(path_grammar(), "path")


class PathValues(OutputModel):
    __match__ = M("source_file", ("object", "array"))
    value: str = capture("value")


path_ext = path_lang.extractor(PathValues)
REPORT["legal_path_alternation"] = {
    "bound": True,
    "rows": [r.model_dump() for r in path_ext.extract("o one\na two\n")],
}


class GapValues(OutputModel):
    __match__ = M("source_file", ..., ("object", "array"))
    value: str = capture("value")


gap_ext = path_lang.extractor(GapValues)
REPORT["legal_gap_path_alternation"] = {
    "bound": True,
    "rows": [r.model_dump() for r in gap_ext.extract("o one\na two\n")],
}


class BadPath(OutputModel):
    # word is real and is a child of object, but not a child of source_file.
    __match__ = M("source_file", ("object", "word"))


try:
    path_lang.extractor(BadPath)
except SchemaCheckError as exc:
    REPORT["illegal_path_alternation"] = {
        "exception": type(exc).__name__,
        "schema_entry": getattr(exc, "schema_entry", None),
        "message": str(exc),
    }


def anchor_kind_grammar() -> tg.Grammar:
    g = tg.Grammar("probe_anchor_kind")
    g.rule("integer", tg.pattern(r"[0-9]+"))
    g.rule("text", tg.pattern(r"[0-9]+"))
    g.rule("number_item", tg.seq(
        "n", tg.field("value", tg.ref("integer"))))
    g.rule("text_item", tg.seq(
        "t", tg.field("value", tg.ref("text"))))
    g.rule("source_file", tg.repeat(
        tg.choice(tg.ref("number_item"), tg.ref("text_item"))))
    g.start("source_file")
    return g


anchor_lang = build_language(
    anchor_kind_grammar(), "anchor",
    value_map=ValueMap(scalars={"integer": "int"}),
)


class AnchorValues(OutputModel):
    __match__ = M("source_file", ("number_item", "text_item"))
    value: int = capture("value")


anchor_ext = anchor_lang.extractor(AnchorValues)
REPORT["per_anchor_kind_inference"] = {
    "query": anchor_ext.query_source,
    "rows": [r.model_dump() for r in anchor_ext.extract(
        "n 1\nt 2\nn 3\nt 4\n")],
}

print("D2 legal path rows:", REPORT["legal_path_alternation"]["rows"])
print("D2 legal GAP path rows:", REPORT["legal_gap_path_alternation"]["rows"])
bad = REPORT["illegal_path_alternation"]
print("D2 illegal path:", bad["exception"], bad["schema_entry"])
print("D2 illegal path message:", bad["message"])
print("D7 query:\n" + REPORT["per_anchor_kind_inference"]["query"])
print("D7 rows:", REPORT["per_anchor_kind_inference"]["rows"])
print("JSON_EVIDENCE")
print(json.dumps(REPORT, indent=2, sort_keys=True))
