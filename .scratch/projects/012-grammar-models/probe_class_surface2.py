"""Probe 2: the rule-class surface with KIND SUBCLASSES + pattern helpers.

Same question as probe 1 — is the grammar.json byte-identical to the
builder-DSL devenv grammar? — but with a refined surface:

  * rule KIND subclasses instead of flag attrs:
        class Number(Pattern)          # bare regex rule      (__pattern__)
        class NamePath(Token)          # token-wrapped        (__pattern__ or __body__)
        class StringFragment(External) # external scanner token
        class Comment(Extra, Token)    # behavioral kinds are MIXINS
        class Value(Supertype)
    The base-class list IS the flag list; the class reads as its own
    declaration. Flags are inherited (assemble uses getattr, not __dict__).
    `External` derives its token name from the rule name (SCREAMING_SNAKE),
    overridable via `__external__`.

  * pattern/token helpers — regex-STRING composition, tree-sitter lexer
    subset (no backrefs / lookaround), so grammar.json carries the same
    strings:
        ident(), integer(), quoted(), slug(), path_literal(),
        dotted_path(), rest_of_line()

Verdict questions: (1) identical IR? (2) is the subclass surface actually
cleaner? (3) do the helpers reproduce the exact regexes?
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Literal, Union, get_args, get_origin

import tsgrammar as tg

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EXAMPLE = REPO / "examples" / "devenv-subset"

# ---------------------------------------------------------------------------
# machinery (same as probe 1, plus kind subclasses + getattr flag reading)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type] = {}


def _snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


class _RuleMeta(type):
    def __new__(mcs, name, bases, ns):
        cls = super().__new__(mcs, name, bases, ns)
        if not ns.get("__abstract__"):          # OWN namespace: kind bases skip
            rn = ns.get("__rule_name__") or _snake(name)
            cls.__rule_name__ = rn
            _REGISTRY[rn] = cls
        return cls


class Rule(metaclass=_RuleMeta):
    """Base for rule declarations. See module docstring for the mapping."""
    __abstract__ = True


# ---- body kinds (abstract bases; they are NOT rules themselves) ------------

class Pattern(Rule):
    """A regex leaf rule — bare `pattern(...)`, not token-wrapped."""
    __abstract__ = True


class Token(Rule):
    """A rule whose body is wrapped in `token(...)` (lexed as ONE token)."""
    __abstract__ = True
    __token__ = True


class External(Rule):
    """A rule backed by an external-scanner token; the token name defaults
    to the rule name in SCREAMING_SNAKE (override with `__external__`)."""
    __abstract__ = True


# ---- behavioral kinds (mixins) ---------------------------------------------

class Extra(Rule):
    """Also an extra — present in the tree as whitespace/comment, matched
    anywhere, never a child."""
    __abstract__ = True
    __extra__ = True


class Supertype(Rule):
    __abstract__ = True
    __supertype__ = True


class Hidden(Rule):
    __abstract__ = True
    __hidden__ = True


class Inline(Rule):
    __abstract__ = True
    __inline__ = True


class Word(Rule):
    __abstract__ = True
    __word__ = True


# ---------------------------------------------------------------------------
# pattern / token helpers (regex-STRING composition; tree-sitter subset)
# ---------------------------------------------------------------------------

def ident(*, hyphen: bool = False) -> str:
    """An identifier: `[a-zA-Z_][a-zA-Z0-9_]*`; `hyphen=True` allows `-`
    in the continuation (nix attr names, css classes)."""
    return r"[a-zA-Z_][a-zA-Z0-9_-]*" if hyphen else r"[a-zA-Z_][a-zA-Z0-9_]*"


def integer() -> str:
    return r"[0-9]+"


def quoted(quote: str = '"') -> str:
    """A quoted string with NO escapes inside: `"[^"]*"`."""
    return f'{quote}[^{quote}]*{quote}'


def slug() -> str:
    """A path-ish chunk: letters, digits, `_`, `.`, `/`, `-`."""
    return r"[A-Za-z0-9_./-]+"


def path_literal() -> str:
    """A nix path literal: `./relative/or/absolute`."""
    return r"\.[/]" + slug()


def dotted_path(segment: str | None = None) -> str:
    """A dotted path, ONE token: `pkgs`  `config.env.DEVENV_ROOT`
    `tasks."quoted".exec`. The FIRST segment may be quoted too; later
    segments are `\\.` + ident-or-quoted (nix attr names allow hyphens).
    Default reproduces the devenv example's exact pattern string."""
    seg = segment or f"{quoted()}|{ident(hyphen=True)}"
    return f"({seg})(\\.{ident(hyphen=True)}|{quoted()})*"


def rest_of_line() -> str:
    return r"[^\n]*"


