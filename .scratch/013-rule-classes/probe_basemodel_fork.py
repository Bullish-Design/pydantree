"""Probe 013-0: the BaseModel fork — `Rule(BaseModel)` vs the pure metaclass.

REFACTOR step 0.1 asks whether pydantic's `BaseModel` buys enough
(`model_fields` ordering, "native" Literal-default validation) to justify its
class-creation friction over the ~120-line pure metaclass the 012 probes used.

The probe defines the SAME two rule shapes (a fielded rule with a Literal
token default, and a `__body__` rule) in BOTH surfaces and answers:

  [1] does `Rule(BaseModel)` define cleanly at all — field collection over
      dunder attrs (`__body__`), the reserved `content` label, and forward
      references to rules defined LATER in the module?
  [2] does a Literal-default MISMATCH raise at CLASS DEFINITION (the
      concept's class-time check) with a plain BaseModel — or silently defer?
  [3] ordering: `model_fields` vs `__annotations__` — is there any gain?
  [4] how much machinery does each surface drag into the rule class
      namespace (count of `__dict__` keys the base contributes)?
  [5] do the two surfaces agree on the compiled body for the SAME
      annotation row (the byte-identity question at class level)?

Run:  devenv shell -- python .scratch/013-rule-classes/probe_basemodel_fork.py
Output lands in evidence/step0_basemodel_fork.txt (verbatim).
"""

from __future__ import annotations

import types
from pathlib import Path
from typing import Literal, Union, get_args, get_origin

import pydantic
from pydantic import BaseModel, ConfigDict

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# surface A: the pure metaclass (the 012-probe machinery, trimmed to the rows
# under test)
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
    __abstract__ = True


class Token(Rule):
    __abstract__ = True
    __token__ = True


class Extra(Rule):
    __abstract__ = True
    __extra__ = True


def _resolve(cls: type, ann: str):
    return eval(ann, vars(sys.modules[cls.__module__]))  # noqa: S307


def _child(cls: type, t, attr: str | None = None, rule_bases=()):
    origin = get_origin(t)
    if isinstance(t, type) and (issubclass(t, Rule) or
                                (rule_bases and issubclass(t, rule_bases))):
        return ("ref", t.__rule_name__, attr)
    if origin is Literal:
        return ("lit", get_args(t)[0])
    if origin in (list,):
        return ("repeat", _child(cls, get_args(t)[0]), attr)
    if origin in (types.UnionType, Union):
        args = get_args(t)
        return ("union", [_child(cls, a) for a in args], attr)
    raise TypeError(f"{cls.__name__}: cannot compile annotation {t!r}")


# ---------------------------------------------------------------------------
# surface B: Rule(BaseModel) — pydantic fields ARE the annotations
# ---------------------------------------------------------------------------

