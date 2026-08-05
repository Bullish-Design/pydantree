"""Phase 8 — probe: unclosed heredoc at EOF + file descriptor on heredocs."""
import sys

sys.path.insert(0, "src")
import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar.schema_tool import build_community_bundle

bundle = build_community_bundle("tests/fixtures/bash", "/tmp/bash-bundle",
                                name="bash", keep=True)
lang, _lib = tg.load_language(str(bundle / "grammar.so"), "bash")


def walk(n, out):
    out.append(n)
    for c in n.children:
        walk(c, out)


# 1. unclosed heredoc at EOF
src1 = "#!/usr/bin/env bash\ncat <<BODY\nunclosed body\n"
tree1 = tg.parse(lang, src1)
n1 = []
walk(tree1.root_node, n1)
print("unclosed-heredoc errors:",
      [(n.type, n.start_point.row + 1) for n in n1 if n.type == "ERROR" or n.is_missing])
for n in n1:
    if n.type == "heredoc_redirect":
        print("  heredoc_redirect:", [(c.type, repr(c.text)) for c in n.children])

# 2. file descriptor on a heredoc redirect
src2 = "3<<EOF\nbody\nEOF\n"
tree2 = tg.parse(lang, src2)
n2 = []
walk(tree2.root_node, n2)
print("fd errors:", [(n.type, n.start_point.row + 1) for n in n2
                     if n.type == "ERROR" or n.is_missing])
for n in n2:
    if n.type == "heredoc_redirect":
        print("  fd heredoc_redirect:", [(c.type, repr(c.text)) for c in n.children])
        print("  field descriptor:", n.child_by_field_name("descriptor"))
        print("  field argument:", n.child_by_field_name("argument"))
        print("  field operator:", n.child_by_field_name("operator"))
        print("  field redirect:", n.child_by_field_name("redirect"))
        print("  field right:", n.child_by_field_name("right"))

# 3. what the unclosed heredoc's body text is
for n in n1:
    if n.type == "heredoc_body":
        print("unclosed body repr:", repr(n.text))
