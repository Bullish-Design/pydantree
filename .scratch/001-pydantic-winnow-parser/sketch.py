"""
Sketch: GrammarModel (IR as a Pydantic discriminated union) + builder sugar
+ a pure-Python executor + compile-time bridge validation against OutputModels.

Run: .venv/bin/python sketch.py

This is a feel-the-ergonomics prototype, NOT a real engine. It demonstrates:
  1. GrammarModel node hierarchy as a Pydantic tagged union  -> validated, serializable IR
  2. RuleRef + a Grammar registry                            -> recursion without cyclic instances
  3. A builder/operator DSL that EMITS GrammarModels          -> authoring isn't raw-model-instantiation
  4. A grammar<->output BRIDGE that is type-checked at compile time
  5. A tiny pure-Python backend that walks the IR and produces OutputModels
"""

from __future__ import annotations

import typing
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field as PField, TypeAdapter


# =============================================================================
# 1. GrammarModel: the IR, expressed as a Pydantic discriminated union.
#    Each node is a frozen model with a `kind` discriminator. Because these are
#    Pydantic models we get validation, serialization, and round-tripping free.
# =============================================================================

class GNode(BaseModel):
    model_config = {"frozen": True}


class LiteralNode(GNode):
    kind: Literal["literal"] = "literal"
    value: str


class CharClassNode(GNode):
    kind: Literal["charclass"] = "charclass"
    cls: Literal["alpha", "digit", "alnum", "ws"]
    min: int = 1


class SkipNode(GNode):
    kind: Literal["skip"] = "skip"
    child: "NodeUnion"


class FieldNode(GNode):
    kind: Literal["field"] = "field"
    name: str
    child: "NodeUnion"


class SeqNode(GNode):
    kind: Literal["seq"] = "seq"
    children: list["NodeUnion"]


class ChoiceNode(GNode):
    kind: Literal["choice"] = "choice"
    children: list["NodeUnion"]


class OptionalNode(GNode):
    kind: Literal["optional"] = "optional"
    child: "NodeUnion"


class RepeatNode(GNode):
    kind: Literal["repeat"] = "repeat"
    child: "NodeUnion"
    sep: Optional["NodeUnion"] = None
    min: int = 0


class TransformNode(GNode):
    kind: Literal["transform"] = "transform"
    op: Literal["parse_int"]
    child: "NodeUnion"


class ProduceNode(GNode):
    """Bridge node: run `child`, collect its fields, build OutputModel `model`."""
    kind: Literal["produce"] = "produce"
    model: str          # OutputModel class name, resolved via the registry
    child: "NodeUnion"


class RuleRefNode(GNode):
    kind: Literal["ruleref"] = "ruleref"
    name: str


# The tagged union. This is what makes serialize -> deserialize reconstruct the
# correct subtype (see the round-trip demo at the bottom).
NodeUnion = Annotated[
    Union[
        LiteralNode, CharClassNode, SkipNode, FieldNode, SeqNode, ChoiceNode,
        OptionalNode, RepeatNode, TransformNode, ProduceNode, RuleRefNode,
    ],
    PField(discriminator="kind"),
]

for _cls in (SkipNode, FieldNode, SeqNode, ChoiceNode, OptionalNode,
             RepeatNode, TransformNode, ProduceNode):
    _cls.model_rebuild()

NODE_ADAPTER = TypeAdapter(NodeUnion)


# =============================================================================
# 3. Builder sugar. Combinators wrap a node and emit GrammarModels. This is the
#    ergonomic authoring layer; GrammarModel stays the canonical, validated form.
# =============================================================================

class B:
    def __init__(self, node: GNode):
        self.node = node

    # a + b  ->  sequence (flattening nested seqs)
    def __add__(self, other: "B") -> "B":
        left = self.node.children if isinstance(self.node, SeqNode) else [self.node]
        right = other.node.children if isinstance(other.node, SeqNode) else [other.node]
        return B(SeqNode(children=[*left, *right]))

    # a | b  ->  ordered choice (flattening)
    def __or__(self, other: "B") -> "B":
        left = self.node.children if isinstance(self.node, ChoiceNode) else [self.node]
        right = other.node.children if isinstance(other.node, ChoiceNode) else [other.node]
        return B(ChoiceNode(children=[*left, *right]))

    def capture(self, name: str) -> "B":
        return B(FieldNode(name=name, child=self.node))

    def optional(self) -> "B":
        return B(OptionalNode(child=self.node))

    def repeat(self, sep: "B | None" = None, min: int = 0) -> "B":
        return B(RepeatNode(child=self.node, sep=sep.node if sep else None, min=min))

    def parse_int(self) -> "B":
        return B(TransformNode(op="parse_int", child=self.node))

    def produce(self, model: type[BaseModel]) -> "B":
        return B(ProduceNode(model=model.__name__, child=self.node))


