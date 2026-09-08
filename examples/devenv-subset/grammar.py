"""The authored Product B grammar used by the both-products example."""

from __future__ import annotations

import pydantree_sitter_grammar as tg


def build() -> tg.Grammar:
    grammar = tg.Grammar("devenv")

    grammar.rule("comment", tg.token(tg.seq("#", tg.pattern(r"[^\n]*"))))
    grammar.extra(tg.ref("comment"))
    grammar.rule("name_path", tg.token(tg.pattern(
        r'("[^"]*"|[a-zA-Z_][a-zA-Z0-9_-]*)(\.[a-zA-Z_][a-zA-Z0-9_-]*|"[^"]*")*')))
    grammar.rule("number", tg.pattern(r"[0-9]+"))
    grammar.rule("path_literal", tg.token(tg.pattern(r"\.[/][A-Za-z0-9_./-]+")))

    grammar.external(tg.tok("STRING_FRAGMENT"),
                     tg.tok("INDENTED_STRING_FRAGMENT"))
    grammar.rule("string_fragment", tg.tok("STRING_FRAGMENT"))
    grammar.rule("indented_string_fragment", tg.tok("INDENTED_STRING_FRAGMENT"))

    grammar.rule("interpolation", tg.seq(
        "${", tg.field("expression", tg.ref("value")), "}"))
    grammar.rule("string", tg.seq(
        '"', tg.repeat(tg.choice(tg.ref("string_fragment"),
                                  tg.ref("interpolation"))), '"'))
    grammar.rule("indented_string", tg.seq(
        "''", tg.repeat(tg.choice(tg.ref("indented_string_fragment"),
                                  tg.ref("interpolation"))), "''"))

    grammar.rule("pair", tg.seq(
        tg.field("key", tg.ref("name_path")), "=",
        tg.field("value", tg.ref("value")), ";"))
    grammar.rule("attrset", tg.seq("{", tg.repeat(tg.ref("pair")), "}"))
    grammar.rule("list", tg.seq(
        "[", tg.repeat(tg.field("element", tg.ref("value"))), "]"))
    grammar.rule("with_expr", tg.seq(
        "with", tg.ref("name_path"), ";", tg.ref("value")))
    grammar.rule("value", tg.choice(
        tg.ref("string"), tg.ref("indented_string"), tg.ref("list"),
        tg.ref("attrset"), tg.ref("name_path"), tg.ref("number"),
        tg.ref("path_literal"), tg.ref("with_expr")), supertype=True)
    grammar.rule("formal", tg.seq(tg.ref("name_path"), tg.opt(",")))
    grammar.rule("formals", tg.seq(
        "{", tg.repeat(tg.ref("formal")), tg.opt("..."), "}"))
    grammar.rule("source_file", tg.seq(
        tg.opt(tg.seq(tg.ref("formals"), ":")), tg.ref("attrset")))
    grammar.start("source_file")
    return grammar
