#!/usr/bin/env python3
"""Walk a vendored typed node universe over the tree-sitter-python wheel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import tree_sitter
import tree_sitter_python

from pydantree_sitter import Grammar

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus.py"
GROUND_TRUTH = HERE / "ground_truth.json"
TRANSCRIPT = HERE / "transcript.txt"
SCHEMA = HERE / "vendor" / "python-node-types.json"

_lines: list[str] = []


def say(line: str = "") -> None:
    _lines.append(line)
    print(line)


def render(node, depth: int = 0, parent=None, idx: int = 0) -> None:
    field = parent.field_name_for_child(idx) if parent is not None else None
    prefix = "  " * depth
    label = f"{field}=" if field else ""
    if node.child_count == 0:
        text = (node.text or b"").decode()
        shown = text if len(text) <= 24 else text[:21] + "..."
        say(f"{prefix}{label}{node.type} {shown!r}")
        return
    say(f"{prefix}{label}{node.type}")
    for index, child in enumerate(node.children):
        render(child, depth + 1, node, index)


def _grammar() -> Grammar:
    language = tree_sitter.Language(tree_sitter_python.language())
    return Grammar.load(language, SCHEMA, schema_name="python")


def run(update: bool) -> int:
    grammar = _grammar()
    nodes = grammar.nodes
    source = CORPUS.read_text()

    say("=== step 1: load the vendored schema and typed node universe ===")
    say(f"schema: {SCHEMA.name!r} — no CLI and no gcc")
    say(f"generated kinds: {len(nodes.KIND_MAP)}")
    say("")

    say("=== step 2: parse the corpus (CST, fields shown) ===")
    tree = grammar.parse(source)
    render(tree.root_node)
    say("")

    say("=== step 3: find typed nodes ===")
    functions = tree.find(nodes.FunctionDefinition)
    assignments = tree.find(nodes.Assignment)
    function_rows = [{
        "name": row.name.__value__(),
        "return_type": row.return_type.__value__()
        if row.return_type is not None else None,
        "line": row.span.line,
    } for row in functions]
    assignment_rows = [{
        "target": row.left.__value__(),
        "value": row.right.__value__() if row.right is not None else None,
        "line": row.span.line,
    } for row in assignments]
    for row in function_rows:
        say(f"Function {row['name']!r} -> {row['return_type']!r} "
            f"at line {row['line']}")
    for row in assignment_rows:
        say(f"Assignment {row['target']!r} = {row['value']!r} "
            f"at line {row['line']}")
    say("")

    say("=== step 4: self-check against ground_truth.json ===")
    truth = json.loads(GROUND_TRUTH.read_text())
    ok = function_rows == truth["functions"] and \
        assignment_rows == truth["assignments"]
    say(f"functions: {len(function_rows)} rows, "
        f"assignments: {len(assignment_rows)} rows")
    say("all rows match the hand-written ground truth ✓" if ok
        else "mismatch ✗ (see above)")
    say("")

    say("=== step 5: the committed per-step transcript oracle ===")
    transcript = "\n".join(_lines) + "\n"
    saved = TRANSCRIPT.read_text() if TRANSCRIPT.exists() else None
    expected = transcript + "transcript.txt matches this run byte-for-byte ✓\n"
    if update:
        TRANSCRIPT.write_text(expected)
        print("transcript.txt UPDATED — eyeball the diff, then commit")
        return 0 if ok else 1
    if saved == expected:
        print("transcript.txt matches this run byte-for-byte ✓")
        return 0 if ok else 1
    print("transcript.txt DRIFTED — regenerate with --update after eyeballing")
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true")
    return run(parser.parse_args(argv).update)


if __name__ == "__main__":
    raise SystemExit(main())
