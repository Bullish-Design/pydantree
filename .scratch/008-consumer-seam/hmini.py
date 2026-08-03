"""hmini — a mini heredoc language (the scanner library seed #2, Phase 6).

Statements end with NEWLINE; a heredoc is `<<TAG` then the content lines,
terminated by a line exactly equal to TAG (the heredoc BODY external token
INCLUDES the delimiter line; the trailing newline is a regular NEWLINE).

    hmini_file   -> statement*
    statement    -> assignment | heredoc_stmt
    assignment   -> identifier '=' number NEWLINE
    heredoc_stmt -> HEREDOC_START HEREDOC_BODY NEWLINE
"""

from __future__ import annotations

import tsgrammar as tg


def build() -> tg.Grammar:
    g = tg.Grammar("hmini")
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"), word=True)
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("newline", tg.token("\n"))

    # the scanner's tokens, in its expected order
    g.external(tg.tok("HEREDOC_START"), tg.tok("HEREDOC_BODY"))

    g.rule("assignment", tg.seq(tg.field("name", tg.ref("identifier")), "=",
                                tg.field("value", tg.ref("number")),
                                tg.ref("newline")))
    g.rule("heredoc_stmt", tg.seq(tg.tok("HEREDOC_START"),
                                  tg.tok("HEREDOC_BODY"),
                                  tg.ref("newline")))
    g.rule("statement", tg.choice(tg.ref("assignment"), tg.ref("heredoc_stmt")),
           supertype=True)
    g.rule("hmini_file", tg.repeat(tg.ref("statement")))
    g.start("hmini_file")
    return g


GOOD = "x = 1\n<<TAG\nhello\nworld\nTAG\ny = 2\n"
GOOD_EXPECTED = (
    "(hmini_file (assignment name: (identifier) '=' value: (number) (newline)) "
    "(heredoc_stmt 'HEREDOC_START' 'HEREDOC_BODY' (newline)) "
    "(assignment name: (identifier) '=' value: (number) (newline)))"
)

# the body token INCLUDES the delimiter line (bash-like); an empty body is
# two consecutive delimiter lines
EMPTY_BODY = "<<END\nEND\n"
NESTED_MARKER = "<<EOT\nif (a) {\n  x();\n}\nEOT\ndone = 2\n"
