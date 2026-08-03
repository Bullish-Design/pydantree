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
    cond_primary: B | object | None = None,
    cond_drops: tuple[str, ...] = ("call",),
) -> Grammar:
    """Register an expression rule `<name>` from a table (see module docstring
    for formats). `ladder` is REQUIRED: the helper's levels are the ladder's
    names, so the ordering is unambiguous and the same ladder is usable by raw
    rules elsewhere in the grammar. Emits the single-rule choice form.

    Phase-3A: `cond_primary=` is the typed spelling for the postfix ×
    bare-cond-`if` interaction (Phase-3 FINDINGS §4.2). When given, the helper
    ALSO registers a hidden `_<name>_cond` rule: the same ladder minus the
    postfix entries whose label is in `cond_drops` (default: `"call"`), with
    `cond_primary` as the primary. Authors use it for condition operands, so
    `if <bare expr> stmt` cannot be misread as a call — the documented
    parens-cond pattern has a declarative form:

        tg.expression(g, "expr", primary=..., postfix=[...], ladder=prec,
                      cond_primary=tg.seq("(", tg.ref("expr"), ")"))
        g.rule("if_stmt", tg.seq("if",
                                 tg.field("cond", tg.ref("_expr_cond")),
                                 ...))
    """
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

    # ---- the cond rule (Phase-3A): the ladder minus the dropped postfixes --
    if cond_primary is not None:
        # The cond rule is FULLY SELF-REFERENTIAL (operands reference
        # `_<name>_cond`, not `<name>`): a near-copy of `<name>` shares its
        # productions and the generator reports reduce/reduce at the cond
        # position; self-referential productions are structurally distinct, so
        # the cond rule generates clean without a prec hack. `if x (y)` (bare
        # cond + parens-capable then) parses unambiguously; `if f(x) y` is a
        # parse error (call conds are rejected — parens-delimit: `if (f(x))`).
        cond_ref = ref(f"_{name}_cond")
        cond_alts: list[B] = []
        for op, assoc, level in infix:
            body = seq(cond_ref, _as_op(op), cond_ref)
            cond_alts.append(prec_left(ladder.n(level), body) if assoc == "left"
                             else prec_right(ladder.n(level), body))
        for op, level in prefix:
            cond_alts.append(prec(ladder.n(level), seq(_as_op(op), cond_ref)))
        for label, level, builder in postfix:
            if label in cond_drops:
                continue
            cond_alts.append(prec(ladder.n(level), builder(cond_ref)))
        cond_alts.append(cond_primary)
        g.rule(f"_{name}_cond", choice(*cond_alts), hidden=True)
    return g


def semantic_smoke(
    g: Grammar,
    *,
    expr: str = "expr",
    cases: list[tuple[str, str]] | None = None,
    build_result=None,
    cache_dir=None,
) -> list[str]:
    """Phase-3A: emit + run the precedence semantic-smoke corpus against a
    built grammar and assert the expression CST shapes — the systematic guard
    for the Phase-3 §4 semantic-intent leak (a wrong ladder order generates
    clean but parses wrongly).

    `cases` default to the probe-2 table, each `(source, expected_render)`:

        ("-a ^ b;",  "(- ((identifier) ^ (identifier)))")   # -(a^b)
        ("-f(x);",   "(- ((identifier) ( (args (identifier)) )))")  # -(f(x))
        ("a.b.c;",   "(((identifier) . identifier) . identifier)")   # (a.b).c
        ("f(x)(y);", "(((identifier) ( (args (identifier)) )) "
                      "( (args (identifier)) ))")            # (f(x))(y)
        ("-a or b;", "((- (identifier)) or (identifier))")   # (-a) or b

    The render walks the FIRST node of type `expr` (the outermost expression
    of the statement): named leaves render as their kind, anonymous tokens as
    their text, nested exprs as `( ... )`.

    Builds the grammar (or reuses `build_result`) and returns a list of
    failure messages — empty means all cases parse with the expected shapes.
    The helper cannot verify intent; it pins the AUTHOR-CHOSEN semantics so a
    ladder reorder that silently changes `-a ^ b` from `-(a^b)` to `(-a)^b`
    is caught at author time.
    """
    from .corpus import Corpus
    result = build_result
    if result is None:
        from .pipeline import build_builder
        result = build_builder(g, cache_dir=cache_dir)
    corpus = Corpus(cases or DEFAULT_PRECEDENCE_CORPUS, style="compact",
                    selector=expr)
    run = corpus.run(build_result=result)
    out: list[str] = []
    for f in run.failures:
        if f.got is None:
            out.append(f"case {f.case.source!r}: no {expr!r} node found "
                       f"({f.detail})")
        else:
            out.append(
                f"case {f.case.source!r}: shape {f.got!r}, "
                f"expected {f.case.expected!r} "
                f"(a ladder reorder changed the parse semantics?)")
    return out


DEFAULT_PRECEDENCE_CORPUS: list[tuple[str, str]] = [
    ("-a ^ b;", "(- ((identifier) ^ (identifier)))"),          # -(a^b)
    ("-f(x);", "(- ((identifier) ( args((identifier)) )))"),    # -(f(x))
    ("a.b.c;", "(((identifier) . identifier) . identifier)"),   # (a.b).c
    ("f(x)(y);", "(((identifier) ( args((identifier)) )) "
                  "( args((identifier)) ))"),                    # (f(x))(y)
    ("-a or b;", "((- (identifier)) or (identifier))"),          # (-a) or b
]


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
