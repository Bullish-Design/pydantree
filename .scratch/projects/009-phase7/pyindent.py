"""pyindent — a mini Python with REAL logical-line semantics (the Phase-7
scanner library copy: NEWLINE/INDENT/DEDENT over logical lines, adapted from
tree-sitter-python's scanner.c — NOT pymini's simplified semantics).

The differences from pymini are the scanner's, and the grammar's shape is
the real one: a compound header line ends with NEWLINE, then INDENT opens the
block (the two-call zero-width cadence), and a statement inside a block ends
with NEWLINE:

    pyindent_file -> statement*
    statement     -> assignment | if_stmt
    assignment    -> identifier '=' expr NEWLINE
    if_stmt       -> 'if' expr ':' NEWLINE INDENT statement+ DEDENT

The scanner's real semantics under test: comment-only lines and blank lines
emit NO NEWLINE (they are skipped inside the scanner); a backslash
continuation keeps the logical line open (one NEWLINE for the whole line);
a trailing comment after an expression is NOT a line ending (the grammar's
comment extra consumes it; the NEWLINE comes after).
"""

from __future__ import annotations

import tsgrammar as tg


def build() -> tg.Grammar:
    g = tg.Grammar("pyindent")
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"), word=True)
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("comment", tg.token(tg.seq("#", tg.pattern(r"[^\n]*"))))
    # a backslash-continuation is an EXTRA (upstream tree-sitter-python's
    # line_continuation) — the main lexer skips `\` + newline between tokens,
    # so a logical line spans the continuation; the scanner's own backslash
    # branch guards the scanner-called-at-backslash case
    g.rule("line_continuation",
           tg.token(tg.seq("\\", tg.pattern(r"[\r]?\n"))))
    g.extra(tg.ref("comment"))
    g.extra(tg.ref("line_continuation"))

    # the scanner's tokens, in its expected order
    g.external(tg.tok("NEWLINE"), tg.tok("INDENT"), tg.tok("DEDENT"))

    g.rule("expr", tg.choice(tg.ref("number"), tg.ref("identifier")))
    g.rule("assignment", tg.seq(tg.field("name", tg.ref("identifier")), "=",
                                tg.field("value", tg.ref("expr")),
                                tg.tok("NEWLINE")))
    # the REAL header shape: `if x:` ends with NEWLINE (the scanner's
    # zero-width NEWLINE), then INDENT opens the block directly — the
    # two-call cadence (NEWLINE at the newline, INDENT at the same position)
    g.rule("if_stmt", tg.seq("if", tg.field("cond", tg.ref("expr")), ":",
                             tg.tok("NEWLINE"), tg.tok("INDENT"),
                             tg.repeat(tg.ref("statement")),
                             tg.tok("DEDENT")))
    g.rule("statement", tg.choice(tg.ref("assignment"), tg.ref("if_stmt")),
           supertype=True)
    g.rule("pyindent_file", tg.repeat(tg.ref("statement")))
    g.start("pyindent_file")
    return g


GOOD = "x = 1\ny = 2\nif x:\n    z = 3\n    w = 4\n"
GOOD_EXPECTED = (
    "(pyindent_file (assignment name: (identifier) '=' value: (expr (number)) "
    "'NEWLINE') (assignment name: (identifier) '=' value: (expr (number)) "
    "'NEWLINE') (if_stmt 'if' cond: (expr (identifier)) ':' 'NEWLINE' 'INDENT' "
    "(assignment name: (identifier) '=' value: (expr (number)) 'NEWLINE') "
    "(assignment name: (identifier) '=' value: (expr (number)) 'NEWLINE') "
    "'DEDENT'))"
)

# comment-only line inside a block: NO NEWLINE token (the scanner skips it) —
# the block's statements stay contiguous (the comment extra renders inline)
COMMENT_IN_BLOCK = "if a:\n    x = 1\n    # a note\n    y = 2\n"
COMMENT_IN_BLOCK_EXPECTED = (
    "(pyindent_file (if_stmt 'if' cond: (expr (identifier)) ':' 'NEWLINE' "
    "'INDENT' (assignment name: (identifier) '=' value: (expr (number)) "
    "'NEWLINE') (comment) (assignment name: (identifier) '=' value: "
    "(expr (number)) 'NEWLINE') 'DEDENT'))"
)

# backslash continuation: `total = \` + newline + `1` is ONE logical line
# (the line_continuation extra is skipped by the main lexer; the NEWLINE
# token comes only after `1`) — a real Python semantic the pymini seed lacks
CONTINUATION = "total = \\\n    1\nnext = 3\n"
CONTINUATION_EXPECTED = (
    "(pyindent_file (assignment name: (identifier) '=' (line_continuation) "
    "value: (expr (number)) 'NEWLINE') (assignment name: (identifier) '=' "
    "value: (expr (number)) 'NEWLINE'))"
)

# trailing comment after an expression is not a line ending; the statement's
# NEWLINE still comes after the comment
TRAILING_COMMENT = "x = 1 # note\ny = 2\n"
TRAILING_COMMENT_EXPECTED = (
    "(pyindent_file (assignment name: (identifier) '=' value: (expr (number)) "
    "(comment) 'NEWLINE') (assignment name: (identifier) '=' value: "
    "(expr (number)) 'NEWLINE'))"
)

# blank lines inside a block are skipped (no NEWLINE, block continues)
BLANK_IN_BLOCK = "if a:\n    x = 1\n\n    y = 2\n"

# EOF with open indentation flushes the pending DEDENT
DEDENT_AT_EOF = "if a:\n    x = 1\n"
DEDENT_AT_EOF_EXPECTED = (
    "(pyindent_file (if_stmt 'if' cond: (expr (identifier)) ':' 'NEWLINE' "
    "'INDENT' (assignment name: (identifier) '=' value: (expr (number)) "
    "'NEWLINE') 'DEDENT'))"
)
# a header with no body is a parse ERROR (statement+ requires at least one
# statement inside the block)
EMPTY_BLOCK = "if x:\n"
