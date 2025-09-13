# pydantree/languages/__init__.py
"""Language abstractions, registry, and concrete implementations."""

from .base import (
    Language,
    LanguageAnalyzer,
    SemanticNode,
    SemanticRole,
    create_language,
    get_language,
    get_language_factory,
    register_language_class,
)
from .registry import (
    LanguageConfig,
    LanguageFeature,
    LanguagePriority,
    LanguageRegistry,
    get_global_registry,
    detect_language,
)

# Import and register built-in languages
from .python import PythonLanguage

register_language_class("python", PythonLanguage)


__all__ = [
    # Base Abstractions
    "Language",
    "LanguageAnalyzer",
    "SemanticNode",
    "SemanticRole",
    # Factory & Instantiation
    "create_language",
    "get_language",
    "get_language_factory",
    "register_language_class",
    # Registry & Configuration
    "LanguageConfig",
    "LanguageFeature",
    "LanguagePriority",
    "LanguageRegistry",
    "get_global_registry",
    "detect_language",
]
