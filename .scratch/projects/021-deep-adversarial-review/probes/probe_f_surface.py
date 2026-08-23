"""Probe F — public-surface consistency + B odds and ends."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))

import pydantree_sitter as A  # noqa: E402
import pydantree_sitter_grammar as Bm  # noqa: E402


def hr(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


hr("F1 — names in __all__ that the module does not define")
for mod in (A, Bm):
    missing = [n for n in mod.__all__ if not hasattr(mod, n)]
    print(f"{mod.__name__}: __all__ has {len(mod.__all__)} names; missing: {missing}")

hr("F2 — documented public API that is NOT exported")
import pydantree_sitter_grammar.pipeline as P  # noqa: E402
import pydantree_sitter_grammar.schema_tool as ST  # noqa: E402
for name in ("write_bundle", "build_from_source_dir", "Toolchain"):
    print(f"  pipeline.{name}: in package namespace? {hasattr(Bm, name)}")
for name in ("derive_schema_for_dir", "build_community_bundle"):
    print(f"  schema_tool.{name}: in package namespace? {hasattr(Bm, name)}")

hr("F3 — bundle_format: what actually differs between 1 and 2?")
import subprocess  # noqa: E402
out = subprocess.run(
    ["grep", "-rn", "bundle_format", "-r", str(REPO / "src"), str(REPO / "tests"),
     str(REPO / "docs")], capture_output=True, text=True)
print(out.stdout)

hr("F4 — rule-class External: what body does the rule get?")
from pydantree_sitter_grammar import External, Rule, assemble  # noqa: E402
import types as _t  # noqa: E402

mod = _t.ModuleType("g_probe_f")
sys.modules["g_probe_f"] = mod
src = '''
from __future__ import annotations
import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar import External, Rule

class Newline(External):
    pass

class Stmt(Rule):
    body: Newline

class SourceFile(Rule):
    content: list[Stmt]
'''
exec(compile(src, "g_probe_f", "exec"), mod.__dict__)
g = assemble("probe", start=mod.SourceFile,
             rules=[mod.Newline, mod.Stmt, mod.SourceFile])
m = g.build()
print("externals:", [e.model_dump() for e in m.externals])
print("rule 'newline':", m.rules["newline"].model_dump())
print("rule 'stmt':", m.rules["stmt"].model_dump())

hr("F5 — _snake / class_name are duplicated, not shared")
from pydantree_sitter_grammar.rules import _snake  # noqa: E402
from pydantree_sitter.codegen import class_name  # noqa: E402
for n in ("HTTPServer", "JSONValue", "IOPort", "_Type", "ABC"):
    s = _snake(n)
    print(f"  {n!r} -> _snake {s!r} -> class_name {class_name(s)!r} "
          f"{'ROUND-TRIP OK' if class_name(s) == n else 'NOT a round trip'}")

hr("F6 — Ladder int mode: prec values are positional, silently renumbered")
g2 = Bm.Grammar("lad")
lad = g2.precedence("add", "mul")
print("add =", lad.n("add"), "mul =", lad.n("mul"))
lad.insert("cmp", before="add")
print("after insert('cmp', before='add'): add =", lad.n("add"),
      "mul =", lad.n("mul"), " (values of already-emitted prec() calls changed)")

hr("F7 — Grammar.build() injects a `\\s` extra even when extras are named rules")
g3 = Bm.Grammar("ws")
g3.rule("source_file", Bm.repeat(Bm.ref("w")))
g3.rule("w", Bm.pattern(r"[a-z]+"))
g3.rule("ws_rule", Bm.pattern(r"[ \t\n]+"))
g3.extra(Bm.ref("ws_rule"))
g3.start("source_file")
print("extras:", [e.model_dump() for e in g3.build().extras])