patterns = types.SimpleNamespace(
    ident=ident, integer=integer, quoted=quoted, slug=slug,
    path_literal=path_literal, dotted_path=dotted_path,
    rest_of_line=rest_of_line)


# ---------------------------------------------------------------------------
# compilation (same as probe 1; flags now read INHERITED via getattr)
# ---------------------------------------------------------------------------

_UNSET = object()


def _resolve(cls: type, ann: str):
    return eval(ann, vars(sys.modules[cls.__module__]))  # noqa: S307


def _wrap(x: tg.B, attr: str | None) -> tg.B:
    if attr is not None and attr != "content":
        return tg.field(attr, x)
    return x


def _child(cls: type, t, attr: str | None = None) -> tg.B:
    origin = get_origin(t)
    if isinstance(t, type) and issubclass(t, Rule):
        return _wrap(tg.ref(t.__rule_name__), attr)
    if origin is Literal:
        return str(get_args(t)[0])
    if origin in (list,):
        inner = _child(cls, get_args(t)[0])
        if attr is not None and attr != "content":
            inner = tg.field(attr, inner)
        return tg.repeat(inner)
    if origin in (types.UnionType, Union):
        args = get_args(t)
        non_none = [a for a in args if a is not type(None)]
        inner = _child(cls, non_none[0])
        if len(non_none) > 1:
            inner = tg.choice(inner, *(_child(cls, a) for a in non_none[1:]))
        if type(None) in args:
            inner = tg.opt(inner)
        return _wrap(inner, attr)
    raise TypeError(f"{cls.__name__}: cannot compile annotation {t!r}")


def _from_annotations(cls: type) -> tg.B:
    members = []
    for attr, ann_str in cls.__annotations__.items():
        if attr.startswith("__"):
            continue
        t = _resolve(cls, ann_str)
        if get_origin(t) is Literal:
            (val,) = get_args(t)
            default = cls.__dict__.get(attr, _UNSET)
            if default is not _UNSET and default != val:
                raise ValueError(
                    f"{cls.__name__}.{attr}: Literal[{val!r}] default "
                    f"{default!r} does not match")
            members.append(val)
        else:
            members.append(_child(cls, t, attr=attr))
    return members[0] if len(members) == 1 else tg.seq(*members)


def R(cls: type) -> tg.B:
    """Ref to a rule class (the `__body__` escape hatch's name layer)."""
    return tg.ref(cls.__rule_name__)


def assemble(name: str, *, start: type) -> tg.Grammar:
    g = tg.Grammar(name)
    for rn, cls in _REGISTRY.items():
        ext = getattr(cls, "__external__", None)
        if ext is None and issubclass(cls, External):
            ext = rn.upper()   # default: rule name in SCREAMING_SNAKE
        if ext is not None:
            g.external(tg.tok(ext))
        body = cls.__dict__.get("__body__")
        if body is None:
            pat = cls.__dict__.get("__pattern__")
            if pat is not None:
                body = tg.token(tg.pattern(pat)) if getattr(cls, "__token__", False) \
                    else tg.pattern(pat)
            elif ext is not None:
                body = tg.tok(ext)
            else:
                body = _from_annotations(cls)
        if getattr(cls, "__token__", False) and body.node.type != "TOKEN":
            body = tg.token(body)
        g.rule(rn, body,
               supertype=getattr(cls, "__supertype__", False),
               hidden=getattr(cls, "__hidden__", False),
               inline=getattr(cls, "__inline__", False),
               word=getattr(cls, "__word__", False))
        if getattr(cls, "__extra__", False):
            g.extra(tg.ref(rn))
    g.start(start.__rule_name__)
    return g


# ---------------------------------------------------------------------------
# the devenv grammar, v2: kind subclasses + pattern helpers
# ---------------------------------------------------------------------------

# ---- lexical --------------------------------------------------------------

class Comment(Extra, Token):
    """`# ...` to end of line — an extra (never a tree node)."""
    __body__ = tg.seq("#", tg.pattern(rest_of_line()))


class NamePath(Token):
    """ONE token: `pkgs`  `config.env.DEVENV_ROOT`  `scripts.hello.exec`
    `"quoted"`  `tasks."quoted".exec` — the text-yielding key leaf Product A
    needs (`key: str = capture("key")`)."""
    __pattern__ = dotted_path()


class Number(Pattern):
    __pattern__ = integer()


class PathLiteral(Token):
    __pattern__ = path_literal()


class StringFragment(External):
    """External-scanner token (scanner.c): a `"..."` string body chunk."""


class IndentedStringFragment(External):
    """External-scanner token: a `''...''` multiline string body chunk."""


# ---- strings --------------------------------------------------------------

