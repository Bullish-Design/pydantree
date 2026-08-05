"""
Cheap static checks for the spike — the trivial ones only (the full analyzer is
Phase 2). Each check mirrors an error the CLI would eventually produce, but
catches it in Python with the author's source site attached.

Easy (implemented here):
  1. undefined Symbol refs        (CLI: silently drops the rule / errors later)
  2. nullable content inside REPEAT / REPEAT1   (CLI: infinite-loop hazard, no error)
  3. SYMBOL inside TOKEN          (CLI: `UnexpectedRule` parse error)
Hard (noted, not implemented — Phase 2):
  - first-set overlap prediction, unused rules, left-recursion reporting,
    precedence name validation, regex-subset validation.
"""

from __future__ import annotations

from dataclasses import dataclass

from builder import Grammar
from grammar_model import (
    RuleNode, Repeat1Node, RepeatNode, StrNode, SymbolNode, TokenNode,
    ImmediateTokenNode, BlankNode, PatternNode, ChoiceNode, SeqNode,
    FieldNode, AliasNode, PrecNode, PrecLeftNode, PrecRightNode,
    PrecDynamicNode, ReservedNode,
)


@dataclass(frozen=True)
class CheckIssue:
    rule: str
    message: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.message}"


def iter_children(node: RuleNode):
    """Yield direct child rule nodes (mirrors the IR node shapes)."""
    for attr in ("content",):
        c = getattr(node, attr, None)
        if isinstance(c, RuleNode):
            yield c
    for attr in ("members",):
        c = getattr(node, attr, None)
        if isinstance(c, list):
            yield from c


def iter_all(node: RuleNode):
    """DFS over the whole rule tree, cycles-safe via node id."""
    seen = set()

    def walk(n: Rule):
        if id(n) in seen:
            return
        seen.add(id(n))
        yield n
        for c in iter_children(n):
            yield from walk(c)

    return walk(node)


def find_symbols(node: RuleNode):
    for n in iter_all(node):
        if isinstance(n, SymbolNode):
            yield n


def find_tokens(node: RuleNode):
    for n in iter_all(node):
        if isinstance(n, TokenNode | ImmediateTokenNode):
            yield n


def is_lexical(node: Rule, g: Grammar) -> bool:
    """True if the rule is a token-ish (lexical) rule: a bare PATTERN/STRING,
    a TOKEN wrap, or a Symbol referencing another lexical rule."""
    if isinstance(node, PatternNode | StrNode | TokenNode):
        return True
    if isinstance(node, SymbolNode):
        if node.name not in g.rules:
            return False
        return is_lexical(g.rules[node.name], g)
    if isinstance(node, ChoiceNode | SeqNode):
        # a choice of strings is lexical once extracted? keep it conservative:
        return False
    return False


def _nullable(node: Rule, g: Grammar, seen: set[str]) -> bool:
    """Nullable computation (cycle-safe). REPEAT is nullable, REPEAT1 is not,
    BLANK is nullable, CHOICE is nullable if any member is, SEQ if all are."""
    if isinstance(node, BlankNode):
        return True
    if isinstance(node, RepeatNode):
        return True
    if isinstance(node, Repeat1Node):
        return False
    if isinstance(node, ChoiceNode):
        return any(_nullable(m, g, seen) for m in node.members)
    if isinstance(node, SeqNode):
        return all(_nullable(m, g, seen) for m in node.members)
    if isinstance(node, SymbolNode):
        if node.name in seen:
            return False  # assume non-nullable for recursive rules (conservative)
        if node.name not in g.rules:
            return False
        seen.add(node.name)
        result = _nullable(g.rules[node.name], g, seen)
        seen.remove(node.name)
        return result
    return False


def check_undefined_symbols(g: Grammar) -> list[CheckIssue]:
    issues = []
    external_names = set()
    for ext in g.build().externals:
        for s in find_symbols(ext):
            external_names.add(s.name)
    for name, rule in g.rules.items():
        for s in find_symbols(rule):
            if s.name not in g.rules and s.name not in external_names:
                issues.append(CheckIssue(name, f"undefined Symbol ref {s.name!r}"))
    return issues


def check_nullable_in_repeat(g: Grammar) -> list[CheckIssue]:
    issues = []
    for name, rule in g.rules.items():
        for n in iter_all(rule):
            if isinstance(n, RepeatNode | Repeat1Node) and _nullable(n.content, g, set()):
                issues.append(CheckIssue(
                    name, f"{n.type} content is nullable — infinite-loop hazard"))
    return issues


def check_symbol_inside_token(g: Grammar) -> list[CheckIssue]:
    """SYMBOL inside TOKEN is an error in the CLI (parse_grammar.rs
    `UnexpectedRule`). IMMEDIATE_TOKEN is exempt at top level (CLI quirk: it
    propagates the *current* is_token flag, not true)."""
    issues = []
    for name, rule in g.rules.items():
        for n in iter_all(rule):
            if isinstance(n, TokenNode):
                for s in find_symbols(n.content):
                    issues.append(CheckIssue(
                        name, f"SYMBOL {s.name!r} inside TOKEN — not allowed"))
    return issues


def run_checks(g: Grammar) -> list[CheckIssue]:
    return (
        check_undefined_symbols(g)
        + check_nullable_in_repeat(g)
        + check_symbol_inside_token(g)
    )
