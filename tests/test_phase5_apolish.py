"""Phase-5 A-polish tests: incremental reparse + typed Diagnostics, richer
ExtractionError (per-match detail), descendant `...` matching, field-mode
lists (anchor-merge), and Unescaped() string decoding — each schema-checked
where possible.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Annotated

import pytest

import tree_sitter
import tree_sitter_json
import tree_sitter_python

import tsgrammar as tg
from tsquery import (
    ExtractionError,
    Language,
    M,
    NodeKind,
    OutputModel,
    Query,
    SchemaCheckError,
    Unescaped,
    capture,
    node,
    source_meta,
)

BRIDGE_DIR = Path(__file__).resolve().parents[1] / ".scratch" / "projects" / "006-tsquery-bridge"
sys.path.insert(0, str(BRIDGE_DIR))

TOOLCHAIN_AVAILABLE = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None

from cfg_grammar import CORPUS, build as build_cfg  # noqa: E402
from json_grammar import build as build_json  # noqa: E402
from tscore.schema import NodeSchema, derive_from_ir  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_schema_registry():
    """The Phase-4 schema registry is keyed by language name and global;
    binding a schema in one test must not leak into another (a schema-less
    extract would silently pick it up). Snapshot + clear around each test."""
    from tsquery.typed import _SCHEMA_REGISTRY
    saved = dict(_SCHEMA_REGISTRY)
    _SCHEMA_REGISTRY.clear()
    yield
    _SCHEMA_REGISTRY.clear()
    _SCHEMA_REGISTRY.update(saved)


def _cfg_lang():
    g = build_cfg()
    result = tg.build_builder(g)
    schema = NodeSchema.from_list(derive_from_ir(g.build()), name="cfg")
    lang, _lib = result.language()
    return Language.load(lang, schema=schema), schema


def _json_lang():
    jmodel = build_json().build()
    tg.build(jmodel)
    schema = NodeSchema.from_list(derive_from_ir(jmodel), name="json")
    return Language.load(tree_sitter_json.language(), schema=schema), schema


# ---------------------------------------------------------------------------
# reparse + typed Diagnostics
# ---------------------------------------------------------------------------

def test_reparse_incremental():
    lang = Language.load(tree_sitter_python.language())
    t1 = lang.parse("x = 1\n")
    t2 = lang.reparse(t1, "x = 1\ny = 2\n")
    assert t2.root_node.named_child_count == 2
    # unchanged left subtree is shared (tree-sitter's incremental machinery)
    q = Query(node("module").child(node("expression_statement")
                                   .child(node("assignment").capture("a"))))
    caps = q.compile(t2.language)
    matches = tree_sitter.QueryCursor(caps).matches(t2.root_node)
    assert len(matches) == 2


def test_typed_diagnostics():
    lang = Language.load(tree_sitter_python.language())
    tree = lang.parse("def (\n")      # a syntax error
    q = Query(node("module"))
    clean, diags = q.validate(tree)
    assert not clean
    assert diags
    d = diags[0]
    assert d.kind == "ERROR"
    assert d.expected is None
    assert d.span.line == 1
    assert d.snippet == "def ("
    # a MISSING node carries the expected kind (the cfg grammar's
    # `[server` — the parser knows a ']' is expected)
    cfg_lang, _schema = _cfg_lang()
    t2 = cfg_lang.parse("[server")
    _clean, diags2 = Query(node("source_file")).validate(t2)
    assert not _clean
    kinds = {d.kind for d in diags2}
    assert "MISSING" in kinds
    missing = [d for d in diags2 if d.kind == "MISSING"]
    assert missing[0].expected == "]"
    assert missing[0].span.line == 1


# ---------------------------------------------------------------------------
# richer ExtractionError — per-match detail, not just the first error
# ---------------------------------------------------------------------------

def test_extraction_error_per_match_detail():
    lang = Language.load(tree_sitter_python.language())

    class BadInts(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        value: int = capture("right")

    src = "x = \"abc\"\ny = \"def\"\nz = 5\n"
    with pytest.raises(ExtractionError) as exc:
        BadInts.extract(src, language=lang)
    e = exc.value
    assert len(e.failures) == 2          # BOTH bad matches, not just the first
    for f in e.failures:
        assert f.span is not None and f.span.line >= 1
        assert f.snippet  # the offending source text
        assert "pydantic" in f.detail
        assert f.pydantic_errors is not None
    assert "abc" in e.failures[0].snippet
    assert "def" in e.failures[1].snippet
    # the message names every failure
    assert "2 match(es) failed" in str(e)


# ---------------------------------------------------------------------------
# descendant matching: '...' in M()
# ---------------------------------------------------------------------------

def test_descendant_path_anywhere_under():
    lang = Language.load(tree_sitter_python.language())

    class Calls(OutputModel):
        __match__ = M("module", ..., "call")
        fn: str = capture("function")
        line: int = source_meta()

    src = "x = f(1)\ndef g():\n    return h(2)\n"
    rows = [r.model_dump() for r in Calls.extract(src, language=lang)]
    # both calls are found — the one INSIDE the function too (that is what a
    # descendant gap buys; a child-chain M() cannot express it at all)
    assert {r["fn"] for r in rows} == {"f", "h"}
    assert sorted(r["line"] for r in rows) == [1, 3]


def test_descendant_path_skips_non_matching_anchors():
    lang = Language.load(tree_sitter_python.language())

    class CallsUnderFn(OutputModel):
        __match__ = M("function_definition", ..., "call")
        fn: str = capture("function")

    src = "x = f(1)\ndef g():\n    return h(2)\n"
    rows = CallsUnderFn.extract(src, language=lang)
    assert [r.fn for r in rows] == ["h"]  # only the call under the function


def test_descendant_job1_checks_the_gap():
    lang, schema = _cfg_lang()

    class Entries(OutputModel):
        __match__ = M("source_file", ..., "entry")
        key: str = capture("key")

    Entries.validate_with(lang)          # source_file root -> descendant OK
    assert len(Entries.extract(CORPUS, language=lang)) == 8  # 5 + 3 entries

    class NotAChain(OutputModel):
        __match__ = M("entry", ..., "source_file")  # never a descendant

    with pytest.raises(SchemaCheckError):
        NotAChain.validate_with(lang)


def test_descendant_record_mode():
    lang, schema = _json_lang()

    class AnyObject(OutputModel):
        __match__ = M("document", ..., "object", record=True)
        name: str = capture("name")

    rows = AnyObject.extract('{"name": "outer", "nested": {"name": "inner"}}',
                             language=lang)
    # both the top-level and the nested object are records
    assert {r.name for r in rows} == {"outer", "inner"}


# ---------------------------------------------------------------------------
# field-mode lists: repeated-field captures merged across matches sharing the
# anchor (the record-mode anchor-merge machinery, reused)
# ---------------------------------------------------------------------------

def _fnlist_grammar() -> tg.Grammar:
    """A node whose repeated `param` field sits ON the anchor (the honest
    field-mode-list case: a grammar that fields every occurrence with the
    same name — like qfilter's params rule).

        fn_params -> name: identifier '(' param: identifier (',' param: identifier)* ')'
    """
    g = tg.Grammar("fnlist")
    g.rule("identifier", tg.pattern(r"[a-z]+"), word=True)
    g.rule("fn_params", tg.seq(
        tg.field("name", tg.ref("identifier")), "(",
        tg.field("param", tg.ref("identifier")),
        tg.repeat(tg.seq(",", tg.field("param", tg.ref("identifier")))), ")"))
    g.rule("source_file", tg.repeat(tg.ref("fn_params")))
    g.start("source_file")
    return g


class _FnParams(OutputModel):
    """Scalar `name` + repeated `param` on the same anchor node."""

    __match__ = M("source_file", "fn_params")
    name: str = capture("name")
    params: list[str] = capture("param")


def test_field_mode_list_collects_repeated_field():
    g = _fnlist_grammar()
    result = tg.build_builder(g)
    lang, _lib = result.language()
    lang = Language.load(lang)

    rows = [r.model_dump() for r in
            _FnParams.extract("f(a, b, c)\ng(x)\n", language=lang)]
    assert rows == [
        {"name": "f", "params": ["a", "b", "c"]},
        {"name": "g", "params": ["x"]},
    ]


def test_field_mode_list_with_schema_bound():
    """The schema-bound path constrains the list capture's kind (here the
    wildcard — params hold identifiers) and merges the same way."""
    g = _fnlist_grammar()
    result = tg.build_builder(g)
    schema = NodeSchema.from_list(derive_from_ir(g.build()), name="fnlist")
    lang, _lib = result.language()
    lang = Language.load(lang, schema=schema)

    _FnParams.validate_with(lang)
    rows = [r.model_dump() for r in
            _FnParams.extract("f(a, b)\ng(x, y)\n", language=lang)]
    assert rows == [{"name": "f", "params": ["a", "b"]},
                    {"name": "g", "params": ["x", "y"]}]


# ---------------------------------------------------------------------------
# Unescaped(): JSON-first string escape decoding, schema-checked
# ---------------------------------------------------------------------------

def test_unescaped_decodes_json_string():
    lang, schema = _json_lang()

    class Doc(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: Annotated[str, Unescaped()] = capture("name")

    src = '[{"name": "a\\nb\\t\\"c\\"\\\\d\\u0041"}]'
    rows = Doc.extract(src, language=lang)
    assert rows[0].name == 'a\nb\t"c"\\dA'


def test_unescaped_noop_on_plain_text():
    lang, schema = _json_lang()

    class Doc(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: Annotated[str, Unescaped()]

    rows = Doc.extract('[{"name": "plain"}]', language=lang)
    assert rows[0].name == "plain"


def test_unescaped_schema_check_requires_string_wrapper():
    lang, schema = _cfg_lang()

    class Bad(OutputModel):
        __match__ = M("source_file", "directive")
        name: Annotated[str, Unescaped()] = capture("name")

    # directive.name is a directive_name kind — NOT a string wrapper -> the
    # schema check rejects Unescaped there
    with pytest.raises(SchemaCheckError):
        Bad.validate_with(lang)


def test_unescaped_over_cfg_string():
    lang, schema = _cfg_lang()

    class Server(OutputModel):
        __match__ = M("source_file", "section", record=True)
        title: Annotated[str | None, Unescaped()] = None

    src = '[x]\ntitle = "A\\nB"\n'
    rows = Server.extract(src, language=lang)
    assert rows[0].title == "A\nB"
