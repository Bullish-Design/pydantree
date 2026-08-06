"""pydantree_sitter.codegen — typed CST codegen (014 §5, D7): real runtime.

`generate_typed_api(schema, module_name)` emits a REAL module (not .pyi
fiction — the old .pyi generator is deleted): a thin `TypedNode` wrapper around a
`tree_sitter.Node`, one class per named kind with field accessors
(`child_by_field_name` + `wrap`) typed from the schema — required+single ->
`T`, optional -> `T | None`, repeated -> `list[T]` — a `children()` accessor
from the children summary, supertypes as unions over their subtypes,
`KIND_MAP` (node kind -> class), and `wrap(node)`.

Class names come from kinds via the acronym-aware snake/camel helper
(shared with the B-side rule naming, F-B4): `function_item` ->
`FunctionItem`, `_type` -> `Type`.
"""

from __future__ import annotations

from pathlib import Path

from .schema import NodeSchema, NodeTypeRef

_ATTR_SHADOWS = {"node", "text", "span", "kind", "children", "type"}


def class_name(kind: str) -> str:
    """A node kind -> a Python class name (acronym-aware camel):
    `function_item` -> `FunctionItem`, `_type` -> `Type`,
    `http_server` -> `HttpServer`."""
    parts = [p for p in kind.split("_") if p]
    if not parts:
        return "Node"
    return "".join(p[0].upper() + p[1:] for p in parts)


def _attr_name(field: str) -> str:
    out = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in field)
    return f"field_{out}" if out in _ATTR_SHADOWS else out


def _ref_name(r: NodeTypeRef) -> str:
    return "TypedNode" if not r.named else class_name(r.type)


def _union(names: list[str], *, optional: bool) -> str:
    names = [n for n in dict.fromkeys(names) if n]
    if not names:
        names = ["Node"]
    if optional:
        names.append("None")
    if len(names) == 1:
        return names[0]
    return " | ".join(names)


