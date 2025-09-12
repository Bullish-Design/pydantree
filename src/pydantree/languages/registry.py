# pydantree/languages/registry.py
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Type, Union, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import importlib.util
import pkg_resources

from pydantic import BaseModel, ConfigDict, Field

from ..core.nodes import TSNode


class LanguageFeature(Enum):
    """Standard language features for capability detection."""
    CLASSES = "classes"
    FUNCTIONS = "functions"
    INTERFACES = "interfaces"
    MODULES = "modules"
    GENERICS = "generics"
    ASYNC = "async"
    DECORATORS = "decorators"
    ANNOTATIONS = "annotations"
    INHERITANCE = "inheritance"
    NAMESPACES = "namespaces"
    MACROS = "macros"
    TRAITS = "traits"
    STRUCTS = "structs"
    ENUMS = "enums"
    UNIONS = "unions"


class LanguagePriority(Enum):
    """Language detection priority levels."""
    CRITICAL = 100
    HIGH = 80
    NORMAL = 60
    LOW = 40
    FALLBACK = 20


@dataclass
class LanguageConfig:
    """Enhanced configuration for a supported language."""
    name: str
    display_name: str
    extensions: List[str]
    tree_sitter_name: str
    package_name: Optional[str] = None
    node_types_path: Optional[Path] = None
    grammar_version: Optional[str] = None
    features: Set[LanguageFeature] = field(default_factory=set)
    priority: LanguagePriority = LanguagePriority.NORMAL
    
    # Detection patterns
    content_patterns: List[str] = field(default_factory=list)
    shebang_patterns: List[str] = field(default_factory=list)
    filename_patterns: List[str] = field(default_factory=list)
    
    # Language-specific settings
    case_sensitive: bool = True
    has_semicolons: bool = True
    has_significant_whitespace: bool = False
    comment_styles: List[str] = field(default_factory=lambda: ["//", "#"])
    
    # Performance settings
    max_file_size_mb: int = 50
    enable_caching: bool = True
    parser_pool_size: int = 10
    
    # Integration settings
    language_server_command: Optional[str] = None
    formatter_command: Optional[str] = None
    linter_command: Optional[str] = None
    
    def __post_init__(self):
        if isinstance(self.features, (list, tuple)):
            self.features = set(self.features)
        if isinstance(self.priority, str):
            self.priority = LanguagePriority[self.priority.upper()]


