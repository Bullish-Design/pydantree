from __future__ import annotations

"""Light‑weight models for Python *import* statements.

These classes keep just enough structure to rebuild the source while
playing nicely with Pydantree’s validation story.  For now we support two
syntax forms:

* ``import module [as alias]``
* ``from package import name1 [, name2 …] [as alias]``

The wrapper stores the *raw* text slice from Graph Sitter so we can
round‑trip **exactly**.  Field accessors expose parsed details for
higher‑level tooling.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .base import BaseCodeNode, GraphSitterEditable
from ..exceptions import GraphSitterIntegrationError


class _ImportedName(BaseModel):
    """Internal helper to represent one imported symbol."""

    name: str
    alias: Optional[str] = None

    def to_source(self) -> str:  # noqa: D401
        return f"{self.name} as {self.alias}" if self.alias else self.name


class PyImport(BaseCodeNode):
    """Represents ``import`` *or* ``from … import …`` at module level."""

    # If ``from`` style, this is the package; otherwise the first module.
    module: str = Field(..., description="Module or package being imported from.")
    names: List[_ImportedName] = Field(
        default_factory=list,
        description="Imported symbols (for 'from x import a, b').  Empty if plain 'import'.",
    )
    is_from_import: bool = Field(
        False, description="True when using 'from x import …'."
    )

    # Preserve original slice for lossless round‑trip
    raw: Optional[str] = Field(default=None, repr=False)

    @field_validator("module")
    def _strip(cls, v: str) -> str:  # noqa: D401
        return v.strip()

    # ---------------------------------------------------------------------
    # Graph‑sitter integration
    # ---------------------------------------------------------------------

    @classmethod
    def from_graphsitter(cls, node: GraphSitterEditable) -> "PyImport":  # noqa: D401
        if node.type not in {"import_statement", "import_from_statement"}:
            raise ValueError("Node is not an import statement")
        if not hasattr(node, "to_source"):
            raise GraphSitterIntegrationError("GraphSitter node lacks to_source()")

        text = node.to_source()
        tokens = text.replace(",", " , ").split()

        if tokens[0] == "import":
            # Simple form: import A as B, C
            # For now store entire right‑hand side as module; names empty.
            module = " ".join(tokens[1:])
            return cls(
                module=module,
                names=[],
                is_from_import=False,
                raw=text,
                graphsitter_node=node,
            )

        # from pkg import a as b, c
        module = tokens[1]
        # Everything after "import" forms names list
        name_tokens = tokens[tokens.index("import") + 1 :]
        names: List[_ImportedName] = []
        current: List[str] = []
        for tok in name_tokens:
            if tok == ",":
                if current:
                    names.append(_parse_name_alias(current))
                    current = []
            else:
                current.append(tok)
        if current:
            names.append(_parse_name_alias(current))
        return cls(
            module=module,
            names=names,
            is_from_import=True,
            raw=text,
            graphsitter_node=node,
        )

    # ------------------------------------------------------------------
    # Source regeneration
    # ------------------------------------------------------------------

    def to_source(self) -> str:  # noqa: D401
        if self.raw:
            return self.raw  # lossless path
        if self.is_from_import:
            joined = ", ".join(n.to_source() for n in self.names)
            return f"from {self.module} import {joined}"
        return f"import {self.module}"


# Helper outside class -------------------------------------------------------


def _parse_name_alias(tokens: List[str]) -> _ImportedName:  # noqa: D401
    if "as" in tokens:
        as_idx = tokens.index("as")
        name = " ".join(tokens[:as_idx])
        alias = " ".join(tokens[as_idx + 1 :])
        return _ImportedName(name=name, alias=alias)
    return _ImportedName(name=" ".join(tokens))