def generate_typed_api(schema: NodeSchema, module_name: str) -> str:
    """Generate a real typed-accessor module for `schema`. Returns the
    module source (a runnable module, not a stub)."""
    supertype_kinds = {t.type for t in schema.node_types if t.subtypes}
    named = sorted((t for t in schema.node_types if t.named),
                   key=lambda t: t.type)
    by_kind = {t.type: t for t in schema.node_types}

    L: list[str] = []
    L.append(f'"""{module_name} — typed CST accessors generated from the '
             f'node-schema (pydantree_sitter.codegen)."""')
    L.append("from __future__ import annotations")
    L.append("")
    L.append("import tree_sitter")
    L.append("")
    L.append("")
    L.append("class TypedNode:")
    L.append('    """A thin wrapper holding a tree_sitter.Node."""')
    L.append("")
    L.append("    def __init__(self, node: tree_sitter.Node) -> None:")
    L.append("        self.node = node")
    L.append("")
    L.append("    @property")
    L.append("    def kind(self) -> str:")
    L.append("        return self.node.type")
    L.append("")
    L.append("    @property")
    L.append("    def text(self) -> str:")
    L.append("        b = self.node.text")
    L.append('        return "" if b is None else b.decode("utf-8")')
    L.append("")
    L.append("    @property")
    L.append("    def line(self) -> int:")
    # tuple access, not `.row`: the 0.26.0 Point getters corrupt the heap
    # (py-tree-sitter#472). Generated code ships to users, so it must not
    # carry the bad access pattern — see materialize.Span.from_node.
    L.append("        return self.node.start_point[0] + 1")
    L.append("")
    L.append("    def children(self, kind: str | None = None) -> list[TypedNode]:")
    L.append("        out = []")
    L.append("        for c in self.node.children:")
    L.append("            if kind is None or c.type == kind:")
    L.append("                out.append(wrap(c))")
    L.append("        return out")
    L.append("")
    L.append("    def __repr__(self) -> str:  # pragma: no cover")
    L.append('        return f"<{type(self).__name__} {self.kind!r}>"')
    L.append("")

    # per-kind classes FIRST (their annotations are lazy strings thanks to
    # the future-annotations import); the supertype unions follow
    for t in named:
        if t.type in supertype_kinds:
            continue
        cls = class_name(t.type)
        fields = t.fields or {}
        L.append(f"class {cls}(TypedNode):")
        L.append(f'    """kind {t.type!r}."""')
        L.append(f"    KIND = {t.type!r}")
        L.append("")
        field_lines = []
        for fname in sorted(fields):
            fi = fields[fname]
            types = sorted(dict.fromkeys(_ref_name(r) for r in fi.types))
            if not types:
                continue
            if fi.multiple:
                ret = f"list[{_union(types, optional=False)}]"
            elif fi.required:
                ret = _union(types, optional=False)
            else:
                ret = _union(types, optional=True)
            attr = _attr_name(fname)
            field_lines.append(f"    @property")
            field_lines.append(f"    def {attr}(self) -> {ret}:")
            if fi.multiple:
                field_lines.append("        out = []")
                field_lines.append("        for i in range(len(self.node.children)):")
                field_lines.append("            c = self.node.children[i]")
                field_lines.append(
                    f'            if self.node.field_name_for_child(i) == {fname!r}:')
                field_lines.append("                out.append(wrap(c))")
                field_lines.append("        return out")
            else:
                field_lines.append(f'        c = self.node.child_by_field_name({fname!r})')
                field_lines.append("        if c is None:")
                field_lines.append("            return None")
                field_lines.append("        return wrap(c)")
            field_lines.append("")
        if not field_lines:
            field_lines.append("    ...")
            field_lines.append("")
        L.extend(field_lines)

    # supertype unions (after the classes: the union expressions evaluate
    # the class names at module import). Unions can reference OTHER unions
    # (Pattern -> LiteralPattern), so emit them dependency-first (a union's
    # referenced union names are defined before it; supertype graphs don't
    # cycle).
    union_defs: dict[str, tuple[str, str]] = {}   # kind -> (name, rhs)
    for t in named:
        if t.type in supertype_kinds:
            subs = sorted(dict.fromkeys(
                _ref_name(NodeTypeRef(type=s.type, named=s.named))
                for s in t.subtypes))
            if subs:
                union_defs[t.type] = (class_name(t.type),
                                      _union(subs, optional=False))
    # emit unions dependency-first (a union may reference another union's
    # name, e.g. Pattern -> LiteralPattern); supertype graphs don't cycle
    import re as _re
    union_names = {name for name, _rhs in union_defs.values()}
    deps = {k: {n for n in _re.findall(r"[A-Za-z_][A-Za-z0-9_]*", rhs)
                if n in union_names and n != name}
            for k, (name, rhs) in union_defs.items()}
    order: list[tuple[str, str, str]] = []
    emitted: set[str] = set()
    while len(order) < len(union_defs):
        ready = sorted(k for k, (name, rhs) in union_defs.items()
                       if name not in emitted and deps[k] <= emitted)
        if not ready:
            # unsatisfiable: a cyclic/undefined union dependency — emit the
            # rest as-is rather than looping forever (A10). A cycle is a
            # supertype-graph anomaly; the emitted union still imports.
            for k, (name, rhs) in union_defs.items():
                if name not in emitted:
                    order.append((k, name, rhs))
                    emitted.add(name)
            break
        for k in ready:
            name, rhs = union_defs[k]
            order.append((k, name, rhs))
            emitted.add(name)
    for _kind, name, rhs in order:
        L.append(f"{name} = {rhs}")
        L.append("")

    # KIND_MAP + wrap
    L.append("KIND_MAP: dict[str, type[TypedNode]] = {")
    for t in named:
        if t.type not in supertype_kinds:
            L.append(f"    {t.type!r}: {class_name(t.type)},")
    L.append("}")
    L.append("")
    L.append("")
    L.append("def wrap(node: tree_sitter.Node | None) -> TypedNode | None:")
    L.append("    \"\"\"Wrap a tree_sitter.Node in its kind class (or TypedNode).\"\"\"")
    L.append("    if node is None:")
    L.append("        return None")
    L.append("    cls = KIND_MAP.get(node.type, TypedNode)")
    L.append("    return cls(node)")
    L.append("")

    text = "\n".join(L)
    return text


def write_typed_api(schema: NodeSchema, out: Path | str, *,
                    module_name: str | None = None) -> Path:
    """Write the generated module to `out` (the bundle hook's target)."""
    out = Path(out)
    name = module_name or out.stem
    out.write_text(generate_typed_api(schema, name))
    return out
