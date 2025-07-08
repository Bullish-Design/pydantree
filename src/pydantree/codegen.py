#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.11",
#     "networkx>=3.0",
# ]
# ///

"""
pydantree.codegen – Grammar-to-code generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Translates Tree-sitter node-types.json into typed Pydantic node classes
with inheritance hierarchy, typed child fields, and grammar-aware edit helpers.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Set, Optional, Tuple
import rustworkx as rx


class NameResolver:
    """Convert Tree-sitter node names to Python class identifiers."""

    # Mapping for punctuation/operators to readable names
    SYMBOL_MAP = {
        "(": "LeftParen",
        ")": "RightParen",
        "[": "LeftBracket",
        "]": "RightBracket",
        "{": "LeftBrace",
        "}": "RightBrace",
        "<": "LessThan",
        ">": "GreaterThan",
        ",": "Comma",
        ".": "Dot",
        ":": "Colon",
        ";": "Semicolon",
        "+": "Plus",
        "-": "Minus",
        "*": "Asterisk",
        "/": "Slash",
        "%": "Percent",
        "&": "Ampersand",
        "|": "Pipe",
        "^": "Caret",
        "~": "Tilde",
        "@": "At",
        "\\": "Backslash",
        "_": "Underscore",
        "=": "Equals",
        "==": "Equality",
        "!=": "NotEquals",
        "<=": "LessEquals",
        ">=": "GreaterEquals",
        "+=": "PlusEquals",
        "-=": "MinusEquals",
        "*=": "TimesEquals",
        "/=": "DivideEquals",
        "%=": "ModEquals",
        "&=": "AmpersandEquals",
        "|=": "PipeEquals",
        "^=": "CaretEquals",
        "@=": "AtEquals",
        "//": "FloorDiv",
        "//=": "FloorDivEquals",
        "**": "Power",
        "**=": "PowerEquals",
        "<<": "LeftShift",
        "<<=": "LeftShiftEquals",
        ">>": "RightShift",
        ">>=": "RightShiftEquals",
        "->": "Arrow",
        ":=": "Walrus",
        "<>": "NotEqualsAlt",
        "is not": "IsNot",
        "not in": "NotIn",
        "except*": "ExceptStar",
    }

    def __init__(self, token_suffix: str = "TokenNode"):
        self.token_suffix = token_suffix
        self.seen: Set[str] = set()

    def resolve(self, node_type: str, is_named: bool = True) -> str:
        """Convert node type to Python class name."""
        if node_type in self.SYMBOL_MAP:
            class_name = self.SYMBOL_MAP[node_type]
        else:
            # Convert snake_case to PascalCase
            class_name = "".join(word.capitalize() for word in node_type.split("_"))

        # Add suffix for anonymous tokens
        if not is_named:
            class_name += self.token_suffix
        else:
            class_name += "Node"

        # Ensure uniqueness
        original = class_name
        counter = 1
        while class_name in self.seen:
            class_name = f"{original}{counter}"
            counter += 1

        self.seen.add(class_name)
        return class_name


class InheritanceAnalyzer:
    """Build inheritance hierarchy from node-types.json supertypes."""

    def __init__(self, node_specs: List[Dict[str, Any]]):
        self.specs = {spec["type"]: spec for spec in node_specs}
        self.graph = rx.DiGraph()
        self._build_graph()

    def _build_graph(self) -> None:
        """Build DAG of supertype relationships."""
        # Add all nodes
        for node_type in self.specs:
            self.graph.add_node(node_type)

        # Add edges for supertypes
        for spec in self.specs.values():
            if "subtypes" in spec:
                supertype = spec["type"]
                for subtype_spec in spec["subtypes"]:
                    subtype = subtype_spec["type"]
                    if subtype in self.specs:
                        self.graph.add_edge(subtype, supertype)

    def get_inheritance_order(self) -> List[str]:
        """Return nodes in topological order (leaves first)."""
        try:
            return list(reversed(list(nx.topological_sort(self.graph))))
        except nx.NetworkXError:
            # Fallback if cycles exist
            return list(self.specs.keys())

    def get_parent(self, node_type: str) -> Optional[str]:
        """Get direct parent type, if any."""
        parents = list(self.graph.successors(node_type))
        return parents[0] if parents else None


class CodeGenerator:
    """Generate Python module from node specifications."""

    def __init__(
        self,
        node_specs: List[Dict[str, Any]],
        token_suffix: str = "TokenNode",
        base_class: str = "TSNode",
    ):
        self.specs = {spec["type"]: spec for spec in node_specs}
        self.resolver = NameResolver(token_suffix)
        self.analyzer = InheritanceAnalyzer(node_specs)
        self.base_class = base_class
        self.class_names: Dict[str, str] = {}

    def _resolve_all_names(self) -> None:
        """Pre-resolve all class names."""
        for node_type, spec in self.specs.items():
            is_named = spec.get("named", True)
            self.class_names[node_type] = self.resolver.resolve(node_type, is_named)

    def _generate_class(self, node_type: str) -> str:
        """Generate a single node class."""
        spec = self.specs[node_type]
        class_name = self.class_names[node_type]

        # Determine parent class
        parent_type = self.analyzer.get_parent(node_type)
        parent_class = (
            self.class_names[parent_type]
            if parent_type and parent_type in self.class_names
            else self.base_class
        )

        # Get fields for __match_args__
        fields = spec.get("fields", {})
        match_args = ["type_name"] + list(fields.keys())

        # Start class definition
        lines = [f"class {class_name}({parent_class}):"]

        # Add docstring
        lines.append(f'    """Generated node for {node_type}."""')

        # Add __match_args__ if we have fields
        if fields:
            lines.append(f"    __match_args__ = {tuple(match_args)}")

        # Add typed field properties
        for field_name, field_spec in fields.items():
            lines.extend(self._generate_field_property(field_name, field_spec))

        # Add edit helper methods
        lines.extend(self._generate_edit_helpers(node_type, spec))

        # Add pass if class is empty
        if len(lines) == 2:  # Only class def and docstring
            lines.append("    pass")

        lines.append("")  # Empty line after class
        return "\n".join(lines)

    def _generate_field_property(
        self, field_name: str, field_spec: Dict[str, Any]
    ) -> List[str]:
        """Generate typed property for a named field."""
        types = field_spec.get("types", [])
        is_multiple = field_spec.get("multiple", False)
        is_required = field_spec.get("required", True)

        # Build type annotation
        if not types:
            type_hint = "TSNode"
        elif len(types) == 1:
            type_hint = self.class_names.get(types[0]["type"], "TSNode")
        else:
            type_names = [self.class_names.get(t["type"], "TSNode") for t in types]
            type_hint = " | ".join(type_names)

        if is_multiple:
            type_hint = f"List[{type_hint}]"
        if not is_required:
            type_hint = f"Optional[{type_hint}]"

        # Generate property
        lines = [
            f"    @property",
            f"    def {field_name}(self) -> {type_hint}:",
            f'        """Access {field_name} field."""',
        ]

        if is_multiple:
            lines.extend(
                [
                    f"        result = []",
                    f"        for child in self.children:",
                    f"            if child.field_name == '{field_name}':",
                    f"                result.append(child)",
                    f"        return result",
                ]
            )
        else:
            lines.extend(
                [
                    f"        for child in self.children:",
                    f"            if child.field_name == '{field_name}':",
                    f"                return child",
                    f"        return None"
                    if not is_required
                    else f"        raise ValueError(f'Required field {field_name} not found')",
                ]
            )

        lines.append("")
        return lines

    def _generate_edit_helpers(self, node_type: str, spec: Dict[str, Any]) -> List[str]:
        """Generate grammar-aware edit helper methods."""
        lines = []

        # insert_child method
        lines.extend(
            [
                "    def insert_child(self, index: int, child: TSNode) -> TSNode:",
                '        """Insert child at index with grammar validation."""',
                "        # TODO: Add grammar validation logic",
                "        new_children = list(self.children)",
                "        new_children.insert(index, child)",
                "        return self.model_copy(update={'children': new_children})",
                "",
            ]
        )

        # replace_child method
        lines.extend(
            [
                "    def replace_child(self, old_child: TSNode, new_child: TSNode) -> TSNode:",
                '        """Replace child with grammar validation."""',
                "        new_children = [",
                "            new_child if c == old_child else c",
                "            for c in self.children",
                "        ]",
                "        return self.model_copy(update={'children': new_children})",
                "",
            ]
        )

        # delete_child method
        lines.extend(
            [
                "    def delete_child(self, child: TSNode) -> TSNode:",
                '        """Delete child with grammar validation."""',
                "        new_children = [c for c in self.children if c != child]",
                "        return self.model_copy(update={'children': new_children})",
                "",
            ]
        )

        return lines

    def generate_module(self) -> str:
        """Generate complete Python module."""
        self._resolve_all_names()

        lines = [
            "# Generated by pydantree.codegen - DO NOT EDIT",
            "from __future__ import annotations",
            "",
            "from typing import List, Optional",
            "from pydantic import BaseModel",
            "from pydantree.core import TSNode",
            "",
            "# Registry for runtime node creation",
            "NODE_MAP: dict[str, type[TSNode]] = {}",
            "",
        ]

        # Generate classes in inheritance order
        for node_type in self.analyzer.get_inheritance_order():
            if node_type in self.specs:
                lines.append(self._generate_class(node_type))

                # Add to NODE_MAP
                class_name = self.class_names[node_type]
                lines.append(f"NODE_MAP[{node_type!r}] = {class_name}")
                lines.append("")

        # Auto-register when imported
        lines.extend(
            [
                "# Auto-register subclasses",
                "TSNode.register_subclasses(NODE_MAP)",
            ]
        )

        return "\n".join(lines)


def generate_from_node_types(
    json_path: str | Path,
    out_path: str | Path,
    token_suffix: str = "TokenNode",
    base_class: str = "TSNode",
) -> None:
    """
    Generate typed node classes from node-types.json.

    Args:
        json_path: Path to node-types.json file
        out_path: Output Python file path
        token_suffix: Suffix for anonymous token nodes
        base_class: Base class for generated nodes
    """
    json_path = Path(json_path)
    out_path = Path(out_path)

    # Load node specifications
    with json_path.open() as f:
        node_specs = json.load(f)

    # Generate module
    generator = CodeGenerator(node_specs, token_suffix, base_class)
    module_code = generator.generate_module()

    # Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        f.write(module_code)


if __name__ == "__main__":
    # CLI interface
    import sys

    if len(sys.argv) != 3:
        print("Usage: python codegen.py <node-types.json> <output.py>")
        sys.exit(1)

    generate_from_node_types(sys.argv[1], sys.argv[2])
