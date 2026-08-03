"""tscore.schema — the grammar node-schema (the Phase-4 bridge artifact).

This is the shared seam between tsgrammar (B) and tsquery (A): a closed set
of node kinds, each kind's possible fields and child types, and supertype
relationships — the second half of the artifact B emits, and what makes A's
extraction *checked*.

The per-type shape mirrors `node-types.json` exactly (the CLI's byproduct —
`cli/generate/src/node_types.rs`):

    {"type": str, "named": bool,
     "root": bool,              # start rule
     "extra": bool,             # appears in grammar extras
     "fields": {name: {multiple, required, types: [{type, named}]}},
     "children": {multiple, required, types: [...]} | null,
     "subtypes": [{type, named}] | null}    # on supertype nodes

The canonical serialization is the CLI's list form, so a B-built
`node-schema.json` is byte-compatible with a community grammar's
`node-types.json`, and A cannot tell which path produced it.

TWO derivation paths converge on that format:

  * `derive_from_ir(GrammarModel)` — the EXACT path: walks the grammar IR's
    rules, FieldNodes, AliasNodes (aliased names), hidden `_`-rules,
    `inline` list, `supertypes` list, `start_rule`. Richer than the CLI
    byproduct (which is post-alias/post-inline flattened): the `tuple` alias
    and hidden `_*` rules only exist here. The derivation mirrors
    node_types.rs's algorithm (per-production quantity bookkeeping,
    fixed-point over recursive rules, hidden-child inheritance, supertype
    subtypes) so it AGREES with the CLI on the shared subset.
  * `derive_from_node_types(node_types_json)` — the weaker community path:
    samples the CLI byproduct directly (supertypes arrive as `subtypes`
    entries; aliases/inline are already flattened away).

Derivation semantics ported from node_types.rs (verified against the CLI's
byproduct in tests/test_schema.py):

  * grammar.json REPEAT (0+) is choice(REPEAT1, BLANK) — its content's
    quantities are (exists, not-required, multiple); REPEAT1 is (exists,
    required, multiple).
  * hidden `_`-rules and inline rules are transparent: their visible
    children/fields inherit into the referencing rule; hidden children's
    quantities are scaled by the referencing step's repeat quantity.
  * a rule whose top-level body is ALIAS registers the alias VALUE as the
    visible kind (the canonical `_tuple: alias("tuple", True, ref(...))`
    pattern); an ALIAS at a step position contributes the alias kind as a
    plain child type.
  * supertype `subtypes` = the supertype rule's visible child types; in
    field/children lists the CLI REPLACES subtypes with their supertype
    (process_supertypes) — replicated here.
  * unused rules are pruned (the CLI silently prunes unreachable rules).

Known simplifications (documented, §11 risk-7 evidence): (a) multiple rules
aliased under one name merge their fields' `required` flags in the CLI — we
union quantities instead, so `required` can be overstated for merged aliases;
(b) anonymous pattern tokens are named by their pattern source text.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# models — mirror node-types.json's per-type shape
# --------------------------------------------------------------------------


class NodeTypeRef(BaseModel):
    """A reference to a node type (in a field/children/subtypes list)."""

    type: str
    named: bool = True


class ChildInfo(BaseModel):
    """Field or children info: quantity + possible types."""

    multiple: bool = False
    required: bool = True
    types: list[NodeTypeRef] = Field(default_factory=list)


class NodeTypeInfo(BaseModel):
    """One node kind's schema entry (mirrors NodeInfoJSON)."""

    type: str
    named: bool = True
    root: bool = False
    extra: bool = False
    fields: dict[str, ChildInfo] = Field(default_factory=dict)
    children: ChildInfo | None = None
    subtypes: list[NodeTypeRef] | None = None


def _canonical_sorted(types: list[NodeTypeInfo]) -> list[NodeTypeInfo]:
    """The CLI's node_types.rs sort: supertypes first, then non-leaves, then
    leaves, alphabetical within each group."""
    def key(t: NodeTypeInfo):
        has_subtypes = t.subtypes is not None
        is_leaf = t.children is None and not t.fields
        return (0 if has_subtypes else 1, 0 if not is_leaf else 1, t.type)
    return sorted(types, key=key)


# --------------------------------------------------------------------------
# the in-memory schema (A-side query helpers)
# --------------------------------------------------------------------------


