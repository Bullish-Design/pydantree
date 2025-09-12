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
    Optional,
    List,
    Union,
    Dict,
    Any,
)

from pydantree import Parser, ParsedDocument, TSNode
from pydantree.nodegroup import NodeGroup, NodeSelector, TypeSelector

from data.pydantree_nodes import (  # generated dataclasses
    ModuleNode,
    FunctionDefinitionNode,
    ClassDefinitionNode,
    IdentifierNode,
    ReturnStatementNode,
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

    def to_nodegroup(self) -> NodeGroup[TSNode]:
        """Convert this view's subtree to a NodeGroup."""
        return NodeGroup.from_tree(self.node)

    def descendants(self) -> NodeGroup[TSNode]:
        """Get all descendant nodes as NodeGroup."""
        return NodeGroup.from_tree(self.node).descendants()


# --------------------------------------------------------------------------- #
# Concrete views
# --------------------------------------------------------------------------- #


class PyModule(PyView[ModuleNode]):
    """Root wrapper around a Python *module* CST."""

    # --- factory helpers -------------------------------------------------
    @classmethod
    def parse(cls, code: str, lang: Language | None = None) -> PyModule:
        if lang is None:
            import tree_sitter_python as tspy

            lang = Language(tspy.language())
        parser = Parser(lang)
        # parser = Parser.for_language("python")  # helper provided by pydantree.core
        doc = ParsedDocument(text=code, parser=parser)
        return cls(doc.root, doc)

    @classmethod
    def parse_file(cls, path: str | Path) -> PyModule:
        return cls.parse(Path(path).read_text())

    # --- selectors using NodeGroup --------------------------------------
    def functions(self) -> QuerySet[PyFunction]:
        """Get all function definitions as QuerySet."""
        nodegroup = self.to_nodegroup()
        function_nodes = nodegroup.filter_class(FunctionDefinitionNode)
        return QuerySet(function_nodes, self._doc, PyFunction)

    def classes(self) -> QuerySet[PyClass]:
        """Get all class definitions as QuerySet."""
        nodegroup = self.to_nodegroup()
        class_nodes = nodegroup.filter_class(ClassDefinitionNode)
        return QuerySet(class_nodes, self._doc, PyClass)

    def imports(self) -> QuerySet[PyImport]:
        """Get all import statements as QuerySet."""
        nodegroup = self.to_nodegroup()
        import_nodes = nodegroup.filter_type("import_statement").union(
            nodegroup.filter_type("import_from_statement")
        )
        return QuerySet(import_nodes, self._doc, PyImport)

    def statements(self) -> NodeGroup[TSNode]:
        """Get all top-level statements."""
        return NodeGroup(self.node.children)


# --------------------------------------------------------------------------- #
# QuerySet – lazy, chainable selectors with NodeGroup backend
# --------------------------------------------------------------------------- #

_S = TypeVar("_S", bound=PyView)


class QuerySet(Generic[_S]):
    """
    Enhanced chainable selector built on NodeGroup foundation.
    Provides Django-inspired API with lazy evaluation.
    """

    def __init__(
        self, nodegroup: NodeGroup[TSNode], doc: ParsedDocument, view_cls: type[_S]
    ):
        self._nodegroup = nodegroup
        self._doc = doc
        self._view_cls = view_cls

    # ----- chaining helpers ---------------------------------------------
    def filter(self, selector: NodeSelector) -> QuerySet[_S]:
        """Add a filter selector (lazy)."""
        filtered = self._nodegroup.filter(selector)
        return QuerySet(filtered, self._doc, self._view_cls)

    def filter_type(self, type_name: str) -> QuerySet[_S]:
        """Filter by node type name."""
        return QuerySet(
            self._nodegroup.filter_type(type_name), self._doc, self._view_cls
        )

    def filter_class(self, node_class: type[TSNode]) -> QuerySet[_S]:
        """Filter by Python class."""
        return QuerySet(
            self._nodegroup.filter_class(node_class), self._doc, self._view_cls
        )

    def named(self, name: str) -> QuerySet[_S]:
        """Filter by name (for named constructs)."""
        return self.where(lambda v: getattr(v, "name", lambda: "")() == name)

    def where(self, predicate: Callable[[_S], bool]) -> QuerySet[_S]:
        """Filter using custom predicate."""
        filtered_nodes = []
        for node in self._nodegroup:
            view = self._view_cls(node, self._doc)
            if predicate(view):
                filtered_nodes.append(node)

        return QuerySet(NodeGroup(filtered_nodes), self._doc, self._view_cls)

    def containing_text(self, text: str) -> QuerySet[_S]:
        """Filter nodes containing specific text."""
        return QuerySet(
            self._nodegroup.filter_text(text, exact=False), self._doc, self._view_cls
        )

    # ----- set operations -----------------------------------------------
    def union(self, other: QuerySet[_S]) -> QuerySet[_S]:
        """Union with another QuerySet."""
        return QuerySet(
            self._nodegroup.union(other._nodegroup), self._doc, self._view_cls
        )

    def intersection(self, other: QuerySet[_S]) -> QuerySet[_S]:
        """Intersection with another QuerySet."""
        return QuerySet(
            self._nodegroup.intersection(other._nodegroup), self._doc, self._view_cls
        )

    def difference(self, other: QuerySet[_S]) -> QuerySet[_S]:
        """Difference from another QuerySet."""
        return QuerySet(
            self._nodegroup.difference(other._nodegroup), self._doc, self._view_cls
        )

    # ----- materialisation ---------------------------------------------
    def __iter__(self) -> Iterator[_S]:
        """Iterate over view objects."""
        for node in self._nodegroup:
            yield self._view_cls(node, self._doc)

    def __len__(self) -> int:
        """Get count of nodes."""
        return len(self._nodegroup)

    def __bool__(self) -> bool:
        """True if QuerySet contains any nodes."""
        return bool(self._nodegroup)

    # ----- collection operations ---------------------------------------
    def first(self) -> Optional[_S]:
        """Get first matching view."""
        node = self._nodegroup.find_first()
        return self._view_cls(node, self._doc) if node else None

    def all(self) -> List[_S]:
        """Get all matching views."""
        return list(self)

    def count(self) -> int:
        """Count matching views."""
        return len(self)

    def exists(self) -> bool:
        """True if any matches exist."""
        return bool(self)

    # ----- transformation operations -----------------------------------
    def map(self, func: Callable[[_S], Any]) -> List[Any]:
        """Apply function to all views."""
        return [func(view) for view in self]

    def to_nodegroup(self) -> NodeGroup[TSNode]:
        """Convert back to NodeGroup."""
        return self._nodegroup


# --------------------------------------------------------------------------- #
# Function / class / import views
# --------------------------------------------------------------------------- #


class PyFunction(PyView[FunctionDefinitionNode]):
    """Wrapper around a `function_definition` CST node."""

    def name(self) -> str:
        """Return the function's identifier."""
        name_child = self.node.child_by_field_name("name")
        if name_child:
            return name_child.text

        # Fallback: scan children for identifier
        for child in self.node.children:
            if child.type_name == "identifier" or isinstance(child, IdentifierNode):
                return child.text

        return "<anonymous>"

    def parameters(self) -> Optional[TSNode]:
        """Get parameters node."""
        return self.node.child_by_field_name("parameters")

    def body(self) -> Optional[TSNode]:
        """Get function body."""
        return self.node.child_by_field_name("body")

    def return_type(self) -> Optional[TSNode]:
        """Get return type annotation."""
        return self.node.child_by_field_name("return_type")

    def has_return(self) -> bool:
        """True if any descendant is a return statement."""
        return any(
            isinstance(node, ReturnStatementNode)
            or node.type_name == "return_statement"
            for node in self.node.descendants()
        )

    def decorators(self) -> List[TSNode]:
        """Get all decorators."""
        # Look for decorated_definition parent
        parent_nodes = []  # Would need parent tracking for this
        # For now, simplified implementation
        return []

    def is_async(self) -> bool:
        """True if this is an async function."""
        # Check for 'async' keyword before 'def'
        return "async" in self.node.text[:20]  # Simplified check


class PyClass(PyView[ClassDefinitionNode]):
    """Wrapper for `class_definition` CST nodes."""

    def name(self) -> str:
        """Return the class name."""
        name_child = self.node.child_by_field_name("name")
        if name_child:
            return name_child.text

        # Fallback
        for child in self.node.children:
            if child.type_name == "identifier" or isinstance(child, IdentifierNode):
                return child.text

        return "<anonymous>"

    def superclasses(self) -> Optional[TSNode]:
        """Get superclasses argument list."""
        return self.node.child_by_field_name("superclasses")

    def body(self) -> Optional[TSNode]:
        """Get class body."""
        return self.node.child_by_field_name("body")

    def methods(self) -> QuerySet[PyFunction]:
        """Get all methods in this class."""
        body = self.body()
        if not body:
            return QuerySet(NodeGroup.empty(), self._doc, PyFunction)

        body_nodegroup = NodeGroup.from_tree(body)
        method_nodes = body_nodegroup.filter_class(FunctionDefinitionNode)
        return QuerySet(method_nodes, self._doc, PyFunction)

    def has_init(self) -> bool:
        """True if class has __init__ method."""
        return any(method.name() == "__init__" for method in self.methods())


class PyImport(PyView[TSNode]):
    """Wrapper for import statements."""

    def module_name(self) -> str:
        """Get the imported module name."""
        if self.node.type_name == "import_statement":
            # import foo.bar
            name_child = self.node.child_by_field_name("name")
            return name_child.text if name_child else ""
        elif self.node.type_name == "import_from_statement":
            # from foo import bar
            module_child = self.node.child_by_field_name("module_name")
            return module_child.text if module_child else ""
        return ""

    def imported_names(self) -> List[str]:
        """Get list of imported names."""
        names = []
        if self.node.type_name == "import_from_statement":
            # Look for name field (can be multiple)
            for child in self.node.children:
                if child.field_name == "name":
                    names.append(child.text)
        return names

    def is_from_import(self) -> bool:
        """True if this is a 'from ... import' statement."""
        return self.node.type_name == "import_from_statement"


# --------------------------------------------------------------------------- #
# Transformer – single-pass, codemod-friendly visitor
# --------------------------------------------------------------------------- #


class PyTransformer:
    """
    Enhanced transformer with NodeGroup integration.

    Subclass and implement ``visit_<node_type>(self, node)`` methods.
    Can also use NodeGroup operations for bulk transformations.
    """

    def __init__(self, mod: PyModule):
        self.mod = mod
        self.edits: List[Tuple[TSNode, str]] = []

    def visit(self) -> str:
        """Apply transformations and return modified source."""
        nodegroup = self.mod.to_nodegroup()

        # Collect all transformations first
        for node in nodegroup:
            handler = getattr(self, f"visit_{node.type_name}", None)
            if handler:
                replacement = handler(node)
                if replacement is not None:
                    self.edits.append((node, replacement))

        # Apply edits in reverse order (from end to beginning) to avoid position conflicts
        self.edits.sort(key=lambda edit: edit[0].start_byte, reverse=True)

        for node, replacement in self.edits:
            self._apply_edit(node, replacement)

        return self.mod._doc.text

    def bulk_transform(
        self, selector: NodeSelector, transformer: Callable[[TSNode], str]
    ) -> None:
        """Apply bulk transformation to selected nodes."""
        nodegroup = self.mod.to_nodegroup()
        selected = nodegroup.filter(selector)

        edits = []
        for node in selected:
            replacement = transformer(node)
            edits.append((node, replacement))

        # Apply in reverse order
        edits.sort(key=lambda edit: edit[0].start_byte, reverse=True)
        for node, replacement in edits:
            self._apply_edit(node, replacement)

    def _apply_edit(self, node: TSNode, replacement: str) -> None:
        """Apply incremental edit to document."""
        self.mod._doc.edit(
            node.start_byte,
            node.end_byte,
            node.start_byte + len(replacement),
            replacement,
        )


# --------------------------------------------------------------------------- #
# High-level convenience functions
# --------------------------------------------------------------------------- #


def parse_python(code: str) -> PyModule:
    """Parse Python code into PyModule."""
    return PyModule.parse(code)


def parse_python_file(path: Union[str, Path]) -> PyModule:
    """Parse Python file into PyModule."""
    return PyModule.parse_file(path)


def find_functions(code: str, name: Optional[str] = None) -> List[PyFunction]:
    """Find functions in Python code."""
    module = parse_python(code)
    functions = module.functions()
    if name:
        functions = functions.named(name)
    return functions.all()


def find_classes(code: str, name: Optional[str] = None) -> List[PyClass]:
    """Find classes in Python code."""
    module = parse_python(code)
    classes = module.classes()
    if name:
        classes = classes.named(name)
    return classes.all()
