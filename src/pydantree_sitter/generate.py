"""Generate and materialize the schema-backed typed node universe."""

from __future__ import annotations

import argparse
import keyword
import operator
import pprint
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .schema import NodeSchema, NodeTypeRef

__all__ = ["ClassSpec", "build_namespace", "class_name", "generate_module"]


_NUMERIC_NAME = re.compile(r"(number|numeric|integer|int|real|decimal|count)\b",
                           re.IGNORECASE)
_FLOAT_NAME = re.compile(r"(float|double|real|decimal|number)", re.IGNORECASE)
_BOOL_NAME = re.compile(r"(true|false|boolean|bool)\b", re.IGNORECASE)
_NULL_NAME = re.compile(r"^(null|none|nil|undefined)$", re.IGNORECASE)


_ATTR_SHADOWS = {"node", "text", "span", "kind", "children", "type"}


def _attr_name(field: str) -> str:
    out = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in field)
    return f"field_{out}" if out in _ATTR_SHADOWS else out


def class_name(kind: str) -> str:
    parts = [part for part in kind.split("_") if part]
    result = "".join(part[0].upper() + part[1:] for part in parts) or "Node"
    return f"{result}_" if keyword.iskeyword(result) or result in {
        "True", "False", "None"} else result


@dataclass(frozen=True)
class ClassSpec:
    kind: str
    class_name: str
    bases: tuple[str, ...]
    children: tuple[tuple[str, str], ...]
    is_supertype: bool
    subtypes: tuple[str, ...]


def _ref_name(ref: NodeTypeRef, names: dict[str, str]) -> str:
    if not ref.named:
        return f"_Literal[{ref.type!r}]"
    return names.get(ref.type, class_name(ref.type))


def _union(names: list[str]) -> str:
    names = list(dict.fromkeys(name for name in names if name))
    return names[0] if len(names) == 1 else " | ".join(names or ["Any"])


def _annotation(info, names: dict[str, str]) -> str:
    value = _union([_ref_name(ref, names) for ref in info.types])
    if info.multiple:
        return f"list[{value}]"
    if not info.required:
        return f"{value} | None"
    return value


def _class_specs(schema: NodeSchema) -> tuple[ClassSpec, ...]:
    supertype_kinds = {item.type for item in schema.node_types
                       if item.subtypes is not None}
    names: dict[str, str] = {}
    used: set[str] = {"Node"}
    for item in schema.to_list():
        if not item.named:
            continue
        base = class_name(item.type)
        candidate = base
        while candidate in used:
            candidate += "_"
        names[item.type] = candidate
        used.add(candidate)

    # The CLI can emit a named alias in a field type without giving that alias
    # a top-level node-types entry. The ABI still exposes the alias as a node
    # kind, so generate a leaf class for it. This keeps the schema faithful
    # while allowing the generated annotation namespace to resolve.
    referenced = {
        ref.type
        for item in schema.node_types
        for ref in [
            *(ref for info in (item.fields or {}).values() for ref in info.types),
            *(item.children.types if item.children is not None else ()),
            *(item.subtypes or ()),
        ]
        if ref.named
    }
    for kind in sorted(referenced - names.keys()):
        candidate = class_name(kind)
        while candidate in used:
            candidate += "_"
        names[kind] = candidate
        used.add(candidate)

    specs: list[ClassSpec] = []
    for item in schema.to_list():
        if not item.named:
            continue
        is_supertype = item.type in supertype_kinds
        children: list[tuple[str, str]] = []
        if not is_supertype:
            for name, info in sorted((item.fields or {}).items()):
                children.append((name, _annotation(info, names)))
            if item.children is not None and item.children.types:
                children.append(("content", _annotation(item.children, names)))
        specs.append(ClassSpec(
            item.type,
            names[item.type],
            ("Node",) if not is_supertype else (),
            tuple(children),
            is_supertype,
            tuple(ref.type for ref in (item.subtypes or ())),
        ))
    declared = {item.type for item in schema.node_types}
    specs.extend(
        ClassSpec(kind, names[kind], ("Node",), (), False, ())
        for kind in sorted(names.keys() - declared)
    )
    return tuple(specs)


