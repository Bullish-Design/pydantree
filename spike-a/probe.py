#!/usr/bin/env python3
"""
Probe: validate 0.26 Query API assumptions with HAND-WRITTEN .scm before any
DSL code exists (the Phase-0 "hand-written grammar.json first" move).

Checks:
  1. wheel loading surface (tree_sitter.Language(<capsule>))
  2. anchored vs. unanchored patterns over a multi-assignment module
  3. captures() dict shape, matches() shape, capture_quantifier()
  4. predicates (#match? / #any-of?) and their failure modes
  5. node.text / byte_range / range / field access

Run: devenv shell -- python spike-a/probe.py
"""

from __future__ import annotations

import tree_sitter
import tree_sitter_python

SRC = """\
WIDTH = 1920
HEIGHT = 1080
NAME = "hello"
RATIO = 16 / 9
"""


def banner(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


def main() -> None:
    banner("1. loading surface")
    lang = tree_sitter.Language(tree_sitter_python.language())
    print("name      :", lang.name)
    print("abi       :", lang.abi_version)
    parser = tree_sitter.Parser(lang)
    tree = parser.parse(SRC.encode())
    print("root      :", tree.root_node, "has_error:", tree.root_node.has_error)

    banner("2. UNANCHORED pattern — one match per assignment?")
    q = tree_sitter.Query(
        lang,
        "(expression_statement (assignment "
        "left: (identifier) @name right: (integer) @value)) @stmt",
    )
    cursor = tree_sitter.QueryCursor(q)
    matches = cursor.matches(tree.root_node)
    print("matches() -> list[(pattern_index, dict[str, list[Node]])]")
    for i, (pi, caps) in enumerate(matches):
        print(f"  match[{i}] pi={pi} name={caps['name'][0].text!r} "
              f"value={caps['value'][0].text!r} stmt={caps['stmt'][0].type}")
    print("capture_count:", q.capture_count, "pattern_count:", q.pattern_count)
    for ci in range(q.capture_count):
        print(f"  capture[{ci}] name={q.capture_name(ci)!r} "
              f"quantifier(0,{ci})={q.capture_quantifier(0, ci)!r}")

    banner("3. ANCHORED pattern — what does (module ...) @root do?")
    q2 = tree_sitter.Query(
        lang,
        "(module (expression_statement (assignment "
        "left: (identifier) @name right: (integer) @value)) @stmt) @root",
    )
    m2 = list(tree_sitter.QueryCursor(q2).matches(tree.root_node))
    print(f"matches: {len(m2)}")
    for i, (pi, caps) in enumerate(m2):
        print(f"  match[{i}] root={caps['root'][0].type} "
              f"stmts={[n.type for n in caps.get('stmt', [])]} "
              f"names={[n.text for n in caps.get('name', [])]}")
    # captures() over the root node:
    caps = tree_sitter.QueryCursor(q2).captures(tree.root_node)
    print("captures(root) ->", {k: len(v) for k, v in caps.items()})

    banner("4. predicates")
    # NOTE: predicates must be INSIDE the pattern's s-expression, not a
    # separate top-level form (a bare (#match? ...) becomes its own empty
    # pattern that matches everything with zero captures).
    q3 = tree_sitter.Query(
        lang,
        "(expression_statement (assignment "
        "left: (identifier) @name "
        "right: (integer) @value)"
        " (#match? @name \"^[A-Z]+\"))",
    )
    got = [(c["name"][0].text, c["value"][0].text)
           for _, c in tree_sitter.QueryCursor(q3).matches(tree.root_node)]
    print("#match? ^[A-Z]+ on name ->", got)

    q4 = tree_sitter.Query(
        lang,
        "(expression_statement (assignment "
        "right: (integer) @value) (#any-of? @value \"1920\" \"1080\"))",
    )
    got4 = [c["value"][0].text
            for _, c in tree_sitter.QueryCursor(q4).matches(tree.root_node)]
    print("#any-of? (1920, 1080) on value ->", got4)

    banner("5. node surface: text / byte_range / range / fields")
    # grab the first assignment via the unanchored query (matches() is a LIST,
    # not a generator — noted for the lazy-cursor design)
    first = tree_sitter.QueryCursor(q).matches(tree.root_node)[0]
    stmt = first[1]["stmt"][0]
    assign = stmt.children[0]  # expression_statement wraps exactly the assignment
    print("stmt children:", [(c.type, c.is_named) for c in stmt.children])
    left = assign.child_by_field_name("left")
    print("left:", left.type, "text=", left.text,
          "byte_range=", left.byte_range, "range=", left.range)
    print("left.start_point:", left.start_point, "end_point:", left.end_point)
    print("field_name_for_named_child(0):", assign.field_name_for_named_child(0))

    banner("6. QUANTIFIERS: repeated captures need them")
    q5 = tree_sitter.Query(
        lang,
        "(module (expression_statement (assignment "
        "left: (identifier) @name right: (integer) @value))) @root",
    )
    caps5 = tree_sitter.QueryCursor(q5).captures(tree.root_node)
    print("single rooted pattern captures:", {k: len(v) for k, v in caps5.items()})
    # a pattern with a * quantifier: attributes are repeated
    q6 = tree_sitter.Query(
        lang,
        "(assignment left: (identifier) @name) @a",
    )
    caps6 = tree_sitter.QueryCursor(q6).captures(tree.root_node)
    print("unanchored assignment captures:", {k: len(v) for k, v in caps6.items()})
    for ci in range(q6.capture_count):
        print(f"  q6 capture[{ci}] {q6.capture_name(ci)!r} "
              f"quantifier={q6.capture_quantifier(0, ci)!r}")

    banner("7. is QueryCursor itself iterable? (lazy-cursor design question)")
    cur = tree_sitter.QueryCursor(q)
    print("has __next__:", hasattr(cur, "__next__"))
    print("has __iter__:", hasattr(cur, "__iter__"))
    print("dir:", [m for m in dir(cur) if not m.startswith("_")])


if __name__ == "__main__":
    main()
