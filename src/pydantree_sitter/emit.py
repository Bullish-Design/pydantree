"""pydantree_sitter.emit — the internal .scm emitter (014 §4.3).

The surviving core of the old query DSL: a NodeSpec tree emits one
S-expression pattern; predicates render inside the pattern's parens; a
capture suffix binds to the node whose `)` it follows. There is NO inline
alternation in tree-sitter queries — `a | b` emits two top-level patterns
(each its own pattern index). Nothing here is part of the public surface.

Design notes (all verified against the 0.26 bindings):
  * `.where()` predicates are emitted INSIDE the pattern's parens (a bare
    top-level `(#eq? ...)` is parsed as a SECOND, empty pattern that matches
    every node).
  * Quantifiers `*`/`+`/`?` on a sub-node: the DSL never captures the
    quantified node itself; captures live on the children.
"""

from __future__ import annotations

import json
from typing import Optional, Union

import tree_sitter

from .errors import QueryBuildError, SchemaCheckError


def _q(s: str) -> str:
    """Quote a literal for a .scm predicate argument (JSON string syntax)."""
    return json.dumps(s)


class Pred:
    """One `#pred?` — e.g. `#match? @name "^[A-Z]+"`."""

    __slots__ = ("name", "args")

    def __init__(self, name: str, args: list[str]):
        self.name = name
        self.args = args

    def emit(self) -> str:
        return "(#" + self.name + " " + " ".join(self.args) + ")"

    def __repr__(self) -> str:  # pragma: no cover
        return self.emit()


class CaptureRef:
    """Reference to a capture name for `.where(...)` predicates."""

    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name

    def matches(self, regex: str) -> Pred:
        return Pred("match?", [f"@{self.name}", _q(regex)])

    def eq(self, value: str) -> Pred:
        return Pred("eq?", [f"@{self.name}", _q(value)])

    def any_of(self, *values: str) -> Pred:
        return Pred("any-of?", [f"@{self.name}", *[_q(v) for v in values]])


def cap(name: str) -> CaptureRef:
    return CaptureRef(name)


class NodeSpec:
    """A tree-sitter node pattern: `(type field: (child) @cap)* ...`."""

    __slots__ = ("type", "field", "cap_name", "children", "predicates", "quant")

    def __init__(self, type: Optional[str] = None):
        self.type = type              # None -> wildcard `_`
        self.field: Optional[str] = None
        self.cap_name: Optional[str] = None
        self.children: list[NodeSpec] = []
        self.predicates: list[Pred] = []
        self.quant: str = ""          # "" | "?" | "*" | "+"

    def capture(self, name: str) -> "NodeSpec":
        self.cap_name = name
        return self

    def child(self, node: Optional[Union["NodeSpec", str]] = None, *,
              field: Optional[str] = None,
              capture: Optional[str] = None,
              quant: str = "") -> "NodeSpec":
        if isinstance(node, str):
            node = NodeSpec(node)
        elif node is None:
            node = NodeSpec(None)
        if field is not None:
            node.field = field
        if capture is not None:
            node.cap_name = capture
        if quant:
            node.quant = quant
        self.children.append(node)
        return self

    def where(self, *preds: Pred) -> "NodeSpec":
        self.predicates.extend(preds)
        return self

    def emit(self) -> str:
        parts: list[str] = []
        _emit(self, parts)
        return "".join(parts)

    def __repr__(self) -> str:  # pragma: no cover
        return f"NodeSpec({self.emit()})"


class PatternSet:
    """A group of patterns emitted as separate top-level query patterns
    (tree-sitter's only form of alternation)."""

    __slots__ = ("specs",)

    def __init__(self, specs: list[NodeSpec]):
        self.specs = specs


def _emit(spec: NodeSpec, parts: list[str]) -> None:
    parts.append("(")
    parts.append(spec.type if spec.type else "_")
    for c in spec.children:
        parts.append(" ")
        if c.field:
            parts.append(c.field)
            parts.append(":")
        _emit(c, parts)   # fully emits ( ... ) quant @cap for the child
    for p in spec.predicates:
        parts.append(" ")
        parts.append(p.emit())
    parts.append(")")
    if spec.quant:
        parts.append(spec.quant)
    if spec.cap_name:
        parts.append(" @" + spec.cap_name)


def node(type: Optional[str] = None) -> NodeSpec:
    return NodeSpec(type)


