"""Phase-5 A-polish tests: incremental reparse + typed Diagnostics, richer
ExtractionError (per-match detail), descendant `...` matching, field-mode
lists (anchor-merge), and Unescaped() string decoding — each schema-checked
where possible.
"""

from __future__ import annotations

from typing import Annotated, get_type_hints

import pytest

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
    Span,
    TreeLanguageError,
    Unescaped,
    ValueMap,
    capture,
    source_meta,
)

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


def test_output_model_declares_compiled_spec_class_attribute():
    assert "_match_spec" in get_type_hints(OutputModel, include_extras=True)


def _json_lang():
    jmodel = build_json().build()
    res = tg.build(jmodel)
    schema = NodeSchema.from_node_types_json(res.node_schema_json, name="json")
    return Language.load(tree_sitter_json.language(), schema=schema), schema


# ---------------------------------------------------------------------------
# reparse + typed Diagnostics
# ---------------------------------------------------------------------------

def test_parse_errors_are_visible_in_the_tree():
    """The typed Diagnostics surface (the old Query.validate) is deleted with
    the public DSL (D11): parse errors surface on the raw tree — ERROR/MISSING
    nodes — and extraction over them is the caller's choice."""
    lang = Language.load(tree_sitter_python.language())
    tree = lang.parse("def (\n")      # a syntax error
    errs = []

    def walk(n):
        if n.type == "ERROR" or n.is_missing:
            errs.append((n.type, Span.from_node(n).line))
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


def test_extract_tree_rejects_a_tree_from_another_language():
    class Assignment(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        value: str = capture("right")

    lang = Language.load(tree_sitter_python.language())
    foreign = Language.load(tree_sitter_json.language())
    with pytest.raises(TreeLanguageError, match="belongs to language"):
        lang.extractor(Assignment).extract_tree(foreign.parse("{}"))


def test_strict_extraction_rejects_error_and_missing_anchors():
    from pydantree_sitter.materialize import _malformed
    tree = Language.load(tree_sitter_python.language()).parse("x = (")
    assert tree.root_node.has_error
    assert _malformed(tree.root_node)
    # An explicitly optional missing child is the documented EOF sentinel.
    from types import SimpleNamespace
    missing = SimpleNamespace(type="MISSING", is_missing=True, children=[])
    assert _malformed(missing)
    assert not _malformed(missing, {"MISSING"})


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
    lang, _schema = _cfg_lang()

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
    lang, _schema = _json_lang()

    class AnyObject(OutputModel):
        __match__ = M("document", ..., "object", record=True)
        name: str = capture("name")

    rows = AnyObject.extract('{"name": "outer", "nested": {"name": "inner"}}',
                             language=lang)
    # both the top-level and the nested object are records
    assert {r.name for r in rows} == {"outer", "inner"}


def test_self_recursive_record_binds_and_extracts_finite_nesting():
    lang, _ = _json_lang()

    class Tree(OutputModel):
        __match__ = M("document", "object", record=True)
        name: str | None = None
        child: Tree | None = capture("child")

    Tree.model_rebuild()
    rows = Tree.extract('{"name": "outer", "child": {"name": "inner"}}',
                        language=lang)
    assert rows[0].child.name == "inner"
    assert rows[0].child.child is None


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


def _multi_list_grammar() -> tg.Grammar:
    """A node with several repeated fields on the same anchor."""
    g = tg.Grammar("multi_list")
    g.rule("identifier", tg.pattern(r"[a-z]+"), word=True)
    g.rule("item", tg.seq(
        "(", tg.repeat(tg.field("left", tg.ref("identifier"))), ";",
        tg.repeat(tg.field("middle", tg.ref("identifier"))), ";",
        tg.repeat(tg.field("right", tg.ref("identifier"))), ")"))
    g.rule("source_file", tg.repeat(tg.ref("item")))
    g.start("source_file")
    return g


def test_field_mode_multiple_lists_do_not_form_cartesian_duplicates():
    """Each repeated field is merged independently, not per combination."""
    class Items(OutputModel):
        __match__ = M("source_file", "item")
        left: list[str] = capture("left")
        middle: list[str] = capture("middle")
        right: list[str] = capture("right")

    lang = Language.load(tg.build_builder(_multi_list_grammar()).language())
    rows = [r.model_dump() for r in
            Items.extract("(a b; c d; e f)\n", language=lang)]
    assert rows == [{
        "left": ["a", "b"],
        "middle": ["c", "d"],
        "right": ["e", "f"],
    }]


def _ordered_field_grammar() -> tg.Grammar:
    """A node whose CST fields have a meaningful grammar order."""
    g = tg.Grammar("ordered_field")
    g.rule("identifier", tg.pattern(r"[a-z]+"), word=True)
    g.rule("function_item", tg.seq(
        tg.field("name", tg.ref("identifier")), "->",
        tg.field("return_type", tg.ref("identifier"))))
    g.rule("source_file", tg.repeat(tg.ref("function_item")))
    g.start("source_file")
    return g


def test_field_mode_capture_order_is_independent_of_model_field_order():
    """Reordering model fields must not reorder CST siblings in a query."""
    class Reordered(OutputModel):
        __match__ = M("source_file", "function_item")
        return_type: str = capture("return_type")
        name: str = capture("name")

    lang = Language.load(tg.build_builder(_ordered_field_grammar()).language())
    rows = [r.model_dump() for r in
            Reordered.extract("f -> int\n", language=lang)]
    assert rows == [{"return_type": "int", "name": "f"}]


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
            _FnParams.extract("f(a b)\ng()\nh(x)\n", language=lang)]
    assert rows == [
        {"name": "f", "params": ["a", "b"]},
        {"name": "g", "params": []},
        {"name": "h", "params": ["x"]},
    ]


