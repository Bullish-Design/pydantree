"""dmini — a mini language with matched-delimiter groups (the scanner library
seed #3, Phase 6). A `(...)` group with ARBITRARY nesting is ONE external
token (BALANCED) — the inner parens never reach the grammar.

    dmini_file -> item*
    item       -> identifier '=' expr
    expr       -> identifier | number | group
    group      -> BALANCED        (the scanner's balanced-parens token)
"""

from __future__ import annotations

import tsgrammar as tg


def build() -> tg.Grammar:
    g = tg.Grammar("dmini")
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"), word=True)
    g.rule("number", tg.pattern(r"\d+"))
    g.external(tg.tok("BALANCED"))

    g.rule("group", tg.tok("BALANCED"))
    g.rule("expr", tg.choice(tg.ref("identifier"), tg.ref("number"),
                             tg.ref("group")),
           supertype=True)
    g.rule("item", tg.seq(tg.field("name", tg.ref("identifier")), "=",
                          tg.field("value", tg.ref("expr"))))
    g.rule("dmini_file", tg.repeat(tg.ref("item")))
    g.start("dmini_file")
    return g


GOOD = "a = (1 + (2))\nb = (deeply (nested (group)))\n"
GOOD_EXPECTED = (
    "(dmini_file (item name: (identifier) '=' value: (group 'BALANCED')) "
    "(item name: (identifier) '=' value: (group 'BALANCED')))"
)

# the scanner refuses an unbalanced group at EOF (strict): the parse falls
# back, so the group is a parse ERROR, not a silently swallowed open paren
UNBALANCED = "a = (1 + (2)\n"
