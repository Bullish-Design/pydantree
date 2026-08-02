"""
The spike grammar — a small expression + statement language with a *real* GLR
test surface, authored via the builder DSL. Defined in several variants:

  * conflict_dangling_else()   — correct expression precedence, but the classic
                                 dangling-else ambiguity in `if_statement`.
  * conflict_precedence_gap()  — expression rules written WITHOUT precedence
                                 (deliberate precedence gap -> conflicts).
  * fixed()                    — dangling else resolved via PREC_LEFT.
  * intentional_ambiguity()    — dangling else whitelisted via `conflicts`
                                 (GLR keeps the ambiguity; runtime resolves).

Language: literals, identifiers, binary ops with mixed associativity
(^ right; + - * / left), unary minus, parentheses, // and /* */ comments in
extras, and a word/keyword rule to keep keywords out of identifiers.
"""

from __future__ import annotations

from builder import Grammar, choice, opt, pattern, prec, prec_left, \
    prec_right, ref, repeat, repeat1, seq, token


# Precedence levels (hand-rolled ladder; Phase 3 will generate this from a table)
ADD, MUL, POW, UNARY = 1, 2, 3, 4


def _lexical_rules(g: Grammar) -> None:
    g.rule("number", pattern(r"\d+(\.\d+)?"))
    g.rule("identifier", pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"))
    # `word` makes the CLI auto-extract keyword tokens from word-like string
    # literals ("if", "else", ...) and reject them as identifiers — the
    # standard keyword/identifier-conflict fix. A separate `keyword` rule is
    # NOT needed (and would be silently dropped as unused).
    g.word("identifier")


def _atom_rule(g: Grammar) -> None:
    g.rule("atom", choice(
        ref("number"),
        ref("identifier"),
        seq("(", ref("expr"), ")"),
    ))


def _statement_rules(g: Grammar, resolve_else: str | None) -> None:
    """statement / expr_statement / if_statement.
    resolve_else: None = leave ambiguous; 'left' = PREC_LEFT fix."""
    if_statement_body = seq(
        "if", ref("expr"), ref("statement"),
        opt(seq("else", ref("statement"))),
    )
    if resolve_else == "left":
        if_statement_body = prec_left(1, if_statement_body)

    g.rule("if_statement", if_statement_body)
    g.rule("expr_statement", ref("expr"))
    g.rule("statement", choice(ref("expr_statement"), ref("if_statement")))


def _expression_rules(g: Grammar, *, precedence: bool) -> None:
    """expr rule. With precedence: hand-rolled PREC_LEFT/PREC_RIGHT ladder.
    Without: naive left-recursive choice -> the precedence-gap conflict."""
    plus = seq(ref("expr"), "+", ref("expr"))
    minus = seq(ref("expr"), "-", ref("expr"))
    times = seq(ref("expr"), "*", ref("expr"))
    divide = seq(ref("expr"), "/", ref("expr"))
    power = seq(ref("expr"), "^", ref("expr"))
    unary = seq("-", ref("expr"))

    members = []
    if precedence:
        members += [
            prec_left(ADD, plus),
            prec_left(ADD, minus),
            prec_left(MUL, times),
            prec_left(MUL, divide),
            prec_right(POW, power),
            prec(UNARY, unary),
        ]
    else:
        members += [plus, minus, times, divide, power, unary]
    members.append(ref("atom"))

    g.rule("expr", choice(*members))


def _source_rule(g: Grammar) -> None:
    # 0+ statements (REPEAT), matching the hand-written reference
    g.rule("source_file", repeat(ref("statement")))


def _extras(g: Grammar) -> None:
    # Comments MUST be a named rule referenced via SYMBOL in extras (C-grammar
    # style). Bare inline PATTERN/TOKEN extras starting with `/` lose to the
    # `/` division token in the lexer and never lex as comments (verified).
    g.rule("comment", token(choice(
        seq("//", pattern(r"(\\+(.|\r?\n)|[^\\\n])*")),
        seq("/*", pattern(r"[^*]*\*+([^/*][^*]*\*+)*"), "/"),
    )))
    g.extra(pattern(r"\s"))
    g.extra(ref("comment"))


def _base() -> Grammar:
    g = Grammar("spike")
    _lexical_rules(g)
    _atom_rule(g)
    _extras(g)
    return g


def conflict_dangling_else() -> Grammar:
    g = _base()
    _expression_rules(g, precedence=True)
    _statement_rules(g, resolve_else=None)   # <-- the deliberate ambiguity
    _source_rule(g)
    return g


def conflict_precedence_gap() -> Grammar:
    g = _base()
    _expression_rules(g, precedence=False)   # <-- the deliberate precedence gap
    _statement_rules(g, resolve_else="left")
    _source_rule(g)
    return g


def fixed() -> Grammar:
    g = _base()
    _expression_rules(g, precedence=True)
    _statement_rules(g, resolve_else="left")  # dangling else -> PREC_LEFT
    _source_rule(g)
    return g


def intentional_ambiguity() -> Grammar:
    g = fixed()
    g.conflict("if_statement")                # whitelist: keep the ambiguity
    return g
