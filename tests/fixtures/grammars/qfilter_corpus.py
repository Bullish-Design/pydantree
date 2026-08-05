"""qfilter corpus — Run 1 of the Phase-5 experiment: the corpus-testing
harness bite on the Phase-3 qfilter grammar (authored entirely through the
pydantree_sitter_grammar DSL + ExpressionGrammar).

The corpus is the author's semantic contract for the grammar. Two layers:

  * EXPR_CASES — expression CST shapes in the *compact* style (the
    Phase-3A semantic-smoke format: the first `expr` node renders as
    bare parens, named nodes as kind(...), anonymous tokens as text).
    This is the smoke seed generalized: the 5 seed cases plus chain /
    associativity / comparison cases that pin the ladder's semantics.

  * STMT_CASES — full-document CST shapes in the *sexp* style
    (tree-sitter-canonical: named nodes + field labels + anonymous
    tokens as 'text'). Statement shapes (assign/let/if/else/fn/expr)
    and edge cases (dangling else, comments, parens, nesting).

Hand-authored expected values (2026-08-02) from the grammar's intended
semantics — verified by hand against the ladder (postfix > pow > unary >
mul > add > compare > not > and > or) and the statement rules.

The corpus caught a real latent bug during authoring: qfilter's if_stmt
`then:`/`else:` used `statement`, which did not include `block` — so
`if (a) { ... }` was a parse ERROR even though the grammar generated
clean. Fixed by adding `block` to the statement supertype; the
if_else_blocks / dangling_else / nested_block cases pin it.
"""

from __future__ import annotations

import pydantree_sitter_grammar as tg
from pydantree_sitter_grammar.corpus import Corpus, corpus_case

# ---------------------------------------------------------------------------
# expression shapes (compact style, first `expr` node) — the smoke seed +
# the chain/associativity/compare cases the 5-case seed cannot reach
# ---------------------------------------------------------------------------

EXPR_CASES = [
    # -- the smoke seed (probe-2 table, pinned verbatim) ------------------
    corpus_case("-a ^ b;",
                "(- ((identifier) ^ (identifier)))",
                name="unary looser than pow", selector="expr"),
    corpus_case("-f(x);",
                "(- ((identifier) ( args((identifier)) )))",
                name="postfix tighter than unary", selector="expr"),
    corpus_case("a.b.c;",
                "(((identifier) . identifier) . identifier)",
                name="member chaining", selector="expr"),
    corpus_case("f(x)(y);",
                "(((identifier) ( args((identifier)) )) ( args((identifier)) ))",
                name="call chaining", selector="expr"),
    corpus_case("-a or b;",
                "((- (identifier)) or (identifier))",
                name="unary vs or (Phase-2 canonical)", selector="expr"),
    # -- chains + associativity (NOT reachable from the 5-case seed) ------
    corpus_case("1 + 2 * 3;",
                "((number) + ((number) * (number)))",
                name="mul tighter than add", selector="expr"),
    corpus_case("1 + 2 + 3;",
                "(((number) + (number)) + (number))",
                name="+ left-associative (chain)", selector="expr"),
    corpus_case("2 ^ 3 ^ 4;",
                "((number) ^ ((number) ^ (number)))",
                name="^ right-associative (chain)", selector="expr"),
    corpus_case("not a == b;",
                "(not ((identifier) == (identifier)))",
                name="not looser than compare", selector="expr"),
    corpus_case("a * -b;",
                "((identifier) * (- (identifier)))",
                name="unary tighter than mul", selector="expr"),
    corpus_case("a.b + c;",
                "(((identifier) . identifier) + (identifier))",
                name="member tighter than add", selector="expr"),
    corpus_case("a.b ^ c;",
                "(((identifier) . identifier) ^ (identifier))",
                name="member tighter than pow", selector="expr"),
    corpus_case("f(x) + 1;",
                "(((identifier) ( args((identifier)) )) + (number))",
                name="call tighter than add", selector="expr"),
    corpus_case("-a.b;",
                "(- ((identifier) . identifier))",
                name="member tighter than unary", selector="expr"),
    corpus_case("-f(x) + 1;",
                "((- ((identifier) ( args((identifier)) ))) + (number))",
                name="combined unary/call/add", selector="expr"),
    corpus_case("1 < 2 + 3;",
                "((number) < ((number) + (number)))",
                name="compare looser than add", selector="expr"),
    corpus_case("a == b == c;",
                "(((identifier) == (identifier)) == (identifier))",
                name="compare left-associative (chain)", selector="expr"),
    corpus_case("a.b(x);",
                "(((identifier) . identifier) ( args((identifier)) ))",
                name="member then call", selector="expr"),
    corpus_case("(-a)^b;",
                "((( (- (identifier)) )) ^ (identifier))",
                name="parens beat pow", selector="expr"),
]

