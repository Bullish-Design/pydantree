#!/usr/bin/env python3
"""Traverse typed nodes from a vendored shell grammar schema."""

from __future__ import annotations

import sys
from pathlib import Path

import tree_sitter

from pydantree_sitter import Grammar, Node
from pydantree_sitter.schema import NodeSchema

HERE = Path(__file__).resolve().parent


class FunctionDefinition(Node):
    __kind__ = "function_definition"


class VariableAssignment(Node):
    __kind__ = "variable_assignment"


class HeredocRedirect(Node):
    __kind__ = "heredoc_redirect"


def load_grammar() -> Grammar:
    if "--bundle" in sys.argv:
        return Grammar.load_bundle(sys.argv[sys.argv.index("--bundle") + 1])
    try:
        import tree_sitter_bash
    except ModuleNotFoundError:
        from pydantree_sitter_grammar.schema_tool import build_community_bundle
        fixture = HERE.parents[1] / "tests" / "fixtures" / "bash"
        bundle = build_community_bundle(fixture, "/tmp/pydantree-example-bash",
                                        name="bash")
        return Grammar.load_bundle(bundle)
    language = tree_sitter.Language(tree_sitter_bash.language())
    schema = NodeSchema.from_node_types_json(HERE / "node-schema.json",
                                             name="bash")
    return Grammar.load(language, schema)


def main() -> int:
    grammar = load_grammar()
    print(f"schema: {len(grammar.schema.kinds())} kinds")
    for filename in ("sample.sh", "real_script.sh", "unclosed.sh"):
        source = (HERE / filename).read_bytes()
        tree = grammar.parse(source)
        functions = tree.find(FunctionDefinition)
        assignments = tree.find(VariableAssignment)
        heredocs = tree.find(HeredocRedirect)
        print(f"{filename}: functions={len(functions)} "
              f"assignments={len(assignments)} heredocs={len(heredocs)}")
        for row in [*functions, *assignments, *heredocs]:
            print(f"  {row.__kind__} line={row.span.line} text={row.__value__()!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
