"""The typed-node ancestor-path matcher."""

from __future__ import annotations

from .nodes import GAP, PathStep

__all__ = ["GAP", "PathStep", "match_ancestor_path"]


def match_ancestor_path(node, path: tuple) -> bool:
    """Return whether ``node`` satisfies a normalized ancestor path."""
    if len(path) == 1:
        return True
    steps = tuple(reversed(path[:-1]))
    parent = node.parent
    if parent is None:
        return all(step is GAP for step in steps)
    return _match_steps(parent, steps, 0)


def _match_steps(node, steps: tuple, index: int) -> bool:
    if index >= len(steps):
        return True
    step = steps[index]
    if step is GAP:
        if _match_steps(node, steps, index + 1):
            return True
        parent = node.parent
        return parent is not None and _match_steps(parent, steps, index)
    if isinstance(step, PathStep) and node.type in step.kinds:
        parent = node.parent
        if parent is None:
            return all(item is GAP for item in steps[index + 1:])
        return _match_steps(parent, steps, index + 1)
    return False
