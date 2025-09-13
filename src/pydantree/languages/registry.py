# pydantree/languages/registry.py
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum


class LanguageFeature(Enum):
    """Standard language features for capability detection."""

    CLASSES = "classes"
    FUNCTIONS = "functions"
    MODULES = "modules"
    ASYNC = "async"
    DECORATORS = "decorators"


class LanguagePriority(Enum):
    """Language detection priority levels."""

    HIGH = 80
    NORMAL = 60
    LOW = 40


@dataclass
class LanguageConfig:
    """Enhanced configuration for a supported language."""

    name: str
    display_name: str
    extensions: List[str]
    tree_sitter_name: str
    package_name: str
    features: Set[LanguageFeature] = field(default_factory=set)
    priority: LanguagePriority = LanguagePriority.NORMAL
    content_patterns: List[str] = field(default_factory=list)
    parser_pool_size: int = 10


class LanguageRegistry:
    """A thread-safe, centralized registry for language configurations."""

    def __init__(self):
        self._configs: Dict[str, LanguageConfig] = {}
        self._extension_map: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._load_builtin_languages()

    def _load_builtin_languages(self):
        """Loads default configurations for common languages."""
        python_config = LanguageConfig(
            name="python",
            display_name="Python",
            extensions=[".py", ".pyi"],
            tree_sitter_name="python",
            package_name="tree-sitter-python",
            features={
                LanguageFeature.CLASSES,
                LanguageFeature.FUNCTIONS,
                LanguageFeature.MODULES,
                LanguageFeature.ASYNC,
                LanguageFeature.DECORATORS,
            },
            priority=LanguagePriority.HIGH,
            content_patterns=["def ", "class ", "import ", "from __future__"],
        )
        self.register_language(python_config)

    def register_language(self, config: LanguageConfig):
        """Register or update a language configuration."""
        with self._lock:
            self._configs[config.name] = config
            for ext in config.extensions:
                # Higher priority languages override lower ones for shared extensions
                if (
                    ext not in self._extension_map
                    or config.priority.value > self._configs[self._extension_map[ext]].priority.value
                ):
                    self._extension_map[ext] = config.name

    def get_language_config(self, language: str) -> Optional[LanguageConfig]:
        """Get the configuration for a specific language."""
        with self._lock:
            return self._configs.get(language.lower())

    def detect_language(self, file_path: Path) -> Optional[str]:
        """Detect language from file extension with priority."""
        return self._extension_map.get(file_path.suffix.lower())

    def get_supported_languages(self) -> List[str]:
        """Get a list of all supported language names."""
        with self._lock:
            return list(self._configs.keys())


_global_registry: Optional[LanguageRegistry] = None
_registry_lock = threading.Lock()


def get_global_registry() -> LanguageRegistry:
    """Get the singleton instance of the LanguageRegistry."""
    global _global_registry
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = LanguageRegistry()
    return _global_registry


def detect_language(file_path: Path) -> Optional[str]:
    """Convenience function to detect language using the global registry."""
    return get_global_registry().detect_language(file_path)


def get_supported_languages() -> List[str]:
    """Convenience function to get supported languages."""
    return get_global_registry().get_supported_languages()
