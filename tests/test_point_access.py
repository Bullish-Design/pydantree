"""Guard: never read `Point.row` / `Point.column` as attributes.

tree-sitter 0.26.0 reworked `Point` into a tuple subclass whose `.row` and
`.column` getters return a BORROWED reference instead of a new one. Reading
either for a non-immortal int — any value above 256, CPython's small-int cache
bound — leaves the int one refcount short, so it is freed while the Point
still owns it. The result is allocator corruption that detonates later in an
unrelated allocation: SIGSEGV, SIGBUS, SIGABRT or a hang, far from the read.
Reading as few as 246 such values is enough to kill a process.

Upstream: tree-sitter/py-tree-sitter#472, fixed by #466 (merged 2026-07-08),
not in any release as of 0.26.0.

Tuple access (`point[0]`, `row, column = point`) goes through
PyTuple_GET_ITEM, is correct on 0.25.x / 0.26.0 / the fixed build alike, and
yields identical values — so it is the permanent form, not a workaround to
revert once 0.26.1 ships.

This test is a source guard rather than a crash reproduction: reproducing the
corruption needs hundreds of thousands of node reads over real files and is
probabilistic, which makes for a slow and flaky test. Grepping the source is
deterministic and catches the regression at the point it is written --
including in `codegen.py`, whose emitted `line` property ships to users where
no runtime fix can reach it.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

PKG_ROOTS = [
    pathlib.Path(__file__).resolve().parents[1] / "src" / "pydantree_sitter",
    pathlib.Path(__file__).resolve().parents[1] / "src" / "pydantree_sitter_grammar",
]
POINT_ATTRS = {"row", "column"}
POINT_SOURCES = {"start_point", "end_point"}


def _python_files() -> list[pathlib.Path]:
    return sorted(p for root in PKG_ROOTS if root.is_dir() for p in root.rglob("*.py"))


def _attr_reads(tree: ast.AST) -> list[tuple[int, str]]:
    """`<expr>.start_point.row` / `<expr>.end_point.column` and friends."""
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr not in POINT_ATTRS:
            continue
        inner = node.value
        if isinstance(inner, ast.Attribute) and inner.attr in POINT_SOURCES:
            hits.append((node.lineno, f"{inner.attr}.{node.attr}"))
    return hits


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_no_point_attribute_reads(path: pathlib.Path) -> None:
    source = path.read_text(encoding="utf-8")
    hits = _attr_reads(ast.parse(source))
    assert not hits, (
        f"{path}: reads Point attributes {hits} — use tuple access instead "
        f"(`row, column = node.start_point` or `node.start_point[0]`). "
        f"See this module's docstring: py-tree-sitter#472."
    )


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_no_point_attribute_reads_in_emitted_code(path: pathlib.Path) -> None:
    """codegen.py builds source as string literals, which the AST pass above
    cannot see through — check the literals themselves."""
    source = path.read_text(encoding="utf-8")
    bad = [
        (i, line.strip())
        for i, line in enumerate(source.splitlines(), 1)
        for src in POINT_SOURCES
        for attr in POINT_ATTRS
        if f"{src}.{attr}" in line and not line.lstrip().startswith("#")
    ]
    assert not bad, (
        f"{path}: emits or references Point attribute access {bad} — use "
        f"tuple access. Emitted code ships to users, where no runtime fix "
        f"can reach it. See py-tree-sitter#472."
    )