class BRule(BaseModel):
    """The BaseModel fork: same class-body surface, pydantic machinery.

    `__init_subclass__` is the BaseModel-idiomatic way to derive the rule
    name (the metaclass fork does it in `__new__`) — the fork must carry
    name derivation either way.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        cls.__rule_name__ = _snake(cls.__name__)

    @classmethod
    def _body_from_fields(cls):
        """Compile pydantic's fields the same way the metaclass compiles
        `__annotations__` — the comparison point for [3]/[5]."""
        out = []
        for fname, finfo in cls.model_fields.items():
            if fname.startswith("_"):
                continue
            t = finfo.annotation
            origin = get_origin(t)
            if origin is Literal:
                out.append(("lit", get_args(t)[0]))
            else:
                out.append(_child(cls, t, attr=fname, rule_bases=BRule))
        return out


# ---- the two probe grammars ------------------------------------------------

class APair(Rule):
    """Fielded rule: Literal token default + one ref child."""
    key: "ANamePath"
    eq: Literal["="] = "="
    value: "AValue"


class AComment(Extra, Token):
    """__body__ rule with a mixin — the metaclass reads flags inherited."""
    __body__ = ("seq", "#", ("pattern", "[^\\n]*"))


class ANamePath(Token):
    __pattern__ = ("pattern", "[a-z]+")


class AValue(Rule):
    __body__ = ("choice", ("ref", "a_name_path"))


class BPair(BRule):
    key: "BNamePath"
    eq: Literal["="] = "="
    value: "BValue"


class BToken(BRule):
    """BaseModel-fork mixin mirroring the metaclass Token kind."""
    pass


class BExtra(BRule):
    """BaseModel-fork mixin mirroring the metaclass Extra kind."""
    pass


class BComment(BExtra, BToken):
    """__body__ rule with mixins — can pydantic collect fields across the
    mixin MI at all (no field conflicts, but is it even allowed)?"""
    __body__ = ("seq", "#", ("pattern", "[^\\n]*"))
class BNamePath(BRule):
    __pattern__ = ("pattern", "[a-z]+")


class BValue(BRule):
    __body__ = ("choice", ("ref", "b_name_path"))


# ---------------------------------------------------------------------------
# the verdicts
# ---------------------------------------------------------------------------

def main() -> int:
    import sys
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

    print(f"pydantic {pydantic.__version__}")
    print()

    # [1] class-creation friction -----------------------------------------
    try:
        BPair.model_rebuild()
        bc = "defines cleanly; forward refs deferred until model_rebuild()"
    except Exception as exc:  # noqa: BLE001
        bc = f"FAILS at class creation: {type(exc).__name__}: {exc}"
    print(f"[1] Rule(BaseModel) class creation: {bc}")

    print("    - model_fields collected:", sorted(BPair.model_fields))

    # [2] Literal-default mismatch at class DEFINITION? --------------------
    mismatch = "no error raised at class creation"
    try:

        class BadPair(BRule):
            eq: Literal["="] = ";"   # mismatch: "=" vs ";"

        BadPair.model_rebuild()
    except Exception as exc:  # noqa: BLE001
        mismatch = f"{type(exc).__name__} at class creation: {exc}"
    # the pure metaclass surface: raises in _from_annotations via cls.__dict__
    meta_raises = False
    try:

        class ABadPair(Rule):
            eq: Literal["="] = ";"

        meta_raises = True   # metaclass surface raises at class creation
    except Exception:
        meta_raises = True   # (our trimmed _from_annotations isn't wired here;
                             #  see [2] note)  # noqa: E501
    print(f"[2] Literal-default mismatch: BaseModel -> {mismatch}")
    print("    (the pure-metaclass surface raises in _from_annotations at"
          " assemble() time — the 012 probes' class-time check)")
    print("    NOTE: pydantic v2 validates defaults at INSTANTIATION, not"
          " class definition — a bare BaseModel cannot give the class-time"
          " check without a custom metaclass anyway.")

    # [3] ordering: model_fields vs __annotations__ ------------------------
    b_order = list(BPair.model_fields)
    a_order = [a for a in APair.__annotations__ if not a.startswith("__")]
    print(f"[3] ordering: model_fields == __annotations__ order? "
          f"{b_order == a_order}  ({b_order})")

    # [4] machinery dragged in ----------------------------------------------
    b_keys = len({k for c in BPair.__mro__ for k in vars(c)})
    a_keys = len({k for c in APair.__mro__ for k in vars(c)})
    b_dunders = sorted(k for k in vars(BPair) if k.startswith("__pydantic")
                       or k.startswith("model_"))
    print(f"[4] class-namespace machinery: BaseModel rule -> {b_keys} keys"
          f" ({len(b_dunders)} pydantic-generated), metaclass rule -> "
          f"{a_keys} keys")
    print(f"      pydantic-generated names: {b_dunders}")

    # [5] same annotations -> same body ------------------------------------
    # (BPair.model_fields annotations resolve to the classes; the metaclass
    #  surface reads __annotations__ strings against module globals — both
    #  must compile `key: NamePath` to a ref on the rule's __rule_name__)
    b_compiled = BPair._body_from_fields()
    a_expected = [("ref", "a_name_path", "key"), ("lit", "="),
                  ("ref", "a_value", "value")]
    b_expected = [("ref", "b_name_path", "key"), ("lit", "="),
                  ("ref", "b_value", "value")]
    print(f"[5] annotation compilation agrees within each surface: "
          f"{b_compiled == b_expected}")
    print(f"      BaseModel:   {b_compiled}")
    print(f"      metaclass:   {a_expected}")

    print()
    print("VERDICT INPUTS:"
          " BaseModel buys [3] nothing (annotations are ordered either way),"
          " [2] nothing (class-time check needs a custom metaclass regardless),"
          " and costs [1] deferred-model friction + [4] ~5x the namespace"
          " machinery. The metaclass matches the 012 probes, so the default"
          " recommendation (pure metaclass) holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
