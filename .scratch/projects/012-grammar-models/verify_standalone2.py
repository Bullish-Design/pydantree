"""Verify the standalone v2 hypothetical (`devenv_grammar_classes2.py`) — the
subclass + pattern-helper surface — produces the SAME grammar.json as the
current builder-DSL `examples/devenv-subset/grammar.py`, by executing it
against probe 2's machinery (the real library would export these)."""

import json
import sys
import types
from pathlib import Path
from typing import Literal

import pydantree_sitter_grammar as tg

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "examples" / "devenv-subset"))

import probe_class_surface2 as P  # noqa: E402
from grammar import build as original_build  # noqa: E402

src = (HERE / "devenv_grammar_classes2.py").read_text()
for line in (
    "import pydantree_sitter_grammar as tg\n",
    "from pydantree_sitter_grammar import (\n    External, Extra, Pattern, R, Rule, "
    "Supertype, Token, assemble,\n)\n",
    "from pydantree_sitter_grammar.patterns import dotted_path, integer, path_literal, "
    "rest_of_line\n",
):
    src = src.replace(line, "")

P._REGISTRY.clear()  # fresh registry: only the standalone file's classes
_mod = types.ModuleType("standalone2")
_mod.__dict__.update({
    "pydantree_sitter_grammar": tg, "tg": tg,
    "R": P.R, "Rule": P.Rule, "assemble": P.assemble,
    "Pattern": P.Pattern, "Token": P.Token, "External": P.External,
    "Extra": P.Extra, "Supertype": P.Supertype,
    "Literal": Literal,
    "dotted_path": P.dotted_path, "integer": P.integer,
    "path_literal": P.path_literal, "rest_of_line": P.rest_of_line,
})
sys.modules["standalone2"] = _mod
exec(compile(src, "devenv_grammar_classes2.py", "exec"), _mod.__dict__)  # noqa: S102

g_new = _mod.build()
new_json = json.loads(g_new.build().model_dump_json(exclude_none=True))
old_json = json.loads(original_build().build().model_dump_json(exclude_none=True))

print(f"standalone v2 class-file grammar.json identical: {new_json == old_json}")
print(f"rule count: {len(g_new.rules)}  checks clean: {not tg.errors(g_new)}")
assert new_json == old_json and not tg.errors(g_new)
