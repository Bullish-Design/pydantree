"""Phase 8 — the bash real-user consumer (shared by every run shape).

One consumer, three run shapes (byte-identical outputs):

  * in-repo bundle shape   — B importable (BFREE_REQUIRED unset)
  * fresh-venv bundle shape — B-free (Language.load_bundle over the bundle)
  * fresh-venv WHEEL shape  — B-free (tree_sitter_bash.language() + the
                              derived schema bound explicitly) — the true
                              "hundreds of grammars" shape

The extraction task (hand truth in ground_truth.json, written BEFORE the
models): function definitions (both `foo() {}` and `function foo {}` forms,
plus the optional `redirect` field), top-level variable assignments (name +
value, no export/prefixes — the direct-child path excludes those naturally),
and heredoc usage (delimiter + body; heredoc_redirect has POSITIONAL
children, so capture_kind is the surface).

Usage: python consumer_bash.py <corpus-dir> <bundle|wheel> <bundle-or-schema-dir>
Env: BFREE_REQUIRED=1 asserts pydantree_sitter_grammar is genuinely unimportable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if os.environ.get("BFREE_REQUIRED"):
    try:
        import pydantree_sitter_grammar  # noqa: F401
        print(json.dumps({"ok": False,
                          "error": "pydantree_sitter_grammar IS importable — B leaked"}))
        sys.exit(1)
    except ModuleNotFoundError:
        pass

from pydantree_sitter import Language, M, OutputModel, capture, capture_kind, source_meta  # noqa: E402

CORPUS = Path(sys.argv[1])
MODE = sys.argv[2]
ARTIFACT = Path(sys.argv[3])


class FunctionDef(OutputModel):
    """Function definitions at the top level (both `foo() {…}` and
    `function foo {…}` are the same node kind)."""

    __match__ = M("program", "function_definition")
    name: str = capture("name")
    line: int = source_meta()


class Assignment(OutputModel):
    """Top-level variable assignments only: the direct-child path
    (program (variable_assignment …)) naturally excludes export-wrapped
    assignments (they nest under declaration_command) and function bodies.
    `value` is the raw node text (string quotes included — bash keeps them
    in the CST)."""

    __match__ = M("program", "variable_assignment")
    name: str = capture("name")
    value: str = capture("value")
    line: int = source_meta()


class Heredoc(OutputModel):
    """Heredoc usage: heredoc_redirect has POSITIONAL children (no CST
    fields) — `capture_kind` binds the delimiter (heredoc_start), the body
    (heredoc_body), and the closing delimiter (heredoc_end). `descriptor`
    and `end` are the optional-capture exercise over bash: the descriptor
    field is absent for plain `<<EOF` (None), and an unclosed heredoc at EOF
    yields a MISSING heredoc_end (captured as ""). NOTE: field order must
    match the CST child order when mixing a field with positional children
    (descriptor precedes the heredoc trio — a wrong order is an "Impossible
    pattern" QueryError). heredoc_start's text keeps the quotes for
    `<<'TAG'`; heredoc_end's is always the clean word."""

    __match__ = M("program", "redirected_statement", "heredoc_redirect")
    descriptor: str | None = capture("descriptor")
    start: str = capture_kind("heredoc_start")
    body: str = capture_kind("heredoc_body")
    end: str | None = capture_kind("heredoc_end")
    line: int = source_meta()


def load_language():
    if MODE == "bundle":
        return Language.load_bundle(str(ARTIFACT))
    if MODE == "wheel":
        import tree_sitter_bash
        schema = ARTIFACT / "node-schema.json"
        return Language.load(tree_sitter_bash.language(), schema=str(schema))
    raise SystemExit(f"unknown mode: {MODE}")


def main() -> int:
    lang = load_language()
    # the checks run BEFORE any text is parsed (Job 1/3/4 over the bound
    # schema — a bad field/path fails here, not after parsing)
    FunctionDef.validate_with(lang)
    Assignment.validate_with(lang)
    Heredoc.validate_with(lang)

    def rows(model, src):
        return [r.model_dump() for r in model.extract(src, language=lang)]

    out = {
        "ok": None,  # filled below
        "mode": MODE,
        "pydantree_sitter_grammar_importable": _b_importable(),
        "schema_bound": lang.schema is not None,
        "schema_kinds": len(lang.schema.kinds()) if lang.schema else None,
        "files": {},
    }
    truth = json.loads((CORPUS / "ground_truth.json").read_text())
    all_ok = True
    for fname in ("sample.sh", "real_script.sh", "unclosed.sh"):
        src = (CORPUS / fname).read_text()
        fns = rows(FunctionDef, src)
        assigns = rows(Assignment, src)
        here = rows(Heredoc, src)
        out["files"][fname] = {
            "functions": fns,
            "assignments": assigns,
            "heredocs": here,
        }
        t = truth[fname]
        all_ok = all_ok and fns == t["functions"] and assigns == t["assignments"] \
            and here == t["heredocs"]
    out["ok"] = all_ok
    print(json.dumps(out, indent=2))
    return 0 if all_ok else 1


def _b_importable() -> bool:
    try:
        import pydantree_sitter_grammar  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False


if __name__ == "__main__":
    sys.exit(main())
