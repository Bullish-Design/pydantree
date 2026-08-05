"""tsgrammar.rules — the rule-class authoring surface ("the model IS the
rule").

Each grammar rule is a CLASS; the class body IS the production. `assemble()`
compiles the classes into the existing builder DSL (builder.py) — the IR,
pipeline, checks, and bundles are untouched by construction.

    class Pair(Rule):
        key: NamePath                  # field("key", ref("name_path"))
        eq: Literal["="] = "="         # anonymous token "="
        value: Value
        semi: Literal[";"] = ";"

    def build() -> tg.Grammar:
        return assemble("devenv", start=SourceFile)

The base class carries the rule's kind and behavioral flags:

  * body kinds:   Pattern (bare regex leaf), Token (token-wrapped body or
                  `__pattern__`), External (external-scanner token)
  * mixins:       Extra, Supertype, Hidden, Inline, Word

Flags compose by multiple inheritance (`class Comment(Extra, Token)`); the
kinds set disjoint attributes, so MRO order is irrelevant in practice.

Annotated attributes are ORDERED children (Python preserves annotation
order); the attribute name is the CST field. `Literal[...]` attributes are
anonymous tokens — the default MUST equal the Literal value (checked at
`assemble()` time, before any build). `list[T]` is a repeat (the field goes
INSIDE the repeat); `A | B` is a choice; `A | None` is opt; the reserved
label `content` is an UNNAMED child.

`__body__` is the escape hatch for shapes annotations cannot express (unnamed
sequences, bare alternations): the combinator DSL as-is, with `R(SomeClass)`
as a class-typed reference — or `tg.ref("name")` at the mutual-recursion
cycle points, where the referenced class is not in scope yet.
"""

from __future__ import annotations

import inspect
import linecache
import sys
import types
from typing import Literal, Union, get_args, get_origin

from .builder import (
    B,
    Grammar,
    RuleSite,
    as_node,
    choice as tg_choice,
    field as tg_field,
    opt as tg_opt,
    pattern as tg_pattern,
    ref as tg_ref,
    repeat as tg_repeat,
    seq as tg_seq,
    tok as tg_tok,
    token as tg_token,
)

__all__ = [
    "Rule", "Pattern", "Token", "External",
    "Extra", "Supertype", "Hidden", "Inline", "Word",
    "R", "assemble",
]


# ---------------------------------------------------------------------------
# the metaclass + the kinds
# ---------------------------------------------------------------------------

def _snake(name: str) -> str:
    """CamelCase -> snake_case (`NamePath` -> `name_path`, `ListRule` ->
    `list_rule`). A leading underscore (hidden-rule convention) survives."""
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _rule_site(depth: int = 2) -> RuleSite:
    """The class-definition site (file/lineno/source) for conflict
    remapping. Walks up from the metaclass `__new__` frame to the module
    frame executing the `class` statement (measured: depth 2)."""
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


class _RuleMeta(type):
    """Registers rule classes: derives `__rule_name__` from the class name
    (overridable with `__rule_name__`) and records the definition site.
    `__abstract__ = True` in a class's OWN namespace skips it — the kind
    bases (Pattern, Token, External, Extra, ...) are never registered."""

    def __new__(mcs, name, bases, ns):
        cls = super().__new__(mcs, name, bases, ns)
        if not ns.get("__abstract__"):      # OWN ns: kind bases skip
            rn = ns.get("__rule_name__") or _snake(name)
            cls.__rule_name__ = rn
            cls.__site__ = _rule_site()
        return cls


class Rule(metaclass=_RuleMeta):
    """The base rule class; annotation-bodied rules (the common case)."""
    __abstract__ = True


# ---- body kinds (they set disjoint flags; read INHERITED via getattr) ------

class Pattern(Rule):
    """A regex leaf rule — bare `pattern(...)`, NOT token-wrapped."""
    __abstract__ = True


class Token(Rule):
    """A rule whose body (or `__pattern__`) is wrapped in `token(...)` —
    lexed as one token."""
    __abstract__ = True
    __token__ = True


