"""pydantree_sitter.schema — the grammar node-schema (the Phase-4 bridge artifact).

This is the shared seam between pydantree_sitter_grammar (B) and pydantree_sitter (A): a closed set
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

The refactor (D3) deleted the hand-port of node_types.rs: the
schema's ONLY source is the CLI's own node-types.json byproduct, tracked by
construction. `NodeSchema.from_node_types_json` / `derive_from_node_types`
parse that byproduct; a B-built bundle's node-schema.json IS the generate
run's node-types.json, copied byte-for-byte.
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
    """One node kind's schema entry (mirrors NodeInfoJSON).

    Phase 6: `fields` is now `None` for entries that carry no field/children
    summary in the CLI's node-types.json (lexical rules, bare alias entries,
    anonymous tokens) and a dict (possibly empty) for computed non-lexical
    rule entries — matching node_types.rs's emission exactly, so our
    serialization round-trips the CLI byproduct byte-for-byte.
    """

    type: str
    named: bool = True
    root: bool = False
    extra: bool = False
    fields: dict[str, ChildInfo] | None = None
    children: ChildInfo | None = None
    subtypes: list[NodeTypeRef] | None = None


def _emit_node_type(t: NodeTypeInfo) -> dict:
    """Serialize one entry in the CLI's exact node_types.rs emission shape:
    `type`/`named` always; `root`/`extra` only when true; `fields` only when
    the entry carries a computed field summary (None for lexical/bare);
    `children`/`subtypes` when present. Phase 6: this is what makes the
    community path (and the exact path) byte-for-byte comparable with the
    CLI's node-types.json."""
    out: dict = {"type": t.type, "named": t.named}
    if t.root:
        out["root"] = True
    if t.extra:
        out["extra"] = True
    if t.fields is not None:
        out["fields"] = {
            k: fi.model_dump(exclude_none=True) for k, fi in t.fields.items()}
    if t.children is not None:
        out["children"] = t.children.model_dump(exclude_none=True)
    if t.subtypes is not None:
        out["subtypes"] = [s.model_dump(exclude_none=True) for s in t.subtypes]
    return out


def _canonical_sorted(types: list[NodeTypeInfo]) -> list[NodeTypeInfo]:
    """The CLI's node_types.rs sort: supertypes first, then non-leaves, then
    leaves, alphabetical within each group. "Leaf" means the entry carries no
    fields AND no children (node_types.rs's `fields.is_none()`)."""
    def key(t: NodeTypeInfo):
        has_subtypes = t.subtypes is not None
        is_leaf = t.children is None and t.fields is None
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
        return json.dumps([_emit_node_type(t) for t in self.to_list()],
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
        if t is None or t.fields is None:
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
        return t is not None and t.fields is not None and field in t.fields

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
        refs = [r.type for f in (t.fields or {}).values() for r in f.types]
        refs += [r.type for r in (t.children.types if t.children else [])]
        return self.expand(refs)

    def is_possible_descent(self, parent: str, child: str) -> bool:
        return child in self.possible_children(parent)

    def is_possible_descendant(self, ancestor: str, descendant: str) -> bool:
        """Can `descendant` occur at ANY depth under `ancestor` (transitive
        closure over possible_children)? The Job-1 check for the `...` path
        element — a gap allows arbitrary depth between the kinds it
        separates."""
        if ancestor == descendant:
            return True
        frontier = set(self.possible_children(ancestor))
        seen: set[str] = set()
        while frontier:
            k = frontier.pop()
            if k in seen:
                continue
            seen.add(k)
            if k == descendant:
                return True
            frontier |= self.possible_children(k)
        return False

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
    """The (only) path: `node-types.json` (the CLI's byproduct) -> the
    canonical node-schema list. Aliases/inline are already flattened away;
    supertypes arrive as `subtypes` entries."""
    if isinstance(node_types_json, (str, Path)):
        node_types_json = json.loads(Path(node_types_json).read_text())
    if isinstance(node_types_json, dict) and "node_types" in node_types_json:
        node_types_json = node_types_json["node_types"]
    return [NodeTypeInfo.model_validate(t) for t in node_types_json]