class LanguageDetector:
    """Intelligent language detection with multiple strategies."""
    
    def __init__(self):
        self._extension_cache: Dict[str, str] = {}
        self._content_cache: Dict[str, str] = {}
        self._cache_lock = threading.RLock()
    
    def detect_from_path(self, file_path: Path, configs: Dict[str, LanguageConfig]) -> Optional[str]:
        """Detect language from file path with caching."""
        extension = file_path.suffix.lower()
        
        with self._cache_lock:
            if extension in self._extension_cache:
                return self._extension_cache[extension]
        
        # Check filename patterns first
        filename = file_path.name.lower()
        candidates = []
        
        for lang_name, config in configs.items():
            # Exact filename matches
            if filename in [p.lower() for p in config.filename_patterns]:
                candidates.append((config.priority.value, lang_name))
                continue
            
            # Extension matches
            if extension in config.extensions:
                candidates.append((config.priority.value, lang_name))
        
        if candidates:
            # Return highest priority match
            candidates.sort(reverse=True)
            result = candidates[0][1]
            
            with self._cache_lock:
                self._extension_cache[extension] = result
            return result
        
        return None
    
    def detect_from_content(self, content: str, file_path: Optional[Path] = None, 
                          configs: Dict[str, LanguageConfig] = None) -> Optional[str]:
        """Advanced content-based language detection."""
        if not content.strip():
            return None
        
        # Cache key based on content hash
        import hashlib
        content_hash = hashlib.md5(content[:2000].encode()).hexdigest()
        
        with self._cache_lock:
            if content_hash in self._content_cache:
                return self._content_cache[content_hash]
        
        configs = configs or {}
        candidates = []
        content_start = content[:2000].strip()
        lines = content_start.split('\n', 10)  # First 10 lines
        
        # 1. Shebang detection (highest priority)
        if lines and lines[0].startswith('#!'):
            shebang = lines[0].lower()
            for lang_name, config in configs.items():
                for pattern in config.shebang_patterns:
                    if pattern.lower() in shebang:
                        candidates.append((LanguagePriority.CRITICAL.value, lang_name))
        
        # 2. Content pattern matching
        for lang_name, config in configs.items():
            score = 0
            
            for pattern in config.content_patterns:
                if pattern in content_start:
                    score += 2
                # Case-insensitive fallback for non-case-sensitive languages
                elif not config.case_sensitive and pattern.lower() in content_start.lower():
                    score += 1
            
            if score > 0:
                # Boost score by priority
                final_score = score * (config.priority.value / 100)
                candidates.append((final_score, lang_name))
        
        # 3. Advanced pattern analysis
        advanced_candidates = self._advanced_content_analysis(content_start, configs)
        candidates.extend(advanced_candidates)
        
        if candidates:
            # Return highest scoring match
            candidates.sort(reverse=True)
            result = candidates[0][1]
            
            with self._cache_lock:
                self._content_cache[content_hash] = result
            return result
        
        return None
    
    def _advanced_content_analysis(self, content: str, configs: Dict[str, LanguageConfig]) -> List[Tuple[float, str]]:
        """Advanced heuristic analysis for ambiguous cases."""
        candidates = []
        
        # Character frequency analysis
        char_stats = self._analyze_character_frequency(content)
        
        # Language-specific heuristics
        for lang_name, config in configs.items():
            score = 0
            
            # Whitespace significance
            if config.has_significant_whitespace:
                if char_stats.get('indentation_consistency', 0) > 0.8:
                    score += 10
            
            # Semicolon usage
            if config.has_semicolons:
                semicolon_ratio = char_stats.get('semicolon_ratio', 0)
                if semicolon_ratio > 0.1:
                    score += 5
                elif semicolon_ratio == 0 and len(content) > 500:
                    score -= 5  # Penalty for missing semicolons in languages that use them
            
            # Case sensitivity patterns
            if config.case_sensitive:
                if char_stats.get('camelCase_ratio', 0) > 0.3:
                    score += 3
            
            # Comment style detection
            for comment_style in config.comment_styles:
                if comment_style in content:
                    score += 2
            
            if score > 0:
                candidates.append((score, lang_name))
        
        return candidates
    
    def _analyze_character_frequency(self, content: str) -> Dict[str, float]:
        """Analyze character frequency and patterns for language detection."""
        lines = content.split('\n')
        total_chars = len(content)
        
        if total_chars == 0:
            return {}
        
        stats = {
            'semicolon_ratio': content.count(';') / total_chars,
            'brace_ratio': (content.count('{') + content.count('}')) / total_chars,
            'paren_ratio': (content.count('(') + content.count(')')) / total_chars,
        }
        
        # Indentation analysis
        if lines:
            indented_lines = [line for line in lines if line.startswith((' ', '\t'))]
            stats['indentation_ratio'] = len(indented_lines) / len(lines)
            
            # Check indentation consistency (spaces vs tabs)
            space_indents = sum(1 for line in indented_lines if line.startswith(' '))
            tab_indents = sum(1 for line in indented_lines if line.startswith('\t'))
            if indented_lines:
                stats['indentation_consistency'] = max(space_indents, tab_indents) / len(indented_lines)
        
        # Case pattern analysis
        import re
        camelCase_matches = len(re.findall(r'[a-z][A-Z]', content))
        snake_case_matches = len(re.findall(r'[a-z]_[a-z]', content))
        
        if camelCase_matches + snake_case_matches > 0:
            stats['camelCase_ratio'] = camelCase_matches / (camelCase_matches + snake_case_matches)
        
        return stats
    
    def clear_cache(self):
        """Clear detection caches."""
        with self._cache_lock:
            self._extension_cache.clear()
            self._content_cache.clear()


