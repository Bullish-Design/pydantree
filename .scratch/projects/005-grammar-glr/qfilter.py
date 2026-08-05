"""
qfilter — a realistic query/filter language authored ENTIRELY through the
Phase-3 ergonomics surface (Run 1 of the bet-#1 feel experiment).

The surface, and nothing else:
  - `g.precedence(...)` — the declarative ladder (no magic integers)
  - `tg.expression(...)` — ExpressionGrammar from a table (infix with
    associativity + levels, prefix, postfix call/member)
  - `g.rule(..., ambiguous=True)` — the intentional-ambiguity opt-in
    (dangling else)
  - `rule(..., word=True)` — keyword extraction one-liner
  - sane-default whitespace extra (no `extra("\\s")` call needed)
  - hidden rule + alias, supertype, fields, opt/repeat — Phase-2 surface
  - zero `conflict(...)` entries and zero `prec*(...)` calls by the author

Baseline for Run 3: the SAME grammar hand-rolled the Phase-2 way (filtlang
pattern) lives in `qfilter_handrolled.py`.
"""

from __future__ import annotations

import pydantree_sitter_grammar as tg


def build() -> tg.Grammar:
    g = tg.Grammar("qfilter")

    # ---- lexical -----------------------------------------------------------
    g.rule("number", tg.pattern(r"\d+(\.\d+)?"))
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"), word=True)
    g.rule("string", tg.token(tg.seq(
        '"',
        tg.repeat(tg.choice(tg.pattern(r"\\."), tg.pattern(r'[^"\\]+'))),
        '"')))
    g.rule("comment", tg.token(tg.choice(
        tg.seq("//", tg.pattern(r"[^\n]*")),
        tg.seq("/*", tg.pattern(r"[^*]*\*+([^/*][^*]*\*+)*"), "/"))))
    g.extra(tg.ref("comment"))            # whitespace is the sane default

    # ---- the ladder (loose -> tight) ----------------------------------------
    prec = g.precedence("or", "and", "not", "compare", "add", "mul",
                        "unary", "pow", "postfix")

    # ---- expressions (from a table) -----------------------------------------
    g.rule("args", tg.seq(tg.ref("expr"),
                          tg.repeat(tg.seq(",", tg.ref("expr")))))
    tg.expression(g, "expr",
        primary=tg.choice(
            tg.ref("number"), tg.ref("string"), tg.ref("identifier"),
            tg.seq("(", tg.ref("expr"), ")")),
        infix=[
            ("or", "left", "or"), ("and", "left", "and"),
            ("<", "left", "compare"), (">", "left", "compare"),
            ("==", "left", "compare"), ("!=", "left", "compare"),
            ("+", "left", "add"), ("-", "left", "add"),
            ("*", "left", "mul"), ("/", "left", "mul"),
            ("^", "right", "pow"),
        ],
        prefix=[("-", "unary"), ("not", "not")],
        postfix=[
            ("call", "postfix",
             lambda e: tg.seq(e, "(", tg.opt(tg.ref("args")), ")")),
            ("member", "postfix",
             lambda e: tg.seq(e, ".", tg.ref("identifier"))),
        ],
        ladder=prec)

    # ---- statements ---------------------------------------------------------
    g.rule("assign", tg.seq(
        tg.field("name", tg.ref("identifier")), "=",
        tg.field("value", tg.ref("expr")), ";"))
    g.rule("let_stmt", tg.seq(
        "let", tg.field("name", tg.ref("identifier")), "=",
        tg.field("value", tg.ref("expr")), ";"))
    g.rule("if_stmt", tg.seq(
        "if",
        tg.field("cond", tg.seq("(", tg.ref("expr"), ")")),
        tg.field("then", tg.ref("statement")),
        tg.opt(tg.seq("else", tg.field("else", tg.ref("statement"))))),
        ambiguous=True)                    # dangling-else opt-in
    g.rule("expr_stmt", tg.seq(tg.ref("expr"), ";"))
    g.rule("fn_def", tg.seq(
        "fn", tg.field("name", tg.ref("identifier")), "(",
        tg.ref("params"), ")",
        tg.field("body", tg.ref("block")), ";"))
    g.rule("params", tg.seq(
        tg.field("param", tg.ref("identifier")),
        tg.repeat(tg.seq(",", tg.field("param", tg.ref("identifier"))))))
    g.rule("block", tg.seq("{", tg.repeat(tg.ref("statement")), "}"))
    g.rule("statement", tg.choice(
        tg.ref("assign"), tg.ref("let_stmt"), tg.ref("if_stmt"),
        tg.ref("expr_stmt"), tg.ref("fn_def"), tg.ref("block")),
        supertype=True)

    # ---- start --------------------------------------------------------------
    g.start("source_file")
    g.rule("source_file", tg.repeat(tg.ref("statement")))
    return g


if __name__ == "__main__":
    g = build()
    print("rules:", ", ".join(g.rules))
    for i in tg.run_checks(g):
        print(f"  ! {i}")
