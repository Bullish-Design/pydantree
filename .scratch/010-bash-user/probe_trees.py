"""Phase 8 — parse-tree probe over real tree-sitter-bash (in-repo, B available).

What the extraction models will match against: function definitions (both
forms), top-level variable assignments, heredoc usage. This probe prints the
trees so the hand truth can be written from bash's actual semantics.
"""
import sys

sys.path.insert(0, "src")
import tsgrammar as tg
from tsgrammar.schema_tool import build_community_bundle

bundle = build_community_bundle("tests/fixtures/bash", "/tmp/bash-bundle",
                                name="bash", keep=True)
lang, _lib = tg.load_language(str(bundle / "grammar.so"), "bash")

SRC = "\n".join([
    "#!/bin/bash",
    "# a comment",
    "greet() {",
    "  echo \"hello $name\"",
    "}",
    "",
    "function add {",
    "  local x=1",
    "}",
    "",
    "NAME=\"world\"",
    "AGE=42",
    "",
    "cat <<EOF",
    "line one",
    "line two",
    "EOF",
    "",
])

tree = tg.parse(lang, SRC)
errs = []


def walk(n):
    if n.type == "ERROR" or n.is_missing:
        errs.append((n.type, n.start_point.row + 1))
    for c in n.children:
        walk(c)


walk(tree.root_node)
print("errors:", errs)
print(tree.root_node)
