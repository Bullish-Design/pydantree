"""
Probe 2 — the final ladder, three emission variants:

  F. single-rule, all-INT ladder, postfix = top level (above unary and pow)
  G. single-rule, all-NAMED ladder via precedence_ordering (descending),
     postfix = highest named level
  H. kitsink-style layered: named or/and on top (expr), int arith + unary +
     postfix below (_arith)

Ladder (loose -> tight): or < and < not < compare < add < mul < unary < pow
< postfix. Semantics target (Python-ish):
  -a ^ b     -> -(a^b)      (unary LOOSER than pow)
  -f(x)      -> -(f(x))     (postfix TIGHTER than unary)
  -a.b       -> -(a.b)
  not a==b   -> not(a==b)   (not looser than compare)
  not a or b -> (not a)or b (not tighter than or)
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
WORK.mkdir(parents=True, exist_ok=True)

IDENT = tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*")
NUMBER = tg.pattern(r"\d+(\.\d+)?")


def expr_shape(n) -> str:
    """Parenthesized operator form. Call nodes are `expr` nodes containing
    `(`/`)` anons -> render as callee(args)."""
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
            inner = [] if args is None else [expr_shape(a) for a in args.named_children]
            return f"{callee}({', '.join(inner)})"
        if c.type == "member":
            obj = expr_shape(c.child_by_field_name("object"))
            prop = c.child_by_field_name("property")
            return f"{obj}.{prop.text.decode() if prop else '?'}"
        if c.type == "expr":
            return "(" + expr_shape(c) + ")"
        return expr_shape(c)
    if n.type == "member":
        obj = expr_shape(n.child_by_field_name("object"))
        prop = n.child_by_field_name("property")
        return f"{obj}.{prop.text.decode() if prop else '?'}"
    # a call: expr node with '(' among its anon children
    if any(c.text.decode() == "(" for c in anon):
        callee = expr_shape(named[0])
        args = named[1] if len(named) > 1 else None
        inner = [] if args is None else [expr_shape(a) for a in args.named_children]
        return f"{callee}({', '.join(inner)})"
    if not named and not anon:
        return n.text.decode()
    if not anon:
        if len(named) == 3 and not named[1].named_child_count:
            op = named[1].text.decode()
            return "(" + expr_shape(named[0]) + op + expr_shape(named[2]) + ")"
        return expr_shape(named[0])
    if len(named) == 1:
        return "(" + anon[0].text.decode() + expr_shape(named[0]) + ")"
    op = anon[0].text.decode()
    return "(" + expr_shape(named[0]) + op + expr_shape(named[1]) + ")"


def base_rules(g: tg.Grammar):
    g.rule("number", NUMBER)
    g.rule("identifier", IDENT)
    g.word("identifier")
    g.rule("statement", tg.seq(tg.ref("expr"), ";"))
    g.start("source_file")
    g.rule("source_file", tg.repeat(tg.ref("statement")))
    g.extra(tg.pattern(r"\s"))


def _ops(l, *, postfix_level):
    """The shared operator alternative list for a ladder object l."""
    return [
        tg.prec_left(l("or"), tg.seq(tg.ref("expr"), "or", tg.ref("expr"))),
        tg.prec_left(l("and"), tg.seq(tg.ref("expr"), "and", tg.ref("expr"))),
        tg.prec(l("not"), tg.seq("not", tg.ref("expr"))),
        tg.prec_left(l("compare"), tg.seq(tg.ref("expr"), "<", tg.ref("expr"))),
        tg.prec_left(l("compare"), tg.seq(tg.ref("expr"), ">", tg.ref("expr"))),
        tg.prec_left(l("compare"), tg.seq(tg.ref("expr"), "==", tg.ref("expr"))),
        tg.prec_left(l("compare"), tg.seq(tg.ref("expr"), "!=", tg.ref("expr"))),
        tg.prec_left(l("add"), tg.seq(tg.ref("expr"), "+", tg.ref("expr"))),
        tg.prec_left(l("add"), tg.seq(tg.ref("expr"), "-", tg.ref("expr"))),
        tg.prec_left(l("mul"), tg.seq(tg.ref("expr"), "*", tg.ref("expr"))),
        tg.prec_left(l("mul"), tg.seq(tg.ref("expr"), "/", tg.ref("expr"))),
        tg.prec(l("unary"), tg.seq("-", tg.ref("expr"))),
        tg.prec_right(l("pow"), tg.seq(tg.ref("expr"), "^", tg.ref("expr"))),
        tg.prec(postfix_level, tg.seq(tg.ref("expr"), "(", tg.opt(tg.ref("args")), ")")),
        tg.prec(postfix_level, tg.seq(tg.ref("expr"), ".", tg.ref("identifier"))),
        tg.ref("atom"),
    ]


def cand_F() -> tg.Grammar:
    """All-int single rule; postfix level = 9 (top)."""
    g = tg.Grammar("cand_F")
    base_rules(g)
    L = {"or": 1, "and": 2, "not": 3, "compare": 4, "add": 5,
         "mul": 6, "unary": 7, "pow": 8}
    g.rule("expr", tg.choice(*_ops(lambda n: L[n], postfix_level=9)))
    g.rule("args", tg.seq(tg.ref("expr"), tg.repeat(tg.seq(",", tg.ref("expr")))))
    g.rule("atom", tg.choice(
        tg.ref("number"), tg.ref("identifier"),
        tg.seq("(", tg.ref("expr"), ")")))
    return g


def cand_G() -> tg.Grammar:
    """All-named single rule + precedence_ordering (descending)."""
    g = tg.Grammar("cand_G")
    base_rules(g)
    ORDER = ["postfix", "pow", "unary", "mul", "add", "compare", "not", "and", "or"]
    g.precedence_ordering(*ORDER)
    g.rule("expr", tg.choice(*_ops(lambda n: n, postfix_level="postfix")))
    g.rule("args", tg.seq(tg.ref("expr"), tg.repeat(tg.seq(",", tg.ref("expr")))))
    g.rule("atom", tg.choice(
        tg.ref("number"), tg.ref("identifier"),
        tg.seq("(", tg.ref("expr"), ")")))
    return g


def cand_H() -> tg.Grammar:
    """Kitsink-style layered: named or/and in expr, int arith in _arith,
    postfix + unary inside _arith (postfix level above unary)."""
    g = tg.Grammar("cand_H")
    base_rules(g)
    g.precedence_ordering("and", "or")
    # top layer: named boolean ops + the arith layer
    g.rule("expr", tg.choice(
        tg.prec_left("or", tg.seq(tg.ref("expr"), "or", tg.ref("expr"))),
        tg.prec_left("and", tg.seq(tg.ref("expr"), "and", tg.ref("expr"))),
        tg.ref("_arith")))
    # arith layer: all-int, operand = _arith
    ADD, MUL, UNARY, POW = 1, 2, 3, 4
    g.rule("_arith", tg.choice(
        tg.prec_left(ADD, tg.seq(tg.ref("_arith"), "+", tg.ref("_arith"))),
        tg.prec_left(ADD, tg.seq(tg.ref("_arith"), "-", tg.ref("_arith"))),
        tg.prec_left(MUL, tg.seq(tg.ref("_arith"), "*", tg.ref("_arith"))),
        tg.prec_left(MUL, tg.seq(tg.ref("_arith"), "/", tg.ref("_arith"))),
        tg.prec(UNARY, tg.seq("-", tg.ref("_arith"))),
        tg.prec_right(POW, tg.seq(tg.ref("_arith"), "^", tg.ref("_arith"))),
        tg.prec(5, tg.seq(tg.ref("_arith"), "(", tg.opt(tg.ref("args")), ")")),
        tg.prec(5, tg.seq(tg.ref("_arith"), ".", tg.ref("identifier"))),
        tg.ref("atom")))
    g.rule("args", tg.seq(tg.ref("expr"), tg.repeat(tg.seq(",", tg.ref("expr")))))
    g.rule("atom", tg.choice(
        tg.ref("number"), tg.ref("identifier"),
        tg.seq("(", tg.ref("expr"), ")")))
    return g


CORPUS = [
    ("1 + 2 * 3;", "(1+(2*3))", "mul tighter than add"),
    ("1 + 2 + 3;", "((1+2)+3)", "+ left-assoc"),
    ("2 ^ 3 ^ 4;", "(2^(3^4))", "^ right-assoc"),
    ("-a + b;", "((-a)+b)", "unary tighter than +"),
    ("-a ^ b;", "(-(a^b))", "unary LOOSER than ^"),
    ("a * -b;", "(a*(-b))", "unary tighter than *"),
    ("not a == b;", "(not(a==b))", "not looser than compare"),
    ("not a or b;", "((nota)orb)", "not tighter than or"),
    ("-a or b;", "((-a)orb)", "unary vs or (Phase-2 canonical)"),
    ("a.b.c;", "((a.b).c)", "member chaining"),
    ("f(x)(y);", "f(x)(y)", "call chaining"),
    ("-f(x);", "(-f(x))", "postfix tighter than unary"),
    ("-a.b;", "(-(a.b))", "member tighter than unary"),
    ("a.b + c;", "((a.b)+c)", "member tighter than +"),
    ("f(x) + 1;", "(f(x)+1)", "call tighter than +"),
    ("a.b ^ c;", "((a.b)^c)", "member tighter than ^"),
    ("1 < 2 + 3;", "(1<(2+3))", "compare looser than +"),
    ("a == b == c;", "((a==b)==c)", "compare left-assoc"),
    ("-f(x) + 1;", "((-f(x))+1)", "combined"),
    ("a.b(x);", "(a.b)(x)", "member then call"),
    ("(-a)^b;", "(((-a))^b)", "parens"),
]


def run_candidate(name, build_fn):
    print(f"\n===== {name} =====")
    g = build_fn()
    issues = tg.run_checks(g)
    for i in issues:
        print(f"  ! {i}")
    try:
        res = tg.build_builder(g, cache_dir=WORK / "cache")
    except tg.GenerateError as e:
        print("  GENERATE FAILED:")
        print("  " + "\n  ".join(e.proc.stderr.strip().splitlines()[:20]))
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
        print(f"  {name}: {failures} failure(s)")
        return False
    print(f"  {name}: CLEAN + ALL PASS")
    return True


def main():
    results = {}
    for name, fn in [("F all-int, postfix=9", cand_F),
                     ("G all-named, ordering", cand_G),
                     ("H layered (named or/and + int arith)", cand_H)]:
        results[name] = run_candidate(name, fn)
    print("\n===== SUMMARY =====")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")


if __name__ == "__main__":
    main()