class Query:
    """A query over one grammar: one or more NodeSpec patterns, compiled ONCE
    against the Language the Extractor binds (the F-A1 lifetime fix: no
    class-level compiled cache — every Query belongs to one bind).
    `Query.raw(source)` wraps a literal .scm (__raw_query__, D11) whose
    captures must map to model fields (checked at compile).
    """

    def __init__(self, *specs: Union[NodeSpec, PatternSet], raw: Optional[str] = None):
        self.raw_source = raw
        self._raw_fields: Optional[set] = None   # the model's field names
        if raw is not None:
            self.specs = []
        else:
            self.specs: list[NodeSpec] = []
            for s in specs:
                if isinstance(s, NodeSpec):
                    self.specs.append(s)
                elif isinstance(s, PatternSet):
                    self.specs.extend(s.specs)
                else:
                    raise TypeError(f"expected NodeSpec/PatternSet, got {type(s)}")
            if not self.specs:
                raise ValueError("Query needs at least one pattern")
        self._compiled: Optional[tree_sitter.Query] = None
        self._quant_maps: Optional[list[dict[str, str]]] = None

    @classmethod
    def raw(cls, source: str) -> "Query":
        return cls(raw=str(source))

    def capture_names(self) -> set[str]:
        if self.raw_source is not None:
            if self._compiled is None:
                return set()
            return {self._compiled.capture_name(ci)
                    for ci in range(self._compiled.capture_count)}
        names: set[str] = set()

        def collect(spec: NodeSpec) -> None:
            if spec.cap_name:
                names.add(spec.cap_name)
            for c in spec.children:
                collect(c)

        for spec in self.specs:
            collect(spec)
        return names

    @property
    def source(self) -> str:
        if self.raw_source is not None:
            return self.raw_source
        return "\n\n".join(s.emit() for s in self.specs)

    def compile(self, lang: tree_sitter.Language) -> tree_sitter.Query:
        if self._compiled is not None:
            return self._compiled
        try:
            q = tree_sitter.Query(lang, self.source)
        except tree_sitter.QueryError as e:
            raise QueryBuildError(
                f"emitted .scm rejected by Query(): {e}\n---\n{self.source}"
            ) from e
        if self.raw_source is None and q.pattern_count != len(self.specs):
            raise QueryBuildError(
                f"emitted {len(self.specs)} pattern(s) but Query() parsed "
                f"{q.pattern_count} — emitter bug")
        if self._raw_fields is not None:
            caps = {q.capture_name(ci) for ci in range(q.capture_count)}
            unknown = caps - self._raw_fields
            if unknown:
                raise SchemaCheckError(
                    f"__raw_query__ captures {sorted(unknown)} that no field "
                    f"declares — model fields: {sorted(self._raw_fields)}")
        spec_caps = [self._capture_names_of(s) for s in self.specs] \
            if self.raw_source is None else [set(caps) if self._raw_fields is not None else set()]
        maps: list[dict[str, str]] = []
        for pi, caps in enumerate(spec_caps):
            m: dict[str, str] = {}
            for ci in range(q.capture_count):
                name = q.capture_name(ci)
                if name in caps:
                    m[name] = q.capture_quantifier(pi, ci)
            maps.append(m)
        self._compiled = q
        self._quant_maps = maps
        return q

    @staticmethod
    def _capture_names_of(spec) -> set[str]:
        names: set[str] = set()

        def collect(s: NodeSpec) -> None:
            if s.cap_name:
                names.add(s.cap_name)
            for c in s.children:
                collect(c)

        collect(spec)
        return names


class Cursor:
    """Match iteration over a compiled query. NOTE: the 0.26 bindings'
    `QueryCursor.matches()` is eager (returns a list); node TEXT/span reads
    happen on demand."""

    __slots__ = ("_query", "_quant_maps", "_tree")

    def __init__(self, query: tree_sitter.Query, quant_maps: list[dict[str, str]],
                 tree: tree_sitter.Tree):
        self._query = query
        self._quant_maps = quant_maps
        self._tree = tree

    def matches(self) -> list["MatchView"]:
        out = []
        for pi, caps in tree_sitter.QueryCursor(self._query).matches(self._tree.root_node):
            out.append(MatchView(pi, caps, self._quant_maps[pi]))
        return out

    def matches_on(self, node: tree_sitter.Node) -> list["MatchView"]:
        """Matches scoped to a node (record extraction)."""
        out = []
        for pi, caps in tree_sitter.QueryCursor(self._query).matches(node):
            out.append(MatchView(pi, caps, self._quant_maps[pi]))
        return out


class MatchView:
    """One query match; captures are raw tree_sitter.Node lists (the
    materializer's only need)."""

    __slots__ = ("pi", "_caps", "_quant")

    def __init__(self, pi: int, captures: dict[str, list],
                 quant: dict[str, str]):
        self.pi = pi
        self._caps = captures
        self._quant = quant

    def nodes(self, name: str) -> list:
        return list(self._caps.get(name, []))

    @property
    def caps(self) -> dict[str, list]:
        return self._caps

    def text(self, name: str) -> Optional[str]:
        ns = self._caps.get(name)
        if not ns:
            return None
        b = ns[0].text
        return "" if b is None else b.decode("utf-8")

    def quantifier(self, name: str) -> str:
        return self._quant.get(name, "")

    def __repr__(self) -> str:  # pragma: no cover
        return f"MatchView(pi={self.pi}, {list(self._caps)})"
