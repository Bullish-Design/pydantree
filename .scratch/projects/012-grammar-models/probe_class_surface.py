"""Probe: can Product B's authoring surface be the grammar RULES as classes?

The B-side mirror of Product A's "the model IS the query": each rule is a
class; the class body IS the production. A metaclass compiles the classes
into the existing `pydantree_sitter_grammar` builder (which emits the pydantic Grammar IR),
and we assert the RESULT IS BYTE-IDENTICAL grammar.json to the current
`examples/devenv-subset/grammar.py` builder-DSL version.

Surface rules (this probe's design decision — NOT a library change):
  * annotated attributes = ORDERED CHILDREN of the production:
      - `key: NamePath`            -> field("key", ref("name_path"))
      - `element: list[Value]`     -> field("element", repeat(ref("value")))
      - `value: Num | Ident`       -> field("value", choice(ref, ref))
      - `maybe: Ident | None`      -> field("maybe", opt(ref))
      - `eq: Literal["="] = "="`   -> anonymous token "="  (attr name is a
                                      READ label only; default must equal the
                                      Literal value — a free class-time check)
  * class attrs carry the flags/leaf forms:
      `__pattern__` (regex), `__token__`, `__external__`, `__extra__`,
      `__supertype__`, `__hidden__`, `__inline__`, `__word__`,
      `__rule_name__` (builtin-name escape: `list` -> class `ListRule`),
      `__body__` (escape hatch: raw combinators, refs via R(Class)).
  * forward refs are legal (grammar rules are mutually recursive): at the
    cycle points, `__body__` uses the underlying DSL's string ref
    (`tg.ref("value")` — exactly as today); elsewhere `R(Class)` is eager.
    Annotations resolve against the defining module's globals at
    `assemble()` time — pydantic's `model_rebuild` pattern.

Verdict questions: (1) identical IR? (2) which rules map to annotations vs
`__body__`? (3) what does NOT map, and is the split coherent?
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Literal, Union, get_args, get_origin

import pydantree_sitter_grammar as tg

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EXAMPLE = REPO / "examples" / "devenv-subset"

# ---------------------------------------------------------------------------
# the class surface (probe-local; ~90 lines, pure-Python, no library changes)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type] = {}   # rule_name -> class, in definition order


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
        if not ns.get("__abstract__"):
            rn = ns.get("__rule_name__") or _snake(name)
            cls.__rule_name__ = rn
            _REGISTRY[rn] = cls
        return cls


class Rule(metaclass=_RuleMeta):
    """Base class for rule declarations. See module docstring for the
    attribute -> production mapping."""
    __abstract__ = True


def R(cls: type) -> tg.B:
    """Ref to a rule class (the `__body__` escape hatch's name layer).
    EAGER: the class must already be defined (Python name resolution). At
    the mutual-recursion cycle points use the underlying DSL's own string
    form instead: `tg.ref("value")` — exactly as today."""
    return tg.ref(cls.__rule_name__)


_UNSET = object()


def _resolve(cls: type, ann: str):
    return eval(ann, vars(sys.modules[cls.__module__]))  # noqa: S307


def _wrap(x: tg.B, attr: str | None) -> tg.B:
    """Field-wrap a top-level child unless it's the reserved `content`
    label (unnamed)."""
    if attr is not None and attr != "content":
        return tg.field(attr, x)
    return x


def _child(cls: type, t, attr: str | None = None) -> tg.B:
    """Compile an annotated child. The CST-field placement follows the
    original builder DSL's shapes:
      - `key: NamePath`      -> field("key", ref)           (field at top)
      - `element: list[T]`   -> repeat(field("element", T))  (field INSIDE
        the repeat — the IR shape of the original list rule)
      - `content: list[T]`   -> repeat(T)                   (unnamed repeat)
      - `value: A | B`       -> field("value", choice(A, B))
      - `maybe: A | None`    -> field("maybe", opt(A))
      - `eq: Literal["="]`  -> anonymous token "="         (never fielded)"""
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
        origin = get_origin(t)
        if origin is Literal:
            (val,) = get_args(t)
            default = cls.__dict__.get(attr, _UNSET)
            if default is not _UNSET and default != val:
                raise ValueError(
                    f"{cls.__name__}.{attr}: Literal[{val!r}] default "
                    f"{default!r} does not match — the grammar.json token "
                    f"would silently change")
            members.append(val)                    # anonymous token, no field
        else:
            # `content` is the reserved label for an UNNAMED child (the
            # IR's own slot name); every other attr name is a CST field.
            members.append(_child(cls, t, attr=attr))
    return members[0] if len(members) == 1 else tg.seq(*members)


def assemble(name: str, *, start: type) -> tg.Grammar:
    g = tg.Grammar(name)
    for rn, cls in _REGISTRY.items():
        ext = cls.__dict__.get("__external__")
        if ext is not None:
            g.external(tg.tok(ext))
        body = cls.__dict__.get("__body__")
        if body is None:
            pat = cls.__dict__.get("__pattern__")
            if pat is not None:
                body = tg.token(tg.pattern(pat)) if cls.__dict__.get("__token__") \
                    else tg.pattern(pat)
            elif ext is not None:
                body = tg.tok(ext)
            else:
                body = _from_annotations(cls)
        if cls.__dict__.get("__token__") and body.node.type != "TOKEN":
            body = tg.token(body)
        g.rule(rn, body,
               supertype=bool(cls.__dict__.get("__supertype__")),
               hidden=bool(cls.__dict__.get("__hidden__")),
               inline=bool(cls.__dict__.get("__inline__")),
               word=bool(cls.__dict__.get("__word__")))
        if cls.__dict__.get("__extra__"):
            g.extra(tg.ref(rn))
    g.start(start.__rule_name__)
    return g


# ---------------------------------------------------------------------------
# the devenv grammar, authored as classes (definition order == the original
# `g.rule(...)` call order, so the emitted `rules` dict matches exactly)
# ---------------------------------------------------------------------------

# ---- lexical --------------------------------------------------------------

class Comment(Rule):
    """# ... to end of line — an extra, never a tree node."""
    __extra__ = True
    __body__ = tg.token(tg.seq("#", tg.pattern(r"[^\n]*")))


class NamePath(Rule):
    """ONE token: `pkgs` `config.env.DEVENV_ROOT` `scripts.hello.exec`
    `"quoted"` `tasks."quoted".exec` — the text-yielding key leaf Product A
    needs (`key: str = capture("key")`)."""
    __token__ = True
    __pattern__ = r'("[^"]*"|[a-zA-Z_][a-zA-Z0-9_-]*)(\.[a-zA-Z_][a-zA-Z0-9_-]*|"[^"]*")*'


class Number(Rule):
    __pattern__ = r"[0-9]+"


class PathLiteral(Rule):
    __token__ = True
    __pattern__ = r"\.[/][A-Za-z0-9_./-]+"


class StringFragment(Rule):
    """External-scanner token (scanner.c): the `"..."` string body."""
    __external__ = "STRING_FRAGMENT"


class IndentedStringFragment(Rule):
    """External-scanner token: the `''...''` multiline string body."""
    __external__ = "INDENTED_STRING_FRAGMENT"


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
    __rule_name__ = "list"          # `list` is a builtin; the kind stays "list"
    open: Literal["["] = "["
    element: list[Value]
    close: Literal["]"] = "]"


class WithExpr(Rule):
    """`with pkgs; value` — two UNNAMED refs, so this stays in `__body__`
    (annotations are fielded by construction; Python can't repeat `_`).
    `tg.ref("value")` is a cycle point: `Value` is defined below (grammar
    rules are a cyclic DAG), so the underlying DSL's string ref is used."""
    __body__ = tg.seq("with", R(NamePath), ";", tg.ref("value"))


class Value(Rule):
    """The supertype over every value shape — a bare alternation, so it too
    stays in `__body__` (a CHOICE has no field names to annotate)."""
    __supertype__ = True
    __body__ = tg.choice(R(String), R(IndentedString), R(ListRule),
                         R(Attrset), R(NamePath), R(Number), R(PathLiteral),
                         tg.ref("with_expr"))


class Formal(Rule):
    """`{ pkgs, lib, ... }:` header formal — each OPTIONALLY eats its comma."""
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

    # 1. IR fidelity: byte-identical grammar.json?
    identical = new_json == old_json
    print(f"[1] grammar.json identical to the builder-DSL version: "
          f"{'YES' if identical else 'NO'}")
    if not identical:
        import difflib
        a = json.dumps(old_json, indent=2, sort_keys=True).splitlines()
        b = json.dumps(new_json, indent=2, sort_keys=True).splitlines()
        print("\n".join(difflib.unified_diff(a, b, "old", "new", lineterm=""))[:4000])
        return 1

    # 2. which rules used which mechanism
    mech = {"annotations": [], "pattern/token": [], "external": [],
            "__body__": []}
    for rn, cls in _REGISTRY.items():
        if cls.__dict__.get("__external__"):
            mech["external"].append(rn)
        elif cls.__dict__.get("__pattern__"):
            mech["pattern/token"].append(rn)
        elif cls.__dict__.get("__body__"):
            mech["__body__"].append(rn)
        else:
            mech["annotations"].append(rn)
    print("[2] authoring mechanism per rule:")
    for k, v in mech.items():
        print(f"      {k:14} {v}")

    # 3. checks + build + smoke parse still work
    issues = list(tg.run_checks(g_new))
    print(f"[3] run_checks clean: {not tg.errors(g_new)} "
          f"({len(issues)} issues total)")
    result = tg.build_builder(g_new, scanner=str(EXAMPLE / "scanner.c"))
    lang, _lib = result.language()

    src = (EXAMPLE / "fixtures" / "pydantree.nix").read_text()
    tree = tg.parse(lang, src)
    text = src
    print(f"[4] smoke parse: {len(src.splitlines())} lines -> "
          f"{tree.root_node.type} root, {tree.root_node.child_count} children")
    for n in tree.root_node.children:
        seg = text[n.start_byte:n.end_byte]
        print(f"      {n.type:12} {seg[:44]!r}")

    return 0 if (identical and not tg.errors(g_new)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
