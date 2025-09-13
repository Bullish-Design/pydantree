# pydantree/languages/python/python_analyzer.py
from typing import List, Optional

from ..base import LanguageAnalyzer, SemanticNode, SemanticRole
from ...core.nodes import TSNode


class PythonAnalyzer(LanguageAnalyzer):
    """Provides semantic analysis for Python source code."""

    def analyze_semantics(self, node: TSNode, scope_stack: List[SemanticNode] | None = None) -> SemanticNode:
        """
        Recursively builds a semantic tree from a Python AST.
        This is a simplified implementation focusing on key structures.
        """
        if scope_stack is None:
            scope_stack = []

        role = self._get_semantic_role(node)
        current_sem_node = SemanticNode(
            original_node=node,
            role=role,
            name=self._extract_name(node, role),
            docstring=self._extract_docstring(node),
            parent_scope=scope_stack[-1] if scope_stack else None,
        )

        # For scopes like functions or classes, add to stack for children
        is_scope = role in {SemanticRole.FUNCTION, SemanticRole.CLASS, SemanticRole.MODULE}
        if is_scope:
            scope_stack.append(current_sem_node)

        # Recursively analyze children
        for child in node.children:
            child_sem_node = self.analyze_semantics(child, scope_stack)
            current_sem_node.children.append(child_sem_node)

        if is_scope:
            scope_stack.pop()

        return current_sem_node

    def extract_definitions(self, root: TSNode) -> List[SemanticNode]:
        """Extracts top-level function and class definitions."""
        definitions = []
        # Find all function and class definitions in the tree
        func_nodes = root.find_all_by_type("function_definition")
        class_nodes = root.find_all_by_type("class_definition")

        for node in func_nodes + class_nodes:
            # We perform a partial analysis just for this definition
            definitions.append(self.analyze_semantics(node))
        return definitions

    def _get_semantic_role(self, node: TSNode) -> SemanticRole:
        """Maps a Python tree-sitter node type to a Pydantree SemanticRole."""
        type_map = {
            "module": SemanticRole.MODULE,
            "function_definition": SemanticRole.FUNCTION,
            "class_definition": SemanticRole.CLASS,
            "import_statement": SemanticRole.IMPORT,
            "import_from_statement": SemanticRole.IMPORT,
        }
        return type_map.get(node.type_name, SemanticRole.VARIABLE)  # Fallback

    def _extract_name(self, node: TSNode, role: SemanticRole) -> Optional[str]:
        """Extracts the name identifier from a definition node."""
        if role in {SemanticRole.FUNCTION, SemanticRole.CLASS}:
            name_node = node.child_by_field_name("name")
            return name_node.text if name_node else None
        return None

    def _extract_docstring(self, node: TSNode) -> Optional[str]:
        """Extracts a docstring from a function or class body."""
        if node.type_name not in {"function_definition", "class_definition", "module"}:
            return None

        body_node = node.child_by_field_name("body")
        if not body_node or not body_node.children:
            return None

        # The docstring is the first statement if it's an expression
        # statement containing a string literal.
        first_statement = body_node.children[0]
        if first_statement.type_name == "expression_statement":
            string_node = first_statement.find_all_by_type("string")
            if string_node:
                # Use ast.literal_eval to safely evaluate the string content
                try:
                    import ast

                    return ast.literal_eval(string_node[0].text)
                except (ValueError, SyntaxError):
                    return string_node[0].text  # Fallback to raw text
        return None
