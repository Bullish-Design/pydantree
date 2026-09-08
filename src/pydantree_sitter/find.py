"""Typed-node traversal and the isolated raw-query binding path."""

from __future__ import annotations

from dataclasses import dataclass

import tree_sitter

from .errors import ExtractionError, QueryBuildError
from .match import match_ancestor_path
from .nodes import (
    Child,
    Node,
    _lazy_child,
    _LazyField,
    _MatchRejected,
    _predicates_match,
    _resolve_value,
    _target_kinds,
    normalize_under,
)
from .raw import Cursor, Query

__all__ = ["Selector", "SelectorChild", "find_in"]


# A raw query is tied to both the node class and the loaded language. Keep the
# Query wrapper so its compiled tree-sitter query stays available and retain
# QueryBuildError objects so an invalid raw query is attempted once.
_QUERY_CACHE: dict[
    tuple[type[Node], object], tree_sitter.Query | QueryBuildError
] = {}


@dataclass
class _Failure:
    pattern: int
    span: object
    snippet: str
    detail: str
    pydantic_errors: object = None


@dataclass(frozen=True)
class SelectorChild:
    """The inspectable filter for one declared node child."""

    name: str
    allowed_kinds: frozenset[str]
    optional: bool = False
    repeated: bool = False
    predicates: tuple[object, ...] = ()
    literal: tuple[str, ...] = ()
    literal_only: bool = False
    is_mapping: bool = False
    content_is_children: bool = False


@dataclass(frozen=True)
class Selector:
    """The shared, inspectable meaning of a generated node declaration.

    ``Selector`` is the data layer between a typed class and its execution
    strategy. It records the declaration and evaluates its anchor and
    required-child filters directly against a CST node.
    """

    anchor_kind: str
    anchor_kinds: frozenset[str]
    ancestor_path: tuple
    children: tuple[SelectorChild, ...]

    @classmethod
    def from_class(cls, node_cls: type[Node]) -> Selector:
        schema = getattr(node_cls, "__schema__", None)
        anchor_refs = _expand_refs(
            schema, ((node_cls.__kind__, True),))
        children = []
        for child in node_cls.__children__:
            info = schema.get(node_cls.__kind__) if schema is not None else None
            content_is_children = child.name == "content" and (
                info is None or "content" not in (info.fields or {}))
            refs = tuple(_schema_kinds(node_cls, child))
            literal = () if child.literal is None else (
                child.literal if isinstance(child.literal, tuple)
                else (child.literal,))
            children.append(SelectorChild(
                name=child.name,
                allowed_kinds=frozenset(kind for kind, _named in refs),
                optional=child.optional,
                repeated=child.repeated,
                predicates=child.predicates,
                literal=literal,
                # Query rendering treats a literal declaration as exact text,
                # including the generated anonymous-token kind alongside it.
                literal_only=child.literal is not None,
                is_mapping=child.is_mapping,
                content_is_children=content_is_children))
        under = tuple(getattr(node_cls, "__under__", None) or ())
        return cls(
            anchor_kind=node_cls.__kind__,
            anchor_kinds=frozenset(kind for kind, _named in anchor_refs),
            ancestor_path=normalize_under((*under, node_cls)),
            children=tuple(children))

    def matches(self, node) -> bool:
        """Return whether ``node`` satisfies this selector's filter."""
        if node.type not in self.anchor_kinds or \
                not match_ancestor_path(node, self.ancestor_path):
            return False
        return all(self._child_matches(node, child) for child in self.children)

    @staticmethod
    def _child_matches(node, child: SelectorChild) -> bool:
        # Optional and repeated values are resolver-owned. Their absence (or
        # an alternative value in a repeated field) does not reject an
        # otherwise matching anchor.
        if child.optional or child.repeated or child.is_mapping:
            return True
        candidates = _selector_candidates(node, child)
        if child.literal:
            acceptable = [candidate for candidate in candidates if
                          _node_text(candidate) in child.literal or
                          (not child.literal_only and
                           candidate.type in child.allowed_kinds)]
        elif child.allowed_kinds:
            acceptable = [candidate for candidate in candidates
                          if candidate.type in child.allowed_kinds]
        else:
            # There is no schema-derived kind set to filter. Let materializing
            # the declaration report a genuinely missing required value.
            acceptable = candidates
        if (child.allowed_kinds or child.literal) and not acceptable:
            return False
        if child.predicates and acceptable:
            return any(_predicates_match(child.predicates, candidate)
                       for candidate in acceptable)
        return True


def _raw_source(value) -> str:
    if isinstance(value, Query):
        return value.source
    return str(value)


def _expand_refs(schema, refs: tuple[tuple[str, bool], ...]) \
        -> list[tuple[str, bool]]:
    """Expand schema supertypes to their concrete node-kind references."""
    if schema is None:
        return list(dict.fromkeys(refs))
    expanded: list[tuple[str, bool]] = []
    pending = list(refs)
    seen: set[tuple[str, bool]] = set()
    while pending:
        kind, named = pending.pop(0)
        key = (kind, named)
        if key in seen:
            continue
        seen.add(key)
        subtypes = schema.supertype_subtypes(kind)
        if subtypes:
            pending[0:0] = [(subtype, True) for subtype in subtypes]
        else:
            expanded.append(key)
    return expanded


