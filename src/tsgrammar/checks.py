"""
tsgrammar.checks — author-time static analysis.

Each check mirrors an error the CLI would eventually produce (or a silent
footgun the CLI would hide), but catches it in Python with the author's DSL
source site attached — the cheap feedback loop before the slow Rust generate.

Checks (mirroring Phase-0 findings + §4.5):

1.  undefined symbols      — SYMBOL refs to a rule that doesn't exist.
2.  unused / unreachable   — rules not reachable from the start rule, not
                            referenced by extras/externals, and not the word
                            rule. The CLI SILENTLY PRUNES these (parse_grammar
                            `variable_is_used`) along with their entries in
                            conflicts/inline/supertypes/precedences — this is
                            the "successful generate, missing grammar" trap.
3.  nullable in repeat     — nullable content inside REPEAT/REPEAT1 is an
                            infinite-loop hazard (the CLI desugars REPEAT to
                            choice(repeat(x), BLANK) internally and never
                            errors).
4.  SYMBOL inside TOKEN    — the CLI raises `UnexpectedRule` (parse_grammar
                            `parse_rule` with is_token=true). IMMEDIATE_TOKEN
                            propagates the *current* is_token flag (CLI quirk)
                            so a bare top-level SYMBOL there is tolerated.
5.  duplicate rule names   — caught at registration (builder) and checked on
                            the IR (impossible in a dict, but verified).
6.  PATTERN flags          — only `i` is supported; `u`/`v` are silently
                            ignored, anything else warns on stderr.
7.  precedence mixing      — named (string) and integer precedence do not
                            compare against each other at conflict time;
                            mixing them in one rule is a warning.
8.  extras x token overlap — an *inline* extra whose first-set prefix overlaps
                            a token prefix never lexes as the extra (Phase-0:
                            comment-vs-`/`). The fix is a named rule referenced
                            via SYMBOL in extras — those are exempt.
9.  start-rule existence   — the declared start rule must be defined.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .builder import B, Grammar as BuilderGrammar, RuleSite
from .grammar import (
    AliasNode, BlankNode, ChoiceNode, FieldNode, Grammar as GrammarModel,
    ImmediateTokenNode, PatternNode, PrecDynamicNode, PrecLeftNode, PrecNode,
    PrecRightNode, Repeat1Node, RepeatNode, ReservedNode, Rule, RuleNode,
    SeqNode, StrNode, SymbolNode, TokenNode,
)

VALID_PATTERN_FLAGS = frozenset("i")


@dataclass(frozen=True)
class CheckIssue:
    """A diagnostic from the analyzer. `site` is the DSL definition site when
    known (builder-analyzed grammars); imported IR grammars have no sites."""
    rule: str
    message: str
    site: RuleSite | None = None
    warning: bool = False

    def __str__(self) -> str:
        loc = f" at {self.site}" if self.site else ""
        return f"[{self.rule}]{loc} {self.message}"

    @property
    def severity(self) -> str:
        return "warning" if self.warning else "error"


# ---------------------------------------------------------------------------
# tree walking helpers
# ---------------------------------------------------------------------------

def iter_children(node: RuleNode) -> Iterable[RuleNode]:
    """Yield direct child rule nodes (mirrors the IR node shapes)."""
    for attr in ("content",):
        c = getattr(node, attr, None)
        if isinstance(c, RuleNode):
            yield c
    for attr in ("members",):
        c = getattr(node, attr, None)
        if isinstance(c, list):
            yield from c


def iter_all(node: RuleNode) -> Iterable[RuleNode]:
    """DFS over the whole rule tree, cycles-safe via node id."""
    seen: set[int] = set()

    def walk(n: Rule):
        if id(n) in seen:
            return
        seen.add(id(n))
        yield n
        for c in iter_children(n):
            yield from walk(c)

    return walk(node)


def find_symbols(node: RuleNode) -> Iterable[SymbolNode]:
    for n in iter_all(node):
        if isinstance(n, SymbolNode):
            yield n


def find_tokens(node: RuleNode) -> Iterable[TokenNode | ImmediateTokenNode]:
    for n in iter_all(node):
        if isinstance(n, TokenNode | ImmediateTokenNode):
            yield n


# ---------------------------------------------------------------------------
# grammar abstraction (builder Grammar or IR Grammar)
# ---------------------------------------------------------------------------

class _GrammarView:
    """Uniform access to either the builder Grammar (with sites) or the IR
    Grammar (imported grammars — no sites)."""

    def __init__(self, g):
        if isinstance(g, BuilderGrammar):
            self._g = g
            self._sites = g.sites
        elif isinstance(g, GrammarModel):
            self._g = g
            self._sites = {}
        else:
            raise TypeError(
                f"expected tsgrammar.builder.Grammar or tsgrammar.grammar.Grammar, "
                f"got {type(g).__name__}")
        self.name = self._g.name

    @property
    def rules(self) -> dict[str, Rule]:
        return self._g.rules if isinstance(self._g, BuilderGrammar) else self._g.rules

    @property
    def extras(self) -> list[Rule]:
        return self._g.extras if isinstance(self._g, GrammarModel) else self._g._extras

    @property
    def externals(self) -> list[Rule]:
        return self._g.externals if isinstance(self._g, GrammarModel) else self._g._externals

    @property
    def word(self) -> str | None:
        return self._g.word if isinstance(self._g, GrammarModel) else self._g._word

    @property
    def start(self) -> str:
        if isinstance(self._g, GrammarModel):
            return self._g.start_rule
        return self._g._start or "source_file"

    def site(self, rule_name: str) -> RuleSite | None:
        return self._sites.get(rule_name)


def _view(g) -> _GrammarView:
    return g if isinstance(g, _GrammarView) else _GrammarView(g)


# ---------------------------------------------------------------------------
# structural properties
# ---------------------------------------------------------------------------

def _nullable(node: Rule, view: _GrammarView, seen: set[str]) -> bool:
    """Nullable computation (cycle-safe). REPEAT is nullable, REPEAT1 is not,
    BLANK is nullable, CHOICE is nullable if any member is, SEQ if all are."""
    if isinstance(node, BlankNode):
        return True
    if isinstance(node, RepeatNode):
        return True
    if isinstance(node, Repeat1Node):
        return False
    if isinstance(node, ChoiceNode):
        return any(_nullable(m, view, seen) for m in node.members)
    if isinstance(node, SeqNode):
        return all(_nullable(m, view, seen) for m in node.members)
    if isinstance(node, SymbolNode):
        if node.name in seen or node.name not in view.rules:
            return False  # recursive/unknown: assume non-nullable (conservative)
        seen.add(node.name)
        result = _nullable(view.rules[node.name], view, seen)
        seen.remove(node.name)
        return result
    return False


def _first_set(node: Rule, view: _GrammarView, seen: set[str]) -> set[str]:
    """First set as a set of terminal keys: STRING values as-is, PATTERN
    values as-is. Follows SYMBOL refs (cycle-safe, conservative empty on
    cycle). BLANK/empty contributes nothing."""
    if isinstance(node, StrNode):
        return {node.value}
    if isinstance(node, PatternNode):
        return {node.value}
    if isinstance(node, BlankNode):
        return set()
    if isinstance(node, ChoiceNode):
        out: set[str] = set()
        for m in node.members:
            out |= _first_set(m, view, seen)
        return out
    if isinstance(node, SeqNode):
        out = set()
        for m in node.members:
            out |= _first_set(m, view, seen)
            if not _nullable(m, view, set()):
                break
        return out
    if isinstance(node, RepeatNode | Repeat1Node):
        return _first_set(node.content, view, seen)
    if isinstance(node, SymbolNode):
        if node.name in seen or node.name not in view.rules:
            return set()
        seen.add(node.name)
        result = _first_set(view.rules[node.name], view, seen)
        seen.remove(node.name)
        return result
    # FIELD / ALIAS / PREC* / TOKEN / IMMEDIATE_TOKEN / RESERVED
    content = getattr(node, "content", None)
    if isinstance(content, RuleNode):
        return _first_set(content, view, seen)
    return set()


def _first_literal_chars(terminal_key: str) -> set[str]:
    """The literal first character(s) of a terminal key (a STRING value or a
    PATTERN value), for prefix-overlap detection. Conservative: returns a
    small set of chars that the terminal can *definitely* start with, empty if
    the key starts with a construct we can't pin down (anchors, classes,
    escapes, metachars)."""
    if terminal_key == "":
        return set()
    # STRING values come through as-is; a PATTERN typically starts with a
    # metachar. Try the first literal character only when it's unambiguous.
    c = terminal_key[0]
    if c in r"\^.*+?(){}[]|$":
        return set()
    return {c}


# ---------------------------------------------------------------------------
# the checks
# ---------------------------------------------------------------------------

def check_undefined_symbols(g) -> list[CheckIssue]:
    view = _view(g)
    external_names = {s.name for ext in view.externals for s in find_symbols(ext)}
    issues = []
    for name, rule in view.rules.items():
        for s in find_symbols(rule):
            if s.name not in view.rules and s.name not in external_names:
                issues.append(CheckIssue(
                    name, f"undefined Symbol ref {s.name!r}", view.site(name)))
    return issues


def check_unused_rules(g) -> list[CheckIssue]:
    """Rules not reachable from the start rule, not referenced by extras or
    externals, and not the word rule — the CLI prunes these SILENTLY."""
    view = _view(g)

    def referenced(rule: Rule, target: str) -> bool:
        return any(s.name == target for s in find_symbols(rule))

    used: set[str] = set()
    frontier = [view.start]
    while frontier:
        name = frontier.pop()
        if name in used:
            continue
        if name not in view.rules:
            continue
        used.add(name)
        for s in find_symbols(view.rules[name]):
            if s.name in view.rules and s.name not in used:
                frontier.append(s.name)

    # references from extras / externals count as usage
    for extra in view.extras:
        used |= {s.name for s in find_symbols(extra) if s.name in view.rules}
    for ext in view.externals:
        used |= {s.name for s in find_symbols(ext) if s.name in view.rules}

    issues = []
    for name in view.rules:
        if name not in used and name != view.word:
            issues.append(CheckIssue(
                name,
                "unused rule — the CLI silently prunes unreachable rules "
                "(and their conflicts/inline/supertypes/precedences entries); "
                "define `start(...)` or reference it from an extras/externals "
                "rule if this is intentional",
                view.site(name)))
    return issues


def check_nullable_in_repeat(g) -> list[CheckIssue]:
    view = _view(g)
    issues = []
    for name, rule in view.rules.items():
        for n in iter_all(rule):
            if isinstance(n, RepeatNode | Repeat1Node) and _nullable(n.content, view, set()):
                issues.append(CheckIssue(
                    name,
                    f"{n.type} content is nullable — infinite-loop hazard",
                    view.site(name)))
    return issues


def check_symbol_inside_token(g) -> list[CheckIssue]:
    """SYMBOL inside TOKEN is an error in the CLI (`UnexpectedRule`).
    IMMEDIATE_TOKEN propagates the current is_token flag (CLI quirk) so a bare
    top-level SYMBOL there is tolerated by the CLI — we mirror that: only TOKEN
    (and IMMEDIATE_TOKEN nested inside a TOKEN) is checked."""
    view = _view(g)
    issues = []
    for name, rule in view.rules.items():
        for n in iter_all(rule):
            if isinstance(n, TokenNode):
                for s in find_symbols(n.content):
                    issues.append(CheckIssue(
                        name, f"SYMBOL {s.name!r} inside TOKEN — not allowed",
                        view.site(name)))
    return issues


def check_pattern_flags(g) -> list[CheckIssue]:
    view = _view(g)
    issues = []
    for name, rule in view.rules.items():
        for n in iter_all(rule):
            if isinstance(n, PatternNode) and n.flags:
                bad = [f for f in n.flags if f not in VALID_PATTERN_FLAGS]
                if bad:
                    issues.append(CheckIssue(
                        name,
                        f"PATTERN flags {n.flags!r}: only 'i' is supported "
                        f"({'/'.join(bad)} is/are not); 'u'/'v' are silently "
                        f"ignored by the generator",
                        view.site(name)))
    return issues


def check_precedence_mixing(g) -> list[CheckIssue]:
    """Named (string) and integer precedence do not compare against each other
    at conflict time — mixing them inside one rule's alternatives is a warning
    (Phase-0 finding §1.5)."""
    view = _view(g)
    issues = []
    for name, rule in view.rules.items():
        for n in iter_all(rule):
            if isinstance(n, ChoiceNode):
                kinds = {_prec_kind(m) for m in n.members if _prec_kind(m)}
                if len(kinds) > 1:
                    issues.append(CheckIssue(
                        name,
                        "mixed named and integer precedence in one CHOICE — "
                        "they do not compare against each other at conflict "
                        "time; use all-integer or all-named",
                        view.site(name), warning=True))
    return issues


def _prec_kind(node: RuleNode) -> str | None:
    if isinstance(node, PrecNode | PrecLeftNode | PrecRightNode):
        return "int" if isinstance(node.value, int) else "name"
    return None


def check_extras_token_prefix_overlap(g) -> list[CheckIssue]:
    """An *inline* extra whose first-set prefix overlaps a token's first
    character never lexes as the extra (Phase-0 §1.8: a bare comment pattern
    starting with `/` loses to the division token). Named rules referenced via
    SYMBOL in extras are the documented fix and are exempt."""
    view = _view(g)
    token_firsts: set[str] = set()
    for name, rule in view.rules.items():
        for key in _first_set(rule, view, set()):
            token_firsts |= _first_literal_chars(key)

    issues = []
    for extra in view.extras:
        if isinstance(extra, SymbolNode):
            continue  # named-rule extras are the documented fix — exempt
        for key in _first_set(extra, view, set()):
            chars = _first_literal_chars(key)
            overlap = chars & token_firsts
            if overlap:
                issues.append(CheckIssue(
                    "",
                    "extras first-set overlaps a token prefix "
                    f"({sorted(overlap)}): the extra may never lex. Use a "
                    "named rule + SYMBOL reference in extras (Phase-0 "
                    "comment-vs-`/` hazard), or a distinct prefix",
                    None, warning=True))
                break
    return issues


def check_start_defined(g) -> list[CheckIssue]:
    view = _view(g)
    if view.start not in view.rules:
        return [CheckIssue(
            view.start, f"start rule {view.start!r} is not defined "
            "(declare it with start(...) or define the rule)",
            view.site(view.start))]
    return []


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def run_checks(g) -> list[CheckIssue]:
    """Run every check. Returns errors AND warnings (check `.severity`)."""
    return (
        check_start_defined(g)
        + check_undefined_symbols(g)
        + check_unused_rules(g)
        + check_nullable_in_repeat(g)
        + check_symbol_inside_token(g)
        + check_pattern_flags(g)
        + check_precedence_mixing(g)
        + check_extras_token_prefix_overlap(g)
    )


def errors(g) -> list[CheckIssue]:
    return [i for i in run_checks(g) if i.severity == "error"]


def warnings(g) -> list[CheckIssue]:
    return [i for i in run_checks(g) if i.severity == "warning"]


class GrammarCheckError(Exception):
    """Raised when a grammar fails the analyzer's error-level checks."""

    def __init__(self, issues: list[CheckIssue]):
        self.issues = issues
        super().__init__("\n".join(f"  ! {i}" for i in issues))


def assert_clean(g) -> None:
    """Raise GrammarCheckError unless the grammar passes every error-level
    check (warnings are tolerated)."""
    bad = errors(g)
    if bad:
        raise GrammarCheckError(bad)
