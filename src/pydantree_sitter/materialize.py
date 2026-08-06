"""pydantree_sitter.materialize — the ONE kwargs builder (014 §4.5).

Everything that turns captures into a model row lives here: `Span`,
`_unescape_json_string`, `build_kwargs` (the single kwargs builder),
`MatchFailure`, and the extract loops (field + record, both calling the ONE
matcher in match.py before grouping). Legacy public stacks (the second
OutputModel / capture / materialize_matches / extract_records / Diagnostic
surfaces) are deleted.

Nested record fields materialize through the SAME compiler: the binding
compiles a sub-extractor at bind time (binding.py), and the value node runs
through it — there is no schema-less/schema-bound interleaving left to get
wrong (F-A2). Nested models in FIELD mode are rejected at class creation
(spec.py) — documented TODO.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any, Optional, get_args, get_origin

import tree_sitter
from pydantic import ValidationError

from .emit import Cursor
from .errors import (
    AmbiguousCaptureError,
    raise_ambiguous_capture,
    ExtractionError,
)
from .markers import ANCHOR, RECORD_CAP, _MARKERS, _MISSING
from .markers import _Derived as _D
from .match import group_matches, match_ancestor_path, merge_group
from .spec import is_optional, unwrap_optional

# MatchFailure is defined here (materialize owns per-match diagnostics);
# ExtractionError (errors.py) carries a list of them.


class Span:
    """A source span (line/column, 1-based lines)."""

    __slots__ = ("line", "column", "end_line", "end_column",
                 "start_byte", "end_byte", "text")

    def __init__(self, line, column, end_line, end_column,
                 start_byte, end_byte, text):
        self.line = line
        self.column = column
        self.end_line = end_line
        self.end_column = end_column
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.text = text

    @classmethod
    def from_node(cls, node: tree_sitter.Node) -> "Span":
        # `Point` is a tuple — unpack it, never read `.row` / `.column`.
        #
        # tree-sitter 0.26.0 reworked Point into a tuple subclass whose
        # `.row` / `.column` getters return a BORROWED reference instead of a
        # new one. Every read of a non-immortal int (any value above 256,
        # CPython's small-int cache bound) leaves the int one refcount short,
        # so it is freed while the Point still owns it — allocator corruption
        # that detonates later in an unrelated allocation (SIGSEGV/SIGBUS/
        # SIGABRT, or a hang). Reading 246 such values is enough.
        # Upstream: tree-sitter/py-tree-sitter#472, fixed by #466 (merged
        # 2026-07-08) but NOT in any release as of 0.26.0.
        #
        # Tuple access goes through PyTuple_GET_ITEM, which is correct, and
        # yields identical values on 0.25.x, 0.26.0 and the fixed build — so
        # this needs no version pin and can stay after 0.26.1 ships.
        r = node.range
        start_row, start_column = r.start_point
        end_row, end_column = r.end_point
        text = node.text.decode("utf-8", "replace") if node.text else ""
        return cls(start_row + 1, start_column,
                   end_row + 1, end_column,
                   r.start_byte, r.end_byte, text)

    def __repr__(self) -> str:  # pragma: no cover
        return (f"Span({self.line}:{self.column}-"
                f"{self.end_line}:{self.end_column} {self.text!r})")


def _unescape_json_string(text: str) -> str:
    """Decode a grammar string literal's content (JSON escape syntax first:
    \\n \\t \\" \\\\ \\uXXXX). Accepts either the string WRAPPER's full text
    (with quotes) or the bare content. Falls back to a manual decode when
    the strict JSON round-trip fails (a grammar lenient about raw newlines)."""
    import json as _json
    try:
        if text.startswith('"') and text.endswith('"') and len(text) >= 2:
            return _json.loads(text)
        return _json.loads('"' + text + '"')
    except ValueError:
        pass
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        text = text[1:-1]
    out: list[str] = []
    i = 0
    mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"',
               "\\": "\\", "b": "\b", "f": "\f", "/": "/"}
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
                continue
            if nxt == "u" and i + 5 <= len(text):
                try:
                    out.append(chr(int(text[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            out.append(text[i])
            i += 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


@dataclass
class MatchFailure:
    """One failed match: pattern index, anchor node, Span, snippet, and the
    structured pydantic errors when the failure was a validation error."""

    pattern: int
    anchor: Any
    span: Optional["Span"]
    snippet: str
    detail: str
    pydantic_errors: Optional[list] = None


def _text_of(n) -> str:
    b = n.text
    return "" if b is None else b.decode("utf-8")


def _first_anchor(caps: dict):
    return (caps.get(ANCHOR) or caps.get(RECORD_CAP) or [None])[0]


def _failure(match, detail: str, *, anchor=None,
             pydantic_errors=None) -> MatchFailure:
    node = anchor
    if node is None and match is not None:
        ns = match.nodes(ANCHOR) or match.nodes(RECORD_CAP)
        node = ns[0] if ns else None
    span = Span.from_node(node) if node is not None else None
    snippet = span.text if span is not None else ""
    return MatchFailure(pattern=getattr(match, "pi", 0), anchor=node,
                        span=span, snippet=snippet, detail=detail,
                        pydantic_errors=pydantic_errors)


# ---------------------------------------------------------------------------
# build_kwargs — the ONE kwargs builder
# ---------------------------------------------------------------------------

def build_kwargs(model_cls, bindings, caps: dict) -> dict:
    """Build one model's kwargs from a merged capture dict. Coercion goes
    through pydantic (the model constructor is the coercion layer); this
    only picks text/list/meta values."""
    kwargs: dict = {}
    for fname, f in model_cls.model_fields.items():
        b = _binding_for(bindings, fname)
        if b is None:
            # derived() field: excluded from the query — its constant value
            # applies (derived(value)); bare derived() stays absent
            if isinstance(f.default, _D) and f.default.default is not _MISSING:
                kwargs[fname] = f.default.default
            continue
        if b.is_meta:
            n = caps.get(b.capture_name)
            node = n[0] if n else None
            if node is not None:
                if unwrap_optional(f.annotation) is int:
                    # REVIEW 020 minor: `int | None` source_meta() used to
                    # fall into the Span branch (annotation is not exactly
                    # `int`) and fail validation.
                    # tuple access, not `.row` — see Span.from_node
                    kwargs[fname] = node.start_point[0] + 1
                else:
                    kwargs[fname] = Span.from_node(node)
            continue
        nodes = caps.get(b.capture_name, [])
        if b.nested is not None:
            # values are already materialized OutputModel instances (the
            # record recursion built them)
            if not nodes:
                if b.is_list:
                    kwargs[fname] = []
                elif not f.is_required():
                    kwargs[fname] = f.default
                continue
            kwargs[fname] = nodes if b.is_list else nodes[0]
            continue
        if not nodes:
            if b.is_list:
                kwargs[fname] = []
            elif not f.is_required():
                kwargs[fname] = None if _is_marker_default(f) else f.default
            elif _is_optional(f.annotation):
                kwargs[fname] = None
            continue
        if b.is_list:
            if b.unescape:
                kwargs[fname] = [_unescape_json_string(_text_of(n))
                                 for n in nodes]
            else:
                kwargs[fname] = [_text_of(n) for n in nodes]
        else:
            if len(nodes) > 1:
                raise_ambiguous_capture(fname, b.capture_name, len(nodes))
            text = _text_of(nodes[0])
            kwargs[fname] = _unescape_json_string(text) if b.unescape else text
    return kwargs


def _binding_for(bindings, fname):
    for b in bindings:
        if b.name == fname:
            return b
    return None


def _is_marker_default(f) -> bool:
    return isinstance(f.default, _MARKERS)


def _is_optional(t) -> bool:
    return is_optional(t)


# ---------------------------------------------------------------------------
# the extract loops (the ONE matcher call site, before grouping)
# ---------------------------------------------------------------------------

def extract_field(model_cls, compiled, tree: tree_sitter.Tree, *,
                  strict: bool) -> list:

    q = compiled.query.compile(tree.language)
    matches = Cursor(q, compiled.quant_maps, tree).matches()
    # ONE call site for the ancestor matcher: before grouping, so scalar and
    # list branches share it (the NEW list-branch skip dies by construction)
    if compiled.match_path is not None:
        matches = [m for m in matches
                   if _anchor_of(m) is not None and
                   match_ancestor_path(_anchor_of(m), compiled.match_path)]
    results, errors = [], []
    if compiled.spec.raw_query is not None:
        # a raw query has no emitted anchor: ONE row per match; source_meta()
        # falls back to the first capture's node as the anchor (A8: the
        # query's DECLARED capture order, not dict insertion order)
        for m in matches:
            caps = dict(m.caps)
            if "__anchor__" not in caps:
                for ci in range(q.capture_count):
                    name = q.capture_name(ci)
                    v = caps.get(name)
                    if v:
                        caps["__anchor__"] = [v[0]]
                        break
            try:
                results.append(model_cls(**build_kwargs(model_cls,
                                                        compiled.bindings,
                                                        caps)))
            except ValidationError as e:
                errors.append(_failure(m, f"pydantic ValidationError: {e.errors()}",
                                       pydantic_errors=e.errors()))
            except AmbiguousCaptureError as e:
                errors.append(_failure(m, str(e)))
        if errors and strict:
            raise ExtractionError(errors, model_cls)
        return results
    groups, order = group_matches(matches)
    for gid in order:
        caps = merge_group(groups[gid], compiled.bindings)
        try:
            results.append(model_cls(**build_kwargs(model_cls,
                                                    compiled.bindings, caps)))
        except ValidationError as e:
            errors.append(_failure(None,
                                   f"pydantic ValidationError: {e.errors()}",
                                   anchor=_first_anchor(caps),
                                   pydantic_errors=e.errors()))
        except AmbiguousCaptureError as e:
            errors.append(_failure(None, str(e), anchor=_first_anchor(caps)))
    if errors and strict:
        raise ExtractionError(errors, model_cls)
    return results


def _anchor_of(match):
    ns = match.nodes(ANCHOR)
    return ns[0] if ns else None


def extract_record(model_cls, compiled, tree: tree_sitter.Tree, *,
                   strict: bool, scoped_to: Any = None) -> list:
    """Record mode: outer query finds record nodes; inner query (one
    anchored pattern per field) fills them; nested bindings recurse through
    their OWN compiled sub-extractor (F-A2: one compiler, no interleaving).
    `scoped_to` restricts the outer query to a subtree (nested models)."""

    rec_q = compiled.records.compile(tree.language)
    results, errors = [], []
    if scoped_to is not None:
        outer = Cursor(rec_q, compiled.records_quant_maps, tree) \
            .matches_on(scoped_to)
    else:
        outer = Cursor(rec_q, compiled.records_quant_maps, tree).matches()
    for rm in outer:
        recs = rm.nodes(RECORD_CAP)
        if not recs:
            continue
        rec = recs[0]
        if compiled.match_path is not None and \
                not match_ancestor_path(rec, compiled.match_path):
            continue
        kwargs = _record_kwargs(model_cls, compiled, rec, tree)
        if kwargs is None:
            continue
        try:
            results.append(model_cls(**kwargs))
        except ValidationError as e:
            errors.append(_failure(rm, f"pydantic ValidationError: {e.errors()}",
                                   anchor=rec, pydantic_errors=e.errors()))
        except AmbiguousCaptureError as e:
            errors.append(_failure(rm, str(e), anchor=rec))
    if errors and strict:
        raise ExtractionError(errors, model_cls)
    return results


def _record_kwargs(model_cls, compiled, rec, tree):
    """Merge a record node's field captures into model kwargs (incl. nested).

    The inner query's patterns are anchored (each captures @__anchor__ on the
    record node), so only matches anchored at `rec` itself contribute —
    pairs inside NESTED record nodes are dropped (the spike-a §3 fix,
    preserved). Nested bindings run their own compiled sub-extractor over
    the value node.
    """

    fld_q = compiled.fields.compile(tree.language)
    merged: dict[str, list] = {}
    for fm in Cursor(fld_q, compiled.fields_quant_maps, tree).matches_on(rec):
        anc = fm.nodes(ANCHOR)
        if not anc or anc[0].id != rec.id:
            continue  # a nested record's pair — not a record-level key
        for cname in set(fm.caps):
            if cname == ANCHOR:
                continue
            merged.setdefault(cname, []).extend(fm.nodes(cname))
    # record-level predicate semantics: a REQUIRED predicate field that did
    # not match (absent) filters the WHOLE record (the row is invalid, like
    # the field-mode query engine); an OPTIONAL one just stays absent (None)
    # — the old check dropped optional predicate fields' records too
    # (REVIEW 020 minor: optional-field-with-predicate lost the record).
    filtered = any(
        b.has_predicate and not b.optional and not merged.get(b.capture_name)
        for b in compiled.bindings)
    if filtered:
        return None
    merged.setdefault(ANCHOR, [rec])
    # nested OutputModel fields: materialize the value node with the nested
    # model's OWN compiled sub-extractor (the F-A2 fix — one compiler)
    for b in compiled.bindings:
        if b.nested is None:
            continue
        nodes = merged.get(b.capture_name, [])
        sub = compiled.nested_extractors.get(b.name)
        out = []
        for n in nodes:
            if sub is None:
                continue
            rows = sub.extract_tree_scoped(n, tree)
            if b.is_list:
                out.extend(rows)
            elif rows:
                out.append(rows[0])
        if not out and not b.is_list and b.optional:
            merged[b.key] = []
            continue
        merged[b.key] = out
    return build_kwargs(model_cls, compiled.bindings, merged)

