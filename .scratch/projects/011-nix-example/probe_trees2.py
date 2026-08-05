#!/usr/bin/env python3
"""Probe 2: exact node texts + the shapes the models must express.
Slices BYTES (tree offsets are byte offsets) and decodes for display."""
import sys
sys.path.insert(0, "src")
from pydantree_sitter.loader import load_bundle
import tree_sitter as ts

lang = load_bundle("/tmp/phase9/bundle9").language
parser = ts.Parser(lang)
data = open("tests/fixtures/nix/fleet/pydantree.nix", "rb").read()
tree = parser.parse(data)

def t(n, limit=70):
    return repr(data[n.start_byte:n.end_byte][:limit].decode())

def fname(n, i):
    return n.field_name_for_child(i) or None

def walk(node):
    yield node
    for c in node.children:
        yield from walk(c)

for n in walk(tree.root_node):
    if n.type == "indented_string_expression" and n.start_point.row in (43, 58):
        print("INDENTED STRING line", n.start_point.row + 1, ":", t(n))
    if n.type == "attrpath" and n.start_point.row in (4, 43, 44):
        attrs = [data[c.start_byte:c.end_byte].decode() for i, c
                 in enumerate(n.children) if fname(n, i) == "attr"]
        print("ATTRPATH line", n.start_point.row + 1, "attrs:", attrs,
              "| raw:", t(n))
    if n.type == "binding" and n.start_point.row == 4:
        print("  env.GREET binding children:")
        for i, c in enumerate(n.children):
            print("   ", fname(n, i), c.type, t(c, 60))
    if n.type == "binding" and n.start_point.row == 48:
        print("  tasks binding children:")
        for i, c in enumerate(n.children):
            print("   ", fname(n, i), c.type, t(c, 60))
    if n.type == "binding_set" and n.start_point.row == 5:
        for i, c in enumerate(n.children):
            if fname(n, i) == "binding":
                print("  env binding:", t(c, 60))
