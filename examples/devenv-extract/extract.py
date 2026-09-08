#!/usr/bin/env python3
"""Build or load the vendored Nix schema and traverse typed nodes."""

from __future__ import annotations

import sys
from pathlib import Path

import tree_sitter

from pydantree_sitter import Grammar, Node
from pydantree_sitter.schema import NodeSchema

HERE = Path(__file__).resolve().parent
FLEET = HERE / "fleet"
FILES = ("mypi-agent.nix", "pydantree.nix", "terminal-state.nix",
         "structured-agents-v2.nix", "fsdantic.nix", "nixvim.nix")


class Binding(Node):
    __kind__ = "binding"


class ListExpression(Node):
    __kind__ = "list_expression"


def load_grammar() -> Grammar:
    if "--bundle" in sys.argv:
        return Grammar.load_bundle(sys.argv[sys.argv.index("--bundle") + 1])
    try:
        import tree_sitter_nix
    except ModuleNotFoundError:
        from pydantree_sitter_grammar.schema_tool import build_community_bundle
        fixture = HERE.parents[1] / "tests" / "fixtures" / "nix"
        bundle = build_community_bundle(fixture, "/tmp/pydantree-example-nix",
                                        name="nix")
        return Grammar.load_bundle(bundle)
    language = tree_sitter.Language(tree_sitter_nix.language())
    schema = NodeSchema.from_node_types_json(HERE / "node-schema.json",
                                             name="nix")
    return Grammar.load(language, schema)


def main() -> int:
    grammar = load_grammar()
    print(f"schema: {len(grammar.schema.kinds())} kinds")
    for filename in FILES:
        source = (FLEET / filename).read_bytes()
        tree = grammar.parse(source)
        bindings = tree.find(Binding)
        lists = tree.find(ListExpression)
        print(f"{filename}: bindings={len(bindings)} lists={len(lists)}")
        for row in bindings[:5]:
            print(f"  binding line={row.span.line} text={row.__value__()!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