def _node_text(node) -> str:
    return (node.text or b"").decode("utf-8", "replace")


def _selector_candidates(node, child: SelectorChild) -> list:
    if child.content_is_children:
        return list(node.named_children)
    if child.repeated:
        return [candidate for index, candidate in enumerate(node.children)
                if node.field_name_for_child(index) == child.name]
    field = node.child_by_field_name(child.name)
    return [field] if field is not None else []


def _schema_kinds(cls: type[Node], child: Child) -> list[tuple[str, bool]]:
    """Return the schema-derived kinds for one declared child."""
    schema = getattr(cls, "__schema__", None)
    refs: list[tuple[str, bool]] = []
    if schema is not None:
        info = schema.get(cls.__kind__)
        has_content_children = info is not None and \
            info.children is not None and "content" not in (info.fields or {})
        if child.name == "content" and has_content_children:
            refs = [(ref.type, ref.named)
                    for ref in schema.children_types(cls.__kind__)]
        elif schema.has_field(cls.__kind__, child.name):
            refs = [(ref.type, ref.named)
                    for ref in schema.field_types(cls.__kind__, child.name)]
    if child.kinds:
        refs = [(kind, True) for kind in child.kinds]
    if not refs:
        refs = [(kind, True) for kind in _target_kinds(child.target)]
    return _expand_refs(schema, tuple(dict.fromkeys(refs)))


def _cached_query(cls: type[Node], language, source: str):
    """Return the cached compiled query or its cached build failure."""
    key = (cls, language)
    try:
        return _QUERY_CACHE[key]
    except KeyError:
        pass
    query = Query.raw(source)
    try:
        compiled = query.compile(language)
    except QueryBuildError as error:
        _QUERY_CACHE[key] = error
        return error
    _QUERY_CACHE[key] = compiled
    return compiled


def _walk(raw, cls: type[Node], out: list, failures: list[_Failure]) -> None:
    selector = Selector.from_class(cls)

    def visit(candidate):
        if selector.matches(candidate):
            try:
                out.append(cls.from_node(candidate))
            except _MatchRejected:
                pass
            except Exception as error:  # noqa: BLE001 - per-match diagnostics
                failures.append(_failure(candidate, error, 0))
        for child in candidate.named_children:
            visit(child)

    visit(raw)


def _failure(node, error: Exception, pattern: int) -> _Failure:
    text = (node.text or b"").decode("utf-8", "replace")
    span = None
    try:
        from .span import Span
        span = Span.from_node(node)
    except Exception:  # noqa: BLE001 - diagnostic fallback
        span = None
    return _Failure(pattern, span, text, str(error),
                    getattr(error, "errors", lambda: None)())


def _raw_find(raw, cls: type[Node], language) -> tuple[list, list[_Failure]]:
    if language is None:
        raise TypeError("raw node queries require a loaded Grammar language")
    source = _raw_source(vars(cls)["__raw_query__"])
    query = _cached_query(cls, language, source)
    if isinstance(query, QueryBuildError):
        raise query
    Query.raw(source).check_captures(
        language, {child.name for child in cls.__children__}, compiled=query)
    matches = Cursor(query, raw).matches_on(raw)
    rows = []
    failures: list[_Failure] = []
    by_name = {child.name: child for child in cls.__children__}
    for match in matches:
        kwargs = {}
        lazy_fields = {}
        captured = [node for values in match.caps.values() for node in values]
        anchor = captured[0] if captured else raw
        if captured and captured[0].parent is not None:
            anchor = captured[0].parent
        try:
            for name, child in by_name.items():
                nodes = match.nodes(name)
                if child.repeated:
                    if nodes and _lazy_child(child):
                        lazy_fields[name] = _LazyField(
                            child.target, tuple(nodes), child.codec, True)
                        kwargs[name] = []
                    else:
                        kwargs[name] = [
                            _resolve_value(child.target, node, child.codec)
                            for node in nodes]
                elif nodes:
                    if _lazy_child(child):
                        lazy_fields[name] = _LazyField(
                            child.target, nodes[0], child.codec)
                    else:
                        kwargs[name] = _resolve_value(
                            child.target, nodes[0], child.codec)
                elif child.optional:
                    kwargs[name] = None
                else:
                    raise ValueError(
                        f"raw query did not capture required field {name!r}")
            for name, lazy in lazy_fields.items():
                kwargs[name] = lazy.placeholder()
            obj = cls.model_validate(kwargs)
            for name in lazy_fields:
                obj.__dict__.pop(name, None)
            obj._lazy_fields = lazy_fields
            obj._node = anchor
            from .span import Span
            obj._span = Span.from_node(anchor)
            rows.append(obj)
        except Exception as error:  # noqa: BLE001 - per-match diagnostics
            failures.append(_failure(anchor, error, match.pattern_index))
    return rows, failures


def find_in(raw, cls: type[Node], language=None) -> list:
    """Resolve every matching node in ``raw`` into ``cls`` instances."""
    out: list = []
    failures: list[_Failure] = []
    if getattr(cls, "__raw_query__", None) is not None:
        out, failures = _raw_find(raw, cls, language)
    else:
        _walk(raw, cls, out, failures)
    if failures:
        raise ExtractionError(failures, cls)
    return out
