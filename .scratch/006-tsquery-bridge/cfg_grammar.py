r"""cfg — the Phase-4 Run-1 config grammar: an INI-like language (sections,
`key = value` entries, comments, directives) built entirely with tsgrammar.
NOT JSON — the hardcoded JSON value-shape map cannot express it, which is the
point: only the derived map can.

Grammar design (hand-written before the derivation, per the kickoff):

    source_file -> statement*                      (start)
    statement   -> section | entry | directive     (supertype)
    section     -> '[' identifier ']' entry*       (the record node)
    entry       -> key: identifier '=' value: value (the pair node)
    directive   -> name: identifier arg: value      (field-mode target)
    value       -> integer | float | boolean | string | identifier (supertype)
    integer     -> /[+-]?[0-9]+/
    float       -> /[+-]?[0-9]+\.[0-9]+/
    boolean     -> 'true' | 'false'                 (one named kind)
    string      -> '"' (string_content | escape_sequence)* '"'   (non-token
                   form: CLI 0.25.3 rejects SYMBOL inside TOKEN)
    identifier  -> /[a-zA-Z_][a-zA-Z0-9_.-]*/       (word)
    comment     -> '#' ... | ';' ...                (extra)

Record mode: M("source_file", "section", record=True) — a section IS the
record; its entries are the pairs (key: identifier, value: value-supertype).
Field mode: M("source_file", "directive") — `include "x.conf"`-style.

The corpus (ground truth hand-computed):

    ; app.cfg
    [server]
    host = example.com          -> host: "example.com" (identifier)
    port = 8080                 -> port: 8080 (integer)
    debug = true                -> debug: True (boolean)
    title = "My App"            -> title: "My App" (string, unquoted)
    ratio = 0.75                -> ignored (not declared)

    [client]
    host = localhost
    port = 9090
    debug = false

    listen 8080                 -> directive (field mode)
    include "base.conf"         -> directive, string arg (excluded from Listen)
    reload 5                    -> directive, integer arg
"""

from __future__ import annotations

import tsgrammar as tg

CORPUS = """\
; app.cfg
[server]
host = example.com
port = 8080
debug = true
title = "My App"
ratio = 0.75

[client]
host = localhost
port = 9090
debug = false

listen 8080
include "base.conf"
reload 5
"""

# hand-computed ground truth
SECTION_GROUND_TRUTH = [
    {"host": "example.com", "port": 8080, "debug": True,
     "title": "My App", "line": 2},   # [server] at line 2 (line 1 is a comment)
    {"host": "localhost", "port": 9090, "debug": False,
     "title": None, "line": 9},
]

# with the schema, `port: int` constrains the arg capture to integer kinds,
# so `include "base.conf"` (string arg) is excluded at query level
LISTEN_GROUND_TRUTH = [
    {"name": "listen", "port": 8080, "line": 14},
    {"name": "reload", "port": 5, "line": 16},
]


def build() -> tg.Grammar:
    g = tg.Grammar("cfg")

    # lexical
    g.rule("comment", tg.token(tg.choice(
        tg.seq("#", tg.pattern(r"[^\n]*")),
        tg.seq(";", tg.pattern(r"[^\n]*")))))
    g.extra(tg.ref("comment"))
    g.rule("integer", tg.pattern(r"[+-]?[0-9]+"))
    g.rule("float", tg.pattern(r"[+-]?[0-9]+\.[0-9]+"))
    g.rule("boolean", tg.choice("true", "false"))
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_.-]*"), word=True)
    g.rule("directive_name", tg.choice("listen", "reload", "include"))
    g.rule("string_content", tg.token(tg.pattern(r'[^"\\]+')))
    g.rule("escape_sequence", tg.token(tg.seq("\\", tg.pattern(r'("|\\|n|t)'))))

    # structure
    g.rule("string", tg.seq(
        '"', tg.repeat(tg.choice(tg.ref("string_content"),
                                 tg.ref("escape_sequence"))), '"'))
    g.rule("value", tg.choice(tg.ref("integer"), tg.ref("float"),
                              tg.ref("boolean"), tg.ref("string"),
                              tg.ref("identifier")),
           supertype=True)
    g.rule("entry", tg.seq(tg.field("key", tg.ref("identifier")), "=",
                           tg.field("value", tg.ref("value"))))
    g.rule("section", tg.seq("[", tg.field("name", tg.ref("identifier")), "]",
                             tg.repeat(tg.ref("entry"))))
    g.rule("directive", tg.seq(tg.field("name", tg.ref("directive_name")),
                               tg.field("arg", tg.ref("value"))))
    g.rule("statement", tg.choice(tg.ref("section"), tg.ref("directive")),
           supertype=True)  # entries live INSIDE sections only
    g.rule("source_file", tg.repeat(tg.ref("statement")))
    g.start("source_file")
    return g
