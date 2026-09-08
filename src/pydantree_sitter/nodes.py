"""The typed node universe.

This module is the additive Phase-1 core of the typed-node-universe refactor.
It owns one annotation grammar for Product A and, later, Product B.
"""

from __future__ import annotations

import inspect
import re
import sys
import types
from dataclasses import dataclass
from typing import (
    Annotated,
    Any,
    ClassVar,
    ForwardRef,
    Literal,
    Union,
    cast,
    get_args,
    get_origin,
)

import tree_sitter
from pydantic import BaseModel, PrivateAttr
from pydantic._internal._model_construction import ModelMetaclass

from .codecs import unescape_json
from .errors import SchemaCheckError, ShapeError
from .schema import NodeSchema
from .span import Span

__all__ = [
    "GAP",
    "AnyOf",
    "Child",
    "Eq",
    "Matches",
    "Node",
    "NodeMeta",
    "PathStep",
    "normalize_under",
]


GAP = object()


@dataclass(frozen=True)
class PathStep:
    """One ancestor-path step used by ``Node.__under__``."""

    kinds: tuple[str, ...]


class Matches:
    """A regular-expression predicate for an ``Annotated`` field."""

    __slots__ = ("pattern",)

    def __init__(self, pattern: str):
        re.compile(pattern)
        self.pattern = pattern


class Eq:
    """An exact-text predicate for an ``Annotated`` field."""

    __slots__ = ("value",)

    def __init__(self, value: str):
        self.value = value


class AnyOf:
    """A finite exact-text predicate for an ``Annotated`` field."""

    __slots__ = ("values",)

    def __init__(self, *values: str):
        if not values:
            raise ValueError("AnyOf needs at least one value")
        self.values = tuple(values)


def _value_type(cls: type[Node]):
    """Return the value codec's declared return annotation."""
    import typing
    return typing.get_type_hints(cls.__value__).get("return", str)


def _snake(name: str) -> str:
    """Convert a class name to the tree-sitter snake-case convention."""
    prefix = "_" if name.startswith("_") else ""
    name = name.lstrip("_")
    out: list[str] = []
    for i, char in enumerate(name):
        if char.isupper() and i and (not name[i - 1].isupper() or
                                     (i + 1 < len(name) and
                                      name[i + 1].islower())):
            out.append("_")
        out.append(char.lower())
    return prefix + "".join(out)


@dataclass(frozen=True, eq=False)
class Child:
    """One annotated CST child declaration.

    ``kinds`` contains explicit node-kind alternatives. ``target`` contains
    the declared Python value type when the annotation is a scalar or node
    class. ``literal`` stores anonymous-token literals.
    """

    name: str
    kinds: tuple[str, ...] = ()
    optional: bool = False
    repeated: bool = False
    literal: str | tuple[str, ...] | None = None
    target: Any = None
    is_mapping: bool = False
    mapping_kind: str | None = None
    codec: Any = None
    predicates: tuple[Any, ...] = ()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Child):
            return NotImplemented
        return (
            self.name, self.kinds, self.optional, self.repeated,
            self.literal, self.is_mapping, _target_signature(self.target),
            self.mapping_kind,
            _target_signature(self.codec),
            self.predicates,
        ) == (
            other.name, other.kinds, other.optional, other.repeated,
            other.literal, other.is_mapping, _target_signature(other.target),
            other.mapping_kind,
            _target_signature(other.codec),
            other.predicates,
        )

    def __hash__(self) -> int:
        return hash((self.name, self.kinds, self.optional, self.repeated,
                     self.literal, self.is_mapping,
                     _target_signature(self.target), self.mapping_kind,
                     _target_signature(self.codec), self.predicates))


def _target_signature(target: Any):
    if _is_node_type(target):
        return ("node", target.__kind__)
    if isinstance(target, tuple) and all(_is_node_type(item) for item in target):
        return ("nodes", tuple(item.__kind__ for item in target))
    origin = get_origin(target)
    if origin in (Union, types.UnionType):
        return ("union", tuple(_target_signature(item)
                               for item in get_args(target)))
    if origin is list:
        return ("list", _target_signature(get_args(target)[0]))
    if origin is Literal:
        return ("literal", get_args(target))
    return target


def _is_union(annotation: Any) -> bool:
    return get_origin(annotation) in (Union, types.UnionType)


def _unwrap_annotated(annotation: Any) -> Any:
    if get_origin(annotation) is Annotated:
        return get_args(annotation)[0]
    return annotation


