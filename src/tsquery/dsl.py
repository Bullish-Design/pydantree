"""tsquery.dsl — query DSL -> .scm emitter for tree-sitter 0.26 (Product A).

Mechanical port of `spike-a/dsl.py` (Phase-1 spike, validated against the
installed 0.26 bindings). Design notes (all verified in spike-a FINDINGS §1):

  * A `NodeSpec` tree emits one S-expression pattern. `.where()` predicates
    are emitted INSIDE the pattern's parens (a bare top-level `(#eq? ...)`
    is parsed as a SECOND, empty pattern that matches every node).
  * A capture suffix binds to the node whose `)` it follows, so a node's own
    `@cap` is appended after ITS closing paren, not after a child's.
  * There is NO inline alternation in tree-sitter queries: `a | b` emits two
    top-level patterns (each its own pattern index).
  * Quantifiers `*`/`+`/`?` on a sub-node: the DSL never captures the
    quantified node itself; captures live on the children.
"""

from __future__ import annotations

import json
from typing import Optional, Union

import tree_sitter


# --------------------------------------------------------------------------
# Predicates
# --------------------------------------------------------------------------

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

    def __repr__(self) -> str:  # pragma: no cover
        return f"cap({self.name!r})"


def cap(name: str) -> CaptureRef:
    return CaptureRef(name)


# --------------------------------------------------------------------------
# Node specs
# --------------------------------------------------------------------------

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

    # ---- builder sugar -----------------------------------------------------

    def capture(self, name: str) -> "NodeSpec":
        self.cap_name = name
        return self

    def child(self, node: Optional[Union["NodeSpec", str]] = None, *,
              field: Optional[str] = None,
              capture: Optional[str] = None,
              quant: str = "") -> "NodeSpec":
        """Add a child. `node` is a NodeSpec, a bare type string, or None
        (wildcard). `field`/`capture`/`quant` sugar the child."""
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

    def __or__(self, other: Union["NodeSpec", "PatternSet"]) -> "PatternSet":
        if isinstance(other, NodeSpec):
            return PatternSet([self, other])
        return PatternSet([self, *other.specs])

    def __repr__(self) -> str:  # pragma: no cover
        return f"NodeSpec({self.emit()})"

    # ---- emission ----------------------------------------------------------

    def emit(self) -> str:
        parts: list[str] = []
        _emit(self, parts)
        return "".join(parts)


class PatternSet:
    """A group of patterns emitted as separate top-level query patterns
    (tree-sitter's only form of alternation)."""

    __slots__ = ("specs",)

    def __init__(self, specs: list[NodeSpec]):
        self.specs = specs

    def __or__(self, other: Union[NodeSpec, "PatternSet"]) -> "PatternSet":
        if isinstance(other, NodeSpec):
            return PatternSet([*self.specs, other])
        return PatternSet([*self.specs, *other.specs])

    def __iter__(self):
        return iter(self.specs)


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


# --------------------------------------------------------------------------
# Query (a compiled pattern set)
# --------------------------------------------------------------------------

class QueryBuildError(Exception):
    """The DSL-emitted .scm was rejected by tree_sitter.Query()."""


class Query:
    """A query over one grammar: one or more NodeSpec patterns.

    compile(lang) -> tree_sitter.Query; the constructor is the cheapest
    validator there is (rejects unknown node kinds and field names).
    """

    def __init__(self, *specs: Union[NodeSpec, PatternSet]):
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

    # ---- cheap checks (no grammar introspection) ---------------------------

    def capture_names(self) -> set[str]:
        names: set[str] = set()

        def collect(spec: NodeSpec) -> None:
            if spec.cap_name:
                names.add(spec.cap_name)
            for c in spec.children:
                collect(c)

        for spec in self.specs:
            collect(spec)
        return names

    def check(self) -> list[str]:
        """Warnings for DSL bugs: predicates referencing captures that no
        pattern declares (a typo'd capture name is otherwise silent)."""
        warnings: list[str] = []
        declared = self.capture_names()
        for spec in self.specs:
            for p in spec.predicates:
                for a in p.args:
                    if a.startswith("@"):
                        name = a[1:]
                        if name not in declared:
                            warnings.append(
                                f"predicate references @{name} but no pattern "
                                f"captures {name!r} (typo?)")
        return warnings

    # ---- compile -----------------------------------------------------------

    @property
    def source(self) -> str:
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
        if q.pattern_count != len(self.specs):
            raise QueryBuildError(
                f"emitted {len(self.specs)} pattern(s) but Query() parsed "
                f"{q.pattern_count} — emitter bug")
        # NOTE: capture_quantifier(pi, ci) raises SystemError for captures
        # that do not belong to pattern pi (0.26), so only query indices for
        # capture names this spec declares (known statically).
        spec_caps = [self._capture_names_of(s) for s in self.specs]
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

    def quantifier_for(self, capture: str) -> str:
        """Max quantifier for a capture across patterns (for binding checks)."""
        best = ""
        for m in self._quant_maps or []:
            q = m.get(capture, "")
            if q in ("*", "+"):
                return q
            if q == "?":
                best = "?"
        return best

    # ---- result modes ------------------------------------------------------

    def run(self, tree: tree_sitter.Tree) -> "Cursor":
        """Lazy mode: no model construction; NodeView text is read on demand."""
        q = self.compile(tree.language)
        return Cursor(q, self._quant_maps or [], tree)

    def extract(self, tree: tree_sitter.Tree, into: type, *,
                strict: bool = True) -> list:
        """Typed mode: captures -> OutputModel instances (opt-in)."""
        from .materialize import materialize_matches
        return materialize_matches(self, tree, into, strict=strict)

    def validate(self, tree: tree_sitter.Tree) -> tuple[bool, list]:
        """Does the tree parse cleanly? Reports ERROR/MISSING diagnostics."""
        diags = []

        def walk(node, depth=0):
            if node.type == "ERROR" or node.is_missing:
                diags.append({
                    "kind": "MISSING" if node.is_missing else "ERROR",
                    "type": node.type,
                    "byte_range": node.byte_range,
                    "line": node.start_point.row + 1,
                    "snippet": _snippet(tree, node),
                })
            for c in node.children:
                walk(c)
        walk(tree.root_node)
        return (not diags), diags


