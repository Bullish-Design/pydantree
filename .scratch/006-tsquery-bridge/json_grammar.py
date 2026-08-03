"""json_grammar — the JSON grammar reconstructed as a tsgrammar IR, matching
the tree-sitter-json 0.24.8 wheel's CST kinds exactly (probed in Phase 4):

    document -> object/array/string/number/true/false/null
    object -> { pair* }
    pair -> key: string  ':'  value: value
    array -> [ value* ]
    string -> '"' (string_content | escape_sequence)* '"'
    number, true, false, null; comment extra

The IR is hand-written to the wheel's kinds so the derived node-schema is
valid for the wheel's language — the JSON reproduction check (the derived
record value-shape map == the spike-a2 JSON v1 map, over tree_sitter_json).

Two CLI-version constraints shaped it (verified in Phase 4):
  * CLI 0.25.3 rejects SYMBOL-inside-TOKEN, so `string` is a plain seq rule
    (not token()) with named string_content/escape_sequence children;
  * `value` is a supertype referenced directly (the real grammar's shape —
    children/field lists show the supertype, subtypes live on it).
"""

from __future__ import annotations

import tsgrammar as tg


def build() -> tg.Grammar:
    g = tg.Grammar("json")

    # lexical
    g.rule("string_content", tg.token(tg.pattern(r'[^"\\]+')))
    g.rule("escape_sequence", tg.token(
        tg.seq("\\", tg.pattern(r'("|\\|/|b|f|n|r|t|u)'))))
    g.rule("number", tg.token(tg.pattern(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?")))
    g.rule("true", "true")
    g.rule("false", "false")
    g.rule("null", "null")
    g.rule("comment", tg.token(tg.seq("//", tg.pattern(r"[^\n]*"))))
    g.extra(tg.ref("comment"))

    # structure
    g.rule("string", tg.seq(
        '"', tg.repeat(tg.choice(tg.ref("string_content"), tg.ref("escape_sequence"))), '"'))
    g.rule("value", tg.choice(tg.ref("object"), tg.ref("array"), tg.ref("string"),
                              tg.ref("number"), tg.ref("true"), tg.ref("false"),
                              tg.ref("null")),
           supertype=True)
    g.rule("pair", tg.seq(tg.field("key", tg.ref("string")), ":",
                          tg.field("value", tg.ref("value"))))
    g.rule("object", tg.seq(
        "{",
        tg.repeat(tg.ref("pair")),
        tg.repeat(tg.seq(",", tg.ref("pair"))),
        tg.opt(","), "}"))
    g.rule("array", tg.seq(
        "[",
        tg.repeat(tg.ref("value")),
        tg.repeat(tg.seq(",", tg.ref("value"))),
        tg.opt(","), "]"))
    g.rule("document", tg.repeat(tg.ref("value")))
    g.start("document")
    return g
