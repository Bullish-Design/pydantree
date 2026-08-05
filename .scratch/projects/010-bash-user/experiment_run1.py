#!/usr/bin/env python3
"""
Phase 8 — Run 1: the grammar-ownership seam over tree-sitter-bash 0.25.1.

A grammar we DON'T own, acquired exactly like rust (Phase 6) and never
touched by us:

  1. acquisition honesty: the PyPI sdist ships only the COMPILED parser.c +
     scanner.c, so the SOURCE (grammar.json + scanner.c + tree_sitter/
     headers) comes from the GitHub tag v0.25.1 — vendored under
     tests/fixtures/bash/ (hermetic), with the repo's own checked-in
     src/node-types.json as the ORACLE;
  2. derive_schema_for_dir over the fixture — byte-for-byte vs the CLI's
     FRESH node-types.json (the tool's contract: the CLI's own byproduct);
  3. the vendored oracle vs our CLI 0.25.3's fresh output — any delta is
     upstream CLI churn, not our derivation (like rust's 38-byte delta);
  4. note what the big multi-context scanner + ~30 externals mean for the
     schema (named externals, hidden rules, supertypes).

Evidence saved verbatim under evidence/ (r8_r1_*).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

EVIDENCE = Path(__file__).parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

BASH_FIXTURE = ROOT / "tests" / "fixtures" / "bash"


def banner(t: str, width: int = 72) -> None:
    print("\n" + "=" * width + f"\n{t}\n" + "=" * width)


def save(name: str, text: str) -> None:
    (EVIDENCE / name).write_text(text)


def main() -> int:
    banner("Run 1 — the grammar-ownership seam over tree-sitter-bash 0.25.1")

    # 0. acquisition facts
    banner("0. acquisition")
    gm = json.loads((BASH_FIXTURE / "grammar.json").read_text())
    externals = gm["externals"]
    n_ext = len(externals)
    ext_names = [e.get("name", e.get("value")) for e in externals]
    rules = gm["rules"]
    n_hidden = sum(1 for k in rules if k.startswith("_"))
    print(f"grammar name: {gm['name']!r}; rules: {len(rules)} "
          f"({n_hidden} hidden); externals: {n_ext}")
    print("externals:", ", ".join(str(e) for e in ext_names))
    save("r8_r1_acquisition.txt",
         f"source: GitHub tag v0.25.1 (tree-sitter/tree-sitter-bash) — "
         f"the PyPI sdist ships only compiled parser.c/scanner.c\n"
         f"rules: {len(rules)} ({n_hidden} hidden); externals: {n_ext}\n"
         f"externals: {', '.join(str(e) for e in ext_names)}\n"
         f"word: {gm.get('word')!r}\n")

    # 1. the schema tool over the real source (the tool's contract)
    banner("1. schema tool -> byte-for-byte vs the CLI's fresh node-types.json")
    from tsgrammar.schema_tool import derive_schema_for_dir
    tmp = Path(tempfile.mkdtemp(prefix="phase8-r1-"))
    schema_out = tmp / "bash-schema.json"
    derived = derive_schema_for_dir(BASH_FIXTURE, name="bash",
                                    workdir=tmp / "cw", out=schema_out,
                                    keep=True)
    fresh_cli = (tmp / "cw" / "gen" / "node-types.json").read_text()
    ours = schema_out.read_text()
    kinds = derived.kinds()
    named_kinds = [k for k in kinds if k.isalpha() or "_" in k]
    print(f"kinds: {len(kinds)}; byte-for-byte vs the CLI's FRESH "
          f"node-types.json: {ours == fresh_cli}")
    save("r8_r1_schema_tool_agreement.txt",
         f"kinds: {len(kinds)}\nbyte-for-byte vs the CLI's fresh "
         f"node-types.json: {ours == fresh_cli}\n")

    # 2. the vendored oracle (a NEWER CLI) vs our CLI 0.25.3 — upstream churn
    banner("2. vendored oracle vs our CLI 0.25.3 (upstream churn check)")
    oracle = (BASH_FIXTURE / "node-types.json").read_text()
    delta = abs(len(oracle) - len(fresh_cli))
    print(f"oracle: {len(oracle)} bytes; CLI 0.25.3 fresh: {len(fresh_cli)} "
          f"bytes — {delta}-byte delta (upstream CLI churn, like rust's 38)")
    save("r8_r1_oracle_delta.txt",
         f"vendored oracle (checked-in node-types.json): {len(oracle)} bytes\n"
         f"CLI 0.25.3 fresh node-types.json: {len(fresh_cli)} bytes\n"
         f"delta: {delta} bytes — upstream CLI churn, not our derivation\n")

    # 3. the schema shape over bash: named externals, hidden rules, supertypes
    banner("3. what the schema looks like over bash's shape")
    schema = json.loads(ours)
    named = [e for e in schema if e.get("named")]
    anon = [e for e in schema if not e.get("named")]
    supertypes = [e["type"] for e in schema if e.get("subtypes")]
    hidden_in_schema = [e["type"] for e in named if e["type"].startswith("_")]
    print(f"named kinds: {len(named)}; anonymous kinds: {len(anon)}")
    print(f"supertypes: {supertypes}")
    print(f"hidden (_) kinds in the schema: {hidden_in_schema}")
    # the external-derived named kinds present in the schema
    ext_named = [n for n in ext_names
                 if any(e["type"] == n and e.get("named") for e in schema)]
    ext_anon = [n for n in ext_names
                if any(e["type"] == n and not e.get("named") for e in schema)]
    ext_missing = [n for n in ext_names
                   if not any(e["type"] == n for e in schema)]
    print(f"externals present as NAMED kinds: {ext_named}")
    print(f"externals present as ANON kinds: {ext_anon}")
    print(f"externals NOT in node-types.json: {ext_missing}")
    save("r8_r1_schema_shape.txt",
         f"named kinds: {len(named)}; anonymous kinds: {len(anon)}\n"
         f"supertypes: {supertypes}\n"
         f"hidden (_) kinds in the schema: {hidden_in_schema}\n"
         f"externals as named kinds: {ext_named}\n"
         f"externals as anon kinds: {ext_anon}\n"
         f"externals absent from node-types.json: {ext_missing}\n"
         f"kinds: {sorted(kinds)}\n")

    ok = ours == fresh_cli
    banner("VERDICT")
    print("Run 1:", "GO — the schema tool is byte-for-byte with the CLI's "
          "fresh node-types.json over bash (29 externals, multi-context "
          "scanner)" if ok else "NO-GO")
    save("r8_r1_verdict.txt", f"verdict: {'GO' if ok else 'NO-GO'}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
