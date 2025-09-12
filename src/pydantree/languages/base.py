# pydantree/languages/base.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Type, Union, Callable, Iterator
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict

from ..core.nodes import TSNode
from ..core.parsers import Parser
from ..processing.collections import NodeGroup
from .registry import LanguageConfig, LanguageFeature


class SemanticRole(Enum):
    """Standard semantic roles for AST nodes across languages."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    PARAMETER = "parameter"
    FIELD = "field"
    PROPERTY = "property"
    MODULE = "module"
    NAMESPACE = "namespace"
    INTERFACE = "interface"
    ENUM = "enum"
    STRUCT = "struct"
    TRAIT = "trait"
    DECORATOR = "decorator"
    ANNOTATION = "annotation"
    COMMENT = "comment"
    LITERAL = "literal"
    IDENTIFIER = "identifier"
    OPERATOR = "operator"
    KEYWORD = "keyword"
    CONTROL_FLOW = "control_flow"
    IMPORT = "import"
    EXPORT = "export"


@dataclass
class SemanticNode:
    """Semantic representation of a node with language-agnostic properties."""
    original_node: TSNode
    role: SemanticRole
    name: Optional[str] = None
    qualified_name: Optional[str] = None
    visibility: Optional[str] = None
    modifiers: Set[str] = None
    type_info: Optional[str] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None
    attributes: Dict[str, Any] = None
    parent_scope: Optional[SemanticNode] = None
    children: List[SemanticNode] = None
    
    def __post_init__(self):
        if self.modifiers is None:
            self.modifiers = set()
        if self.attributes is None:
            self.attributes = {}
        if self.children is None:
            self.children = []


class LanguageAnalyzer(ABC):
    """Abstract base for language-specific semantic analysis."""
    
    def __init__(self, config: LanguageConfig, parser: Parser):
        self.config = config
        self.parser = parser
        self._semantic_cache: Dict[str, SemanticNode] = {}
    
    @abstractmethod
    def analyze_semantics(self, node: TSNode) -> SemanticNode:
        """Analyze a node and extract semantic information."""
        pass
    
    @abstractmethod
    def extract_functions(self, root: TSNode) -> List[SemanticNode]:
        """Extract all function definitions from the AST."""
        pass
    
    @abstractmethod
    def extract_classes(self, root: TSNode) -> List[SemanticNode]:
        """Extract all class definitions from the AST."""
        pass
    
    @abstractmethod
    def extract_imports(self, root: TSNode) -> List[SemanticNode]:
        """Extract all import statements from the AST."""
        pass
    
    @abstractmethod
    def extract_variables(self, root: TSNode) -> List[SemanticNode]:
        """Extract all variable declarations from the AST."""
        pass
    
    def get_supported_features(self) -> Set[LanguageFeature]:
        """Get the language features this analyzer supports."""
        return self.config.features
    
    def analyze_file(self, file_path: Path) -> SemanticNode:
        """Analyze an entire file and return semantic representation."""
        root_node = self.parser.parse_file(file_path)
        return self.analyze_semantics(root_node)
    
    def extract_all_symbols(self, root: TSNode) -> Dict[SemanticRole, List[SemanticNode]]:
        """Extract all symbols grouped by semantic role."""
        symbols = {}
        
        if LanguageFeature.FUNCTIONS in self.config.features:
            symbols[SemanticRole.FUNCTION] = self.extract_functions(root)
        
        if LanguageFeature.CLASSES in self.config.features:
            symbols[SemanticRole.CLASS] = self.extract_classes(root)
        
        if LanguageFeature.MODULES in self.config.features:
            symbols[SemanticRole.IMPORT] = self.extract_imports(root)
        
        symbols[SemanticRole.VARIABLE] = self.extract_variables(root)
        
        return symbols
    
    def clear_cache(self):
        """Clear semantic analysis cache."""
        self._semantic_cache.clear()


class LanguageTransformer(ABC):
    """Abstract base for language-specific AST transformations."""
    
    def __init__(self, config: LanguageConfig):
        self.config = config
        self._transformation_rules: List[Callable] = []
    
    @abstractmethod
    def transform_node(self, node: TSNode, context: Dict[str, Any] = None) -> TSNode:
        """Transform a single node based on language-specific rules."""
        pass
    
    @abstractmethod
    def transform_tree(self, root: TSNode, context: Dict[str, Any] = None) -> TSNode:
        """Transform an entire AST tree."""
        pass
    
    def add_transformation_rule(self, rule: Callable[[TSNode], TSNode]):
        """Add a custom transformation rule."""
        self._transformation_rules.append(rule)
    
    def apply_rules(self, node: TSNode) -> TSNode:
        """Apply all registered transformation rules to a node."""
        result = node
        for rule in self._transformation_rules:
            result = rule(result)
        return result


class LanguageFormatter(ABC):
    """Abstract base for language-specific code formatting."""
    
    def __init__(self, config: LanguageConfig):
        self.config = config
        self.formatting_options = self._get_default_options()
    
    @abstractmethod
    def format_node(self, node: TSNode, options: Dict[str, Any] = None) -> str:
        """Format a single node as source code."""
        pass
    
    @abstractmethod
    def format_tree(self, root: TSNode, options: Dict[str, Any] = None) -> str:
        """Format an entire AST tree as source code."""
        pass
    
    @abstractmethod
    def _get_default_options(self) -> Dict[str, Any]:
        """Get default formatting options for this language."""
        pass
    
    def set_formatting_option(self, key: str, value: Any):
        """Set a formatting option."""
        self.formatting_options[key] = value
    
    def get_indentation(self, level: int) -> str:
        """Get indentation string for the specified level."""
        indent_char = self.formatting_options.get('indent_char', ' ')
        indent_size = self.formatting_options.get('indent_size', 4)
        return indent_char * (indent_size * level)


class LanguageValidator(ABC):
    """Abstract base for language-specific validation and linting."""
    
    def __init__(self, config: LanguageConfig):
        self.config = config
        self._rules: Dict[str, Callable] = {}
    
    @abstractmethod
    def validate_syntax(self, node: TSNode) -> List[Dict[str, Any]]:
        """Validate syntax and return list of issues."""
        pass
    
    @abstractmethod
    def validate_semantics(self, semantic_node: SemanticNode) -> List[Dict[str, Any]]:
        """Validate semantic correctness."""
        pass
    
    def add_validation_rule(self, name: str, rule: Callable[[TSNode], List[Dict[str, Any]]]):
        """Add a custom validation rule."""
        self._rules[name] = rule
    
    def validate_with_rules(self, node: TSNode) -> List[Dict[str, Any]]:
        """Apply all registered validation rules."""
        issues = []
        for rule_name, rule in self._rules.items():
            try:
                rule_issues = rule(node)
                for issue in rule_issues:
                    issue['rule'] = rule_name
                issues.extend(rule_issues)
            except Exception as e:
                issues.append({
                    'type': 'validation_error',
                    'rule': rule_name,
                    'message': f"Validation rule failed: {e}",
                    'severity': 'error'
                })
        return issues


class Language(ABC):
    """Abstract base class for language implementations."""
    
    def __init__(self, config: LanguageConfig):
        self.config = config
        self.name = config.name
        self.display_name = config.display_name
        
        # Core components (to be implemented by subclasses)
        self._parser: Optional[Parser] = None
        self._analyzer: Optional[LanguageAnalyzer] = None
        self._transformer: Optional[LanguageTransformer] = None
        self._formatter: Optional[LanguageFormatter] = None
        self._validator: Optional[LanguageValidator] = None
        
        # Initialize components
        self._initialize_components()
    
    @abstractmethod
    def _initialize_components(self):
        """Initialize language-specific components."""
        pass
    
    @property
    def parser(self) -> Parser:
        """Get the parser for this language."""
        if self._parser is None:
            raise RuntimeError(f"Parser not initialized for {self.name}")
        return self._parser
    
    @property
    def analyzer(self) -> LanguageAnalyzer:
        """Get the semantic analyzer for this language."""
        if self._analyzer is None:
            raise RuntimeError(f"Analyzer not initialized for {self.name}")
        return self._analyzer
    
    @property
    def transformer(self) -> LanguageTransformer:
        """Get the transformer for this language."""
        if self._transformer is None:
            raise RuntimeError(f"Transformer not initialized for {self.name}")
        return self._transformer
    
    @property
    def formatter(self) -> LanguageFormatter:
        """Get the formatter for this language."""
        if self._formatter is None:
            raise RuntimeError(f"Formatter not initialized for {self.name}")
        return self._formatter
    
    @property
    def validator(self) -> LanguageValidator:
        """Get the validator for this language."""
        if self._validator is None:
            raise RuntimeError(f"Validator not initialized for {self.name}")
        return self._validator
    
    # High-level API methods
    def parse_file(self, file_path: Path) -> TSNode:
        """Parse a file and return the AST."""
        return self.parser.parse_file(file_path)
    
    def parse_code(self, code: str) -> TSNode:
        """Parse code string and return the AST."""
        return self.parser.parse(code)
    
    def analyze_file(self, file_path: Path) -> SemanticNode:
        """Analyze a file and return semantic representation."""
        return self.analyzer.analyze_file(file_path)
    
    def analyze_code(self, code: str) -> SemanticNode:
        """Analyze code string and return semantic representation."""
        ast = self.parse_code(code)
        return self.analyzer.analyze_semantics(ast)
    
    def extract_symbols(self, file_path: Path) -> Dict[SemanticRole, List[SemanticNode]]:
        """Extract all symbols from a file."""
        ast = self.parse_file(file_path)
        return self.analyzer.extract_all_symbols(ast)
    
    def format_file(self, file_path: Path, options: Dict[str, Any] = None) -> str:
        """Format a file and return formatted code."""
        ast = self.parse_file(file_path)
        return self.formatter.format_tree(ast, options)
    
    def validate_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Validate a file and return list of issues."""
        ast = self.parse_file(file_path)
        syntax_issues = self.validator.validate_syntax(ast)
        
        # Add semantic validation if analyzer is available
        try:
            semantic_node = self.analyzer.analyze_semantics(ast)
            semantic_issues = self.validator.validate_semantics(semantic_node)
            return syntax_issues + semantic_issues
        except Exception:
            return syntax_issues
    
    def transform_file(self, file_path: Path, 
                      transformations: List[str] = None,
                      context: Dict[str, Any] = None) -> str:
        """Transform a file and return transformed code."""
        ast = self.parse_file(file_path)
        transformed_ast = self.transformer.transform_tree(ast, context)
        return self.formatter.format_tree(transformed_ast)
    
    # Utility methods
    def get_file_metrics(self, file_path: Path) -> Dict[str, Any]:
        """Get comprehensive metrics for a file."""
        ast = self.parse_file(file_path)
        base_metrics = ast.get_metrics(include_advanced=True)
        
        # Add language-specific metrics
        symbols = self.analyzer.extract_all_symbols(ast)
        
        language_metrics = {
            'symbol_counts': {
                role.value: len(nodes) for role, nodes in symbols.items()
            },
            'language': self.name,
            'features': [f.value for f in self.config.features]
        }
        
        return {**base_metrics, **language_metrics}
    
    def create_nodegroup(self, source: Union[Path, str, TSNode]) -> NodeGroup:
        """Create a NodeGroup from various sources."""
        if isinstance(source, Path):
            ast = self.parse_file(source)
        elif isinstance(source, str):
            ast = self.parse_code(source)
        else:
            ast = source
        
        return NodeGroup.from_tree(ast)
    
    def supports_feature(self, feature: LanguageFeature) -> bool:
        """Check if this language supports a specific feature."""
        return feature in self.config.features
    
    def get_language_info(self) -> Dict[str, Any]:
        """Get comprehensive information about this language."""
        return {
            'name': self.name,
            'display_name': self.display_name,
            'extensions': self.config.extensions,
            'features': [f.value for f in self.config.features],
            'priority': self.config.priority.name,
            'tree_sitter_name': self.config.tree_sitter_name,
            'package_name': self.config.package_name,
            'case_sensitive': self.config.case_sensitive,
            'has_semicolons': self.config.has_semicolons,
            'has_significant_whitespace': self.config.has_significant_whitespace,
            'comment_styles': self.config.comment_styles,
            'components': {
                'parser': self._parser is not None,
                'analyzer': self._analyzer is not None,
                'transformer': self._transformer is not None,
                'formatter': self._formatter is not None,
                'validator': self._validator is not None
            }
        }


