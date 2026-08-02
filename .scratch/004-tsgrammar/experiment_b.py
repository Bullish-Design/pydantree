#!/usr/bin/env python3
"""
Experiment B — DSL-authored grammar end-to-end (the go/no-go).

  1. Build a nontrivial grammar ENTIRELY through the builder DSL (filtlang).
  2. Static analysis clean -> generate (ABI 15) -> gcc -> load -> parse.
  3. Assert CST shapes against hand-computed ground truth.
  4. Plant each known footgun on throwaway grammars and show the analyzer
     catches it pre-generate (unused rule, nullable-in-repeat, SYMBOL-in-
     TOKEN + the IMMEDIATE_TOKEN quirk, extras x token-prefix overlap,
     pattern flags, precedence mixing, undefined refs).
  5. Author a deliberate conflict and show GrammarConflictError naming the
     DSL source lines with the ambiguous shape + competing productions +
     suggested fixes.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

import tsgrammar as tg                       # noqa: E402
import filtlang                              # noqa: E402

WORK = ROOT / "work-b"
EVIDENCE = ROOT / "evidence"


def banner(t: str) -> None:
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


def shape(n) -> str:
    """Hand-computed-shape helper: compact structural rendering of a CST node
    (named children + anonymous operators in parens, recursive)."""
    if n.type == "ERROR" or n.type == "MISSING":
        return "ERROR"
    anon = [c for c in n.children if not c.is_named]
    named = n.named_children
    if not named and not anon:
        return n.type  # leaf (e.g. (number) with no children is anonymous?)
    parts = []
    i = 0
    # interleave anonymous ops between named children
    for c in n.children:
        if c.is_named:
            parts.append(shape(c))
    if anon:
        ops = "".join(a.text.decode() for a in anon)
        return f"({n.type}{' ' if parts else ''}{' '.join(parts)}{' ' if parts else ''}[{ops}])"
    return f"({n.type} {' '.join(parts)})"


def expr_shape(n) -> str:
    """Narrow shape for expr/atom subtrees: parenthesized operator form.
    Leaves render as their text; parens as (...); calls as f(a, b)."""
    if n.type == "ERROR":
        return "ERROR"
    anon = [c for c in n.children if not c.is_named]
    named = n.named_children
    if n.type == "atom":
        if not named:
            return n.text.decode()
        c = named[0]
        if c.type == "call":
            callee = c.named_children[0]
            args_node = c.named_children[1] if len(c.named_children) > 1 else None
            args = [] if args_node is None else \
                [expr_shape(a) for a in args_node.named_children]
            return f"{callee.text.decode()}({', '.join(args)})"
        if c.type == "expr":
            return "(" + expr_shape(c) + ")"
        return expr_shape(c)
    if not named and not anon:
        return n.text.decode()   # leaf (number / identifier / string)
    if not anon:
        # named-operator binary (e.g. compare_op) or unwrap chain
        if len(named) == 3 and not named[1].named_child_count:
            op = named[1].text.decode()
            return "(" + expr_shape(named[0]) + op + expr_shape(named[2]) + ")"
        return expr_shape(named[0])
    if len(named) == 1:
        return "(-" + expr_shape(named[0]) + ")"
    op = anon[0].text.decode()
    return "(" + expr_shape(named[0]) + op + expr_shape(named[1]) + ")"


def value_shape(n) -> str:
    """Shape of an assign's value field (drill to the expr)."""
    return expr_shape(n)


def stage_1_build_and_analyze() -> tg.Grammar:
    banner("STAGE 1: DSL-authored grammar -> static analysis")
    g = filtlang.build()
    issues = tg.run_checks(g)
    print(f"rules: {', '.join(g.rules)}")
    print(f"start: {g.build().start_rule!r}  word: {g.build().word!r}")
    print(f"supertypes: {g.build().supertypes}  conflicts: {g.build().conflicts}")
    for i in issues:
        print(f"  ! {i}")
    if issues:
        print("expected clean — analyzer found problems")
        sys.exit(1)
    print("static analysis: CLEAN")
    return g


def stage_2_build_pipeline(g: tg.Grammar):
    banner("STAGE 2: generate (ABI 15) -> gcc -> load -> parse")
    result = tg.build_builder(g, cache_dir=WORK / "cache")
    print(f"generate exit: {result.generate_proc.returncode if result.generate_proc else 'cached'}")
    print(f"gcc exit:      {result.compile_proc.returncode if result.compile_proc else 'cached'}")
    lang, lib = tg.load_language(result.so_path, "filtlang")
    print(f"loaded: language={lang.name!r} abi={lang.abi_version} cached={result.cached}")
    return lang


