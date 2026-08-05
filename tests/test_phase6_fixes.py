"""014 Phase 6.4 pinning tests: the B-side bug-fix sweep (F-B1..F-B13, D9).

Each fix has a test that pins the CORRECT behavior (the pre-fix repros are
in .scratch/projects/014-adversarial-review/probe_b_side.py and now show
correct behavior).
"""

import sys
import types
from typing import Literal

import pytest

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar.rules import Rule, _snake, assemble, module_rules


# ---- F-B1: rule(alias=) deleted; alias() combinator is the one way -------

def test_rule_alias_param_is_deleted():
    g = tg.Grammar("f_b1")
    with pytest.raises(TypeError):
        g.rule("x", tg.pattern(r"[a-z]+"), alias="pretty")


def test_alias_combinator_is_the_way():
    g = tg.Grammar("f_b1b")
    g.rule("x", tg.alias("pretty", True, tg.token(tg.pattern("[a-z]+"))))
    g.rule("source_file", tg.repeat(tg.ref("x")))
    g.start("source_file")
    m = g.build()
    assert "x" in m.rules and "pretty" not in m.rules


# ---- F-B2: multi-value Literal -> choice of anonymous tokens --------------

def test_multi_literal_emits_choice_of_anonymous_tokens():
    class Op(Rule):
        op: Literal["+", "-"]
    class Start(Rule):
        child: Op

    g = assemble("f_b2", start=Start, rules=[Op, Start])
    body = g.rules["op"]
    # B11: the multi-value Literal keeps its FIELD wrap — `op` IS the CST
    # field (was: an anonymous, un-wrapped choice)
    assert body.type == "FIELD" and body.name == "op"
    inner = body.content
    assert inner.type == "CHOICE"
    assert sorted(m.value for m in inner.members) == ["+", "-"]


def test_multi_literal_default_must_be_one_of_the_values():
    class Bad(Rule):
        op: Literal["+", "-"] = "*"

    with pytest.raises(ValueError):
        assemble("f_b2b", start=Bad, rules=[Bad])


# ---- F-B4: acronym-aware _snake -------------------------------------------

def test_snake_is_acronym_aware():
    assert _snake("HTTPServer") == "http_server"
    assert _snake("JSONValue") == "json_value"
    assert _snake("IOPort") == "io_port"
    assert _snake("NamePath") == "name_path"
    assert _snake("_Hidden") == "_hidden"


# ---- F-B5: whitespace extras suppress the injected \s default -------------

def test_noncanonical_whitespace_extra_suppresses_default():
    g = tg.Grammar("f_b5")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("tok")))
    g.start("source_file")
    g.extra(tg.pattern(r"[ \t]+"))     # matches only whitespace
    m = g.build()
    assert [e.value for e in m.extras] == ["[ \\t]+"]


def test_non_whitespace_extra_keeps_the_default():
    g = tg.Grammar("f_b5b")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("tok")))
    g.start("source_file")
    g.extra(tg.pattern(r"//[^\n]*"))   # comments — not whitespace
    m = g.build()
    assert [e.value for e in m.extras] == ["\\s", "//[^\\n]*"]


def test_tab_newline_class_extra_suppresses_default():
    """B24 (REVIEW 018): `[ \\t\\n]+` is a whitespace-only class — it must
    suppress the injected `\\s` default like the canonical `[ \\t]+` (the
    old fixed-literal recognizer missed it -> two whitespace extras)."""
    g = tg.Grammar("f_b5c")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.ref("tok")))
    g.start("source_file")
    g.extra(tg.pattern(r"[ \t\n]+"))
    m = g.build()
    assert [e.value for e in m.extras] == ["[ \\t\\n]+"]


# ---- F-B6: replace_rule honors hidden -------------------------------------

def test_replace_rule_honors_hidden():
    g = tg.Grammar("f_b6")
    g.rule("x", tg.pattern(r"[a-z]+"))
    g.rule("source_file", tg.repeat(tg.ref("x")))
    g.start("source_file")
    g.replace_rule("x", tg.pattern(r"[0-9]+"), hidden=True)
    assert "_x" in g.rules and "x" not in g.rules


# ---- D9: assemble takes an explicit rules list; module_rules filters ------

def test_module_rules_excludes_imported_classes():
    """The silent-join bug dies: a class imported INTO a module is not swept."""
    import importlib.util
    import types as _types

    imported = types.ModuleType("_imported_for_test")
    # a Rule subclass DEFINED in another module
    other = _types.ModuleType("_other_module")
    exec("""
from pydantree_sitter_grammar.rules import Rule
from typing import Literal
class Foreign(Rule):
    x: Literal['f'] = 'f'
""", other.__dict__)
    sys.modules["_other_module"] = other
    imp = other.Foreign
    mod = _types.ModuleType("_host_module")
    mod.Foreign = imp            # imported into the host namespace
    mod.own = None
    exec("""
from pydantree_sitter_grammar.rules import Rule
from typing import Literal
class Own(Rule):
    x: Literal['o'] = 'o'
""", mod.__dict__)
    sys.modules["_host_module"] = mod
    found = module_rules(mod)
    names = {c.__name__ for c in found}
    assert "Own" in names
    assert "Foreign" not in names      # imported — excluded


def test_function_local_rule_classes_work():
    """D9: no module lookup — function-local classes just work."""
    class Inner(Rule):
        x: Literal["i"] = "i"
    class InnerStart(Rule):
        child: Inner

    g = assemble("f_local", start=InnerStart, rules=[Inner, InnerStart])
    assert "inner" in g.rules and "inner_start" in g.rules
