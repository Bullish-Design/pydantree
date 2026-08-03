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
    ReservedNode,
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
    hidden child ("hidden"). `tok` records the token source for anonymous
    kinds ("str" | "pattern" | None) — the CLI emits STRING-based anonymous
    kinds but never PATTERN-based ones (probed Phase 6)."""

    __slots__ = ("kind", "name", "named", "field", "quant", "tok")

    def __init__(self, kind: str, name: str, named: bool,
                 field: str | None, quant: _Quantity, tok: str | None = None):
        self.kind = kind
        self.name = name
        self.named = named
        self.field = field
        self.quant = quant
        self.tok = tok


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
        """The CLI's variable_is_used port: a rule survives iff it is the
        start rule, referenced by an extra/external, or referenced by another
        surviving rule. Phase 6: the exact port (previously a seeds+walk
        approximation that never actually pruned)."""
        return {name for name in self.rules
                if _variable_is_used(self.rules, self.grammar.extras,
                                     self.grammar.externals, name, set())}

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
        # Phase-6.5 calibration (probed against the CLI over the markdown
        # block grammar): a HIDDEN rule whose body is NOT a bare top-level
        # REPEAT1 gets its repeats treated as 0+ (required false) — the CLI
        # wraps such repeats in an auxiliary binary-tree rule whose
        # children_without_fields quantity is optional, whereas a bare
        # top-level REPEAT1 body becomes the recursion ITSELF (required).
        self._relax_hidden_repeat = name.startswith("_") and \
            not isinstance(body, Repeat1Node) and \
            _contains_repeat(body)
        new_state = self._summarize(body)
        fields, field_types, children_q, children_types, wo_q, wo_types, \
            multi_step = new_state
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

    def _summarize(self, body: RuleNode):
        """Accumulate a body's production summary (the _recompute core, over
        an ARBITRARY body — rules AND alias contents like markdown's
        alias(REPEAT1(choice(_line, ...)), "inline")).

        The CLI seeds every accumulator at ChildQuantity::one() (FieldInfo
        default) and only unions production quantities in — required flips
        OFF when a production lacks the field/child, but never flips on."""
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
                    if step.field is not None:
                        # a field step over a hidden child: the field exists
                        # and its possible types are the hidden child's
                        # children (node_types.rs: field_info.types += the
                        # hidden variable's children.types)
                        pf[step.field].append(
                            child.children_q.scaled_by(step.quant))
                        pft[step.field].update(child.children_types)
                    elif child.wo_types:
                        wq = child.wo_q.scaled_by(step.quant)
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

        return (fields, dict(field_types), children_q, children_types,
                wo_q, wo_types, multi_step)

    def _productions(self, node: RuleNode, guard: set[str]) -> list[list[_Step]]:
        """Expand a body into productions (step lists). Choice forks; SEQ
        concats; inline rules expand; hidden rules become inherit-steps;
        repeats mark quantity; aliases contribute their kind as a child."""
        node = _unwrap_prec(node)
        if isinstance(node, (TokenNode, ImmediateTokenNode)):
            # a token wrapper: a single-STRING content is an anonymous string
            # terminal (anon-eligible); anything else is fused (no anon kind)
            c = _unwrap_prec(node.content)
            if isinstance(c, StrNode):
                return [[_Step("kind", c.value, False, None, _Quantity.one(),
                               tok="str")]]
            if isinstance(c, PatternNode):
                return [[_Step("kind", c.value, False, None, _Quantity.one(),
                               tok="pattern")]]
            return [[]]  # fused multi-part token — no visible child steps
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
            if name in self.supertypes:
                # supertype symbols are never hidden (node_types.rs's
                # variable_type_for_child_type exemption): a visible kind step
                return [[_Step("kind", name, True, None, _Quantity.one())]]
            if name in self.inline:
                if name in guard:
                    return [[]]  # recursive inline — conservative
                body = self.rules.get(name)
                if body is None:
                    return [[]]
                return self._productions(body, guard | {name})
            if name in self.hidden:
                # a hidden (non-inline) ref is an INHERIT step: the fixed
                # point merges the hidden rule's own children/fields, scaled
                # by this step's quantity (node_types.rs's production
                # analysis — recursive hidden rules like rust's _let_chain
                # converge through this, giving multiple=true)
                return [[_Step("hidden", name, True, None, _Quantity.one())]]
            if name.startswith("_") and ref_body is None:
                # a hidden EXTERNAL (e.g. rust's `_block_comment_content`):
                # hidden in node_types.rs (external kind), so an inherit step
                # whose (empty) summary contributes nothing
                return [[_Step("hidden", name, True, None, _Quantity.one())]]
            return [[_Step("kind", name, True, None, _Quantity.one())]]
        if isinstance(node, StrNode):
            return [[_Step("kind", node.value, False, None, _Quantity.one(),
                           tok="str")]]
        if isinstance(node, PatternNode):
            # pattern tokens never become anonymous kinds in node-types.json
            # (the CLI's lexical grammar does not carry them) — still a step
            # for quantity purposes, tagged so the anon pass skips it
            return [[_Step("kind", node.value, False, None, _Quantity.one(),
                           tok="pattern")]]
        if isinstance(node, AliasNode):
            content = _unwrap_prec(node.content)
            if isinstance(content, SymbolNode):
                # an explicit alias of a rule reference: the alias VALUE is
                # the child kind (anonymous aliases of non-terminals —
                # python's `is not` — stay opaque: the rule loop emits them)
                return [[_Step("kind", node.value, node.named, None,
                               _Quantity.one())]]
            # an alias wrapping STRUCTURED content (markdown's
            # alias(REPEAT(...), "section")): the alias is ONE child kind
            # carrying the content's QUANTITY — the members do NOT expand
            # (the CLI's production analysis sees the repeat inside the
            # alias content as the step's quantity)
            quant = _Quantity.one()
            c = content
            while isinstance(c, _PREC_NODES):
                c = c.content
            if isinstance(c, (RepeatNode, Repeat1Node)):
                quant = _Quantity.one().repeat_quantity(
                    plus=isinstance(c, Repeat1Node))
            return [[_Step("kind", node.value, node.named, None, quant,
                           tok="str" if not node.named else None)]]
        if isinstance(node, FieldNode):
            return [[_Step(s.kind, s.name, s.named, node.name, s.quant,
                           s.tok)
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
            plus = isinstance(node, Repeat1Node) and \
                not getattr(self, "_relax_hidden_repeat", False)
            q = _Quantity.one().repeat_quantity(plus=plus)
            return [[_Step(s.kind, s.name, s.named, s.field,
                           s.quant.scaled_by(q), s.tok)
                     for s in st] for st in self._productions(node.content, guard)]
        return [[]]


_PREC_NODES = (PrecNode, PrecLeftNode, PrecRightNode, PrecDynamicNode)


def _unwrap_prec(node: RuleNode) -> RuleNode:
    """Unwrap precedence wrappers only (not TOKEN/IMMEDIATE_TOKEN — those are
    the is_token path and must be seen by _productions)."""
    while isinstance(node, _PREC_NODES):
        node = node.content
    return node


def _rule_token_outcome(body: RuleNode) -> tuple[str | None, bool]:
    """The CLI's extract_tokens rule-level outcome (extract_tokens.rs):
    (terminal_kind, fully_extracted).

    * "anon" — the rule's token is a single STRING (bare, or wrapped in
      TOKEN/IMMEDIATE_TOKEN): an ANONYMOUS terminal named after the string.
    * "aux" — a PATTERN or multi-part TOKEN: an AUXILIARY terminal
      (`{rule}_token{N}`), never emitted in node-types.
    * fully_extracted — the rule's body became a bare Symbol(terminal): the
      condition for the "give the rule its name to the token" rename. A
      PREC-wrapped string stays in the syntax grammar (body becomes
      Metadata(PREC, Symbol)), so it is NOT fully extracted — e.g. python's
      `break_statement: PREC_LEFT(0, 'break')` keeps a rule-loop entry
      (fields:{}) AND the anonymous `break` kind.
    """
    if isinstance(body, (TokenNode, ImmediateTokenNode)):
        c = _unwrap_prec(body.content)
        if isinstance(c, StrNode):
            return "anon", True
        return "aux", True
    node = body
    wrapped = False
    while isinstance(node, _PREC_NODES):
        wrapped = True
        node = node.content
    if isinstance(node, StrNode):
        return "anon", not wrapped
    if isinstance(node, PatternNode):
        return "aux", not wrapped
    if isinstance(node, (TokenNode, ImmediateTokenNode)):
        inner = _unwrap_prec(node.content)
        return ("anon" if isinstance(inner, StrNode) else "aux"), False
    return None, False


def _string_usage(d: "_Deriver", reachable: set) -> dict:
    """Bare-STRING terminal usage counts (the CLI's extracted_usage_counts):
    how many rule bodies / extras / externals reference each anonymous string
    terminal. A bare-string rule is only renamed to a named terminal when its
    string is used exactly once."""
    counts: dict = defaultdict(int)

    def walk(node: RuleNode) -> None:
        node = _unwrap_prec(node)
        if isinstance(node, StrNode):
            counts[node.value] += 1
            return
        if isinstance(node, (TokenNode, ImmediateTokenNode)):
            return  # TOKEN-wrapped strings are DIFFERENT terminals
        if isinstance(node, AliasNode):
            walk(node.content)
            return
        c = getattr(node, "content", None)
        if isinstance(c, RuleNode):
            walk(c)
        m = getattr(node, "members", None)
        if isinstance(m, list):
            for mm in m:
                walk(mm)

    for name in reachable:
        walk(d.rules[name])
    for ex in list(d.grammar.extras) + list(d.grammar.externals):
        walk(ex)
    return counts


def _rule_is_renamed(name: str, body: RuleNode, i: int,
                     usage: dict) -> bool:
    """Would the CLI rename this rule's extracted token to the rule name
    (removing the rule from the syntax grammar)? The aux case always renames
    (when fully extracted) — but a HIDDEN rule's renamed terminal stays
    Hidden (the CLI's node-types terminal loop skips it), so it produces NO
    entry either way. The anon-string case renames only a visible non-start
    rule whose string appears exactly once."""
    kind, full = _rule_token_outcome(body)
    if not full:
        return False
    if kind == "aux":
        return i > 0 and not name.startswith("_")
    if kind == "anon":
        value = _unwrap_prec(body).value if isinstance(
            _unwrap_prec(body), StrNode) else None
        if value is None:
            c = _unwrap_prec(body.content) if isinstance(
                body, (TokenNode, ImmediateTokenNode)) else None
            value = getattr(c, "value", None)
        return i > 0 and not name.startswith("_") and usage.get(value) == 1
    return False


def _contains_repeat(node: RuleNode) -> bool:
    """Does the body contain a REPEAT/REPEAT1 anywhere?"""
    node = _unwrap_prec(node)
    if isinstance(node, (RepeatNode, Repeat1Node)):
        return True
    if isinstance(node, AliasNode):
        return _contains_repeat(node.content)
    c = getattr(node, "content", None)
    if isinstance(c, RuleNode) and _contains_repeat(c):
        return True
    m = getattr(node, "members", None)
    if isinstance(m, list) and any(_contains_repeat(mm) for mm in m):
        return True
    return False


def _is_lexical_rule(body: RuleNode) -> bool:
    """A rule whose body is a TOKEN/IMMEDIATE_TOKEN or a bare
    STRING/PATTERN is a lexical variable in the CLI — it gets `{type,
    named}` and no fields/children (its content fuses into the lexer).
    Phase 6: kept for the legacy check; the token-extraction model is
    `_rule_token_outcome` + `_rule_is_renamed`."""
    if isinstance(body, (TokenNode, ImmediateTokenNode)):
        return True
    body = _unwrap(body)
    return isinstance(body, (StrNode, PatternNode))


# --------------------------------------------------------------------------
# the CLI's pruning + aliasing, ported (parse_grammar.rs, node_types.rs)
# --------------------------------------------------------------------------

# the rule-level wrappers the CLI's rule_is_referenced treats as "Metadata"
# (recursed with the SAME is_external flag): precedence, token wrappers, FIELD
# and ALIAS
_METADATA_WRAPPERS = (PrecNode, PrecLeftNode, PrecRightNode, PrecDynamicNode,
                      TokenNode, ImmediateTokenNode, FieldNode, AliasNode,
                      ReservedNode)


def _rule_is_referenced(node: RuleNode, target: str, is_external: bool) -> bool:
    """Port of parse_grammar.rs's `rule_is_referenced`. `is_external` is set
    only while scanning an external token's body; NamedSymbol references do
    not count there (external bodies are token-level)."""
    if isinstance(node, SymbolNode):
        return node.name == target and not is_external
    if isinstance(node, (ChoiceNode, SeqNode)):
        return any(_rule_is_referenced(m, target, False) for m in node.members)
    if isinstance(node, _METADATA_WRAPPERS):
        return _rule_is_referenced(node.content, target, is_external)
    if isinstance(node, (RepeatNode, Repeat1Node)):
        return _rule_is_referenced(node.content, target, False)
    return False  # BLANK / STRING / PATTERN


def _variable_is_used(grammar_rules: dict, extras: list, externals: list,
                      target: str, in_progress: set) -> bool:
    """Port of parse_grammar.rs's `variable_is_used`: a rule is used iff it
    is the start rule, referenced by an extra or external rule (with the
    CLI's follow-alias semantics), or referenced by another used rule.
    This is the CLI's silent pruning — a rule that is unreachable here gets
    NO node-types entry."""
    root = next(iter(grammar_rules))
    if target == root:
        return True
    if any(_rule_is_referenced(ex, target, False) for ex in extras):
        return True
    if any(_rule_is_referenced(ex, target, True) for ex in externals):
        return True
    in_progress.add(target)
    result = False
    for name, rule in grammar_rules.items():
        if name == target or name in in_progress:
            continue
        if _rule_is_referenced(rule, target, False) and \
                _variable_is_used(grammar_rules, extras, externals, name,
                                  in_progress):
            result = True
            break
    in_progress.discard(target)
    return result


def _step_aliases(node: RuleNode, rules: dict, d: "_Deriver"):
    """Yield (symbol_name, explicit_alias | None) for every symbol step in
    `node`, resolving references to inline/hidden alias rules to their
    content symbol — the CLI's post-inline step (an `_foo` rule whose body is
    `alias($.bar, $.baz)` becomes a step on `bar` with alias `baz`)."""
    node = _unwrap(node)
    if isinstance(node, SymbolNode):
        ref = rules.get(node.name)
        if isinstance(ref, AliasNode) and \
                (node.name in d.inline or node.name in d.hidden):
            inner = _unwrap(ref.content)
            if isinstance(inner, SymbolNode):
                yield (inner.name, (ref.value, ref.named))
            else:
                yield (None, None)  # lexical content — anonymous token
        else:
            yield (node.name, None)
        return
    if isinstance(node, AliasNode):
        content = _unwrap_prec(node.content)
        if isinstance(content, SymbolNode):
            # an alias over a single symbol reference: the alias applies to
            # that symbol (resolving inline/hidden alias-rule refs first)
            for sym, _a in _step_aliases(content, rules, d):
                if sym is not None:
                    yield (sym, (node.value, node.named))
        # else: an alias over STRUCTURED content (markdown's
        # alias(REPEAT1(choice(...)), "inline")) — the alias wraps a
        # synthetic content symbol, NOT the inner symbols; the
        # structured_aliases machinery gives the value its own entry
        return
    if isinstance(node, FieldNode):
        yield from _step_aliases(node.content, rules, d)
        return
    if isinstance(node, (ChoiceNode, SeqNode)):
        for m in node.members:
            yield from _step_aliases(m, rules, d)
        return
    if isinstance(node, (RepeatNode, Repeat1Node)):
        yield from _step_aliases(node.content, rules, d)
        return


def _aliases_by_symbol(d: "_Deriver", reachable: set):
    """Port of node_types.rs's `get_aliases_by_symbol`: every symbol's set of
    (alias_value, named) | None — from default aliases (non-inline rules
    whose body is an alias), the extras (their own name when not
    default-aliased), every production step's alias-or-default-alias, and the
    start rule. This is what makes merged aliases (several rules under one
    visible kind) and alias-derived kinds (type_identifier etc.) come out
    right. Also returns `bare_aliases`: named alias values whose content is
    lexical (no symbol steps — e.g. rust's `primitive_type`), which the CLI
    emits as bare named entries of their own; and `structured_aliases`:
    named alias values over structured content WITH symbols (markdown's
    `inline` over REPEAT1(choice(...))) — the entry inherits the content's
    summary."""
    rules = d.rules
    aliases: dict = defaultdict(set)
    bare_aliases: set = set()
    structured_aliases: list = []
    for name, body in rules.items():
        if name in d.inline:
            continue
        if isinstance(body, AliasNode):
            aliases[name].add((body.value, body.named))
    default_aliased = {n for n, b in rules.items()
                       if n not in d.inline and isinstance(b, AliasNode)}
    for ex in d.grammar.extras:
        ex = _unwrap(ex)
        if isinstance(ex, SymbolNode) and ex.name not in default_aliased:
            aliases[ex.name].add(None)
        elif isinstance(ex, AliasNode):
            aliases[ex.value].add(None)
    for name in reachable:
        if name not in rules:
            continue
        body = rules[name]
        if isinstance(body, AliasNode):
            body = body.content
        steps = list(_step_aliases(body, rules, d))
        # named aliases over non-symbol content (bare or structured) become
        # entries of their own
        for a in _alias_values(body):
            if a is None:
                continue
            value, named, content = a
            if content is None:
                bare_aliases.add((value, named))
            else:
                structured_aliases.append((value, named, content))
        for sym, explicit in steps:
            if sym is None:
                continue
            if explicit is not None:
                aliases[sym].add(explicit)
                continue
            ref = rules.get(sym)
            if isinstance(ref, AliasNode) and sym not in d.inline:
                aliases[sym].add((ref.value, ref.named))
            else:
                aliases[sym].add(None)
    aliases[d.start].add(None)
    return aliases, bare_aliases, structured_aliases


def _alias_values(node: RuleNode):
    """Alias values whose content is NOT a plain rule reference: yields
    (value, named, content_or_None) — content=None for a lexical body (a
    bare entry — rust's `primitive_type`), content=the body for structured
    content WITH symbols (markdown's alias(REPEAT1(choice(_line, ...)),
    "inline") — the entry inherits the content's summary)."""
    node = _unwrap(node)
    if isinstance(node, AliasNode):
        if isinstance(_unwrap_prec(node.content), SymbolNode):
            return  # a plain rule reference — handled by aliases_by_symbol
        if not _has_symbol(node.content):
            yield (node.value, node.named, None)
        else:
            yield (node.value, node.named, node.content)
        return
    c = getattr(node, "content", None)
    if isinstance(c, RuleNode):
        yield from _alias_values(c)
    m = getattr(node, "members", None)
    if isinstance(m, list):
        for mm in m:
            yield from _alias_values(mm)


def _has_symbol(node: RuleNode) -> bool:
    node = _unwrap_prec(node)
    if isinstance(node, SymbolNode):
        return True
    if isinstance(node, AliasNode):
        return _has_symbol(node.content)
    c = getattr(node, "content", None)
    if isinstance(c, RuleNode) and _has_symbol(c):
        return True
    m = getattr(node, "members", None)
    if isinstance(m, list) and any(_has_symbol(mm) for mm in m):
        return True
    return False


def _sorted_types(types: set) -> list[NodeTypeRef]:
    return [NodeTypeRef(type=k, named=n) for k, n in sorted(types)]


# --------------------------------------------------------------------------
# derive_from_ir — the exact path (mirrors node_types.rs's entry emission)
# --------------------------------------------------------------------------


def derive_from_ir(grammar: GrammarModel) -> list[NodeTypeInfo]:
    """The exact path: walk the grammar IR -> the canonical node-schema list.

    Phase 6: ported to mirror node_types.rs's emission exactly — reachability
    (the CLI's variable_is_used pruning), the aliases-by-symbol mapping
    (merged aliases, alias-derived kinds), the supertype subtypes, the
    STRING-only anonymous kinds, and the emission shape (no `fields: {}` on
    lexical/bare entries, `root`/`extra` only when true). Verified
    byte-for-byte against the CLI's node-types.json over the real
    tree-sitter-rust grammar (a grammar we don't own)."""
    d = _Deriver(grammar)
    reachable = d._reachable()
    d.compute()
    string_usage = _string_usage(d, reachable)
    aliases, bare_aliases, structured_aliases = _aliases_by_symbol(d, reachable)

    node_types: dict[tuple, NodeTypeInfo] = {}  # keyed by (kind, named) — a
    # named kind and an anonymous kind can share a name (rust's `block` rule
    # AND the `block` metavariable string both appear in the CLI output)
    supertype_map: list[tuple[str, list[NodeTypeRef]]] = []

    # ---- the rule loop (non-terminal variables) -------------------------
    for i, (name, body) in enumerate(grammar.rules.items()):
        if name not in reachable:
            continue
        if name in d.supertypes:
            # supertypes are emitted even when inline (the CLI checks the
            # supertype list before variables_to_inline)
            subs = _sorted_types(d.info[name].children_types)
            entry = node_types.setdefault(
                (name, True), NodeTypeInfo(type=name, named=True))
            entry.subtypes = subs
            supertype_map.append((name, subs))
            continue
        if name in d.inline:
            continue
        if _rule_is_renamed(name, body, i, string_usage):
            continue  # a renamed named terminal -> the terminal loop below
        info = d.info[name]
        is_start = (i == 0)
        for alias in aliases.get(name) or {None}:
            if alias is None:
                if name.startswith("_"):
                    continue  # hidden rule: no own-name entry (aliases only)
                kind, is_named = name, True
            else:
                # an anonymous alias of a rule still gets an entry (the CLI
                # emits `{type, named: false, fields: {}}` — python's
                # `is not` over the hidden `_is_not`)
                kind, is_named = alias
            existed = (kind, is_named) in node_types
            entry = node_types.setdefault(
                (kind, is_named),
                NodeTypeInfo(type=kind, named=is_named,
                             root=is_start, fields={}))
            # merged-alias field semantics (node_types.rs): new fields on an
            # existing entry start required=false; fields absent from THIS
            # rule flip required off; quantities union.
            for fname, fq in sorted(info.fields.items()):
                ftypes = info.field_types.get(fname)
                if not ftypes:
                    continue
                fj = entry.fields.setdefault(
                    fname, ChildInfo(multiple=False, required=not existed))
                fj.multiple = fj.multiple or fq.multiple
                fj.required = fj.required and fq.required
                fj.types = [NodeTypeRef(type=k, named=n)
                            for k, n in sorted(
                                {(r.type, r.named) for r in fj.types}
                                | {(k, n) for k, n in ftypes})]
            for fname in list(entry.fields):
                if fname not in info.fields:
                    entry.fields[fname].required = False
            if info.wo_q.exists and info.wo_types:
                ch = entry.children
                if ch is None:
                    ch = ChildInfo(multiple=False, required=True)
                ch.multiple = ch.multiple or info.wo_q.multiple
                ch.required = ch.required and info.wo_q.required
                ch.types = [NodeTypeRef(type=k, named=n)
                            for k, n in sorted(
                                {(r.type, r.named) for r in ch.types}
                                | {(k, n) for k, n in info.wo_types})]
                entry.children = ch

    # ---- terminal + external loop (renamed terminals, bare entries) ----
    for i, (name, body) in enumerate(grammar.rules.items()):
        if name not in reachable or name in d.inline:
            continue
        if not _rule_is_renamed(name, body, i, string_usage):
            continue
        for alias in aliases.get(name) or {None}:
            if alias is None:
                kind, is_named = name, True
            else:
                kind, is_named = alias
                if not is_named:
                    continue
            entry = node_types.setdefault(
                (kind, True), NodeTypeInfo(type=kind, named=True,
                                           extra=name in d._extra_names))
            # an existing entry (a rule with fields/children) is relaxed
            if entry.children is not None:
                entry.children.required = False
            if entry.fields is not None:
                for fi in entry.fields.values():
                    fi.required = False
    for ex in d.grammar.externals:
        ex = _unwrap(ex)
        if not isinstance(ex, SymbolNode):
            continue
        for alias in aliases.get(ex.name) or {None}:
            if alias is None:
                kind, is_named = ex.name, not ex.name.startswith("_")
            else:
                kind, is_named = alias
            if not is_named:
                continue
            entry = node_types.setdefault(
                (kind, True), NodeTypeInfo(type=kind, named=True,
                                           extra=kind in d._extra_names))
            if entry.children is not None:
                entry.children.required = False
            if entry.fields is not None:
                for fi in entry.fields.values():
                    fi.required = False

    # ---- anonymous kinds: STRING tokens only (never PATTERNs) -----------
    for kind in sorted(_anonymous_kinds(d, reachable, string_usage)):
        if (kind, False) not in node_types:
            node_types[(kind, False)] = NodeTypeInfo(type=kind, named=False)

    # ---- bare alias entries whose content is lexical ---------------------
    # (e.g. rust's alias(choice("f64", "bool", ...), "primitive_type")) —
    # the CLI names the fused terminal's alias value; no rule/terminal owns it
    for kind, is_named in sorted(bare_aliases):
        if is_named and (kind, True) not in node_types:
            node_types[(kind, True)] = NodeTypeInfo(type=kind, named=True)

    # ---- structured-content alias entries --------------------------------
    # (markdown's alias(REPEAT1(choice(_line, ...)), "inline")) — the entry
    # inherits the content's SUMMARY (fields/children), MERGED with any
    # existing entry of the same kind (the CLI merges all aliases of a kind:
    # `_line`'s heading alias AND the paragraph's content alias both map to
    # `inline` — the paragraph's children win, the merged-alias rules apply)
    for kind, is_named, content in sorted(structured_aliases,
                                          key=lambda a: a[0]):
        if not is_named:
            continue
        existed = (kind, True) in node_types
        entry = node_types.setdefault(
            (kind, True), NodeTypeInfo(type=kind, named=True, fields={}))
        fields, ftypes, _cq, _ctypes, woq, wotypes, _ms = d._summarize(content)
        for fname in sorted(fields):
            ft = ftypes.get(fname)
            if not ft:
                continue
            fj = entry.fields.setdefault(
                fname, ChildInfo(multiple=False, required=not existed))
            fj.multiple = fj.multiple or fields[fname].multiple
            fj.required = fj.required and fields[fname].required
            fj.types = [NodeTypeRef(type=k, named=n)
                        for k, n in sorted(
                            {(r.type, r.named) for r in fj.types}
                            | {(k, n) for k, n in ft})]
        if woq.exists and wotypes:
            ch = entry.children
            if ch is None:
                ch = ChildInfo(multiple=False, required=True)
            ch.multiple = ch.multiple or woq.multiple
            ch.required = ch.required and woq.required
            ch.types = [NodeTypeRef(type=k, named=n)
                        for k, n in sorted(
                            {(r.type, r.named) for r in ch.types}
                            | {(k, n) for k, n in wotypes})]
            entry.children = ch

    # ---- process_supertypes: subtypes are replaced by their supertype ----
    supertype_map.sort(key=lambda pair: pair[0])
    for entry in node_types.values():
        if entry.fields is not None:
            for fname, fi in list(entry.fields.items()):
                entry.fields[fname] = _process_supertypes(fi, supertype_map)
        if entry.children is not None:
            entry.children = _process_supertypes(entry.children, supertype_map)

    return _canonical_sorted(list(node_types.values()))


def _anonymous_kinds(d: "_Deriver", reachable: set, string_usage: dict) -> set[str]:
    """All anonymous STRING token kinds reachable from the grammar's rules.
    Pattern tokens never appear in node-types.json (probed Phase 6 — inline
    patterns and even token()-wrapped anonymous patterns are absent from the
    CLI's lexical grammar); anonymous extras do not appear either. A renamed
    terminal's string is consumed by the rename and is not anonymous."""
    out: set[str] = set()
    for i, (name, body) in enumerate(d.rules.items()):
        if name not in reachable:
            continue
        if isinstance(body, AliasNode):
            body = body.content
        if _rule_is_renamed(name, body, i, string_usage):
            continue
        for steps in d._productions(body, set()):
            for step in steps:
                if step.kind == "kind" and not step.named \
                        and step.tok == "str":
                    out.add(step.name)
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
