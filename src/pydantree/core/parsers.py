# pydantree/core/parsers.py
from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Optional, Dict, Type, List, Set
from queue import Queue, Empty

try:
    from tree_sitter import Language, Parser as _TSParser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

from .nodes import TSNode
from .container import inject
from .config import Config
from ..languages.registry import get_global_registry, LanguageConfig


class ParserPool:
    """Thread-safe pool of tree-sitter parsers for a single language."""

    def __init__(self, language: Language, pool_size: int = 10):
        if not HAS_TREE_SITTER:
            raise ImportError("tree-sitter is required for parsing.")
        self.language = language
        self.pool_size = pool_size
        self._parsers: Queue[_TSParser] = Queue(maxsize=pool_size)
        self._created_count = 0
        self._lock = threading.Lock()

    def get_parser(self) -> _TSParser:
        """Get a parser from the pool, creating a new one if necessary."""
        try:
            return self._parsers.get_nowait()
        except Empty:
            with self._lock:
                if self._created_count < self.pool_size:
                    parser = _TSParser(self.language)
                    #parser.set_language(self.language)
                    self._created_count += 1
                    return parser
            return self._parsers.get(timeout=5.0)

    def return_parser(self, parser: _TSParser) -> None:
        """Return a parser to the pool."""
        try:
            self._parsers.put_nowait(parser)
        except:
            pass  # Pool is full, let parser be garbage collected


class GrammarLoader:
    """Dynamically loads Tree-sitter grammars with caching."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._loaded_languages: Dict[str, Language] = {}
                cls._instance._parser_pools: Dict[str, ParserPool] = {}
        return cls._instance

    def get_language(self, config: LanguageConfig) -> Language:
        """Load and cache a Tree-sitter Language object."""
        if config.name in self._loaded_languages:
            return self._loaded_languages[config.name]

        try:
            # Dynamically import the tree-sitter grammar package
            module_name = config.package_name.replace("-", "_")
            module = __import__(module_name)
            # Some packages have a language() function, others language_typescript() etc.
            lang_func = getattr(module, config.tree_sitter_name, getattr(module, "language"))
            language = Language(lang_func())
            self._loaded_languages[config.name] = language
            return language
        except ImportError as e:
            raise ImportError(
                f"Tree-sitter grammar for '{config.name}' not installed. "
                f"Please run: pip install {config.package_name}"
            ) from e

    def get_parser_pool(self, config: LanguageConfig) -> ParserPool:
        """Get or create a parser pool for a given language configuration."""
        if config.name in self._parser_pools:
            return self._parser_pools[config.name]

        language = self.get_language(config)
        pool = ParserPool(language, pool_size=config.parser_pool_size)
        self._parser_pools[config.name] = pool
        return pool


class Parser:
    """High-performance parser for a single language, using pooling and caching."""

    def __init__(self, language_name: str, config: Optional[Config] = None):
        self.config = config or inject(Config)
        registry = get_global_registry()
        self.language_config = registry.get_language_config(language_name)
        if not self.language_config:
            raise ValueError(f"Language '{language_name}' is not registered.")

        self.language_name = language_name
        self.grammar_loader = GrammarLoader()
        self.parser_pool = self.grammar_loader.get_parser_pool(self.language_config)
        self._parse_cache: Dict[str, TSNode] = {}  # Simple in-memory cache

    def parse(self, text: str, use_cache: bool = True) -> TSNode:
        """Parse text into a Pydantree AST."""
        if use_cache and self.config.cache_enabled:
            text_hash = hashlib.md5(text.encode()).hexdigest()
            if text_hash in self._parse_cache:
                return self._parse_cache[text_hash]

        parser = self.parser_pool.get_parser()
        try:
            byte_text = text.encode("utf-8")
            tree = parser.parse(byte_text)
            result = TSNode.from_tree_sitter(tree.root_node, byte_text)
        finally:
            self.parser_pool.return_parser(parser)

        if use_cache and self.config.cache_enabled:
            self._parse_cache[text_hash] = result
        return result

    def parse_file(self, file_path: Path) -> TSNode:
        """Parse a file with robust encoding detection."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1", errors="ignore")
        return self.parse(content)

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'cache_size': len(self._parse_cache),
            'cache_enabled': self.config.cache_enabled
        }

    def clear_cache(self) -> None:
        """Clear parse cache."""
        self._parse_cache.clear()

    @classmethod
    def for_language(cls, language_name: str) -> Parser:
        """Factory method to create a parser for a specific language."""
        return cls(language_name)