class LanguageFactory:
    """Factory for creating language instances."""
    
    def __init__(self):
        self._language_classes: Dict[str, Type[Language]] = {}
        self._instances: Dict[str, Language] = {}
    
    def register_language_class(self, name: str, language_class: Type[Language]):
        """Register a language implementation class."""
        self._language_classes[name] = language_class
    
    def create_language(self, name: str, config: LanguageConfig = None) -> Language:
        """Create a language instance."""
        if name in self._instances:
            return self._instances[name]
        
        if name not in self._language_classes:
            raise ValueError(f"Language class not registered for: {name}")
        
        if config is None:
            from .registry import get_global_registry
            config = get_global_registry().get_language_config(name)
            if config is None:
                raise ValueError(f"No configuration found for language: {name}")
        
        language_class = self._language_classes[name]
        instance = language_class(config)
        self._instances[name] = instance
        
        return instance
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return list(self._language_classes.keys())
    
    def clear_instances(self):
        """Clear cached language instances."""
        self._instances.clear()


# Global factory instance
_global_factory: Optional[LanguageFactory] = None


def get_language_factory() -> LanguageFactory:
    """Get the global language factory."""
    global _global_factory
    if _global_factory is None:
        _global_factory = LanguageFactory()
    return _global_factory


def create_language(name: str, config: LanguageConfig = None) -> Language:
    """Create a language instance using the global factory."""
    return get_language_factory().create_language(name, config)


