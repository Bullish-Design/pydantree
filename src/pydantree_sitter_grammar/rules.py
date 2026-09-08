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
import os
import sys
import types
from collections.abc import Sequence
from typing import Any, ClassVar, Literal, cast, get_args, get_origin

from pydantree_sitter.nodes import (
    Node,
    _children_for,
    _resolve_forward,
    _snake,
)

from .builder import (
    B,
    Grammar,
    RuleSite,
    _iter_body_nodes,
    as_node,
    site_of,
)
from .builder import (
    choice as tg_choice,
)
from .builder import (
    field as tg_field,
)
from .builder import (
    opt as tg_opt,
)
from .builder import (
    pattern as tg_pattern,
)
from .builder import (
    ref as tg_ref,
)
from .builder import (
    repeat as tg_repeat,
)
from .builder import (
    seq as tg_seq,
)
from .builder import (
    tok as tg_tok,
)
from .builder import (
    token as tg_token,
)

__all__ = [
    "External",
    "Extra",
    "Hidden",
    "Inline",
    "Pattern",
    "R",
    "Rule",
    "Supertype",
    "Token",
    "Word",
    "assemble",
]

_RULES_FILE = os.path.abspath(__file__)

def _rule_meta_hook(cls: type) -> None:
    """Add Product B's provenance and registration metadata to a Node."""
    if cls.__dict__.get("__abstract__", False):
        return
    from .builder import RuleSite, caller_site

    rule_cls = cast(Any, cls)
    rule_cls.__rule_name__ = (cls.__dict__.get("__rule_name__") or
                               _snake(cls.__name__))
    rule_cls.__site__ = caller_site(skip=3)
    sites: dict[str, RuleSite] = {}
    try:
        source, start = inspect.getsourcelines(cls)
    except (OSError, TypeError):
        source, start = (), 0
    annotations = getattr(cls, "__annotations__", {})
    for attr in annotations:
        if attr.startswith("__"):
            continue
        for offset, line in enumerate(source):
            stripped = line.lstrip()
            if stripped.startswith(f"{attr}:"):
                sites[attr] = RuleSite(
                    rule_cls.__site__.file, start + offset,
                    stripped.rstrip("\n"))
                break
    rule_cls.__attr_sites__ = sites


class Rule(Node):
    """The base rule class; annotation-bodied rules (the common case)."""
    __kind__ = "node"
    __schema__ = None
    __node_meta_hook__: ClassVar[Any] = staticmethod(_rule_meta_hook)
    __rule_name__: ClassVar[str]
    __site__: ClassVar[RuleSite]
    __attr_sites__: ClassVar[dict[str, RuleSite]]
    __abstract__ = True

    @classmethod
    def to_ir(cls):
        """Compile the shared ``Child`` declaration to builder IR."""
        return _from_children(cls)


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

def _resolved_name(cls: type[Rule]) -> str:
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


def _wrap(body: B | str, attr: str | None) -> B:
    if attr is not None and attr != "content":
        return tg_field(attr, body)
    return body if isinstance(body, B) else B(as_node(body))


def _target_body(cls: type[Rule], target: Any,
                 namespace: dict[str, Any] | None = None) -> B | str:
    """Render a resolved ``Child.target`` without reparsing annotations."""
    target = _resolve_forward(target, cls, namespace)
    origin = get_origin(target)
    if isinstance(target, type) and issubclass(target, Rule):
        return tg_ref(_resolved_name(target))
    if origin is Literal:
        values = get_args(target)
        return str(values[0]) if len(values) == 1 else tg_choice(
            *[str(value) for value in values])
    if origin is types.UnionType:
        args = tuple(item for item in get_args(target)
                     if item is not type(None))
        if len(args) == 1:
            return _target_body(cls, args[0], namespace)
        return tg_choice(*[_target_body(cls, item, namespace)
                           for item in args])
    if isinstance(target, tuple) and target and all(
            isinstance(item, type) and issubclass(item, Rule)
            for item in target):
        return tg_choice(*[tg_ref(_resolved_name(item)) for item in target])
    raise TypeError(f"{cls.__name__}: cannot compile annotation {target!r}")


def _stamp(cls: type[Rule], body: B | str,
           attr: str | None = None) -> None:
    """Stamp a body's nodes with the class's site (attribute-line precision
    via `__attr_sites__` when known) AT CREATION (D8 — no post-hoc repair;
    provenance lives on the node). Repoints nodes whose site still points
    into this module (rules.py) — annotation/token/pattern compilation
    builds combinator nodes HERE, so their `_track` site is a library
    internal, not the author's file (B10). `__body__` combinator sites land
    in the author's module and are left alone."""
    site = None
    if attr is not None:
        site = cls.__attr_sites__.get(attr)
    site = site or cls.__site__
    for n in _iter_body_nodes(as_node(body)):
        existing = site_of(n)
        if existing is None or existing.file == _RULES_FILE:
            n._site = site   # pydantic private attr


