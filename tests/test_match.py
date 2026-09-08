"""The typed universe's one backtracking ancestor matcher."""

from __future__ import annotations

import random

from pydantree_sitter.match import GAP, PathStep, match_ancestor_path


class _Node:
    def __init__(self, kind: str, parent: _Node | None = None):
        self.type = kind
        self.parent = parent


def _chain(kinds: list[str]) -> _Node:
    node = _Node(kinds[0])
    for kind in kinds[1:]:
        node = _Node(kind, parent=node)
    return node


def _brute(node, path: tuple) -> bool:
    steps = list(reversed(path[:-1]))
    ancestors = []
    current = node.parent
    while current is not None:
        ancestors.append(current)
        current = current.parent

    def rec(ai: int, si: int) -> bool:
        if si >= len(steps):
            return True
        step = steps[si]
        if step is GAP:
            return rec(ai, si + 1) or (
                ai < len(ancestors) and rec(ai + 1, si))
        return ai < len(ancestors) and ancestors[ai].type in step.kinds and \
            rec(ai + 1, si + 1)

    return rec(0, 0)


def _ancestry(node) -> list[str]:
    out = []
    while node is not None:
        out.append(node.type)
        node = node.parent
    return list(reversed(out))


def test_matcher_agrees_with_brute_force():
    rng = random.Random(20260805)
    kinds = ["a", "b", "c"]
    for _ in range(2000):
        chain = [rng.choice(kinds) for _ in range(rng.randint(1, 8))]
        node = _chain(chain)
        prefix = [
            GAP if rng.random() < 0.35 else PathStep((rng.choice(kinds),))
            for _ in range(rng.randint(0, 5))
        ]
        path = (*prefix, PathStep((chain[-1],)))
        assert match_ancestor_path(node, path) == _brute(node, path), (
            f"mismatch on chain={_ancestry(node)} path={path}")


def test_path_step_alternation():
    node = _chain(["a", "b", "c"])
    assert match_ancestor_path(
        node, (PathStep(("x", "a")), GAP, PathStep(("c",))))
    assert not match_ancestor_path(
        node, (PathStep(("x", "z")), GAP, PathStep(("c",))))