def _split_annotated(annotation: Any) -> tuple[Any, tuple[Any, ...]]:
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        return args[0], tuple(args[1:])
    return annotation, ()


def _resolve_forward(annotation: Any, owner: type,
                     namespace: dict[str, Any] | None = None) -> Any:
    if isinstance(annotation, str):
        module = sys.modules.get(owner.__module__)
        scope = namespace if namespace is not None else (
            vars(module) if module is not None else None)
        if scope is not None:
            try:
                return eval(annotation, scope, scope)
            except Exception:  # noqa: BLE001 - unresolved until rebuild
                return annotation
        return annotation
    if not isinstance(annotation, ForwardRef):
        return annotation
    module = sys.modules.get(owner.__module__)
    if module is None:
        return annotation
    try:
        return eval(annotation.__forward_arg__, vars(module), vars(module))
    except Exception:  # noqa: BLE001 - pydantic may resolve it later
        return annotation


def _is_node_type(annotation: Any) -> bool:
    try:
        return isinstance(annotation, type) and issubclass(annotation, Node)
    except TypeError:
        return False


def _kind_of(annotation: Any) -> str | None:
    return getattr(annotation, "__kind__", None) if _is_node_type(annotation) else None


def _node_kinds(annotations: tuple[Any, ...]) -> tuple[str, ...]:
    kinds: list[str] = []
    for annotation in annotations:
        kind = _kind_of(annotation)
        if kind is not None:
            kinds.append(kind)
    return tuple(kinds)


def _parse_child(owner: type[Node], name: str, annotation: Any,
                 namespace: dict[str, Any] | None = None) -> Child:
    annotation, metadata = _split_annotated(annotation)
    annotation = _resolve_forward(annotation, owner, namespace)
    predicates = tuple(item for item in metadata
                       if isinstance(item, (Matches, Eq, AnyOf)))
    optional = False
    repeated = False
    is_mapping = False

    if _is_union(annotation):
        args = tuple(_resolve_forward(_unwrap_annotated(a), owner, namespace)
                     for a in get_args(annotation))
        optional = type(None) in args
        args = tuple(a for a in args if a is not type(None))
        if not args:
            raise ShapeError(f"field {name!r}: annotation has no value type")
        if len(args) == 1:
            annotation = args[0]
        else:
            literal_values: list[str] = []
            node_args: list[Any] = []
            valid = True
            for arg in args:
                if get_origin(arg) is Literal:
                    values = get_args(arg)
                    if not values or not all(isinstance(v, str)
                                             for v in values):
                        valid = False
                        break
                    literal_values.extend(values)
                elif _is_node_type(arg):
                    node_args.append(arg)
                else:
                    valid = False
                    break
            if valid and len(literal_values) + len(node_args) == len(args):
                literal: str | tuple[str, ...] | None = None
                if literal_values:
                    literal = (literal_values[0]
                               if len(literal_values) == 1
                               else tuple(literal_values))
                return Child(
                    name=name,
                    kinds=_node_kinds(tuple(node_args)),
                    optional=optional,
                    literal=literal,
                    target=tuple(node_args) if node_args else annotation,
                    predicates=predicates)
            node_kinds = tuple(k for a in args if (k := _kind_of(a)) is not None)
            if len(node_kinds) == len(args):
                return Child(name, node_kinds, optional=optional, target=args,
                             predicates=predicates)
            raise ShapeError(
                f"field {name!r}: union alternatives must be node classes "
                f"or an optional value, got {args!r}")

    origin = get_origin(annotation)
    if origin is list:
        repeated = True
        args = get_args(annotation)
        annotation = _resolve_forward(
            _unwrap_annotated(args[0] if args else Any), owner, namespace)
    elif origin is dict:
        is_mapping = True
        mapping_type = annotation
        args = get_args(annotation)
        annotation = _resolve_forward(
            _unwrap_annotated(args[1] if len(args) > 1 else Any), owner,
            namespace)
        schema = getattr(owner, "__schema__", None)
        if schema is None:
            raise ShapeError(
                f"field {name!r}: dict projections require a node schema")
        parent = next((item for item in schema.node_types
                       if item.type == owner.__kind__ and item.named), None)
        refs = parent.children.types if parent and parent.children else ()
        candidates = []
        for ref in refs:
            for kind in schema.expand([ref.type]):
                info = schema.get(kind)
                if info is not None and info.fields and \
                        "key" in info.fields and "value" in info.fields:
                    candidates.append(kind)
        candidates = sorted(set(candidates))
        if len(candidates) != 1:
            shown = ", ".join(candidates) or "none"
            raise ShapeError(
                f"field {name!r}: dict projection on {owner.__kind__!r} "
                f"has {len(candidates)} key/value child kinds ({shown}); "
                "write list[Pair] with an explicit pair class")
        return Child(name, (candidates[0],), optional=optional,
                     target=mapping_type, is_mapping=True,
                     mapping_kind=candidates[0], predicates=predicates)

    if origin is Literal:
        values = get_args(annotation)
        if not values or not all(isinstance(v, str) for v in values):
            raise ShapeError(
                f"field {name!r}: Literal must contain string tokens")
        literal: str | tuple[str, ...] = values[0] if len(values) == 1 else values
        return Child(name, (), optional=optional, repeated=repeated,
                     literal=literal, target=annotation,
                     is_mapping=is_mapping, predicates=predicates)

    kind = _kind_of(annotation)
    if kind is not None:
        return Child(name, (kind,), optional=optional, repeated=repeated,
                     target=annotation, is_mapping=is_mapping,
                     predicates=predicates)
    if isinstance(annotation, tuple) and all(_is_node_type(a) for a in annotation):
        return Child(name, _node_kinds(tuple(annotation)), optional=optional,
                     repeated=repeated, target=annotation,
                     is_mapping=is_mapping, predicates=predicates)
    return Child(name, (), optional=optional, repeated=repeated,
                 target=annotation, is_mapping=is_mapping,
                 predicates=predicates)


