"""pydantree_sitter schema-jobs tests: Jobs 1/3/4 (model↔grammar, value-shape
derivation, capture↔type) and record-level anchoring — each planted Phase-4
failure surfaces at validate_with/class creation, BEFORE any text is parsed."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Annotated

import pytest
import tree_sitter_json

import pydantree_sitter_grammar as tg
from pydantree_sitter.schema import NodeSchema, derive_from_ir
from pydantree_sitter import (
    Language,
    M,
    Eq,
    NodeKind,
    OutputModel,
    SchemaCheckError,
    UnsupportedShapeError,
    capture,
    source_meta,
)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / ".scratch" / "projects" / "006-query-bridge"))

TOOLCHAIN_AVAILABLE = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None

pytestmark = pytest.mark.skipif(
    not TOOLCHAIN_AVAILABLE, reason="tree-sitter CLI / gcc not on PATH")


# ---------------------------------------------------------------------------
# fixtures: the JSON schema (from the hand-written IR) + the config grammar
# ---------------------------------------------------------------------------

def json_schema() -> NodeSchema:
    from json_grammar import build as build_json
    model = build_json().build()
    return NodeSchema.from_list(derive_from_ir(model), name="json")


def cfg_schema() -> tuple[NodeSchema, object, object]:
    from cfg_grammar import build as build_cfg
    from pydantree_sitter_grammar.language import load_language
    g = build_cfg()
    res = tg.build_builder(g)
    schema = NodeSchema.from_list(derive_from_ir(g.build()), name="cfg")
    lang, _lib = load_language(res.so_path, "cfg")
    return schema, lang, g


JSON_SAMPLE = """\
[
  {"name": "alice", "age": 30, "tags": ["red"], "nickname": "ali", "active": true},
  {"name": "bob", "age": 41, "tags": ["dev"], "active": false},
  {"name": "carol", "age": 25, "tags": [], "score": 98.5, "address": {"city": "Paris"}},
  {"name": "dave", "age": 55, "tags": ["x"], "active": true}
]
"""


# ---------------------------------------------------------------------------
# the JSON reproduction check (Job 3's soundness over the wheel)
# ---------------------------------------------------------------------------

def test_derived_map_reproduces_v1_over_json_wheel():
    class Person(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        age: int
        tags: list[str]
        nickname: str | None = None
        active: bool = False
        line: int = source_meta()

    lang = Language.load(tree_sitter_json.language(), schema=json_schema())
    Person.validate_with(lang)
    rows = [r.model_dump() for r in Person.extract(JSON_SAMPLE, language=lang)]
    assert [(r["name"], r["age"], r["tags"], r["active"]) for r in rows] == [
        ("alice", 30, ["red"], True),
        ("bob", 41, ["dev"], False),
        ("carol", 25, [], False),
        ("dave", 55, ["x"], True),
    ]
    # carol's nested address.city must NOT collide with the record-level keys
    carol = [r for r in rows if r["name"] == "carol"][0]
    assert carol["nickname"] is None and carol["tags"] == []


def test_derived_json_inner_query_is_the_v1_pattern_set():
    class Person(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        age: int
        tags: list[str]
        active: bool

    schema = json_schema()
    src = Person.compiled_source(schema=schema)
    inner = src.split("-- inner --")[1]
    # the v1 map, plus record-level anchoring — no extra patterns
    for expected in (
        "value:(string (string_content) @name)",
        "value:(number) @age",
        "value:(array (string (string_content) @tags))",
        "value:(false) @active",
        "value:(true) @active",
    ):
        assert expected in inner
    # anchored: every inner pattern names the record node
    assert "(object (pair" in inner
    assert "@__anchor__" in inner


# ---------------------------------------------------------------------------
# Run 2 — planted failures surface at validate_with (no text parsed)
# ---------------------------------------------------------------------------

def test_r2_failure1_nodekind_non_numeric_feeds_int():
    """Run-2 #1: an int-typed capture constrained to a non-numeric kind —
    the schema decides the spike-a2 §2.2 question."""
    schema, lang, _g = cfg_schema()

    class BadPort(OutputModel):
        __match__ = M("source_file", "directive")
        name: str = capture("name")
        value: Annotated[int, NodeKind("identifier")] = capture("arg")

    with pytest.raises(SchemaCheckError) as ei:
        BadPort.validate_with(lang, schema=schema)
    msg = str(ei.value)
    assert "identifier" in msg and "int" in msg
    assert ei.value.schema_entry == "NodeKind(('identifier',)) vs int"


def test_r2_failure2_field_missing_on_kind():
    """Run-2 #2: a __match__ node that cannot have the CST field a capture
    uses — cited with the kind + its actual fields."""
    schema, lang, _g = cfg_schema()

    class BadField(OutputModel):
        __match__ = M("source_file", "section")
        name: str = capture("value")  # section has no 'value' field

    with pytest.raises(SchemaCheckError) as ei:
        BadField.validate_with(lang, schema=schema)
    msg = str(ei.value)
    assert "'section' has no CST field 'value'" in msg
    assert "key" in msg or "name" in msg  # its actual fields are listed


def test_r2_failure3_no_derivable_shape():
    """Run-2 #3: a record-mode field type with no derivable shape in the
    config grammar — the schema says so (not a hardcoded map's import error)."""
    schema, lang, _g = cfg_schema()

    class BadList(OutputModel):
        __match__ = M("source_file", "section", record=True)
        host: str
        tags: list[str]  # cfg has no array-like kind

    with pytest.raises(SchemaCheckError) as ei:
        BadList.validate_with(lang, schema=schema)
    msg = str(ei.value)
    assert "list" in msg
    assert ei.value.schema_entry == "value-under-entry"


def test_r2_failure4_bad_match_chain():
    """Job 1: the __match__ ancestor chain must be a possible descent."""
    schema, lang, _g = cfg_schema()

    class BadChain(OutputModel):
        __match__ = M("source_file", "entry", record=True)
        name: str  # entry cannot be a record under source_file

    with pytest.raises(SchemaCheckError) as ei:
        BadChain.validate_with(lang, schema=schema)
    assert "cannot occur as a child of" in str(ei.value)
    assert ei.value.schema_entry == "source_file -> entry"


def test_record_level_anchoring_kills_collision():
    """Run-2 #4: nested pairs under nested record nodes no longer collide —
    no AmbiguousCaptureError, correct rows, no text mis-parsed."""
    schema = json_schema()

    class Person(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        age: int

    src = ('[{"name": "outer", "age": 1, "meta": {"name": "inner", "age": 2}}]')
    lang = Language.load(tree_sitter_json.language(), schema=schema)
    rows = Person.extract(src, language=lang)
    assert [(r.name, r.age) for r in rows] == [("outer", 1)]


# ---------------------------------------------------------------------------
# Job 4's derived kind constraints in field mode
# ---------------------------------------------------------------------------

def test_field_mode_int_constraint_derived():
    schema, lang, _g = cfg_schema()

    class Listen(OutputModel):
        __match__ = M("source_file", "directive")
        name: str = capture("name")
        port: int = capture("arg")
        line: int = source_meta()

    Listen.validate_with(lang, schema=schema)
    # the derived query constrains the arg to integer kinds (no NodeKind needed)
    assert "arg:(integer) @port" in Listen.compiled_source(schema=schema)
    from cfg_grammar import CORPUS
    rows = Listen.extract(CORPUS, language=lang, schema=schema)
    # include "base.conf" (string arg) is excluded at query level
    assert [(r.name, r.port) for r in rows] == [("listen", 8080), ("reload", 5)]


# ---------------------------------------------------------------------------
# the schema registry + community-path schema
# ---------------------------------------------------------------------------

def test_language_load_registry_finds_schema():
    schema, lang, _g = cfg_schema()

    class Server(OutputModel):
        __match__ = M("source_file", "section", record=True)
        host: str
        port: int

    bound = Language.load(lang, schema=schema)
    Server.validate_with(bound)  # schema rides on the language object
    # per-instance binding: a later schema-less call with the WRAPPER finds
    # the schema; a later call with the BARE language does NOT (Phase 6: the
    # automatic name-keyed registry is gone — the leak it caused: a bound
    # schema silently applied to every later schema-less consumer).
    from cfg_grammar import CORPUS
    rows = Server.extract(CORPUS, language=bound)
    assert [(r.host, r.port) for r in rows] == [("example.com", 8080),
                                                ("localhost", 9090)]


def test_language_load_registry_is_opt_in():
    """Phase 6: the name-keyed convenience survives as an EXPLICIT opt-in
    (register=True) — a named language's schema is found by later bare-
    language calls only when the caller opted in; a nameless language is
    refused (the Phase-6 leak: rust's bundle registered under None and hit
    every wheel-loaded language)."""
    schema, lang, _g = cfg_schema()
    from pydantree_sitter.typed import _SCHEMA_REGISTRY, _maybe_register
    # a nameless language is refused
    _maybe_register(None, schema)
    assert None not in _SCHEMA_REGISTRY

    class Server(OutputModel):
        __match__ = M("source_file", "section", record=True)
        host: str
        port: int

    bound = Language.load(lang, schema=schema, register=True)
    from cfg_grammar import CORPUS
    rows = Server.extract(CORPUS, language=lang)  # bare lang, opted-in
    assert [(r.host, r.port) for r in rows] == [("example.com", 8080),
                                                ("localhost", 9090)]
    assert _SCHEMA_REGISTRY.get(lang.name) is schema


def test_community_path_node_types_schema():
    """A node-schema built from the CLI's node-types.json (derive_from_node_types)
    is equivalent for the shared subset — the community-grammar path."""
    from cfg_grammar import build as build_cfg
    from pydantree_sitter.schema import NodeSchema, derive_from_node_types
    schema_ir, lang, _g = cfg_schema()
    model = build_cfg().build()
    res = tg.build(model)
    import json as _json
    nt = _json.loads(res.node_types_json.read_text())
    schema_nt = NodeSchema.from_list(derive_from_node_types(nt), name="cfg")

    class Server(OutputModel):
        __match__ = M("source_file", "section", record=True)
        host: str
        port: int

    for s in (schema_ir, schema_nt):
        Server.validate_with(lang, schema=s)
    # both produce the same record shapes
    assert Server.compiled_source(schema=schema_ir) == \
        Server.compiled_source(schema=schema_nt)
