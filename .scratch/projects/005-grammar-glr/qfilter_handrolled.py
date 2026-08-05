"""
qfilter_handrolled — the Run-3 CONTROL: the SAME qfilter grammar authored the
Phase-2 way (the filtlang pattern), with no Phase-3 helpers.

- hand-rolled integer precedence ladder (magic constants)
- explicit prec_left/prec_right/prec on every operator alternative
- explicit `conflict("if_stmt")` whitelist + manual prec_dynamic wrapper
- explicit whitespace extra + separate word() call
- hand-written expr rule with the author picking every integer

The expression structure is IDENTICAL to the helper's emission (single-rule
choice, all-int, postfix at the top): this is the "without Phase 3" control,
not a strawman.
"""

from __future__ import annotations

import pydantree_sitter_grammar as tg

# hand-rolled ladder (magic integers; renumbering is manual)
OR, AND, NOT, COMPARE, ADD, MUL, UNARY, POW, POSTFIX = 1, 2, 3, 4, 5, 6, 7, 8, 9


def build() -> tg.Grammar:
    g = tg.Grammar("qfilter_hand")

    # ---- lexical -----------------------------------------------------------
    g.rule("number", tg.pattern(r"\d+(\.\d+)?"))
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"))
    g.word("identifier")
    g.rule("string", tg.token(tg.seq(
        '"',
        tg.repeat(tg.choice(tg.pattern(r"\\."), tg.pattern(r'[^"\\]+'))),
        '"')))
    g.rule("comment", tg.token(tg.choice(
        tg.seq("//", tg.pattern(r"[^\n]*")),
        tg.seq("/*", tg.pattern(r"[^*]*\*+([^/*][^*]*\*+)*"), "/"))))
    g.extra(tg.pattern(r"\s"))
    g.extra(tg.ref("comment"))

    # ---- expressions: one rule, every alternative explicitly annotated ------
    g.rule("args", tg.seq(tg.ref("expr"),
                          tg.repeat(tg.seq(",", tg.ref("expr")))))
    g.rule("expr", tg.choice(
        tg.prec_left(OR, tg.seq(tg.ref("expr"), "or", tg.ref("expr"))),
        tg.prec_left(AND, tg.seq(tg.ref("expr"), "and", tg.ref("expr"))),
        tg.prec(NOT, tg.seq("not", tg.ref("expr"))),
        tg.prec_left(COMPARE, tg.seq(tg.ref("expr"), "<", tg.ref("expr"))),
        tg.prec_left(COMPARE, tg.seq(tg.ref("expr"), ">", tg.ref("expr"))),
        tg.prec_left(COMPARE, tg.seq(tg.ref("expr"), "==", tg.ref("expr"))),
        tg.prec_left(COMPARE, tg.seq(tg.ref("expr"), "!=", tg.ref("expr"))),
        tg.prec_left(ADD, tg.seq(tg.ref("expr"), "+", tg.ref("expr"))),
        tg.prec_left(ADD, tg.seq(tg.ref("expr"), "-", tg.ref("expr"))),
        tg.prec_left(MUL, tg.seq(tg.ref("expr"), "*", tg.ref("expr"))),
        tg.prec_left(MUL, tg.seq(tg.ref("expr"), "/", tg.ref("expr"))),
        tg.prec(UNARY, tg.seq("-", tg.ref("expr"))),
        tg.prec_right(POW, tg.seq(tg.ref("expr"), "^", tg.ref("expr"))),
        # postfix MUST outrank the unary (Phase-3 probe-2 finding)
        tg.prec(POSTFIX, tg.seq(tg.ref("expr"), "(", tg.opt(tg.ref("args")), ")")),
        tg.prec(POSTFIX, tg.seq(tg.ref("expr"), ".", tg.ref("identifier"))),
        tg.ref("number"), tg.ref("string"), tg.ref("identifier"),
        tg.seq("(", tg.ref("expr"), ")"),
    ))

    # ---- statements ---------------------------------------------------------
    g.rule("assign", tg.seq(
        tg.field("name", tg.ref("identifier")), "=",
        tg.field("value", tg.ref("expr")), ";"))
    g.rule("let_stmt", tg.seq(
        "let", tg.field("name", tg.ref("identifier")), "=",
        tg.field("value", tg.ref("expr")), ";"))
    g.rule("if_stmt", tg.prec_dynamic(1, tg.seq(
        "if",
        tg.field("cond", tg.seq("(", tg.ref("expr"), ")")),
        tg.field("then", tg.ref("statement")),
        tg.opt(tg.seq("else", tg.field("else", tg.ref("statement")))))))
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
        tg.ref("expr_stmt"), tg.ref("fn_def")),
        supertype=True)

    # ---- start --------------------------------------------------------------
    g.start("source_file")
    g.rule("source_file", tg.repeat(tg.ref("statement")))

    # dangling else, whitelisted the old way
    g.conflict("if_stmt")
    return g


if __name__ == "__main__":
    g = build()
    print("rules:", ", ".join(g.rules))
    for i in tg.run_checks(g):
        print(f"  ! {i}")
