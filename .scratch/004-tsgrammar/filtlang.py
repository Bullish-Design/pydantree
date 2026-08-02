"""
filtlang — a small filter/expression language authored ENTIRELY through the
tsgrammar builder DSL (Experiment B's grammar).

Exercises the DSL surface: tokens (PATTERN), a `word` declaration, FIELD,
extras with a comment rule per the Phase-0 rule (named rule + SYMBOL
reference), opt/repeat, a hidden rule with an ALIAS (Experiment-A lesson:
alias wraps a single hidden symbol, not a seq), a supertype, an intentional-
ambiguity whitelist (dangling else), and an int precedence ladder.
"""

from __future__ import annotations

import tsgrammar as tg

# precedence ladder (hand-rolled; Phase 3 will generate this from a table)
COMPARE, ADD, MUL, UNARY = 1, 2, 3, 4


def build() -> tg.Grammar:
    g = tg.Grammar("filtlang")

    # ---- lexical rules -----------------------------------------------------
    g.rule("number", tg.pattern(r"\d+(\.\d+)?"))
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"))
    g.word("identifier")

    # strings are TOKENs: quote, then escapes-or-runs, quote
    g.rule("string", tg.token(tg.seq(
        '"',
        tg.repeat(tg.choice(tg.pattern(r"\\."), tg.pattern(r'[^"\\]+'))),
        '"',
    )))

    # comments MUST be a named rule referenced via SYMBOL in extras
    # (Phase-0: a bare inline pattern whose prefix is a token never lexes)
    g.rule("comment", tg.token(tg.choice(
        tg.seq("//", tg.pattern(r"[^\n]*")),
        tg.seq("/*", tg.pattern(r"[^*]*\*+([^/*][^*]*\*+)*"), "/"),
    )))
    g.extra(tg.pattern(r"\s"))
    g.extra(tg.ref("comment"))

    # ---- statements --------------------------------------------------------
    g.rule("assign", tg.seq(
        tg.field("name", tg.ref("identifier")),
        "=",
        tg.field("value", tg.ref("expr"))))

    g.rule("if_stmt", tg.seq(
        "if",
        tg.field("cond", tg.ref("expr")),
        tg.field("then", tg.ref("statement")),
        tg.opt(tg.seq("else", tg.field("else", tg.ref("statement"))))))

    g.rule("expr_stmt", tg.seq(tg.ref("expr"), ";"))

    g.rule("fn_def", tg.seq(
        "fn",
        tg.field("name", tg.ref("identifier")),
        "(",
        tg.ref("params"),
        ")",
        tg.field("body", tg.ref("block"))))

    g.rule("params", tg.seq(
        tg.field("param", tg.ref("identifier")),
        tg.repeat(tg.seq(",", tg.field("param", tg.ref("identifier"))))))

    g.rule("block", tg.seq("{", tg.repeat(tg.ref("statement")), "}"))

    g.rule("statement", tg.choice(
        tg.ref("assign"), tg.ref("if_stmt"),
        tg.ref("expr_stmt"), tg.ref("fn_def")),
        supertype=True)

    # ---- expressions -------------------------------------------------------
    g.rule("compare_op", tg.choice("<", ">", "==", "!="))
    g.rule("expr", tg.choice(
        tg.prec_left(COMPARE, tg.seq(tg.ref("expr"), tg.ref("compare_op"), tg.ref("expr"))),
        tg.prec_left(ADD, tg.seq(tg.ref("expr"), "+", tg.ref("expr"))),
        tg.prec_left(ADD, tg.seq(tg.ref("expr"), "-", tg.ref("expr"))),
        tg.prec_left(MUL, tg.seq(tg.ref("expr"), "*", tg.ref("expr"))),
        tg.prec_left(MUL, tg.seq(tg.ref("expr"), "/", tg.ref("expr"))),
        tg.prec(UNARY, tg.seq("-", tg.ref("expr"))),
        tg.ref("atom")))

    g.rule("atom", tg.choice(
        tg.ref("number"), tg.ref("identifier"), tg.ref("string"),
        tg.ref("call"),
        tg.seq("(", tg.ref("expr"), ")")))

    # hidden rule + ALIAS: the visible "arguments" node is produced by a hidden
    # container (`_args`) aliasing a single hidden symbol (`_args_content`).
    g.rule("_args_content", tg.seq(
        tg.field("arg", tg.ref("expr")),
        tg.repeat(tg.seq(",", tg.field("arg", tg.ref("expr"))))))
    g.rule("_args", tg.alias("arguments", True, tg.ref("_args_content")))
    g.rule("call", tg.prec(1, tg.seq(
        tg.ref("identifier"), "(",
        tg.choice(tg.ref("_args"), tg.blank()),
        ")")))

    # ---- start (emitted first) ---------------------------------------------
    g.start("source_file")
    g.rule("source_file", tg.repeat(tg.ref("statement")))

    # dangling-else whitelist (GLR keeps the ambiguity; runtime resolves greedy)
    g.conflict("if_stmt")
    return g