class External(Rule):
    """A rule backed by an external-scanner token; the token name defaults
    to the rule name in SCREAMING_SNAKE (override with `__external__`)."""
    __abstract__ = True


# ---- behavioral mixins ------------------------------------------------------

class Extra(Rule):
    """Also an extra (whitespace/comment — matched anywhere, never a child)."""
    __abstract__ = True
    __extra__ = True


class Supertype(Rule):
    """Also a grammar-level supertype entry."""
    __abstract__ = True
    __supertype__ = True


class Hidden(Rule):
    """Also a hidden rule — renamed `_<name>` per the tree-sitter
    convention. `R(cls)` and annotation refs resolve the underscore."""
    __abstract__ = True
    __hidden__ = True


class Inline(Rule):
    """Also added to the grammar-level `inline` list."""
    __abstract__ = True
    __inline__ = True


class Word(Rule):
    """Also declared as the grammar's `word` token."""
    __abstract__ = True
    __word__ = True


# ---------------------------------------------------------------------------
# name resolution
# ---------------------------------------------------------------------------

def _resolved_name(cls: type) -> str:
    """The rule name as REGISTERED — for a `Hidden` rule this is the
    underscore-prefixed name the builder's `rule(hidden=True)` produces."""
    rn = cls.__rule_name__
    if getattr(cls, "__hidden__", False) and not rn.startswith("_"):
        return "_" + rn
    return rn


# ---------------------------------------------------------------------------
# compilation: annotations -> builder calls
# ---------------------------------------------------------------------------

_UNSET = object()


def _resolve(cls: type, ann) -> object:
    """Resolve an annotation against the defining module's globals. With
    `from __future__ import annotations` the annotation is a string, eval'd
    lazily (the pydantic `model_rebuild` pattern) — so a rule may reference
    classes defined later in the module. The annotation is the author's own
    module code; eval() runs with exactly that module's namespace."""
    if isinstance(ann, str):
        return eval(ann, vars(sys.modules[cls.__module__]))  # noqa: S307
    return ann


def _wrap(x: B, attr: str | None) -> B:
    """Field-wrap unless unnamed (`content` is the reserved label for an
    UNNAMED child — the IR's own slot name)."""
    if attr is not None and attr != "content":
        return tg_field(attr, x)
    return x


def _child(cls: type, t, attr: str | None = None) -> B:
    """One annotation -> one body node. Rows (each probe-verified):

        key: NamePath              -> field("key", ref("name_path"))
        eq: Literal["="] = "="     -> the string "=" (anonymous token)
        element: list[Value]       -> repeat(field("element", ref("value")))
                                     (the field goes INSIDE the repeat)
        content: list[X]           -> repeat(ref(...))  (no field)
        value: String | Number     -> field("value", choice(ref, ref))
        maybe: Number | None       -> field("maybe", opt(ref))
    """
    origin = get_origin(t)
    if isinstance(t, type) and issubclass(t, Rule):
        return _wrap(tg_ref(_resolved_name(t)), attr)
    if origin is Literal:
        return str(get_args(t)[0])
    if origin in (list,):
        inner = _child(cls, get_args(t)[0])
        if attr is not None and attr != "content":
            inner = tg_field(attr, inner)
        return tg_repeat(inner)
    if origin in (types.UnionType, Union):
        args = get_args(t)
        non_none = [a for a in args if a is not type(None)]
        if not non_none:
            raise TypeError(f"{cls.__name__}: cannot compile annotation {t!r}")
        inner = _child(cls, non_none[0])
        if len(non_none) > 1:
            inner = tg_choice(inner, *(_child(cls, a) for a in non_none[1:]))
        if type(None) in args:
            inner = tg_opt(inner)
        return _wrap(inner, attr)
    raise TypeError(f"{cls.__name__}: cannot compile annotation {t!r}")


