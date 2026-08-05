#!/usr/bin/env python3
"""wheel-extract — Product A over a COMMUNITY WHEEL, no toolchain.

The toolchain-free example (REVIEW 020 §3 recommendation): a community
grammar wheel (tree-sitter-python — no CLI, no gcc, no bundle build) drives
the whole Product A surface, and EVERY step lands in the COMMITTED per-step
transcript oracle (`transcript.txt`), so a reader sees exactly what is being
done at each step and a test proves the example still produces that exact
output.

Run it (any env with pydantree_sitter + tree-sitter-python installed):

    python examples/wheel-extract/extract.py             # run + self-check
    python examples/wheel-extract/extract.py --update    # regenerate the oracle
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import tree_sitter_python

from pydantree_sitter import Language, M, OutputModel, capture, source_meta

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus.py"
GROUND_TRUTH = HERE / "ground_truth.json"
TRANSCRIPT = HERE / "transcript.txt"


# ---------------------------------------------------------------------------
# the models (the A surface — the model IS the query)
# ---------------------------------------------------------------------------

class Function(OutputModel):
    """Every `def`: the name, the optional return type, and the line."""

    __match__ = M("module", "function_definition")
    name: str = capture("name")
    return_type: str | None = capture("return_type")
    line: int = source_meta()


class Assignment(OutputModel):
    """Every `target = value`: the left side, the right side, and the line."""

    __match__ = M("module", "expression_statement", "assignment")
    target: str = capture("left")
    value: str = capture("right")
    line: int = source_meta()


# ---------------------------------------------------------------------------
# transcript machinery (every step lands in the committed oracle)
# ---------------------------------------------------------------------------

_lines: list[str] = []


def say(line: str = "") -> None:
    _lines.append(line)
    print(line)


# ---------------------------------------------------------------------------
# the per-step run
# ---------------------------------------------------------------------------

def render(node, depth: int = 0, parent=None, idx: int = 0) -> None:
    """A compact CST render: kinds with their field names, leaf texts
    truncated — deterministic, so it can live in the transcript oracle."""
    field = parent.field_name_for_child(idx) if parent is not None else None
    prefix = "  " * depth
    label = f"{field}=" if field else ""
    if node.child_count == 0:
        text = node.text.decode()
        shown = text if len(text) <= 24 else text[:21] + "..."
        say(f"{prefix}{label}{node.type} {shown!r}")
    else:
        say(f"{prefix}{label}{node.type}")
        for i, c in enumerate(node.children):
            render(c, depth + 1, node, i)


def run(update: bool) -> int:
    lang = Language.from_module(tree_sitter_python)

    # step 1 — bind: what the models declare (the derived .scm, no build)
    say("=== step 1: bind the models over the tree_sitter_python wheel ===")
    say(f"language: {lang.name!r} — a community wheel (no CLI, no gcc, no "
        "bundle build)")
    say("")
    say("Function.compiled_source()  # the query each class IS:")
    say(Function.compiled_source(language=lang))
    say("")
    say("Assignment.compiled_source():")
    say(Assignment.compiled_source(language=lang))
    say("")

    # step 2 — parse: the corpus and its CST
    source = CORPUS.read_text()
    say("=== step 2: parse the corpus (CST, fields shown) ===")
    tree = lang.parse(source)
    render(tree.root_node)
    say("")

    # step 3 — extract: the typed rows
    say("=== step 3: extract typed rows ===")
    funcs = [r.model_dump() for r in Function.extract(source, language=lang)]
    assigns = [r.model_dump() for r in Assignment.extract(source, language=lang)]
    for r in funcs:
        say(f"Function {r['name']!r} -> {r['return_type']!r} at line {r['line']}")
    for r in assigns:
        say(f"Assignment {r['target']!r} = {r['value']!r} at line {r['line']}")
    say("")

    # step 4 — self-check against the hand-written ground truth
    say("=== step 4: self-check against ground_truth.json ===")
    truth = json.loads(GROUND_TRUTH.read_text())
    ok = funcs == truth["functions"] and assigns == truth["assignments"]
    say(f"functions: {len(funcs)} rows, assignments: {len(assigns)} rows")
    say("all rows match the hand-written ground truth ✓" if ok
        else "mismatch ✗ (see above)")
    say("")

    # step 5 — the committed per-step transcript oracle. The status line is
    # NOT part of _lines: the committed oracle ends with the (fixed) success
    # line, so a green run's stdout equals transcript.txt byte-for-byte — a
    # self-referential status ("DRIFTED") could never be a stable oracle.
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
    print("transcript.txt DRIFTED from this run — regenerate with --update "
          "after eyeballing, then commit")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update", action="store_true",
                    help="rewrite transcript.txt from this run")
    args = ap.parse_args(argv)
    return run(update=args.update)


if __name__ == "__main__":
    raise SystemExit(main())
