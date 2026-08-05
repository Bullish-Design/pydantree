#!/usr/bin/env python3
"""Regenerate the golden conflict-report corpus (REVIEW 018 §4.2/B7).

The three `tests/fixtures/conflicts/*_stderr.json` files are the VERBATIM
conflict report the real tree-sitter CLI (0.25.3) emits on stderr under
`--json` for three minimal grammars. The golden tests parse/render them
WITHOUT invoking the CLI — that is the structural drift guard. This script
re-creates the report with the real CLI so the saved bytes stay honest.

Usage (from the repository root, through the managed shell):

    # Check only; no repository mutation. Exits 1 if any fixture differs.
    devenv shell -- python tests/fixtures/conflicts/regenerate.py

    # Intentional refresh after a supported-CLI change (0.25.x only — a
    # minor bump is caught by tests/test_toolchain_version.py first).
    devenv shell -- python tests/fixtures/conflicts/regenerate.py --write

The grammars are the minimal ones that exhibit each conflict:

  shift_reduce  expr -> expr '+' expr | number         (no precedence)
  dangling_else if_stmt / if_else over stmt           (classic if/else)
  reduce_reduce a -> 'x'; b -> 'x'; s -> a | b        (two rules, one token)

Each grammar is built with the authoring DSL (the same shape the golden
render test uses), emitted to a temp dir, and run through the real CLI with
--json. The report object is extracted from stderr (warnings may precede it)
and compared byte-for-byte to the tracked fixture. The write path uses
atomic replacement and never touches the source tree in check mode.
"""

from __future__ import annotations

import argparse
import difflib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CONFLICTS = Path(__file__).resolve().parent

CORPUS = ("shift_reduce", "dangling_else", "reduce_reduce")


def cli_version() -> str:
    try:
        out = subprocess.run(["tree-sitter", "--version"],
                             capture_output=True, text=True)
        return (out.stdout or out.stderr).strip()
    except FileNotFoundError:
        return "(tree-sitter not on PATH)"


def _extract_report(raw: str) -> str | None:
    """The CLI's JSON conflict report out of stderr (warnings may land
    ahead of it — the same extraction the library uses, B7)."""
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]
    return None


def _shift_reduce(tg, g):
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("expr", tg.choice(
        tg.seq(tg.ref("expr"), "+", tg.ref("expr")),
        tg.ref("number")))
    g.rule("source_file", tg.repeat(tg.ref("expr")))
    g.start("source_file")


def _dangling_else(tg, g):
    g.rule("ident", tg.pattern(r"[a-z]+"))
    g.rule("if_stmt", tg.seq("if", tg.ref("expr"), "then", tg.ref("stmt")))
    g.rule("if_else", tg.seq(
        "if", tg.ref("expr"), "then", tg.ref("stmt"), "else", tg.ref("stmt")))
    g.rule("stmt", tg.choice(
        tg.ref("if_stmt"), tg.ref("if_else"), tg.ref("assign")))
    g.rule("assign", tg.seq(tg.ref("ident"), "=", tg.ref("expr")))
    g.rule("expr", tg.ref("ident"))
    g.rule("source_file", tg.repeat(tg.ref("stmt")))
    g.start("source_file")


def _reduce_reduce(tg, g):
    g.rule("a", "x")
    g.rule("b", "x")
    g.rule("s", tg.choice(tg.ref("a"), tg.ref("b")))
    g.rule("source_file", tg.repeat(tg.ref("s")))
    g.start("source_file")


_BUILDERS = {
    "shift_reduce": _shift_reduce,
    "dangling_else": _dangling_else,
    "reduce_reduce": _reduce_reduce,
}


def generate_report(name: str, tmp: Path) -> str:
    """Run the real CLI over the minimal grammar and return the report text
    (the JSON object + trailing newline, the fixture's exact format)."""
    import pydantree_sitter_grammar as tg

    g = tg.Grammar(name)
    _BUILDERS[name](tg, g)
    json_path = g.emit_bundle(tmp / name)
    proc = tg.run_generate(json_path)
    assert proc.returncode != 0, (
        f"{name}: expected the CLI to fail on the conflict, got 0")
    report = _extract_report(proc.stderr)
    assert report is not None, (
        f"{name}: no conflict report in CLI stderr:\n{proc.stderr}")
    return report + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*",
                        help="corpus names to check/write (default: all)")
    parser.add_argument("--write", action="store_true",
                        help="replace tracked fixtures that differ (atomic)")
    args = parser.parse_args(argv)

    names = args.names or list(CORPUS)
    unknown = [n for n in names if n not in CORPUS]
    if unknown:
        parser.error(f"unknown corpus name(s): {unknown}")

    print(f"tree-sitter CLI: {cli_version()}")
    print(f"mode: {'WRITE (atomic replacement)' if args.write else 'check only'}")
    print()

    rc = 0
    with tempfile.TemporaryDirectory(prefix="pydantree-conflicts-") as td:
        tmp = Path(td)
        for name in names:
            fresh = generate_report(name, tmp)
            target = CONFLICTS / f"{name}_stderr.json"
            tracked = target.read_text()
            if fresh == tracked:
                print(f"  {target.name}: unchanged")
                continue
            rc = 1
            print(f"  {target.name}: DIFFERS")
            print("\n".join(difflib.unified_diff(
                tracked.splitlines(), fresh.splitlines(),
                fromfile=f"{target.name} (tracked)",
                tofile=f"{target.name} (fresh CLI stderr)",
                lineterm="")))
            if args.write:
                fd, tmp_path = tempfile.mkstemp(
                    dir=str(target.parent), prefix=".conflict-", suffix=".tmp")
                try:
                    with os.fdopen(fd, "w") as fh:
                        fh.write(fresh)
                    os.replace(tmp_path, target)
                except BaseException:
                    try:
                        os.unlink(tmp_path)
                    except FileNotFoundError:
                        pass
                    raise
                print(f"    -> replaced {target}")
            else:
                print("    -> run with --write to replace the tracked file")

    print()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
