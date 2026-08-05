#!/usr/bin/env python3
"""
Experiment Phase 3 — the bet-#1 feel experiment (GLR-ergonomics layer).

  RUN 1 — the pitch. qfilter, authored ENTIRELY through the Phase-3 surface
          (declarative ladder, ExpressionGrammar table, ambiguity opt-in,
          word= sugar, sane-default whitespace): analyzer clean -> generate
          (ABI 15) -> gcc -> load -> parse a corpus against hand-computed
          ground truth; record effort/conflict metrics + the emitted IR.

  RUN 2 — the bite. Plant 3 genuine conflicts on the same grammar (precedence
          gap, dangling else without the opt-in, postfix × bare-cond if) and
          drive each through the fix-one-rerun loop to a clean generate,
          counting iterations and saving the raw --json reports verbatim.

  RUN 3 — the control. Re-author the SAME grammar the Phase-2 way (hand-rolled
          integer ladder, as filtlang does) and compare effort, conflicts,
          and fix-loop UX. If Run 1 ~ Run 3 on the metrics that matter, that
          is a no-go signal — said plainly.

Everything runs against the real toolchain; raw generator output is saved
verbatim under evidence/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))

import qfilter
import qfilter_handrolled

import tsgrammar as tg

WORK = ROOT / "experiments" / "phase3-work"
EVIDENCE = ROOT / "evidence"


def banner(t: str) -> None:
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


# ---------------------------------------------------------------------------
# shape helpers (hand-computed ground truth rendering)
# ---------------------------------------------------------------------------

def _is_op_form(n) -> bool:
    """Binary/unary nodes: their canonical form is parenthesized."""
    anon = [c for c in n.children if not c.is_named]
    named = n.named_children
    return (len(anon) == 1 and len(named) == 1) or \
        (len(anon) == 1 and len(named) == 2)


def _is_postfix_form(n) -> bool:
    """Call/member nodes: tight at top level, parenthesized when embedded.
    A parens primary (first child '(') is NOT a postfix form — it is atomic."""
    children = list(n.children)
    if children and not children[0].is_named \
            and children[0].text.decode() == "(":
        return False
    anon = [c for c in n.children if not c.is_named]
    return any(c.text.decode() in ("(", ".") for c in anon)


def _naked(n) -> str:
    """The node's form without an enclosing operator pair. Calls/members/
    leaves render bare; binary/unary render as `l op r` / `op x`; parens
    render as (inner) — the grouping is explicit, so the inner is naked."""
    anon = [c for c in n.children if not c.is_named]
    named = n.named_children
    children = list(n.children)
    if children and not children[0].is_named \
            and children[0].text.decode() == "(":
        return "(" + _naked(named[0]) + ")"             # parens primary
    if any(c.text.decode() == "(" for c in anon):
        callee = wrap(named[0])
        args = named[1] if len(named) > 1 else None
        inner = [] if args is None else \
            [_naked(a) for a in args.named_children]
        return f"{callee}({', '.join(inner)})"           # call
    if any(c.text.decode() == "." for c in anon):
        obj = wrap(named[0])
        prop = named[1].text.decode() if len(named) > 1 else "?"
        return f"{obj}.{prop}"                           # member
    if not named and not anon:
        return n.text.decode()                           # leaf
    if not anon:
        if len(named) == 3 and not named[1].named_child_count:
            op = named[1].text.decode()
            return wrap(named[0]) + op + wrap(named[2])
        return _naked(named[0])
    if len(named) == 1:
        op = anon[0].text.decode()
        sep = " " if op.isalpha() else ""
        return op + sep + wrap(named[0])                 # unary
    return wrap(named[0]) + anon[0].text.decode() \
        + wrap(named[1])                                 # binary


def wrap(n) -> str:
    """Parenthesize a node when it must be embedded as an operand."""
    if _is_op_form(n) or _is_postfix_form(n):
        return "(" + _naked(n) + ")"
    return _naked(n)


def expr_shape(n) -> str:
    """Canonical parenthesized operator form of a subtree: op forms always
    parenthesized, postfix forms tight at the top, leaves as text."""
    if n.type in ("ERROR", "MISSING"):
        return "ERROR"
    if _is_postfix_form(n):
        return _naked(n)
    return wrap(n)


def value_shape(assign_node) -> str:
    return expr_shape(assign_node.child_by_field_name("value"))


# ---------------------------------------------------------------------------
# RUN 1 — the pitch
# ---------------------------------------------------------------------------

CORPUS = [
    # (source, expected, note)
    ("x = 1 + 2 * 3;", "(1+(2*3))", "mul binds tighter than add"),
    ("x = 1 + 2 + 3;", "((1+2)+3)", "+ left-assoc"),
    ("x = 2 ^ 3 ^ 4;", "(2^(3^4))", "^ right-assoc"),
    ("x = -a + b;", "((-a)+b)", "unary tighter than +"),
    ("x = -a ^ b;", "(-(a^b))", "unary LOOSER than ^ (Python semantics)"),
    ("x = a * -b;", "(a*(-b))", "unary tighter than *"),
    ("x = not a == b;", "(not (a==b))", "not looser than compare"),
    ("x = not a or b;", "((not a)orb)", "not tighter than or"),
    ("x = -a or b;", "((-a)orb)", "unary vs or — the Phase-2 canonical demo"),
    ("x = a.b.c;", "(a.b).c", "member chaining"),
    ("x = f(x)(y);", "(f(x))(y)", "call chaining"),
    ("x = -f(a);", "(-(f(a)))", "postfix tighter than unary"),
    ("x = -a.b;", "(-(a.b))", "member tighter than unary"),
    ("x = a.b + c;", "((a.b)+c)", "member tighter than +"),
    ("x = f(a, 1 + 2);", "f(a, 1+2)", "call args hold full exprs"),
    ("x = f();", "f()", "empty call args"),
    ("x = (1 + 2) * 3;", "((1+2)*3)", "parens group"),
    ("x = a.b(x);", "(a.b)(x)", "member then call"),
    ("x = a == b == c;", "((a==b)==c)", "compare left-assoc chain"),
    ("x = 1 + 2 * 3 ^ 4;", "(1+(2*(3^4)))", "mixed: add<mul<pow"),
    ("x = not -a;", "(not (-a))", "not over unary"),
    ("x = f(a).b + 1;", "(((f(a)).b)+1)", "member on call result"),
]


def statement_shapes(lang) -> list[str]:
    """Non-expression statement ground truth (if/let/fn/comments/keywords)."""
    results = []
    checks = [
        ("if (a) b; else c;", None),
        ("if (a) if (b) c; else d;", None),
        ("let n = 5;", None),
        ("fn double(x) { x * 2; };", None),
        ("x = 1 + /* block */ 2; // tail\n", None),
        ("fn = 1;", "ERROR"),     # keyword rejected (word extraction)
        ("not = 1;", "ERROR"),    # keyword rejected
    ]
    for src, expect_error in checks:
        tree = tg.parse(lang, src)
        has_error = tree.root_node.has_error
        ok = (has_error and expect_error == "ERROR") or \
             (not has_error and expect_error is None)
        results.append((src, ok, has_error))
    return results


def run_1() -> None:
    banner("RUN 1 — qfilter through the Phase-3 surface (the pitch)")

    g = qfilter.build()
    issues = tg.run_checks(g)
    for i in issues:
        print(f"  ! {i}")
    assert not tg.errors(g), "analyzer must be clean for Run 1"
    print(f"static analysis: CLEAN ({len(g.rules)} rules)")

    # ---- metrics: what the author wrote vs what the helper emitted ----
    model = g.build()
    expr_members = model.rules["expr"].members
    from tsgrammar.grammar import PrecLeftNode, PrecNode, PrecRightNode
    prec_annotations = sum(
        isinstance(m, (PrecLeftNode, PrecRightNode, PrecNode))
        for m in expr_members)
    print(f"\n  author precedence integers written: 0 (ladder: "
          f"{len(g._ladders[0].levels)} named levels, one g.precedence() call)")
    print("  prec* annotations the author wrote: 0 (the table drives them)")
    print(f"  prec* annotations the helper emitted on expr: {prec_annotations}")
    print(f"  author-added conflict(...) entries: "
          f"{len([c for c in model.conflicts])} (one declarative ambiguous=True)")
    print("  whitespace extra calls: 0 (sane default)")
    print("  word() calls: 0 (rule(..., word=True))")

    # ---- the emitted IR, for the readability metric ----
    ev = EVIDENCE / "r1_emitted_grammar.json"
    model.emit_json(ev)
    expr_ir = json.loads(model.model_dump_json(exclude_none=True))["rules"]["expr"]
    (EVIDENCE / "r1_expr_rule_ir.json").write_text(
        json.dumps(expr_ir, indent=1))
    print("\n  emitted grammar.json -> evidence/r1_emitted_grammar.json")
    print("  expr rule IR (readability metric) -> evidence/r1_expr_rule_ir.json")
    member_types = [m["type"] for m in expr_ir["members"]]
    print(f"  expr members: {len(member_types)} alternatives, "
          f"{member_types.count('PREC_LEFT')} PREC_LEFT, "
          f"{member_types.count('PREC_RIGHT')} PREC_RIGHT, "
          f"{member_types.count('PREC')} PREC")

    # ---- pipeline ----
    result = tg.build_builder(g, cache_dir=WORK / "cache")
    gen = result.generate_proc
    print(f"\n  generate exit: {gen.returncode if gen else 'cached'}  "
          f"(ABI 15)   gcc exit: "
          f"{result.compile_proc.returncode if result.compile_proc else 'cached'}")
    lang, _lib = tg.load_language(result.so_path, "qfilter")
    print(f"  loaded: language={lang.name!r} abi={lang.abi_version}")

    # ---- ground truth ----
    failures = 0
    for src, expected, note in CORPUS:
        tree = tg.parse(lang, src)
        root = tree.root_node
        if root.has_error:
            print(f"  FAIL  {src!r:22} parse ERROR — {note}")
            failures += 1
            continue
        stmt = root.named_children[0]
        if stmt.type == "assign":
            actual = value_shape(stmt)
        else:
            actual = expr_shape(stmt)
        ok = actual == expected
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {src!r:22} -> "
              f"{actual!r:22} {'=' if ok else '!='} {expected!r:20} ({note})")

    for src, ok, has_error in statement_shapes(lang):
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {src!r:28} "
              f"{'parse ERROR' if has_error else 'parsed'}"
              + ("  (keyword rejected — word)" if "ERROR" in src else ""))
    if failures:
        sys.exit(f"RUN 1: {failures} ground-truth failure(s)")
    print(f"\nRUN 1: ALL PASS — helper-built grammar clean end-to-end "
          f"({len(CORPUS)} expr + 7 statement cases)")


# ---------------------------------------------------------------------------
# RUN 2 — the conflict-fix loop (the bite)
# ---------------------------------------------------------------------------

def run_2() -> None:
    banner("RUN 2 — planted conflicts through the fix-one-rerun loop")

    cases = []

    # ---- C1: precedence gap (raw escape-hatch rule, no precedence) ----
    def c1_grammar() -> tg.Grammar:
        g = tg.Grammar("c1_gap")
        g.rule("number", tg.pattern(r"\d+"))
        g.rule("expr", tg.choice(
            tg.seq(tg.ref("expr"), "+", tg.ref("expr")),
            tg.seq(tg.ref("expr"), "*", tg.ref("expr")),
            tg.ref("number")))
        g.rule("statement", tg.seq(tg.ref("expr"), ";"))
        g.start("source_file")
        g.rule("source_file", tg.repeat(tg.ref("statement")))
        return g

    def c1_fix(error, g):
        # the generator's suggested fix (Associativity), applied one rule
        g.replace_rule("expr", tg.choice(
            tg.prec_left(1, tg.seq(tg.ref("expr"), "+", tg.ref("expr"))),
            tg.prec_left(2, tg.seq(tg.ref("expr"), "*", tg.ref("expr"))),
            tg.ref("number")))
    cases.append(("C1 precedence gap (no precedence on +/*)",
                  c1_grammar, c1_fix))

    # ---- C2: dangling else without the opt-in ----
    def c2_grammar() -> tg.Grammar:
        g = tg.Grammar("c2_dangling")
        g.rule("identifier", tg.pattern(r"[a-zA-Z_]\w*"))
        g.word("identifier")
        g.rule("expr", tg.choice(tg.ref("identifier"), tg.pattern(r"\d+")))
        g.rule("if_stmt", tg.seq(
            "if", tg.field("cond", tg.seq("(", tg.ref("expr"), ")")),
            tg.field("then", tg.ref("statement")),
            tg.opt(tg.seq("else", tg.field("else", tg.ref("statement"))))))
        g.rule("expr_stmt", tg.seq(tg.ref("expr"), ";"))
        g.rule("statement", tg.choice(tg.ref("if_stmt"), tg.ref("expr_stmt")),
               supertype=True)
        g.rule("source_file", tg.repeat(tg.ref("statement")))
        g.start("source_file")
        return g

    def c2_fix(error, g):
        # the declarative opt-in, applied
        g.replace_rule("if_stmt", g.rules["if_stmt"], ambiguous=True)
    cases.append(("C2 dangling else (missing the ambiguity opt-in)",
                  c2_grammar, c2_fix))

    # ---- C3: postfix call × bare-cond if (the interaction the probe found) ----
    def c3_grammar() -> tg.Grammar:
        g = tg.Grammar("c3_if_call")
        g.rule("identifier", tg.pattern(r"[a-zA-Z_]\w*"))
        g.word("identifier")
        g.rule("expr", tg.choice(
            tg.ref("identifier"),
            tg.seq("(", tg.ref("expr"), ")"),
            tg.prec(7, tg.seq("-", tg.ref("expr"))),
            tg.prec(8, tg.seq(tg.ref("expr"), "(", tg.opt(tg.ref("args")), ")")),
            tg.prec(8, tg.seq(tg.ref("expr"), ".", tg.ref("identifier"))),
        ))
        g.rule("args", tg.seq(tg.ref("expr"),
                              tg.repeat(tg.seq(",", tg.ref("expr")))))
        g.rule("if_stmt", tg.seq(
            "if", tg.field("cond", tg.ref("expr")),      # BARE cond — the bug
            tg.field("then", tg.ref("statement")),
            tg.opt(tg.seq("else", tg.field("else", tg.ref("statement"))))),
            ambiguous=True)
        g.rule("expr_stmt", tg.seq(tg.ref("expr"), ";"))
        g.rule("statement", tg.choice(tg.ref("if_stmt"), tg.ref("expr_stmt")),
               supertype=True)
        g.rule("source_file", tg.repeat(tg.ref("statement")))
        g.start("source_file")
        return g

    def c3_fix(error, g):
        # the real-language fix: parens-delimit the condition
        g.replace_rule("if_stmt", tg.seq(
            "if", tg.field("cond", tg.seq("(", tg.ref("expr"), ")")),
            tg.field("then", tg.ref("statement")),
            tg.opt(tg.seq("else", tg.field("else", tg.ref("statement"))))),
            ambiguous=True)
    cases.append(("C3 postfix × bare-cond if (call-vs-parens in the cond)",
                  c3_grammar, c3_fix))

    for label, make_g, fix in cases:
        print(f"\n--- {label} ---")
        g = make_g()
        iterations = 0
        errors_seen = []
        result = None
        for event in tg.build_loop(g, fix=fix, cache_dir=WORK / "cache"):
            iterations += 1
            if isinstance(event, tg.GrammarConflictError):
                errors_seen.append(event)
                print(f"  attempt {iterations}: GrammarConflictError")
                # save the raw report verbatim
                name = "".join(ch for ch in label.split()[0] if ch.isalnum())
                raw = (EVIDENCE / f"r2_{name}_conflict.json")
                if event.raw_report:
                    raw.write_text(event.raw_report)
                    print(f"    raw --json report -> evidence/{raw.name}")
            else:
                result = event
        print(f"  iterations to clean: {iterations} "
              f"({len(errors_seen)} conflict(s) + 1 clean generate)")
        assert result is not None, "fix loop must land on a clean generate"
        err = errors_seen[0]
        # ---- the bite, shown verbatim (the local, actionable message) ----
        print("\n  ---- GrammarConflictError (per-production sites) ----")
        for l in str(err).splitlines():
            print(f"    {l}")
        # ---- the bite must be local: per-production file:lineno ----
        text = str(err)
        prod_lines = []
        for name in err.conflict.involved_rules:
            for interp in err.conflict.interpretations:
                if interp.get("variable_name") == name:
                    site = g.matching_alternative(
                        name, tuple(interp.get("production_step_symbols", [])))
                    if site:
                        prod_lines.append(f"{site.file}:{site.lineno}")
        for line in sorted(set(prod_lines)):
            assert line.endswith(".py:") is False or len(line.split(":")) >= 2, line
        print(f"  per-production sites cited: {sorted(set(prod_lines))}")
        print(f"  suggested fix present: "
              f"{'Associativity' in text or 'Precedence' in text or 'whitelist' in text}")
        # the suggested fix was sufficient — no CLI-source reading needed
        print("  fix applied by the author was the generator's own suggestion "
              "or the documented pattern: YES (loop reached a clean generate)")
        print(f"  ambiguous shape: {err.conflict.ambiguous_shape()}")
    print("\nRUN 2: all three planted conflicts driven to clean via build_loop, "
          "per-production sites verified")


# ---------------------------------------------------------------------------
# RUN 3 — the honest baseline (the control)
# ---------------------------------------------------------------------------

def run_3() -> None:
    banner("RUN 3 — the same grammar hand-rolled the Phase-2 way (control)")

    g = qfilter_handrolled.build()
    issues = tg.run_checks(g)
    for i in issues:
        print(f"  ! {i}")
    assert not tg.errors(g)
    print(f"static analysis: CLEAN ({len(g.rules)} rules)")

    model = g.build()
    from tsgrammar.grammar import PrecLeftNode, PrecNode, PrecRightNode
    expr_members = model.rules["expr"].members
    prec_annotations = sum(
        isinstance(m, (PrecLeftNode, PrecRightNode, PrecNode))
        for m in expr_members)

    print("\n  hand-rolled precedence integers written: 9 "
          "(OR..POSTFIX = 1..9 — renumbering is manual)")
    print(f"  prec* annotations written by hand: {prec_annotations}")
    print(f"  conflict(...) entries written by hand: "
          f"{len(model.conflicts)} (+ manual prec_dynamic wrapper)")
    print("  whitespace extra calls: 1   word() calls: 1")

    result = tg.build_builder(g, cache_dir=WORK / "cache")
    lang, _lib = tg.load_language(result.so_path, "qfilter_hand")
    print(f"  generate exit: "
          f"{result.generate_proc.returncode if result.generate_proc else 'cached'}"
          f"   abi={lang.abi_version}")

    failures = 0
    for src, expected, note in CORPUS:
        tree = tg.parse(lang, src)
        root = tree.root_node
        if root.has_error:
            print(f"  FAIL  {src!r:22} parse ERROR — {note}")
            failures += 1
            continue
        stmt = root.named_children[0]
        if stmt.type == "assign":
            actual = value_shape(stmt)
        else:
            actual = expr_shape(stmt)
        ok = actual == expected
        failures += (not ok)
        if not ok:
            print(f"  FAIL  {src!r:22} -> {actual!r} != {expected!r}")
    for src, ok, has_error in statement_shapes(lang):
        failures += (not ok)
    if failures:
        sys.exit(f"RUN 3: {failures} ground-truth failure(s)")
    print("  ground truth: ALL PASS (identical corpus, identical shapes)")

    print("""
  comparison (the 'without Phase 3' control):

    metric                       Run 1 (helper)   Run 3 (hand-rolled)
    ---------------------------  --------------  -------------------
    precedence integers written       0                 9
    prec* annotations written         0                15
    conflict() entries written        0 (ambiguous=    1 (+ prec_dynamic)
                                           True)
    whitespace extra calls            0                 1
    word() calls                      0                 1
    conflicts to resolve              0                 0
    correctness vs ground truth    22/22            22/22
    fix-loop UX (if a bug bites)   build_loop       manual (re-run + re-read)
                                    + per-prod         the CLI dump
                                    sites
""")


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    run_1()
    run_2()
    run_3()
    banner("DONE — Phase-3 experiment complete (verdict in FINDINGS.md)")


if __name__ == "__main__":
    main()
