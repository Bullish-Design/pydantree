#!/usr/bin/env python3
"""Phase 8 — Run 3 evidence: the A surface over the bash schema.

The extraction task itself (hand truth, validate_with active, rows matching)
is the consumer runs (r8_r2_*). This captures the remaining surface
evidence over bash's shape:

  * compiled_source — the derived .scm for each model (what a user never
    sees but can diff);
  * stubs — generate_stubs over the bash schema (Job-2 .pyi quality).

Evidence saved verbatim under evidence/ (r8_r3_*).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

EVIDENCE = Path(__file__).parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

from pydantree_sitter_grammar.schema_tool import build_community_bundle
from pydantree_sitter import Language

sys.argv = ["x", "examples/bash-extract", "bundle", "/tmp/bash-bundle"]
import importlib.util
spec = importlib.util.spec_from_file_location(
    "consumer_bash", ".scratch/010-bash-user/consumer_bash.py")
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)


def main() -> int:
    bundle = build_community_bundle("tests/fixtures/bash", "/tmp/bash-bundle",
                                    name="bash", keep=True)
    lang = Language.load_bundle(bundle)

    # 1. the derived .scm for each model (the user-visible diagnostic)
    scm = {}
    for name in ("FunctionDef", "Assignment", "Heredoc"):
        model = getattr(consumer, name)
        scm[name] = model.compiled_source(schema=lang.schema, language=lang)
    text = "\n\n".join(f"=== {n} ===\n{s}" for n, s in scm.items()) + "\n"
    (EVIDENCE / "r8_r3_compiled_source.scm").write_text(text)
    print(text)

    # 2. stubs over the bash schema
    from pydantree_sitter.stubs import generate_stubs
    out = EVIDENCE / "r8_r3_bash_stubs.pyi"
    n = generate_stubs(lang.schema, out=out)
    print(f"\nstubs written: {out} ({n} lines)")
    stub = out.read_text()
    # sanity: the kinds we extracted from must have accessors
    for probe in ("class heredoc_redirect", "class function_definition",
                  "class variable_assignment", "class heredoc_start",
                  "class heredoc_body", "class heredoc_end"):
        assert probe in stub, f"missing {probe!r} in stubs"
    # the record of what the stubs look like for the three anchors
    lines = [l for l in stub.splitlines()
             if l.startswith("class ") or "def " in l]
    (EVIDENCE / "r8_r3_stub_quality.txt").write_text(
        "\n".join(lines) + f"\n\n({n} lines total)\n")
    print(f"stub classes/accessors: {len(lines)}")
    for l in lines[:25]:
        print(" ", l)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