def stage_3_ground_truth(lang) -> None:
    banner("STAGE 3: CST shapes vs hand-computed ground truth")
    cases = [
        # (source, expected expr/value shape, note)
        ("x = 1 + 2 * 3", "(1+(2*3))", "mul binds tighter than add"),
        ("x = 1 + 2 + 3", "((1+2)+3)", "+ is left-assoc"),
        ("x = -a + b", "((-a)+b)", "unary minus binds tighter than +"),
        ("x = a < b", "(a<b)", "compare binds looser than + (named op)"),
        ("x = 2 - 1 * 3", "(2-(1*3))", "mul tighter than minus"),
        ("f(a, 1 + 2);", "f(a, (1+2))", "call + arguments alias"),
        ("x = f()", "f()", "empty arguments via BLANK choice"),
    ]
    failures = 0
    for src, expected, note in cases:
        tree = tg.parse(lang, src)
        if tree.root_node.has_error:
            print(f"  FAIL  {src!r:18} parse ERROR — {note}")
            failures += 1
            continue
        n = tree.root_node
        # find the assign / expr_stmt
        stmt = n.named_children[0]
        if stmt.type == "assign":
            actual = value_shape(stmt.child_by_field_name("value"))
        else:
            actual = expr_shape(stmt.named_children[0])
        ok = actual == expected
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {src!r:18} -> {actual!r:24} "
              f"({'= ' if ok else '!= '}{expected!r})  ({note})")

    # dangling else: greedy (inner if) — statements need `;`
    tree = tg.parse(lang, "if a if b c; else d;")
    print(f"  {'PASS' if not tree.root_node.has_error else 'FAIL'}  "
          f"{'if a if b c; else d;':18} whitelisted dangling else parses "
          f"(GLR greedy)")
    failures += tree.root_node.has_error

    # comment extras parse cleanly (named rule + SYMBOL)
    tree = tg.parse(lang, "x = 1 + /* c */ 2 // tail\n")
    print(f"  {'PASS' if not tree.root_node.has_error else 'FAIL'}  "
          f"{'comments':18} block+line comments as extras")
    failures += tree.root_node.has_error

    # keywords rejected as identifiers
    tree = tg.parse(lang, "fn = 1")
    print(f"  {'PASS' if tree.root_node.has_error else 'FAIL'}  "
          f"{'fn = 1':18} keyword `fn` rejected as identifier (word)")
    failures += (not tree.root_node.has_error)

    if failures:
        sys.exit(f"{failures} ground-truth failure(s)")
    print("ground truth: ALL PASS")


def stage_4_footguns() -> None:
    banner("STAGE 4: planted footguns caught pre-generate")

    def new_g(name):
        return tg.Grammar(name)

    # (a) unused rule — the silent-pruning trap
    g = new_g("footgun_unused")
    g.rule("used", tg.pattern(r"\d+"))
    g.rule("orphan", tg.pattern(r"\w+"))
    g.rule("source_file", tg.repeat(tg.ref("used")))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("unused rule" in i.message for i in issues), issues
    print(f"  PASS  unused rule detected pre-generate: "
          f"{[i.message for i in issues if 'unused rule' in i.message]}")

    # (b) nullable inside repeat
    g = new_g("footgun_nullable")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.repeat(tg.opt(tg.ref("tok"))))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("nullable" in i.message for i in issues), issues
    print(f"  PASS  nullable-in-REPEAT detected: "
          f"{[i.message for i in issues if 'nullable' in i.message]}")

    # (c) SYMBOL inside TOKEN
    g = new_g("footgun_token")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.token(tg.seq(tg.ref("tok"), ";")), hidden=True)
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("inside TOKEN" in i.message for i in issues), issues
    print(f"  PASS  SYMBOL-in-TOKEN detected: "
          f"{[i.message for i in issues if 'inside TOKEN' in i.message]}")

    # (c2) SYMBOL inside IMMEDIATE_TOKEN: the CLI rejects this too (Phase 2
    # verified: parse_grammar.rs propagates is_token so the first check passes,
    # but the token-expansion phase raises UnexpectedRule). The analyzer flags
    # it, and the CLI agrees.
    g = new_g("footgun_immediate")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("source_file", tg.immediate_token(tg.ref("tok")))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("inside IMMEDIATE_TOKEN" in i.message for i in issues), issues
    json_path = g.emit_bundle(WORK / "footgun_immediate")
    proc = tg.run_generate(json_path)
    ok = proc.returncode != 0  # CLI must also reject it
    print(f"  PASS  SYMBOL-in-IMMEDIATE_TOKEN flagged pre-generate; CLI agrees "
          f"(exit {proc.returncode})" if ok else
          f"  NOTE  CLI accepted SYMBOL-in-IMMEDIATE_TOKEN (exit 0) — analyzer "
          f"is stricter than the generator")

    # (d) extras x token-prefix overlap (warning, not error)
    g = new_g("footgun_extra")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("div", tg.pattern(r"/"))
    g.rule("source_file", tg.repeat(tg.ref("tok")))
    g.start("source_file")
    g.extra(tg.pattern(r"/\*"))      # bare inline extra whose prefix is a token
    issues = tg.run_checks(g)
    assert any("overlaps" in i.message for i in issues), issues
    print(f"  PASS  extras-prefix overlap warning fired (bare inline extra): "
          f"{[i.message for i in issues if 'overlaps' in i.message]}")
    # the named-rule + SYMBOL fix is exempt
    g2 = new_g("footgun_extra_fixed")
    g2.rule("comment", tg.token(tg.seq("/*", tg.pattern(r"[^*]*"), "*/")))
    g2.rule("tok", tg.pattern(r"\d+"))
    g2.rule("source_file", tg.repeat(tg.ref("tok")))
    g2.start("source_file")
    g2.extra(tg.pattern(r"\s"))
    g2.extra(tg.ref("comment"))
    assert not any("overlaps" in i.message for i in tg.run_checks(g2)), \
        [i.message for i in tg.run_checks(g2)]
    print(f"  PASS  named-rule + SYMBOL extras (the documented fix) not flagged")

    # (e) pattern flags — only 'i'
    g = new_g("footgun_flags")
    g.rule("tok", tg.pattern(r"[a-z]+", flags="x"))
    g.rule("source_file", tg.repeat(tg.ref("tok")))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("only 'i'" in i.message for i in issues), issues
    flagged = [i.message for i in issues if "only 'i'" in i.message]
    assert flagged, issues
    print(f"  PASS  bad PATTERN flag detected: {flagged}")

    # (f) undefined symbol
    g = new_g("footgun_undef")
    g.rule("source_file", tg.repeat(tg.ref("nope")))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("undefined" in i.message for i in issues), issues
    print(f"  PASS  undefined Symbol detected: "
          f"{[i.message for i in issues if 'undefined' in i.message]}")

    # (g) named/int precedence mixing warning
    g = new_g("footgun_mix")
    g.rule("tok", tg.pattern(r"\d+"))
    g.rule("expr", tg.choice(
        tg.prec_left(1, tg.seq(tg.ref("expr"), "+", tg.ref("expr"))),
        tg.prec("and", tg.seq(tg.ref("expr"), "and", tg.ref("expr"))),
        tg.ref("tok")))
    g.rule("source_file", tg.repeat(tg.ref("expr")))
    g.start("source_file")
    issues = tg.run_checks(g)
    assert any("mixed" in i.message for i in issues), issues
    print(f"  PASS  named/int precedence mixing warning fired: "
          f"{[i.message for i in issues if 'mixed' in i.message]}")


