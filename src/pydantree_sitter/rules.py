"""pydantree_sitter.rules — `Rule`, the validated ast-grep rule model (022 §6).

ast-grep's rule object is a nested dictionary. This module makes it a
Pydantic model, so the caller sends a checked structure instead of a free
string:

    rule = Rule(
        pattern="$OBJ.$METHOD($$$ARGS)",
        inside=Rule(kind="class_definition"),
        **{"not": Rule(pattern="self.$METHOD($$$ARGS)")},
    )

That is the reason project 022 exists. The consumer is an untrusted language
model, and a raw pattern string is close to an argument vector while a `Rule`
is a typed, bounded, grammar-checked capability (022 §11).

The module is pure Pydantic. It imports no engine, and `ast_grep_py` need not
be installed to build or validate a rule.

Vocabulary (022 §5). A `metavariable` is a `$NAME` inside a pattern string.
It belongs only to the structural-pattern layer and is separate from typed
node fields.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import PatternBuildError

__all__ = [
    "MAX_PATTERN_LENGTH",
    "MAX_RULE_DEPTH",
    "MAX_RULE_NODES",
    "Rule",
    "metavariables_of",
]

# -- the bounds (022 §6.1) --------------------------------------------------
#
# Untrusted input is the design assumption, so depth is not the only axis
# that needs a bound. A rule arrives as model output and every one of these
# is reachable by a model that is confused rather than hostile.

MAX_RULE_DEPTH = 8          # nesting levels; 8 is generous for real rules
MAX_RULE_NODES = 64         # total Rule objects in one tree
MAX_PATTERN_LENGTH = 4096   # characters in one `pattern` or `regex` string

# ast-grep's default metavariable spelling: `$NAME` binds one node,
# `$$$NAME` binds a sequence. The grammar may configure another one-character
# sigil, so compile this expression at the boundary that knows the grammar.
_METAVAR = re.compile(r"\$(\$\$)?([A-Z_][A-Z0-9_]*)")


def _metavar_pattern(meta_var_char: str = "$") -> re.Pattern:
    if not isinstance(meta_var_char, str) or len(meta_var_char) != 1:
        raise ValueError(
            f"meta_var_char must be one character, got {meta_var_char!r}")
    escaped = re.escape(meta_var_char)
    return re.compile(
        rf"{escaped}({escaped}{{2}})?([A-Z_][A-Z0-9_]*)")


def metavariables_of(pattern: str, meta_var_char: str = "$") \
        -> frozenset[str]:
    """The capturing metavariable names in one pattern string.

    Names come back WITHOUT their `$` sigils, and a `$$$ARGS` multi-match
    contributes the same bare `ARGS` as a single `$ARGS` would — the caller
    checks that a replacement template names something the rule binds, and
    the arity is not part of that question.

    A leading-underscore name (`$_IGNORED`) is ast-grep's non-capturing form
    and is excluded: it binds nothing, so naming it in a template is an
    error rather than a match.
    """
    return frozenset(
        name for _multi, name in _metavar_pattern(meta_var_char).findall(pattern)
        if not name.startswith("_")
    )


class Rule(BaseModel):
    """One ast-grep rule, validated.

    Atomic keys (`pattern`, `kind`, `regex`) say what a node looks like.
    Relational keys (`inside`, `has`, `precedes`, `follows`) say where it
    sits. Composite keys (`all`, `any`, `not`) combine rules.

    `all`, `any` and `not` are Python keywords, so the fields carry a
    trailing underscore and an alias. The model populates BY ALIAS as well as
    by name, so `Rule(**{"not": ...})` and `Rule(not_=...)` both work and the
    serialized JSON stays idiomatic ast-grep.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # atomic
    pattern: str | None = None
    kind: str | None = None
    regex: str | None = None

    # relational operand modifiers. ast-grep calls a relational operand a
    # `Relation`: a rule PLUS `stopBy` and `field`. They are fields of `Rule`
    # here rather than a separate class, so `inside=Rule(kind=...)` — the
    # spelling 022 §3 documents — keeps working.
    stop_by: Literal["neighbor", "end"] | None = Field(None, alias="stopBy")
    field: str | None = None

    # relational
    inside: Rule | None = None
    has: Rule | None = None
    precedes: Rule | None = None
    follows: Rule | None = None

    # composite
    all_: tuple[Rule, ...] | None = Field(None, alias="all")
    any_: tuple[Rule, ...] | None = Field(None, alias="any")
    not_: Rule | None = Field(None, alias="not")

    _ATOMIC = ("pattern", "kind", "regex")
    _MODIFIERS = ("stop_by", "field")
    _RELATIONAL = ("inside", "has", "precedes", "follows")
    _COMPOSITE = ("all_", "any_", "not_")

    # -- construction -------------------------------------------------------

    @classmethod
    def of(cls, pattern: str) -> Rule:
        """The bare-pattern rule. `Rule(pattern=...)` says the same thing;
        this spelling validates through the alias machinery, so a checker
        that does not read pydantic's aliases stays quiet."""
        return cls.model_validate({"pattern": pattern})

    # -- validation ---------------------------------------------------------

    @model_validator(mode="after")
    def _check(self) -> Rule:
        self._check_non_empty()
        self._check_lengths()
        self._check_regex()
        self._check_bounds()
        return self

    # `stopBy` decides how far a relational search walks. ast-grep's own
    # default is "neighbor" — the IMMEDIATE parent, sibling, or child only.
    # `inside=Rule(kind="class_definition")` therefore reads as "anywhere
    # inside a class" and matches only a direct child of the class body,
    # which is almost never what the caller meant and returns an empty set
    # rather than an error.
    #
    # An empty result set is the worst possible answer for the consumer this
    # module serves: a model reads "no matches" as "the code does not contain
    # this", and acts on it. So a relational operand that does not say
    # otherwise gets "end" — walk to the root. Say `stop_by="neighbor"` to
    # get ast-grep's own default back. The choice is visible in
    # `to_astgrep()`, never hidden.
    _DEFAULT_STOP_BY = "end"

    def _check_non_empty(self) -> None:
        """A rule must say something. An all-None rule matches every node,
        which is never what the caller meant and is expensive to discover by
        running it."""
        named = [f for f in self._ATOMIC + self._COMPOSITE
                 if getattr(self, f) is not None]
        if named:
            return
        relational = [f for f in self._RELATIONAL if getattr(self, f) is not None]
        if relational:
            raise PatternBuildError(
                f"rule has only relational key(s) "
                f"{', '.join(sorted(relational))}: a relational key CONSTRAINS "
                f"a match, it does not make one. Add `pattern`, `kind`, "
                f"`regex`, or a composite key.")
        modifiers = [f for f in self._MODIFIERS if getattr(self, f) is not None]
        if modifiers:
            raise PatternBuildError(
                f"rule sets only {', '.join(sorted(modifiers))}: those modify "
                f"a relational operand, they do not match anything on their "
                f"own. Add `pattern`, `kind`, or `regex`.")
        raise PatternBuildError(
            "empty rule: set at least one of "
            f"{', '.join(self._ATOMIC)}, or a composite key (all, any, not).")

    def _check_lengths(self) -> None:
        for field in ("pattern", "regex"):
            value = getattr(self, field)
            if value is not None and len(value) > MAX_PATTERN_LENGTH:
                raise PatternBuildError(
                    f"{field} is {len(value)} characters, over the "
                    f"{MAX_PATTERN_LENGTH} limit.")

    def _check_regex(self) -> None:
        """`regex` must compile. This catches the typo, and nothing more —
        a regex that compiles can still run for a very long time, and this
        model cannot bound that. The caller owns the timeout."""
        if self.regex is None:
            return
        try:
            re.compile(self.regex)
        except re.error as exc:
            raise PatternBuildError(
                f"regex {self.regex!r} does not compile: {exc}") from exc

    def _check_bounds(self) -> None:
        """Depth and total size (§6.1). A recursive model with a
        model-supplied payload needs a bound in both directions: deep and
        wide."""
        depth, nodes = self._measure()
        if depth > MAX_RULE_DEPTH:
            raise PatternBuildError(
                f"rule nests {depth} levels deep, over the "
                f"{MAX_RULE_DEPTH} limit.")
        if nodes > MAX_RULE_NODES:
            raise PatternBuildError(
                f"rule holds {nodes} sub-rules, over the "
                f"{MAX_RULE_NODES} limit.")

    def _measure(self) -> tuple[int, int]:
        """(depth, node count) of this subtree, self included."""
        depth = 1
        nodes = 1
        for child in self._children():
            d, n = child._measure()
            depth = max(depth, d + 1)
            nodes += n
        return depth, nodes

    def _children(self) -> list[Rule]:
        out: list[Rule] = []
        for field in self._RELATIONAL + ("not_",):
            value = getattr(self, field)
            if value is not None:
                out.append(value)
        for field in ("all_", "any_"):
            value = getattr(self, field)
            if value is not None:
                out.extend(value)
        return out

    # -- the grammar check (022 §6) -----------------------------------------

    def check_kinds(self, schema) -> None:
        """Reject a `kind` the bound grammar does not have, by name.

        This is the highest-value validator in the module: it turns a typo
        into a precise message in one round trip, before any parser starts.
        It runs at `Pattern` construction, where a schema exists — a Rule on
        its own has no grammar to check against.

        Every `kind` in the whole tree is checked, not only the root's.
        """
        known = schema.kinds()
        bad = sorted(k for k in self.kinds_used() if k not in known)
        if not bad:
            return
        raise PatternBuildError(
            f"unknown node kind(s) {', '.join(repr(k) for k in bad)} for "
            f"grammar {schema.name or '?'}. "
            + _suggest(bad[0], known))

    def kinds_used(self) -> frozenset[str]:
        """Every `kind` named anywhere in this rule tree."""
        out: set[str] = set()
        if self.kind is not None:
            out.add(self.kind)
        for child in self._children():
            out |= child.kinds_used()
        return frozenset(out)

    def metavariables(self, meta_var_char: str = "$") -> frozenset[str]:
        """Every capturing metavariable bound anywhere in this rule tree.

        `codeman` uses this to verify that a replacement template names only
        metavariables the rule binds. That check belongs to the caller; this
        method exists to make it one line.

        A metavariable under `not` is reported, and it does NOT bind at match
        time — a negated branch matches nothing by definition. Templates must
        not name one, and the caller can see which they are by walking the
        tree itself.
        """
        out: set[str] = set()
        if self.pattern is not None:
            out |= metavariables_of(self.pattern, meta_var_char)
        for child in self._children():
            out |= child.metavariables(meta_var_char)
        return frozenset(out)

    # -- emission -----------------------------------------------------------

    def to_astgrep(self) -> dict[str, Any]:
        """The plain nested dict `ast_grep_py` accepts.

        Emitted by alias (`all`/`any`/`not`) with every unset key dropped,
        so the result is the rule the caller wrote — plus the one default
        this module supplies, `stopBy: "end"` on a relational operand, which
        is emitted explicitly and is therefore inspectable.
        """
        out = self.model_dump(by_alias=True, exclude_none=True, mode="json")
        for key in ("inside", "has", "precedes", "follows"):
            operand = out.get(key)
            if operand is not None:
                operand.setdefault("stopBy", self._DEFAULT_STOP_BY)
        return out


def _suggest(bad: str, known: set[str]) -> str:
    """A near-miss hint for an unknown kind. Cheap edit-distance by prefix
    and containment — enough to catch a plural or a typo, and it never
    guesses when nothing is close."""
    near = sorted(k for k in known if k.startswith(bad[:4]) or bad in k)[:3]
    if near:
        return "Did you mean " + ", ".join(repr(k) for k in near) + "?"
    return "Check the grammar's node-types for the spelling."
