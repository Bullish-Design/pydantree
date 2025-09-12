"""
Clean typed overlay system with explicit field factories.
"""

from __future__ import annotations

from typing import Optional, List, Type, Union
from pydantree import NodeGroup
from pydantree.core import TSNode
from data.pydantree_nodes import *
from pydantic import BaseModel, Field


def PydantreeNode(node_type: Type[TSNode], relationship: str = "self", **kwargs):
    """Field that preserves the actual node."""
    return Field(
        json_schema_extra={
            "extract": "node",
            "match_type": node_type,
            "relationship": relationship,
        },
        **kwargs,
    )


def PydantreeText(node_type: Type[TSNode], relationship: str = "name", **kwargs):
    """Field that extracts text from a node."""
    return Field(
        json_schema_extra={
            "extract": "text",
            "match_type": node_type,
            "relationship": relationship,
        },
        **kwargs,
    )


def PydantreeOverlays(overlay_type: Type["PydantreeOverlay"], **kwargs):
    """Field that creates nested overlays."""
    return Field(
        json_schema_extra={"extract": "overlays", "match_type": overlay_type}, **kwargs
    )


class PydantreeOverlay(BaseModel):
    """Base overlay with typed node support."""

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, **data):
        super().__init__(**data)
        self._node: Optional[TSNode] = None
        self._nodes: List[TSNode] = []

    @classmethod
    def match_in_graph(
        cls,
        nodegroup: NodeGroup,
        existing_overlays: dict[Type, List["PydantreeOverlay"]] = None,
    ) -> List["PydantreeOverlay"]:
        """Match using typed node classes."""
        existing_overlays = existing_overlays or {}

        # Get primary field type
        primary_field = cls._get_primary_field()
        if not primary_field:
            return []

        field_name, field_info, extra = primary_field
        match_type = extra["match_type"]

        # Get candidates based on typed class
        if issubclass(match_type, TSNode):
            candidates = list(nodegroup.filter_class(match_type))
        elif issubclass(match_type, PydantreeOverlay):
            candidates = existing_overlays.get(match_type, [])
        else:
            return []

        # Build overlays
        overlays = []
        for candidate in candidates:
            overlay_data = cls._extract_all_fields(
                candidate, nodegroup, existing_overlays
            )
            if overlay_data:
                overlay = cls(**overlay_data)
                overlay._node = (
                    candidate._node if hasattr(candidate, "_node") else candidate
                )
                overlays.append(overlay)

        return overlays

    @classmethod
    def _get_primary_field(cls):
        """Get primary matching field."""
        for field_name, field_info in cls.model_fields.items():
            extra = field_info.json_schema_extra or {}
            if "match_type" in extra:
                return field_name, field_info, extra
        return None

    @classmethod
    def _extract_all_fields(cls, candidate, nodegroup, existing_overlays):
        """Extract all field values using typed nodes."""
        data = {}

        for field_name, field_info in cls.model_fields.items():
            extra = field_info.json_schema_extra or {}
            if "match_type" not in extra:
                continue

            value = cls._extract_field_value(
                candidate, field_name, field_info, extra, nodegroup, existing_overlays
            )

            if value is not None:
                data[field_name] = value
            elif hasattr(field_info, "default") and field_info.default is not None:
                data[field_name] = field_info.default

        return data

    @classmethod
    def _extract_field_value(
        cls, candidate, field_name, field_info, extra, nodegroup, existing_overlays
    ):
        """Extract field value based on extract type."""
        extract_type = extra.get("extract", "node")
        match_type = extra["match_type"]
        relationship = extra.get("relationship", "name")

        # Get base node
        if hasattr(candidate, "_node"):
            node = candidate._node
        else:
            node = candidate

        if extract_type == "text":
            # Extract text from node
            if relationship == "name":
                child = node.child_by_field_name("name")
                return child.text if child else None
            elif relationship == "field":
                child = node.child_by_field_name(field_name)
                return child.text if child else None
            elif relationship == "return_type":
                child = node.child_by_field_name("return_type")
                return child.text if child else None

        elif extract_type == "node":
            # Return the actual node
            if relationship == "field":
                return node.child_by_field_name(field_name)
            else:
                return node

        elif extract_type == "overlays":
            # Create nested overlays
            sub_nodegroup = NodeGroup.from_tree(node)
            return match_type.match_in_graph(sub_nodegroup, existing_overlays)

        elif relationship == "child":
            # Find first child of specified type
            for child in node.children:
                print(f"    Child: {child}")
                if isinstance(child, match_type):
                    print(f"        -> Match!")
                    return child.text if extract_type == "text" else child
            return None

        return None


