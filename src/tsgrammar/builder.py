"""
tsgrammar.builder — the authoring DSL that emits Grammar IR nodes.

Every combinator is sugar; every operator lands on the same validated
`tsgrammar.grammar.Rule` nodes. `Grammar` is a registry of named rules +
grammar-level options that records the Python definition site (`file`,
`lineno`, source line) of every `rule()` call — grammar.json carries no source
positions, so this recording is what makes conflict remapping
(`tsgrammar.conflicts`) able to point at the author's Python source.

Public surface (module level): Grammar, rule (the combinator), seq, choice,
repeat, repeat1, opt, field, token, tok, immediate_token, ref, pattern, alias,
prec, prec_left, prec_right, prec_dynamic, blank.

Notes:

- `opt(x)` emits `CHOICE(x, BLANK)` — grammar.json has no OPTIONAL node.
- `+` concatenates (SEQ, flattening nested seqs), `|` alternates (CHOICE,
  flattening), `.star()/.plus()/.opt()` add repetition.
- `prec*` accept an int or a precedence-name string; `precedence_ordering`
  declares the named ladder (low -> high). Mixing named and integer
  precedence in one rule is a warning target for the analyzer (§4.5).
- Hidden rules: `g.rule("name", body, hidden=True)` — the DSL renames to a
  leading underscore if needed (tree-sitter's hidden-rule convention) and
  records a visible alias name.
"""

from __future__ import annotations

import inspect
import linecache
from dataclasses import dataclass
from pathlib import Path

from .grammar import (
    AliasNode, BlankNode, ChoiceNode, FieldNode, Grammar as GrammarModel,
    ImmediateTokenNode, PatternNode, PrecDynamicNode, PrecLeftNode,
    PrecNode, PrecRightNode, Repeat1Node, RepeatNode, ReservedNode, Rule,
    RuleNode, SeqNode, StrNode, SymbolNode, TokenNode,
)


# ---------------------------------------------------------------------------
# definition-site recording
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuleSite:
    """Where a rule was defined in the author's Python source."""
    file: str
    lineno: int
    source: str  # the offending line, for error messages

    def __str__(self) -> str:
        return f"{self.file}:{self.lineno}: {self.source.strip()}"


def _caller_site(depth: int = 2) -> RuleSite:
    """Capture the call site of the DSL entry point (file/lineno/source)."""
    frame = inspect.currentframe()
    try:
        for _ in range(depth):
            frame = frame.f_back  # type: ignore[union-attr]
        fname = frame.f_code.co_filename  # type: ignore[union-attr]
        lineno = frame.f_lineno  # type: ignore[union-attr]
        source = linecache.getline(fname, lineno).rstrip("\n")
        return RuleSite(fname, lineno, source)
    finally:
        del frame


# ---------------------------------------------------------------------------
# node constructors (return Rule nodes directly; thin B wrapper for operators)
# ---------------------------------------------------------------------------

Node = Rule  # type alias used by the DSL


def as_node(x: "B | Rule | str") -> Rule:
    if isinstance(x, B):
        return x.node
    if isinstance(x, str):
        return StrNode(value=x)
    if isinstance(x, RuleNode):
        return x
    raise TypeError(f"cannot build a rule node from {type(x).__name__}")


def blank() -> B:
    return B(BlankNode())


def ref(name: str) -> B:
    return B(SymbolNode(name=name))


def seq(*parts: "B | Rule | str") -> B:
    members = []
    for p in parts:
        node = as_node(p)
        if isinstance(node, SeqNode):
            members.extend(node.members)
        else:
            members.append(node)
    return B(SeqNode(members=members))


def choice(*parts: "B | Rule | str") -> B:
    members = []
    for p in parts:
        node = as_node(p)
        if isinstance(node, ChoiceNode):
            members.extend(node.members)
        else:
            members.append(node)
    return B(ChoiceNode(members=members))


def repeat(x: "B | Rule | str") -> B:
    return B(RepeatNode(content=as_node(x)))


