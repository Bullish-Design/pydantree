# The devenv grammar authored with the BUILDER DSL — the preserved reference
# side of the byte-identity gate (tests/test_rules.py).
#
# This is the pre-migration spelling of `examples/devenv-subset/grammar.py`,
# saved verbatim from commit e2f3c6f when that example migrated to the
# rule-class surface. The gate asserts the class-authored example emits
# grammar.json DEEP-EQUAL to this file's build() — the surface is faithful
# sugar over the builder, not a new grammar language.

"""Product B — the "devenv config surface" grammar (the both-halves example).

A small grammar for the devenv.nix CONFIG surface — attrsets with dotted
attr paths, quoted path segments, `"..."` strings with `${...}`
interpolation, `''...''` multiline strings with `''${` escapes, lists,
`with pkgs; [...]`, `true`/`false`, comments — the shapes the fleet's real
configs actually use, WITHOUT the full Nix language (no let/in, function
formals are a simple header, no binary operators, no apply).

Authored with the tsgrammar DSL (Product B) so the consumer-side shape is
exactly what Product A wants:

  * the attrset's key/value pair is a DIRECT CHILD KIND with `key`/`value`
    FIELDS — the pair-kind detection record mode needs (upstream
    tree-sitter-nix's binding_set/binding/attrpath shape fails it — the
    Phase-9 finding);
  * the key is ONE TOKEN (`env.GREET`, `tasks."quoted".exec`) — a
    text-yielding leaf, so `key: str = capture("key")` passes the schema
    checks (upstream nix's structural attrpath is rejected);
  * the multiline-string fragments come from a tiny external scanner
    (scanner.c) — the same mechanism upstream uses, but simple enough to be
    position-stable (upstream's 7.6 KB scanner triggers a tree-sitter 0.26
    position corruption on large files — the Phase-9 finding).

Run it with `devenv shell -- python examples/devenv-subset/extract.py`
(builds the bundle with B, then extracts with A).
"""

from __future__ import annotations

import tsgrammar as tg


def build() -> tg.Grammar:
    g = tg.Grammar("devenv")

    # ---- lexical ----------------------------------------------------------
    g.rule("comment", tg.token(tg.seq("#", tg.pattern(r"[^\n]*"))))
    g.extra(tg.ref("comment"))

    # identifiers, dotted paths, and quoted path segments — ONE token rule,
    # so keys, value refs and formals share a single text-yielding leaf kind.
    # The FIRST segment may be a quoted string too (a standalone quoted key
    # like tasks' `"pydantree:venv-src-pth" = { ... }`):
    #   pkgs  config.env.DEVENV_ROOT  scripts.hello.exec  "quoted"
    #   tasks."quoted".exec
    g.rule("name_path", tg.token(tg.pattern(
        r'("[^"]*"|[a-zA-Z_][a-zA-Z0-9_-]*)(\.[a-zA-Z_][a-zA-Z0-9_-]*|"[^"]*")*')))
    g.rule("number", tg.pattern(r"[0-9]+"))
    g.rule("path_literal", tg.token(tg.pattern(r"\.[/][A-Za-z0-9_./-]+")))

    # the string fragments are external-scanner tokens (scanner.c)
    g.external(tg.tok("STRING_FRAGMENT"), tg.tok("INDENTED_STRING_FRAGMENT"))
    g.rule("string_fragment", tg.tok("STRING_FRAGMENT"))
    g.rule("indented_string_fragment", tg.tok("INDENTED_STRING_FRAGMENT"))

    # ---- strings ----------------------------------------------------------
    g.rule("interpolation", tg.seq("${",
                                   tg.field("expression", tg.ref("value")),
                                   "}"))
    g.rule("string", tg.seq('"',
                            tg.repeat(tg.choice(tg.ref("string_fragment"),
                                                tg.ref("interpolation"))),
                            '"'))
    g.rule("indented_string", tg.seq("''",
                                     tg.repeat(tg.choice(
                                         tg.ref("indented_string_fragment"),
                                         tg.ref("interpolation"))),
                                     "''"))

    # ---- structure --------------------------------------------------------
    # the KEY/VALUE PAIR: a direct child kind of the attrset with key/value
    # fields — the exact shape record mode's pair-kind detection needs
    g.rule("pair", tg.seq(tg.field("key", tg.ref("name_path")), "=",
                          tg.field("value", tg.ref("value")), ";"))
    g.rule("attrset", tg.seq("{", tg.repeat(tg.ref("pair")), "}"))
    g.rule("list", tg.seq("[",
                          tg.repeat(tg.field("element", tg.ref("value"))),
                          "]"))
    g.rule("with_expr", tg.seq("with", tg.ref("name_path"), ";",
                               tg.ref("value")))
    g.rule("value", tg.choice(tg.ref("string"), tg.ref("indented_string"),
                              tg.ref("list"), tg.ref("attrset"),
                              tg.ref("name_path"), tg.ref("number"),
                              tg.ref("path_literal"), tg.ref("with_expr")),
           supertype=True)
    # the `{ pkgs, lib, config, inputs, ... }:` header — each formal OPTIONALLY
    # eats its trailing comma (the real nix grammar's trick: the comma
    # attaches to the preceding formal, so `{ a, b }` and `{ a, b, ... }` are
    # unambiguous)
    g.rule("formal", tg.seq(tg.ref("name_path"), tg.opt(",")))
    g.rule("formals", tg.seq(
        "{",
        tg.repeat(tg.ref("formal")),
        tg.opt("..."),
        "}"))
    g.rule("source_file", tg.seq(
        tg.opt(tg.seq(tg.ref("formals"), ":")),
        tg.ref("attrset")))
    g.start("source_file")
    return g


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "src")
    g = build()
    print("rule count:", len(g.rules()))
    for w in tg.run_checks(g):
        print(w)