def _from_annotations(cls: type) -> B:
    """The annotation form: ordered children -> one seq (or a bare member)."""
    members = []
    for attr, ann in cls.__annotations__.items():
        if attr.startswith("__"):
            continue
        t = _resolve(cls, ann)
        if get_origin(t) is Literal:
            (val,) = get_args(t)
            default = cls.__dict__.get(attr, _UNSET)
            if default is not _UNSET and default != val:
                raise ValueError(
                    f"{cls.__name__}.{attr}: Literal[{val!r}] default "
                    f"{default!r} does not match — anonymous tokens must "
                    f"default to their Literal value")
            members.append(val)
        else:
            members.append(_child(cls, t, attr=attr))
    if not members:
        raise ValueError(
            f"{cls.__name__}: no children — annotate at least one attribute, "
            f"or give the rule __body__ / __pattern__ / __external__")
    return members[0] if len(members) == 1 else tg_seq(*members)


def R(cls: type) -> B:
    """Reference to a rule class — the `__body__` escape hatch's name layer.
    Compiles to the same SYMBOL as `tg.ref("name")`, class-typed instead of
    stringly-typed. (`tg.ref("name")` stays the spelling at the mutual-
    recursion cycle points, where the referenced class is not in scope.)"""
    if not (isinstance(cls, type) and issubclass(cls, Rule)):
        raise TypeError(f"R() expects a Rule subclass, got {cls!r}")
    return tg_ref(_resolved_name(cls))


# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------

def assemble(name: str, *, start: type) -> Grammar:
    """Compile the rule classes of the module that defines `start` into a
    builder `Grammar` — the SAME object the builder DSL produces, so
    `run_checks`, `build_builder`, and the bundle pipeline are unchanged.

    Rules are module-level `Rule` subclasses in the start class's module
    (imported rule classes count — `from other_module import X` binds X in
    the namespace). Definition order = rule order = external order (externals
    must precede their rules in the scanner's expected order).
    """
    if not (isinstance(start, type) and issubclass(start, Rule)):
        raise TypeError(
            f"assemble(start=...) needs a Rule subclass, got {start!r}")
    module = sys.modules[start.__module__]
    classes = [
        obj for obj in vars(module).values()
        if isinstance(obj, type) and issubclass(obj, Rule)
        and hasattr(obj, "__rule_name__")          # concrete (kind bases skip)
    ]
    if not classes:
        raise ValueError(
            f"no rule classes found in module {start.__module__!r} — rules "
            f"are module-level Rule subclasses (import them if defined "
            f"elsewhere)")

    g = Grammar(name)
    for cls in classes:
        rn = _resolved_name(cls)
        # external-scanner token, declared BEFORE the rule (the scanner's
        # expected order follows class definition order)
        ext = getattr(cls, "__external__", None)
        if ext is None and issubclass(cls, External):
            ext = cls.__rule_name__.upper()
        if ext is not None:
            g.external(tg_tok(ext))
        # body: __body__ (own ns) -> __pattern__ (own ns) -> __external__ ->
        # annotations
        body = cls.__dict__.get("__body__")
        if body is None:
            pat = cls.__dict__.get("__pattern__")
            if pat is not None:
                if isinstance(pat, str):
                    pat = tg_pattern(pat)
                elif not (isinstance(pat, B)
                          and pat.node.type == "PATTERN"):
                    raise TypeError(
                        f"{cls.__name__}.__pattern__ must be a regex string "
                        f"or tg.pattern(...), got {pat!r}")
                body = tg_token(pat) if getattr(cls, "__token__", False) \
                    else pat
            elif ext is not None:
                body = tg_tok(ext)
            else:
                body = _from_annotations(cls)
        if not isinstance(body, B):
            body = B(as_node(body))
        # token-wrap (the guard prevents double-wrapping an already-token body
        # or an External's tok)
        if getattr(cls, "__token__", False) and body.node.type != "TOKEN":
            body = tg_token(body)
        g.rule(rn, body,
               supertype=getattr(cls, "__supertype__", False),
               hidden=getattr(cls, "__hidden__", False),
               inline=getattr(cls, "__inline__", False),
               word=getattr(cls, "__word__", False))
        if getattr(cls, "__extra__", False):
            g.extra(tg_ref(_resolved_name(cls)))
    g.start(_resolved_name(start))
    return g