class NodeSchema(BaseModel):
    """The node-schema in memory, with the query helpers A's checks use.

    `node_types` is the canonical list. `name` is optional provenance
    (grammar name when known).
    """

    name: str | None = None
    node_types: list[NodeTypeInfo] = Field(default_factory=list)

    # -- construction -------------------------------------------------------

    @classmethod
    def from_list(cls, types: Iterable[Any], *, name: str | None = None) -> "NodeSchema":
        return cls(name=name, node_types=[NodeTypeInfo.model_validate(t) for t in types])

    @classmethod
    def from_node_types_json(cls, path: str | Path, *, name: str | None = None) -> "NodeSchema":
        data = json.loads(Path(path).read_text())
        if isinstance(data, dict) and "node_types" in data:  # our serialized form
            return cls.model_validate(data)
        return cls.from_list(data, name=name)

    # -- canonical serialization --------------------------------------------

    def to_list(self) -> list[NodeTypeInfo]:
        """The canonical list (byte-compatible with node-types.json)."""
        return _canonical_sorted([t.model_copy(deep=True) for t in self.node_types])

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            [t.model_dump(exclude_none=True) for t in self.to_list()],
            indent=indent)

    def write(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_text(self.to_json())
        return path

    # -- lookups ------------------------------------------------------------

    def by_type(self) -> dict[str, NodeTypeInfo]:
        return {t.type: t for t in self.node_types}

    def kinds(self) -> set[str]:
        return {t.type for t in self.node_types}

    def named_kinds(self) -> set[str]:
        return {t.type for t in self.node_types if t.named}

    def get(self, kind: str) -> NodeTypeInfo | None:
        return self.by_type().get(kind)

    def field_types(self, kind: str, field: str) -> list[NodeTypeRef]:
        """The possible node types of `field` on `kind` ([] if unknown)."""
        t = self.get(kind)
        if t is None:
            return []
        info = t.fields.get(field)
        return list(info.types) if info is not None else []

    def children_types(self, kind: str) -> list[NodeTypeRef]:
        """The named children kinds of `kind` ([] if unknown/leaf)."""
        t = self.get(kind)
        if t is None or t.children is None:
            return []
        return list(t.children.types)

    def has_field(self, kind: str, field: str) -> bool:
        t = self.get(kind)
        return t is not None and field in t.fields

    def supertype_subtypes(self, kind: str) -> list[str]:
        t = self.get(kind)
        if t is None or t.subtypes is None:
            return []
        return [r.type for r in t.subtypes]

    def is_supertype(self, kind: str) -> bool:
        t = self.get(kind)
        return t is not None and t.subtypes is not None

    def expand(self, refs: Iterable[str]) -> set[str]:
        """Expand a set of kind names by replacing supertypes with their
        subtypes (the CLI's process_supertypes inverse)."""
        out: set[str] = set()
        for k in refs:
            subs = self.supertype_subtypes(k)
            if subs:
                out.update(subs)
            else:
                out.add(k)
        return out

    # -- structure queries used by A's checks -------------------------------

    def possible_children(self, kind: str) -> set[str]:
        """All kinds that can appear as a child of `kind` (fields' types +
        children types, supertypes expanded)."""
        t = self.get(kind)
        if t is None:
            return set()
        refs = [r.type for f in t.fields.values() for r in f.types]
        refs += [r.type for r in (t.children.types if t.children else [])]
        return self.expand(refs)

    def is_possible_descent(self, parent: str, child: str) -> bool:
        return child in self.possible_children(parent)

    def can_occur(self, kind: str) -> bool:
        """Is `kind` a real, named, producible node kind?"""
        t = self.get(kind)
        return t is not None and t.named

    def __repr__(self) -> str:  # pragma: no cover
        return f"NodeSchema({len(self.node_types)} node types, name={self.name!r})"


# --------------------------------------------------------------------------
# derivation path 2 — the community path (sample the CLI byproduct)
# --------------------------------------------------------------------------


def derive_from_node_types(node_types_json: Any) -> list[NodeTypeInfo]:
    """The weaker community path: `node-types.json` (the CLI's byproduct) ->
    the canonical node-schema list. Aliases/inline are already flattened
    away; supertypes arrive as `subtypes` entries."""
    if isinstance(node_types_json, (str, Path)):
        node_types_json = json.loads(Path(node_types_json).read_text())
    if isinstance(node_types_json, dict) and "node_types" in node_types_json:
        node_types_json = node_types_json["node_types"]
    return [NodeTypeInfo.model_validate(t) for t in node_types_json]


# --------------------------------------------------------------------------
# derivation path 1 — the exact path (walk the grammar IR)
# --------------------------------------------------------------------------

from tsgrammar.grammar import (  # noqa: E402  (lazy import: tscore stays B-free at import time)
    AliasNode,
    BlankNode,
    ChoiceNode,
    FieldNode,
    Grammar as GrammarModel,
    ImmediateTokenNode,
    PatternNode,
    PrecDynamicNode,
    PrecLeftNode,
    PrecNode,
    PrecRightNode,
    Repeat1Node,
    RepeatNode,
    RuleNode,
    SeqNode,
    StrNode,
    SymbolNode,
    TokenNode,
)

_PREC = (PrecNode, PrecLeftNode, PrecRightNode, PrecDynamicNode)
_TRANSPARENT = (*_PREC, TokenNode, ImmediateTokenNode)


def _unwrap(node: RuleNode) -> RuleNode:
    while isinstance(node, _TRANSPARENT):
        node = node.content
    return node


class _Quantity:
    """ChildQuantity port (exists/required/multiple), node_types.rs."""

    __slots__ = ("exists", "required", "multiple")

    def __init__(self, exists: bool, required: bool, multiple: bool):
        self.exists = exists
        self.required = required
        self.multiple = multiple

    @classmethod
    def zero(cls) -> "_Quantity":
        return cls(False, False, False)

    @classmethod
    def one(cls) -> "_Quantity":
        return cls(True, True, False)

    def append(self, other: "_Quantity") -> None:
        if other.exists:
            if self.exists or other.multiple:
                self.multiple = True
            if other.required:
                self.required = True
            self.exists = True

    def union(self, other: "_Quantity") -> bool:
        changed = False
        if not self.exists and other.exists:
            self.exists = True
            changed = True
        if self.required and not other.required:
            self.required = False
            changed = True
        if not self.multiple and other.multiple:
            self.multiple = True
            changed = True
        return changed

    def repeat_quantity(self, *, plus: bool) -> "_Quantity":
        """Content inside grammar.json REPEAT (0+: optional+multiple) or
        REPEAT1 (1+: required+multiple), per the CLI's desugar."""
        return _Quantity(True, plus, True)

    def scaled_by(self, other: "_Quantity") -> "_Quantity":
        """Inherit a hidden child's quantity through a referencing step whose
        own quantity is `other` (repeat-wrapped hidden children)."""
        return _Quantity(self.exists and other.exists,
                         self.required and other.required,
                         self.multiple or other.multiple)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _Quantity):
            return NotImplemented
        return (self.exists, self.required, self.multiple) == \
            (other.exists, other.required, other.multiple)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Q({self.exists},{self.required},{self.multiple})"


