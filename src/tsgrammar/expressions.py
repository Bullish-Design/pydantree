"""
tsgrammar.expressions — the ExpressionGrammar (Pratt-style) helper.

From a table — primaries, infix operators with associativity + ladder levels,
prefix operators, and postfix element builders — emit the expression rule
(`prec.left/right` alternatives + the choice ladder) with the Phase-3
probe-verified semantics:

- ONE consistent ladder (all-int by default, all-named via `named=`); the
  helper can only emit consistent precedence, so the Phase-2 kitsink
  named/int-mixing failure is unreachable through it.
- The single-rule emission form (filtlang-style): every operator is a
  `prec*`-annotated alternative of ONE `<name>` rule whose operands are the
  `<name>` ref itself. Probe 1/2 (`.scratch/005-tsgrammar-glr/`) verified this
  generates conflict-free for the full tricky operator set and keeps a clean
  per-op CST (layered hidden-rule emission flattens ops into one node —
  rejected).
- POSTFIX MUST OUTRANK THE UNARY (probe-2 finding): with an expr-callee
  postfix (`expr ( args )`), a postfix level below the unary makes `-f(x)`
  parse as `(-f)(x)`; postfix above the unary gives `-(f(x))` (the semantics
  every real expression language has). Authors put the postfix level at the
  top of their ladder.

Table formats:

    infix:  [(op, assoc, level), ...]      # op: str literal | B (named-op rule)
    prefix: [(op, level), ...]
    postfix: [(label, level, builder), ...]  # builder(expr_ref) -> B

Escape hatch: the helper emits ONE rule; authors can drop to raw `g.rule()`
+ `prec*` for anything weird (or add a `postfix` builder that does it).

Usage:

    prec = g.precedence("or", "and", "not", "compare", "add", "mul",
                        "unary", "pow", "postfix")
    g.rule("args", seq(ref("expr"), repeat(seq(",", ref("expr")))))
    g.expression("expr",
        primary=choice(ref("number"), ref("identifier"),
                       seq("(", ref("expr"), ")")),
        infix=[("+", "left", "add"), ("-", "left", "add"),
               ("*", "left", "mul"), ("/", "left", "mul"),
               ("^", "right", "pow"), ("<", "left", "compare")],
        prefix=[("-", "unary"), ("not", "not")],
        postfix=[
            ("call", "postfix", lambda e: seq(e, "(", opt(ref("args")), ")")),
            ("member", "postfix", lambda e: seq(e, ".", ref("identifier"))),
        ],
        ladder=prec)
"""

from __future__ import annotations

from .builder import (
    B,
    Grammar,
    Ladder,
    as_node,
    choice,
    prec,
    prec_left,
    prec_right,
    ref,
    seq,
)

_Op = str | B  # an operator: literal string or a rule node (named op)


def expression(
    g: Grammar,
    name: str,
    *,
    primary: B | object,
    infix: list[tuple[_Op, str, str]] | None = None,
    prefix: list[tuple[_Op, str]] | None = None,
    postfix: list[tuple[str, str, object]] | None = None,
    ladder: Ladder,
) -> Grammar:
    """Register an expression rule `<name>` from a table (see module docstring
    for formats). `ladder` is REQUIRED: the helper's levels are the ladder's
    names, so the ordering is unambiguous and the same ladder is usable by raw
    rules elsewhere in the grammar. Emits the single-rule choice form."""
    infix = infix or []
    prefix = prefix or []
    postfix = postfix or []

    # validate levels against the ladder up front (fail fast in Python, not in
    # the Rust generator)
    for entry in infix:
        _require_level(ladder, entry[2], f"infix {entry[0]!r}")
    for entry in prefix:
        _require_level(ladder, entry[1], f"prefix {entry[0]!r}")
    for label, level, _builder in postfix:
        _require_level(ladder, level, f"postfix {label!r}")

    expr_ref = ref(name)
    alternatives: list[B] = []

    # infix operators, ladder order -> tightest last
    for op, assoc, level in infix:
        body = seq(expr_ref, _as_op(op), expr_ref)
        if assoc == "left":
            alternatives.append(prec_left(ladder.n(level), body))
        elif assoc == "right":
            alternatives.append(prec_right(ladder.n(level), body))
        else:
            raise ValueError(
                f"infix assoc must be 'left' or 'right', got {assoc!r} "
                f"(operator {op!r})")

    # prefix operators
    for op, level in prefix:
        alternatives.append(prec(ladder.n(level), seq(_as_op(op), expr_ref)))

    # postfix elements (call/member/etc.) — builder receives the expr ref
    for label, level, builder in postfix:
        body = builder(expr_ref)
        alternatives.append(prec(ladder.n(level), body))

    alternatives.append(primary)
    g.rule(name, choice(*alternatives))
    return g


def _require_level(ladder: Ladder, level: str, what: str) -> None:
    if level not in ladder.levels:
        raise KeyError(
            f"{what}: level {level!r} not in the ladder {ladder.levels} — "
            "declare it with g.precedence(...) (postfix belongs at the top: "
            "it must outrank the unary)")


def _as_op(op: _Op) -> B:
    """An operator can be a literal string (anonymous token) or a B/rule node
    (a named operator rule, e.g. a compare-op choice). Literal strings stay
    inline (Phase-2 appendix fact 5: anonymous tokens are inline literals)."""
    if isinstance(op, str):
        return seq(op)  # seq over a literal -> StrNode, kept anonymous
    return as_node(op)
