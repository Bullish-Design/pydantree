#!/usr/bin/env python3
"""Probe the nix grammar's tree shapes over devenv.nix shapes (the shapes the
fleet-inventory models must express). Not extraction — just reading trees."""
import sys
sys.path.insert(0, "src")
from tscore.loader import load_bundle
import tree_sitter as ts

lang = load_bundle("/tmp/phase9/bundle9").language
parser = ts.Parser(lang)
src = open("tests/fixtures/nix/fleet/pydantree.nix").read()
tree = parser.parse(src.encode())
print(tree.root_node)

def find(node, types, out):
    if node.type in types:
        out.append(node)
    for c in node.children:
        find(c, types, out)

for t in ("binding_set", "attrset_expression", "list_expression", "indented_string_expression", "binding"):
    out = []
    find(tree.root_node, {t}, out)
    print(f"\n=== {t}: {len(out)} ===")
    for n in out[:2]:
        print(src[n.start_byte:n.end_byte][:200].replace(chr(10), "⏎"))