class LanguageRegistry:
    """Enhanced registry for language configurations with plugin support."""
    
    def __init__(self):
        self._configs: Dict[str, LanguageConfig] = {}
        self._detector = LanguageDetector()
        self._lock = threading.RLock()
        self._plugin_handlers: Dict[str, Callable] = {}
        
        # Load built-in languages
        self._load_builtin_languages()
    
    def _load_builtin_languages(self):
        """Load built-in language configurations."""
        builtin_configs = {
            "python": LanguageConfig(
                name="python",
                display_name="Python",
                extensions=[".py", ".pyx", ".pyi", ".pyw"],
                tree_sitter_name="python",
                package_name="tree-sitter-python",
                features={
                    LanguageFeature.CLASSES, LanguageFeature.FUNCTIONS,
                    LanguageFeature.MODULES, LanguageFeature.ASYNC,
                    LanguageFeature.DECORATORS, LanguageFeature.ANNOTATIONS,
                    LanguageFeature.INHERITANCE
                },
                priority=LanguagePriority.HIGH,
                content_patterns=[
                    "def ", "class ", "import ", "from ", "__init__",
                    "if __name__ == \"__main__\":", "self.", "@"
                ],
                shebang_patterns=["python", "python3"],
                filename_patterns=["__init__.py", "setup.py", "conftest.py"],
                has_significant_whitespace=True,
                has_semicolons=False,
                comment_styles=["#"]
            ),
            
            "javascript": LanguageConfig(
                name="javascript",
                display_name="JavaScript",
                extensions=[".js", ".mjs", ".cjs", ".jsx"],
                tree_sitter_name="javascript",
                package_name="tree-sitter-javascript",
                features={
                    LanguageFeature.CLASSES, LanguageFeature.FUNCTIONS,
                    LanguageFeature.MODULES, LanguageFeature.ASYNC
                },
                priority=LanguagePriority.HIGH,
                content_patterns=[
                    "function ", "var ", "let ", "const ", "=>", "require(",
                    "module.exports", "console.log", "&&", "||", "class "
                ],
                shebang_patterns=["node", "javascript"],
                filename_patterns=["package.json", "webpack.config.js"],
                comment_styles=["//", "/*"]
            ),
            
            "typescript": LanguageConfig(
                name="typescript",
                display_name="TypeScript",
                extensions=[".ts", ".tsx", ".d.ts"],
                tree_sitter_name="typescript",
                package_name="tree-sitter-typescript",
                features={
                    LanguageFeature.CLASSES, LanguageFeature.FUNCTIONS,
                    LanguageFeature.INTERFACES, LanguageFeature.MODULES,
                    LanguageFeature.GENERICS, LanguageFeature.ANNOTATIONS,
                    LanguageFeature.ASYNC
                },
                priority=LanguagePriority.HIGH,
                content_patterns=[
                    "interface ", ": string", ": number", ": boolean",
                    "type ", "enum ", "declare ", "namespace ",
                    "implements ", "extends "
                ],
                filename_patterns=["tsconfig.json"],
                comment_styles=["//", "/*"]
            ),
            
            "rust": LanguageConfig(
                name="rust",
                display_name="Rust",
                extensions=[".rs"],
                tree_sitter_name="rust",
                package_name="tree-sitter-rust",
                features={
                    LanguageFeature.STRUCTS, LanguageFeature.ENUMS,
                    LanguageFeature.TRAITS, LanguageFeature.MACROS,
                    LanguageFeature.FUNCTIONS, LanguageFeature.MODULES
                },
                priority=LanguagePriority.NORMAL,
                content_patterns=[
                    "fn ", "let ", "mut ", "struct ", "impl ", "match ",
                    "pub ", "use ", "::", "cargo", "println!"
                ],
                filename_patterns=["Cargo.toml", "main.rs", "lib.rs"],
                comment_styles=["//", "/*"]
            ),
            
            "go": LanguageConfig(
                name="go",
                display_name="Go",
                extensions=[".go"],
                tree_sitter_name="go",
                package_name="tree-sitter-go",
                features={
                    LanguageFeature.STRUCTS, LanguageFeature.INTERFACES,
                    LanguageFeature.FUNCTIONS, LanguageFeature.MODULES
                },
                priority=LanguagePriority.NORMAL,
                content_patterns=[
                    "package ", "func ", "import ", "var ", "type ",
                    "go ", "chan ", "defer ", "goroutine"
                ],
                filename_patterns=["go.mod", "go.sum"],
                comment_styles=["//", "/*"]
            ),
            
            "java": LanguageConfig(
                name="java",
                display_name="Java",
                extensions=[".java"],
                tree_sitter_name="java",
                package_name="tree-sitter-java",
                features={
                    LanguageFeature.CLASSES, LanguageFeature.INTERFACES,
                    LanguageFeature.INHERITANCE, LanguageFeature.ANNOTATIONS,
                    LanguageFeature.GENERICS
                },
                priority=LanguagePriority.NORMAL,
                content_patterns=[
                    "public class", "private ", "protected ", "static ",
                    "import java", "package ", "@Override", "extends ", "implements "
                ],
                comment_styles=["//", "/*"]
            ),
            
            "json": LanguageConfig(
                name="json",
                display_name="JSON",
                extensions=[".json", ".jsonl", ".json5"],
                tree_sitter_name="json",
                package_name="tree-sitter-json",
                features=set(),
                priority=LanguagePriority.LOW,
                content_patterns=['":', '",', '"}', '"['],
                has_semicolons=False,
                comment_styles=[]
            )
        }
        
        for config in builtin_configs.values():
            self.register_language(config)
    
    def register_language(self, config: LanguageConfig) -> None:
        """Register a language configuration."""
        with self._lock:
            self._configs[config.name] = config
    
    def get_language_config(self, language: str) -> Optional[LanguageConfig]:
        """Get configuration for language."""
        with self._lock:
            return self._configs.get(language.lower())
    
    def get_all_configs(self) -> Dict[str, LanguageConfig]:
        """Get all language configurations."""
        with self._lock:
            return self._configs.copy()
    
    def detect_language(self, file_path: Path) -> Optional[str]:
        """Detect language from file path."""
        return self._detector.detect_from_path(file_path, self._configs)
    
    def detect_from_content(self, content: str, file_path: Optional[Path] = None) -> Optional[str]:
        """Detect language from content."""
        return self._detector.detect_from_content(content, file_path, self._configs)
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language names sorted by priority."""
        with self._lock:
            configs = list(self._configs.items())
            configs.sort(key=lambda x: x[1].priority.value, reverse=True)
            return [name for name, _ in configs]
    
    def get_supported_extensions(self) -> Dict[str, List[str]]:
        """Get mapping of languages to their extensions."""
        with self._lock:
            result = {}
            for lang_name, config in self._configs.items():
                result[lang_name] = config.extensions.copy()
            return result
    
    def get_languages_by_feature(self, feature: LanguageFeature) -> List[str]:
        """Get languages that support a specific feature."""
        with self._lock:
            return [
                name for name, config in self._configs.items()
                if feature in config.features
            ]
    
    def search_languages(self, 
                        query: str,
                        search_extensions: bool = True,
                        search_patterns: bool = True,
                        search_names: bool = True) -> List[str]:
        """Search for languages matching query."""
        query_lower = query.lower()
        matches = []
        
        with self._lock:
            for lang_name, config in self._configs.items():
                score = 0
                
                if search_names:
                    if query_lower in lang_name.lower():
                        score += 10
                    if query_lower in config.display_name.lower():
                        score += 8
                
                if search_extensions:
                    if any(query_lower in ext.lower() for ext in config.extensions):
                        score += 5
                
                if search_patterns:
                    if any(query_lower in pattern.lower() for pattern in config.content_patterns):
                        score += 3
                
                if score > 0:
                    matches.append((score, lang_name))
        
        # Sort by score and return language names
        matches.sort(reverse=True)
        return [lang_name for _, lang_name in matches]
    
    def register_plugin_handler(self, plugin_name: str, handler: Callable) -> None:
        """Register a plugin handler for language detection."""
        with self._lock:
            self._plugin_handlers[plugin_name] = handler
    
    def load_from_file(self, config_path: Path) -> None:
        """Load language configurations from JSON/YAML file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        if config_path.suffix.lower() == '.json':
            with config_path.open() as f:
                data = json.load(f)
        elif config_path.suffix.lower() in ['.yaml', '.yml']:
            try:
                import yaml
                with config_path.open() as f:
                    data = yaml.safe_load(f)
            except ImportError:
                raise ImportError("PyYAML required for YAML config files")
        else:
            raise ValueError(f"Unsupported config file format: {config_path.suffix}")
        
        # Parse and register configurations
        for lang_name, lang_data in data.get('languages', {}).items():
            config = self._parse_config_dict(lang_name, lang_data)
            self.register_language(config)
    
    def _parse_config_dict(self, name: str, data: Dict[str, Any]) -> LanguageConfig:
        """Parse configuration dictionary into LanguageConfig."""
        # Convert features list to enum set
        features_data = data.get('features', [])
        features = set()
        for feature_name in features_data:
            try:
                features.add(LanguageFeature(feature_name))
            except ValueError:
                # Skip unknown features
                pass
        
        # Convert priority
        priority_str = data.get('priority', 'NORMAL')
        try:
            priority = LanguagePriority[priority_str.upper()]
        except KeyError:
            priority = LanguagePriority.NORMAL
        
        return LanguageConfig(
            name=name,
            display_name=data.get('display_name', name.title()),
            extensions=data.get('extensions', []),
            tree_sitter_name=data.get('tree_sitter_name', name),
            package_name=data.get('package_name'),
            features=features,
            priority=priority,
            content_patterns=data.get('content_patterns', []),
            shebang_patterns=data.get('shebang_patterns', []),
            filename_patterns=data.get('filename_patterns', []),
            case_sensitive=data.get('case_sensitive', True),
            has_semicolons=data.get('has_semicolons', True),
            has_significant_whitespace=data.get('has_significant_whitespace', False),
            comment_styles=data.get('comment_styles', ['//'])
        )
    
    def export_config(self, output_path: Path, languages: Optional[List[str]] = None) -> None:
        """Export language configurations to file."""
        languages = languages or list(self._configs.keys())
        
        export_data = {
            'languages': {}
        }
        
        with self._lock:
            for lang_name in languages:
                if lang_name in self._configs:
                    config = self._configs[lang_name]
                    export_data['languages'][lang_name] = {
                        'display_name': config.display_name,
                        'extensions': config.extensions,
                        'tree_sitter_name': config.tree_sitter_name,
                        'package_name': config.package_name,
                        'features': [f.value for f in config.features],
                        'priority': config.priority.name,
                        'content_patterns': config.content_patterns,
                        'shebang_patterns': config.shebang_patterns,
                        'filename_patterns': config.filename_patterns,
                        'case_sensitive': config.case_sensitive,
                        'has_semicolons': config.has_semicolons,
                        'has_significant_whitespace': config.has_significant_whitespace,
                        'comment_styles': config.comment_styles
                    }
        
        if output_path.suffix.lower() == '.json':
            with output_path.open('w') as f:
                json.dump(export_data, f, indent=2)
        elif output_path.suffix.lower() in ['.yaml', '.yml']:
            try:
                import yaml
                with output_path.open('w') as f:
                    yaml.dump(export_data, f, default_flow_style=False)
            except ImportError:
                raise ImportError("PyYAML required for YAML export")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            total_languages = len(self._configs)
            
            # Feature distribution
            feature_counts = {}
            for feature in LanguageFeature:
                feature_counts[feature.value] = len(self.get_languages_by_feature(feature))
            
            # Priority distribution
            priority_counts = {}
            for config in self._configs.values():
                priority_name = config.priority.name
                priority_counts[priority_name] = priority_counts.get(priority_name, 0) + 1
            
            # Extension statistics
            total_extensions = sum(len(config.extensions) for config in self._configs.values())
            
            return {
                'total_languages': total_languages,
                'total_extensions': total_extensions,
                'feature_distribution': feature_counts,
                'priority_distribution': priority_counts,
                'languages': list(self._configs.keys()),
                'cache_stats': {
                    'extension_cache_size': len(self._detector._extension_cache),
                    'content_cache_size': len(self._detector._content_cache)
                }
            }
    
    def clear_caches(self) -> None:
        """Clear all internal caches."""
        self._detector.clear_cache()


# Global registry instance
_global_registry: Optional[LanguageRegistry] = None
_registry_lock = threading.Lock()


def get_global_registry() -> LanguageRegistry:
    """Get the global language registry instance."""
    global _global_registry
    
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = LanguageRegistry()
    
    return _global_registry


def register_language(config: LanguageConfig) -> None:
    """Register a language in the global registry."""
    get_global_registry().register_language(config)


def detect_language(file_path: Path) -> Optional[str]:
    """Detect language using global registry."""
    return get_global_registry().detect_language(file_path)


def detect_from_content(content: str, file_path: Optional[Path] = None) -> Optional[str]:
    """Detect language from content using global registry."""
    return get_global_registry().detect_from_content(content, file_path)


def get_supported_languages() -> List[str]:
    """Get supported languages from global registry."""
    return get_global_registry().get_supported_languages()