class OverlayMatcher:
    """Matcher with typed node support."""

    def __init__(self, nodegroup: NodeGroup):
        self.nodegroup = nodegroup
        self.overlays: dict[Type, List[PydantreeOverlay]] = {}

    def match_overlays(
        self, overlay_classes: List[Type[PydantreeOverlay]]
    ) -> dict[Type, List[PydantreeOverlay]]:
        """Match overlays bottom-up."""
        sorted_classes = self._sort_by_dependencies(overlay_classes)

        for overlay_class in sorted_classes:
            matches = overlay_class.match_in_graph(self.nodegroup, self.overlays)
            self.overlays[overlay_class] = matches

        return self.overlays

    def _sort_by_dependencies(self, overlay_classes):
        """Sort by overlay dependencies."""

        def dependency_score(cls):
            score = 0
            for field_info in cls.model_fields.values():
                extra = field_info.json_schema_extra or {}
                if extra.get("extract") == "overlays":
                    score += 10
                else:
                    score += 1
            return score

        return sorted(overlay_classes, key=dependency_score)


# ===== Clean Overlay Definitions =====


class ParameterOverlay(PydantreeOverlay):
    """Matches parameters with explicit field types."""

    node: TypedParameterNode = PydantreeNode(TypedParameterNode, default=None)
    name: str = PydantreeText(IdentifierNode, relationship="child", default="unknown")
    type_hint: Optional[str] = PydantreeText(
        TypeTokenNode, relationship="field", default=None
    )


class FunctionOverlay(PydantreeOverlay):
    """Matches functions with nested parameter overlays."""

    node: FunctionDefinitionNode = PydantreeNode(FunctionDefinitionNode, default=None)
    name: str = PydantreeText(IdentifierNode, default="unknown")
    parameters: List[ParameterOverlay] = PydantreeOverlays(ParameterOverlay, default=[])
    return_type: Optional[str] = PydantreeText(
        TypeTokenNode, relationship="return_type", default=None
    )

    def get_docstring(self) -> Optional[str]:
        """Extract docstring using typed node access."""
        if isinstance(self._node, FunctionDefinitionNode):
            body = self._node.body
            if body.children:
                first = body.children[0]
                if isinstance(first, ExpressionStatementNode):
                    if first.children and isinstance(first.children[0], StringNode):
                        return first.children[0].text.strip("\"\"\"'''")
        return None


class ClassOverlay(PydantreeOverlay):
    """Matches classes with nested method overlays."""

    node: ClassDefinitionNode = PydantreeNode(ClassDefinitionNode, default=None)
    name: str = PydantreeText(IdentifierNode, default="unknown")
    methods: List[FunctionOverlay] = PydantreeOverlays(FunctionOverlay, default=[])
    superclasses: Optional[ArgumentListNode] = PydantreeNode(
        ArgumentListNode, relationship="field", default=None
    )

    def get_base_classes(self) -> List[str]:
        """Get base class names using typed access."""
        if isinstance(self._node, ClassDefinitionNode) and self._node.superclasses:
            return [
                child.text
                for child in self._node.superclasses.children
                if isinstance(child, IdentifierNode)
            ]
        return []


class PydanticModelOverlay(PydantreeOverlay):
    """Matches Pydantic models using overlay composition."""

    class_node: ClassOverlay = PydantreeOverlays(ClassOverlay)

    @property
    def name(self) -> str:
        return self.class_node[0].name if self.class_node else "unknown"

    def is_pydantic_model(self) -> bool:
        """Check if this is a Pydantic model."""
        if self.class_node:
            base_classes = self.class_node[0].get_base_classes()
            return "BaseModel" in base_classes
        return False


def main():
    from pydantree import parse_python, NodeGroup

    code = '''
class UserModel(BaseModel):
    def validate_user(self, data: dict) -> bool:
        """Validate user data."""
        return True
    '''

    module = parse_python(code)
    nodegroup = NodeGroup.from_tree(module.node)

    matcher = OverlayMatcher(nodegroup)
    results = matcher.match_overlays(
        [ParameterOverlay, FunctionOverlay, ClassOverlay, PydanticModelOverlay]
    )

    for overlay_type, instances in results.items():
        print(f"{overlay_type.__name__}: {len(instances)}")
        for instance in instances:
            print(f"  - {getattr(instance, 'name', 'unnamed')}")


if __name__ == "__main__":
    main()