def _snippet(tree, node, width=40) -> str:
    src = _source_of(tree)
    if src is None:
        return ""
    s, e = node.byte_range
    return src[s:e][:width].decode("utf-8", "replace")


def _source_of(tree) -> Optional[bytes]:
    # best-effort: the tree doesn't retain the source; callers that need
    # snippets should use Cursor which holds it. Fall back to the root text.
    return getattr(tree, "_source", None)


# --------------------------------------------------------------------------
# Lazy result surface
# --------------------------------------------------------------------------

class NodeView:
    """A lazy view of a captured Node: text/span are computed on demand."""

    __slots__ = ("_node", "_source")

    def __init__(self, node: tree_sitter.Node, source: bytes):
        self._node = node
        self._source = source

    @property
    def type(self) -> str:
        return self._node.type

    @property
    def text(self) -> str:
        b = self._node.text
        return "" if b is None else b.decode("utf-8")

    @property
    def bytes(self) -> bytes:
        return self._node.text or b""

    @property
    def byte_range(self) -> tuple[int, int]:
        return self._node.byte_range

    @property
    def line(self) -> int:
        return self._node.start_point.row + 1

    @property
    def column(self) -> int:
        return self._node.start_point.column

    @property
    def span(self) -> "Span":
        from .materialize import Span
        return Span.from_node(self._node)

    @property
    def snippet(self) -> str:
        s, e = self._node.byte_range
        return self._source[s:e].decode("utf-8", "replace")

    def __repr__(self) -> str:  # pragma: no cover
        return f"NodeView({self._node.type!r}, {self.text!r})"


class MatchView:
    """One query match; captures are NodeViews, read lazily."""

    __slots__ = ("pi", "_caps", "_source", "_quant")

    def __init__(self, pi: int, captures: dict[str, list],
                 source: bytes, quant: dict[str, str]):
        self.pi = pi
        self._caps = captures
        self._source = source
        self._quant = quant

    def capture(self, name: str) -> list[NodeView]:
        return [NodeView(n, self._source) for n in self._caps.get(name, [])]

    def nodes(self, name: str) -> list:
        """Raw tree_sitter.Node list (for the materializer)."""
        return list(self._caps.get(name, []))

    def first(self, name: str) -> Optional[NodeView]:
        ns = self._caps.get(name)
        if not ns:
            return None
        return NodeView(ns[0], self._source)

    def text(self, name: str) -> Optional[str]:
        f = self.first(name)
        return None if f is None else f.text

    def all_text(self, name: str) -> list[str]:
        return [v.text for v in self.capture(name)]

    def has(self, name: str) -> bool:
        return bool(self._caps.get(name))

    def pattern(self) -> int:
        return self.pi

    def quantifier(self, name: str) -> str:
        return self._quant.get(name, "")

    def __repr__(self) -> str:  # pragma: no cover
        return f"MatchView(pi={self.pi}, {list(self._caps)})"


class Cursor:
    """Lazy cursor: iterates matches without constructing models. NOTE: the
    0.26 bindings' `QueryCursor.matches()` is eager (returns a list); our
    laziness is that node TEXT/span reads happen on demand, and nothing is
    coerced or validated."""

    __slots__ = ("_query", "_quant_maps", "_tree", "_source")

    def __init__(self, query: tree_sitter.Query, quant_maps: list[dict[str, str]],
                 tree: tree_sitter.Tree):
        self._query = query
        self._quant_maps = quant_maps
        self._tree = tree
        # the bindings don't keep the source; recover it from the root text.
        root = tree.root_node
        self._source = root.text or b""

    def matches(self) -> list[MatchView]:
        out = []
        for pi, caps in tree_sitter.QueryCursor(self._query).matches(self._tree.root_node):
            out.append(MatchView(pi, caps, self._source, self._quant_maps[pi]))
        return out

    def matches_on(self, node: tree_sitter.Node) -> list[MatchView]:
        """Sub-query: matches scoped to a node (used by record extraction)."""
        out = []
        for pi, caps in tree_sitter.QueryCursor(self._query).matches(node):
            out.append(MatchView(pi, caps, self._source, self._quant_maps[pi]))
        return out
