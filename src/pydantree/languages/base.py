# pydantree/languages/base.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Type, Union, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from ..core.nodes import TSNode
from ..core.parsers import Parser
from .registry import LanguageConfig, LanguageFeature


class SemanticRole(Enum):
    """Language-agnostic semantic roles for AST nodes."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    PARAMETER = "parameter"
    MODULE = "module"
    IMPORT = "import"
    # ... and other roles as needed


@dataclass
class SemanticNode:
    """A language-agnostic, semantic representation of a code construct."""

    original_node: TSNode
    role: SemanticRole
    name: Optional[str] = None
    qualified_name: Optional[str] = None
    docstring: Optional[str] = None
    parent_scope: Optional[SemanticNode] = field(default=None, repr=False)
    children: List[SemanticNode] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)


class LanguageAnalyzer(ABC):
    """Abstract base for language-specific semantic analysis."""

    def __init__(self, config: LanguageConfig):
        self.config = config

    @abstractmethod
    def analyze_semantics(self, node: TSNode, scope_stack: List[SemanticNode] | None = None) -> SemanticNode:
        """Recursively analyze a node and its children to build a semantic tree."""
        pass

    @abstractmethod
    def extract_definitions(self, root: TSNode) -> List[SemanticNode]:
        """Extract all major definitions (functions, classes, etc.) from an AST."""
        pass


class Language(ABC):
    """Abstract base class for a complete language implementation."""

    def __init__(self, config: LanguageConfig):
        self.config = config
        self.name = config.name
        self._parser: Optional[Parser] = None
        self._analyzer: Optional[LanguageAnalyzer] = None
        self._initialize_components()

    @abstractmethod
    def _initialize_components(self):
        """Initialize language-specific components like parser and analyzer."""
        pass

    @property
    def parser(self) -> Parser:
        if self._parser is None:
            raise RuntimeError(f"Parser not initialized for {self.name}")
        return self._parser

    @property
    def analyzer(self) -> LanguageAnalyzer:
        if self._analyzer is None:
            raise RuntimeError(f"Analyzer not initialized for {self.name}")
        return self._analyzer

    def parse_file(self, file_path: Path) -> TSNode:
        """Parse a file and return the structural AST."""
        return self.parser.parse_file(file_path)

    def analyze_file(self, file_path: Path) -> SemanticNode:
        """Analyze a file and return the semantic AST."""
        structural_ast = self.parse_file(file_path)
        return self.analyzer.analyze_semantics(structural_ast)


class LanguageFactory:
    """Factory for creating and caching language-specific service instances."""

    def __init__(self):
        self._language_classes: Dict[str, Type[Language]] = {}
        self._instances: Dict[str, Language] = {}

    def register_language_class(self, name: str, language_class: Type[Language]):
        self._language_classes[name] = language_class

    def create_language(self, name: str) -> Language:
        """Create a language instance, using a cached one if available."""
        if name in self._instances:
            return self._instances[name]
        if name not in self._language_classes:
            raise ValueError(f"Language class not registered for: {name}")

        from .registry import get_global_registry

        config = get_global_registry().get_language_config(name)
        if config is None:
            raise ValueError(f"No configuration found for language: {name}")

        instance = self._language_classes[name](config)
        self._instances[name] = instance
        return instance


_global_factory: Optional[LanguageFactory] = None


def get_language_factory() -> LanguageFactory:
    global _global_factory
    if _global_factory is None:
        _global_factory = LanguageFactory()
    return _global_factory


def create_language(name: str) -> Language:
    """Create a language instance using the global factory."""
    return get_language_factory().create_language(name)


def get_language(name: str) -> Language:
    """Alias for create_language for convenience."""
    return create_language(name)


def register_language_class(name: str, language_class: Type[Language]):
    """Register a language implementation in the global factory."""
    get_language_factory().register_language_class(name, language_class)
