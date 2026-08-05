#!/usr/bin/env python3
"""bash-extract — extract typed rows from shell scripts with pydantree.

A copyable end-to-end over the REAL tree-sitter-bash grammar (0.25.1):
function definitions, top-level variable assignments, and heredoc usage —
as typed rows, with the schema checks active BEFORE any text is parsed.

Usage — inside the repository (the supported developer path):

    devenv shell -- python -m pytest tests/test_oracles.py -q

the suite builds a fresh bundle from tests/fixtures/bash and compares the
saved oracle JSON plus the example's hand-written ground truth; or build a
bundle yourself and run the script directly:

    devenv shell -- python -c \
      'from pydantree_sitter_grammar.schema_tool import build_community_bundle; build_community_bundle("tests/fixtures/bash", "/tmp/pydantree-example-bash", name="bash")'
    devenv shell -- python examples/bash-extract/extract.py \
      --bundle /tmp/pydantree-example-bash

Usage — standalone (consumer documentation, NOT the repo workflow):

    uv venv --python 3.13 .venv
    uv pip install --python .venv/bin/python \
        pydantree-sitter tree-sitter-bash
    .venv/bin/python extract.py

The models below are the whole query: each `__match__` ancestor path plus
the captures declare both the pattern and the output type. The schema
(`node-schema.json`, derived from the grammar SOURCE v0.25.1) is bound to
the language so `validate_with` runs the model↔grammar and capture↔type
checks before parsing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

from pydantree_sitter import Language, M, OutputModel, capture, capture_kind, source_meta


class FunctionDef(OutputModel):
    """Function definitions (both `foo() { … }` and `function foo { … }`) at
    the top level: the `name` CST field + the definition's line."""

    __match__ = M("program", "function_definition")
    name: str = capture("name")
    line: int = source_meta()


class Assignment(OutputModel):
    """Top-level variable assignments only (name + raw value text). The
    direct-child path (program → variable_assignment) naturally excludes
    `export VAR=…` (wrapped by declaration_command) and function bodies."""

    __match__ = M("program", "variable_assignment")
    name: str = capture("name")
    value: str = capture("value")
    line: int = source_meta()


class Heredoc(OutputModel):
    """Heredoc usage: heredoc_redirect has POSITIONAL children (no CST
    fields), so `capture_kind` binds the delimiter (heredoc_start), the
    body (heredoc_body) and the closing delimiter (heredoc_end). The
    optional `descriptor` field is a field-mode capture (None for plain
    `<<EOF`; "3" for `3<<EOF`). NOTE: field order must match the CST child
    order when mixing a field with positional children (descriptor precedes
    the heredoc trio)."""

    __match__ = M("program", "redirected_statement", "heredoc_redirect")
    descriptor: str | None = capture("descriptor")
    start: str = capture_kind("heredoc_start")
    body: str = capture_kind("heredoc_body")
    end: str | None = capture_kind("heredoc_end")
    line: int = source_meta()


def load_language() -> Language:
    """Default: the wheel shape — tree_sitter_bash.language() with the
    derived schema bound explicitly (the schema ships in this dir). With
    `--bundle <dir>`: the one-line bundle shape."""
    if "--bundle" in sys.argv:
        return Language.load_bundle(sys.argv[sys.argv.index("--bundle") + 1])
    import tree_sitter_bash
    return Language.load(tree_sitter_bash.language(),
                         schema=str(HERE / "node-schema.json"))


def main() -> int:
    lang = load_language()
    # the checks run BEFORE any text is parsed
    for model in (FunctionDef, Assignment, Heredoc):
        model.validate_with(lang)

    print(f"schema: {len(lang.schema.kinds())} kinds · checks active\n")
    total = 0
    for fname in ("sample.sh", "real_script.sh", "unclosed.sh"):
        src = (HERE / fname).read_text()
        print(f"── {fname} ──")
        for label, model in (("functions", FunctionDef),
                             ("assignments", Assignment),
                             ("heredocs", Heredoc)):
            rows = model.extract(src, language=lang)
            total += len(rows)
            print(f"  {label} ({len(rows)}):")
            for r in rows:
                print("    ", r.model_dump())
        print()

    # self-check: the rows must match the hand-written ground truth
    truth = json.loads((HERE / "ground_truth.json").read_text())
    ok = True
    for fname in ("sample.sh", "real_script.sh", "unclosed.sh"):
        for label, model in (("functions", FunctionDef),
                             ("assignments", Assignment),
                             ("heredocs", Heredoc)):
            rows = [r.model_dump() for r in
                    model.extract((HERE / fname).read_text(), language=lang)]
            if rows != truth[fname][label]:
                ok = False
                print(f"  MISMATCH in {fname}.{label}")
    print(f"{total} rows extracted — "
          + ("all match the hand-written ground truth ✓" if ok
             else "mismatch (see above) ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
