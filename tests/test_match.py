"""match.py property tests: the ONE backtracking ancestor matcher (014 §4.3).

`match_ancestor_path` is property-tested against a brute-force reference
matcher over random paths with repeated kinds and gaps (the greedy
right-to-left version fails e.g. on M("a", ..., "a") over an a->b->a chain —
the backtracking version must find the far `a`). The reference is a
straightforward recursive search over the ancestor chain.
"""

from __future__ import annotations

import random

from pydantree_sitter.match import match_ancestor_path
from pydantree_sitter.markers import GAP
from pydantree_sitter.spec import PathStep


class _Node:
    """A minimal ancestry chain (parent pointers only)."""

    def __init__(self, kind: str, parent: "_Node | None" = None):
        self.type = kind
        self.parent = parent


def _chain(kinds: list[str]) -> _Node:
    """kinds[0] = root; the last element is the anchor."""
    root = _Node(kinds[0])
    cur = root
    for k in kinds[1:]:
        cur = _Node(k, parent=cur)
    return cur


def _brute(node, path: tuple) -> bool:
    """Reference: try EVERY way of assigning the path's prefix steps to
    ancestors (the anchor is path[-1]; the prefix must appear bottom-up in
    order; gaps absorb any number of ancestors)."""
    steps = list(reversed(path[:-1]))  # from the anchor upward
    ancestors = []
    n = node.parent
    while n is not None:
        ancestors.append(n)
        n = n.parent

    def rec(ai: int, si: int) -> bool:
        if si >= len(steps):
            return True
        step = steps[si]
        if step is GAP:
            # zero ancestors consumed, or one at a time
            if rec(ai, si + 1):
                return True
            if ai < len(ancestors):
                return rec(ai + 1, si)
            return False
        if ai >= len(ancestors):
            return False
        if ancestors[ai].type in step.kinds:
            return rec(ai + 1, si + 1)
        return False

    return rec(0, 0)


def test_reference_matches_hand_cases():
    # M("a", ..., "a") over a -> b -> a: the far `a` satisfies the gap
    node = _chain(["a", "b", "a"])
    assert _brute(node, (PathStep(("a",)), GAP, PathStep(("a",)))) is True
    # M("a", "b") over a -> b -> c (anchor c): a->b is consecutive — fails
    node = _chain(["a", "b", "c"])
    assert _brute(node, (PathStep(("a",)), PathStep(("b",)), PathStep(("c",)))) \
        is True
    # consecutive steps must be CONSECUTIVE ancestors
    node = _chain(["a", "x", "b", "c"])
    assert _brute(node, (PathStep(("a",)), PathStep(("b",)), PathStep(("c",)))) \
        is False
    # a gap lets the chain skip: a -> ... -> b -> c
    assert _brute(node, (PathStep(("a",)), GAP, PathStep(("b",)),
                         PathStep(("c",)))) is True


def _random_case(rng: random.Random):
    kinds = ["a", "b", "c"]
    depth = rng.randint(1, 8)
    chain = [rng.choice(kinds) for _ in range(depth)]
    node = _chain(chain)
    # a random path: anchor = chain[-1]; prefix steps chosen from kinds +
    # gaps, always ending at the anchor
    anchor = chain[-1]
    prefix = []
    for _ in range(rng.randint(0, 5)):
        if rng.random() < 0.35:
            prefix.append(GAP)
        else:
            prefix.append(PathStep((rng.choice(kinds),)))
    prefix.append(PathStep((anchor,)))
    return node, tuple(prefix)


def test_matcher_agrees_with_brute_force():
    rng = random.Random(20260805)
    for _ in range(2000):
        node, path = _random_case(rng)
        got = match_ancestor_path(node, path)
        want = _brute(node, path)
        assert got == want, f"mismatch on chain={_ancestry(node)} path={path}"


def test_path_step_alternation():
    """A PathStep with multiple kinds matches ANY of them."""
    node = _chain(["a", "b", "c"])
    path = (PathStep(("x", "a")), GAP, PathStep(("c",)))
    assert match_ancestor_path(node, path) is True
    path = (PathStep(("x", "z")), GAP, PathStep(("c",)))
    assert match_ancestor_path(node, path) is False


def _ancestry(node) -> list[str]:
    out = []
    n = node
    while n is not None:
        out.append(n.type)
        n = n.parent
    return list(reversed(out))
