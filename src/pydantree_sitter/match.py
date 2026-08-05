"""pydantree_sitter.match — the ONE ancestor-path matcher + anchor merge (014 §4.3).

`match_ancestor_path(node, path)` is a single BACKTRACKING matcher over the
M() path's prefix (the steps before the anchor), applied uniformly to every
match loop (scalar and list branches share it — the NEW list-branch skip bug
is fixed by construction). It is called from EXACTLY ONE place: the match
loop, before grouping.

Property-tested (hypothesis) against a brute-force reference matcher.

The anchor grouping/merge (the old `_extract_field` list branch) lives here
too, applied after filtering: one merged capture dict per anchor node.
"""

from __future__ import annotations

from .errors import raise_ambiguous_capture
from .markers import ANCHOR, GAP
from .spec import PathStep


def match_ancestor_path(node, path: tuple) -> bool:
    """Does the anchor's ancestor chain satisfy the M() path?

    `path` is the full `MatchSpec.path` (PathStep | GAP tuples); the anchor
    is the LAST step (guaranteed by the query). The PREFIX steps are matched
    against the anchor's ancestors, bottom-up (the step nearest the anchor
    first), with backtracking across gaps (F-A12): a gap absorbs any number
    of ancestors, and when several assignments are possible, the matcher
    tries them all (the greedy right-to-left version fails e.g. on
    M("a", ..., "a") over an a→b→a chain — the far `a` satisfies the path).
    """
    if len(path) == 1:
        return True
    steps = tuple(reversed(path[:-1]))   # from the anchor upward
    parent = node.parent
    if parent is None:
        # no ancestors: the prefix must be all gaps (consumed with zero)
        return all(s is GAP for s in steps)
    return _match_steps(parent, steps, 0)


def _match_steps(node, steps: tuple, i: int) -> bool:
    """Match `steps[i:]` against `node` and its ancestors (backtracking)."""
    if i >= len(steps):
        return True
    step = steps[i]
    if step is GAP:
        # the gap absorbs zero ancestors (the next step matches `node`
        # itself) or one at a time — try both orders
        if _match_steps(node, steps, i + 1):
            return True
        parent = node.parent
        if parent is not None:
            return _match_steps(parent, steps, i)
        return False
    if isinstance(step, PathStep) and node.type in step.kinds:
        parent = node.parent
        if parent is None:
            # the remaining steps must be gaps (consumable with zero
            # ancestors) — the path needn't reach the root
            return all(s is GAP for s in steps[i + 1:])
        return _match_steps(parent, steps, i + 1)
    return False


# ---------------------------------------------------------------------------
# anchor grouping / merge (the ONE place captures become rows)
# ---------------------------------------------------------------------------

def group_matches(matches: list, anchor_cap: str = ANCHOR):
    """Group matches by their anchor node id, preserving first-seen order.

    Returns (groups, order): groups[id] = [capture dicts sharing the anchor].
    Matches with no anchor share the synthetic id 0 (the emitter always
    captures the anchor, so this is a defensive fallback only).
    """
    groups: dict[int, list[dict]] = {}
    order: list[int] = []
    for m in matches:
        caps = dict(m.caps)
        anc = caps.get(anchor_cap)
        if not anc:
            gid = 0
        else:
            gid = anc[0].id
        if gid not in groups:
            order.append(gid)
            groups[gid] = []
        groups[gid].append(caps)
    return groups, order


def _dedup_by_id(nodes: list) -> list:
    """Dedupe capture nodes by their stable C node id (across matches the
    bindings may hand out distinct Python wrappers for the same node)."""
    seen: set[int] = set()
    out = []
    for n in nodes:
        if n.id not in seen:
            seen.add(n.id)
            out.append(n)
    return out


def merge_group(caps_list: list[dict], bindings) -> dict:
    """Merge one anchor's capture dicts into a single capture dict:

      * list captures extend across matches;
      * scalar captures dedup by node id, and raise
        `AmbiguousCaptureError` if a scalar is still fed by more than one
        distinct node (the ONE AmbiguousCaptureError, §1.3).
    """
    merged: dict[str, list] = {}
    for caps in caps_list:
        for name, nodes in caps.items():
            merged.setdefault(name, []).extend(nodes)
    for b in bindings:
        if b.is_meta or b.is_list:
            continue
        nodes = merged.get(b.capture_name, [])
        if len(nodes) > 1:
            dedup = _dedup_by_id(nodes)
            if len(dedup) > 1:
                raise_ambiguous_capture(b.name, b.capture_name, len(dedup))
            merged[b.capture_name] = dedup
    return merged
