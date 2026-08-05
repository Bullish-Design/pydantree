"""pydantree_sitter_grammar.rules — the rule-class authoring surface ("the model IS the
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
import os
import sys
import types
from typing import Literal, Union, get_args, get_origin

from .builder import (
    B,
    Grammar,
    RuleSite,
    _SITES,
    _iter_body_nodes,
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

# this module's own file — body nodes built here (annotation compilation,
# token/pattern wrapping) get their sites repointed at the class/attribute
# lines during assemble(); `__body__` combinator sites land in the author's
# module and are left alone.
_RULES_FILE = os.path.abspath(__file__)


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


def _attr_sites(cls: type) -> dict[str, RuleSite]:
    """file/lineno/source for each annotated attribute — the class body's
    `attr: Type` lines — so conflict remapping can point at `Pair.value`
    (class + attribute), not a raw combinator line. Found by scanning the
    class's own source lines for the `attr:` prefix."""
    sites: dict[str, RuleSite] = {}
    try:
        src_lines, start = inspect.getsourcelines(cls)
    except (OSError, TypeError):
        return sites
    for attr in cls.__annotations__:
        if attr.startswith("__"):
            continue
        for i, line in enumerate(src_lines):
            stripped = line.lstrip()
            if stripped.startswith(f"{attr}:"):
                sites[attr] = RuleSite(
                    cls.__site__.file, start + i, stripped.rstrip("\n"))
                break
    return sites


def _snapshot_body_sites(body) -> dict[int, RuleSite]:
    """The combinator call sites of a class's `__body__` expression,
    captured ONCE at class creation. The builder's global `_SITES` table is
    drained by the first `assemble()` (each `rule()` registration pops the
    body's entries), so a SECOND `assemble()` in the same process would
    otherwise lose every per-node site and fall back to rule-level lines. The
    DSL re-creates its nodes per `build()` call; class bodies evaluate once,
    so the snapshot is re-applied by every `assemble()`."""
    sites: dict[int, RuleSite] = {}
    if body is None:
        return sites
    for n in _iter_body_nodes(as_node(body)):
        site = _SITES.get(id(n))
        if site is not None:
            sites[id(n)] = site
    return sites


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
            cls.__attr_sites__ = _attr_sites(cls)
            cls.__body_sites__ = _snapshot_body_sites(ns.get("__body__"))
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


def _from_annotations(cls: type) -> tuple[B, dict[int, str]]:
    """The annotation form: ordered children -> one seq (or a bare member).

    Returns the body plus a node-id -> attribute-name map (for source-site
    remapping: each annotation-emitted node points at its attribute line).
    """
    members: list[B | str] = []
    attr_nodes: dict[int, str] = {}
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
            member: B | str = val
        else:
            member = _child(cls, t, attr=attr)
        for n in _iter_body_nodes(as_node(member)):
            attr_nodes[id(n)] = attr
        members.append(member)
    if not members:
        raise ValueError(
            f"{cls.__name__}: no children — annotate at least one attribute, "
            f"or give the rule __body__ / __pattern__ / __external__")
    body = members[0] if len(members) == 1 else tg_seq(*members)
    return body, attr_nodes


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
        attr_nodes: dict[int, str] = {}
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
                body, attr_nodes = _from_annotations(cls)
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
        # source sites: the rule points at its CLASS definition; every body
        # node that was built inside rules.py internals (annotation-emitted
        # fields/repeats/choices, token/pattern wrappers) is repointed at the
        # class or the exact attribute line — `__body__` combinator sites
        # already point at the author's module lines and are left alone.
        g.sites[rn] = cls.__site__
        attr_sites = getattr(cls, "__attr_sites__", {})
        for node in _iter_body_nodes(as_node(body)):
            current = g._node_sites.get(id(node))
            if (current is not None
                    and os.path.abspath(current.file) == _RULES_FILE):
                attr = attr_nodes.get(id(node))
                site = (attr_sites.get(attr) if attr is not None
                        else None) or cls.__site__
                g._node_sites[id(node)] = site
        # `__body__` combinator sites are stable per class (evaluated once at
        # class creation, drained by the first assemble) — re-apply them on
        # every assemble so repeated build() calls keep per-node remapping.
        for nid, site in cls.__body_sites__.items():
            g._node_sites[nid] = site
        if getattr(cls, "__extra__", False):
            g.extra(tg_ref(_resolved_name(cls)))
    g.start(_resolved_name(start))
    return g