def stage_5_conflict_remap() -> None:
    banner("STAGE 5: deliberate conflict -> GrammarConflictError -> DSL source")

    # a naive expression grammar (no precedence) -> precedence-gap conflict
    def naive_expr() -> tg.Grammar:
        g = tg.Grammar("conflict_gap")
        g.rule("number", tg.pattern(r"\d+"))
        g.rule("expr", tg.choice(
            tg.seq(tg.ref("expr"), "+", tg.ref("expr")),
            tg.seq(tg.ref("expr"), "*", tg.ref("expr")),
            tg.ref("number")))
        g.rule("statement", tg.seq(tg.ref("expr"), ";"))
        g.start("source_file")
        g.rule("source_file", tg.repeat(tg.ref("statement")))
        return g

    g = naive_expr()
    json_path = g.emit_bundle(WORK / "conflict_gap")
    proc = tg.run_generate(json_path, json_report=True)
    (EVIDENCE / "b5_conflict_gap_stderr.json").write_text(proc.stderr)
    assert proc.returncode == 1, "expected a conflict — got success"
    conflict, err = tg.remap_from_proc(g, proc)
    print(f"machine fields: symbol_sequence={list(conflict.symbol_sequence)}")
    print(f"  conflicting_lookahead={conflict.conflicting_lookahead!r}")
    print(f"  involved rules={conflict.involved_rules}")
    print(f"  possible_resolutions={list(conflict.resolutions)}")
    print("\n--- GrammarConflictError (names the DSL source lines) ---\n")
    text = str(err)
    print(text)
    # the error must cite the real DSL file:lineno of the rule() calls
    for name in conflict.involved_rules:
        site = g.sites[name]
        assert site.file.endswith("experiment_b.py"), site
        assert site.lineno > 0, site
        assert name in text, text
    print("\nremapping verified: every involved rule cited at its DSL "
          "definition site")
    raw = (EVIDENCE / "b5_conflict_gap_stderr.json").read_text()
    print("raw generator report saved verbatim to evidence/b5_conflict_gap_stderr.json")


def main() -> None:
    WORK.mkdir(exist_ok=True)
    EVIDENCE.mkdir(exist_ok=True)
    g = stage_1_build_and_analyze()
    lang = stage_2_build_pipeline(g)
    stage_3_ground_truth(lang)
    stage_4_footguns()
    stage_5_conflict_remap()
    banner("DONE — Experiment B passed (DSL-authored pipeline end-to-end)")


if __name__ == "__main__":
    main()