def _alias_order(specs: tuple[ClassSpec, ...]) -> list[tuple[str, str]]:
    names = {spec.kind: spec.class_name for spec in specs}
    aliases = {
        spec.kind: (spec.class_name,
                    _union([names[kind] for kind in spec.subtypes
                            if kind in names]))
        for spec in specs if spec.is_supertype
    }
    names = {name for name, _ in aliases.values()}
    deps = {
        kind: {name for name in rhs.replace("|", " ").split()
               if name in names and name != alias}
        for kind, (alias, rhs) in aliases.items()
    }
    ordered: list[tuple[str, str]] = []
    emitted: set[str] = set()
    while len(ordered) < len(aliases):
        ready = sorted(kind for kind, (alias, _rhs) in aliases.items()
                       if alias not in emitted and deps[kind] <= emitted)
        if not ready:
            unresolved = sorted(name for name in names if name not in emitted)
            raise ValueError(
                "cannot generate typed API: cyclic or undefined supertype "
                f"dependency among {unresolved}")
        for kind in ready:
            alias, rhs = aliases[kind]
            ordered.append((alias, rhs))
            emitted.add(alias)
    return ordered


def _schema_data(schema: NodeSchema) -> list[dict[str, Any]]:
    return [item.model_dump(exclude_none=True) for item in schema.to_list()]


def generate_module(schema: NodeSchema, *, language_import: str = "",
                    fingerprint: tuple = (), codecs: str | None = None) -> str:
    """Render a runnable module from a node schema."""
    specs = _class_specs(schema)
    annotations = [annotation for spec in specs for _, annotation in spec.children]
    typing_imports = []
    if any("Any" in annotation for annotation in annotations):
        typing_imports.append("Any")
    if any("_Literal" in annotation for annotation in annotations):
        typing_imports.append("Literal as _Literal")
    typing_line = (
        f"from typing import {', '.join(typing_imports)}"
        if typing_imports else None)
    lines = [
        '"""Generated typed nodes; edit the schema or generator, not this file."""',
        "from __future__ import annotations",
        "",
        "from pydantree_sitter import Grammar, Node",
        "from pydantree_sitter.nodes import NodeMeta",
        "from pydantree_sitter.schema import NodeSchema",
        "",
        f"__schema__ = NodeSchema.from_list({pprint.pformat(_schema_data(schema), width=88)!s})",
        f"__fingerprint__ = {pprint.pformat(tuple(fingerprint), width=88)}",
        "",
    ]
    if typing_line:
        lines[3:3] = [typing_line, ""]
    if codecs:
        lines.extend([
            f"from {codecs} import *  # codec overrides",
            "",
            "class _NoCodec:",
            "    ...",
            "",
            "def _codec_base(name):",
            "    return globals().get(name, _NoCodec)",
            "",
        ])
    for spec in specs:
        if spec.is_supertype:
            continue
        bases = ", ".join(spec.bases)
        if codecs:
            bases = f'_codec_base({spec.class_name!r}), {bases}'
        lines.append(f"class {spec.class_name}({bases}):")
        lines.append(f"    __kind__ = {spec.kind!r}")
        # Forward references (including recursive kinds) are resolved after
        # every class and supertype alias exists below.
        lines.append("    __schema__ = None")
        if spec.children:
            for name, annotation in spec.children:
                default = " = None" if annotation.endswith(" | None") else ""
                lines.append(f"    {name}: {annotation}{default}")
        lines.append("")
    for alias, rhs in _alias_order(specs):
        lines.append(f"{alias} = {rhs}")
        lines.append("")
    lines.append("KIND_MAP = {")
    for spec in specs:
        if not spec.is_supertype:
            lines.append(f"    {spec.kind!r}: {spec.class_name},")
    lines.append("}")
    lines.append("")
    lines.append("for _node_class in KIND_MAP.values():")
    lines.append("    _node_class.__schema__ = __schema__")
    lines.append("    NodeMeta.rebuild(_node_class, globals())")
    lines.append("")
    lines.append(
        f"grammar = Grammar._from_generated(__name__, {language_import!r}, "
        "__fingerprint__)")
    return "\n".join(lines) + "\n"


