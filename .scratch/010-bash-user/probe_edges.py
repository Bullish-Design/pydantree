"""Phase 8 — edge probes: export's parent chain, heredoc variants, quoted
delimiters on separate commands, multi-heredoc on one line."""
import sys

sys.path.insert(0, "src")
import tsgrammar as tg
from tsgrammar.schema_tool import build_community_bundle

bundle = build_community_bundle("tests/fixtures/bash", "/tmp/bash-bundle",
                                name="bash", keep=True)
lang, _lib = tg.load_language(str(bundle / "grammar.so"), "bash")

# 1. export's parent chain
src1 = "export EXPORTED=1\nX=2\n"
tree = tg.parse(lang, src1)

def walk(n, out):
    out.append(n)
    for c in n.children:
        walk(c, out)

nodes = []
walk(tree.root_node, nodes)
for n in nodes:
    if n.type == "variable_assignment":
        chain = []
        p = n
        while p is not None:
            chain.append(p.type)
            p = p.parent
        print("var-assign ancestor chain:", " <- ".join(chain))
        print("  text:", repr(n.text))

# 2. heredoc variants on separate commands
src2 = "\n".join([
    "cat <<EOF",
    "plain body",
    "EOF",
    "",
    "cat <<'QUOTED'",
    "raw $body",
    "QUOTED",
    "",
    "cat <<-TAB",
    "\tindented line",
    "TAB",
    "",
])
tree2 = tg.parse(lang, src2)
nodes2 = []
walk(tree2.root_node, nodes2)
print("\nseparate-command heredocs errors:",
      [(n.type, n.start_point.row + 1) for n in nodes2
       if n.type == "ERROR" or n.is_missing])
for n in nodes2:
    if n.type == "heredoc_redirect":
        print("heredoc_redirect:", [(c.type, repr(c.text)) for c in n.children])

# 3. multi-heredoc on ONE command line
src3 = "cat <<A <<B\nbody A\nA\nbody B\nB\n"
tree3 = tg.parse(lang, src3)
nodes3 = []
walk(tree3.root_node, nodes3)
print("\nmulti-heredoc-on-one-line errors:",
      [(n.type, n.start_point.row + 1, repr(n.text)) for n in nodes3
       if n.type == "ERROR" or n.is_missing])
for n in nodes3:
    if n.type == "heredoc_redirect":
        print("  heredoc_redirect:", [(c.type, repr(c.text)) for c in n.children])

# 4. heredoc_end text + body trailing newline details
src4 = "cat <<E\none\ntwo\nE\n"
tree4 = tg.parse(lang, src4)
nodes4 = []
walk(tree4.root_node, nodes4)
for n in nodes4:
    if n.type == "heredoc_end":
        print("\nheredoc_end text:", repr(n.text), "start", n.start_point, "end", n.end_point)