def _path_alternation_grammar() -> tg.Grammar:
    """A small grammar with two legal anchor alternatives and one leaf."""
    g = tg.Grammar("path_alternation")
    g.rule("word", tg.pattern(r"[a-z]+"), word=True)
    g.rule("object", tg.seq("o", tg.field("value", tg.ref("word"))))
    g.rule("array", tg.seq("a", tg.field("value", tg.ref("word"))))
    g.rule("left", tg.seq(
        "l", tg.choice(tg.ref("object"), tg.ref("array"))))
    g.rule("right", tg.seq(
        "r", tg.choice(tg.ref("object"), tg.ref("array"))))
    g.rule("source_file", tg.repeat(
        tg.choice(tg.ref("object"), tg.ref("array"),
                  tg.ref("left"), tg.ref("right"))))
    g.start("source_file")
    return g


def _path_alternation_lang():
    result = tg.build_builder(_path_alternation_grammar())
    schema = NodeSchema.from_node_types_json(
        result.node_schema_json, name="path_alternation")
    return Language.load(result.language(), schema=schema), schema


def test_schema_bound_path_alternation_binds_and_extracts():
    """A PathStep tuple is an alternative set at one path level."""
    lang, _ = _path_alternation_lang()

    class Values(OutputModel):
        __match__ = M("source_file", ("object", "array"))
        value: str = capture("value")

    Values.validate_with(lang)
    rows = [r.model_dump() for r in Values.extract(
        "o one\na two\n", language=lang)]
    assert rows == [{"value": "one"}, {"value": "two"}]


def test_schema_bound_gap_path_alternation_binds_and_extracts():
    """The alternatives remain siblings when a GAP permits descendants."""
    lang, _ = _path_alternation_lang()

    class Values(OutputModel):
        __match__ = M("source_file", ..., ("object", "array"))
        value: str = capture("value")

    Values.validate_with(lang)
    rows = [r.model_dump() for r in Values.extract(
        "o one\na two\n", language=lang)]
    assert rows == [{"value": "one"}, {"value": "two"}]


