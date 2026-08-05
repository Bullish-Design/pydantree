"""bashmini — a mini shell with REAL bash-style heredocs (the Phase-7 scanner
library copy: the MULTI-heredoc pending queue, `<<-` indent-stripped, quoted
delimiters — adapted from tree-sitter-bash's scanner.c, on the hmini
mechanism: a single HEREDOC_BODY token that INCLUDES the delimiter line).

The grammar consumes the heredoc bodies in OPENING order (real bash reads
`cat <<A <<B` as A's body then B's body — the scanner serves the queue
FIFO, one HEREDOC_BODY token per pending heredoc):

    bashmini_file -> item*
    item          -> command newline heredoc*
    command       -> (identifier | HEREDOC_START)+     # `cat <<A <<B`
    heredoc       -> HEREDOC_BODY
    newline       -> '\n'

`<<` and `<<-` forms; `<<'TAG'` / `<<"TAG"` quoted delimiters (exact match).
The scanner's real semantics under test: several pending delimiters on ONE
command line (the queue), each body ends at ITS exact delimiter line, `<<-`
allows leading tabs on the delimiter line, an empty body is one BODY token
holding just the delimiter line, and a line that merely STARTS with the
delimiter word is content, not the end.
"""

from __future__ import annotations

import pydantree_sitter_grammar as tg


def build() -> tg.Grammar:
    g = tg.Grammar("bashmini")
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"), word=True)
    g.rule("newline", tg.token("\n"))

    # the scanner's tokens, in its expected order
    g.external(tg.tok("HEREDOC_START"), tg.tok("HEREDOC_BODY"))

    g.rule("command", tg.repeat1(tg.choice(tg.ref("identifier"),
                                           tg.tok("HEREDOC_START"))))
    g.rule("heredoc", tg.tok("HEREDOC_BODY"))
    g.rule("item", tg.seq(tg.ref("command"), tg.ref("newline"),
                          tg.repeat(tg.ref("heredoc"))))
    g.rule("bashmini_file", tg.repeat(tg.ref("item")))
    g.start("bashmini_file")
    return g


GOOD = ("cat <<EOF\nhello world\nEOF\n"
        "echo done\n")
GOOD_EXPECTED = (
    "(bashmini_file (item (command (identifier) 'HEREDOC_START') (newline) "
    "(heredoc 'HEREDOC_BODY')) "
    "(item (command (identifier) (identifier)) (newline)))"
)

# the MULTI-heredoc case: two pending delimiters on ONE command line — the
# bodies are served in OPENING order (A's content, then B's), one BODY token
# each (the token includes the delimiter line)
MULTI = ("cat <<A <<B\n"
         "body of A\n"
         "A\n"
         "body of B\n"
         "B\n")
MULTI_EXPECTED = (
    "(bashmini_file (item (command (identifier) 'HEREDOC_START' "
    "'HEREDOC_START') (newline) (heredoc 'HEREDOC_BODY') "
    "(heredoc 'HEREDOC_BODY')))"
)

# `<<-` indent-stripped: the delimiter line may be preceded by tabs
INDENTED = "cat <<-EOT\nline one\n\tEOT\n"
INDENTED_EXPECTED = (
    "(bashmini_file (item (command (identifier) 'HEREDOC_START') (newline) "
    "(heredoc 'HEREDOC_BODY')))"
)

# quoted delimiter: `<<'END'` — the quotes delimit the word, the body is
# inert content, and the delimiter line matches exactly
QUOTED = "cat <<'END'\n$var {not expansion}\nEND\n"
QUOTED_EXPECTED = (
    "(bashmini_file (item (command (identifier) 'HEREDOC_START') (newline) "
    "(heredoc 'HEREDOC_BODY')))"
)

# an empty body: the delimiter line is the immediate next content — ONE BODY
# token holding just the delimiter line (the hmini empty-body case)
EMPTY = "cat <<END\nEND\n"
EMPTY_EXPECTED = (
    "(bashmini_file (item (command (identifier) 'HEREDOC_START') (newline) "
    "(heredoc 'HEREDOC_BODY')))"
)

# a delimiter line that never comes: the body runs to EOF (lenient EOF, like
# the indentation seed — the pending heredoc is closed at EOF, bash-like)
UNTERMINATED = "cat <<END\nnever closed\n"
UNTERMINATED_EXPECTED = (
    "(bashmini_file (item (command (identifier) 'HEREDOC_START') (newline) "
    "(heredoc 'HEREDOC_BODY')))"
)

# a heredoc with no delimiter word (`<<` then a newline) is a parse ERROR
# (the scanner declines — there is no delimiter to match)
NO_DELIMITER = "cat <<\n"

# a line that merely STARTS with the delimiter word is NOT the delimiter line
# (exact match — only a line exactly equal to the delimiter ends the body)
PREFIX_LINE = "cat <<END\nENDless content\nEND\n"
PREFIX_LINE_EXPECTED = (
    "(bashmini_file (item (command (identifier) 'HEREDOC_START') (newline) "
    "(heredoc 'HEREDOC_BODY')))"
)