class _Step:
    """One step of a production: a visible child ("kind") or an inherited
    hidden child ("hidden")."""

    __slots__ = ("kind", "name", "named", "field", "quant")

    def __init__(self, kind: str, name: str, named: bool,
                 field: str | None, quant: _Quantity):
        self.kind = kind
        self.name = name
        self.named = named
        self.field = field
        self.quant = quant


class _VarInfo:
    """Per-rule summary (VariableInfo port) — the fixed-point state."""

    __slots__ = ("fields", "field_types", "children_q", "children_types",
                 "wo_q", "wo_types", "multi_step", "changed")

    def __init__(self):
        self.fields: dict[str, _Quantity] = {}
        self.field_types: dict[str, set[tuple[str, bool]]] = defaultdict(set)
        self.children_q = _Quantity.zero()
        self.children_types: set[tuple[str, bool]] = set()
        self.wo_q = _Quantity.zero()
        self.wo_types: set[tuple[str, bool]] = set()
        self.multi_step = False
        self.changed = False


class _Deriver:
    def __init__(self, grammar: GrammarModel):
        self.grammar = grammar
        self.rules = grammar.rules
        self.inline = set(grammar.inline)
        self.supertypes = set(grammar.supertypes)
        self.hidden = {n for n in self.rules if n.startswith("_")}
        self.start = grammar.start_rule
        self.word = grammar.word
        self._extra_names: set[str] = set()
        for ex in grammar.extras:
            ex = _unwrap(ex)
            if isinstance(ex, SymbolNode):
                self._extra_names.add(ex.name)
            elif isinstance(ex, AliasNode):
                self._extra_names.add(ex.value)
            elif isinstance(ex, (StrNode, PatternNode)):
                self._extra_names.add(ex.value)
        self._externals = {s.name for s in grammar.externals
                           if isinstance(s, SymbolNode)}
        self.info: dict[str, _VarInfo] = {n: _VarInfo() for n in self.rules}

    # ---- reachability (the CLI silently prunes unreachable rules) --------

    def _reachable(self) -> set[str]:
        seeds = {self.start}
        if self.word:
            seeds.add(self.word)
        seeds |= self._extra_names
        seeds |= self._externals
        seen: set[str] = set()
        stack = [s for s in seeds if s in self.rules]
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            for ref in _symbol_refs(self.rules[name]):
                if ref in self.rules and ref not in seen:
                    stack.append(ref)
        return seen

    # ---- fixed point over all rules --------------------------------------

    def compute(self) -> None:
        reachable = self._reachable()
        while True:
            changed = False
            for name in reachable:
                if self._recompute(name):
                    changed = True
            if not changed:
                break

    def _recompute(self, name: str) -> bool:
        """Recompute a rule's summary from the current hidden-child states.
        Returns True if it changed."""
        info = self.info[name]
        body = self.rules[name]
        if isinstance(body, AliasNode):
            body = body.content

        # The CLI seeds every accumulator at ChildQuantity::one() (FieldInfo
        # default) and only unions production quantities in — required flips
        # OFF when a production lacks the field/child, but never flips on.
        fields: dict[str, _Quantity] = {}
        field_types: dict[str, set[tuple[str, bool]]] = defaultdict(set)
        children_q = _Quantity.one()
        children_types: set[tuple[str, bool]] = set()
        wo_q = _Quantity.one()
        wo_types: set[tuple[str, bool]] = set()
        multi_step = False

        for steps in self._productions(body, set()):
            if len(steps) > 1:
                multi_step = True
            pf: dict[str, _Quantity] = defaultdict(_Quantity.zero)
            pft: dict[str, set[tuple[str, bool]]] = defaultdict(set)
            pc = _Quantity.zero()
            pwo = _Quantity.zero()
            ptypes: set[tuple[str, bool]] = set()
            pwo_types: set[tuple[str, bool]] = set()

            for step in steps:
                if step.kind == "kind":
                    ptypes.add((step.name, step.named))
                    pc.append(step.quant)
                    if step.field is not None:
                        pf[step.field].append(step.quant)
                        pft[step.field].add((step.name, step.named))
                    elif step.named:
                        pwo.append(step.quant)
                        pwo_types.add((step.name, True))
                else:  # hidden child: inherit its children/fields/types
                    child = self.info.get(step.name)
                    if child is None:
                        continue
                    pc.append(child.children_q.scaled_by(step.quant))
                    ptypes.update(child.children_types)
                    for fname, fq in child.fields.items():
                        pf[fname].append(fq.scaled_by(step.quant))
                        pft[fname].update(child.field_types.get(fname, set()))
                    if step.field is None:
                        wq = child.wo_q.scaled_by(step.quant)
                        if child.wo_types:
                            pwo.append(wq)
                            pwo_types.update(child.wo_types)

            # union this production into the rule totals
            for fname, q in pf.items():
                acc = fields.setdefault(fname, _Quantity.one())
                acc.union(q)
                field_types[fname].update(pft[fname])
            # a field absent from this production flips required off
            for fname in list(fields):
                if fname not in pf:
                    fields[fname].union(_Quantity.zero())
            children_q.union(pc)
            children_types.update(ptypes)
            wo_q.union(pwo)
            wo_types.update(pwo_types)

        new_state = (fields, dict(field_types), children_q, children_types,
                     wo_q, wo_types, multi_step)
        old_state = (info.fields, dict(info.field_types), info.children_q,
                     info.children_types, info.wo_q, info.wo_types,
                     info.multi_step)
        info.fields = fields
        info.field_types = field_types
        info.children_q = children_q
        info.children_types = children_types
        info.wo_q = wo_q
        info.wo_types = wo_types
        info.multi_step = multi_step
        info.changed = new_state != old_state
        return info.changed

    def _productions(self, node: RuleNode, guard: set[str]) -> list[list[_Step]]:
        """Expand a body into productions (step lists). Choice forks; SEQ
        concats; hidden/inline symbols become inherit-steps; repeats mark
        quantity; aliases contribute their kind as a child."""
        node = _unwrap(node)
        if isinstance(node, BlankNode):
            return [[]]
        if isinstance(node, SymbolNode):
            name = node.name
            ref_body = self.rules.get(name)
            if isinstance(ref_body, AliasNode):
                # a top-level-alias rule has a DEFAULT alias: every reference
                # sees the alias kind (the CLI's extract_default_aliases)
                return [[_Step("kind", ref_body.value, ref_body.named,
                               None, _Quantity.one())]]
            if name in self.inline or name in self.hidden:
                if name in guard:
                    return [[]]  # recursive hidden/inline — conservative
                body = self.rules.get(name)
                if body is None:
                    return [[]]
                return self._productions(body, guard | {name})
            return [[_Step("kind", name, True, None, _Quantity.one())]]
        if isinstance(node, (StrNode, PatternNode)):
            return [[_Step("kind", node.value, False, None, _Quantity.one())]]
        if isinstance(node, AliasNode):
            return [[_Step("kind", node.value, node.named, None, _Quantity.one())]]
        if isinstance(node, FieldNode):
            return [[_Step(s.kind, s.name, s.named, node.name, s.quant)
                     for s in st] for st in self._productions(node.content, guard)]
        if isinstance(node, SeqNode):
            result: list[list[_Step]] = [[]]
            for m in node.members:
                result = [prefix + suffix
                          for prefix in result
                          for suffix in self._productions(m, guard)]
            return result
        if isinstance(node, ChoiceNode):
            out: list[list[_Step]] = []
            for m in node.members:
                out.extend(self._productions(m, guard))
            return out
        if isinstance(node, (RepeatNode, Repeat1Node)):
            plus = isinstance(node, Repeat1Node)
            q = _Quantity.one().repeat_quantity(plus=plus)
            return [[_Step(s.kind, s.name, s.named, s.field, s.quant.scaled_by(q))
                     for s in st] for st in self._productions(node.content, guard)]
        return [[]]