class Interpolation(Rule):
    """`${ value }` — the fielded child is what Product A captures."""
    open: Literal["${"] = "${"
    expression: Value
    close: Literal["}"] = "}"


class String(Rule):
    open: Literal['"'] = '"'
    content: list[StringFragment | Interpolation]
    close: Literal['"'] = '"'


class IndentedString(Rule):
    open: Literal["''"] = "''"
    content: list[IndentedStringFragment | Interpolation]
    close: Literal["''"] = "''"


# ---- structure ------------------------------------------------------------

class Pair(Rule):
    """The direct-child-kind pair with key/value FIELDS — the exact shape
    record mode's pair-kind detection needs."""
    key: NamePath
    eq: Literal["="] = "="
    value: Value
    semi: Literal[";"] = ";"


class Attrset(Rule):
    open: Literal["{"] = "{"
    content: list[Pair]
    close: Literal["}"] = "}"


class ListRule(Rule):
    """`[ ... ]` — `list` is a builtin, hence `__rule_name__`."""
    __rule_name__ = "list"
    open: Literal["["] = "["
    element: list[Value]
    close: Literal["]"] = "]"


class WithExpr(Rule):
    """`with pkgs; value` — two UNNAMED refs (annotations are fielded by
    construction; Python can't repeat `_`), so `__body__`. `tg.ref("value")`
    is a cycle point: `Value` is defined below — grammars are cyclic DAGs."""
    __body__ = tg.seq("with", R(NamePath), ";", tg.ref("value"))


class Value(Supertype):
    """The supertype over every value shape — a bare alternation (a CHOICE
    has no field names to annotate). `tg.ref("with_expr")` is the cycle
    point back to `WithExpr`."""
    __body__ = tg.choice(R(String), R(IndentedString), R(ListRule),
                         R(Attrset), R(NamePath), R(Number), R(PathLiteral),
                         tg.ref("with_expr"))


class Formal(Rule):
    """`{ pkgs, lib, config, inputs, ... }:` header — each formal OPTIONALLY
    eats its trailing comma (the real nix grammar's trick)."""
    __body__ = tg.seq(R(NamePath), tg.opt(","))


class Formals(Rule):
    __body__ = tg.seq("{", tg.repeat(R(Formal)), tg.opt("..."), "}")


class SourceFile(Rule):
    __body__ = tg.seq(tg.opt(tg.seq(R(Formals), ":")), R(Attrset))


# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------

def main() -> int:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(EXAMPLE))
    from grammar import build as original_build

    g_new = assemble("devenv", start=SourceFile)
    g_old = original_build()
    new_json = json.loads(g_new.build().model_dump_json(exclude_none=True))
    old_json = json.loads(g_old.build().model_dump_json(exclude_none=True))

    identical = new_json == old_json
    print(f"[1] grammar.json identical to the builder-DSL version: "
          f"{'YES' if identical else 'NO'}")
    if not identical:
        import difflib
        a = json.dumps(old_json, indent=2, sort_keys=True).splitlines()
        b = json.dumps(new_json, indent=2, sort_keys=True).splitlines()
        print("\n".join(difflib.unified_diff(a, b, "old", "new",
                                             lineterm=""))[:4000])
        return 1

    print("[2] rule classes:")
    for rn in _REGISTRY:
        cls = _REGISTRY[rn]
        bases = ", ".join(b.__name__ for b in cls.__bases__)
        print(f"      {rn:24} ({bases})")

    print("[3] helper-produced regexes equal the hand-written ones:")
    for rn, want in [
        ("name_path", r'("[^"]*"|[a-zA-Z_][a-zA-Z0-9_-]*)'
                      r'(\.[a-zA-Z_][a-zA-Z0-9_-]*|"[^"]*")*'),
        ("number", r"[0-9]+"),
        ("path_literal", r"\.[/][A-Za-z0-9_./-]+"),
    ]:
        got = {"name_path": dotted_path(), "number": integer(),
               "path_literal": path_literal()}[rn]
        print(f"      {rn:12} helper == hand-written: {got == want}")
        assert got == want

    issues = list(tg.run_checks(g_new))
    print(f"[4] run_checks clean: {not tg.errors(g_new)} "
          f"({len(issues)} issues total)")
    result = tg.build_builder(g_new, scanner=str(EXAMPLE / "scanner.c"))
    lang, _lib = result.language()
    src = (EXAMPLE / "fixtures" / "pydantree.nix").read_text()
    tree = tg.parse(lang, src)
    print(f"[5] smoke parse: {len(src.splitlines())} lines -> "
          f"{tree.root_node.type} root, {tree.root_node.child_count} children")
    return 0 if (identical and not tg.errors(g_new)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
