"""Phase 8 — detailed probe of the three extraction targets over bash.

Prints field names, child kinds, and node texts for function_definition,
variable_assignment, and heredoc_redirect nodes, across the variant forms:
foo() {}, function foo {}, <<EOF, <<-EOF, <<'EOF', and assignments.
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
    "greet() {",
    "  echo \"hi $name\"",
    "}",
    "function add {",
    "  local x=1",
    "}",
    "NAME=\"world\"",
    "AGE=42",
    "export EXPORTED=1",
    "cat <<EOF",
    "line one",
    "line two",
    "EOF",
    "cat <<-TAB <<'QUOTED'",
    "  indented",
    "TAB",
    "raw $not_expanded",
    "QUOTED",
    "",
])

tree = tg.parse(lang, SRC)


def walk(n, out):
    out.append(n)
    for c in n.children:
        walk(c, out)


def show(label, text):
    print(f"--- {label} ---")
    print(text)


nodes = []
walk(tree.root_node, nodes)
errs = [(n.type, n.start_point.row + 1) for n in nodes
        if n.type == "ERROR" or n.is_missing]
print("errors:", errs)

for n in nodes:
    if n.type == "function_definition":
        show("function_definition", f"name field: {n.child_by_field_name('name')}"
             f"\nbody field: {n.child_by_field_name('body')}"
             f"\nstart_line: {n.start_point.row + 1}"
             f"\nchildren: {[(c.type, c.is_named) for c in n.children]}")
        print(repr(n.text))
    elif n.type == "variable_assignment":
        show("variable_assignment",
             f"name field: {n.child_by_field_name('name')!r}"
             f"\nvalue field: {n.child_by_field_name('value')!r}"
             f"\nstart_line: {n.start_point.row + 1}"
             f"\nchildren: {[(c.type, c.is_named) for c in n.children]}")
        print(repr(n.text))
    elif n.type == "heredoc_redirect":
        show("heredoc_redirect",
             f"children: {[(c.type, c.is_named, repr(c.text)) for c in n.children]}"
             f"\nstart_line: {n.start_point.row + 1}")
        for c in n.children:
            if c.type in ("heredoc_body", "heredoc_content"):
                print(f"  {c.type} repr: {c.text!r}")
    elif n.type == "heredoc_start":
        print(f"heredoc_start standalone: {n.text!r} line {n.start_point.row + 1}")