# primitive constructors
def lit(value: str) -> B:
    return B(LiteralNode(value=value))

def skip(x: "B | str") -> B:
    node = x.node if isinstance(x, B) else LiteralNode(value=x)
    return B(SkipNode(child=node))

def field(name: str, x: B) -> B:
    return x.capture(name)

def seq(*xs: B) -> B:
    out = xs[0]
    for x in xs[1:]:
        out = out + x
    return out

def ref(name: str) -> B:
    return B(RuleRefNode(name=name))

alpha1 = B(CharClassNode(cls="alpha"))
digit1 = B(CharClassNode(cls="digit"))
ws0 = B(CharClassNode(cls="ws", min=0))


# =============================================================================
# 5. A tiny pure-Python backend: walk the IR, produce values / OutputModels.
#    (No spans/arena/backtracking-optimizations here — just enough to run.)
# =============================================================================

class ParseFail(Exception):
    pass

class _Field:
    __slots__ = ("name", "value")
    def __init__(self, name, value):
        self.name, self.value = name, value

_PREDS = {
    "alpha": str.isalpha,
    "digit": str.isdigit,
    "alnum": str.isalnum,
    "ws": lambda c: c in " \t",
}
_TRANSFORMS = {"parse_int": int}


def run(node: GNode, s: str, pos: int, g: "Grammar"):
    k = node.kind
    if k == "literal":
        if s.startswith(node.value, pos):
            return node.value, pos + len(node.value)
        raise ParseFail(f"expected {node.value!r} at {pos}")
    if k == "charclass":
        pred = _PREDS[node.cls]
        start = pos
        while pos < len(s) and pred(s[pos]):
            pos += 1
        if pos - start < node.min:
            raise ParseFail(f"expected {node.cls} at {start}")
        return s[start:pos], pos
    if k == "skip":
        _, pos = run(node.child, s, pos, g)
        return None, pos
    if k == "field":
        val, pos = run(node.child, s, pos, g)
        return _Field(node.name, val), pos
    if k == "seq":
        collected: dict = {}
        for c in node.children:
            v, pos = run(c, s, pos, g)
            if isinstance(v, _Field):
                collected[v.name] = v.value
        return collected, pos
    if k == "produce":
        d, pos = run(node.child, s, pos, g)
        if isinstance(d, _Field):          # produce wrapping a single field
            d = {d.name: d.value}
        model = g.models[node.model]
        return model(**d), pos
    if k == "transform":
        v, pos = run(node.child, s, pos, g)
        return _TRANSFORMS[node.op](v), pos
    if k == "optional":
        try:
            return run(node.child, s, pos, g)
        except ParseFail:
            return None, pos
    if k == "choice":
        for c in node.children:
            try:
                return run(c, s, pos, g)
            except ParseFail:
                continue
        raise ParseFail(f"no choice matched at {pos}")
    if k == "repeat":
        items = []
        try:
            v, pos = run(node.child, s, pos, g)
            items.append(v)
        except ParseFail:
            if node.min == 0:
                return items, pos
            raise
        while True:
            save = pos
            try:
                if node.sep is not None:
                    _, pos = run(node.sep, s, pos, g)
                v, pos = run(node.child, s, pos, g)
                items.append(v)
            except ParseFail:
                pos = save
                break
        if len(items) < node.min:
            raise ParseFail("too few repetitions")
        return items, pos
    if k == "ruleref":
        return run(g.rules[node.name], s, pos, g)
    raise AssertionError(f"unknown node {k}")


# =============================================================================
# 4. The Grammar registry + compile-time bridge validation.
# =============================================================================

def _infer_output_type(node: GNode, g: "Grammar"):
    """Best-effort static type a node produces — used to check the bridge."""
    k = node.kind
    if k in ("literal", "charclass"):
        return str
    if k == "transform" and node.op == "parse_int":
        return int
    if k == "optional":
        return Optional[_infer_output_type(node.child, g)]
    if k == "repeat":
        return list
    if k == "produce":
        return g.models[node.model]
    if k == "ruleref":
        return _infer_output_type(g.rules[node.name], g)
    if k == "field":
        return _infer_output_type(node.child, g)
    return typing.Any


def _iter_fields(node: GNode):
    if node.kind == "field":
        yield node
    for attr in ("child", "sep"):
        c = getattr(node, attr, None)
        if isinstance(c, GNode):
            yield from _iter_fields(c)
    for c in getattr(node, "children", []) or []:
        yield from _iter_fields(c)