# ---------------------------------------------------------------------------
# statement shapes (sexp style, whole document) — what the smoke seed
# (expression-only) cannot reach
# ---------------------------------------------------------------------------

STMT_CASES = [
    corpus_case("x = 1 + 2;",
                "(source_file (assign name: (identifier) '=' "
                "value: (expr (expr (number)) '+' (expr (number))) ';'))",
                name="assign with binary value"),
    corpus_case("let name = f(a, b);",
                "(source_file (let_stmt 'let' name: (identifier) '=' "
                "value: (expr (expr (identifier)) '(' "
                "(args (expr (identifier)) ',' (expr (identifier))) ')') ';'))",
                name="let with a call value"),
    corpus_case("if (a) { b = 1; } else { b = 2; }",
                "(source_file (if_stmt 'if' cond: '(' cond: (expr (identifier)) "
                "cond: ')' then: (block '{' (assign name: (identifier) '=' "
                "value: (expr (number)) ';') '}') 'else' "
                "else: (block '{' (assign name: (identifier) '=' "
                "value: (expr (number)) ';') '}')))",
                name="if/else with block bodies"),
    corpus_case("if (a) if (b) { c; } else { d; }",
                "(source_file (if_stmt 'if' cond: '(' cond: (expr (identifier)) "
                "cond: ')' then: (if_stmt 'if' cond: '(' cond: (expr (identifier)) "
                "cond: ')' then: (block '{' (expr_stmt (expr (identifier)) ';') '}') "
                "'else' else: (block '{' (expr_stmt (expr (identifier)) ';') '}'))))",
                name="dangling else binds to the INNER if"),
    corpus_case("fn foo(x, y) { x + y; };",
                "(source_file (fn_def 'fn' name: (identifier) '(' "
                "(params param: (identifier) ',' param: (identifier)) ')' "
                "body: (block '{' (expr_stmt (expr (expr (identifier)) '+' "
                "(expr (identifier))) ';') '}') ';'))",
                name="function definition with params + block body"),
    corpus_case("x;",
                "(source_file (expr_stmt (expr (identifier)) ';'))",
                name="bare expression statement"),
    corpus_case("-a ^ b;",
                "(source_file (expr_stmt (expr '-' (expr (expr (identifier)) "
                "'^' (expr (identifier)))) ';'))",
                name="statement-level unary-pow (same semantics as the smoke)"),
    corpus_case("f(a)(b);",
                "(source_file (expr_stmt (expr (expr (expr (identifier)) '(' "
                "(args (expr (identifier))) ')') '(' (args (expr (identifier))) "
                "')') ';'))",
                name="statement-level call chaining"),
    corpus_case("(-a)^b;",
                "(source_file (expr_stmt (expr (expr '(' (expr '-' "
                "(expr (identifier))) ')') '^' (expr (identifier))) ';'))",
                name="parens primary"),
    corpus_case("if (a) { if (b) { x; } }",
                "(source_file (if_stmt 'if' cond: '(' cond: (expr (identifier)) "
                "cond: ')' then: (block '{' (if_stmt 'if' cond: '(' "
                "cond: (expr (identifier)) cond: ')' then: (block '{' "
                "(expr_stmt (expr (identifier)) ';') '}')) '}')))",
                name="nested if in a block"),
    # -- edge cases ---------------------------------------------------------
    corpus_case("", "(source_file)", name="empty document"),
    corpus_case("// just a comment\n", "(source_file (comment))",
                name="comment-only document"),
    corpus_case("x = 1; // tail\n",
                "(source_file (assign name: (identifier) '=' "
                "value: (expr (number)) ';') (comment))",
                name="trailing comment (extra)"),
]


def expression_corpus() -> Corpus:
    return Corpus(EXPR_CASES, name="qfilter-expressions", style="compact")


def statement_corpus() -> Corpus:
    return Corpus(STMT_CASES, name="qfilter-statements", style="sexp")


def build() -> tg.Grammar:
    import qfilter  # the Phase-3 grammar (with the block fix)
    return qfilter.build()
