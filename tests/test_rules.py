"""The rule-class surface (`pydantree_sitter_grammar.rules`) — tests.

The load-bearing test is THE GATE: the class-authored devenv grammar
(`tests/fixtures/devenv_builder_dsl_grammar.py`) must emit grammar.json
DEEP-EQUAL to the builder-DSL spelling (`examples/devenv-subset/grammar.py`).
The surface is faithful sugar over the existing builder — any mapping row
(field placement, token wrapping, flag reading, helper output) that drifts
from the DSL's IR fails here first.

The mapping matrix + surface rules follow (REFACTOR step 6): annotation
rows, kinds, `__body__`/R, assemble semantics, and the pipeline.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Literal

import pytest

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar.ir import (
    BlankNode,
    ChoiceNode,
    FieldNode,
    PatternNode,
    RepeatNode,
    SeqNode,
    StrNode,
    SymbolNode,
    TokenNode,
)

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
FIXTURES = TESTS / "fixtures"


HEADER = "from __future__ import annotations\n" \
    "import pydantree_sitter_grammar as tg\n" \
    "from typing import Literal\n" \
    "from pydantree_sitter_grammar import (Rule, Pattern, Token, External, Extra, " \
    "Supertype, Hidden, Inline, Word, R, assemble, module_rules)\n"


def _exec_grammar(source: str, name: str) -> types.ModuleType:
    """Compile + exec a class-surface grammar in a FRESH module namespace.
    Rule classes are module-level declarations (the surface's contract) and
    `assemble()` walks the start class's module — each mini-grammar needs its
    own namespace so one test's classes don't leak into another's. The
    module is registered so `module_rules(sys.modules[__name__])` works, and
    removed afterwards (7.3: no sys.modules leaks)."""
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    exec(compile(HEADER + source, f"<{name}>", "exec"), mod.__dict__)  # noqa: S102
    return mod


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# the gate: class-authored == builder-DSL grammar.json
# ---------------------------------------------------------------------------

def _ir_dict(build):
    """Grammar.build() -> the IR as a plain dict (the probe convention:
    model_dump_json(exclude_none=True), parsed — formatting-free deep equal)."""
    return json.loads(build().build().model_dump_json(exclude_none=True))


def _load_devenv_example(name: str):
    """The class-authored devenv grammar (the migrated example)."""
    return _load_module(name, REPO / "examples" / "devenv-subset" /
                        "grammar.py")


def _load_devenv_dsl(name: str):
    """The preserved builder-DSL spelling (the gate's reference side)."""
    return _load_module(name, FIXTURES / "devenv_builder_dsl_grammar.py")


def test_gate_devenv_class_grammar_identical_to_builder_dsl():
    """THE GATE — byte-identity. The same grammar authored two ways must emit
    the same grammar.json: rule order, externals, extras, flags, and every
    regex string in the IR. The class side is the migrated example; the DSL
    side is the preserved pre-migration spelling."""
    classes = _load_devenv_example("devenv_example_class")
    dsl = _load_devenv_dsl("devenv_example_dsl")

    new = _ir_dict(classes.build)
    old = _ir_dict(dsl.build)
    assert new == old
    assert list(new["rules"]) == list(old["rules"])
    assert len(new["rules"]) == 17

    # the assembled grammar passes the checks the DSL version passes
    assert not tg.errors(classes.build())
    assert not tg.errors(dsl.build())


def test_gate_rule_order_matches_example():
    """Rule registration order (definition order) + start-first reordering
    matches the builder-DSL file exactly (the CLI's root + pruning contract)."""
    classes = _load_devenv_example("devenv_example_class2")
    g = classes.build()
    m = g.build()
    assert list(m.rules)[0] == "source_file"
    assert list(m.rules)[1:] == [
        "comment", "name_path", "number", "path_literal", "string_fragment",
        "indented_string_fragment", "interpolation", "string",
        "indented_string", "pair", "attrset", "list", "with_expr", "value",
        "formal", "formals",
    ]


def test_gate_external_and_extra_placement():
    """Externals (definition order, SCREAMING_SNAKE default) and the comment
    extra land exactly where the DSL file puts them."""
    classes = _load_devenv_example("devenv_example_class3")
    m = classes.build().build()
    assert [e.type for e in m.externals] == ["TOKEN", "TOKEN"]
    assert [e.content.value for e in m.externals] == [
        "STRING_FRAGMENT", "INDENTED_STRING_FRAGMENT"]
    # extras: the builder prepends the whitespace default; then the comment
    assert len(m.extras) == 2
    assert m.extras[0].value == r"\s"
    assert m.extras[1].type == "SYMBOL" and m.extras[1].name == "comment"
    assert m.supertypes == ["value"]
    assert m.word is None
    assert m.inline == []


# ---------------------------------------------------------------------------
# the mapping matrix (REFACTOR step 6)
# ---------------------------------------------------------------------------

def test_annotation_rows_compile_to_the_ir():
    """Every row of the annotation mapping (CONCEPT §2.2), asserted on the
    compiled rule body: field, anonymous Literal token, field-inside-repeat,
    `content` = unnamed repeat, A|B choice, A|None opt."""
    mod = _exec_grammar("""
class Leaf(Rule):
    __body__ = tg.pattern(r"\\w+")

class Other(Rule):
    __body__ = tg.pattern(r"\\d+")

class Top(Rule):
    key: Leaf                       # field("key", ref("leaf"))
    eq: Literal["="] = "="          # anonymous token "="
    element: list[Leaf]             # repeat(field("element", ref("leaf")))
    content: list[Leaf]             # repeat(ref("leaf")) — unnamed
    choice: Leaf | Other            # field("choice", choice(ref, ref))
    maybe: Leaf | None              # field("maybe", opt(ref))

def build():
    return assemble("rows", start=Top)
""", "g_rows")
    g = mod.build()
    body = g.rules["top"]
    assert isinstance(body, SeqNode), body.type
    m = body.members
    assert m[0] == FieldNode(name="key", content=SymbolNode(name="leaf"))
    assert m[1] == StrNode(value="=")
    assert m[2] == RepeatNode(
        content=FieldNode(name="element", content=SymbolNode(name="leaf")))
    assert m[3] == RepeatNode(content=SymbolNode(name="leaf"))
    assert m[4] == FieldNode(
        name="choice",
        content=ChoiceNode(members=[SymbolNode(name="leaf"),
                                    SymbolNode(name="other")]))
    assert m[5] == FieldNode(
        name="maybe",
        content=ChoiceNode(members=[SymbolNode(name="leaf"), BlankNode()]))
    # run_checks clean (all rules reachable from the start)
    assert not tg.errors(g)


def test_literal_default_mismatch_raises_at_assemble():
    """The class-time check: an anonymous token's default must equal its
    Literal value — raised at assemble(), before any build."""
    mod = _exec_grammar("""
class Bad(Rule):
    eq: Literal["="] = ";"     # mismatch: "=" vs ";"

def build():
    return assemble("bad", start=Bad)
""", "g_bad_lit")
    with pytest.raises(ValueError, match=r"Bad.eq: Literal\[.*\].*';'") as ei:
        mod.build()
    assert "does not match" in str(ei.value)


def test_literal_default_omitted_is_allowed():
    """A Literal attribute without a default is fine (the token value comes
    from the Literal itself)."""
    mod = _exec_grammar("""
class Bare(Rule):
    eq: Literal["="]

def build():
    return assemble("bare", start=Bare)
""", "g_bare_lit")
    body = mod.build().rules["bare"]
    assert body == StrNode(value="=")


def test_kinds_pattern_bare_vs_token_wrapped():
    """Pattern = bare regex leaf; Token = wrapped in the TOKEN wrapper."""
    mod = _exec_grammar("""
class Num(Pattern):
    __pattern__ = r"[0-9]+"

class WordTok(Token):
    __pattern__ = r"\\w+"

def build():
    return assemble("kinds", start=WordTok)
""", "g_kinds")
    g = mod.build()
    assert g.rules["num"] == PatternNode(value=r"[0-9]+")
    assert g.rules["word_tok"] == TokenNode(
        content=PatternNode(value=r"\w+"))


def test_kinds_token_body_and_external():
    """A Token rule wraps its __body__; an External rule is the scanner token
    (default SCREAMING_SNAKE name, __external__ override); an External is
    declared in the grammar's externals."""
    mod = _exec_grammar("""
class Frag(External):
    pass

class Custom(External):
    __external__ = "MY_TOKEN"

class SeqTok(Token):
    __body__ = tg.seq("a", "b")

def build():
    return assemble("ext", start=SeqTok)
""", "g_ext")
    g = mod.build()
    m = g.build()
    assert g.rules["frag"] == TokenNode(content=StrNode(value="FRAG"))
    assert g.rules["custom"] == TokenNode(content=StrNode(value="MY_TOKEN"))
    assert g.rules["seq_tok"] == TokenNode(
        content=SeqNode(members=[StrNode(value="a"), StrNode(value="b")]))
    assert [e.content.value for e in m.externals] == ["FRAG", "MY_TOKEN"]


def test_kinds_mixin_composition_and_flags():
    """Extra + Token compose; Supertype/Hidden/Inline/Word land in the
    grammar-level lists (hidden renamed to _name, R() resolves the
    underscore)."""
    mod = _exec_grammar("""
class Comment(Extra, Token):
    __body__ = tg.seq("#", tg.pattern(r"[^\\n]*"))

class Helper(Hidden):
    __body__ = tg.pattern(r"x")

class Inl(Inline):
    __body__ = tg.pattern(r"y")

class WordTok(Word, Token):
    __pattern__ = r"\\w+"

class Value(Supertype):
    __body__ = tg.choice(R(WordTok))

class Source(Rule):
    __body__ = tg.seq(R(Comment), R(Helper), R(Inl), R(Value))

def build():
    return assemble("flags", start=Source)
""", "g_flags")
    g = mod.build()
    m = g.build()
    # Extra: the comment rule is in the extras (after the whitespace default)
    assert m.extras[1] == SymbolNode(name="comment")
    # Token: comment body is token-wrapped
    assert isinstance(g.rules["comment"], TokenNode)
    # Hidden: registered under the underscore name; R(Helper) resolves to it
    assert "_helper" in m.rules and "helper" not in m.rules
    assert m.rules["source"] == SeqNode(members=[
        SymbolNode(name="comment"), SymbolNode(name="_helper"),
        SymbolNode(name="inl"), SymbolNode(name="value")])
    # grammar-level flag lists
    assert m.supertypes == ["value"]
    assert m.inline == ["inl"]
    assert m.word == "word_tok"


def test_R_compiles_to_ref_and_cycle_points_use_string_refs():
    """R(Class) == the same SYMBOL as tg.ref("name"); the mutual-recursion
    cycle points use the DSL's string spelling (concept §4.6) and resolve."""
    mod = _exec_grammar("""
class B(Rule):
    __body__ = tg.seq("b", tg.ref("a"))

class A(Rule):
    __body__ = tg.seq(R(B), tg.ref("b"))    # R = backward ref; tg.ref = cycle point

def build():
    return assemble("cycle", start=A)
""", "g_cycle")
    g = mod.build()
    assert g.rules["a"] == SeqNode(members=[
        SymbolNode(name="b"), SymbolNode(name="b")])
    assert g.rules["b"] == SeqNode(members=[
        StrNode(value="b"), SymbolNode(name="a")])
    # the string refs resolve: checks are clean
    assert not tg.errors(g)


def test_assemble_start_rule_first_and_build_type():
    """assemble() returns the same builder Grammar; the start rule is emitted
    first; the other rules follow in definition order."""
    mod = _exec_grammar("""
class Zeta(Rule):
    __body__ = tg.pattern(r"z")

class Alpha(Rule):
    __body__ = tg.pattern(r"a")

def build():
    return assemble("order", start=Alpha)
""", "g_order")
    g = mod.build()
    assert isinstance(g, tg.Grammar)
    assert list(g.build().rules) == ["alpha", "zeta"]
    assert g.name == "order"


def test_abstract_kind_bases_not_registered():
    """The kind bases are not rules: a grammar assembled from only a pattern
    leaf + start has exactly those two rules."""
    mod = _exec_grammar("""
class Num(Pattern):
    __pattern__ = r"[0-9]+"

class Source(Rule):
    __body__ = R(Num)

def build():
    return assemble("bare", start=Source)
""", "g_bare")
    assert set(mod.build().rules) == {"num", "source"}


def test_no_rule_classes_raises():
    """assemble() with a start class whose module has no rule classes is an
    authoring error with a clear message."""
    mod = types.ModuleType("g_empty")
    sys.modules["g_empty"] = mod
    # a Rule subclass defined elsewhere, with this module as __module__
    class Orphan(tg.Rule):
        __abstract__ = True   # never registered (abstract)
    with pytest.raises(ValueError, match="no rule classes found"):
        tg.assemble("empty", start=Orphan)


# ---------------------------------------------------------------------------
# checks + pipeline on the assembled grammar (the devenv fixture)
# ---------------------------------------------------------------------------

@pytest.mark.toolchain
def test_assembled_grammar_passes_checks_build_and_parse():
    """The assembled devenv grammar passes run_checks clean, builds with the
    scanner, and parses a real fixture — the full B-side pipeline over the
    class surface (probe [4]/[5] as a test)."""
    classes = _load_devenv_example("devenv_example_class4")
    g = classes.build()
    assert not tg.errors(g)
    scanner = REPO / "examples" / "devenv-subset" / "scanner.c"
    result = tg.build_builder(g, scanner=str(scanner))
    lang, _lib = result.language()
    src = (REPO / "examples" / "devenv-subset" / "fixtures"
           / "pydantree.nix").read_text()
    tree = tg.parse(lang, src)
    assert tree.root_node.type == "source_file"
    assert tree.root_node.child_count > 0


# ---------------------------------------------------------------------------
# 014 D8: caller_site is the ONE frame-walking helper — attribution is pinned
# ---------------------------------------------------------------------------

def test_caller_site_attributes_to_the_known_fixture_line():
    """caller_site(skip) attributes to a KNOWN file/lineno: the combinator
    call in THIS test module. A frame added anywhere in the call path fails
    here instead of silently mis-attributing (D8's frame-depth guard)."""
    from pydantree_sitter_grammar.builder import caller_site, site_of, seq

    marker_line = None
    node = None

    def _build():
        site = caller_site(skip=2)     # the attribution under test
        return site, seq("a", "b")     # the combinator stamps its own site

    site, seq_node = _build()
    # skip=2 -> the frame calling _build (this test's line)
    assert site.file.endswith("test_rules.py")
    assert "site, seq_node = _build()" in site.source
    # the seq() combinator's node carries ITS caller's site (the line in
    # _build that called seq) — stamped on the node itself (D8)
    nsite = site_of(seq_node.node)
    assert nsite is not None and nsite.file.endswith("test_rules.py")
    assert "return site, seq" in nsite.source