def register_language_class(name: str, language_class: Type[Language]):
    """Register a language class in the global factory."""
    get_language_factory().register_language_class(name, language_class)


# Utility functions for semantic analysis
def find_semantic_nodes(semantic_node: SemanticNode, role: SemanticRole) -> List[SemanticNode]:
    """Find all nodes with a specific semantic role."""
    results = []
    
    if semantic_node.role == role:
        results.append(semantic_node)
    
    for child in semantic_node.children:
        results.extend(find_semantic_nodes(child, role))
    
    return results


def build_symbol_table(semantic_node: SemanticNode) -> Dict[str, SemanticNode]:
    """Build a symbol table from a semantic node tree."""
    symbol_table = {}
    
    def collect_symbols(node: SemanticNode, scope_prefix: str = ""):
        if node.name:
            qualified_name = f"{scope_prefix}.{node.name}" if scope_prefix else node.name
            symbol_table[qualified_name] = node
            
            # Add to parent scope if it's a scope-creating node
            if node.role in {SemanticRole.CLASS, SemanticRole.FUNCTION, SemanticRole.MODULE}:
                scope_prefix = qualified_name
        
        for child in node.children:
            collect_symbols(child, scope_prefix)
    
    collect_symbols(semantic_node)
    return symbol_table


def extract_dependencies(semantic_node: SemanticNode) -> Set[str]:
    """Extract dependencies (imports) from a semantic node tree."""
    dependencies = set()
    
    import_nodes = find_semantic_nodes(semantic_node, SemanticRole.IMPORT)
    for import_node in import_nodes:
        if import_node.name:
            dependencies.add(import_node.name)
        
        # Extract from attributes if available
        imported_items = import_node.attributes.get('imported_items', [])
        dependencies.update(imported_items)
    
    return dependencies