def suggest_codecs(schema: NodeSchema) -> None:
    """Print reviewable ``__value__`` stubs; write nothing and return None."""
    for kind in sorted(schema.named_kinds()):
        info = schema.get(kind)
        if info is None or schema.is_supertype(kind):
            continue
        cls = class_name(kind)
        if _BOOL_NAME.search(kind):
            value_type = "bool"
        elif _NUMERIC_NAME.search(kind):
            value_type = "int"
        elif _FLOAT_NAME.search(kind):
            value_type = "float"
        elif _NULL_NAME.match(kind):
            value_type = "None"
        elif info.fields or (info.children is not None and info.children.types):
            continue
        else:
            value_type = "str"
        print(f"class {cls}Codec:")
        print(f"    def __value__(self) -> {value_type}:")
        print("        ...")
        print()


def build_namespace(schema: NodeSchema, language=None) -> SimpleNamespace:
    """Build the same node classes as ``generate_module`` in memory."""
    from .nodes import Node, NodeMeta

    specs = _class_specs(schema)
    namespace: dict[str, Any] = {"Node": Node, "__schema__": schema,
                                 "Any": Any}
    for spec in specs:
        if spec.is_supertype:
            continue
        annotations = {name: annotation for name, annotation in spec.children}
        defaults = {}
        info = schema.get(spec.kind)
        for name, _annotation_text in spec.children:
            entry = (info.fields or {}).get(name) if info is not None else None
            if name == "content" and info is not None:
                entry = info.children
            if entry is not None and not entry.required:
                defaults[name] = None
        namespace[spec.class_name] = NodeMeta(
            spec.class_name,
            (Node,),
            {"__module__": __name__, "__kind__": spec.kind,
             "__schema__": None, "__annotations__": annotations,
             **defaults},
        )
    by_alias = {spec.class_name: spec for spec in specs if spec.is_supertype}
    for alias, _rhs in _alias_order(specs):
        spec = by_alias[alias]
        values = [namespace[next(item.class_name for item in specs
                                 if item.kind == kind)]
                  for kind in spec.subtypes
                  if any(item.kind == kind for item in specs)]
        namespace[spec.class_name] = (
            values[0] if len(values) == 1 else
            __import__("functools").reduce(operator.or_, values))
    namespace["_Literal"] = __import__("typing").Literal
    kind_map = {spec.kind: namespace[spec.class_name] for spec in specs
                if not spec.is_supertype}
    namespace["KIND_MAP"] = kind_map
    for node_class in kind_map.values():
        node_class.__schema__ = schema
        node_class.__annotations__ = {
            name: eval(annotation, namespace, namespace)
            for name, annotation in next(
                spec.children for spec in specs
                if spec.class_name == node_class.__name__)
        }
        NodeMeta.rebuild(node_class, namespace)
    return SimpleNamespace(**namespace)


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--language", default="")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--codecs")
    parser.add_argument("--suggest-codecs", action="store_true")
    args = parser.parse_args()
    schema = NodeSchema.from_node_types_json(args.schema,
                                              name=args.language.rsplit(".", 1)[-1])
    if args.suggest_codecs:
        suggest_codecs(schema)
        return
    if args.out is None:
        parser.error("--out is required unless --suggest-codecs is used")
    fingerprint = ()
    if args.language:
        from .grammar import _fingerprint, _language

        language = _language(args.language)
        if language is not None:
            fingerprint = _fingerprint(language)
    args.out.write_text(generate_module(schema, language_import=args.language,
                                        fingerprint=fingerprint,
                                        codecs=args.codecs))


if __name__ == "__main__":
    _main()
