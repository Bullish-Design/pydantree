"""
Tiny builder DSL for the spike. Emits GrammarModel nodes (grammar_model.py),
recording the Python definition site (file/lineno/source) of every `rule()`
call — that's what the conflict-remapping experiment needs.

Style reference: sketch.py (017). Combinators here are sugar; every operator
lands on the same validated GrammarModel IR.
"""

from __future__ import annotations

import inspect
import linecache
from dataclasses import dataclass
from typing import Callable

from grammar_model import (
    AliasNode, BlankNode, ChoiceNode, FieldNode, GrammarModel,
    ImmediateTokenNode, PatternNode, PrecDynamicNode, PrecLeftNode,
    PrecNode, PrecRightNode, Repeat1Node, RepeatNode, Rule, RuleNode,
    SeqNode, StrNode, SymbolNode, TokenNode,
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
    """Thin wrapper so `a + b` (seq) and `a | b` (choice) work, sketch.py style."""

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

    # node access
    def __repr__(self) -> str:
        return f"B({self.node.type})"


# ---------------------------------------------------------------------------
# the Grammar registry
# ---------------------------------------------------------------------------

class Grammar:
    """Registry of named rules + grammar options, with source-site recording."""

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

    # -- authoring ----------------------------------------------------------
    def start(self, name: str) -> "Grammar":
        """Declare the start rule. NOTE: this CLI version (0.25.3) has NO `start`
        field in grammar.json — the start rule is the FIRST entry of `rules`
        (Symbol index 0 in the generated parser). We emit the start rule first.
        """
        self._start = name
        return self

    def rule(self, name: str, body: B, *, hidden: bool = False,
             inline: bool = False, supertype: bool = False) -> "Grammar":
        """Register `name -> body`, recording the call site for conflict remapping."""
        if hidden:
            if not name.startswith("_"):
                name = f"_{name}"
        if name in self.rules:
            raise ValueError(f"duplicate rule {name!r}")
        self.rules[name] = body.node
        self.sites[name] = _caller_site(depth=2)
        if inline:
            self._inline.append(name)
        if supertype:
            self._supertypes.append(name)
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
        """Declarative precedence ordering (low -> high). Only strings/symbols
        are allowed inside, mirroring the CLI's `precedences` schema."""
        self._precedences.append([StrNode(value=n) for n in names])
        return self

    def external(self, x: "B | Rule | str") -> "Grammar":
        self._externals.append(as_node(x))
        return self

    # -- emission -----------------------------------------------------------
    def build(self) -> GrammarModel:
        # The start rule must be FIRST in the emitted `rules` map — the CLI
        # treats the first rule as the grammar root (there is no `start` field
        # in this CLI version) and silently prunes unreachable rules.
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
        )

    def emit_json(self, path: str) -> None:
        import json
        model = self.build()
        with open(path, "w") as f:
            # exclude_none: keep grammar.json clean (CLI treats missing as None)
            f.write(model.model_dump_json(indent=2, exclude_none=True))
        # sanity: the file must parse as JSON
        json.load(open(path))

    def site(self, rule_name: str) -> RuleSite:
        return self.sites[rule_name]