class MultiLanguageParser:
    """Parser that can handle multiple languages with auto-detection."""
    
    def __init__(self, supported_languages: List[str], config: Optional[Config] = None):
        self.config = config or inject(Config)
        self.supported_languages = supported_languages
        self._parsers: Dict[str, Parser] = {}
        self._registry = get_global_registry()
        
        # Pre-create parsers for supported languages
        for language in supported_languages:
            try:
                self._parsers[language] = Parser(language, config)
            except (ImportError, ValueError) as e:
                if self.config.strict_mode:
                    raise
                # Skip unsupported languages in non-strict mode
                continue
    
    def parse(self, text: str, language: Optional[str] = None) -> TSNode:
        """Parse text with optional language hint."""
        if language and language in self._parsers:
            return self._parsers[language].parse(text)
        
        if not language and self.config.auto_detect_language:
            language = self.detect_language_from_content(text)
        
        if not language:
            language = self.config.fallback_language or self.supported_languages[0]
        
        if language not in self._parsers:
            raise ValueError(f"Language '{language}' not supported")
        
        return self._parsers[language].parse(text)
    
    def parse_with_language(self, text: str, language: str) -> TSNode:
        """Parse text with explicit language."""
        if language not in self._parsers:
            raise ValueError(f"Language '{language}' not supported")
        return self._parsers[language].parse(text)
    
    def parse_file(self, file_path: Path, language: Optional[str] = None) -> TSNode:
        """Parse file with language detection."""
        if not language:
            language = self._registry.detect_language(file_path)
        
        if not language:
            language = self.config.fallback_language or self.supported_languages[0]
        
        if language not in self._parsers:
            raise ValueError(f"Language '{language}' not supported for file: {file_path}")
        
        return self._parsers[language].parse_file(file_path)
    
    def detect_language_from_content(self, content: str, file_path: Optional[Path] = None) -> Optional[str]:
        """Detect language from content patterns."""
        # Check file extension first if available
        if file_path:
            detected = self._registry.detect_language(file_path)
            if detected and detected in self._parsers:
                return detected
        
        # Content-based detection using simple heuristics
        content_lower = content.lower()
        
        # Python detection
        if any(pattern in content for pattern in ["def ", "class ", "import ", "from __future__"]):
            if "python" in self._parsers:
                return "python"
        
        # JavaScript/TypeScript detection
        if any(pattern in content for pattern in ["function ", "const ", "let ", "var "]):
            if "typescript" in self._parsers and ("interface " in content or ": " in content):
                return "typescript"
            if "javascript" in self._parsers:
                return "javascript"
        
        # Add more language detection heuristics as needed
        
        return None
    
    def get_supported_languages(self) -> List[str]:
        """Get list of actually supported languages (with working parsers)."""
        return list(self._parsers.keys())
    
    def get_supported_extensions(self) -> Set[str]:
        """Get all supported file extensions."""
        extensions = set()
        for language in self._parsers:
            config = self._registry.get_language_config(language)
            if config:
                extensions.update(config.extensions)
        return extensions
    
    def get_cache_stats(self) -> Dict[str, Dict[str, int]]:
        """Get cache statistics for all parsers."""
        return {
            language: parser.get_cache_stats() 
            for language, parser in self._parsers.items()
        }
    
    def clear_caches(self) -> None:
        """Clear all parser caches."""
        for parser in self._parsers.values():
            parser.clear_cache()


def parse_file(file_path: Path) -> TSNode:
    """Convenience function to parse a file with auto-detected language."""
    print(f"\nGetting parser for file: {file_path}")
    registry = get_global_registry()
    print(f"    Supported languages: {registry}")
    language_name = registry.detect_language(file_path)
    print(f"    Detected language: {language_name}")
    if not language_name:
        raise ValueError(f"Could not detect language for file: {file_path}")
    

    parser = Parser.for_language(language_name)
    print(f"    Using parser for language: {language_name}")
    parsed_output = parser.parse_file(file_path)
    print(f"    Parsed {file_path} into AST with root type: {parsed_output.type_name}\n")
    return parsed_output
