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

    # def validate_structure(self):
    #    pass

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
        """Construct a *PyFile* from a Graph Sitter `SourceFile` / `File`.

        Accepted minimal interface:
            • `source` **or** `to_source()`  → full file text
            • `symbols` list                → ordered children (preferred)
            • *else* `imports`, `classes`, `functions` lists used as fallback
            • optional `docstring` attribute
        """
        # ---- get raw text --------------------------------------------------
        if hasattr(node, "to_source"):
            src = node.to_source()
        elif hasattr(node, "source"):
            src = node.source  # type: ignore[attr-defined]
        else:
            raise GraphSitterIntegrationError(
                "Editable must expose .source or .to_source()"
            )

        # ---- shebang -------------------------------------------------------
        shebang = src.split("\n", 1)[0].rstrip() if src.startswith("#!") else None

        # ---- gather children in source order ------------------------------
        if hasattr(node, "symbols"):
            children = list(node.symbols)  # already source‑ordered
        elif all(hasattr(node, attr) for attr in ("imports", "classes", "functions")):
            children = list(node.imports) + list(node.classes) + list(node.functions)
        else:
            raise GraphSitterIntegrationError(
                "Editable lacks accessible children lists"
            )

        def ensure_to_source(child):  # attach .to_source if only .source exists
            if not hasattr(child, "to_source") and hasattr(child, "source"):
                child.to_source = lambda c=child: c.source  # type: ignore[attr-defined]
            return child

        items: List[TopLevelNode] = []
        for child in map(ensure_to_source, children):
            name = child.__class__.__name__.lower()
            if "import" in name:
                items.append(PyImport.from_graphsitter(child))
            elif "class" in name:
                items.append(PyClass.from_graphsitter(child))
            elif "function" in name:
                items.append(PyFunction.from_graphsitter(child))
            else:
                items.append(PyStatement.from_graphsitter(child))

        # ---- docstring -----------------------------------------------------
        docstring = None
        if hasattr(node, "docstring") and node.docstring is not None:
            raw = getattr(node.docstring, "source", None)
            if raw:
                docstring = raw.strip()

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