def repeat1(x: "B | Rule | str") -> B:
    return B(Repeat1Node(content=as_node(x)))


def opt(x: "B | Rule | str") -> B:
    """opt(x) is sugar for choice(x, BLANK) — grammar.json has no OPTIONAL node."""
    return B(ChoiceNode(members=[as_node(x), BlankNode()]))


def field(name: str, x: "B | Rule | str") -> B:
    return B(FieldNode(name=name, content=as_node(x)))


def token(x: "B | Rule | str") -> B:
    return B(TokenNode(content=as_node(x)))


# `tok` is the tree-sitter grammar.js name for token(); both work.
tok = token


def immediate_token(x: "B | Rule | str") -> B:
    return B(ImmediateTokenNode(content=as_node(x)))


def pattern(value: str, flags: str | None = None) -> B:
    return B(PatternNode(value=value, flags=flags))


def alias(value: str, named: bool, x: "B | Rule | str") -> B:
    return B(AliasNode(value=value, named=named, content=as_node(x)))


def prec(value: int | str, x: "B | Rule | str") -> B:
    return B(PrecNode(value=value, content=as_node(x)))


def prec_left(value: int | str, x: "B | Rule | str") -> B:
    return B(PrecLeftNode(value=value, content=as_node(x)))


def prec_right(value: int | str, x: "B | Rule | str") -> B:
    return B(PrecRightNode(value=value, content=as_node(x)))


def prec_dynamic(value: int, x: "B | Rule | str") -> B:
    return B(PrecDynamicNode(value=value, content=as_node(x)))


class B:
    """Thin wrapper so `a + b` (seq) and `a | b` (choice) work."""

    __slots__ = ("node",)

    def __init__(self, node: Rule):
        self.node = node

    # a + b  ->  sequence (flattening nested seqs)
    def __add__(self, other: "B | Rule | str") -> "B":
        left = self.node.members if isinstance(self.node, SeqNode) else [self.node]
        right_node = as_node(other)
        right = right_node.members if isinstance(right_node, SeqNode) else [right_node]
        return B(SeqNode(members=[*left, *right]))

    # a | b  ->  choice (flattening)
    def __or__(self, other: "B | Rule | str") -> "B":
        left = self.node.members if isinstance(self.node, ChoiceNode) else [self.node]
        right_node = as_node(other)
        right = right_node.members if isinstance(right_node, ChoiceNode) else [right_node]
        return B(ChoiceNode(members=[*left, *right]))

    # sugar methods
    def opt(self) -> "B":
        return opt(self)

    def star(self) -> "B":
        return repeat(self)

    def plus(self) -> "B":
        return repeat1(self)

    def capture(self, name: str) -> "B":
        return field(name, self)

    def __repr__(self) -> str:
        return f"B({self.node.type})"


# ---------------------------------------------------------------------------
# the Grammar registry
# ---------------------------------------------------------------------------

