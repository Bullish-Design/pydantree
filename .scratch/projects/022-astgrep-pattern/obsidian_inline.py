"""Bounded Obsidian inline grammar for project 022."""

import pydantree_sitter_grammar as tg

g = tg.Grammar("obsidian_inline")

g.rule("wiki_link", tg.token(tg.pattern(r"\[\[[^\]\n]+\]\]")))
g.rule("embed", tg.token(tg.pattern(r"!\[\[[^\]\n]+\]\]")))
g.rule("tag", tg.token(tg.pattern(r"#[A-Za-z][A-Za-z0-9_/-]*")))
g.rule("callout_marker", tg.token(tg.pattern(r"\[![A-Za-z]+\]-?")))
g.rule("inline_field", tg.token(tg.pattern(
    r"[A-Za-z_][A-Za-z0-9_.-]*::[A-Za-z0-9 .,;_'-]+")))
g.rule("block_id", tg.token(tg.pattern(r"\^[A-Za-z0-9_-]+")))
g.rule("highlight", tg.token(tg.pattern(r"==[^=\n]+==")))
g.rule("comment", tg.token(tg.pattern(r"%%[^%\n]+%%")))
g.rule("line_break", tg.token("\n"))
g.rule("text", tg.pattern(r"[^!\[\]#\^=%\n]+"))
g.rule("punctuation", tg.pattern(r"[!\[\]#\^=%]"))
g.rule("source_file", tg.repeat1(tg.choice(
    tg.ref("embed"), tg.ref("wiki_link"), tg.ref("tag"),
    tg.ref("callout_marker"), tg.ref("inline_field"), tg.ref("block_id"),
    tg.ref("highlight"), tg.ref("comment"), tg.ref("line_break"),
    tg.ref("text"),
    tg.ref("punctuation"))))
g.start("source_file")


def build():
    """Build and return the grammar builder result."""
    issues = list(tg.run_checks(g))
    if tg.errors(g):
        raise RuntimeError("grammar checks failed: " + repr(issues))
    return tg.build_builder(g)