def test_schema_bound_adjacent_path_alternatives_bind_and_extract():
    """Both adjacent path levels can contain independent alternatives."""
    lang, _ = _path_alternation_lang()

    class Values(OutputModel):
        __match__ = M("source_file", ("left", "right"),
                       ("object", "array"))
        value: str = capture("value")

    Values.validate_with(lang)
    rows = [r.model_dump() for r in Values.extract(
        "l o one\nr a two\n", language=lang)]
    assert rows == [{"value": "one"}, {"value": "two"}]


def test_schema_bound_path_alternation_rejects_impossible_kind():
    """Every path alternative must be legal against some prior alternative."""
    lang, _ = _path_alternation_lang()

    class BadPath(OutputModel):
        # ``word`` is a real kind and is a child of ``object``, but it is not
        # a child of ``source_file``. The old implementation accepts it by
        # incorrectly checking it after the ``object`` alternative.
        __match__ = M("source_file", ("object", "word"))

    with pytest.raises(SchemaCheckError) as exc:
        lang.extractor(BadPath)
    assert exc.value.schema_entry == "source_file -> word"
    message = str(exc.value)
    assert "cannot occur as a child of any previous path alternative" in message
    assert "'word'" in message


def _anchor_kind_grammar() -> tg.Grammar:
    """Two anchors expose one logical field through different node kinds."""
    g = tg.Grammar("anchor_kind")
    g.rule("integer", tg.pattern(r"[0-9]+"))
    # This is a textual CST kind whose source text is numeric so pydantic can
    # coerce both branches to the model's int field after matching.
    g.rule("text", tg.pattern(r"[0-9]+"))
    g.rule("number_item", tg.seq(
        "n", tg.field("value", tg.ref("integer"))))
    g.rule("text_item", tg.seq(
        "t", tg.field("value", tg.ref("text"))))
    g.rule("source_file", tg.repeat(
        tg.choice(tg.ref("number_item"), tg.ref("text_item"))))
    g.start("source_file")
    return g


def test_field_kind_inference_is_per_anchor_alternative():
    """Each concrete anchor gets its own inferred field-kind constraint."""
    result = tg.build_builder(_anchor_kind_grammar())
    schema = NodeSchema.from_node_types_json(
        result.node_schema_json, name="anchor_kind")
    lang = Language.load(
        result.language(), schema=schema,
        value_map=ValueMap(scalars={"integer": "int"}))

    class Values(OutputModel):
        __match__ = M("source_file", ("number_item", "text_item"))
        value: int = capture("value")

    ext = lang.extractor(Values)
    source = ext.query_source
    assert "(number_item value:(integer) @value)" in source
    assert "(text_item value:(_) @value)" in source
    assert "(text_item value:(integer) @value)" not in source

    rows = [r.model_dump() for r in ext.extract(
        "n 1\nt 2\nn 3\nt 4\n")]
    assert rows == [{"value": 1}, {"value": 2},
                    {"value": 3}, {"value": 4}]


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
    lang, _schema = _json_lang()

    class Doc(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: Annotated[str, Unescaped()] = capture("name")

    src = '[{"name": "a\\nb\\t\\"c\\"\\\\d\\u0041"}]'
    rows = Doc.extract(src, language=lang)
    assert rows[0].name == 'a\nb\t"c"\\dA'


def test_unescaped_noop_on_plain_text():
    lang, _schema = _json_lang()

    class Doc(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: Annotated[str, Unescaped()]

    rows = Doc.extract('[{"name": "plain"}]', language=lang)
    assert rows[0].name == "plain"


def test_unescaped_schema_check_requires_string_wrapper():
    lang, _schema = _cfg_lang()

    class Bad(OutputModel):
        __match__ = M("source_file", "directive")
        name: Annotated[str, Unescaped()] = capture("name")

    # directive.name is a directive_name kind — NOT a string wrapper -> the
    # schema check rejects Unescaped there
    with pytest.raises(SchemaCheckError):
        Bad.validate_with(lang)


def test_unescaped_over_cfg_string():
    lang, _schema = _cfg_lang()

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
