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

import pydantree_sitter_grammar as tg
from pydantree_sitter import (
    Eq,
    ExtractionError,
    Language,
    M,
    NodeKind,
    OutputModel,
    SchemaCheckError,
    ShapeError,
    Unescaped,
    capture,
    source_meta,
)

import pytest
pytestmark = pytest.mark.toolchain

from cfg_grammar import CORPUS, build as build_cfg  # noqa: E402
from json_grammar import build as build_json  # noqa: E402
from pydantree_sitter.schema import NodeSchema  # noqa: E402


def _cfg_lang():
    from pydantree_sitter import propose_value_map
    g = build_cfg()
    result = tg.build_builder(g)
    schema = NodeSchema.from_node_types_json(result.node_schema_json, name="cfg")
    lang = result.language()
    return Language.load(lang, schema=schema,
                         value_map=propose_value_map(schema)), schema


def _json_lang():
    jmodel = build_json().build()
    res = tg.build(jmodel)
    schema = NodeSchema.from_node_types_json(res.node_schema_json, name="json")
    return Language.load(tree_sitter_json.language(), schema=schema), schema


# ---------------------------------------------------------------------------
# reparse + typed Diagnostics
# ---------------------------------------------------------------------------

def test_reparse_incremental():
    lang = Language.load(tree_sitter_python.language())
    t1 = lang.parse("x = 1\n")
    t2 = lang.reparse(t1, "x = 1\ny = 2\n")
    assert t2.root_node.named_child_count == 2
    # unchanged left subtree is shared (tree-sitter's incremental machinery):
    # the reparse tree extracts identically
    class Assignment(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str = capture("left")

    rows = [r.model_dump() for r in lang.extractor(Assignment).extract_tree(t2)]
    assert [r["name"] for r in rows] == ["x", "y"]


def test_reparse_mid_buffer_edit_applies_the_edit():
    """A3/REVIEW 020: reparse() used to never call old_tree.edit() — a
    mid-buffer edit re-used the old tree's subtrees at shifted offsets,
    producing silently wrong trees. The old->new diff is now computed and
    applied (only the edited region is reparsed)."""
    lang = Language.load(tree_sitter_python.language())
    t1 = lang.parse("x = 1\ny = 2\nz = 3\n")
    # a LENGTH-CHANGING mid-buffer edit: inserting a byte shifts every later
    # offset — without old_tree.edit() the old tree's subtrees are reused at
    # their stale positions and `z` parses as garbage.
    t2 = lang.reparse(t1, "x = 1\ny = 22\nz = 3\n")

    texts = []

    def collect(n):
        if n.type == "assignment":
            texts.append(n.text.decode())
        for c in n.children:
            collect(c)

    collect(t2.root_node)
    assert texts == ["x = 1", "y = 22", "z = 3"]
    # without the edit, tree-sitter's stale-subtree reuse leaves an ERROR
    # node (verified empirically) — the proper edit protocol parses clean
    assert not t2.root_node.has_error


def test_parse_errors_are_visible_in_the_tree():
    """The typed Diagnostics surface (the old Query.validate) is deleted with
    the public DSL (D11): parse errors surface on the raw tree — ERROR/MISSING
    nodes — and extraction over them is the caller's choice."""
    import tree_sitter as _ts
    lang = Language.load(tree_sitter_python.language())
    tree = lang.parse("def (\n")      # a syntax error
    errs = []

    def walk(n):
        if n.type == "ERROR" or n.is_missing:
            errs.append((n.type, n.start_point.row + 1))
        for c in n.children:
            walk(c)

    walk(tree.root_node)
    assert errs and errs[0][0] == "ERROR"


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
    lang = result.language()
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
    schema = NodeSchema.from_node_types_json(result.node_schema_json, name="fnlist")
    lang = result.language()
    lang = Language.load(lang, schema=schema)

    _FnParams.validate_with(lang)
    rows = [r.model_dump() for r in
            _FnParams.extract("f(a, b)\ng(x, y)\n", language=lang)]
    assert rows == [{"name": "f", "params": ["a", "b"]},
                    {"name": "g", "params": ["x", "y"]}]


def test_field_mode_list_anchor_with_zero_occurrences_matches():
    """A2/REVIEW 020: a non-optional list[T] field whose anchor has ZERO
    occurrences of the repeated child used to vanish — the emitted quantifier
    was "" (exactly one), so the whole row was silently dropped (a function
    with no args disappeared). `?` keeps the row with an empty list while N
    occurrences still collect all N via the anchor merge."""
    g = tg.Grammar("fnlist4")
    g.rule("identifier", tg.pattern(r"[a-z]+"), word=True)
    g.rule("fn_params", tg.seq(
        tg.field("name", tg.ref("identifier")), "(",
        tg.repeat(tg.field("param", tg.ref("identifier"))), ")"))
    g.rule("source_file", tg.repeat(tg.ref("fn_params")))
    g.start("source_file")
    lang = Language.load(tg.build_builder(g).language())

    rows = [r.model_dump() for r in
            _FnParams.extract("f(a, b)\ng()\nh(x)\n", language=lang)]
    assert rows == [
        {"name": "f", "params": ["a", "b"]},
        {"name": "g", "params": []},
        {"name": "h", "params": ["x"]},
    ]


def test_alternation_anchor_checks_every_kind():
    """A4/REVIEW 020: for an alternation anchor, bind checks used only
    anchor_kinds[0] — a field missing on the SECOND alternative escaped the
    actionable SchemaCheckError and only failed later as a raw
    QueryBuildError."""
    lang, _ = _json_lang()

    class BadPair(OutputModel):
        __match__ = M(("object", "array"))
        x: str = capture("pair")    # 'array' has no 'pair' field

    with pytest.raises(SchemaCheckError) as exc:
        lang.extractor(BadPair)
    assert "'array'" in str(exc.value) and "pair" in str(exc.value)


def test_source_meta_into_optional_int():
    """REVIEW 020 minor: `line: int | None = source_meta()` used to take the
    Span branch (the annotation is not exactly `int`) and fail validation."""
    lang = Language.load(tree_sitter_python.language())

    class WithMeta(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str = capture("left")
        line: int | None = source_meta()

    rows = [r.model_dump() for r in
            WithMeta.extract("x = 1\ny = 2\n", language=lang)]
    assert rows == [{"name": "x", "line": 1}, {"name": "y", "line": 2}]


def test_model_without_declaration_raises_friendly_shape_error():
    """REVIEW 020 minor: a subclass with no __match__/__raw_query__ used to
    surface a raw AttributeError at bind."""
    class Bare(OutputModel):
        label: str = "x"

    lang = Language.load(tree_sitter_python.language())
    with pytest.raises(ShapeError, match="not an extraction model"):
        lang.extractor(Bare)


def test_field_mode_str_over_string_wrapper_captures_content():
    """REVIEW 020 minor: a field-mode `str` capture over a string-WRAPPER
    kind kept the wrapper's quotes/escapes (record mode unwraps). The inner
    content is now captured — `\"hi\"` -> `hi`."""
    lang, _ = _json_lang()

    class Pair(OutputModel):
        __match__ = M("document", "object", "pair")
        value: Annotated[str, NodeKind("string")] = capture("value")

    rows = [r.model_dump() for r in Pair.extract('{"a": "hi"}', language=lang)]
    assert rows == [{"value": "hi"}]


def test_record_optional_predicate_field_keeps_the_record():
    """REVIEW 020 minor: a record with an OPTIONAL predicate field that does
    not match used to drop the WHOLE record; it now just stays absent (None)."""
    lang, _ = _json_lang()

    class Rec(OutputModel):
        __match__ = M("document", "object", record=True)
        name: str
        tag: Annotated[str | None, Eq("x")] = None

    rows = [r.model_dump() for r in
            Rec.extract('{"name": "a", "tag": "y"}', language=lang)]
    assert rows == [{"name": "a", "tag": None}]

    # a REQUIRED predicate field that fails still filters the record
    class Strict(OutputModel):
        __match__ = M("document", "object", record=True)
        name: str
        tag: Annotated[str, Eq("x")]

    rows = [r.model_dump() for r in
            Strict.extract('{"name": "a", "tag": "y"}', language=lang)]
    assert rows == []


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


# ---------------------------------------------------------------------------
# A2 (REVIEW 018): the documented sugar one-liner must not recompile and
# re-check every call — memoized per-input Language on the sugar path
# ---------------------------------------------------------------------------

def test_sugar_reuses_compiled_query(monkeypatch):
    from pydantree_sitter import emit

    n = {"c": 0}
    orig = emit.Query.compile

    def counting(self, lang):
        if self._compiled is None:
            n["c"] += 1
        return orig(self, lang)

    monkeypatch.setattr(emit.Query, "compile", counting)

    class Rec(OutputModel):
        __match__ = M("document", "object", record=True)
        a: int | None = None

    text = '{"a": 1}'
    for _ in range(5):
        Rec.extract(text, language=tree_sitter_json)
    assert n["c"] <= 2, f"recompiled {n['c']}x for 5 identical sugar calls"


# ---------------------------------------------------------------------------
# A4 (REVIEW 018): the source-diagnostic must not raise the SchemaCheckError
# you called it to inspect
# ---------------------------------------------------------------------------

def test_compiled_source_is_a_diagnostic_not_a_checker():
    from pydantree_sitter import SchemaCheckError
    from pydantree_sitter.schema import NodeSchema

    class Bad(OutputModel):
        __match__ = M("document", "object")
        x: str = capture("x")

    # both kinds exist, but `object` cannot occur as a child of `document`
    # (empty children) — the real bind rejects the chain
    bad = NodeSchema.from_list([
        {"type": "document", "named": True},
        {"type": "object", "named": True},
    ])

    # the diagnostic returns the emitted source even for a schema the bind
    # would reject
    src = Bad.compiled_source(schema=bad)
    assert isinstance(src, str) and src

    # the real bind still checks (check is opt-in for the diagnostic, always
    # on for the bind)
    lang = Language.load(tree_sitter_json.language(), schema=bad)
    with pytest.raises(SchemaCheckError):
        lang.extractor(Bad)


# ---------------------------------------------------------------------------
# REVIEW 018 §5.1: "one compiler" — every path (field / record / raw) routes
# through compile_spec exactly once per bind
# ---------------------------------------------------------------------------

def test_one_compiler_all_paths_route_through_compile_spec(monkeypatch):
    from pydantree_sitter import binding as B

    n = {"calls": 0}
    orig = B.compile_spec

    def counting(model, language, *, value_map):
        n["calls"] += 1
        return orig(model, language, value_map=value_map)

    monkeypatch.setattr(B, "compile_spec", counting)

    class F(OutputModel):
        __match__ = M("document", "object", "pair")
        key: str = capture("key")

    F.validate_with(tree_sitter_json)
    assert n["calls"] == 1

    class R(OutputModel):
        __match__ = M("document", "object", record=True)
        a: int | None = None

    R.validate_with(tree_sitter_json)
    assert n["calls"] == 2

    class Raw(OutputModel):
        __raw_query__ = "(pair key: (string) @key)"
        key: str = capture("key")

    Raw.validate_with(tree_sitter_json)
    assert n["calls"] == 3


# ---------------------------------------------------------------------------
# A3 (REVIEW 018 §4.1b): the raw-query escape hatch keeps SOME of the
# differentiator — explicit capture('field')/capture_kind('kind') keys are
# capture↔type checked schema-wide (no anchor kind to pin)
# ---------------------------------------------------------------------------

def test_raw_query_explicit_capture_is_schema_checked():
    from pydantree_sitter import RawQuery, SchemaCheckError

    lang, _schema = _cfg_lang()

    class D(OutputModel):
        __raw_query__ = RawQuery("(entry key: (identifier) @key)")
        key: str = capture("key")

    lang.extractor(D)          # 'key' is a real field; str-compatible
    rows = lang.extractor(D).extract("[s]\na = 1\n")
    assert rows and rows[0].key == "a"

    class Bad(OutputModel):
        __raw_query__ = RawQuery("(entry key: (identifier) @key)")
        key: str = capture("nope")

    with pytest.raises(SchemaCheckError) as exc:
        lang.extractor(Bad)
    assert "no kind in the grammar has a CST field 'nope'" in str(exc.value)

    class WrongType(OutputModel):
        __raw_query__ = RawQuery("(entry key: (identifier) @key)")
        key: int = capture("key")

    with pytest.raises(SchemaCheckError) as exc:
        lang.extractor(WrongType)
    assert "int" in str(exc.value)   # identifier can only yield str


# ---------------------------------------------------------------------------
# REVIEW 018 §4.3: record mode over a grammar with SEVERAL key+value pair
# kinds must raise (naming the candidates) instead of silently guessing the
# alphabetically first — M(..., record_pair=) pins it
# ---------------------------------------------------------------------------

def _twopair_grammar() -> tg.Grammar:
    g = tg.Grammar("twopair")
    g.rule("ident", tg.pattern(r"[a-z]+"), word=True)
    g.rule("pair", tg.seq(tg.field("key", tg.ref("ident")), "=",
                          tg.field("value", tg.ref("ident"))))
    g.rule("kv2", tg.seq(tg.field("key", tg.ref("ident")), ":",
                         tg.field("value", tg.ref("ident"))))
    g.rule("document", tg.repeat(
        tg.choice(tg.ref("pair"), tg.ref("kv2"))))
    g.start("document")
    return g


def _twopair_lang():
    from pydantree_sitter import propose_value_map
    g = _twopair_grammar()
    result = tg.build_builder(g)
    schema = NodeSchema.from_node_types_json(result.node_schema_json, name="twopair")
    lang = result.language()
    return Language.load(lang, schema=schema,
                         value_map=propose_value_map(schema)), schema


def test_record_pair_kind_must_be_pinned_when_ambiguous():
    from pydantree_sitter import ShapeError

    lang, _schema = _twopair_lang()

    class Ambiguous(OutputModel):
        __match__ = M("document", record=True)
        k: str | None = None

    with pytest.raises(ShapeError) as exc:
        Ambiguous.validate_with(lang)
    msg = str(exc.value)
    assert "kv2" in msg and "pair" in msg        # names BOTH candidates
    assert "record_pair" in msg                   # and says how to pin it

    class Pinned(OutputModel):
        __match__ = M("document", record=True, record_pair="pair")
        a: str | None = None
        b: str | None = None

    rows = Pinned.extract("a = x\nb: y\n", language=lang)
    # only the `pair` kind is a record; the `kv2` lines are not records
    assert len(rows) == 1 and rows[0].a == "x" and rows[0].b is None

    class BadPair(OutputModel):
        __match__ = M("document", record=True, record_pair="nope")
        k: str | None = None

    with pytest.raises(ShapeError) as exc:
        BadPair.validate_with(lang)
    assert "record_pair='nope'" in str(exc.value)
