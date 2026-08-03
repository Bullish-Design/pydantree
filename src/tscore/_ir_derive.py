"""tscore._ir_derive — the exact-path node-schema derivation (derive_from_ir).

Kept OUT of tscore.schema's import graph: it imports tsgrammar.grammar (B's
IR), so it is only importable when B is present. tscore.schema exposes
`derive_from_ir` as a lazy function that imports this module on first call —
A (tsquery consumers, the B-free bundle path) imports tscore.schema without
ever touching tsgrammar; the exact-path derivation is B-side machinery.

The derivation mirrors node_types.rs (see tscore.schema's module docstring).
"""

from __future__ import annotations

from collections import defaultdict

# --------------------------------------------------------------------------
# derivation path 1 — the exact path (walk the grammar IR)
# --------------------------------------------------------------------------

from tsgrammar.grammar import (  # noqa: E402  (this module is B-side only)
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

from .schema import ChildInfo, NodeTypeInfo, NodeTypeRef  # noqa: E402
from .schema import _canonical_sorted  # noqa: E402

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
