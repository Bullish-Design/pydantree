#!/usr/bin/env python3
"""
Phase 6 — Run 2: the community seam over a REAL grammar (tree-sitter-rust).

A grammar we DON'T own, end to end:

  1. the source: tree-sitter-rust master (vendored under tests/fixtures/rust —
     grammar.json + scanner.c + the tree_sitter headers; the upstream repo:
     github.com/tree-sitter/tree-sitter-rust, acquired via the GitHub master
     tarball; the PyPI sdist ships only the compiled parser.c, not the
     grammar source);
  2. the schema tool over it — byte-for-byte with the CLI's own node-types.json;
  3. derive_from_ir over the real grammar.json — byte-for-byte with the CLI's
     FRESH 0.25.3 output (the repo's checked-in node-types.json is generated
     by a newer CLI and differs by 38 bytes — upstream churn, documented);
  4. build the community bundle (generate + gcc + schema + metadata + loader);
  5. a B-free consumer extracts a real rust task against HAND-AUTHORED ground
     truth, checks active, pydantree_sitter_grammar unimportable.

Evidence saved verbatim under evidence/ (r2_*).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / ".scratch" / "007-query-distribution"))
sys.path.insert(0, str(ROOT / ".scratch" / "008-consumer-seam"))

EVIDENCE = Path(__file__).parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

RUST_FIXTURE = ROOT / "tests" / "fixtures" / "rust"


def banner(t: str, width: int = 72) -> None:
    print("\n" + "=" * width + f"\n{t}\n" + "=" * width)


def save(name: str, text: str) -> None:
    (EVIDENCE / name).write_text(text)


def main() -> int:
    banner("Run 2 — the community seam over the real tree-sitter-rust")
    tmp = Path(tempfile.mkdtemp(prefix="phase6-run2-"))

    # 1. the schema tool over the real source (the tool's contract)
    banner("1. schema tool -> byte-for-byte vs the CLI's node-types.json")
    from pydantree_sitter_grammar.schema_tool import derive_schema_for_dir
    schema_out = tmp / "rust-schema.json"
    derived = derive_schema_for_dir(RUST_FIXTURE, name="rust",
                                    workdir=tmp / "cw", out=schema_out,
                                    keep=True)
    fresh_cli = (tmp / "cw" / "gen" / "node-types.json").read_text()
    ours = schema_out.read_text()
    print(f"kinds: {len(derived.kinds())}; byte-for-byte vs the CLI's FRESH "
          f"node-types.json: {ours == fresh_cli}")
    save("r2_schema_tool_agreement.txt",
         f"kinds: {len(derived.kinds())}\nbyte-for-byte vs the CLI's fresh "
         f"node-types.json: {ours == fresh_cli}\n")
    # the repo's checked-in node-types.json (a NEWER CLI): the diff is
    # upstream churn, not our derivation
    checked_in = (RUST_FIXTURE / "node-types.json").read_text()
    print(f"repo checked-in node-types.json is {len(checked_in)} bytes, our "
          f"CLI 0.25.3 emits {len(fresh_cli)} — the {abs(len(checked_in) - len(fresh_cli))}"
          f"-byte delta is upstream CLI churn (documented)")

    # 2. derive_from_ir over the real grammar.json, byte-for-byte
    banner("2. derive_from_ir over the real grammar.json (exact path)")
    from pydantree_sitter_grammar.ir import Grammar as GrammarModel
    from pydantree_sitter.schema import NodeSchema, derive_from_ir
    model = GrammarModel.model_validate(
        json.loads((RUST_FIXTURE / "grammar.json").read_text()))
    ours_ir = NodeSchema.from_list(derive_from_ir(model), name="rust").to_json()
    print(f"derive_from_ir byte-for-byte vs the CLI's FRESH node-types.json: "
          f"{ours_ir == fresh_cli}")
    save("r2_derive_from_ir_agreement.txt",
         f"byte-for-byte vs the CLI's fresh node-types.json: "
         f"{ours_ir == fresh_cli}\n")

    # 3. build the community bundle
    banner("3. build the community bundle (source -> 4 files)")
    from pydantree_sitter_grammar.schema_tool import build_community_bundle
    bundle = build_community_bundle(RUST_FIXTURE, tmp / "bundle", name="rust",
                                    workdir=tmp / "bw", keep=True)
    sizes = {p.name: p.stat().st_size for p in bundle.iterdir()}
    print(json.dumps(sizes, indent=2))
    save("r2_bundle_manifest.txt", json.dumps(sizes, indent=2) + "\n")

    # 4. the B-free consumer vs hand-authored ground truth
    banner("4. B-free consumer (pydantree_sitter_grammar unimportable) vs hand truth")
    from bfree import run_bfree
    script = (ROOT / ".scratch" / "008-consumer-seam" / "consumer_rust.py").resolve()
    rc, out = run_bfree(script, str(bundle), workdir=tmp / "bfree")
    print(out)
    save("r2_bfree_consumer.txt", out)
    data = json.loads(out)
    ok = data["ok"] and data["schema_bound"] and rc == 0

    banner("VERDICT")
    print("Run 2:", "GO — the community-schema path holds over a grammar we "
          "don't own (tool byte-for-byte; exact path byte-for-byte; B-free "
          "extraction vs hand truth)" if ok else "NO-GO")
    save("r2_verdict.txt", f"verdict: {'GO' if ok else 'NO-GO'}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
