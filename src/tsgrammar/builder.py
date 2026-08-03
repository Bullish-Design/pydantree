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
    AliasNode,
    BlankNode,
    ChoiceNode,
    FieldNode,
    ImmediateTokenNode,
    PatternNode,
    PrecDynamicNode,
    PrecLeftNode,
    PrecNode,
    PrecRightNode,
    Repeat1Node,
    RepeatNode,
    Rule,
    RuleNode,
    SeqNode,
    StrNode,
    SymbolNode,
    TokenNode,
)
from .grammar import (
    Grammar as GrammarModel,
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


# Per-node definition-site registry. Every node constructor registers its own
# call site here (id(node) -> site); `Grammar.rule()` drains the entries that
# belong to its body into the grammar's `_node_sites`, which the conflict
# remapper uses to point at the exact `seq(...)` alternative, not just the
# `rule(...)` call. Entries are consumed on registration into a rule, so the
# table stays small; a stale entry for a dead node id is harmless (any new node
# reusing that id overwrites it with its own site).
_SITES: dict[int, RuleSite] = {}


def _track(node: Rule) -> Rule:
    """Register the call site of a node constructor. Every combinator calls
    this before returning its node; depth accounts for the combinator frame."""
    _SITES[id(node)] = _caller_site(depth=3)
    return node


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


def _iter_body_nodes(node: RuleNode):
    """DFS over a rule tree (cycles impossible: Symbol refs are leaves)."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        c = getattr(n, "content", None)
        if isinstance(c, RuleNode):
            stack.append(c)
        m = getattr(n, "members", None)
        if isinstance(m, list):
            stack.extend(m)


def as_node(x: B | Rule | str) -> Rule:
    if isinstance(x, B):
        return x.node
    if isinstance(x, str):
        return StrNode(value=x)
    if isinstance(x, RuleNode):
        return x
    raise TypeError(f"cannot build a rule node from {type(x).__name__}")


def blank() -> B:
    return B(_track(BlankNode()))


def ref(name: str) -> B:
    return B(_track(SymbolNode(name=name)))


def seq(*parts: B | Rule | str) -> B:
    members = []
    for p in parts:
        node = as_node(p)
        if isinstance(node, SeqNode):
            members.extend(node.members)
        else:
            members.append(node)
    return B(_track(SeqNode(members=members)))


def choice(*parts: B | Rule | str) -> B:
    members = []
    for p in parts:
        node = as_node(p)
        if isinstance(node, ChoiceNode):
            members.extend(node.members)
        else:
            members.append(node)
    return B(_track(ChoiceNode(members=members)))


def repeat(x: B | Rule | str) -> B:
    return B(_track(RepeatNode(content=as_node(x))))


def repeat1(x: B | Rule | str) -> B:
    return B(_track(Repeat1Node(content=as_node(x))))


def opt(x: B | Rule | str) -> B:
    """opt(x) is sugar for choice(x, BLANK) — grammar.json has no OPTIONAL node."""
    return B(_track(ChoiceNode(members=[as_node(x), _track(BlankNode())])))


def field(name: str, x: B | Rule | str) -> B:
    return B(_track(FieldNode(name=name, content=as_node(x))))


def token(x: B | Rule | str) -> B:
    return B(_track(TokenNode(content=as_node(x))))


# `tok` is the tree-sitter grammar.js name for token(); both work.
tok = token


def immediate_token(x: B | Rule | str) -> B:
    return B(_track(ImmediateTokenNode(content=as_node(x))))


def pattern(value: str, flags: str | None = None) -> B:
    return B(_track(PatternNode(value=value, flags=flags)))


def alias(value: str, named: bool, x: B | Rule | str) -> B:
    """Alias a rule as `value`. GUARD (Phase-2 finding §1.3.3): aliasing a
    bare SEQ aliases every named child (the CLI applies the alias metadata to
    each step) — the canonical pattern is `alias` over a single hidden symbol
    (e.g. `_tuple: alias("tuple", True, ref("_tuple_contents"))`). Wrapping a
    sequence in `token(...)` first is the escape hatch."""
    node = as_node(x)
    if isinstance(node, SeqNode):
        # structural misuse, not a wrong Python type — ValueError is the
        # builder's consistent error for authoring mistakes (see duplicate rule)
        raise ValueError(  # noqa: TRY004
            "alias() over a SEQ aliases every named child (Phase-2 kitsink "
            "footgun). Alias a single hidden symbol instead: "
            "alias('name', True, ref('_contents')) — or wrap the seq in "
            "token(...) to alias it as one token.")
    return B(_track(AliasNode(value=value, named=named, content=node)))


def prec(value: int | str, x: B | Rule | str) -> B:
    return B(_track(PrecNode(value=value, content=as_node(x))))


def prec_left(value: int | str, x: B | Rule | str) -> B:
    return B(_track(PrecLeftNode(value=value, content=as_node(x))))


def prec_right(value: int | str, x: B | Rule | str) -> B:
    return B(_track(PrecRightNode(value=value, content=as_node(x))))


def prec_dynamic(value: int, x: B | Rule | str) -> B:
    return B(_track(PrecDynamicNode(value=value, content=as_node(x))))


class B:
    """Thin wrapper so `a + b` (seq) and `a | b` (choice) work."""

    __slots__ = ("node",)

    def __init__(self, node: Rule):
        self.node = node

    # a + b  ->  sequence (flattening nested seqs)
    def __add__(self, other: B | Rule | str) -> B:
        left = self.node.members if isinstance(self.node, SeqNode) else [self.node]
        right_node = as_node(other)
        right = right_node.members if isinstance(right_node, SeqNode) else [right_node]
        return B(_track(SeqNode(members=[*left, *right])))

    # a | b  ->  choice (flattening)
    def __or__(self, other: B | Rule | str) -> B:
        left = self.node.members if isinstance(self.node, ChoiceNode) else [self.node]
        right_node = as_node(other)
        right = right_node.members if isinstance(right_node, ChoiceNode) else [right_node]
        return B(_track(ChoiceNode(members=[*left, *right])))

    # sugar methods
    def opt(self) -> B:
        return opt(self)

    def star(self) -> B:
        return repeat(self)

    def plus(self) -> B:
        return repeat1(self)

    def capture(self, name: str) -> B:
        return field(name, self)

    def __repr__(self) -> str:
        return f"B({self.node.type})"


# ---------------------------------------------------------------------------
# the Grammar registry
# ---------------------------------------------------------------------------

class Grammar:
    """Registry of named rules + grammar options, with source-site recording.

    Authoring surface: rule(), start(), word(), extra(), conflict(),
    precedence(), precedence_ordering(), external(), reserved_word(),
    ambiguous(). `build()` returns the serializable Grammar IR with the start
    rule reordered to FIRST (the CLI treats the first rule as the grammar root
    and silently prunes everything unreachable from it).

    Phase 3 additions:
    - `precedence(*levels, named=)` returns a `Ladder` (declarative
      precedence levels, ascending integers by default; named mode emits a
      descending `precedence_ordering`).
    - per-production source sites: every combinator call site is recorded and
      drained into `_node_sites` at rule registration, so the conflict
      remapper can point at the exact `seq(...)` alternative.
    - `rule(..., ambiguous=, dynamic=)` synthesizes the intentional-ambiguity
      opt-in (PREC_DYNAMIC wrapper + conflicts whitelist entry).
    - sane-default whitespace extra (`pattern(r"\\s")`, on unless disabled).
    """

    def __init__(self, name: str, *, whitespace: bool = True):
        self.name = name
        self.rules: dict[str, Rule] = {}
        self.sites: dict[str, RuleSite] = {}
        self._node_sites: dict[int, RuleSite] = {}
        self._start: str | None = None
        self._word: str | None = None
        self._extras: list[Rule] = []
        self._conflicts: list[list[str]] = []
        self._inline: list[str] = []
        self._supertypes: list[str] = []
        self._externals: list[Rule] = []
        self._precedences: list[list[Rule]] = []
        self._reserved: dict[str, list[Rule]] = {}
        self._ladders: list[Ladder] = []
        self._whitespace = whitespace
        self._explicit_whitespace = False

    # -- authoring ----------------------------------------------------------
    def start(self, name: str) -> Grammar:
        """Declare the start rule. There is no `start` field in grammar.json
        (0.25.3) — the start rule is the FIRST entry of `rules` (Symbol index
        0). We reorder emission so the start rule is first."""
        self._start = name
        return self

    def rule(self, name: str, body: B | Rule | str, *,
             hidden: bool = False, inline: bool = False,
             supertype: bool = False, alias: str | None = None,
             word: bool = False,
             ambiguous: bool = False, dynamic: int = 1) -> Grammar:
        """Register `name -> body`, recording the call site for conflict
        remapping and draining the per-node combinator sites for
        per-production remapping.

        - hidden: rename to `_<name>` if not already underscore-prefixed
          (tree-sitter's hidden-rule convention).
        - inline: add to the grammar-level `inline` list (rule is inlined into
          its references — the CLI makes the rule invisible to the CST).
        - supertype: add to the grammar-level `supertypes` list (a named
          supertype over the rule's subtypes).
        - alias: add an `inline` entry under an alias name (convenience for
          the common `inline` + rename pattern).
        - word: also declare this rule as the grammar's `word` token
          (keyword extraction — one-liner instead of a separate `word()` call).
        - ambiguous: opt INTO an intentional GLR ambiguity — wraps the body in
          `PREC_DYNAMIC(dynamic, ...)` and whitelists `name` in `conflicts`
          (Phase-2 kitsink proved this exact shape: dangling-else resolves
          greedy at runtime).
        """
        if hidden and not name.startswith("_"):
            name = f"_{name}"
        if name in self.rules:
            raise ValueError(f"duplicate rule {name!r}")
        node = as_node(body)
        self.rules[name] = node
        self.sites[name] = _caller_site(depth=2)
        # drain the per-node combinator sites belonging to this body
        for n in _iter_body_nodes(node):
            site = _SITES.pop(id(n), None)
            if site is not None:
                self._node_sites[id(n)] = site
        if inline:
            self._inline.append(name)
        if supertype:
            self._supertypes.append(name)
        if alias:
            self._inline.append(alias)
        if word:
            if self._word is not None and self._word != name:
                raise ValueError(
                    f"word rule already set to {self._word!r} — cannot also "
                    f"be {name!r}")
            self._word = name
        if ambiguous:
            self.rules[name] = PrecDynamicNode(value=dynamic, content=node)
            self._conflicts.append([name])
        return self

    def replace_rule(self, name: str, body: B | Rule | str,
                     **flags) -> Grammar:
        """Replace an existing rule's body (re-recording the definition site
        and per-node sites). Used by the fix-one-rerun loop and by iterative
        authoring. Flags match `rule()`; ambiguity/word flags are re-applied
        idempotently (the old conflict whitelist entry is replaced)."""
        if name not in self.rules:
            raise ValueError(f"cannot replace unknown rule {name!r}")
        # undo the previous ambiguous wrapper/whitelist so the new body's flags
        # decide
        self._conflicts = [c for c in self._conflicts if c != [name]]
        old = self.rules[name]
        node = as_node(body)
        for n in _iter_body_nodes(node):
            site = _SITES.pop(id(n), None)
            if site is not None:
                self._node_sites[id(n)] = site
        # remove stale per-node sites that belonged to the old body
        old_ids = {id(n) for n in _iter_body_nodes(old)}
        for oid in old_ids:
            self._node_sites.pop(oid, None)
        self.rules[name] = node
        self.sites[name] = _caller_site(depth=2)
        if flags.get("inline") and name not in self._inline:
            self._inline.append(name)
        if flags.get("supertype") and name not in self._supertypes:
            self._supertypes.append(name)
        if flags.get("word"):
            self._word = name
        if flags.get("ambiguous"):
            self.rules[name] = PrecDynamicNode(
                value=flags.get("dynamic", 1), content=node)
            self._conflicts.append([name])
        return self

    def ambiguous(self, name: str, body: B | Rule | str, *,
                  dynamic: int = 1, **flags) -> Grammar:
        """Intentional-ambiguity opt-in (dedicated spelling): register `name`
        with its body wrapped in PREC_DYNAMIC(dynamic) and whitelist it in
        conflicts — the typed, declarative form of hand-editing the `conflicts`
        array. `rule(..., ambiguous=True, dynamic=...)` is the one-liner."""
        return self.rule(name, body, ambiguous=True, dynamic=dynamic, **flags)

    def word(self, rule_name: str) -> Grammar:
        """Declare the word token rule (keyword extraction; avoids
        keyword/identifier conflicts). The referenced rule must be a token."""
        self._word = rule_name
        return self

    def extra(self, x: B | Rule | str) -> Grammar:
        self._extras.append(as_node(x))
        node = as_node(x)
        if isinstance(node, PatternNode) and node.value == r"\s":
            self._explicit_whitespace = True
        return self

    def conflict(self, *rule_names: str) -> Grammar:
        """Whitelist an intentional ambiguity between the named rules."""
        self._conflicts.append(list(rule_names))
        return self

    def precedence(self, *levels: str, named: bool = False) -> Ladder:
        """Declare a precedence ladder, **loose -> tight** (low -> high), and
        return a `Ladder` for annotating operators.

        - int mode (default): each level gets an ascending integer (1..N);
          inserting a level mid-ladder renumbers everything automatically
          (integers are computed at use time, never stored).
        - named mode: each level keeps its NAME; the grammar emits a
          descending `precedence_ordering` (first = highest) at build time,
          and `prec*` values are the names. Named and integer precedence
          never compare against each other (Phase-2 finding) — the helper's
          ladder is consistent by construction; mixing modes across rules is
          the author's call (the analyzer warns).

        Usage: `prec = g.precedence("or", "and", "add", "mul", "unary")`
        then `prec.left("add", seq(expr, "+", expr))`.
        """
        if len(set(levels)) != len(levels):
            raise ValueError(f"duplicate levels in precedence ladder: {levels}")
        if not levels:
            raise ValueError("precedence() needs at least one level")
        ladder = Ladder(self, list(levels), named=named)
        self._ladders.append(ladder)
        return ladder

    def precedence_ordering(self, *names: str) -> Grammar:
        """Declare a named precedence ordering, **highest first** (descending)
        — mirroring the CLI's `precedences` schema (STRING/SYMBOL entries only;
        the first entry binds tightest, per tree-sitter's own test grammars).
        Phase-3 will sugar this with a ladder helper; here it is raw."""
        self._precedences.append([StrNode(value=n) for n in names])
        return self

    def external(self, *x) -> Grammar:
        """Declare external token(s) (provided by a C scanner at runtime).
        No scanner authoring here — the IR accepts the declaration; the
        pipeline compiles a user-supplied scanner.c if one is present (and
        raises ExternalScannerRequiredError when a grammar declares externals
        without one).
        """
        for tok_ in x:
            self._externals.append(as_node(tok_))
        return self

    def reserved_word(self, context_name: str, x: B | Rule | str) -> Grammar:
        """Declare a reserved word set: when `context_name` is active, the
        given rule(s) are disabled from matching (tree-sitter 0.25+)."""
        self._reserved.setdefault(context_name, []).append(as_node(x))
        return self

    # -- emission -----------------------------------------------------------
    def build(self) -> GrammarModel:
        r"""Build the serializable Grammar IR.

        The start rule is reordered to FIRST — the CLI treats the first rule
        as the grammar root (no `start` field in this CLI version) and
        silently prunes unreachable rules.

        Phase 3 defaults: a whitespace extra (`\s`) is prepended unless the
        author disabled it or added `\s` explicitly (grammar.json has NO
        default extras — the grammar.js `[\s]` default does not carry over);
        named-mode ladders emit their descending `precedence_ordering`.
        """
        start = self._start or "source_file"
        if start not in self.rules:
            raise ValueError(f"start rule {start!r} is not defined")
        ordered = {start: self.rules[start]}
        ordered.update({n: r for n, r in self.rules.items() if n != start})
        extras = list(self._extras)
        if self._whitespace and not self._explicit_whitespace:
            extras.insert(0, PatternNode(value=r"\s"))
        precedences = list(self._precedences)
        for ladder in self._ladders:
            if ladder.named:
                precedences.append(ladder.ordering())
        return GrammarModel(
            name=self.name,
            rules=ordered,
            precedences=precedences,
            conflicts=self._conflicts,
            externals=self._externals,
            extras=extras,
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

    # -- per-production source sites ----------------------------------------
    def node_site(self, node: RuleNode) -> RuleSite | None:
        """The DSL site recorded for a body node (or None)."""
        return self._node_sites.get(id(node))

    def matching_alternative(self, rule_name: str,
                             production: tuple[str, ...]) -> RuleSite | None:
        """Find the DSL site of the choice alternative of `rule_name` whose
        production matches the given step-symbol list (the CLI's
        `production_step_symbols` rendering). Returns the site of the
        `seq(...)`/`prec*` combinator that produced the alternative — NOT the
        rule-level `rule(...)` site. Falls back to the rule site when no
        member matches (imported IR grammars, inlined rules, auxiliary
        productions)."""
        if rule_name not in self.rules:
            return None
        body = self.rules[rule_name]
        for member in _choice_members(body):
            for prod in _production_symbols(member):
                if prod == list(production):
                    return _production_site(self, member) or self.sites.get(rule_name)
        return self.sites.get(rule_name)


# module-level constructor alias (kickoff surface: `Grammar`)
def grammar(name: str) -> Grammar:
    return Grammar(name)


# ---------------------------------------------------------------------------
# precedence ladders
# ---------------------------------------------------------------------------

class Ladder:
    """A declarative precedence ladder, **loose -> tight** (low -> high).

    - int mode (default): each level maps to an ascending integer, computed at
      use time — inserting a level mid-ladder renumbers everything after it
      automatically (nothing stores the integers).
    - named mode: each level keeps its name; the grammar emits a descending
      `precedence_ordering` (first = highest, per the CLI) and `prec*` values
      are the names.

    Associativity is attached at the operator (`left`/`right`), not the
    integer/level. The ladder is consistent by construction (all-int or
    all-named) — the named/int mixing that broke Phase-2's kitsink cannot
    come from one ladder.

    Usage:
        prec = g.precedence("or", "and", "compare", "add", "mul", "unary")
        g.rule("expr", choice(
            prec.left("add", seq(expr, "+", expr)),
            prec("unary", seq("-", expr)),
            ...))
    """

    def __init__(self, grammar: Grammar, levels: list[str], *, named: bool = False):
        self._grammar = grammar
        self._levels = list(levels)
        self.named = named

    @property
    def levels(self) -> list[str]:
        return list(self._levels)

    def __getitem__(self, level: str) -> int | str:
        return self.n(level)

    def __call__(self, level: str, x: B | Rule | str | None = None):
        """`prec("unary")` -> the level's precedence value;
        `prec("unary", body)` -> `prec(value, body)` (shorthand)."""
        if x is None:
            return self.n(level)
        return prec(self.n(level), x)

    def n(self, level: str) -> int | str:
        """The precedence value (int or name) for a ladder level."""
        if level not in self._levels:
            raise KeyError(
                f"level {level!r} not in precedence ladder {self._levels}")
        if self.named:
            return level
        return self._levels.index(level) + 1

    def insert(self, level: str, *, before: str | None = None,
               after: str | None = None) -> Ladder:
        """Add a level; int-mode values renumber automatically. Exactly one of
        `before`/`after` may anchor the position."""
        if level in self._levels:
            raise ValueError(f"level {level!r} already in ladder")
        if before is not None and after is not None:
            raise ValueError("specify only one of before=/after=")
        if before is not None:
            self._levels.insert(self._levels.index(before), level)
        elif after is not None:
            self._levels.insert(self._levels.index(after) + 1, level)
        else:
            self._levels.append(level)
        return self

    def ordering(self) -> list[Rule]:
        """Descending precedence_ordering (first = highest) for named mode."""
        return [StrNode(value=n) for n in reversed(self._levels)]

    def prec(self, level: str, x: B | Rule | str) -> B:
        return prec(self.n(level), x)

    def left(self, level: str, x: B | Rule | str) -> B:
        return prec_left(self.n(level), x)

    def right(self, level: str, x: B | Rule | str) -> B:
        return prec_right(self.n(level), x)

    def __repr__(self) -> str:
        mode = "named" if self.named else "int"
        return f"Ladder({self._levels}, {mode})"


# ---------------------------------------------------------------------------
# per-production matching helpers
# ---------------------------------------------------------------------------

def _choice_members(node: Rule) -> list[Rule]:
    """A rule body's top-level alternatives (a non-CHOICE body is one)."""
    return node.members if isinstance(node, ChoiceNode) else [node]


def _production_symbols(node: Rule) -> list[list[str]]:
    """The production step-symbol lists a node can produce, rendered the way
    the CLI's `production_step_symbols` does (SYMBOL -> name, STRING ->
    `'value'`). A choice inside a seq cross-products into alternative
    productions (the CLI expands choices at rule-normalization time, so each
    is a distinct production with its own step list)."""
    if isinstance(node, (PrecNode, PrecLeftNode, PrecRightNode,
                         PrecDynamicNode, AliasNode, TokenNode,
                         ImmediateTokenNode, FieldNode)):
        return _production_symbols(node.content)
    if isinstance(node, SeqNode):
        results: list[list[str]] = [[]]
        for m in node.members:
            alts = _production_symbols(m)
            results = [r + a for r in results for a in alts]
        return results
    if isinstance(node, ChoiceNode):
        out: list[list[str]] = []
        for m in node.members:
            out.extend(_production_symbols(m))
        return out
    if isinstance(node, SymbolNode):
        return [[node.name]]
    if isinstance(node, StrNode):
        return [[f"'{node.value}'"]]
    if isinstance(node, PatternNode):
        return [[node.value]]
    if isinstance(node, BlankNode):
        return [[]]
    if isinstance(node, RepeatNode | Repeat1Node):
        # the CLI desugars repeats into auxiliary symbols; best effort
        return _production_symbols(node.content)
    return [[]]


def _production_site(grammar: Grammar, member: Rule) -> RuleSite | None:
    """The most precise DSL site for a matched alternative: prefer the inner
    `seq(...)` combinator line over the `prec*` wrapper that holds it, so the
    conflict lands on the exact `seq(expr, '+', expr)` argument."""
    site = grammar.node_site(member)
    n = member
    while isinstance(n, (PrecNode, PrecLeftNode, PrecRightNode,
                         PrecDynamicNode, AliasNode)):
        n = n.content
    if isinstance(n, SeqNode):
        s = grammar.node_site(n)
        if s is not None:
            return s
    return site
