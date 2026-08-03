"""Phase-4 dev helper: the derive_from_ir <-> CLI node-types.json agreement
check (cheap check #2 from the kickoff). Not a test; run ad-hoc:

    devenv shell -- python .scratch/006-tsquery-bridge/dev_agreement.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / ".scratch" / "006-tsquery-bridge"))
sys.path.insert(0, str(ROOT / ".scratch" / "005-tsgrammar-glr"))

import tsgrammar as tg  # noqa: E402
from tscore.schema import derive_from_ir  # noqa: E402


def norm(types):
    out = {}
    for t in types:
        f = {k: (v["multiple"], v["required"], tuple(sorted((r["type"], r["named"]) for r in v["types"])))
             for k, v in t.get("fields", {}).items()}
        ch = (t["children"]["multiple"], t["children"]["required"],
              tuple(sorted((r["type"], r["named"]) for r in t["children"]["types"]))) \
            if t.get("children") else None
        subs = tuple(sorted((r["type"], r["named"]) for r in t["subtypes"])) \
            if t.get("subtypes") else None
        out[t["type"]] = (t["named"], t.get("root", False), t.get("extra", False), f, ch, subs)
    return out


def agree(model, label: str, *, verbose: bool = True) -> int:
    res = tg.build(model)
    cli = json.loads(res.node_types_json.read_text())
    mine = [t.model_dump(exclude_none=True) for t in derive_from_ir(model)]
    a, b = norm(cli), norm(mine)
    diffs = [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    print(f"{label}: {len(a)} cli vs {len(b)} mine kinds, diffs: {len(diffs)}")
    for k in diffs[:8]:
        x, y = a.get(k), b.get(k)
        print(f"  KIND {k}\n    cli:  {json.dumps(x) if x else 'ABSENT'}\n    mine: {json.dumps(y) if y else 'ABSENT'}")
    return len(diffs)


def probe_json_like():
    g = tg.Grammar("probe_json")
    g.rule("string_content", tg.token(tg.pattern(r'[^"\\]+')))
    g.rule("escape_sequence", tg.token(tg.seq("\\", tg.pattern(r'("|\\|n)'))))
    g.rule("string", tg.seq('"', tg.repeat(tg.choice(tg.ref("string_content"),
                                                     tg.ref("escape_sequence"))), '"'))
    g.rule("true", "true")
    g.rule("false", "false")
    g.rule("number", tg.token(tg.pattern(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")))
    g.rule("value", tg.choice(tg.ref("string"), tg.ref("true"), tg.ref("false"),
                              tg.ref("number")), supertype=True)
    g.rule("pair", tg.seq(tg.field("key", tg.ref("string")), ":",
                          tg.field("value", tg.ref("value"))))
    g.rule("array", tg.seq("[", tg.repeat(tg.ref("value")), tg.opt(","), "]"))
    g.rule("source_file", tg.repeat(tg.choice(tg.ref("pair"), tg.ref("array"))))
    g.start("source_file")
    return agree(g.build(), "probe_json_like")


def probe_qfilter():
    import qfilter
    return agree(qfilter.build().build(), "qfilter")


if __name__ == "__main__":
    total = 0
    total += probe_json_like()
    total += probe_qfilter()
    print(f"\nTOTAL DIFFS: {total}")
