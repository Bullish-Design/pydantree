"""
Probe 1 — which expression emission structure generates clean on the CLI and
parses the Run-1 operator set with the right shapes?

Run-1 operator set (the pitch):
  or / and / not (prefix) / compare (< > <= >= == !=) / + - * / /
  ^ (right-assoc) / unary - / postfix call f(x) / postfix member a.b

Candidates:
  A. single-rule, all-int ladder, unary operand = full expr (filtlang-style)
  B. single-rule, all-int, layered operands (unary/postfix operand = the arith layer)
  C. single-rule, all-named ladder, postfix as prec(1) int
  D. kitsink-style two-layer (named or/and on top, int arith below)
  E. A but postfix = prec_left(1) instead of prec(1) (member chaining)

Each candidate must: generate exit 0 (ABI 15) -> compile -> load -> parse the
corpus -> match hand-computed shapes.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

import tsgrammar as tg

WORK = ROOT / "experiments" / "probe-work"
EVIDENCE = ROOT / "evidence"
WORK.mkdir(parents=True, exist_ok=True)
EVIDENCE.mkdir(parents=True, exist_ok=True)

IDENT = tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*")
NUMBER = tg.pattern(r"\d+(\.\d+)?")


def expr_shape(n) -> str:
    """Parenthesized operator form; leaves render as text; calls f(a,b);
    member a.b; parens (x)."""
    if n.type in ("ERROR", "MISSING"):
        return "ERROR"
    anon = [c for c in n.children if not c.is_named]
    named = n.named_children
    if n.type == "atom":
        if not named:
            return n.text.decode()
        c = named[0]
        if c.type == "call":
            callee = expr_shape(c.named_children[0])
            args = c.named_children[1] if len(c.named_children) > 1 else None
            inner = [] if args is None else \
                [expr_shape(a) for a in args.named_children]
            return f"{callee}({', '.join(inner)})"
        if c.type == "member":
            obj = expr_shape(c.child_by_field_name("object"))
            prop = c.child_by_field_name("property")
            prop_txt = prop.text.decode() if prop is not None else "?"
            return f"{obj}.{prop_txt}"
        if c.type == "expr":
            return "(" + expr_shape(c) + ")"
        return expr_shape(c)
    if n.type == "member":
        obj = expr_shape(n.child_by_field_name("object"))
        prop = n.child_by_field_name("property")
        return f"{obj}.{prop.text.decode() if prop else '?'}"
    if not named and not anon:
        return n.text.decode()
    if not anon:
        if len(named) == 3 and not named[1].named_child_count:
            op = named[1].text.decode()
            return "(" + expr_shape(named[0]) + op + expr_shape(named[2]) + ")"
        return expr_shape(named[0])
    if len(named) == 1 and anon:
        return "(" + anon[0].text.decode() + expr_shape(named[0]) + ")"
    op = anon[0].text.decode()
    return "(" + expr_shape(named[0]) + op + expr_shape(named[1]) + ")"


# ---------------------------------------------------------------- candidates

def base_rules(g: tg.Grammar):
    """Lexical + statement scaffolding shared by all candidates."""
    g.rule("number", NUMBER)
    g.rule("identifier", IDENT)
    g.word("identifier")
    g.rule("statement", tg.seq(tg.ref("expr"), ";"))
    g.start("source_file")
    g.rule("source_file", tg.repeat(tg.ref("statement")))
    g.extra(tg.pattern(r"\s"))
    return g


def cand_A() -> tg.Grammar:
    """Single rule, all-int, unary/postfix operand = full expr (filtlang-style)."""
    g = tg.Grammar("cand_A")
    base_rules(g)
    OR, AND, NOT, CMP, ADD, MUL, UNARY, POW = 1, 2, 3, 4, 5, 6, 7, 8
    g.rule("expr", tg.choice(
        tg.prec_left(OR, tg.seq(tg.ref("expr"), "or", tg.ref("expr"))),
        tg.prec_left(AND, tg.seq(tg.ref("expr"), "and", tg.ref("expr"))),
        tg.prec(NOT, tg.seq("not", tg.ref("expr"))),
        tg.prec_left(CMP, tg.seq(tg.ref("expr"), "<", tg.ref("expr"))),
        tg.prec_left(CMP, tg.seq(tg.ref("expr"), ">", tg.ref("expr"))),
        tg.prec_left(CMP, tg.seq(tg.ref("expr"), "==", tg.ref("expr"))),
        tg.prec_left(CMP, tg.seq(tg.ref("expr"), "!=", tg.ref("expr"))),
        tg.prec_left(ADD, tg.seq(tg.ref("expr"), "+", tg.ref("expr"))),
        tg.prec_left(ADD, tg.seq(tg.ref("expr"), "-", tg.ref("expr"))),
        tg.prec_left(MUL, tg.seq(tg.ref("expr"), "*", tg.ref("expr"))),
        tg.prec_left(MUL, tg.seq(tg.ref("expr"), "/", tg.ref("expr"))),
        tg.prec(UNARY, tg.seq("-", tg.ref("expr"))),
        tg.prec_right(POW, tg.seq(tg.ref("expr"), "^", tg.ref("expr"))),
        tg.prec(1, tg.seq(tg.ref("expr"), "(", tg.opt(tg.ref("args")), ")")),
        tg.prec(1, tg.seq(tg.ref("expr"), ".", tg.ref("identifier"))),
        tg.ref("atom")))
    g.rule("args", tg.seq(tg.ref("expr"),
                          tg.repeat(tg.seq(",", tg.ref("expr")))))
    g.rule("atom", tg.choice(
        tg.ref("number"), tg.ref("identifier"),
        tg.seq("(", tg.ref("expr"), ")")))
    return g


def cand_E() -> tg.Grammar:
    """Candidate A but postfix uses prec_left(1) (member chaining without
    equal-precedence conflict)."""
    g = tg.Grammar("cand_E")
    base_rules(g)
    OR, AND, NOT, CMP, ADD, MUL, UNARY, POW = 1, 2, 3, 4, 5, 6, 7, 8
    g.rule("expr", tg.choice(
        tg.prec_left(OR, tg.seq(tg.ref("expr"), "or", tg.ref("expr"))),
        tg.prec_left(AND, tg.seq(tg.ref("expr"), "and", tg.ref("expr"))),
        tg.prec(NOT, tg.seq("not", tg.ref("expr"))),
        tg.prec_left(CMP, tg.seq(tg.ref("expr"), "<", tg.ref("expr"))),
        tg.prec_left(ADD, tg.seq(tg.ref("expr"), "+", tg.ref("expr"))),
        tg.prec_left(ADD, tg.seq(tg.ref("expr"), "-", tg.ref("expr"))),
        tg.prec_left(MUL, tg.seq(tg.ref("expr"), "*", tg.ref("expr"))),
        tg.prec_left(MUL, tg.seq(tg.ref("expr"), "/", tg.ref("expr"))),
        tg.prec(UNARY, tg.seq("-", tg.ref("expr"))),
        tg.prec_right(POW, tg.seq(tg.ref("expr"), "^", tg.ref("expr"))),
        tg.prec_left(1, tg.seq(tg.ref("expr"), "(", tg.opt(tg.ref("args")), ")")),
        tg.prec_left(1, tg.seq(tg.ref("expr"), ".", tg.ref("identifier"))),
        tg.ref("atom")))
    g.rule("args", tg.seq(tg.ref("expr"),
                          tg.repeat(tg.seq(",", tg.ref("expr")))))
    g.rule("atom", tg.choice(
        tg.ref("number"), tg.ref("identifier"),
        tg.seq("(", tg.ref("expr"), ")")))
    return g


CORPUS = [
    # (source, expected shape, note)
    ("1 + 2 * 3;", "(1+(2*3))", "mul binds tighter than add"),
    ("1 + 2 + 3;", "((1+2)+3)", "+ left-assoc"),
    ("2 ^ 3 ^ 4;", "(2^(3^4))", "^ right-assoc"),
    ("-a + b;", "((-a)+b)", "unary tighter than +"),
    ("-a ^ b;", "-(a^b)", "unary LOOSER than ^ (Python semantics)"),
    ("a * -b;", "(a*(-b))", "unary tighter than *"),
    ("not a == b;", "not(a==b)", "not looser than compare"),
    ("not a or b;", "(not a)or b", "not tighter than or"),
    ("-a or b;", "((-a))or b", "unary vs or (the canonical Phase-2 demo)"),
    ("a.b.c;", "(a.b).c", "member chaining"),
    ("f(x)(y);", "f(x)(y)", "call chaining"),
    ("a.b + c;", "((a.b)+c)", "member binds tighter than +"),
    ("f(x) + 1;", "(f(x)+1)", "call binds tighter than +"),
    ("-f(x);", "-(f(x))", "call inside unary"),
    ("a.b ^ c;", "((a.b)^c)", "member tighter than ^"),
    ("1 < 2 + 3;", "(1<(2+3))", "compare looser than +"),
    ("a == b == c;", "((a==b)==c)", "compare left-assoc chaining"),
]


def run_candidate(name, build_fn):
    print(f"\n===== {name} =====")
    try:
        issues = tg.run_checks(build_fn())
        if issues:
            print("  analyzer issues:")
            for i in issues:
                print(f"    ! {i}")
    except ValueError as e:
        print(f"  analyzer exception: {e}")
    g = build_fn()
    try:
        res = tg.build_builder(g, cache_dir=WORK / "cache")
    except tg.GenerateError as e:
        print(f"  GENERATE FAILED (exit {e.proc.returncode})")
        print("  " + "\n  ".join(e.proc.stderr.strip().splitlines()[:15]))
        return False
    lang, _lib = tg.load_language(res.so_path, g.name)
    failures = 0
    for src, expected, note in CORPUS:
        tree = tg.parse(lang, src)
        root = tree.root_node
        if root.has_error:
            print(f"  FAIL  {src:16} parse ERROR — {note}")
            failures += 1
            continue
        stmt = root.named_children[0]
        actual = expr_shape(stmt.named_children[0])
        ok = actual == expected
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {src:16} -> {actual:22} "
              f"{'=' if ok else '!='} {expected:16} ({note})")
    if failures:
        print(f"  {name}: {failures} ground-truth failure(s)")
        return False
    print(f"  {name}: CLEAN generate + all ground truth PASS")
    return True


def main():
    results = {}
    for name, fn in [("A single-rule all-int, prec(1) postfix", cand_A),
                     ("E single-rule all-int, prec_left(1) postfix", cand_E)]:
        results[name] = run_candidate(name, fn)
    print("\n===== SUMMARY =====")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")


if __name__ == "__main__":
    main()
