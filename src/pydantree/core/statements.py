from __future__ import annotations

"""Generic wrapper for *other* top‑level statements (assignments, expr, etc.)."""

from pydantic import Field

from .base import BaseCodeNode, GraphSitterEditable
from ..exceptions import GraphSitterIntegrationError


class PyStatement(BaseCodeNode):
    """Catch‑all wrapper for any node Pydantree hasn’t specialised."""

    raw: str = Field(..., description="Raw source code slice.")

    @classmethod
    def from_graphsitter(cls, node: GraphSitterEditable) -> "PyStatement":  # noqa: D401
        if not hasattr(node, "to_source"):
            raise GraphSitterIntegrationError("GraphSitter node lacks to_source()")
        return cls(raw=node.to_source(), graphsitter_node=node)

    def to_source(self) -> str:  # noqa: D401
        return self.raw