def _own_annotations(cls: type[Node],
                     namespace: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        annotations = inspect.get_annotations(
            cls, eval_str=True, globals=namespace, locals=namespace)
    except (NameError, TypeError):
        annotations = inspect.get_annotations(cls, eval_str=False)
    out: dict[str, Any] = {}
    for name, annotation in annotations.items():
        if name.startswith(("_", "__")):
            continue
        if get_origin(annotation) is ClassVar:
            continue
        out[name] = annotation
    return out


def _children_for(cls: type[Node],
                  namespace: dict[str, Any] | None = None) -> tuple[Child, ...]:
    inherited = {child.name: child for base in cls.__mro__[1:]
                 for child in getattr(base, "__children__", ())}
    children: list[Child] = []
    for name, annotation in _own_annotations(cls, namespace).items():
        child = _parse_child(cls, name, annotation, namespace)
        base = inherited.get(name)
        if base is not None and not child.kinds and base.kinds:
            child = Child(
                name=child.name,
                kinds=base.kinds,
                optional=child.optional,
                repeated=child.repeated,
                literal=child.literal,
                target=child.target,
                is_mapping=child.is_mapping,
                mapping_kind=child.mapping_kind,
                codec=child.codec,
                predicates=child.predicates)
        children.append(child)
    # A generated base owns the complete schema declaration. A narrowed
    # subclass replaces only the attributes it declares.
    declared = {child.name for child in children}
    for child in inherited.values():
        if child.name not in declared:
            children.append(child)
    return tuple(children)


def normalize_under(path: tuple[Any, ...]) -> tuple[Any, ...]:
    """Normalize node classes and ``...`` for ``match_ancestor_path``."""
    out = []
    for step in path:
        if step is Ellipsis or step == "...":
            out.append(GAP)
            continue
        alternatives = (get_args(step) if _is_union(step) else
                        step if isinstance(step, (tuple, list)) else (step,))
        kinds = []
        for item in alternatives:
            if isinstance(item, str):
                kinds.append(item)
            else:
                kind = _kind_of(item)
                if kind is None:
                    raise TypeError(f"__under__ expects node classes, got {item!r}")
                kinds.append(kind)
        out.append(PathStep(tuple(kinds)))
    return tuple(out)


def _schema_entry(schema: NodeSchema, kind: str, name: str):
    info = schema.get(kind)
    if info is not None and not info.named:
        info = next((candidate for candidate in schema.node_types
                     if candidate.type == kind and candidate.named), info)
    if info is None:
        return None
    if name == "content":
        return info.children
    return (info.fields or {}).get(name)


def _check_against_schema(cls: type[Node]) -> None:
    schema = getattr(cls, "__schema__", None)
    if schema is None or not getattr(cls, "__kind__", None):
        return
    if getattr(cls, "__raw_query__", None) is not None:
        # Raw captures are intentionally name-addressed rather than
        # schema-field-addressed; Query.check_captures performs the bind-time
        # validation against the loaded language.
        return
    kind = cls.__kind__
    for child in cls.__children__:
        if child.literal is not None and not child.is_mapping:
            continue
        if child.is_mapping:
            continue
        entry = _schema_entry(schema, kind, child.name)
        if entry is None:
            possible = schema.possible_children(kind)
            if child.name != "content" and child.name not in possible:
                raise SchemaCheckError(
                    f"{cls.__name__}.{child.name}: {child.name!r} is not a "
                    f"field or possible child of schema entry {kind!r}",
                    schema_entry=child.name, model=cls)
            continue
        schema_kinds: set[str] = set()
        pending = {ref.type for ref in entry.types}
        while pending:
            expanded = schema.expand(pending)
            fresh = expanded - schema_kinds
            schema_kinds.update(fresh)
            pending = {kind for kind in fresh if schema.is_supertype(kind)}
        if child.kinds and not set(child.kinds) <= schema_kinds:
            raise SchemaCheckError(
                f"{cls.__name__}.{child.name}: declared kinds "
                f"{child.kinds!r} are not a subset of schema entry "
                f"{kind!r}.{child.name!r} ({sorted(schema_kinds)!r})",
                schema_entry=f"{kind}.{child.name}", model=cls)
        schema_optional = not entry.required
        if not entry.multiple and child.optional != schema_optional:
            raise SchemaCheckError(
                f"{cls.__name__}.{child.name}: optionality disagrees with "
                f"schema entry {kind!r}.{child.name!r} (schema optional="
                f"{schema_optional})",
                schema_entry=f"{kind}.{child.name}", model=cls)
        if child.repeated != entry.multiple:
            raise SchemaCheckError(
                f"{cls.__name__}.{child.name}: repetition disagrees with "
                f"schema entry {kind!r}.{child.name!r} (schema multiple="
                f"{entry.multiple})",
                schema_entry=f"{kind}.{child.name}", model=cls)


def _text(node: tree_sitter.Node) -> str:
    return node.text.decode("utf-8", "replace") if node.text else ""


class _MatchRejected(Exception):
    """The anchor failed a required field predicate."""


def _predicates_match(predicates: tuple[Any, ...], node) -> bool:
    text = _text(node)
    for predicate in predicates:
        if isinstance(predicate, Matches) and re.search(predicate.pattern, text) is None:
            return False
        if isinstance(predicate, Eq) and text != predicate.value:
            return False
        if isinstance(predicate, AnyOf) and text not in predicate.values:
            return False
    return True


def _contains_node_target(target: Any) -> bool:
    if _is_node_type(target):
        return True
    if isinstance(target, tuple):
        return any(_contains_node_target(item) for item in target)
    return any(_contains_node_target(item) for item in get_args(target))


def _lazy_child(child: Child) -> bool:
    """Whether a child resolves to a Node and can be deferred."""
    return child.codec is None and _contains_node_target(child.target)


def _build_resolver(cls: type[Node]):
    children = cls.__children__
    schema = getattr(cls, "__schema__", None)

    def resolve(node: tree_sitter.Node, *, _lazy: bool = False):
        kwargs: dict[str, Any] = {}
        lazy_fields: dict[str, _LazyField] = {}
        for child in children:
            if child.literal is not None and not child.kinds and \
                    not child.is_mapping:
                literal_values = (child.literal if isinstance(child.literal,
                                  tuple) else (child.literal,))
                literal = next(
                    (candidate for candidate in node.children
                     if _text(candidate) in literal_values), None)
                if literal is not None:
                    kwargs[child.name] = _text(literal)
                continue
            if child.is_mapping:
                candidates = [candidate for candidate in node.named_children
                              if candidate.type == child.mapping_kind]
                values: dict[str, Any] = {}
                value_type = (get_args(child.target)[1]
                              if get_origin(child.target) is dict and
                              len(get_args(child.target)) > 1 else Any)
                for pair in candidates:
                    key = pair.child_by_field_name("key")
                    value = pair.child_by_field_name("value")
                    if key is None or value is None:
                        continue
                    key_text = _text(key)
                    if key.type == "string":
                        key_text = unescape_json(key_text)
                    decoded = _resolve_value(value_type, value)
                    if value.type == "string" and value_type is str:
                        decoded = unescape_json(_text(value))
                    values[key_text] = decoded
                kwargs[child.name] = values
                continue
            info = schema.get(cls.__kind__) if schema is not None else None
            content_is_children = child.name == "content" and (
                info is None or "content" not in (info.fields or {}))
            if content_is_children:
                candidates = list(node.named_children)
            else:
                if child.repeated:
                    candidates = [candidate for index, candidate in
                                  enumerate(node.children)
                                  if node.field_name_for_child(index) ==
                                  child.name]
                else:
                    field = node.child_by_field_name(child.name)
                    candidates = [field] if field is not None else []
            allowed_kinds = set(child.kinds) or _target_kinds(child.target)
            if allowed_kinds:
                candidates = [candidate for candidate in candidates
                              if candidate is not None and
                              candidate.type in allowed_kinds]
            if child.repeated:
                candidates = [candidate for candidate in candidates
                              if _predicates_match(child.predicates, candidate)]
                if _lazy and candidates and _lazy_child(child):
                    lazy_fields[child.name] = _LazyField(
                        child.target, tuple(candidates), child.codec, True)
                    kwargs[child.name] = []
                else:
                    values = [_resolve_value(child.target, candidate, child.codec)
                              for candidate in candidates]
                    if values or child.repeated:
                        kwargs[child.name] = values
            elif candidates:
                candidate = candidates[0]
                if not _predicates_match(child.predicates, candidate):
                    if child.optional:
                        kwargs[child.name] = None
                    else:
                        raise _MatchRejected(child.name)
                elif _lazy and _lazy_child(child):
                    lazy_fields[child.name] = _LazyField(
                        child.target, candidate, child.codec)
                else:
                    kwargs[child.name] = _resolve_value(
                        child.target, candidate, child.codec)
            elif child.optional:
                kwargs[child.name] = None
        return (kwargs, lazy_fields) if _lazy else kwargs

    return resolve


def _resolve_value(target: Any, node: tree_sitter.Node, codec=None) -> Any:
    if codec is not None:
        if isinstance(codec, tuple):
            for candidate in codec:
                if candidate.__kind__ == node.type:
                    return candidate.from_node(node).__value__()
        elif _is_node_type(codec):
            return codec.from_node(node).__value__()
    if _is_node_type(target):
        return target.from_node(node)
    value = _resolve_node_target(target, node)
    if value is not _UNRESOLVED:
        return value
    return _text(node)


_UNRESOLVED = object()


def _node_target(target: Any, kind: str):
    if _is_node_type(target):
        return target if target.__kind__ == kind else None
    candidates = target if isinstance(target, tuple) else get_args(target)
    for candidate in candidates:
        resolved = _node_target(candidate, kind)
        if resolved is not None:
            return resolved
    return None


@dataclass
class _LazyField:
    """A deferred direct child resolution, including its cached outcome."""

    target: Any
    nodes: tree_sitter.Node | tuple[tree_sitter.Node, ...]
    codec: Any = None
    repeated: bool = False
    _resolved: bool = False
    _value: Any = None
    _error: Exception | None = None

    def placeholder(self):
        nodes = (cast(tuple[tree_sitter.Node, ...], self.nodes)
                 if self.repeated else
                 (cast(tree_sitter.Node, self.nodes),))
        values = []
        for node in nodes:
            target = _node_target(self.target, node.type)
            if target is None:
                raise TypeError(
                    f"cannot defer {self.target!r} for node kind {node.type!r}")
            values.append(target.model_construct())
        return values if self.repeated else values[0]

    def resolve(self):
        if self._error is not None:
            raise self._error
        if self._resolved:
            return self._value
        try:
            if self.repeated:
                nodes = cast(tuple[tree_sitter.Node, ...], self.nodes)
                value = [_resolve_value(self.target, node, self.codec)
                         for node in nodes]
            else:
                node = cast(tree_sitter.Node, self.nodes)
                value = _resolve_value(self.target, node, self.codec)
        except Exception as error:
            self._error = error
            raise
        self._value = value
        self._resolved = True
        return value


def _target_kinds(target: Any) -> set[str]:
    if _is_node_type(target):
        return {target.__kind__}
    candidates = target if isinstance(target, tuple) else get_args(target)
    return {kind for candidate in candidates
            for kind in _target_kinds(candidate)}


def _resolve_node_target(target: Any, node: tree_sitter.Node) -> Any:
    if _is_node_type(target):
        return target.from_node(node) if target.__kind__ == node.type \
            else _UNRESOLVED
    candidates = target if isinstance(target, tuple) else get_args(target)
    for candidate in candidates:
        value = _resolve_node_target(candidate, node)
        if value is not _UNRESOLVED:
            return value
    return _UNRESOLVED


class NodeMeta(ModelMetaclass):
    """Build node metadata, checks, and a resolver at class creation."""

    def __new__(mcls, name, bases, namespace, **kwargs):
        if "__kind__" not in namespace:
            authoring_base = any(
                getattr(base, "__node_meta_hook__", None) is not None
                for base in bases)
            inherited_kind = next(
                (getattr(base, "__kind__", None) for base in bases
                 if getattr(base, "__kind__", None) not in (None, "node")),
                None)
            namespace["__kind__"] = (
                _snake(name) if authoring_base else inherited_kind or _snake(name))
        cls = cast(Any, super().__new__(mcls, name, bases, namespace, **kwargs))
        hook = getattr(cls, "__node_meta_hook__", None)
        if hook is not None:
            hook(cls)
        cls.__children__ = _children_for(cls, namespace)
        _check_against_schema(cls)
        cls.__resolver__ = _build_resolver(cls)
        return cls

    @staticmethod
    def rebuild(node_cls: type[Node],
                namespace: dict[str, Any] | None = None) -> None:
        """Resolve generated forward annotations after a module is complete."""
        if namespace is None:
            module = sys.modules.get(node_cls.__module__)
            namespace = vars(module) if module is not None else None
        node_cls.model_rebuild(_types_namespace=namespace, force=True)
        node_cls.__children__ = _children_for(node_cls, namespace)
        _check_against_schema(node_cls)
        node_cls.__resolver__ = _build_resolver(node_cls)


class Node(BaseModel, metaclass=NodeMeta):
    """One typed tree-sitter node."""

    __kind__: ClassVar[str]
    __schema__: ClassVar[NodeSchema | None] = None
    __under__: ClassVar[tuple[Any, ...] | None] = None
    __children__: ClassVar[tuple[Child, ...]] = ()
    __resolver__: ClassVar[Any]
    _node: tree_sitter.Node = PrivateAttr()
    _span: Span = PrivateAttr()
    _lazy_fields: dict[str, _LazyField] = PrivateAttr(default_factory=dict)

    @property
    def span(self) -> Span:
        return self._span

    def __value__(self) -> str:
        return (self._node.text or b"").decode("utf-8", "replace")

    @classmethod
    def value_type(cls):
        """Return the declared return type of the class's value codec."""
        return _value_type(cls)

    @classmethod
    def resolver(cls):
        return cls.__resolver__

    @classmethod
    def from_node(cls, node: tree_sitter.Node):
        kwargs, lazy_fields = cls.__resolver__(node, _lazy=True)
        for name, lazy in lazy_fields.items():
            kwargs[name] = lazy.placeholder()
        obj = cls.model_validate(kwargs)
        for name in lazy_fields:
            obj.__dict__.pop(name, None)
        obj._lazy_fields = lazy_fields
        obj._node = node
        obj._span = Span.from_node(node)
        return obj

    def _resolve_lazy_fields(self) -> None:
        for name in tuple(self._lazy_fields):
            getattr(self, name)
        for name in type(self).model_fields:
            if name in self.__dict__:
                value = self.__dict__[name]
                if isinstance(value, Node):
                    value._resolve_lazy_fields()
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        if isinstance(item, Node):
                            item._resolve_lazy_fields()
                elif isinstance(value, dict):
                    for item in value.values():
                        if isinstance(item, Node):
                            item._resolve_lazy_fields()

    def __getattribute__(self, name: str):
        try:
            private = object.__getattribute__(self, "__pydantic_private__")
        except AttributeError:
            private = None
        lazy_fields: dict[str, _LazyField] | None = (
            cast(dict[str, _LazyField], private.get("_lazy_fields"))
            if isinstance(private, dict) else None)
        if lazy_fields is not None:
            lazy = lazy_fields.get(name)
            if lazy is not None:
                value = lazy.resolve()
                object.__getattribute__(self, "__dict__")[name] = value
                lazy_fields.pop(name, None)
                object.__getattribute__(self, "__pydantic_fields_set__").add(
                    name)
                return value
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        try:
            private = object.__getattribute__(self, "__pydantic_private__")
        except AttributeError:
            private = None
        lazy_fields = (private.get("_lazy_fields")
                       if isinstance(private, dict) else None)
        if lazy_fields is not None:
            lazy_fields.pop(name, None)
        super().__setattr__(name, value)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self._resolve_lazy_fields()
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:
        self._resolve_lazy_fields()
        return super().model_dump_json(*args, **kwargs)
