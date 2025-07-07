"""
pydantree.views
~~~~~~~~~~~~~~~
A thin, composable wrapper layer that turns the low-level, Pydantic-typed
Tree-sitter nodes generated in *python_nodes.py* into ergonomic “views”
with chainable selectors and a one-pass transformer API.

Public entry-points:
    • PyModule.parse(code: str)            – parse from source string
    • PyModule.parse_file(path: str | Path)
    • PyTransformer                        – subclass for codemods
"""

from __future__ import annotations

from pathlib import Path
from typing import (
    Callable,
    Generic,
    Iterable,
    Iterator,
    TypeVar,
)

from pydantree import Parser, ParsedDocument, TSNode
from data.python_nodes import (  # generated dataclasses
    ModuleNode,
    FunctionDefinitionNode,
    ClassDefinitionNode,
)
from tree_sitter import Language, Parser as _TSParser, Query  # , QueryCursor

# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _walk(node: TSNode) -> Iterator[TSNode]:
    """Depth-first traversal that works on any TSNode wrapper."""
    for child in node.children:
        yield child
        yield from _walk(child)


# --------------------------------------------------------------------------- #
# Generic “view” wrapper
# --------------------------------------------------------------------------- #

_TNode = TypeVar("_TNode", bound=TSNode)


class PyView(Generic[_TNode]):
    """
    Base wrapper that exposes common conveniences while keeping a reference
    to the original ParsedDocument (so we can apply incremental edits).
    """

    __slots__ = ("node", "_doc")

    def __init__(self, node: _TNode, doc: ParsedDocument):
        self.node: _TNode = node
        self._doc = doc

    # Convenience ---------------------------------------------------------
    @property
    def text(self) -> str:  # full source slice for this node
        return self.node.text

    @property
    def start_point(self):  # (row, col) tuple
        return self.node.start_point

    def children(self, cls: type[TSNode] | None = None) -> Iterator[TSNode]:
        """
        Yield direct children, optionally filtering by subclass/type.
        """
        for c in self.node.children:
            if cls is None or isinstance(c, cls):
                yield c


# --------------------------------------------------------------------------- #
# Concrete views
# --------------------------------------------------------------------------- #


class PyModule(PyView[ModuleNode]):
    """Root wrapper around a Python *module* CST."""

    # --- factory helpers -------------------------------------------------
    @classmethod
    def parse(cls, code: str, lang: Language | None = None) -> "PyModule":
        if lang is None:
            import tree_sitter_python as tspy

            lang = Language(tspy.language())
        parser = Parser(lang)
        # parser = Parser.for_language("python")  # helper provided by pydantree.core
        doc = ParsedDocument(text=code, parser=parser)
        return cls(doc.root, doc)

    @classmethod
    def parse_file(cls, path: str | Path) -> "PyModule":
        return cls.parse(Path(path).read_text())

    # --- selectors -------------------------------------------------------
    def functions(self) -> "QuerySet[PyFunction]":
        return QuerySet(self).filter_type(FunctionDefinitionNode).wrap(PyFunction)

    def classes(self) -> "QuerySet[PyClass]":
        return QuerySet(self).filter_type(ClassDefinitionNode).wrap(PyClass)


# --------------------------------------------------------------------------- #
# QuerySet – lazy, chainable selectors
# --------------------------------------------------------------------------- #

_S = TypeVar("_S", bound=PyView)


class QuerySet(Generic[_S]):
    """
    Minimal, Django-inspired chainable selector over a subtree.

    Each call returns *self* so you can do:

        module.functions().named("foo").where(lambda f: f.has_return())
    """

    def __init__(self, root: PyView):
        # Traverse the entire subtree so deep-nested defs are included
        self._iter: Iterable[TSNode] = _walk(root.node)
        self._root = root
        # By default, yield raw TSNodes until .wrap() is called
        self._wrap: Callable[[TSNode, ParsedDocument], _S] = lambda n, d: n  # type: ignore

    # ----- chaining helpers ---------------------------------------------
    def filter(self, fn: Callable[[TSNode], bool]) -> "QuerySet[_S]":
        self._iter = filter(fn, self._iter)
        return self

    def filter_type(self, cls: type[TSNode]) -> "QuerySet[_S]":
        return self.filter(lambda n: isinstance(n, cls))

    def named(self, name: str) -> "QuerySet[_S]":
        return self.filter(lambda n: getattr(n, "text", "") == name)

    def where(self, pred: Callable[[_S], bool]) -> "QuerySet[_S]":
        return self.filter(lambda n: pred(self._wrap(n, self._root._doc)))

    def wrap(self, view_cls: type[_S]) -> "QuerySet[_S]":
        """
        Specify the view wrapper class to materialise for each node.
        Must be called *before* iteration if you want view objects back.
        """
        self._wrap = lambda n, d: view_cls(n, d)
        return self

    # ----- materialisation ---------------------------------------------
    def __iter__(self) -> Iterator[_S]:
        for n in self._iter:
            yield self._wrap(n, self._root._doc)

    # Pythonic sugar
    def map(self, fn: Callable[[_S], "T"]) -> list["T"]:
        return [fn(v) for v in self]


# --------------------------------------------------------------------------- #
# Function / class views
# --------------------------------------------------------------------------- #


class PyFunction(PyView[FunctionDefinitionNode]):
    """Wrapper around a `function_definition` CST node."""

    # --- semantic helpers ----------------------------------------------
    def name(self) -> str:
        """
        Return the function’s identifier, robust to grammar/ABI changes.

        1. Tree-sitter exposes it via field name ``name``.
        2. Fallback: scan children for IdentifierNode *or* raw ``identifier``.
        """
        print(f"\nNode: {self.node.dict()}\n")  # "__dir__()}\n")
        # 1) Field lookup on raw Tree-sitter node
        if hasattr(self.node, "child_by_field_name"):
            child = self.node.child_by_field_name("name")
            if child:
                return child.text

        # 2) Scan immediate children
        for c in self.node.children:
            print(f"    Child: {c.dict()}")  # "__dir__()}\n"
            if (
                c.__class__.__name__.endswith("IdentifierNode")
                or getattr(c, "type", "") == "identifier"
                or getattr(c, "type_name", "") == "identifier"
            ):
                return c.text

        return "<anonymous>"

    def has_return(self) -> bool:
        """True if any descendant is a return statement."""
        return any(
            (
                getattr(n, "type", "") == "return_statement"
                or getattr(n, "type_name", "") == "return_statement"
                or n.__class__.__name__.endswith("ReturnStatementNode")
            )
            for n in _walk(self.node)
        )


class PyClass(PyView[ClassDefinitionNode]):
    """Wrapper for `class_definition` CST nodes."""

    # Extend as needed
    pass


# --------------------------------------------------------------------------- #
# Transformer – single-pass, codemod-friendly visitor
# --------------------------------------------------------------------------- #


class PyTransformer:
    """
    Subclass and implement ``visit_<node_type>(self, node)`` methods.

    If a visit_* handler returns a *str*, that slice is spliced into the
    underlying ParsedDocument via incremental edit; return ``None`` to leave
    the node unchanged.
    """

    def __init__(self, mod: PyModule):
        self.mod = mod

    # ------------------------------------------------------------- main --
    def visit(self) -> str:
        for node in _walk(self.mod.node):
            handler = getattr(self, f"visit_{node.type_name}", None)
            if handler:
                replacement = handler(node)
                if replacement is not None:
                    # Apply incremental edit
                    self.mod._doc.edit(
                        node.start_byte,
                        node.end_byte,
                        node.start_byte + len(replacement),
                        replacement,
                    )
        return self.mod._doc.text
