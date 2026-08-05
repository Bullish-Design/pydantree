"""The devenv grammar authored with the tsgrammar RULE-CLASS surface — the
byte-identity gate's class side (the fixture).

This module is the class-authoring spelling of
`examples/devenv-subset/grammar.py` (the builder-DSL spelling): every rule
is a class, the class body IS the production, and `build()` returns the SAME
`tg.Grammar` the DSL returns. The gate test (`tests/test_rules.py`) asserts
the two spellings emit grammar.json deep-equal — the surface is faithful
sugar, not a new grammar language.

The surface (see src/tsgrammar/rules.py):

  * the base class IS the rule's kind — the subclass list is the flag list
        class Number(Pattern)          # bare regex rule      (__pattern__)
        class NamePath(Token)          # token-wrapped        (__pattern__)
        class StringFragment(External) # external-scanner token
        class Comment(Extra, Token)    # behavioral kinds are MIXINS
        class Value(Supertype)
  * annotated attributes are ORDERED CHILDREN; the attribute name is the CST
    field (except Literal[...] attributes = anonymous tokens, and the
    reserved label `content` = an UNNAMED child)
        key: NamePath           -> field("key", ref("name_path"))
        element: list[Value]    -> repeat(field("element", ref("value")))
        value: String | Number  -> field("value", choice(ref, ref))
        maybe: Number | None    -> field("maybe", opt(ref))
        eq: Literal["="] = "="  -> the anonymous token "=" (the default MUST
                                   equal the Literal value — checked at
                                   assemble() time, before any build)
  * `__body__` is the escape hatch for shapes annotations can't express
    (unnamed sequences, bare alternations): the combinator DSL as-is, with
    `R(SomeClass)` as a class-typed reference — or `tg.ref("name")` at the
    mutual-recursion cycle points (`value` <-> `with_expr`), where the
    referenced class is not in scope yet.
  * pattern helpers (`tsgrammar.patterns`) return composable regex STRINGS:
    `ident()`, `integer()`, `quoted()`, `slug()`, `path_literal()`,
    `dotted_path()`, `rest_of_line()`.
  * `__rule_name__` overrides the class-name -> rule-name spelling (`list`).
"""

from __future__ import annotations

from typing import Literal

import tsgrammar as tg
from tsgrammar import (
    External, Extra, Pattern, R, Rule, Supertype, Token, assemble,
)
from tsgrammar.patterns import dotted_path, integer, path_literal, rest_of_line

# ---- lexical --------------------------------------------------------------

class Comment(Extra, Token):
    """`# ...` to end of line — an extra (never a tree node)."""
    __body__ = tg.seq("#", tg.pattern(rest_of_line()))


class NamePath(Token):
    """ONE token: `pkgs`  `config.env.DEVENV_ROOT`  `scripts.hello.exec`
    `"quoted"`  `tasks."quoted".exec` — the text-yielding key leaf Product A
    needs (`key: str = capture("key")`)."""
    __pattern__ = dotted_path()


class Number(Pattern):
    __pattern__ = integer()


class PathLiteral(Token):
    __pattern__ = path_literal()


class StringFragment(External):
    """External-scanner token (scanner.c): a `"..."` string body chunk."""


class IndentedStringFragment(External):
    """External-scanner token: a `''...''` multiline string body chunk."""


# ---- strings --------------------------------------------------------------

class Interpolation(Rule):
    """`${ value }` — the fielded child is what Product A captures."""
    open: Literal["${"] = "${"
    expression: Value
    close: Literal["}"] = "}"


class String(Rule):
    open: Literal['"'] = '"'
    content: list[StringFragment | Interpolation]
    close: Literal['"'] = '"'


class IndentedString(Rule):
    open: Literal["''"] = "''"
    content: list[IndentedStringFragment | Interpolation]
    close: Literal["''"] = "''"


# ---- structure ------------------------------------------------------------

class Pair(Rule):
    """The direct-child-kind pair with key/value FIELDS — the exact shape
    record mode's pair-kind detection needs."""
    key: NamePath
    eq: Literal["="] = "="
    value: Value
    semi: Literal[";"] = ";"


class Attrset(Rule):
    open: Literal["{"] = "{"
    content: list[Pair]
    close: Literal["}"] = "}"


class ListRule(Rule):
    """`[ ... ]` — `list` is a builtin, hence `__rule_name__`."""
    __rule_name__ = "list"
    open: Literal["["] = "["
    element: list[Value]
    close: Literal["]"] = "]"


class WithExpr(Rule):
    """`with pkgs; value` — two UNNAMED refs (annotations are fielded by
    construction; Python can't repeat `_`), so `__body__`. `tg.ref("value")`
    is a cycle point: `Value` is defined below — grammars are cyclic DAGs."""
    __body__ = tg.seq("with", R(NamePath), ";", tg.ref("value"))


class Value(Supertype):
    """The supertype over every value shape — a bare alternation (a CHOICE
    has no field names to annotate). `tg.ref("with_expr")` is the cycle
    point back to `WithExpr`."""
    __body__ = tg.choice(R(String), R(IndentedString), R(ListRule),
                         R(Attrset), R(NamePath), R(Number), R(PathLiteral),
                         tg.ref("with_expr"))


class Formal(Rule):
    """`{ pkgs, lib, config, inputs, ... }:` header — each formal OPTIONALLY
    eats its trailing comma (the real nix grammar's trick: the comma attaches
    to the preceding formal, so `{ a, b }` and `{ a, b, ... }` are
    unambiguous)."""
    __body__ = tg.seq(R(NamePath), tg.opt(","))


class Formals(Rule):
    __body__ = tg.seq("{", tg.repeat(R(Formal)), tg.opt("..."), "}")


class SourceFile(Rule):
    __body__ = tg.seq(tg.opt(tg.seq(R(Formals), ":")), R(Attrset))


def build() -> tg.Grammar:
    """Drop-in for the builder-DSL `build()` — the SAME `tg.Grammar` object,
    so `run_checks`, `build_builder`, and the bundle pipeline are untouched.
    `assemble()` compiles the rule classes into the builder's registry."""
    return assemble("devenv", start=SourceFile)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "src")
    g = build()
    print("rule count:", len(g.rules))
    for w in tg.run_checks(g):
        print(w)
