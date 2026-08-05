"""Product B — the "devenv config surface" grammar (the both-halves example).

A small grammar for the devenv.nix CONFIG surface — attrsets with dotted
attr paths, quoted path segments, `"..."` strings with `${...}`
interpolation, `''...''` multiline strings with `''${` escapes, lists,
`with pkgs; [...]`, `true`/`false`, comments — the shapes the fleet's real
configs actually use, WITHOUT the full Nix language (no let/in, function
formals are a simple header, no binary operators, no apply).

Authored with the pydantree_sitter_grammar RULE-CLASS surface (Product B) so the
consumer-side shape is exactly what Product A wants:

  * the attrset's key/value pair is a DIRECT CHILD KIND with `key`/`value`
    FIELDS — the pair-kind detection record mode needs (upstream
    tree-sitter-nix's binding_set/binding/attrpath shape fails it — the
    Phase-9 finding);
  * the key is ONE TOKEN (`env.GREET`, `tasks."quoted".exec`) — a
    text-yielding leaf, so `key: str = capture("key")` passes the schema
    checks (upstream nix's structural attrpath is rejected);
  * the multiline-string fragments come from a tiny external scanner
    (scanner.c) — position-stable (upstream's 7.6 KB scanner triggers a
    tree-sitter 0.26 position corruption on large files).

The surface — each rule is a class; the class body IS the production:

  * the BASE CLASS is the rule's KIND — the subclass list is the flag list:

        class Number(Pattern)          # bare regex rule      (__pattern__)
        class NamePath(Token)          # token-wrapped        (__pattern__/body)
        class StringFragment(External) # external-scanner token
        class Comment(Extra, Token)    # behavioral kinds are MIXINS
        class Value(Supertype)

  * annotated attributes are ORDERED CHILDREN; the attribute name is the CST
    field (except `Literal[...]` attributes, which are anonymous tokens, and
    the reserved label `content`, which is an UNNAMED child — the IR's own
    slot name):

        key: NamePath           -> field("key", ref("name_path"))
        element: list[Value]    -> repeat(field("element", ref("value")))
        value: String | Number  -> field("value", choice(ref, ref))
        maybe: Number | None    -> field("maybe", opt(ref))
        eq: Literal["="] = "="  -> the anonymous token "=" (the default MUST
                                   equal the Literal value — checked at class
                                   definition, before any build)

  * `__body__` is the escape hatch for shapes annotations can't express
    (unnamed sequences, bare alternations): the combinator DSL as-is, with
    `R(SomeClass)` as a reference — or `tg.ref("name")` at the mutual-
    recursion cycle points, where the referenced class isn't in scope yet.
  * pattern helpers (`pydantree_sitter_grammar.patterns`) return composable regex STRINGS
    in the tree-sitter lexer subset: `ident()`, `integer()`, `quoted()`,
    `slug()`, `path_literal()`, `dotted_path()`, `rest_of_line()`.
  * `__rule_name__` overrides the class-name -> rule-name spelling (`list`).

`build()` returns the SAME `tg.Grammar` the builder DSL returns — the
pipeline below (run_checks, generate, gcc, bundle) is untouched.
"""

from __future__ import annotations
from typing import Literal

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar import (
    External, Extra, Pattern, R, Rule, Supertype, Token, assemble,
)
from pydantree_sitter_grammar.patterns import dotted_path, integer, path_literal, rest_of_line

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
