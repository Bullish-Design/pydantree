"""tsquery.stubs — Job 2: typed node accessors generated from the node-schema.

The schema's per-kind children/fields are the source of a typed accessor
surface (CONCEPT §7.2, Phase 4 "worth it after distribution"). For every
named kind the generator emits a class with:

  * one field accessor per CST field — `def name(self) -> Identifier | None`
    (a repeated field is `-> list[Type]`);
  * a `get(field)` overload per field — the `node.get("name")` surface;
  * a `children(kind)` overload per possible child kind — the
    `node.get("statement") -> list[Statement]` surface.

Supertypes are emitted as type aliases over their subtypes (a real node is
always a concrete kind; `_type` never exists in the CST), and anonymous
token kinds map to `Node`, so every name in the stub resolves against the
schema. The stub is a typing VIEW, not the runtime: the consumer casts a
tree_sitter.Node to the kind class (`cast(function_item, node)`) and the
accessors type-check (verified with mypy in tests/test_stubs.py).
"""

from __future__ import annotations

from pathlib import Path

from tscore.schema import NodeSchema, NodeTypeRef


def _py_name(kind: str) -> str:
    """A valid Python identifier for a node kind."""
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in kind)


def _ref_name(r: NodeTypeRef) -> str:
    # anonymous token kinds have no class — a real node is always a Node
    return "Node" if not r.named else _py_name(r.type)


def _union(names: list[str], *, optional: bool) -> str:
    names = [n for n in dict.fromkeys(names) if n]
    if not names:
        return "object"
    if optional:
        names.append("None")
    if len(names) == 1:
        return names[0]
    return " | ".join(names)


def _emit_method(lines: list[str], name: str, ret: str, is_overload: bool) -> None:
    if is_overload:
        lines.append("    @overload")
    lines.append(f"    def {name}(self) -> {ret}: ...")


def generate_stubs(schema: NodeSchema, *, lang_name: str | None = None,
                   out: Path | str | None = None) -> str:
    """Generate the typed-accessor `.pyi` for `schema`. Returns the stub text;
    writes it to `out` (a `.pyi` path) when given — the 'shipped beside the
    schema' surface (Phase-4 Job 2, landed Phase 6)."""
    supertype_kinds = {t.type for t in schema.node_types if t.subtypes}
    named = sorted((t for t in schema.node_types if t.named),
                   key=lambda t: t.type)

    lines: list[str] = []
    lines.append(f"# Typed node accessors for "
                 f"{lang_name or schema.name or '<grammar>'} — generated from "
                 f"the node-schema (tsquery.stubs).")
    lines.append("from __future__ import annotations")
    lines.append("from typing import Literal, overload")
    lines.append("")
    lines.append("class Node:")
    lines.append("    type: str")
    lines.append("    ...")
    lines.append("")

    # supertype aliases first (fields/children reference them by name); a
    # supertype kind is ONLY an alias — no class (the node never exists)
    for t in named:
        if t.type in supertype_kinds:
            subs = sorted(dict.fromkeys(_ref_name(s) for s in t.subtypes))
            if subs:
                lines.append(f"{_py_name(t.type)} = "
                             f"{_union(subs, optional=False)}")
                lines.append("")

    # per-kind classes
    for t in named:
        if t.type in supertype_kinds:
            continue
        cls = _py_name(t.type)
        fields = t.fields or {}
        children = list((t.children.types if t.children else []))
        # names that would shadow a referenced type (a field named like a
        # kind, e.g. associated_type.type_parameters) get a `field_` prefix
        referenced = {_ref_name(r) for fi in fields.values() for r in fi.types}
        referenced |= {_ref_name(c) for c in children}
        referenced.add(cls)
        # names the class surface already owns (Node's attrs + the accessor
        # methods) also shadow referenced types
        referenced |= {"type", "get", "children"}

        def mname(fname: str) -> str:
            pn = _py_name(fname)
            return f"field_{pn}" if pn in referenced else pn

        lines.append(f"class {cls}(Node):")
        lines.append(f"    \"\"\"kind {t.type!r}.\"\"\"")
        field_specs = []
        for fname in sorted(fields):
            fi = fields[fname]
            types = sorted(dict.fromkeys(_ref_name(r) for r in fi.types))
            if not types:
                continue
            ret = (f"list[{_union(types, optional=False)}]"
                   if fi.multiple else _union(types, optional=True))
            field_specs.append((mname(fname), fname, ret))
        child_specs = []
        for c in sorted(set((c.type, c.named) for c in children)):
            child_kind, named_child = c
            cname = _ref_name(NodeTypeRef(type=child_kind, named=named_child))
            child_specs.append((child_kind, cname))

        # field accessors: a plain def per field (a single field needs no
        # overload machinery)
        for meth, _f, ret in field_specs:
            lines.append(f"    def {meth}(self) -> {ret}: ...")
        # the get(field) surface: overloads when several fields, else a def
        if field_specs:
            multi = len(field_specs) > 1
            for _meth, fname, ret in field_specs:
                _emit_method(lines, "get", ret, multi)
                lines[-1] = lines[-1].replace(
                    f"def get(self) -> {ret}",
                    f"def get(self, field: Literal[{fname!r}]) -> {ret}")
        # the children(kind) surface: overloads when several kinds, else a def
        if child_specs:
            multi = len(child_specs) > 1
            for child_kind, cname in child_specs:
                _emit_method(lines, "children", f"list[{cname}]", multi)
                lines[-1] = lines[-1].replace(
                    "def children(self)",
                    f"def children(self, kind: Literal[{child_kind!r}])")
        if not field_specs and not child_specs:
            lines.append("    ...")
        lines.append("")

    text = "\n".join(lines)
    if out is not None:
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return text
