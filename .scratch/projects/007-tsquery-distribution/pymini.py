"""pymini — a mini indentation-sensitive language (the external-scanner seed
grammar, Phase 5). Blocks are delimited by the INDENT/DEDENT tokens the
canonical scanner emits; statements end with NEWLINE.

    pymini_file -> statement*
    statement   -> assignment | if_stmt | expr_stmt
    assignment  -> identifier '=' expr NEWLINE
    expr_stmt   -> expr NEWLINE
    if_stmt     -> 'if' expr ':' 'NEWLINE' 'INDENT' statement+ DEDENT

Grammar design note: externals are declared in the scanner's expected order
(NEWLINE, INDENT, DEDENT — see scanners/indent_scanner.c). `if_stmt` ends
with an explicit DEDENT, so a nested `if` inside a block is a statement of
the inner block and its DEDENT closes it before the outer block's.
"""

from __future__ import annotations

import tsgrammar as tg


def build() -> tg.Grammar:
    g = tg.Grammar("pymini")

    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"), word=True)
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("comment", tg.token(tg.seq("#", tg.pattern(r"[^\n]*"))))
    g.extra(tg.ref("comment"))

    # the scanner's tokens, in its expected order
    g.external(tg.tok("NEWLINE"), tg.tok("INDENT"), tg.tok("DEDENT"))

    g.rule("expr", tg.choice(tg.ref("number"), tg.ref("identifier")))
    g.rule("assignment", tg.seq(tg.field("name", tg.ref("identifier")), "=",
                                tg.field("value", tg.ref("expr")),
                                tg.tok("NEWLINE")))
    g.rule("expr_stmt", tg.seq(tg.field("value", tg.ref("expr")),
                               tg.tok("NEWLINE")))
    # the block is INDENT statements DEDENT — no NEWLINE before INDENT (the
    # canonical indentation model: NEWLINE ends statements, INDENT opens a
    # block directly, so the scanner can emit INDENT in the same call that
    # measured the indentation; a NEWLINE-then-INDENT sequence cannot work
    # because emitting NEWLINE consumes the indentation the INDENT needs)
    g.rule("if_stmt", tg.seq("if", tg.field("cond", tg.ref("expr")), ":",
                             tg.tok("INDENT"),
                             tg.repeat(tg.ref("statement")),
                             tg.tok("DEDENT")))
    g.rule("statement", tg.choice(tg.ref("assignment"), tg.ref("if_stmt"),
                                  tg.ref("expr_stmt")),
           supertype=True)
    g.rule("pymini_file", tg.repeat(tg.ref("statement")))
    g.start("pymini_file")
    return g


# hand-computed ground truth shapes (sexp renderer, anonymous kept — the
# external tokens are anonymous literals, so they render quoted: 'NEWLINE')
GOOD = "x = 1\ny = 2\nif x:\n    z = 3\n    w = 4\n"
GOOD_EXPECTED = (
    "(pymini_file (assignment name: (identifier) '=' value: (expr (number)) "
    "'NEWLINE') (assignment name: (identifier) '=' value: (expr (number)) "
    "'NEWLINE') (if_stmt 'if' cond: (expr (identifier)) ':' 'INDENT' "
    "(assignment name: (identifier) '=' value: (expr (number)) 'NEWLINE') "
    "(assignment name: (identifier) '=' value: (expr (number)) 'NEWLINE') "
    "'DEDENT'))"
)

NESTED = "if a:\n    if b:\n        c = 1\n    d = 2\n"
NESTED_EXPECTED = (
    "(pymini_file (if_stmt 'if' cond: (expr (identifier)) ':' 'INDENT' "
    "(if_stmt 'if' cond: (expr (identifier)) ':' 'INDENT' "
    "(assignment name: (identifier) '=' value: (expr (number)) 'NEWLINE') "
    "'DEDENT') (assignment name: (identifier) '=' value: (expr (number)) "
    "'NEWLINE') 'DEDENT'))"
)

# comment-only lines inside a block do not break the block (Python semantics)
COMMENT_IN_BLOCK = "if a:\n    # a note\n    b = 1\n"
