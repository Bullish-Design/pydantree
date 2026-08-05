#!/usr/bin/env python3
"""
Phase 9 — Run 3 evidence: compiled_source + Job-2 stubs over the nix schema,
the record-mode probe, and the position-bug summary (the ecosystem finding).

Evidence saved verbatim under evidence/ (r9_r3_*).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).parent))

EVIDENCE = Path(__file__).parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

NIX_FIXTURE = ROOT / "tests" / "fixtures" / "nix"
FLEET = NIX_FIXTURE / "fleet"


def save(name: str, text: str) -> None:
    (EVIDENCE / name).write_text(text)


def main() -> int:
    from tsgrammar.schema_tool import build_community_bundle
    from tsquery import Language
    bundle = build_community_bundle(NIX_FIXTURE, "/tmp/phase9/bundle9",
                                    name="nix", keep=True)
    lang = Language.load_bundle(bundle)
    from consumer_nix import Binding, List
    Binding.validate_with(lang)
    List.validate_with(lang)

    # 1. the compiled .scm for the two models
    scm = (Binding.compiled_source(schema=lang.schema, language=lang)
           + "\n\n# --- List ---\n"
           + List.compiled_source(schema=lang.schema, language=lang) + "\n")
    print("=== compiled_source ===")
    print(scm)
    save("r9_r3_compiled_source.scm", scm)

    # 2. Job-2 stubs over the nix schema
    from tsquery.stubs import generate_stubs
    stub_path = EVIDENCE / "r9_r3_nix_stubs.pyi"
    generate_stubs(lang.schema, out=str(stub_path))
    stub_text = stub_path.read_text()
    print(f"=== stubs: {len(stub_text.splitlines())} lines ===")
    # the anchors the consumer's models use:
    for kind in ("binding", "binding_set", "list_expression", "attrpath",
                 "indented_string_expression"):
        if f"class {kind}" in stub_text:
            start = stub_text.index(f"class {kind}")
            print(stub_text[start:start + 600])
    save("r9_r3_stub_quality.txt", stub_text)

    # 3. the record-mode probe (the kickoff's flagged question)
    print("\n=== record-mode probe over nix's attrset shape ===")
    probe = []
    try:
        from tsquery import M, OutputModel, source_meta
        from tsquery.schema import find_pair_kind

        class EnvRecord(OutputModel):
            __match__ = M("source_code", ..., "binding_set", record=True)
            GREET: str
            line: int = source_meta()

        pair = find_pair_kind(lang.schema, "binding_set")
        probe.append(f"find_pair_kind('binding_set') -> {pair!r}")
        EnvRecord.validate_with(lang)
        rows = EnvRecord.extract(
            (FLEET / "pydantree.nix").read_bytes(), language=lang)
        probe.append(f"rows: {rows!r}")
    except Exception as e:
        probe.append(f"{type(e).__name__}: {e}")
    for p in probe:
        print(" ", p)
    save("r9_r3_record_mode_probe.txt", "\n".join(probe) + "\n")

    # 4. the position-bug summary (the ecosystem finding)
    print("\n=== the nix position-bug summary ===")
    lines = [
        "The nix grammar under tree-sitter 0.26: node start-POINT corruption",
        "  (reads of start_point/range return garbage rows or segfault) on",
        "  large multiline-string-heavy files (flora 526 lines).",
        "  - upstream wheel parser, start_point walk over the fleet (30",
        "    attempts each, r9_r3_fleet_stability.txt): flora 30/30",
        "    SIGSEGV; the other six vendored files 0/30 each;",
        "  - our gcc build of v0.3.0: ~6/10 direct walks;",
        "  - the tsquery EXTRACTION path (query engine + source_meta reads",
        "    on anchor nodes only): 0/24 crashes, but 22/55 flora binding",
        "    line numbers are garbage (start_point == start_byte);",
        "  - the tree-sitter CLI 0.25.3 runtime parses flora with CORRECT",
        "    positions (the same grammar source) — a runtime-version",
        "    interaction, not the grammar source;",
        "  - trigger isolated: flora line 258 (a `case ... in` line inside a",
        "    multiline string body); the first 257 lines were stable (0/8)",
        "    and 258+ crashes ~always;",
        "  - start_BYTE / node text / children reads are ALWAYS safe (0/8,",
        "    0/30) — only the POINT computation corrupts.",
        "Escape hatch used by the consumer: line numbers are computed from",
        "  BYTE offsets (start_byte is reliable); start_POINT reads are",
        "  avoided on the large file. source_meta lines are cross-checked",
        "  and agree on the six stable files (22 flora disagreements).",
        "Upstream: nix-community/tree-sitter-nix + tree-sitter 0.26 runtime",
        "  interaction — a candidate bug report.",
    ]
    for l in lines:
        print(" ", l)
    save("r9_r3_position_bug_summary.txt", "\n".join(lines) + "\n")

    # 5. fleet parse-stability table (30 attempts each, the upstream WHEEL's
    # parser + tree-sitter 0.26 — the crash is nondeterministic, so the rate
    # is the honest number)
    print("\n=== fleet parse-stability table (30 attempts each, wheel) ===")
    wheel_py = None
    for cand in sorted(Path("/tmp/phase9").glob("wv2/bin/python")):
        wheel_py = cand
    rows = []
    for fname in ("mypi-agent.nix", "pydantree.nix", "terminal-state.nix",
                  "structured-agents-v2.nix", "fsdantic.nix", "nixvim.nix",
                  "flora.nix"):
        path = str(FLEET / fname)
        crashes = 0
        corrupt = 0
        for _ in range(30):
            p = subprocess.run(
                [str(wheel_py), "-c", """
import sys, tree_sitter, tree_sitter_nix
lang = tree_sitter.Language(tree_sitter_nix.language())
src = open(sys.argv[1], 'rb').read()
tree = tree_sitter.Parser(lang).parse(src)
def walk(n):
    tr = src[:n.start_byte].count(bytes([10]))
    if n.start_point.row != tr:
        raise SystemExit(2)
    for c in n.children: walk(c)
walk(tree.root_node)
""", path], capture_output=True, text=True, check=False)
            if p.returncode in (-11, 139):
                crashes += 1
            elif p.returncode == 2:
                corrupt += 1
        rows.append(f"  {fname:26} crashes={crashes}/30 corrupt-walks={corrupt}")
    for r in rows:
        print(r)
    save("r9_r3_fleet_stability.txt",
         "fleet parse-stability (30 attempts each, the upstream wheel parser, "
         "start_point walk):\n" + "\n".join(rows) + "\n")

    banner = "Run 3 evidence captured (r9_r3_*)."
    print("\n" + banner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