def _symbol_refs(node: RuleNode) -> list[str]:
    out: list[str] = []
    stack = [node]
    while stack:
        n = _unwrap(stack.pop())
        if isinstance(n, SymbolNode):
            out.append(n.name)
            continue
        if isinstance(n, AliasNode):
            stack.append(n.content)
            continue
        c = getattr(n, "content", None)
        if isinstance(c, RuleNode):
            stack.append(c)
        m = getattr(n, "members", None)
        if isinstance(m, list):
            stack.extend(m)
    return out


def _is_lexical_rule(body: RuleNode) -> bool:
    """A rule whose body is a TOKEN/IMMEDIATE_TOKEN or a bare
    STRING/PATTERN is a lexical variable in the CLI — it gets `{type,
    named}` and no fields/children (its content fuses into the lexer)."""
    if isinstance(body, (TokenNode, ImmediateTokenNode)):
        return True
    body = _unwrap(body)
    return isinstance(body, (StrNode, PatternNode))


def derive_from_ir(grammar: GrammarModel) -> list[NodeTypeInfo]:
    """The exact path: walk the grammar IR -> the canonical node-schema list.

    Mirrors the CLI's node-types.json for the shared subset (verified by the
    agreement check in tests/): field-bearing kinds, supertype `subtypes`,
    children, root/extra markers, and the anonymous-kind list.
    """
    d = _Deriver(grammar)
    d.compute()

    node_types: dict[str, NodeTypeInfo] = {}
    supertype_map: list[tuple[str, list[NodeTypeRef]]] = []

    for i, (name, body) in enumerate(grammar.rules.items()):
        alias_visible = None
        if isinstance(body, AliasNode):
            alias_visible = (body.value, body.named)
        if name in d.inline:
            continue
        if name.startswith("_") and alias_visible is None:
            continue  # plain hidden rule — no node kind of its own
        info = d.info.get(name)
        if info is None:
            continue  # unreachable -> pruned by the CLI

        is_start = (i == 0)
        extra = name in d._extra_names

        # a top-level ALIAS registers the alias value as the visible kind
        if _is_lexical_rule(body):
            # named lexical rules (STRING/PATTERN/TOKEN bodies) are entries
            # with {type, named} and nothing else
            if alias_visible is not None:
                if alias_visible[1]:
                    kind = alias_visible[0]
                    entry = node_types.setdefault(
                        kind, NodeTypeInfo(type=kind, named=True,
                                           root=is_start, extra=extra))
                    entry.root = entry.root or is_start
            else:
                entry = node_types.setdefault(
                    kind := name, NodeTypeInfo(type=kind, named=True,
                                               root=is_start, extra=extra))
                entry.root = entry.root or is_start
            continue

        if alias_visible is not None:
            kind = alias_visible[0]
            if not alias_visible[1]:
                continue
        else:
            kind = name

        entry = node_types.setdefault(
            kind, NodeTypeInfo(type=kind, named=True, root=is_start,
                               extra=extra))
        entry.root = entry.root or is_start
        entry.extra = entry.extra or extra

        fields: dict[str, ChildInfo] = {}
        for fname in sorted(info.fields):
            q = info.fields[fname]
            refs = sorted(info.field_types.get(fname, set()))
            if refs:
                fields[fname] = ChildInfo(
                    multiple=q.multiple, required=q.required,
                    types=[NodeTypeRef(type=k, named=n) for k, n in refs])
        entry.fields.update(fields)

        if info.wo_q.exists and info.wo_types:
            entry.children = ChildInfo(
                multiple=info.wo_q.multiple, required=info.wo_q.required,
                types=[NodeTypeRef(type=k, named=n)
                       for k, n in sorted(info.wo_types)])

        if name in d.supertypes:
            # supertypes get ONLY subtypes in the CLI (no fields/children)
            subs = [NodeTypeRef(type=k, named=n)
                    for k, n in sorted(info.children_types)]
            entry.subtypes = subs
            supertype_map.append((kind, subs))
            if not entry.fields and not entry.children:
                continue
            # a supertype never carries its own fields/children in the JSON
            entry.fields = {}
            entry.children = None
            continue

    # ---- process_supertypes: subtypes are replaced by their supertype ----
    for entry in node_types.values():
        for fname, fi in list(entry.fields.items()):
            entry.fields[fname] = _process_supertypes(fi, supertype_map)
        if entry.children is not None:
            entry.children = _process_supertypes(entry.children, supertype_map)

    # ---- anonymous kinds (lexical tokens) ----
    for kind, named in sorted(_anonymous_kinds(d)):
        if kind not in node_types:
            node_types[kind] = NodeTypeInfo(type=kind, named=False,
                                            extra=kind in d._extra_names)

    return _canonical_sorted(list(node_types.values()))


