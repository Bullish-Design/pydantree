# pydantree/codegen/generator.py
from __future__ import annotations

import json
import textwrap
import keyword
from pathlib import Path
from typing import Any, Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

try:
    import rustworkx as rx
    HAS_RUSTWORKX = True
except ImportError:
    HAS_RUSTWORKX = False


class NameResolver:
    """Advanced name resolver with collision detection and optimization."""
    
    # Enhanced symbol mapping for common punctuation/operators
    SYMBOL_MAP = {
        # Single character symbols
        "(": "LeftParen", ")": "RightParen", "[": "LeftBracket", "]": "RightBracket",
        "{": "LeftBrace", "}": "RightBrace", "<": "LessThan", ">": "GreaterThan",
        ",": "Comma", ".": "Dot", ":": "Colon", ";": "Semicolon", "+": "Plus",
        "-": "Minus", "*": "Asterisk", "/": "Slash", "%": "Percent",
        "&": "Ampersand", "|": "Pipe", "^": "Caret", "~": "Tilde", "@": "At",
        "\\": "Backslash", "_": "Underscore", "=": "Equals", "?": "Question",
        "!": "Exclamation", "$": "Dollar", "#": "Hash", "`": "Backtick",
        "'": "SingleQuote", '"': "DoubleQuote",
        
        # Multi-character operators
        "==": "Equality", "!=": "NotEquals", "<=": "LessEquals", ">=": "GreaterEquals",
        "+=": "PlusEquals", "-=": "MinusEquals", "*=": "TimesEquals", "/=": "DivideEquals",
        "%=": "ModEquals", "&=": "AmpersandEquals", "|=": "PipeEquals", "^=": "CaretEquals",
        "@=": "AtEquals", "//": "FloorDiv", "//=": "FloorDivEquals", "**": "Power",
        "**=": "PowerEquals", "<<": "LeftShift", "<<=": "LeftShiftEquals",
        ">>": "RightShift", ">>=": "RightShiftEquals", "->": "Arrow", ":=": "Walrus",
        "<>": "NotEqualsAlt", "&&": "LogicalAnd", "||": "LogicalOr", "++": "Increment",
        "--": "Decrement", "=>": "FatArrow", "::": "DoubleColon", "...": "Ellipsis",
        
        # Language-specific keywords
        "is not": "IsNot", "not in": "NotIn", "except*": "ExceptStar",
        "and": "LogicalAnd", "or": "LogicalOr", "not": "LogicalNot",
        "in": "InOperator", "is": "IsOperator", "del": "Delete",
        "lambda": "Lambda", "yield": "Yield", "await": "Await",
        "async": "Async", "with": "With", "as": "As", "from": "From",
        "import": "Import", "global": "Global", "nonlocal": "Nonlocal",
        "assert": "Assert", "pass": "Pass", "break": "Break", "continue": "Continue",
        "return": "Return", "raise": "Raise", "try": "Try", "except": "Except",
        "finally": "Finally", "if": "If", "elif": "Elif", "else": "Else",
        "for": "For", "while": "While", "def": "Def", "class": "Class",
        "match": "Match", "case": "Case", "type": "Type",
        
        # Literals
        "true": "TrueLiteral", "false": "FalseLiteral", "null": "NullLiteral",
        "none": "NoneLiteral", "undefined": "UndefinedLiteral",
    }
    
    # Reserved Python keywords that can't be used as class names
    PYTHON_KEYWORDS = set(keyword.kwlist) | {
        'True', 'False', 'None', '__name__', '__main__', '__file__',
        'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple',
        'type', 'object', 'super', 'property', 'classmethod', 'staticmethod'
    }
    
    def __init__(self, token_suffix: str = "TokenNode", base_class: str = "TSNode"):
        self.token_suffix = token_suffix
        self.base_class = base_class
        self.seen: Set[str] = set()
        self.type_mapping: Dict[str, str] = {}
        self.collision_count = 0
    
    def resolve(self, node_type: str, is_named: bool = True) -> str:
        """Convert node type to Python class name with collision handling."""
        # Check cache first
        cache_key = f"{node_type}:{is_named}"
        if cache_key in self.type_mapping:
            return self.type_mapping[cache_key]
        
        # Apply symbol mapping first
        if node_type in self.SYMBOL_MAP:
            base_name = self.SYMBOL_MAP[node_type]
        else:
            # Convert to PascalCase
            base_name = self._to_pascal_case(node_type)
        
        # Add appropriate suffix
        if not is_named:
            class_name = base_name + self.token_suffix
        else:
            class_name = base_name + "Node"
        
        # Handle Python keyword conflicts
        if class_name in self.PYTHON_KEYWORDS:
            class_name = f"{class_name}_"
        
        # Ensure uniqueness
        original_name = class_name
        counter = 1
        while class_name in self.seen:
            class_name = f"{original_name}{counter}"
            counter += 1
            self.collision_count += 1
        
        self.seen.add(class_name)
        self.type_mapping[cache_key] = class_name
        return class_name
    
    def _to_pascal_case(self, name: str) -> str:
        """Convert snake_case or kebab-case to PascalCase."""
        if not name:
            return "Empty"
        
        # Handle special characters
        name = name.replace("-", "_").replace(".", "_")
        
        # Split and capitalize
        parts = [part.capitalize() for part in name.split("_") if part]
        
        if not parts:
            return "Unknown"
        
        result = "".join(parts)
        
        # Ensure it starts with a letter
        if result and not result[0].isalpha():
            result = "Node" + result
        
        return result or "Unknown"
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get resolver statistics."""
        return {
            'total_resolved': len(self.seen),
            'collision_count': self.collision_count,
            'mapping_cache_size': len(self.type_mapping),
            'symbol_mappings_used': sum(1 for k in self.type_mapping.keys() 
                                       if k.split(':')[0] in self.SYMBOL_MAP)
        }


@dataclass
class FieldInfo:
    """Information about a node field."""
    name: str
    types: List[str]
    is_multiple: bool = False
    is_required: bool = True
    is_optional: bool = False
    description: Optional[str] = None


@dataclass
class NodeSpec:
    """Specification for generating a node class."""
    type_name: str
    class_name: str
    is_named: bool
    fields: List[FieldInfo] = field(default_factory=list)
    supertypes: List[str] = field(default_factory=list)
    subtypes: List[str] = field(default_factory=list)
    children: Set[str] = field(default_factory=set)


class InheritanceAnalyzer:
    """Analyze inheritance relationships with graph-based optimization."""
    
    def __init__(self, node_specs: List[Dict[str, Any]]):
        self.specs = {spec["type"]: spec for spec in node_specs}
        self.inheritance_graph = None
        self.type_hierarchy: Dict[str, List[str]] = {}
        self.common_ancestors: Dict[str, str] = {}
        
        if HAS_RUSTWORKX:
            self._build_inheritance_graph()
        else:
            self._build_simple_hierarchy()
    
    def _build_inheritance_graph(self) -> None:
        """Build inheritance graph using rustworkx for advanced analysis."""
        self.inheritance_graph = rx.PyDiGraph()
        node_indices = {}
        
        # Add all node types
        for node_type in self.specs:
            index = self.inheritance_graph.add_node(node_type)
            node_indices[node_type] = index
        
        # Add inheritance edges
        for spec in self.specs.values():
            if "subtypes" in spec:
                parent_type = spec["type"]
                parent_idx = node_indices[parent_type]
                
                for subtype_spec in spec["subtypes"]:
                    child_type = subtype_spec["type"]
                    if child_type in self.specs:
                        child_idx = node_indices[child_type]
                        # Edge from child to parent
                        self.inheritance_graph.add_edge(child_idx, parent_idx, {})
        
        # Analyze hierarchy
        self._analyze_inheritance_patterns()
    
    def _build_simple_hierarchy(self) -> None:
        """Fallback hierarchy building without rustworkx."""
        for spec in self.specs.values():
            if "subtypes" in spec:
                parent_type = spec["type"]
                for subtype_spec in spec["subtypes"]:
                    child_type = subtype_spec["type"]
                    if child_type in self.specs:
                        if parent_type not in self.type_hierarchy:
                            self.type_hierarchy[parent_type] = []
                        self.type_hierarchy[parent_type].append(child_type)
    
    def _analyze_inheritance_patterns(self) -> None:
        """Analyze inheritance patterns for optimization opportunities."""
        if not self.inheritance_graph:
            return
        
        # Find common ancestor patterns
        node_types = list(self.specs.keys())
        
        for i, type1 in enumerate(node_types):
            for type2 in node_types[i+1:]:
                try:
                    ancestors1 = self._get_ancestors(type1)
                    ancestors2 = self._get_ancestors(type2)
                    
                    common = ancestors1 & ancestors2
                    if common:
                        # Find most specific common ancestor
                        most_specific = self._find_most_specific_ancestor(common)
                        key = tuple(sorted([type1, type2]))
                        self.common_ancestors[key] = most_specific
                except Exception:
                    continue
    
    def _get_ancestors(self, node_type: str) -> Set[str]:
        """Get all ancestors of a node type."""
        if not self.inheritance_graph:
            return set()
        
        try:
            node_indices = {
                self.inheritance_graph.get_node_data(i): i 
                for i in self.inheritance_graph.node_indices()
            }
            
            if node_type not in node_indices:
                return set()
            
            node_idx = node_indices[node_type]
            ancestors = set()
            
            # BFS to find all ancestors
            queue = [node_idx]
            visited = set()
            
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                
                for parent_idx in self.inheritance_graph.successors(current):
                    parent_type = self.inheritance_graph.get_node_data(parent_idx)
                    ancestors.add(parent_type)
                    queue.append(parent_idx)
            
            return ancestors
        except Exception:
            return set()
    
    def _find_most_specific_ancestor(self, ancestors: Set[str]) -> Optional[str]:
        """Find the most specific common ancestor."""
        if not ancestors:
            return None
        
        # Simple heuristic: prefer shorter type names (usually more general)
        return min(ancestors, key=len)
    
    def get_parent(self, node_type: str) -> Optional[str]:
        """Get direct parent of a node type."""
        if not self.inheritance_graph:
            # Fallback logic
            for parent_type, children in self.type_hierarchy.items():
                if node_type in children:
                    return parent_type
            return None
        
        try:
            node_indices = {
                self.inheritance_graph.get_node_data(i): i 
                for i in self.inheritance_graph.node_indices()
            }
            
            if node_type not in node_indices:
                return None
            
            node_idx = node_indices[node_type]
            parents = list(self.inheritance_graph.successors(node_idx))
            
            if parents:
                parent_idx = parents[0]  # Take first parent
                return self.inheritance_graph.get_node_data(parent_idx)
            
            return None
        except Exception:
            return None
    
    def get_inheritance_order(self) -> List[str]:
        """Get topological ordering for class generation."""
        if not self.inheritance_graph:
            # Simple fallback ordering
            return list(self.specs.keys())
        
        try:
            indices = rx.topological_sort(self.inheritance_graph)
            return [self.inheritance_graph.get_node_data(idx) for idx in reversed(indices)]
        except Exception:
            return list(self.specs.keys())


class CodeGenerator:
    """Enhanced code generator with inheritance analysis and optimization."""
    
    def __init__(self,
                 node_specs: List[Dict[str, Any]],
                 language: str = "generic",
                 token_suffix: str = "TokenNode",
                 base_class: str = "TSNode",
                 include_metadata: bool = True,
                 format_code: bool = True):
        
        self.specs = {spec["type"]: spec for spec in node_specs}
        self.language = language
        self.resolver = NameResolver(token_suffix, base_class)
        self.analyzer = InheritanceAnalyzer(node_specs)
        self.base_class = base_class
        self.include_metadata = include_metadata
        self.format_code = format_code
        
        # Generate node specifications
        self.node_specs: Dict[str, NodeSpec] = {}
        self._analyze_all_nodes()
    
    def _analyze_all_nodes(self) -> None:
        """Analyze all nodes and build specifications."""
        for node_type, spec in self.specs.items():
            is_named = spec.get("named", True)
            class_name = self.resolver.resolve(node_type, is_named)
            
            # Extract field information
            fields = []
            if "fields" in spec:
                for field_name, field_spec in spec["fields"].items():
                    field_info = FieldInfo(
                        name=field_name,
                        types=[t.get("type", "TSNode") for t in field_spec.get("types", [])],
                        is_multiple=field_spec.get("multiple", False),
                        is_required=field_spec.get("required", True)
                    )
                    fields.append(field_info)
            
            # Extract inheritance information
            supertypes = []
            subtypes = []
            if "subtypes" in spec:
                subtypes = [s["type"] for s in spec["subtypes"] if s["type"] in self.specs]
            
            # Find parent
            parent = self.analyzer.get_parent(node_type)
            if parent:
                supertypes.append(parent)
            
            self.node_specs[node_type] = NodeSpec(
                type_name=node_type,
                class_name=class_name,
                is_named=is_named,
                fields=fields,
                supertypes=supertypes,
                subtypes=subtypes
            )
    
    def generate_module(self) -> str:
        """Generate complete Python module with optimized class hierarchy."""
        lines = self._generate_header()
        lines.extend(self._generate_mixins())
        lines.extend(self._generate_classes())
        lines.extend(self._generate_registry())
        lines.extend(self._generate_metadata())
        
        module_code = "\n".join(lines)
        
        if self.format_code:
            return self._format_generated_code(module_code)
        
        return module_code
    
    def _generate_header(self) -> List[str]:
        """Generate module header with imports and metadata."""
        return [
            f"# Generated by pydantree.codegen - DO NOT EDIT",
            f"# Language: {self.language}",
            f"# Generated classes: {len(self.node_specs)}",
            f"# Inheritance relationships: {len([s for s in self.node_specs.values() if s.supertypes])}",
            "",
            "from __future__ import annotations",
            "",
            "from typing import List, Optional, Union, Dict, Any",
            "from pydantic import Field",
            f"from ..core.nodes import {self.base_class}",
            "",
            "# Registry for runtime node creation",
            "NODE_MAP: Dict[str, type[TSNode]] = {}",
            "",
            "# Metadata for generated classes",
            "CLASS_METADATA: Dict[str, Dict[str, Any]] = {}",
            "",
        ]
    
    def _generate_mixins(self) -> List[str]:
        """Generate mixin classes for common functionality."""
        lines = [
            "# Mixin classes for enhanced functionality",
            "",
            "class FieldAccessMixin:",
            '    """Mixin providing enhanced field access methods."""',
            "",
            "    def get_field_value(self, field_name: str, default=None):",
            '        """Get field value with fallback to child lookup."""',
            "        # First try direct attribute access",
            "        if hasattr(self, field_name):",
            "            return getattr(self, field_name)",
            "        ",
            "        # Fallback to child field lookup",
            "        return self.child_by_field_name(field_name) or default",
            "",
            "    def has_field(self, field_name: str) -> bool:",
            '        """Check if field exists."""',
            "        return (hasattr(self, field_name) or ",
            "                self.child_by_field_name(field_name) is not None)",
            "",
            "",
            "class ValidationMixin:",
            '    """Mixin providing validation capabilities."""',
            "",
            "    def validate_structure(self) -> List[str]:",
            '        """Validate node structure and return issues."""',
            "        issues = []",
            "        ",
            "        # Validate required fields",
            "        metadata = CLASS_METADATA.get(self.__class__.__name__, {})",
            "        required_fields = metadata.get('required_fields', [])",
            "        ",
            "        for field_name in required_fields:",
            "            if not self.has_field(field_name):",
            "                issues.append(f'Missing required field: {field_name}')",
            "        ",
            "        return issues",
            "",
            "",
        ]
        return lines
    
    def _generate_classes(self) -> List[str]:
        """Generate node classes in inheritance order."""
        lines = []
        
        # Generate in topological order
        for node_type in self.analyzer.get_inheritance_order():
            if node_type in self.node_specs:
                spec = self.node_specs[node_type]
                lines.extend(self._generate_single_class(spec))
                lines.append("")  # Empty line between classes
        
        return lines
    
    def _generate_single_class(self, spec: NodeSpec) -> List[str]:
        """Generate a single node class."""
        lines = []
        
        # Determine parent class
        if spec.supertypes:
            parent_type = spec.supertypes[0]
            if parent_type in self.node_specs:
                parent_class = self.node_specs[parent_type].class_name
            else:
                parent_class = self.base_class
        else:
            parent_class = self.base_class
        
        # Add mixins
        mixins = ["FieldAccessMixin", "ValidationMixin"]
        parent_with_mixins = f"{parent_class}, {', '.join(mixins)}"
        
        # Class definition
        lines.append(f"class {spec.class_name}({parent_with_mixins}):")
        
        # Docstring
        docstring = f'"""Generated node class for {spec.type_name}."""'
        lines.append(f"    {docstring}")
        
        # Add __match_args__ for pattern matching
        if spec.fields:
            match_args = ["type_name"] + [f.name for f in spec.fields]
            lines.append(f"    __match_args__ = {tuple(match_args)}")
        
        # Generate field properties
        field_lines = self._generate_field_properties(spec)
        if field_lines:
            lines.append("")
            lines.extend(field_lines)
        
        # Add utility methods
        utility_lines = self._generate_utility_methods(spec)
        if utility_lines:
            lines.append("")
            lines.extend(utility_lines)
        
        # If no content was added, add pass
        if len(lines) == 2:  # Only class definition and docstring
            lines.append("    pass")
        
        return lines
    
    def _generate_field_properties(self, spec: NodeSpec) -> List[str]:
        """Generate typed field properties."""
        lines = []
        
        for field in spec.fields:
            # Build type annotation
            if not field.types:
                type_hint = self.base_class
            elif len(field.types) == 1:
                type_hint = self._resolve_type_hint(field.types[0])
            else:
                type_hints = [self._resolve_type_hint(t) for t in field.types]
                type_hint = " | ".join(type_hints)
            
            if field.is_multiple:
                type_hint = f"List[{type_hint}]"
            if not field.is_required:
                type_hint = f"Optional[{type_hint}]"
            
            # Property method
            lines.extend([
                f"    @property",
                f"    def {field.name}(self) -> {type_hint}:",
                f'        """Access {field.name} field."""'
            ])
            
            if field.is_multiple:
                lines.extend([
                    f"        result = []",
                    f"        for child in self.children:",
                    f"            if child.field_name == '{field.name}':",
                    f"                result.append(child)",
                    f"        return result"
                ])
            else:
                if field.is_required:
                    lines.extend([
                        f"        child = self.child_by_field_name('{field.name}')",
                        f"        if child is None:",
                        f"            raise ValueError(f'Required field {field.name} not found')",
                        f"        return child"
                    ])
                else:
                    lines.extend([
                        f"        return self.child_by_field_name('{field.name}')"
                    ])
            
            lines.append("")  # Empty line after property
        
        return lines
    
    def _generate_utility_methods(self, spec: NodeSpec) -> List[str]:
        """Generate utility methods for the class."""
        lines = []
        
        # Generate field list method
        if spec.fields:
            field_names = [f.name for f in spec.fields]
            lines.extend([
                f"    def get_field_names(self) -> List[str]:",
                f'        """Get list of all field names."""',
                f"        return {field_names}",
                ""
            ])
        
        # Generate semantic type method for language-specific nodes
        if self.language != "generic":
            lines.extend([
                f"    def get_semantic_type(self) -> str:",
                f'        """Get semantic type for this node."""',
                f"        return '{self._infer_semantic_type(spec)}'",
                ""
            ])
        
        return lines
    
    def _resolve_type_hint(self, type_name: str) -> str:
        """Resolve a type name to a proper type hint."""
        if type_name in self.node_specs:
            return self.node_specs[type_name].class_name
        elif type_name == "TSNode":
            return self.base_class
        else:
            # Return as-is for unknown types
            return type_name
    
    def _infer_semantic_type(self, spec: NodeSpec) -> str:
        """Infer semantic type from node specification."""
        type_name_lower = spec.type_name.lower()
        
        if "function" in type_name_lower:
            return "function"
        elif "class" in type_name_lower:
            return "class"
        elif "variable" in type_name_lower or "identifier" in type_name_lower:
            return "variable"
        elif "import" in type_name_lower:
            return "import"
        elif "comment" in type_name_lower:
            return "comment"
        elif "string" in type_name_lower or "literal" in type_name_lower:
            return "literal"
        else:
            return "unknown"
    
    def _generate_registry(self) -> List[str]:
        """Generate NODE_MAP registry."""
        lines = [
            "# Register all generated classes",
            ""
        ]
        
        for node_type, spec in self.node_specs.items():
            lines.append(f"NODE_MAP[{node_type!r}] = {spec.class_name}")
        
        lines.extend([
            "",
            "# Auto-register subclasses when imported",
            f"{self.base_class}.register_subclasses(NODE_MAP)",
            ""
        ])
        
        return lines
    
    def _generate_metadata(self) -> List[str]:
        """Generate class metadata for runtime introspection."""
        if not self.include_metadata:
            return []
        
        lines = [
            "# Generate metadata for runtime introspection",
            ""
        ]
        
        for node_type, spec in self.node_specs.items():
            metadata = {
                'type_name': spec.type_name,
                'is_named': spec.is_named,
                'field_count': len(spec.fields),
                'required_fields': [f.name for f in spec.fields if f.is_required],
                'optional_fields': [f.name for f in spec.fields if not f.is_required],
                'multiple_fields': [f.name for f in spec.fields if f.is_multiple],
                'parent_types': spec.supertypes,
                'child_types': spec.subtypes,
                'language': self.language
            }
            
            lines.append(f"CLASS_METADATA['{spec.class_name}'] = {metadata!r}")
        
        return lines
    
    def _format_generated_code(self, code: str) -> str:
        """Format generated code using black if available."""
        try:
            import black
            
            # Format with black
            formatted = black.format_str(code, mode=black.Mode(
                target_versions={black.TargetVersion.PY311},
                line_length=120,
                string_normalization=True,
                experimental_string_processing=False
            ))
            return formatted
        except ImportError:
            # Fallback: basic formatting
            return self._basic_format(code)
    
    def _basic_format(self, code: str) -> str:
        """Basic code formatting without external dependencies."""
        lines = code.split('\n')
        formatted_lines = []
        
        for line in lines:
            # Remove trailing whitespace
            line = line.rstrip()
            
            # Ensure no more than 2 consecutive empty lines
            if line == "":
                if (len(formatted_lines) >= 2 and 
                    formatted_lines[-1] == "" and 
                    formatted_lines[-2] == ""):
                    continue
            
            formatted_lines.append(line)
        
        # Remove trailing empty lines
        while formatted_lines and formatted_lines[-1] == "":
            formatted_lines.pop()
        
        return '\n'.join(formatted_lines) + '\n'
    
    def get_generation_statistics(self) -> Dict[str, Any]:
        """Get statistics about the code generation process."""
        total_fields = sum(len(spec.fields) for spec in self.node_specs.values())
        inheritance_count = len([s for s in self.node_specs.values() if s.supertypes])
        
        # Field type distribution
        field_types = []
        for spec in self.node_specs.values():
            for field in spec.fields:
                field_types.extend(field.types)
        
        from collections import Counter
        type_distribution = Counter(field_types)
        
        return {
            'total_classes': len(self.node_specs),
            'total_fields': total_fields,
            'inheritance_relationships': inheritance_count,
            'language': self.language,
            'field_type_distribution': dict(type_distribution.most_common(10)),
            'resolver_stats': self.resolver.get_statistics(),
            'has_inheritance_graph': self.analyzer.inheritance_graph is not None,
            'generation_optimizations': {
                'mixins_used': True,
                'field_properties': True,
                'metadata_included': self.include_metadata,
                'code_formatted': self.format_code
            }
        }


def generate_from_node_types(json_path: Union[str, Path],
                           out_path: Union[str, Path],
                           language: str = "generic",
                           token_suffix: str = "TokenNode",
                           base_class: str = "TSNode",
                           include_metadata: bool = True,
                           format_code: bool = True) -> Dict[str, Any]:
    """
    Generate typed node classes from node-types.json with enhanced features.
    
    Args:
        json_path: Path to node-types.json file
        out_path: Output Python file path
        language: Target language name for semantic inference
        token_suffix: Suffix for anonymous token nodes
        base_class: Base class for generated nodes
        include_metadata: Include runtime metadata
        format_code: Format generated code with black
    
    Returns:
        Dictionary with generation statistics
    """
    json_path = Path(json_path)
    out_path = Path(out_path)
    
    if not json_path.exists():
        raise FileNotFoundError(f"Node types file not found: {json_path}")
    
    # Load node specifications
    with json_path.open() as f:
        node_specs = json.load(f)
    
    # Generate module
    generator = CodeGenerator(
        node_specs=node_specs,
        language=language,
        token_suffix=token_suffix,
        base_class=base_class,
        include_metadata=include_metadata,
        format_code=format_code
    )
    
    module_code = generator.generate_module()
    
    # Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        f.write(module_code)
    
    # Return statistics
    stats = generator.get_generation_statistics()
    stats['output_file'] = str(out_path)
    stats['output_size_kb'] = out_path.stat().st_size / 1024
    stats['lines_generated'] = len(module_code.splitlines())
    
    return stats


def discover_node_types_files(search_paths: List[Path]) -> List[Path]:
    """Discover node-types.json files in search paths."""
    discovered = []
    
    for search_path in search_paths:
        if search_path.is_file() and search_path.name == "node-types.json":
            discovered.append(search_path)
        elif search_path.is_dir():
            # Search recursively
            discovered.extend(search_path.rglob("node-types.json"))
    
    return discovered


def validate_node_types_json(json_path: Path) -> List[str]:
    """Validate node-types.json file and return issues."""
    issues = []
    
    try:
        with json_path.open() as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]
    except Exception as e:
        return [f"Failed to read file: {e}"]
    
    if not isinstance(data, list):
        issues.append("Root element must be an array")
        return issues
    
    for i, spec in enumerate(data):
        if not isinstance(spec, dict):
            issues.append(f"Item {i}: Must be an object")
            continue
        
        if "type" not in spec:
            issues.append(f"Item {i}: Missing 'type' field")
        
        if "named" not in spec:
            issues.append(f"Item {i}: Missing 'named' field")
        
        # Validate fields structure
        if "fields" in spec:
            fields = spec["fields"]
            if not isinstance(fields, dict):
                issues.append(f"Item {i}: 'fields' must be an object")
            else:
                for field_name, field_spec in fields.items():
                    if not isinstance(field_spec, dict):
                        issues.append(f"Item {i}, field '{field_name}': Must be an object")
                    elif "types" not in field_spec:
                        issues.append(f"Item {i}, field '{field_name}': Missing 'types'")
    
    return issues
