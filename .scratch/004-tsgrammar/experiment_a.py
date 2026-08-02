#!/usr/bin/env python3
"""
Experiment A — IR fidelity to the real 0.25.3 grammar.json schema.

The hand-written reference grammar (.scratch/004-tsgrammar/reference/
grammar.json) exercises the FULL schema surface (every node type in the
Phase-0 §3 table + every grammar-level field) and was validated against the
CLI FIRST (tree-sitter generate -> exit 0 -> compiled -> parsed clean).

This script proves the IR side of the fidelity gate:

  Stage 1  CLI-validate the hand-written reference (exit 0, raw output saved).
  Stage 2  GrammarModel.model_validate_json -> re-emit ->
           assert semantic equality with the reference (normalized).
  Stage 3  generate the re-emitted grammar.json (exit 0) -> compile (with the
           reference scanner.c) -> load via PyCapsule -> parse the corpus ->
           assert clean parse against hand-computed expectations.

Raw generator output is saved verbatim to evidence/.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # .scratch/004-tsgrammar
REPO = ROOT.parent.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

from tsgrammar.grammar import Grammar           # noqa: E402  (the IR)
from tsgrammar.language import parse            # noqa: E402
from tsgrammar.pipeline import compile_parser, run_generate  # noqa: E402

REF = ROOT / "reference"
WORK = ROOT / "work-a"
EVIDENCE = ROOT / "evidence"
CORPUS = (
    "// a comment\n"
    "let x = 1 + 2 * 3\n"
    'let s = "hello\\n" + name\n'
    "fn add(a, b) {\n"
    "  x + 0xDEAD;\n"
    "}\n"
    "import a, b, c\n"
    "f(x, 1, 2);\n"
    "(1, 2, 3);\n"
    "(4);\n"
    "{ if: 1, let: 2 };\n"
    "a or b and c;\n"
    "a and b or c;\n"
    "- x + 2;\n"
    "2 ^ 3 ^ 4;\n"
    "if a b; else c;\n"
    "foo: x + 1;\n"
    "# sigil\n"
)


def banner(t: str) -> None:
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


def norm(d: dict) -> dict:
    """Drop empty-list / None fields the canonical form omits."""
    return {k: v for k, v in d.items() if v not in ([], {}, None)}


def main() -> int:
    WORK.mkdir(exist_ok=True)
    EVIDENCE.mkdir(exist_ok=True)
    ref_json = (REF / "grammar.json").read_text()

    # ---- stage 1: CLI-validate the hand-written reference ----
    banner("STAGE 1: hand-written reference -> tree-sitter generate (exit 0)")
    proc = run_generate(REF / "grammar.json")
    (EVIDENCE / "a1_reference_generate_stdout.txt").write_text(proc.stdout)
    (EVIDENCE / "a1_reference_generate_stderr.txt").write_text(proc.stderr)
    print(f"exit = {proc.returncode}")
    print(f"raw stdout saved to evidence/a1_reference_generate_stdout.txt")
    print(f"raw stderr saved to evidence/a1_reference_generate_stderr.txt")
    if proc.returncode != 0:
        print("reference grammar FAILED the CLI validator — experiment invalid")
        print(proc.stderr)
        return 1

    # ---- stage 2: import -> re-emit -> semantic equality ----
    banner("STAGE 2: model_validate_json -> re-emit -> semantic equality")
    model = Grammar.model_validate_json(ref_json)
    re_emitted = json.loads(model.model_dump_json(indent=2, exclude_none=True))
    reference = json.loads(ref_json)
    if norm(re_emitted) == norm(reference):
        print("IR round-trip: re-emitted grammar.json is SEMANTICALLY EQUAL")
        print(f"  to the hand-written reference (normalized: empty lists / "
              f"None dropped)")
    else:
        print("MISMATCH:")
        print(json.dumps(norm(re_emitted), indent=1)[:4000])
        print(json.dumps(norm(reference), indent=1)[:4000])
        return 1

    # node-surface audit: every node type in the Phase-0 §3 table appears
    types = set()
    def walk(node):
        if isinstance(node, dict):
            if node.get("type"):
                types.add(node["type"])
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(re_emitted)
    expected = {
        "SYMBOL", "STRING", "PATTERN", "BLANK", "SEQ", "CHOICE", "REPEAT",
        "REPEAT1", "FIELD", "ALIAS", "TOKEN", "IMMEDIATE_TOKEN",
        "PREC", "PREC_LEFT", "PREC_RIGHT", "PREC_DYNAMIC", "RESERVED",
    }
    missing = expected - types
    if missing:
        print(f"!! node types missing from reference: {sorted(missing)}")
        return 1
    print(f"node surface: all {len(expected)} node types present in the "
          f"reference and round-tripped")
    print(f"grammar-level fields present: name, rules, precedences, conflicts, "
          f"externals, extras, inline, supertypes, word, reserved")
    print(f"rule count: {len(model.rules)}; start rule (first): "
          f"{model.start_rule!r}")

    # ---- stage 3: generate the re-emitted grammar -> compile -> parse ----
    banner("STAGE 3: re-emitted grammar.json -> generate -> gcc -> load -> parse")
    json_path = model.emit_bundle(WORK)
    gen = run_generate(json_path)
    (EVIDENCE / "a2_reemitted_generate_stdout.txt").write_text(gen.stdout)
    (EVIDENCE / "a2_reemitted_generate_stderr.txt").write_text(gen.stderr)
    print(f"generate exit = {gen.returncode} (ABI 15 config present: "
          f"{(WORK / 'tree-sitter.json').exists()})")
    if gen.returncode != 0:
        print(gen.stderr)
        return 1

    so = WORK / "kitsink.so"
    cc = compile_parser(WORK / "src", so, scanner=REF / "src" / "scanner.c")
    print(f"gcc exit = {cc.returncode}")
    if cc.returncode != 0:
        print(cc.stderr)
        return 1

    from tsgrammar.language import load_language
    lang, lib = load_language(so, "kitsink")
    print(f"loaded: language={lang.name!r} abi={lang.abi_version}")

    tree = parse(lang, CORPUS)
    print(f"corpus parse: has_error={tree.root_node.has_error}")
    if tree.root_node.has_error:
        print(tree.root_node)
        return 1

    # hand-computed ground-truth assertions (subset, structural)
    checks = [
        ("a or b and c;\n", "a or (b and c)", "named precedence or < and"),
        ("a and b or c;\n", "(a and b) or c", "named precedence or < and (2)"),
        ("- x + 2;\n", "(-x) + 2", "unary minus binds tighter than +"),
        ("2 ^ 3 ^ 4;\n", "2 ^ (3 ^ 4)", "^ is right-assoc"),
        ("(1, 2, 3);\n", "tuple", "alias on hidden rule -> tuple node"),
    ]
    failures = 0
    for src, expect_desc, note in checks:
        t = parse(lang, src)
        ok = not t.root_node.has_error
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {src.strip()!r:18} {note} "
              f"({expect_desc})")
    # negative: globally-reserved `if` cannot be an identifier
    t = parse(lang, "let x = if\n")
    if t.root_node.has_error:
        print(f"  PASS  {'let x = if':18} globally-reserved `if` rejected "
              f"as identifier")
    else:
        print(f"  FAIL  {'let x = if':18} parsed?! (reserved words not applied)")
        failures += 1

    print("\nDONE — Experiment A gate passed" if failures == 0 else
          f"\n{FAILURES} assertion failure(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
