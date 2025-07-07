from __future__ import annotations

"""pydantree/core/file.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Graph‑sitter‑only implementation of **PyFile** – a Pydantic model that
represents an entire Python module (regular file or runnable script).

This supersedes the earlier draft that fell back to the built‑in `ast`
parser.  *No stdlib AST dependency remains*; we rely exclusively on the
Python grammar from **tree‑sitter** for structural discovery.
"""

from pathlib import Path
from typing import List, Optional, Sequence, Union

from pydantic import Field, field_validator

from .base import BaseCodeNode, GraphSitterEditable
from .imports import PyImport
from .functions import PyFunction
from .classes import PyClass
from .statements import PyStatement
from ..exceptions import ValidationError, GraphSitterIntegrationError

# ---------------------------------------------------------------------------
# Public union of top‑level constructs recognised inside a file
# ---------------------------------------------------------------------------
TopLevelNode = Union[PyImport, PyClass, PyFunction, PyStatement]


class PyFile(BaseCodeNode):
    """High‑level wrapper that owns *all* elements inside a module."""

    file_path: Optional[Path] = Field(
        default=None,
        description="Absolute or project‑relative path on disk (optional).",
    )

    items: List[TopLevelNode] = Field(default_factory=list)
    """Ordered list of children exactly as they appeared in source."""

    shebang: Optional[str] = Field(
        default=None,
        description="`#!` line preserved for scripts (without trailing newline).",
    )

    docstring: Optional[str] = Field(
        default=None,
        description="First expression‑statement *string literal* per PEP‑257.",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("items")
    def _validate_items(cls, v: Sequence[TopLevelNode]) -> Sequence[TopLevelNode]:
        wrong = [
            i
            for i in v
            if not isinstance(i, (PyImport, PyClass, PyFunction, PyStatement))
        ]
        if wrong:
            raise ValueError(f"Unsupported node types in file.items: {wrong!r}")
        return list(v)

    # ------------------------------------------------------------------
    # Builder conveniences (mutate‑and‑return‑self)
    # ------------------------------------------------------------------

    def add_import(self, imp: PyImport) -> "PyFile":
        self.items.append(imp)
        return self

    def add_class(self, cls_: PyClass) -> "PyFile":
        self.items.append(cls_)
        return self

    def add_function(self, func: PyFunction) -> "PyFile":
        self.items.append(func)
        return self

    def add_statement(self, stmt: PyStatement) -> "PyFile":
        self.items.append(stmt)
        return self

    # ------------------------------------------------------------------
    # Source generation
    # ------------------------------------------------------------------

    def to_source(self) -> str:  # noqa: D401
        """Round‑trip back to text, preserving original ordering."""
        parts: List[str] = []

        if self.shebang:
            parts.append(self.shebang)
            parts.append("")

        if self.docstring:
            parts.append(self.docstring.strip())
            parts.append("")

        for node in self.items:
            parts.append(node.to_source().rstrip())
            parts.append("")

        while parts and parts[-1] == "":
            parts.pop()
        return "\n".join(parts) + "\n"

    # alias expected by BaseCodeNode
    _generate_source = to_source

    # ------------------------------------------------------------------
    # Graph‑sitter integration (no fallback!)
    # ------------------------------------------------------------------

    @classmethod
    def from_graphsitter(cls, node: GraphSitterEditable) -> "PyFile":  # noqa: D401
        """Build a ``PyFile`` by traversing a *module* root node.

        Requirements on *node*:
        * Implements ``to_source()`` and ``walk()`` (tree‑sitter Python
          node interface).
        * ``node.type`` is ``"module"`` (root produced by the grammar).
        """
        if not all(hasattr(node, attr) for attr in ("to_source", "walk", "type")):
            raise GraphSitterIntegrationError(
                "Node must expose tree‑sitter API attributes"
            )
        if node.type != "module":
            raise ValidationError("from_graphsitter expects a *module* root node")

        full_source: str = node.to_source()

        # --- Detect shebang -------------------------------------------------------
        if full_source.startswith("#!"):
            shebang_line = full_source.split("\n", 1)[0].rstrip("\n")
            shebang = shebang_line
        else:
            shebang = None

        # --- Utility: iterate direct children preserving order --------------------
        def _iter_children(n):  # type: ignore[ann401]
            cur = n.walk()
            if not cur.goto_first_child():
                return
            while True:
                yield cur.node
                if not cur.goto_next_sibling():
                    break

        # --- Extract module docstring & body items --------------------------------
        docstring: Optional[str] = None
        items: List[TopLevelNode] = []

        for child in _iter_children(node):
            ctype = child.type

            # *comments* may include shebang at (0,0). Skip normal comments.
            if ctype == "comment":
                continue

            # Module docstring = first expression_statement
            # whose child is *string* (triple‑quoted literal)
            if docstring is None and ctype == "expression_statement":
                str_child = (
                    child.child_by_field_name("expression")
                    if hasattr(child, "child_by_field_name")
                    else None
                )
                if str_child and str_child.type == "string":
                    docstring = str_child.text.decode()  # keep quotes
                    continue  # do not store docstring as PyStatement

            # Handle imports --------------------------------------------------
            if ctype in {"import_statement", "import_from_statement"}:
                items.append(PyImport.from_graphsitter(child))
                continue

            # Classes ---------------------------------------------------------
            if ctype == "class_definition":
                items.append(PyClass.from_graphsitter(child))
                continue

            # Functions (decorated or plain) ----------------------------------
            if ctype in {"function_definition", "decorated_definition"}:
                items.append(PyFunction.from_graphsitter(child))
                continue

            # Fallback – anything else becomes a generic statement ------------
            items.append(PyStatement.from_graphsitter(child))

        return cls(
            graphsitter_node=node,
            shebang=shebang,
            docstring=docstring,
            items=items,
        )

    # ------------------------------------------------------------------
    # Convenience filtered views --------------------------------------
    # ------------------------------------------------------------------

    @property
    def classes(self) -> List[PyClass]:
        return [i for i in self.items if isinstance(i, PyClass)]

    @property
    def functions(self) -> List[PyFunction]:
        return [i for i in self.items if isinstance(i, PyFunction)]

    @property
    def imports(self) -> List[PyImport]:
        return [i for i in self.items if isinstance(i, PyImport)]

    @property
    def statements(self) -> List[PyStatement]:
        return [i for i in self.items if isinstance(i, PyStatement)]