class Grammar:
    """Registry of named rules + grammar options, with source-site recording.

    Authoring surface: rule(), start(), word(), extra(), conflict(),
    precedence_ordering(), external(), reserved_word(). `build()` returns the
    serializable Grammar IR with the start rule reordered to FIRST (the CLI
    treats the first rule as the grammar root and silently prunes everything
    unreachable from it).
    """

    def __init__(self, name: str):
        self.name = name
        self.rules: dict[str, Rule] = {}
        self.sites: dict[str, RuleSite] = {}
        self._start: str | None = None
        self._word: str | None = None
        self._extras: list[Rule] = []
        self._conflicts: list[list[str]] = []
        self._inline: list[str] = []
        self._supertypes: list[str] = []
        self._externals: list[Rule] = []
        self._precedences: list[list[Rule]] = []
        self._reserved: dict[str, list[Rule]] = {}

    # -- authoring ----------------------------------------------------------
    def start(self, name: str) -> "Grammar":
        """Declare the start rule. There is no `start` field in grammar.json
        (0.25.3) — the start rule is the FIRST entry of `rules` (Symbol index
        0). We reorder emission so the start rule is first."""
        self._start = name
        return self

    def rule(self, name: str, body: "B | Rule | str", *,
             hidden: bool = False, inline: bool = False,
             supertype: bool = False, alias: str | None = None) -> "Grammar":
        """Register `name -> body`, recording the call site for conflict
        remapping.

        - hidden: rename to `_<name>` if not already underscore-prefixed
          (tree-sitter's hidden-rule convention).
        - inline: add to the grammar-level `inline` list (rule is inlined into
          its references — the CLI makes the rule invisible to the CST).
        - supertype: add to the grammar-level `supertypes` list (a named
          supertype over the rule's subtypes).
        - alias: add an `inline` entry under an alias name (convenience for
          the common `inline` + rename pattern).
        """
        if hidden:
            if not name.startswith("_"):
                name = f"_{name}"
        if name in self.rules:
            raise ValueError(f"duplicate rule {name!r}")
        self.rules[name] = as_node(body)
        self.sites[name] = _caller_site(depth=2)
        if inline:
            self._inline.append(name)
        if supertype:
            self._supertypes.append(name)
        if alias:
            self._inline.append(alias)
        return self

    def word(self, rule_name: str) -> "Grammar":
        """Declare the word token rule (keyword extraction; avoids
        keyword/identifier conflicts). The referenced rule must be a token."""
        self._word = rule_name
        return self

    def extra(self, x: "B | Rule | str") -> "Grammar":
        self._extras.append(as_node(x))
        return self

    def conflict(self, *rule_names: str) -> "Grammar":
        """Whitelist an intentional ambiguity between the named rules."""
        self._conflicts.append(list(rule_names))
        return self

    def precedence_ordering(self, *names: str) -> "Grammar":
        """Declare a named precedence ordering, **highest first** (descending)
        — mirroring the CLI's `precedences` schema (STRING/SYMBOL entries only;
        the first entry binds tightest, per tree-sitter's own test grammars).
        Phase-3 will sugar this with a ladder helper; here it is raw."""
        self._precedences.append([StrNode(value=n) for n in names])
        return self

    def external(self, x: "B | Rule | str") -> "Grammar":
        """Declare an external token (provided by a C scanner at runtime).
        No scanner authoring here — the IR accepts the declaration; the
        pipeline compiles a user-supplied scanner.c if one is present."""
        self._externals.append(as_node(x))
        return self

    def reserved_word(self, context_name: str, x: "B | Rule | str") -> "Grammar":
        """Declare a reserved word set: when `context_name` is active, the
        given rule(s) are disabled from matching (tree-sitter 0.25+)."""
        self._reserved.setdefault(context_name, []).append(as_node(x))
        return self

    # -- emission -----------------------------------------------------------
    def build(self) -> GrammarModel:
        """Build the serializable Grammar IR.

        The start rule is reordered to FIRST — the CLI treats the first rule
        as the grammar root (no `start` field in this CLI version) and
        silently prunes unreachable rules.
        """
        start = self._start or "source_file"
        if start not in self.rules:
            raise ValueError(f"start rule {start!r} is not defined")
        ordered = {start: self.rules[start]}
        ordered.update({n: r for n, r in self.rules.items() if n != start})
        return GrammarModel(
            name=self.name,
            rules=ordered,
            precedences=self._precedences,
            conflicts=self._conflicts,
            externals=self._externals,
            extras=self._extras,
            inline=self._inline,
            supertypes=self._supertypes,
            word=self._word,
            reserved=self._reserved,
        )

    def emit_json(self, path: str) -> None:
        self.build().emit_json(path)

    def emit_bundle(self, dirpath) -> Path:
        return self.build().emit_bundle(dirpath)

    def site(self, rule_name: str) -> RuleSite:
        return self.sites[rule_name]


# module-level constructor alias (kickoff surface: `Grammar`)
def grammar(name: str) -> Grammar:
    return Grammar(name)