def _from_children(cls: type[Rule],
                   namespace: dict[str, Any] | None = None) -> B | str:
    """Render the shared node declaration into the builder IR."""
    members: list[B | str] = []
    if namespace is None:
        module = sys.modules.get(cls.__module__)
        namespace = vars(module) if module is not None else None
    for child in _children_for(cls, namespace):
        target = _resolve_forward(child.target, cls, namespace)
        if get_origin(target) is Literal:
            values = get_args(target)
            default = cls.__dict__.get(child.name, _UNSET)
            if default is _UNSET:
                field = getattr(cls, "model_fields", {}).get(child.name)
                if field is not None and not field.is_required():
                    default = field.default
            if default is not _UNSET and default not in values:
                raise ValueError(
                    f"{cls.__name__}.{child.name}: Literal[{values!r}] default "
                    f"{default!r} does not match any value — anonymous "
                    f"tokens must default to one of their Literal values, "
                    f"or have no default")
        body = _target_body(cls, target, namespace)
        if child.repeated:
            body = _wrap(body, child.name if child.name != "content" else None)
            body = tg_repeat(body)
        elif child.optional:
            body = tg_opt(body)
            body = _wrap(body, child.name)
        elif get_origin(target) is Literal and len(get_args(target)) == 1:
            pass
        else:
            body = _wrap(body, child.name)
        member = body
        _stamp(cls, member, attr=child.name)
        members.append(member)
    if not members:
        raise ValueError(
            f"{cls.__name__}: no children — annotate at least one attribute, "
            f"or give the rule __body__ / __pattern__ / __external__")
    body = members[0] if len(members) == 1 else tg_seq(*members)
    return body


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

def module_rules(module) -> list[type[Rule]]:
    """The concrete Rule classes DEFINED IN `module` — `cls.__module__ ==
    module.__name__` only (imported classes are excluded: the silent-join
    bug dies, F-B3) — in definition order. The explicit-rules helper (D9):
    rule order and externals order are load-bearing and now visible.
    """
    return [
        obj for obj in vars(module).values()
        if isinstance(obj, type) and issubclass(obj, Rule)
        and hasattr(obj, "__rule_name__")          # concrete (kind bases skip)
        and getattr(obj, "__module__", None) == module.__name__
    ]


def assemble(name: str, *, start: type[Rule],
             rules: Sequence[type[Rule]] | None = None) -> Grammar:
    """Compile rule classes into a builder `Grammar` — the SAME object the
    builder DSL produces, so `run_checks`, `build_builder`, and the bundle
    pipeline are unchanged.

    `rules` is the EXPLICIT class list (D9): its order is load-bearing —
    rule order, and externals order (externals must precede their rules in
    the scanner's expected order — document loudly). Without `rules`, the
    classes DEFINED IN the start class's module are used (module_rules) —
    imported classes never join silently (F-B3).

        def build() -> tg.Grammar:
            return assemble("devenv", start=SourceFile,
                            rules=module_rules(sys.modules[__name__]))
    """
    if not (isinstance(start, type) and issubclass(start, Rule)):
        raise TypeError(
            f"assemble(start=...) needs a Rule subclass, got {start!r}")
    if rules is None:
        rules = module_rules(sys.modules[start.__module__])
    if not rules:
        raise ValueError(
            f"no rule classes found in module {start.__module__!r} — pass "
            f"rules=[...] explicitly or define Rule subclasses at module "
            f"level")

    module = sys.modules.get(start.__module__)
    namespace = dict(vars(module)) if module is not None else {}
    namespace.update({cls.__name__: cls for cls in rules})
    g = Grammar(name)
    for cls in rules:
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
                body = _from_children(cls, namespace)
        if not isinstance(body, B):
            body = B(as_node(body))
        # token-wrap (the guard prevents double-wrapping an already-token body
        # or an External's tok)
        if getattr(cls, "__token__", False) and body.node.type != "TOKEN":
            body = tg_token(body)
        # source sites (D8, B10): repoint any node still carrying a
        # rules.py site — annotation-seq wrappers, pattern/token/external
        # bodies compiled HERE — at the class (or attribute) line.
        # Author-built `__body__` combinator sites are already the author's
        # module lines and are left alone (their file is not rules.py).
        _stamp(cls, body)
        g.rule(rn, body,
               supertype=getattr(cls, "__supertype__", False),
               hidden=getattr(cls, "__hidden__", False),
               inline=getattr(cls, "__inline__", False),
               word=getattr(cls, "__word__", False))
        # source sites (D8): the rule points at its CLASS definition; every
        # annotation-emitted node was already stamped at creation
        # (_from_children); `__body__` combinator sites are stamped by the
        # combinators themselves (the author's module lines)
        g.sites[rn] = cls.__site__
        if getattr(cls, "__extra__", False):
            g.extra(tg_ref(_resolved_name(cls)))
    g.start(_resolved_name(start))
    return g