class Grammar:
    def __init__(self, rules: dict[str, B], entry: str, models: list[type[BaseModel]]):
        self.rules = {name: b.node for name, b in rules.items()}
        self.entry = entry
        self.models = {m.__name__: m for m in models}

    def validate_bridge(self) -> list[str]:
        """Check that every produce-node's captured field types match the
        OutputModel's declared field types. This is the capability jc/TextFSM
        cannot offer: the grammar and the output schema are cross-checked
        BEFORE any input is parsed."""
        errors: list[str] = []
        for rule_name, node in self.rules.items():
            for prod in _find_produce(node):
                model = self.models[prod.model]
                declared = {n: f.annotation for n, f in model.model_fields.items()}
                for fnode in _direct_fields(prod.child):
                    got = _infer_output_type(fnode.child, self)
                    if fnode.name not in declared:
                        errors.append(
                            f"[{rule_name}] grammar captures '{fnode.name}' but "
                            f"{model.__name__} has no such field")
                        continue
                    want = declared[fnode.name]
                    if not _types_compatible(got, want):
                        errors.append(
                            f"[{rule_name}] field '{fnode.name}': grammar yields "
                            f"{_tn(got)} but {model.__name__}.{fnode.name} is {_tn(want)}")
        return errors

    def parse(self, text: str):
        val, pos = run(self.rules[self.entry], text, 0, self)
        return val


def _find_produce(node: GNode):
    if node.kind == "produce":
        yield node
    for attr in ("child", "sep"):
        c = getattr(node, attr, None)
        if isinstance(c, GNode):
            yield from _find_produce(c)
    for c in getattr(node, "children", []) or []:
        yield from _find_produce(c)


def _direct_fields(node: GNode):
    """Fields directly owned by a produce's sequence (not nested produces)."""
    if node.kind == "produce":
        return
    if node.kind == "field":
        yield node
        return
    for attr in ("child", "sep"):
        c = getattr(node, attr, None)
        if isinstance(c, GNode):
            yield from _direct_fields(c)
    for c in getattr(node, "children", []) or []:
        yield from _direct_fields(c)


def _types_compatible(got, want) -> bool:
    if got is typing.Any or want is typing.Any:
        return True
    if got == want:
        return True
    # unwrap list[X] on the want side vs bare list from repeat inference
    if typing.get_origin(want) is list and got is list:
        return True
    return False


def _tn(t) -> str:
    return getattr(t, "__name__", str(t))


# =============================================================================
# 6. End-to-end example.
# =============================================================================

# --- OutputModels: ordinary Pydantic, the parser's output ---
class Assignment(BaseModel):
    name: str
    value: int

class Document(BaseModel):
    assignments: list[Assignment]


# --- Grammar authored via the builder DSL (emits GrammarModels) ---
identifier = alpha1
integer = digit1.parse_int()

assignment = seq(
    field("name", identifier),
    skip(ws0), skip("="), skip(ws0),
    field("value", integer),
).produce(Assignment)

# `document` references `assignment` BY NAME (RuleRef) — recursion/reuse without
# embedding cyclic model instances.
document = seq(
    field("assignments", ref("assignment").repeat(sep=skip("\n"), min=0)),
).produce(Document)

grammar = Grammar(
    rules={"assignment": assignment, "document": document},
    entry="document",
    models=[Assignment, Document],
)


def main():
    print("=" * 70)
    print("IR is a Pydantic model — here's the `assignment` rule as data:")
    print("=" * 70)
    print(assignment.node.model_dump_json(indent=2))

    print("\n" + "=" * 70)
    print("Serialize -> deserialize round-trip reconstructs the right subtypes:")
    print("=" * 70)
    dumped = assignment.node.model_dump()
    restored = NODE_ADAPTER.validate_python(dumped)
    print("round-trips equal:", restored == assignment.node)
    print("restored type    :", type(restored).__name__)

    print("\n" + "=" * 70)
    print("Compile-time bridge validation (grammar <-> OutputModel):")
    print("=" * 70)
    errs = grammar.validate_bridge()
    print("errors:", errs or "none — grammar captures match OutputModel fields")

    print("\n" + "=" * 70)
    print("Run the pure-Python backend on real input:")
    print("=" * 70)
    src = "width=1920\nheight=1080\ndepth=24"
    result = grammar.parse(src)
    print("input :", repr(src))
    print("output:", result)
    print("typed?:", isinstance(result, Document),
          "->", [type(a).__name__ for a in result.assignments])

    print("\n" + "=" * 70)
    print("Now break the bridge on purpose (declare value: str) and re-check:")
    print("=" * 70)

    class BadAssignment(BaseModel):
        name: str
        value: str  # grammar yields int here -> mismatch

    bad = seq(
        field("name", identifier),
        skip("="),
        field("value", integer),
    ).produce(BadAssignment)
    bad_grammar = Grammar(rules={"a": bad}, entry="a",
                          models=[BadAssignment])
    for e in bad_grammar.validate_bridge():
        print("  -", e)


if __name__ == "__main__":
    main()