def _anonymous_kinds(d: _Deriver) -> set[tuple[str, bool]]:
    """All anonymous token kinds reachable from the grammar's rules (the
    CLI's regular_tokens list: every Str/Pattern step's value). Anonymous
    extras (patterns/literals in the `extras` list) do NOT appear in
    node-types.json — only NAMED extras (e.g. a comment rule) do, and those
    are handled as regular entries with extra=true."""
    out: set[tuple[str, bool]] = set()
    for name in d._reachable():
        if name not in d.rules:
            continue
        body = d.rules[name]
        if isinstance(body, AliasNode):
            body = body.content
        if _is_lexical_rule(body):
            continue  # named lexical rule; not anonymous
        for steps in d._productions(body, set()):
            for step in steps:
                if step.kind == "kind" and not step.named:
                    out.add((step.name, False))
    return out


def _process_supertypes(fi: ChildInfo,
                        supertype_map: list[tuple[str, list[NodeTypeRef]]]) -> ChildInfo:
    """The CLI's process_supertypes: when a type list contains a supertype,
    drop its subtypes from the list."""
    types = list(fi.types)
    for kind, subs in supertype_map:
        if any(t.type == kind for t in types):
            sub_kinds = {s.type for s in subs}
            types = [t for t in types if t.type not in sub_kinds]
    seen: set[tuple[str, bool]] = set()
    deduped: list[NodeTypeRef] = []
    for t in sorted(types, key=lambda r: (r.type, r.named)):
        if (t.type, t.named) not in seen:
            seen.add((t.type, t.named))
            deduped.append(t)
    return ChildInfo(multiple=fi.multiple, required=fi.required, types=deduped)
