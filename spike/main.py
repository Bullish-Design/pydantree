#!/usr/bin/env python3
"""
Phase 0 spike runner — prove the emission pipeline end-to-end.

    devenv shell -- python spike/main.py

Stages:
  1. IR round-trip   — build the fixed grammar via the DSL, emit grammar.json,
                       re-validate it back into the IR models, compare.
  2. Emit-vs-hand    — the DSL-emitted grammar.json must match the hand-written
                       reference that was validated against the CLI first.
  3. Static checks   — the cheap ones (undefined refs, nullable-in-repeat,
                       SYMBOL-in-TOKEN).
  4. PRIMARY EXPERIMENT — conflict -> Python-source remapping:
       a. precedence-gap conflict (naive expr rules)
       b. dangling-else conflict
       Each: run `tree-sitter generate --json`, save raw output verbatim to
       evidence/, parse it, map symbols back to the DSL's recorded rule sites,
       raise GrammarConflictError.
  5. Fix & parse     — fixed grammar: generate clean, compile, load, parse;
                       verify precedence/associativity CST shapes, keyword
                       behavior, comment extras.
  6. Intentional ambiguity — conflicts-whitelisted grammar: generate, compile,
                       parse the dangling-else input, show runtime resolution.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from builder import Grammar          # noqa: E402
from checks import run_checks        # noqa: E402
from conflicts import GrammarConflictError, remap_from_proc  # noqa: E402
from grammar_model import GrammarModel  # noqa: E402
from pipeline import (compile_parser, load_language, parse,  # noqa: E402
                      run_generate)
import spike_lang                    # noqa: E402

WORK = ROOT / "work"
EVIDENCE = ROOT / "evidence"


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def stage_roundtrip() -> GrammarModel:
    banner("STAGE 1: GrammarModel IR round-trip (build -> emit -> re-validate)")
    g = spike_lang.fixed()
    json_path = WORK / "spike_fixed.json"
    g.emit_json(str(json_path))
    restored = GrammarModel.model_validate_json(json_path.read_text())
    assert restored == g.build(), "round-trip mismatch"
    print(f"emitted        : {json_path}")
    print(f"round-trip     : OK  (IR -> grammar.json -> IR, structurally equal)")
    print(f"rule count     : {len(restored.rules)}")
    print(f"rules          : {', '.join(restored.rules)}")
    print(f"word           : {restored.word}")
    print(f"extras         : {[r.model_dump() for r in restored.extras]}")
    return g


def stage_emit_vs_hand(g: Grammar) -> None:
    banner("STAGE 2: DSL emission vs. hand-written reference grammar.json")
    emitted = json.loads(g.build().model_dump_json(exclude_none=True))

    def _norm(d):
        """Drop empty-list / null fields the hand-written reference omits."""
        return {k: v for k, v in d.items() if v not in ([], {}, None)}

    ref = json.loads((ROOT / "probe" / "grammar_fixed.json").read_text())
    if _norm(emitted) == _norm(ref):
        print("DSL-emitted grammar.json is semantically identical to the")
        print("hand-written reference that was validated by hand first. OK")
    else:
        print("MISMATCH vs hand-written reference (see diff above)")
        raise SystemExit(1)


def stage_checks(g: Grammar) -> None:
    banner("STAGE 3: cheap static checks (Python-side, before the Rust step)")
    issues = run_checks(g)
    if issues:
        for i in issues:
            print(f"  ! {i}")
        print(f"{len(issues)} issue(s) found")
    else:
        print("no issues found on the fixed grammar")
    # demonstrate the SYMBOL-in-TOKEN check catches a real mistake
    from builder import token as _token
    bad = Grammar("demo")
    bad.rule("number", spike_lang.pattern(r"\\d+"))
    bad.rule("identifier", spike_lang.pattern(r"\\w+"))
    bad.rule("t", spike_lang.seq(_token(spike_lang.ref("number")),
                                 spike_lang.ref("identifier")))
    bad.start("t")
    print("  - on a deliberately broken grammar, checks report:")
    for i in run_checks(bad):
        print(f"    ! {i}")


def save_raw(proc, name: str) -> None:
    (EVIDENCE / f"{name}_stdout.txt").write_text(proc.stdout)
    (EVIDENCE / f"{name}_stderr.txt").write_text(proc.stderr)


def stage_conflict_experiment() -> None:
    banner("STAGE 4: PRIMARY EXPERIMENT — conflict -> Python-source remapping")

    cases = [
        ("02_precedence_gap", spike_lang.conflict_precedence_gap,
         "naive expression rules (no precedence) -> precedence-gap conflict"),
        ("03_dangling_else", spike_lang.conflict_dangling_else,
         "correct expression precedence, dangling-else ambiguity -> conflict"),
    ]
    for tag, build_fn, desc in cases:
        print(f"\n--- case: {tag}  ({desc}) ---")
        g = build_fn()
        json_path = WORK / f"{tag}.json"
        g.emit_json(str(json_path))
        proc = run_generate(json_path, json_report=True)
        save_raw(proc, tag)
        print(f"generate exit : {proc.returncode}")
        print(f"raw output    : saved verbatim to evidence/{tag}_stdout.txt"
              f" / _{tag}_stderr.txt")
        if proc.returncode == 0:
            print("!! expected a conflict, got success — experiment invalid")
            raise SystemExit(1)
        conflict, err = remap_from_proc(g, proc)
        print(f"machine fields: symbol_sequence={list(conflict.symbol_sequence)}")
        print(f"  conflicting_lookahead={conflict.conflicting_lookahead!r}")
        print(f"  involved rules={conflict.involved_rules}")
        print("  possible_resolutions=" +
              json.dumps(list(conflict.resolutions)))
        print("\n--- GrammarConflictError raised from Python source sites ---\n")
        try:
            raise err
        except GrammarConflictError as e:
            print(str(e))


def _expr_shape(n) -> str:
    """Compact structural summary of an expr node, e.g. `((1+2)*3)`.
    Descends source_file -> statement -> expr_statement -> expr first."""
    while n.type not in ("expr", "ERROR") and n.named_child_count:
        n = n.named_children[0]
    if n.type == "expr":
        named = n.named_children
        anon = [c for c in n.children if not c.is_named]
        if not anon:
            return _expr_shape(named[0])  # the `expr -> atom` alternative
        if len(named) == 1:
            return "(-" + _expr_shape(named[0]) + ")"  # unary minus
        op = anon[0].text.decode()
        return "(" + _expr_shape(named[0]) + op + _expr_shape(named[1]) + ")"
    if n.type in ("atom", "number", "identifier"):
        inner = [c for c in n.named_children]
        if not inner:
            return n.text.decode()
        return _expr_shape(inner[0]) if n.type == "atom" else n.text.decode()
    if n.type == "ERROR":
        return "ERROR"
    return n.type


def stage_fixed_parse() -> None:
    banner("STAGE 5: fixed grammar -> generate -> compile -> load -> parse")

    g = spike_lang.fixed()
    json_path = WORK / "spike_fixed.json"
    g.emit_json(str(json_path))

    print("\n[5.1] tree-sitter generate (ABI 15)...")
    proc = run_generate(json_path, abi15=True)
    print(f"      exit {proc.returncode}; "
          f"{'OK' if proc.returncode == 0 else proc.stderr[:800]}")
    if proc.returncode != 0:
        raise SystemExit(1)

    print("[5.2] gcc -> shared library...")
    src_dir = WORK / "src"
    so_path = WORK / "spike.so"
    cc = compile_parser(src_dir, so_path)
    if cc.returncode != 0:
        print(cc.stderr[:2000])
        raise SystemExit(1)
    print(f"      compiled {so_path}")

    print("[5.3] load via Python bindings (tree-sitter 0.26, PyCapsule)...")
    lang, _ = load_language(so_path, "spike")
    print(f"      language={lang.name!r} abi={lang.abi_version}")

    print("[5.4] parse + verify precedence/associativity...")
    cases = [
        # (source, expected_shape, note)
        ("1 + 2 * 3", "(1+(2*3))", "mul binds tighter than add"),
        ("1 + 2 + 3", "((1+2)+3)", "+ is left-assoc"),
        ("2 ^ 3 ^ 4", "(2^(3^4))", "^ is right-assoc"),
        ("-2 + 3", "((-2)+3)", "unary minus binds tighter than +"),
        ("1 + 2 * 3 ^ 2", "(1+(2*(3^2)))", "add < mul < pow"),
        ("(1 + 2) * 3", "((1+2)*3)", "parentheses override"),
        ("x * 2 - 3 / y", "((x*2)-(3/y))", "mixed ids + precedence"),
    ]
    failures = 0
    for src, expected, note in cases:
        tree = parse(lang, src)
        shape = _expr_shape(tree.root_node)
        ok = shape == expected
        failures += (not ok)
        print(f"      {'PASS' if ok else 'FAIL'}  {src!r:20} -> {shape!r:26}"
              f"  ({note})")
    if failures:
        raise SystemExit(f"{failures} precedence verification(s) failed")

    print("[5.5] keyword (word) behavior + comment extras...")
    kw_tests = [
        ("iftrue + 1", "identifier `iftrue` parses fine"),
        ("if a b else c", "keywords `if`/`else` structure the if_statement"),
    ]
    for src, note in kw_tests:
        tree = parse(lang, src)
        has_error = tree.root_node.has_error
        print(f"      {'PASS' if not has_error else 'FAIL'}  {src!r:20} -> "
              f"{'clean parse' if not has_error else 'ERROR'}  ({note})")
    # `if` used as an identifier must NOT parse (keyword exclusion)
    tree = parse(lang, "if + 1")
    print(f"      {'PASS' if tree.root_node.has_error else 'FAIL'}  "
          f"{'if + 1'!r:20} -> {'ERROR (keyword excluded)' if tree.root_node.has_error else 'parsed?!'}  "
          f"(keywords rejected as identifiers)")
    tree = parse(lang, "1 + /* comment */ 2 // trailing")
    print(f"      {'PASS' if not tree.root_node.has_error else 'FAIL'}  "
          f"{'1 + /* c */ 2 // t'!r:20} -> "
          f"{'clean parse' if not tree.root_node.has_error else 'ERROR'}  "
          f"(block + line comments are extras)")

    print("\n[5.6] sample CST (dangling else resolved to the INNER if):")
    tree = parse(lang, "if a if b c else d")
    print("      " + str(tree.root_node))


def stage_intentional_ambiguity() -> None:
    banner("STAGE 6: intentional ambiguity via `conflicts` whitelist")
    g = spike_lang.intentional_ambiguity()
    json_path = WORK / "spike_ambiguous.json"
    g.emit_json(str(json_path))
    proc = run_generate(json_path, abi15=True)
    print(f"generate exit : {proc.returncode} "
          f"({'OK — whitelisted conflict accepted' if proc.returncode == 0 else proc.stderr[:500]})")
    if proc.returncode != 0:
        raise SystemExit(1)
    so_path = WORK / "spike_ambiguous.so"
    compile_parser(WORK / "src", so_path)
    lang, _ = load_language(so_path, "spike")
    tree = parse(lang, "if a if b c else d")
    print("dangling-else input parses; runtime picks the greedy (inner-if) parse:")
    print("      " + str(tree.root_node))
    print("\n(no generator error — the ambiguity is whitelisted; tree-sitter's")
    print(" GLR resolves it at parse time via the default shift bias)")


def main() -> None:
    WORK.mkdir(exist_ok=True)
    EVIDENCE.mkdir(exist_ok=True)

    g_fixed = stage_roundtrip()
    stage_emit_vs_hand(g_fixed)
    stage_checks(g_fixed)
    stage_conflict_experiment()
    stage_fixed_parse()
    stage_intentional_ambiguity()

    banner("DONE — see spike/FINDINGS.md for the verdict")


if __name__ == "__main__":
    main()
